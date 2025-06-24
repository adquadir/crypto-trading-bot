"""
Dynamic Profit Scraper - Adaptive trading system that flows with market conditions
Switches between scalping (trending) and grid trading (ranging) automatically
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import numpy as np

logger = logging.getLogger(__name__)

class MarketRegime(Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down" 
    RANGING = "ranging"
    VOLATILE = "volatile"

class StrategyMode(Enum):
    SCALPING = "scalping"
    GRID = "grid"
    STANDBY = "standby"

@dataclass
class TradeResult:
    symbol: str
    strategy: str
    side: str
    pnl_pct: float
    profit_usd: float
    duration_min: float
    timestamp: datetime

class ProfitScraper:
    """Main profit scraping engine"""
    
    def __init__(self, exchange_client=None):
        self.exchange_client = exchange_client
        self.active_symbols = set()
        self.symbol_strategies = {}
        self.symbol_regimes = {}
        self.active_positions = {}
        self.profit_history = []
        self.running = False
        
        # Performance tracking
        self.total_profits = 0.0
        self.total_trades = 0
        self.winning_trades = 0
        
    async def start(self, symbols: List[str]):
        """Start profit scraping"""
        self.running = True
        self.active_symbols = set(symbols[:5])  # Limit concurrent symbols
        
        logger.info(f"🚀 Starting Profit Scraper on {len(self.active_symbols)} symbols")
        
        # Initialize
        for symbol in self.active_symbols:
            self.symbol_strategies[symbol] = StrategyMode.STANDBY
            self.symbol_regimes[symbol] = MarketRegime.RANGING
        
        # Start main loop
        asyncio.create_task(self._main_loop())
    
    def stop(self):
        """Stop profit scraping"""
        self.running = False
        logger.info("🛑 Stopping Profit Scraper")
    
    async def _main_loop(self):
        """Main execution loop"""
        while self.running:
            try:
                for symbol in self.active_symbols:
                    # Get market data
                    market_data = await self._get_market_data(symbol)
                    
                    # Detect regime
                    regime = self._detect_regime(symbol, market_data)
                    
                    # Update strategy if regime changed
                    if regime != self.symbol_regimes.get(symbol):
                        await self._switch_strategy(symbol, regime)
                        self.symbol_regimes[symbol] = regime
                    
                    # Execute current strategy
                    await self._execute_strategy(symbol, market_data)
                    
                    # Check for completed trades
                    await self._check_exits(symbol, market_data)
                
                await asyncio.sleep(30)  # 30 second intervals
                
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                await asyncio.sleep(60)
    
    async def _get_market_data(self, symbol: str) -> Dict[str, Any]:
        """Get market data for symbol"""
        # Mock data for testing
        import random
        import time
        
        base_price = 50000 if 'BTC' in symbol else 3000
        klines = []
        
        for i in range(20):
            price = base_price * (1 + random.uniform(-0.02, 0.02))
            klines.append({
                'close': str(price),
                'high': str(price * 1.001),
                'low': str(price * 0.999),
                'volume': str(random.uniform(1000, 5000))
            })
        
        return {'symbol': symbol, 'klines': klines}
    
    def _detect_regime(self, symbol: str, market_data: Dict[str, Any]) -> MarketRegime:
        """Detect market regime"""
        try:
            klines = market_data['klines']
            if len(klines) < 10:
                return MarketRegime.RANGING
            
            closes = [float(k['close']) for k in klines[-10:]]
            
            # Simple trend detection
            sma_short = np.mean(closes[-5:])
            sma_long = np.mean(closes[-10:])
            
            # Volatility
            returns = np.diff(closes) / closes[:-1]
            volatility = np.std(returns)
            
            if volatility > 0.03:  # High volatility
                return MarketRegime.VOLATILE
            elif sma_short > sma_long * 1.005:  # Strong uptrend
                return MarketRegime.TRENDING_UP
            elif sma_short < sma_long * 0.995:  # Strong downtrend
                return MarketRegime.TRENDING_DOWN
            else:
                return MarketRegime.RANGING
                
        except Exception as e:
            logger.error(f"Error detecting regime for {symbol}: {e}")
            return MarketRegime.RANGING
    
    async def _switch_strategy(self, symbol: str, regime: MarketRegime):
        """Switch strategy based on regime"""
        try:
            # Close any existing positions
            if symbol in self.active_positions:
                del self.active_positions[symbol]
            
            # Set new strategy
            if regime in [MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN]:
                self.symbol_strategies[symbol] = StrategyMode.SCALPING
                logger.info(f"Switching {symbol} to SCALPING mode ({regime.value})")
            elif regime == MarketRegime.RANGING:
                self.symbol_strategies[symbol] = StrategyMode.GRID
                logger.info(f"Switching {symbol} to GRID mode")
            else:
                self.symbol_strategies[symbol] = StrategyMode.STANDBY
                logger.info(f"Switching {symbol} to STANDBY mode")
                
        except Exception as e:
            logger.error(f"Error switching strategy for {symbol}: {e}")
    
    async def _execute_strategy(self, symbol: str, market_data: Dict[str, Any]):
        """Execute current strategy"""
        strategy = self.symbol_strategies.get(symbol, StrategyMode.STANDBY)
        
        if strategy == StrategyMode.SCALPING:
            await self._execute_scalping(symbol, market_data)
        elif strategy == StrategyMode.GRID:
            await self._execute_grid(symbol, market_data)
    
    async def _execute_scalping(self, symbol: str, market_data: Dict[str, Any]):
        """Execute scalping strategy"""
        try:
            if symbol in self.active_positions:
                return  # Already have position
            
            klines = market_data['klines']
            current_price = float(klines[-1]['close'])
            regime = self.symbol_regimes[symbol]
            
            # Simple scalping signal
            closes = [float(k['close']) for k in klines[-5:]]
            rsi = self._calculate_rsi(closes)
            
            signal = None
            
            if regime == MarketRegime.TRENDING_UP and rsi < 30:
                # Oversold in uptrend - buy
                signal = {
                    'side': 'LONG',
                    'entry_price': current_price,
                    'take_profit': current_price * 1.005,  # 0.5% profit
                    'stop_loss': current_price * 0.997,    # 0.3% loss
                    'entry_time': datetime.utcnow()
                }
            
            elif regime == MarketRegime.TRENDING_DOWN and rsi > 70:
                # Overbought in downtrend - sell
                signal = {
                    'side': 'SHORT',
                    'entry_price': current_price,
                    'take_profit': current_price * 0.995,  # 0.5% profit
                    'stop_loss': current_price * 1.003,    # 0.3% loss
                    'entry_time': datetime.utcnow()
                }
            
            if signal:
                self.active_positions[symbol] = signal
                logger.info(f"Scalp entry: {symbol} {signal['side']} at ${current_price:.6f}")
                
        except Exception as e:
            logger.error(f"Error executing scalping for {symbol}: {e}")
    
    async def _execute_grid(self, symbol: str, market_data: Dict[str, Any]):
        """Execute grid trading strategy"""
        try:
            if symbol in self.active_positions:
                return  # Grid already active
            
            current_price = float(market_data['klines'][-1]['close'])
            
            # Setup simple grid
            grid_spacing = 0.004  # 0.4%
            profit_target = 0.002  # 0.2% per level
            
            grid = {
                'type': 'grid',
                'center_price': current_price,
                'buy_levels': [
                    current_price * (1 - grid_spacing),
                    current_price * (1 - grid_spacing * 2)
                ],
                'sell_levels': [
                    current_price * (1 + grid_spacing),
                    current_price * (1 + grid_spacing * 2)
                ],
                'profit_target': profit_target,
                'filled_levels': [],
                'entry_time': datetime.utcnow()
            }
            
            self.active_positions[symbol] = grid
            logger.info(f"Grid setup: {symbol} around ${current_price:.6f}")
            
        except Exception as e:
            logger.error(f"Error executing grid for {symbol}: {e}")
    
    def _calculate_rsi(self, prices: List[float], period: int = 5) -> float:
        """Calculate RSI"""
        if len(prices) < period + 1:
            return 50
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    async def _check_exits(self, symbol: str, market_data: Dict[str, Any]):
        """Check for trade exits"""
        if symbol not in self.active_positions:
            return
        
        try:
            position = self.active_positions[symbol]
            current_price = float(market_data['klines'][-1]['close'])
            
            if position.get('type') == 'grid':
                await self._check_grid_exits(symbol, position, current_price)
            else:
                await self._check_scalp_exits(symbol, position, current_price)
                
        except Exception as e:
            logger.error(f"Error checking exits for {symbol}: {e}")
    
    async def _check_scalp_exits(self, symbol: str, position: Dict, current_price: float):
        """Check scalp trade exits"""
        try:
            side = position['side']
            entry_price = position['entry_price']
            take_profit = position['take_profit']
            stop_loss = position['stop_loss']
            
            should_exit = False
            exit_reason = ""
            
            # Check TP/SL
            if side == 'LONG':
                if current_price >= take_profit:
                    should_exit = True
                    exit_reason = "take_profit"
                elif current_price <= stop_loss:
                    should_exit = True
                    exit_reason = "stop_loss"
            else:  # SHORT
                if current_price <= take_profit:
                    should_exit = True
                    exit_reason = "take_profit"
                elif current_price >= stop_loss:
                    should_exit = True
                    exit_reason = "stop_loss"
            
            # Time limit
            duration = (datetime.utcnow() - position['entry_time']).total_seconds()
            if duration > 900:  # 15 minutes
                should_exit = True
                exit_reason = "time_limit"
            
            if should_exit:
                # Calculate P&L
                if side == 'LONG':
                    pnl_pct = (current_price - entry_price) / entry_price
                else:
                    pnl_pct = (entry_price - current_price) / entry_price
                
                profit_usd = pnl_pct * 1000  # Assume $1000 position
                
                # Record result
                result = TradeResult(
                    symbol=symbol,
                    strategy='scalp',
                    side=side,
                    pnl_pct=pnl_pct,
                    profit_usd=profit_usd,
                    duration_min=duration / 60,
                    timestamp=datetime.utcnow()
                )
                
                self._record_trade(result)
                del self.active_positions[symbol]
                
                logger.info(f"Scalp exit: {symbol} {side} P&L: {pnl_pct:.2%} (${profit_usd:.2f}) - {exit_reason}")
                
        except Exception as e:
            logger.error(f"Error checking scalp exits for {symbol}: {e}")
    
    async def _check_grid_exits(self, symbol: str, grid: Dict, current_price: float):
        """Check grid trade exits"""
        try:
            # Check buy levels
            for buy_level in grid['buy_levels']:
                if current_price <= buy_level and buy_level not in grid['filled_levels']:
                    # Level hit - simulate fill and immediate profit target
                    profit_target = buy_level * (1 + grid['profit_target'])
                    grid['filled_levels'].append(buy_level)
                    
                    logger.info(f"Grid BUY filled: {symbol} at ${buy_level:.6f}, target ${profit_target:.6f}")
                    
                    # Check if can immediately take profit
                    if current_price >= profit_target:
                        pnl_pct = grid['profit_target']
                        profit_usd = pnl_pct * 500  # $500 per level
                        
                        result = TradeResult(
                            symbol=symbol,
                            strategy='grid',
                            side='BUY',
                            pnl_pct=pnl_pct,
                            profit_usd=profit_usd,
                            duration_min=1,  # Quick grid profit
                            timestamp=datetime.utcnow()
                        )
                        
                        self._record_trade(result)
                        logger.info(f"Grid profit: {symbol} BUY ${profit_usd:.2f}")
            
            # Check sell levels
            for sell_level in grid['sell_levels']:
                if current_price >= sell_level and sell_level not in grid['filled_levels']:
                    # Level hit
                    profit_target = sell_level * (1 - grid['profit_target'])
                    grid['filled_levels'].append(sell_level)
                    
                    logger.info(f"Grid SELL filled: {symbol} at ${sell_level:.6f}, target ${profit_target:.6f}")
                    
                    # Check profit
                    if current_price <= profit_target:
                        pnl_pct = grid['profit_target']
                        profit_usd = pnl_pct * 500
                        
                        result = TradeResult(
                            symbol=symbol,
                            strategy='grid',
                            side='SELL',
                            pnl_pct=pnl_pct,
                            profit_usd=profit_usd,
                            duration_min=1,
                            timestamp=datetime.utcnow()
                        )
                        
                        self._record_trade(result)
                        logger.info(f"Grid profit: {symbol} SELL ${profit_usd:.2f}")
            
        except Exception as e:
            logger.error(f"Error checking grid exits for {symbol}: {e}")
    
    def _record_trade(self, result: TradeResult):
        """Record trade result"""
        self.profit_history.append(result)
        self.total_trades += 1
        self.total_profits += result.profit_usd
        
        if result.profit_usd > 0:
            self.winning_trades += 1
        
        logger.info(f"💰 Trade completed: {result.symbol} {result.strategy} "
                   f"${result.profit_usd:.2f} ({result.pnl_pct:.2%})")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status"""
        win_rate = self.winning_trades / max(1, self.total_trades)
        
        return {
            'running': self.running,
            'active_symbols': len(self.active_symbols),
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'win_rate': win_rate,
            'total_profits': self.total_profits,
            'avg_profit_per_trade': self.total_profits / max(1, self.total_trades),
            'active_positions': len(self.active_positions),
            'strategies': {
                strategy.value: sum(1 for s in self.symbol_strategies.values() if s == strategy)
                for strategy in StrategyMode
            },
            'regimes': {
                regime.value: sum(1 for r in self.symbol_regimes.values() if r == regime)
                for regime in MarketRegime
            }
        }
    
    def get_recent_trades(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent trade results"""
        recent = self.profit_history[-limit:]
        return [
            {
                'symbol': t.symbol,
                'strategy': t.strategy,
                'side': t.side,
                'pnl_pct': t.pnl_pct,
                'profit_usd': t.profit_usd,
                'duration_min': t.duration_min,
                'timestamp': t.timestamp.isoformat()
            }
            for t in recent
        ] 