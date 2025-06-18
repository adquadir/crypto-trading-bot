from typing import Dict, List, Optional, Set, Union, Any
import asyncio
import logging
from datetime import datetime, timedelta
import numpy as np
from dataclasses import dataclass, field
from src.market_data.exchange_client import ExchangeClient
from src.signals.signal_generator import SignalGenerator
from src.models.trading import TradingOpportunity
import os
from functools import lru_cache
import json
from pathlib import Path
import pandas as pd
from typing import Tuple
import time
from src.strategy.dynamic_config import strategy_config
from src.database.database import Database
from dotenv import load_dotenv
import statistics
from src.utils.config import load_config

logger = logging.getLogger(__name__)


@dataclass
class SignalValidationResult:
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class CachedSignal:
    signal: Dict
    timestamp: datetime
    expires_at: datetime


@dataclass
class SignalEvaluation:
    """Track signal performance and outcomes."""
    symbol: str
    direction: str
    entry_price: float
    take_profit: float
    stop_loss: float
    confidence: float
    score: float
    timestamp: datetime
    outcome: Optional[str] = None  # 'win', 'loss', 'breakeven'
    pnl: Optional[float] = None
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    metrics: Dict = field(default_factory=dict)  # Store all input metrics
    reasoning: List[str] = field(default_factory=list)


class SignalTracker:
    """Track and evaluate signal performance."""

    def __init__(self):
        self.signals: List[SignalEvaluation] = []
        self.score_weights = {
            'volume': 0.15,
            'volatility': 0.15,
            'trend': 0.20,
            'momentum': 0.20,
            'liquidity': 0.15,
            'oi_trend': 0.15
        }
        self.min_samples = 100  # Minimum samples for weight tuning
        self.win_rate_threshold = 0.55  # Target win rate
        self.score_buckets = {
            'high': (0.8, 1.0),
            'medium': (0.6, 0.8),
            'low': (0.4, 0.6),
            'very_low': (0.0, 0.4)
        }
        self.score_bucket_stats = {}
        
    def add_signal(self, signal: SignalEvaluation):
        """Add a new signal for tracking."""
        self.signals.append(signal)
        self._log_signal_details(signal)
        
    def _log_signal_details(self, signal: SignalEvaluation):
        """Log detailed signal information for analysis."""
        log_entry = {
            'timestamp': signal.timestamp.isoformat(),
            'symbol': signal.symbol,
            'direction': signal.direction,
            'entry_price': signal.entry_price,
            'take_profit': signal.take_profit,
            'stop_loss': signal.stop_loss,
            'confidence': signal.confidence,
            'score': signal.score,
            'metrics': signal.metrics,
            'reasoning': signal.reasoning
        }
        
        # Log to daily file
        log_dir = Path('logs/signals')
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / \
            f"signals_{signal.timestamp.strftime('%Y%m%d')}.jsonl"
        
        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
            
    def update_outcome(
    self,
    symbol: str,
    outcome: str,
    pnl: float,
     exit_price: float):
        """Update signal outcome after trade completion."""
        for signal in self.signals:
            if signal.symbol == symbol and signal.outcome is None:
                signal.outcome = outcome
                signal.pnl = pnl
                signal.exit_price = exit_price
                signal.exit_time = datetime.now()
                
                # Log outcome
                self._log_outcome(signal)
                
                # Update analytics
                self._update_analytics(signal)
                break
                
    def _log_outcome(self, signal: SignalEvaluation):
        """Log trade outcome for analysis."""
        log_entry = {
            'timestamp': signal.exit_time.isoformat(),
            'symbol': signal.symbol,
            'outcome': signal.outcome,
            'pnl': signal.pnl,
            'exit_price': signal.exit_price,
            # hours
            'holding_time': (signal.exit_time - signal.timestamp).total_seconds() / 3600,
            'score': signal.score,
            'confidence': signal.confidence
        }
        
        log_dir = Path('logs/outcomes')
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / \
            f"outcomes_{signal.exit_time.strftime('%Y%m%d')}.jsonl"
        
        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
            
    def _update_analytics(self, signal: SignalEvaluation):
        """Update performance analytics."""
        # Update score bucket performance
        bucket = self._get_score_bucket(signal.score)
        if bucket not in self.score_bucket_stats:
            self.score_bucket_stats[bucket] = {
                'total': 0,
                'wins': 0,
                'losses': 0,
                'total_pnl': 0.0,
                'avg_holding_time': 0.0
            }
            
        stats = self.score_bucket_stats[bucket]
        stats['total'] += 1
        if signal.outcome == 'win':
            stats['wins'] += 1
        else:
            stats['losses'] += 1
        stats['total_pnl'] += signal.pnl
        stats['avg_holding_time'] = (
            (stats['avg_holding_time'] * (stats['total'] - 1) +
             (signal.exit_time - signal.timestamp).total_seconds() / 3600) /
            stats['total']
        )
        
    def _get_score_bucket(self, score: float) -> str:
        """Get the score bucket for a given score."""
        for bucket, (low, high) in self.score_buckets.items():
            if low <= score < high:
                return bucket
        return 'very_low'
        
    def get_performance_metrics(self) -> Dict:
        """Get comprehensive performance metrics."""
        metrics = {
            'overall': self._calculate_overall_metrics(),
            'by_score': self._calculate_score_metrics(),
            'by_confidence': self._calculate_confidence_metrics(),
            'by_regime': self._calculate_regime_metrics(),
            'by_timeframe': self._calculate_timeframe_metrics()
        }
        
        # Calculate optimal thresholds
        metrics['optimal_thresholds'] = self.get_optimal_thresholds()
        
        return metrics
        
    def _calculate_overall_metrics(self) -> Dict:
        """Calculate overall performance metrics."""
        completed = [s for s in self.signals if s.outcome is not None]
        if not completed:
            return {}
            
        return {
            'total_trades': len(completed),
            'win_rate': sum(1 for s in completed if s.outcome == 'win') / len(completed),
            'avg_pnl': sum(s.pnl for s in completed) / len(completed),
            'avg_holding_time': sum((s.exit_time - s.timestamp).total_seconds() / 3600 
                                  for s in completed) / len(completed),
            'profit_factor': (
                sum(s.pnl for s in completed if s.pnl > 0) /
                abs(sum(s.pnl for s in completed if s.pnl < 0))
                if any(s.pnl < 0 for s in completed) else float('inf')
            )
        }
        
    def _calculate_score_metrics(self) -> Dict:
        """Calculate performance metrics by score bucket."""
        return {
            bucket: {
                'win_rate': stats['wins'] / stats['total'] if stats['total'] > 0 else 0,
                'avg_pnl': stats['total_pnl'] / stats['total'] if stats['total'] > 0 else 0,
                'avg_holding_time': stats['avg_holding_time'],
                'total_trades': stats['total']
            }
            for bucket, stats in self.score_bucket_stats.items()
        }
        
    def _calculate_confidence_metrics(self) -> Dict:
        """Calculate performance metrics by confidence level."""
        completed = [s for s in self.signals if s.outcome is not None]
        if not completed:
            return {}
            
        confidence_ranges = {
            'high': (0.8, 1.0),
            'medium': (0.6, 0.8),
            'low': (0.4, 0.6),
            'very_low': (0.0, 0.4)
        }
        
        metrics = {}
        for level, (low, high) in confidence_ranges.items():
            level_signals = [
    s for s in completed if low <= s.confidence < high]
            if level_signals:
                metrics[level] = {
                    'win_rate': sum(1 for s in level_signals if s.outcome == 'win') / len(level_signals),
                    'avg_pnl': sum(s.pnl for s in level_signals) / len(level_signals),
                    'total_trades': len(level_signals)
                }
                
        return metrics
        
    def _calculate_regime_metrics(self) -> Dict:
        """Calculate performance metrics by market regime."""
        completed = [s for s in self.signals if s.outcome is not None]
        if not completed:
            return {}
            
        regimes = {}
        for signal in completed:
            regime = signal.metrics.get('regime', 'unknown')
            if regime not in regimes:
                regimes[regime] = {
                    'total': 0,
                    'wins': 0,
                    'total_pnl': 0.0
                }
                
            stats = regimes[regime]
            stats['total'] += 1
            if signal.outcome == 'win':
                stats['wins'] += 1
            stats['total_pnl'] += signal.pnl
            
        return {
            regime: {
                'win_rate': stats['wins'] / stats['total'],
                'avg_pnl': stats['total_pnl'] / stats['total'],
                'total_trades': stats['total']
            }
            for regime, stats in regimes.items()
        }
        
    def _calculate_timeframe_metrics(self) -> Dict:
        """Calculate performance metrics by time of day."""
        completed = [s for s in self.signals if s.outcome is not None]
        if not completed:
            return {}
            
        timeframes = {
            'morning': (6, 12),
            'afternoon': (12, 18),
            'evening': (18, 24),
            'night': (0, 6)
        }
        
        metrics = {}
        for period, (start, end) in timeframes.items():
            period_signals = [
                s for s in completed
                if start <= s.timestamp.hour < end
            ]
            if period_signals:
                metrics[period] = {
                    'win_rate': sum(1 for s in period_signals if s.outcome == 'win') / len(period_signals),
                    'avg_pnl': sum(s.pnl for s in period_signals) / len(period_signals),
                    'total_trades': len(period_signals)
                }
                
        return metrics

    def get_optimal_thresholds(self) -> Dict:
        """Calculate optimal thresholds based on historical performance."""
        completed = [s for s in self.signals if s.outcome is not None]
        if len(completed) < self.min_samples:
            return {
                'min_score': 0.6,
                'min_confidence': 0.6,
                'min_win_rate': 0.55
            }
            
        # Calculate optimal score threshold
        scores = sorted([s.score for s in completed])
        win_rates = []
        for i in range(len(scores)):
            threshold = scores[i]
            signals_above = [s for s in completed if s.score >= threshold]
            if len(signals_above) >= self.min_samples:
                win_rate = sum(
    1 for s in signals_above if s.outcome == 'win') / len(signals_above)
                win_rates.append((threshold, win_rate))
                
        optimal_score = max(
            (threshold for threshold,
     win_rate in win_rates if win_rate >= self.win_rate_threshold),
            default=0.6
        )
        
        # Calculate optimal confidence threshold
        confidences = sorted([s.confidence for s in completed])
        win_rates = []
        for i in range(len(confidences)):
            threshold = confidences[i]
            signals_above = [s for s in completed if s.confidence >= threshold]
            if len(signals_above) >= self.min_samples:
                win_rate = sum(
    1 for s in signals_above if s.outcome == 'win') / len(signals_above)
                win_rates.append((threshold, win_rate))
                
        optimal_confidence = max(
            (threshold for threshold,
     win_rate in win_rates if win_rate >= self.win_rate_threshold),
            default=0.6
        )
        
        # Calculate optimal win rate threshold
        win_rates = []
        for i in range(len(scores)):
            threshold = scores[i]
            signals_above = [s for s in completed if s.score >= threshold]
            if len(signals_above) >= self.min_samples:
                win_rate = sum(
    1 for s in signals_above if s.outcome == 'win') / len(signals_above)
                win_rates.append((threshold, win_rate))
                
        optimal_win_rate = max(
            (win_rate for _, win_rate in win_rates),
            default=self.win_rate_threshold
        )
        
        return {
            'min_score': optimal_score,
            'min_confidence': optimal_confidence,
            'min_win_rate': optimal_win_rate
        }


class SymbolDiscovery:
    """Discovers and manages trading symbols from the exchange."""
    
    def __init__(
        self, exchange_client_or_config: Union[ExchangeClient, Dict[str, Any]]):
        """Initialize symbol discovery.
        
        Args:
            exchange_client_or_config: Either an ExchangeClient instance or a configuration dictionary.
                If ExchangeClient: Used directly for API calls
                If Dict: Configuration dictionary containing:
                    - update_interval: Interval between symbol updates in hours (default: 1.0)
                    - min_volume: Minimum 24h volume in USD (default: 1000000)
                    - min_price: Minimum price in USD (default: 0.1)
                    - max_price: Maximum price in USD (default: 100000)
                    - min_market_cap: Minimum market cap in USD (default: 10000000)
                    - excluded_symbols: List of symbols to exclude
                    - included_symbols: List of symbols to include (overrides other filters)
        """
        if isinstance(exchange_client_or_config, ExchangeClient):
            self.exchange_client = exchange_client_or_config
            self.config = exchange_client_or_config.config
        else:
            self.config = exchange_client_or_config
            self.exchange_client = None  # Will be set during initialize()
        
        self.logger = logging.getLogger(__name__)
        
        # Parse update interval from config or environment
        update_interval = self.config.get('update_interval')
        if update_interval is None:
            update_interval = float(os.getenv('UPDATE_INTERVAL', '1.0'))
        # Convert to float to handle both int and float strings
        self.update_interval = float(update_interval)
        
        # Initialize filters
        self.min_volume = self.config.get(
    'min_volume', float(
        os.getenv(
            'MIN_VOLUME', '1000000')))
        self.min_price = self.config.get(
    'min_price', float(
        os.getenv(
            'MIN_PRICE', '0.1')))
        self.max_price = self.config.get(
    'max_price', float(
        os.getenv(
            'MAX_PRICE', '100000')))
        self.min_market_cap = self.config.get(
    'min_market_cap', float(
        os.getenv(
            'MIN_MARKET_CAP', '10000000')))
        
        # Initialize symbol lists
        self.excluded_symbols = set(self.config.get('excluded_symbols', []))
        self.included_symbols = set(self.config.get('included_symbols', []))
        
        # Initialize state
        self.running = False
        self.last_update_time = datetime.now()
        self.symbols = set()
        
        self.signal_generator = SignalGenerator()
        self.opportunities: Dict[str, TradingOpportunity] = {}
        self._update_task = None
        self._processing_lock = asyncio.Lock()  # Add lock for concurrent processing
        self._discovery_lock = asyncio.Lock()
        self.cache = {}  # Simple dictionary for caching
        # 5 seconds for scalping, 5 minutes for normal mode
        self.cache_ttl = 5 if self.config.get('scalping_mode', False) else 300
        logger.info("SymbolDiscovery initialized with caching")
        
        # Load configuration from environment
        self.min_volume_24h = float(os.getenv('MIN_24H_VOLUME', '1000000'))
        self.min_volume_24h = max(self.min_volume_24h, 1.0)  # Ensure non-zero minimum
        if float(os.getenv('MIN_24H_VOLUME', '1000000')) <= 0:
            logger.debug(f"MIN_24H_VOLUME was <= 0, using minimum threshold of {self.min_volume_24h}")
            
        # Minimum confidence for accepting a signal (default 0.4, can be set at runtime or via API)
        self.min_confidence = float(os.getenv('MIN_CONFIDENCE', '0.4'))
        self.min_risk_reward = float(os.getenv('MIN_RISK_REWARD', '1.5'))
        self.max_leverage = float(os.getenv('MAX_LEVERAGE', '20.0'))
        
        # Advanced filtering parameters
        self.max_spread = float(os.getenv('MAX_SPREAD', '0.002'))
        self.min_liquidity = float(os.getenv('MIN_LIQUIDITY', '500000'))
        self.max_correlation = float(os.getenv('MAX_CORRELATION', '0.7'))
        self.min_volatility = float(os.getenv('MIN_VOLATILITY', '0.01'))
        self.max_volatility = float(os.getenv('MAX_VOLATILITY', '0.05'))
        self.min_funding_rate = float(os.getenv('MIN_FUNDING_RATE', '-0.0001'))
        self.max_funding_rate = float(os.getenv('MAX_FUNDING_RATE', '0.0001'))
        self.min_open_interest = float(os.getenv('MIN_OPEN_INTEREST', '100000'))
        self.max_symbols = int(os.getenv('MAX_SYMBOLS', '50'))
        
        # Log the actual values being used
        logger.info("SymbolDiscovery filter parameters:")
        logger.info(f"min_volume_24h: {self.min_volume_24h}")
        logger.info(f"min_confidence: {self.min_confidence}")
        logger.info(f"min_risk_reward: {self.min_risk_reward}")
        logger.info(f"max_leverage: {self.max_leverage}")
        logger.info(f"min_market_cap: {self.min_market_cap}")
        logger.info(f"max_spread: {self.max_spread}")
        logger.info(f"min_liquidity: {self.min_liquidity}")
        logger.info(f"max_correlation: {self.max_correlation}")
        logger.info(f"min_volatility: {self.min_volatility}")
        logger.info(f"max_volatility: {self.max_volatility}")
        logger.info(f"min_funding_rate: {self.min_funding_rate}")
        logger.info(f"max_funding_rate: {self.max_funding_rate}")
        logger.info(f"min_open_interest: {self.min_open_interest}")
        logger.info(f"max_symbols: {self.max_symbols}")
        logger.info(f"scalping_mode: {self.config.get('scalping_mode', False)}")
        
        # Cache configuration
        self.cache_dir = Path('cache/signals')
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.signal_cache: Dict[str, CachedSignal] = {}
        self.cache_duration = int(
    os.getenv(
        'SYMBOL_CACHE_DURATION',
         '3600'))  # Use SYMBOL_CACHE_DURATION from .env
        
    async def initialize(self):
        """Initialize the symbol discovery component."""
        if not self.exchange_client:
            self.exchange_client = ExchangeClient(self.config)
            await self.exchange_client.initialize()
        logger.info("Symbol discovery initialized")
        
    async def start(self):
        """Start the symbol discovery process."""
        self._update_task = asyncio.create_task(self._update_loop())
        logger.info("Symbol discovery started")
        
    async def stop(self):
        """Stop the symbol discovery process."""
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
        logger.info("Symbol discovery stopped")
        
    async def _update_loop(self):
        """Periodic update loop for symbol discovery."""
        while True:
            try:
                await self.discover_symbols()
                self.last_update_time = datetime.now()
                logger.info(f"Symbol list updated at {self.last_update_time}")
                await asyncio.sleep(self.update_interval)
            except Exception as e:
                logger.error(f"Error in symbol update loop: {e}")
                await asyncio.sleep(60)  # Wait a minute before retrying
                
    async def get_market_data(self, symbol: str) -> Optional[Dict]:
        """Get market data for a symbol."""
        try:
            # Get orderbook
            orderbook = await self.exchange_client.get_orderbook(symbol)
            if not orderbook:
                return None

            # Get 24h ticker
            ticker_24h = await self.exchange_client.get_ticker_24h(symbol)
            if not ticker_24h:
                return None

            # Get OHLCV data
            ohlcv = await self.exchange_client.get_ohlcv(symbol, '1h', limit=24)
            if not ohlcv:
                return None

            # Get open interest
            open_interest = await self.exchange_client.get_open_interest(symbol)
            if not open_interest:
                return None

            # Get funding rate
            funding_rate = await self.exchange_client.get_funding_rate(symbol)
            if not funding_rate:
                return None

            # Get recent trades
            trades = await self.exchange_client.get_recent_trades(symbol, limit=100)
            if not trades:
                return None

            return {
                'orderbook': orderbook,
                'ticker_24h': ticker_24h,
                'ohlcv': ohlcv,
                'open_interest': open_interest,
                'funding_rate': funding_rate,
                'trades': trades
            }
        except Exception as e:
            logger.error(f"Error getting market data for {symbol}: {str(e)}")
            return None
                
    async def discover_symbols(self) -> List[str]:
        """Fetch available futures trading pairs based on configuration mode."""
        try:
            logger.debug("Starting symbol discovery")
            discovery_mode = os.getenv('SYMBOL_DISCOVERY_MODE', 'static')
            logger.debug(f"Using discovery mode: {discovery_mode}")
            
            if discovery_mode == 'static':
                # Use symbols from configuration
                symbols = os.getenv('TRADING_SYMBOLS', 'BTCUSDT').split(',')
                logger.info(f"Retrieved {len(symbols)} trading symbols from exchange")
                logger.info(f"Using {len(symbols)} static symbols from configuration: {', '.join(symbols)}")
                logger.info(f"Found {len(symbols)} symbols matching criteria")
                return symbols
            else:
                # Dynamic discovery from exchange
                logger.debug("Fetching exchange info for dynamic discovery")
                try:
                    exchange_info = await self.exchange_client.get_exchange_info()
                    logger.debug("Successfully fetched exchange info")
                    # Add debug logging for exchange info structure
                    logger.debug(f"Exchange info keys: {exchange_info.keys()}")
                    if 'symbols' in exchange_info:
                        logger.debug(
                            f"Number of symbols in response: {len(exchange_info['symbols'])}")
                        if exchange_info['symbols']:
                            sample_symbol = exchange_info['symbols'][0]
                            logger.debug(f"Sample symbol structure: {sample_symbol.keys()}")
                            logger.debug(f"Sample symbol data: {sample_symbol}")
                except Exception as e:
                    logger.error(f"Failed to fetch exchange info: {e}")
                    raise
                
                futures_symbols = []
                for symbol in exchange_info.get('symbols', []):
                    try:
                        # Add debug logging for symbol filtering
                        logger.debug(f"Processing symbol: {symbol.get('symbol')} - Status: {symbol.get('status')} - ContractType: {symbol.get('contractType')}")
                        if (symbol.get('status') == 'TRADING' and
                            symbol.get('contractType') == 'PERPETUAL' and
                            symbol.get('symbol', '').endswith('USDT')):
                            futures_symbols.append(symbol['symbol'])
                            logger.debug(f"Added symbol {symbol['symbol']} to futures symbols")
                    except Exception as e:
                        logger.warning(f"Error processing symbol {symbol.get('symbol', 'UNKNOWN')}: {e}")
                        continue

                logger.debug(f"Initial perpetual trading symbols found: {len(futures_symbols)}")
                if futures_symbols:
                    logger.debug(f"First 5 symbols: {', '.join(futures_symbols[:5])}")
                
                # Limit the number of symbols to process
                MAX_SYMBOLS = 20  # Process only top 20 symbols
                if len(futures_symbols) > MAX_SYMBOLS:
                    logger.info(f"Limiting symbol processing to top {MAX_SYMBOLS} symbols")
                    futures_symbols = futures_symbols[:MAX_SYMBOLS]
                
                # Apply filters
                filtered_symbols = []
                for symbol in futures_symbols:
                    logger.debug(f"Processing symbol for advanced filtering: {symbol}")
                    try:
                        market_data = await self.get_market_data(symbol)
                        if market_data:
                            logger.debug(f"Market data fetched for {symbol}")
                            if self._apply_advanced_filters(market_data):
                                logger.debug(f"Symbol {symbol} passed advanced filters")
                                filtered_symbols.append(symbol)
                            else:
                                logger.debug(f"Symbol {symbol} failed advanced filters")
                        else:
                            logger.debug(f"Failed to fetch market data for {symbol}")
                    except Exception as e:
                        logger.error(f"Error processing {symbol}: {e}")
                        continue
                
                logger.info(f"Discovered {len(filtered_symbols)} trading pairs after filtering")
                if filtered_symbols:
                    logger.debug(f"Filtered symbols: {', '.join(filtered_symbols)}")
                    return filtered_symbols
                
        except Exception as e:
            logger.error(f"Error discovering symbols: {e}")
            # Fallback to static symbols on error
            symbols = os.getenv('TRADING_SYMBOLS', 'BTCUSDT').split(',')
            logger.warning(f"Falling back to {len(symbols)} static symbols due to error")
            return symbols
            
    def _calculate_spread(self, orderbook: Dict) -> float:
        """Calculate the spread between best bid and ask."""
        try:
            best_bid = float(orderbook['bids'][0][0])
            best_ask = float(orderbook['asks'][0][0])
            return (best_ask - best_bid) / best_bid
        except (KeyError, IndexError, ValueError) as e:
            logger.error(f"Error calculating spread: {e}")
            return float('inf')
            
    def _apply_advanced_filters(self, market_data: Dict) -> bool:
        """Apply advanced filters to market data."""
        try:
            # Check spread
            spread = self._calculate_spread(market_data['orderbook'])
            if spread > 0.001:  # 0.1% max spread
                return False

            # Check volume
            volume = float(market_data['ticker_24h']['volume'])
            if volume < 1000000:  # 1M USDT minimum volume
                return False

            # Check price
            price = float(market_data['ticker_24h']['lastPrice'])
            if price < 0.1:  # Minimum price of 0.1 USDT
                return False

            return True
        except Exception as e:
            logger.error(f"Error applying advanced filters: {e}")
            return False

    async def scan_opportunities(self) -> List[TradingOpportunity]:
        """Scan for trading opportunities across all symbols."""
        try:
            # Get list of symbols to scan
            symbols = await self.discover_symbols()
            logger.info(f"Processing {len(symbols)} symbols: {', '.join(symbols)}")
            
            opportunities = []
            for symbol in symbols:
                try:
                    # Get market data
                    market_data = await self.get_market_data(symbol)
                    if not market_data:
                        continue
                    
                    # Generate signals
                    signals = await self.signal_generator.generate_signals(symbol, market_data)
                    if not signals:
                        continue
                    
                    # Convert signals to opportunities
                    for signal in signals:
                        opportunity = TradingOpportunity(
                            symbol=symbol,
                            direction=signal['direction'],
                            entry_price=float(signal['entry']),
                            take_profit=float(signal['take_profit']),
                            stop_loss=float(signal['stop_loss']),
                            confidence=float(signal['confidence']),
                            leverage=float(signal.get('leverage', 1.0)),
                            risk_reward=float(signal.get('risk_reward', 1.0)),
                            volume_24h=float(market_data['ticker_24h']['volume']),
                            volatility=float(signal.get('volatility', 0.0)),
                            score=float(signal.get('score', 0.0)),
                            indicators=signal.get('indicators', {}),
                            reasoning=signal.get('reasoning', []),
                            book_depth=float(signal.get('book_depth', 0.0)),
                            oi_trend=float(signal.get('oi_trend', 0.0)),
                            volume_trend=float(signal.get('volume_trend', 0.0)),
                            slippage=float(signal.get('slippage', 0.0)),
                            data_freshness=signal.get('data_freshness', {})
                        )
                        opportunities.append(opportunity)
                except Exception as e:
                    logger.error(f"Error processing {symbol}: {e}")
                    continue
            
            logger.info(f"Found {len(opportunities)} opportunities out of {len(symbols)} symbols")
            return opportunities
            
        except Exception as e:
            logger.error(f"Error scanning opportunities: {e}")
            return []