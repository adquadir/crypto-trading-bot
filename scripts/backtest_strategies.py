#!/usr/bin/env python3
"""
Comprehensive strategy backtesting system.
Tests strategies against historical data to measure accuracy.
"""

import asyncio
import argparse
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
import json
from pathlib import Path
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.market_data.exchange_client import ExchangeClient
from src.signals.signal_generator import SignalGenerator
from src.strategy.dynamic_config import StrategyConfig
from src.utils.config import load_config
from src.models.trading import TradingOpportunity

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StrategyBacktester:
    def __init__(self):
        self.config = load_config()
        self.exchange_client = ExchangeClient(self.config)
        self.strategy_config = StrategyConfig()
        self.signal_generator = SignalGenerator()
        self.results = {}
        
    async def initialize(self):
        """Initialize exchange client."""
        await self.exchange_client.initialize()
        
    async def backtest_strategy(
        self, 
        symbols: List[str], 
        start_date: datetime, 
        end_date: datetime,
        strategy_profile: str = "default"
    ) -> Dict:
        """Backtest strategy on historical data."""
        logger.info(f"Starting backtest for {len(symbols)} symbols from {start_date} to {end_date}")
        
        # Set strategy profile
        self.signal_generator.set_strategy_profile(strategy_profile)
        
        all_results = {}
        
        for symbol in symbols:
            logger.info(f"Backtesting {symbol}...")
            symbol_results = await self._backtest_symbol(
                symbol, start_date, end_date
            )
            all_results[symbol] = symbol_results
            
        # Calculate overall metrics
        overall_metrics = self._calculate_overall_metrics(all_results)
        
        return {
            'strategy_profile': strategy_profile,
            'period': f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            'symbols': symbols,
            'individual_results': all_results,
            'overall_metrics': overall_metrics
        }
        
    async def _backtest_symbol(
        self, 
        symbol: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict:
        """Backtest a single symbol."""
        try:
            # Get historical data
            historical_data = await self._get_historical_data(
                symbol, start_date, end_date
            )
            
            if not historical_data:
                logger.warning(f"No historical data for {symbol}")
                return {}
                
            # Generate signals on historical data
            signals = await self._generate_historical_signals(symbol, historical_data)
            
            # Simulate trades
            trades = self._simulate_trades(signals, historical_data)
            
            # Calculate metrics
            metrics = self._calculate_symbol_metrics(trades)
            
            return {
                'total_signals': len(signals),
                'total_trades': len(trades),
                'metrics': metrics,
                'trades': trades[:10]  # Store first 10 trades for analysis
            }
            
        except Exception as e:
            logger.error(f"Error backtesting {symbol}: {e}")
            return {}
            
    async def _get_historical_data(
        self, 
        symbol: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[Dict]:
        """Get historical candlestick data."""
        try:
            # Calculate number of periods needed
            days = (end_date - start_date).days
            periods_per_day = 24 * 4  # 15-minute candles
            total_periods = min(days * periods_per_day, 1000)  # API limit
            
            # Get data in chunks if needed
            all_data = []
            current_end = end_date
            
            while len(all_data) < total_periods and current_end > start_date:
                chunk_data = await self.exchange_client.get_historical_data(
                    symbol=symbol,
                    interval='15m',
                    limit=min(500, total_periods - len(all_data))
                )
                
                if not chunk_data:
                    break
                    
                # Filter by date range
                filtered_data = [
                    candle for candle in chunk_data
                    if start_date.timestamp() * 1000 <= candle['openTime'] <= end_date.timestamp() * 1000
                ]
                
                all_data.extend(filtered_data)
                
                # Update for next chunk
                if chunk_data:
                    current_end = datetime.fromtimestamp(chunk_data[0]['openTime'] / 1000)
                else:
                    break
                    
            # Sort by time
            all_data.sort(key=lambda x: x['openTime'])
            
            logger.info(f"Retrieved {len(all_data)} historical candles for {symbol}")
            return all_data
            
        except Exception as e:
            logger.error(f"Error getting historical data for {symbol}: {e}")
            return []
            
    async def _generate_historical_signals(
        self, 
        symbol: str, 
        historical_data: List[Dict]
    ) -> List[Dict]:
        """Generate signals on historical data."""
        signals = []
        
        # Process data in sliding windows
        window_size = 50  # Need enough data for indicators
        
        for i in range(window_size, len(historical_data)):
            try:
                # Create market data window
                window_data = historical_data[i-window_size:i+1]
                
                market_data = {
                    'symbol': symbol,
                    'klines': window_data,
                    'current_price': float(window_data[-1]['close']),
                    'volume_24h': sum(float(k['volume']) for k in window_data[-96:]),  # Last 24h
                    'timestamp': window_data[-1]['openTime']
                }
                
                # Generate signal
                signal = await asyncio.to_thread(
                    self.signal_generator.generate_signal, market_data
                )
                
                if signal and signal.get('signal_type') != 'NEUTRAL':
                    signal['timestamp'] = market_data['timestamp']
                    signal['symbol'] = symbol
                    signals.append(signal)
                    
            except Exception as e:
                logger.debug(f"Error generating signal at index {i}: {e}")
                continue
                
        logger.info(f"Generated {len(signals)} signals for {symbol}")
        return signals
        
    def _simulate_trades(
        self, 
        signals: List[Dict], 
        historical_data: List[Dict]
    ) -> List[Dict]:
        """Simulate trade execution on historical data."""
        trades = []
        
        # Create price lookup for fast access
        price_data = {
            candle['openTime']: {
                'open': float(candle['open']),
                'high': float(candle['high']),
                'low': float(candle['low']),
                'close': float(candle['close'])
            }
            for candle in historical_data
        }
        
        timestamps = sorted(price_data.keys())
        
        for signal in signals:
            try:
                trade = self._simulate_single_trade(signal, price_data, timestamps)
                if trade:
                    trades.append(trade)
            except Exception as e:
                logger.debug(f"Error simulating trade: {e}")
                continue
                
        return trades
        
    def _simulate_single_trade(
        self, 
        signal: Dict, 
        price_data: Dict, 
        timestamps: List[int]
    ) -> Optional[Dict]:
        """Simulate a single trade execution."""
        try:
            entry_time = signal['timestamp']
            entry_price = signal['entry_price']
            take_profit = signal['take_profit']
            stop_loss = signal['stop_loss']
            direction = signal['direction']
            
            # Find entry timestamp index
            entry_idx = None
            for i, ts in enumerate(timestamps):
                if ts >= entry_time:
                    entry_idx = i
                    break
                    
            if entry_idx is None:
                return None
                
            # Simulate trade execution
            max_holding_periods = 96  # Max 24 hours (15min candles)
            
            for i in range(entry_idx + 1, min(entry_idx + max_holding_periods, len(timestamps))):
                timestamp = timestamps[i]
                candle = price_data[timestamp]
                
                # Check for exit conditions
                if direction == 'LONG':
                    if candle['high'] >= take_profit:
                        # Take profit hit
                        return {
                            'entry_time': entry_time,
                            'exit_time': timestamp,
                            'entry_price': entry_price,
                            'exit_price': take_profit,
                            'direction': direction,
                            'pnl': take_profit - entry_price,
                            'pnl_pct': (take_profit - entry_price) / entry_price * 100,
                            'outcome': 'win',
                            'exit_reason': 'take_profit'
                        }
                    elif candle['low'] <= stop_loss:
                        # Stop loss hit
                        return {
                            'entry_time': entry_time,
                            'exit_time': timestamp,
                            'entry_price': entry_price,
                            'exit_price': stop_loss,
                            'direction': direction,
                            'pnl': stop_loss - entry_price,
                            'pnl_pct': (stop_loss - entry_price) / entry_price * 100,
                            'outcome': 'loss',
                            'exit_reason': 'stop_loss'
                        }
                else:  # SHORT
                    if candle['low'] <= take_profit:
                        # Take profit hit
                        return {
                            'entry_time': entry_time,
                            'exit_time': timestamp,
                            'entry_price': entry_price,
                            'exit_price': take_profit,
                            'direction': direction,
                            'pnl': entry_price - take_profit,
                            'pnl_pct': (entry_price - take_profit) / entry_price * 100,
                            'outcome': 'win',
                            'exit_reason': 'take_profit'
                        }
                    elif candle['high'] >= stop_loss:
                        # Stop loss hit
                        return {
                            'entry_time': entry_time,
                            'exit_time': timestamp,
                            'entry_price': entry_price,
                            'exit_price': stop_loss,
                            'direction': direction,
                            'pnl': entry_price - stop_loss,
                            'pnl_pct': (entry_price - stop_loss) / entry_price * 100,
                            'outcome': 'loss',
                            'exit_reason': 'stop_loss'
                        }
                        
            # Trade timed out - exit at market
            final_candle = price_data[timestamps[min(entry_idx + max_holding_periods - 1, len(timestamps) - 1)]]
            exit_price = final_candle['close']
            
            if direction == 'LONG':
                pnl = exit_price - entry_price
            else:
                pnl = entry_price - exit_price
                
            return {
                'entry_time': entry_time,
                'exit_time': timestamps[min(entry_idx + max_holding_periods - 1, len(timestamps) - 1)],
                'entry_price': entry_price,
                'exit_price': exit_price,
                'direction': direction,
                'pnl': pnl,
                'pnl_pct': pnl / entry_price * 100,
                'outcome': 'win' if pnl > 0 else 'loss',
                'exit_reason': 'timeout'
            }
            
        except Exception as e:
            logger.debug(f"Error in single trade simulation: {e}")
            return None
            
    def _calculate_symbol_metrics(self, trades: List[Dict]) -> Dict:
        """Calculate performance metrics for a symbol."""
        if not trades:
            return {}
            
        total_trades = len(trades)
        winning_trades = len([t for t in trades if t['outcome'] == 'win'])
        losing_trades = total_trades - winning_trades
        
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        total_pnl = sum(t['pnl'] for t in trades)
        avg_pnl = total_pnl / total_trades
        
        winning_pnl = sum(t['pnl'] for t in trades if t['outcome'] == 'win')
        losing_pnl = sum(t['pnl'] for t in trades if t['outcome'] == 'loss')
        
        avg_win = winning_pnl / winning_trades if winning_trades > 0 else 0
        avg_loss = losing_pnl / losing_trades if losing_trades > 0 else 0
        
        profit_factor = abs(winning_pnl / losing_pnl) if losing_pnl != 0 else float('inf')
        
        # Calculate Sharpe ratio
        returns = [t['pnl_pct'] for t in trades]
        sharpe_ratio = np.mean(returns) / np.std(returns) if len(returns) > 1 and np.std(returns) > 0 else 0
        
        # Calculate maximum drawdown
        cumulative_pnl = np.cumsum([t['pnl'] for t in trades])
        max_drawdown = 0
        peak = cumulative_pnl[0] if len(cumulative_pnl) > 0 else 0
        
        for pnl in cumulative_pnl:
            if pnl > peak:
                peak = pnl
            drawdown = (peak - pnl) / abs(peak) if peak != 0 else 0
            max_drawdown = max(max_drawdown, drawdown)
            
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'avg_pnl': avg_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown
        }
        
    def _calculate_overall_metrics(self, all_results: Dict) -> Dict:
        """Calculate overall metrics across all symbols."""
        all_trades = []
        
        for symbol_results in all_results.values():
            if 'trades' in symbol_results:
                all_trades.extend(symbol_results.get('trades', []))
                
        if not all_trades:
            return {}
            
        return self._calculate_symbol_metrics(all_trades)
        
    def save_results(self, results: Dict, filename: str = None):
        """Save backtest results to file."""
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"backtest_results_{timestamp}.json"
            
        results_dir = Path('data/backtest_results')
        results_dir.mkdir(parents=True, exist_ok=True)
        
        filepath = results_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2, default=str)
            
        logger.info(f"Results saved to {filepath}")
        return filepath

async def main():
    parser = argparse.ArgumentParser(description='Backtest trading strategies')
    parser.add_argument('--symbols', default='BTC/USDT,ETH/USDT,ADA/USDT', 
                       help='Comma-separated list of symbols')
    parser.add_argument('--days', type=int, default=30, 
                       help='Number of days to backtest')
    parser.add_argument('--profile', default='default', 
                       help='Strategy profile to use')
    
    args = parser.parse_args()
    
    symbols = [s.strip() for s in args.symbols.split(',')]
    end_date = datetime.now()
    start_date = end_date - timedelta(days=args.days)
    
    backtester = StrategyBacktester()
    await backtester.initialize()
    
    logger.info(f"Starting backtest for {args.days} days with profile '{args.profile}'")
    
    results = await backtester.backtest_strategy(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        strategy_profile=args.profile
    )
    
    # Print summary
    overall = results.get('overall_metrics', {})
    if overall:
        print(f"\n{'='*50}")
        print(f"BACKTEST RESULTS SUMMARY")
        print(f"{'='*50}")
        print(f"Period: {results['period']}")
        print(f"Strategy: {results['strategy_profile']}")
        print(f"Symbols: {', '.join(results['symbols'])}")
        print(f"")
        print(f"Total Trades: {overall.get('total_trades', 0)}")
        print(f"Win Rate: {overall.get('win_rate', 0):.1%}")
        print(f"Profit Factor: {overall.get('profit_factor', 0):.2f}")
        print(f"Sharpe Ratio: {overall.get('sharpe_ratio', 0):.2f}")
        print(f"Max Drawdown: {overall.get('max_drawdown', 0):.1%}")
        print(f"Total PnL: ${overall.get('total_pnl', 0):.2f}")
        print(f"Avg Trade: ${overall.get('avg_pnl', 0):.2f}")
        
        # Individual symbol results
        print(f"\nINDIVIDUAL SYMBOL RESULTS:")
        print(f"{'-'*50}")
        for symbol, symbol_results in results['individual_results'].items():
            metrics = symbol_results.get('metrics', {})
            if metrics:
                print(f"{symbol}: {metrics.get('total_trades', 0)} trades, "
                      f"{metrics.get('win_rate', 0):.1%} win rate, "
                      f"${metrics.get('total_pnl', 0):.2f} PnL")
    
    # Save results
    filepath = backtester.save_results(results)
    print(f"\nDetailed results saved to: {filepath}")

if __name__ == "__main__":
    asyncio.run(main()) 