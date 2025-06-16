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
        self.min_volume_24h = max(
    self.min_volume_24h,
     1.0)  # Ensure non-zero minimum
        if float(os.getenv('MIN_24H_VOLUME', '1000000')) <= 0:
            logger.debug(
    f"MIN_24H_VOLUME was <= 0, using minimum threshold of {
        self.min_volume_24h}")
            
        # Minimum confidence for accepting a signal (default 0.4, can be set at
        # runtime or via API)
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
        self.min_open_interest = float(
            os.getenv('MIN_OPEN_INTEREST', '100000'))
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
        logger.info(f"cache_ttl: {self.cache_ttl} seconds")
        logger.info(
    f"scalping_mode: {
        self.config.get(
            'scalping_mode',
             False)}")
        
        # Cache configuration
        self.cache_dir = Path('cache/signals')
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.signal_cache: Dict[str, CachedSignal] = {}
        self.cache_duration = int(
    os.getenv(
        'SYMBOL_CACHE_DURATION',
         '3600'))  # Use SYMBOL_CACHE_DURATION from .env
        
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
                
    async def discover_symbols(self) -> List[str]:
        """Fetch available futures trading pairs based on configuration mode."""
        try:
            logger.debug("Starting symbol discovery")
            discovery_mode = os.getenv('SYMBOL_DISCOVERY_MODE', 'static')
            logger.debug(f"Using discovery mode: {discovery_mode}")
            
            if discovery_mode == 'static':
                # Use symbols from configuration
                symbols = os.getenv('TRADING_SYMBOLS', 'BTCUSDT').split(',')
                logger.info(
    f"Using {
        len(symbols)} static symbols from configuration: {
            ', '.join(symbols)}")
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
                            logger.debug(
    f"Sample symbol structure: {
        sample_symbol.keys()}")
                            logger.debug(
    f"Sample symbol data: {sample_symbol}")
                except Exception as e:
                    logger.error(f"Failed to fetch exchange info: {e}")
                    raise
                
                futures_symbols = []
                for symbol in exchange_info.get('symbols', []):
                    try:
                        # Add debug logging for symbol filtering
                        logger.debug(
    f"Processing symbol: {
        symbol.get('symbol')} - Status: {
            symbol.get('status')} - ContractType: {
                symbol.get('contractType')}")
                        if (symbol.get('status') == 'TRADING' and
                            symbol.get('contractType') == 'PERPETUAL' and
                            symbol.get('symbol', '').endswith('USDT')):
                            futures_symbols.append(symbol['symbol'])
                            logger.debug(
    f"Added symbol {
        symbol['symbol']} to futures symbols")
                    except Exception as e:
                        logger.warning(
    f"Error processing symbol {
        symbol.get(
            'symbol',
             'UNKNOWN')}: {e}")
                        continue

                logger.debug(
    f"Initial perpetual trading symbols found: {
        len(futures_symbols)}")
                if futures_symbols:
                    logger.debug(
                        f"First 5 symbols: {', '.join(futures_symbols[:5])}")
                
                # Limit the number of symbols to process
                MAX_SYMBOLS = 20  # Process only top 20 symbols
                if len(futures_symbols) > MAX_SYMBOLS:
                    logger.info(
    f"Limiting symbol processing to top {MAX_SYMBOLS} symbols")
                    futures_symbols = futures_symbols[:MAX_SYMBOLS]
                
                # Apply filters
                filtered_symbols = []
                for symbol in futures_symbols:
                    logger.debug(
    f"Processing symbol for advanced filtering: {symbol}")
                    try:
                        market_data = await self.get_market_data(symbol)
                        if market_data:
                            logger.debug(f"Market data fetched for {symbol}")
                            if self._apply_advanced_filters(market_data):
                                logger.debug(
    f"Symbol {symbol} passed advanced filters")
                                filtered_symbols.append(symbol)
                            else:
                                logger.debug(
    f"Symbol {symbol} failed advanced filters")
                        else:
                            logger.debug(
    f"Failed to fetch market data for {symbol}")
                    except Exception as e:
                        logger.error(f"Error processing {symbol}: {e}")
                        continue
                
                logger.info(
    f"Discovered {
        len(filtered_symbols)} trading pairs after filtering")
                if filtered_symbols:
                    logger.debug(
    f"Filtered symbols: {
        ', '.join(filtered_symbols)}")
                return filtered_symbols
                
        except Exception as e:
            logger.error(f"Error discovering symbols: {e}")
            # Fallback to static symbols on error
            symbols = os.getenv('TRADING_SYMBOLS', 'BTCUSDT').split(',')
            logger.warning(
    f"Falling back to {
        len(symbols)} static symbols due to error")
            return symbols

    async def get_market_data(self, symbol: str) -> Optional[Dict]:
        """Get market data for a symbol with proper formatting for signal generation."""
        try:
            # Get cached data
            cache_key = f"market_data_{symbol}"
            cached_data = self.cache.get(cache_key)
            current_time = time.time()

            # Check if cached data is fresh (less than 5 seconds old)
            if cached_data and (
    current_time -
    cached_data.get(
        'timestamp',
         0)) < 5:
                    return cached_data

            # Get fresh data from exchange
            klines = await self.exchange_client.get_klines(symbol, '1m', limit=100)
            ticker_24h = await self.exchange_client.get_ticker_24h(symbol)
            orderbook = await self.exchange_client.get_orderbook(symbol, limit=20)
            funding_rate = await self.exchange_client.get_funding_rate(symbol)
            open_interest = await self.exchange_client.get_open_interest(symbol)

            # Process klines data
            klines_dict = []
            for k in klines:
                if isinstance(k, (list, tuple)) and len(k) >= 6:
                    klines_dict.append({
                        'timestamp': k[0],
                        'open': float(k[1]),
                        'high': float(k[2]),
                        'low': float(k[3]),
                        'close': float(k[4]),
                        'volume': float(k[5])
                    })
                elif isinstance(k, dict):
                    klines_dict.append({
                        'timestamp': k.get('timestamp', 0),
                        'open': float(k.get('open', 0)),
                        'high': float(k.get('high', 0)),
                        'low': float(k.get('low', 0)),
                        'close': float(k.get('close', 0)),
                        'volume': float(k.get('volume', 0))
                    })

            # Process orderbook data
            orderbook_processed = {
                'bids': [[float(price), float(qty)] for price, qty in orderbook.get('bids', [])],
                'asks': [[float(price), float(qty)] for price, qty in orderbook.get('asks', [])]
            }

            # Process ticker data
            ticker_processed = {}
            if isinstance(ticker_24h, dict):
                ticker_processed = {
                    'price': float(ticker_24h.get('lastPrice', 0)),
                    'volume': float(ticker_24h.get('volume', 0)),
                    'priceChange': float(ticker_24h.get('priceChange', 0)),
                    'priceChangePercent': float(ticker_24h.get('priceChangePercent', 0)),
                    'highPrice': float(ticker_24h.get('highPrice', 0)),
                    'lowPrice': float(ticker_24h.get('lowPrice', 0))
                }

            # Process funding rate
            funding_rate_float = 0.0
            if isinstance(funding_rate, dict):
                funding_rate_float = float(funding_rate.get('fundingRate', 0))
            else:
                try:
                    funding_rate_float = float(funding_rate)
                except (ValueError, TypeError):
                    funding_rate_float = 0.0

            # Process open interest
            open_interest_float = 0.0
            if isinstance(open_interest, dict):
                open_interest_float = float(
                    open_interest.get('openInterest', 0))
            else:
                try:
                    open_interest_float = float(open_interest)
                except (ValueError, TypeError):
                    open_interest_float = 0.0

            # Calculate additional metrics
            spread = self._calculate_spread(orderbook_processed)
            liquidity = self._calculate_liquidity(orderbook_processed)
            volatility = self.calculate_volatility(klines_dict)

            # Create market data dictionary
            market_data = {
                'symbol': symbol,
                'klines': klines_dict,
                'ticker_24h': ticker_processed,
                'orderbook': orderbook_processed,
                'funding_rate': funding_rate_float,
                'open_interest': open_interest_float,
                'spread': spread,
                'liquidity': liquidity,
                'volatility': volatility,
                'timestamp': current_time,
                'ohlcv_freshness': 0.0,  # Will be updated by the signal generator
                'orderbook_freshness': 0.0,
                'ticker_freshness': 0.0,
                'oi_freshness': 0.0
            }

            # Cache the data
            self.cache[cache_key] = market_data
            return market_data

        except Exception as e:
            logger.error(f"Error getting market data for {symbol}: {e}")
            return None
            
    def _calculate_spread(self, orderbook: Dict) -> float:
        """Calculate the current spread from orderbook."""
        try:
            if not orderbook['bids'] or not orderbook['asks']:
                return float('inf')
                
            best_bid = float(orderbook['bids'][0][0])
            best_ask = float(orderbook['asks'][0][0])
            
            return (best_ask - best_bid) / best_bid
        except Exception as e:
            logger.error(f"Error calculating spread: {e}")
            return float('inf')
            
    def _calculate_liquidity(self, orderbook: Dict) -> float:
        """Calculate the current liquidity from orderbook."""
        try:
            # Calculate liquidity as the sum of (price * quantity) for top 10
            # levels
            bid_liquidity = sum(float(bid[0]) * float(bid[1])
                                for bid in orderbook['bids'][:10])
            ask_liquidity = sum(float(ask[0]) * float(ask[1])
                                for ask in orderbook['asks'][:10])
            
            return (bid_liquidity + ask_liquidity) / 2
        except Exception as e:
            logger.error(f"Error calculating liquidity: {e}")
            return 0.0
            
    def _calculate_market_cap(self, ticker_24h: Dict) -> float:
        """Calculate market cap from 24h ticker data."""
        try:
            quote_volume = ticker_24h.get('quoteVolume', 0)
            return float(quote_volume) if quote_volume is not None else 0.0
        except (ValueError, TypeError):
            return 0.0

    def calculate_volatility(self, ohlcv: List[Dict]) -> float:
        """Calculate annualized volatility from OHLCV data."""
        try:
            if not ohlcv or len(ohlcv) < 2:
                return 0.0

            # Extract close prices and convert to float
            close_prices = []
            for candle in ohlcv:
                if isinstance(candle, dict):
                    close = candle.get('close')
                    if close is not None:
                        try:
                            close_prices.append(float(close))
                        except (ValueError, TypeError):
                            continue
                elif isinstance(candle, (list, tuple)) and len(candle) > 3:
                    try:
                        # Assuming close is at index 3
                        close_prices.append(float(candle[3]))
                    except (ValueError, TypeError, IndexError):
                        continue

            if len(close_prices) < 2:
                return 0.0

            # Calculate returns
            returns = []
            for i in range(1, len(close_prices)):
                if close_prices[i - 1] > 0:  # Avoid division by zero
                    returns.append(
                        (close_prices[i] - close_prices[i - 1]) / close_prices[i - 1])

            if not returns:
                return 0.0

            # Calculate standard deviation of returns
            std_dev = np.std(returns)

            # Annualize volatility (assuming daily data)
            # 252 trading days in a year
            annualized_vol = std_dev * np.sqrt(252)

            return float(annualized_vol)

        except Exception as e:
            logger.error(f"Error calculating volatility: {e}")
            return 0.0

    def calculate_opportunity_score(
    self, opportunity: TradingOpportunity) -> float:
        """Calculate a comprehensive score for the trading opportunity."""
        try:
            # Base score from signal confidence (30%)
            score = opportunity.confidence * 0.3
            
            # Volume factor (15%)
            volume_threshold = self.min_volume_24h if self.min_volume_24h > 0 else 1.0
            volume_score = min(opportunity.volume_24h / volume_threshold, 2.0)
            
            # Check for recent volume spike (3-bar volume surge)
            recent_volume_surge = self._check_volume_surge(opportunity.symbol)
            if recent_volume_surge:
                volume_score *= 1.2  # Boost score if volume is surging
                
            logger.debug(
    f"Volume score for {
        opportunity.symbol}: {
            volume_score:.2f} (volume: {
                opportunity.volume_24h:.2f}, threshold: {
                    volume_threshold:.2f})")
            score += volume_score * 0.15
            
            # Risk-reward factor (15%)
            rr_score = min(opportunity.risk_reward / self.min_risk_reward, 3.0)
            logger.debug(
    f"Risk-reward score for {
        opportunity.symbol}: {
            rr_score:.2f} (RR: {
                opportunity.risk_reward:.2f}, min: {
                    self.min_risk_reward:.2f})")
            score += rr_score * 0.15
            
            # Volatility factor (15% - increased from 10%)
            # Target 1.5% volatility for scalping
            vol_score = 1.0 - abs(opportunity.volatility - 0.015) / 0.015
            logger.debug(
    f"Volatility score for {
        opportunity.symbol}: {
            vol_score:.2f} (vol: {
                opportunity.volatility:.4f})")
            score += vol_score * 0.15
            
            # Leverage factor (5%)
            lev_score = 1.0 - (opportunity.leverage / self.max_leverage)
            logger.debug(
    f"Leverage score for {
        opportunity.symbol}: {
            lev_score:.2f} (lev: {
                opportunity.leverage:.2f}, max: {
                    self.max_leverage:.2f})")
            score += lev_score * 0.05
            
            # Technical indicators (20% - reduced from 25%)
            tech_score = self._calculate_technical_score(
                opportunity.indicators)
            logger.debug(
    f"Technical score for {
        opportunity.symbol}: {
            tech_score:.2f}")
            score += tech_score * 0.20
            
            # Apply risk/reward confidence scaling
            if opportunity.risk_reward > 1.5:
                score *= 1.1
                logger.debug(
    f"Boosting score for {
        opportunity.symbol} due to good risk/reward ratio")
            elif opportunity.risk_reward < 1.0:
                score *= 0.9
                logger.debug(
    f"Reducing score for {
        opportunity.symbol} due to poor risk/reward ratio")
            
            final_score = min(score, 1.0)
            logger.debug(
    f"Final opportunity score for {
        opportunity.symbol}: {
            final_score:.2f}")
            return final_score
            
        except Exception as e:
            logger.error(
    f"Error calculating opportunity score for {
        opportunity.symbol}: {e}")
            return 0.0
            
    def _calculate_technical_score(self, indicators: Dict) -> float:
        """Calculate score based on technical indicators."""
        try:
            score = 0.0
            weights = {
                'trend': 0.25,
                'momentum': 0.20,
                'volatility': 0.15,
                'volume': 0.10,
                'support_resistance': 0.10,
                'trend_strength': 0.10,
                'oscillators': 0.10
            }
            # Trend indicators
            if 'macd' in indicators:
                macd = indicators['macd']
                macd_value = macd['value'] if isinstance(macd, dict) else macd
                macd_signal = macd['signal'] if isinstance(macd, dict) else 0
                macd_histogram = macd['histogram'] if isinstance(
                    macd, dict) else 0
                if macd_value > macd_signal and macd_histogram > 0:
                    score += weights['trend'] * 1.0
                elif macd_value < macd_signal and macd_histogram < 0:
                    score += weights['trend'] * 1.0
            if 'ema' in indicators:
                ema = indicators['ema']
                ema_fast = ema['fast'] if isinstance(ema, dict) else ema
                ema_slow = ema['slow'] if isinstance(ema, dict) else 0
                if ema_fast > ema_slow:
                    score += weights['trend'] * 0.5
            # RSI
            if 'rsi' in indicators:
                rsi = indicators['rsi']
                rsi_value = rsi.get('value') if isinstance(rsi, dict) else rsi
                if rsi_value < 30 or rsi_value > 70:
                    score += weights['momentum'] * 1.0
                elif 40 <= rsi_value <= 60:
                    score += weights['momentum'] * 0.5
            # CCI
            if 'cci' in indicators:
                cci = indicators['cci']
                cci_value = cci.get('value') if isinstance(cci, dict) else cci
                if cci_value > 100:
                    score += weights['oscillators'] * 1.0
                elif cci_value < -100:
                    score += weights['oscillators'] * 1.0
                elif abs(cci_value) < 50:
                    score += weights['oscillators'] * 0.3
            # ADX
            if 'adx' in indicators:
                adx = indicators['adx']
                adx_value = adx.get('value') if isinstance(adx, dict) else adx
                di_plus = adx.get('di_plus') if isinstance(adx, dict) else 0
                di_minus = adx.get('di_minus') if isinstance(adx, dict) else 0
                if adx_value > 25:
                    score += weights['trend_strength'] * 1.0
                    if di_plus > di_minus:
                        score += weights['trend'] * 0.5
                    elif di_minus > di_plus:
                        score += weights['trend'] * 0.5
                elif adx_value > 20:
                    score += weights['trend_strength'] * 0.5
            # BB
            if 'bb' in indicators:
                bb = indicators['bb']
                bb_upper = bb.get('upper') if isinstance(bb, dict) else 0
                bb_lower = bb.get('lower') if isinstance(bb, dict) else 0
                bb_middle = bb.get('middle') if isinstance(bb, dict) else 1
                if abs(bb_middle) > 1e-9:
                    bb_width = (bb_upper - bb_lower) / bb_middle
                    if bb_width < 0.02:
                        score += weights['volatility'] * 1.0
                    elif bb_width < 0.05:
                        score += weights['volatility'] * 0.5
                else:
                    logger.warning(
    f"Bollinger Band middle is zero or near-zero, skipping BB width calculation for technical score.")
            if 'atr' in indicators:
                atr = indicators['atr']
                atr_value = atr.get('value') if isinstance(atr, dict) else atr
                if 0.01 <= atr_value <= 0.03:
                    score += weights['volatility'] * 1.0
            # OBV
            if 'obv' in indicators:
                obv = indicators['obv']
                obv_trend = obv.get('trend') if isinstance(
                    obv, dict) else 'down'
                if obv_trend == 'up':
                    score += weights['volume'] * 1.0
            if 'vwap' in indicators:
                vwap = indicators['vwap']
                vwap_price = vwap.get('price') if isinstance(vwap, dict) else 0
                vwap_value = vwap.get('value') if isinstance(vwap, dict) else 0
                if vwap_price > vwap_value:
                    score += weights['volume'] * 0.5
            if 'sr' in indicators:
                sr = indicators['sr']
                sr_price = sr.get('price') if isinstance(sr, dict) else 0
                sr_support = sr.get('support') if isinstance(sr, dict) else 0
                sr_resistance = sr.get(
                    'resistance') if isinstance(sr, dict) else 0
                if sr_price > sr_support and sr_price < sr_resistance:
                    score += weights['support_resistance'] * 1.0
            return min(score, 1.0)
        except Exception as e:
            logger.error(f"Error calculating technical score: {e}")
            return 0.0
            
    async def scan_opportunities(
    self, risk_per_trade: float = 50.0) -> List[TradingOpportunity]:
        """Scan all symbols for trading opportunities with rate limiting and batch processing."""
        if not hasattr(self, '_processing_lock'):
            self._processing_lock = asyncio.Lock()
            
        async with self._processing_lock:  # Add lock to prevent concurrent processing
            try:
                logger.info("Starting opportunity scan")
                # Get all available symbols
                symbols = await self.discover_symbols()
                
                # Limit the number of symbols to process
                MAX_SYMBOLS_TO_PROCESS = 20  # Process only top 20 symbols
                if len(symbols) > MAX_SYMBOLS_TO_PROCESS:
                    logger.info(
    f"Limiting symbol processing to top {MAX_SYMBOLS_TO_PROCESS} symbols")
                    symbols = symbols[:MAX_SYMBOLS_TO_PROCESS]
                
                logger.info(
    f"Processing {
        len(symbols)} symbols: {
            ', '.join(symbols)}")
                
                # Constants for rate limiting and concurrency control
                BATCH_SIZE = 5  # Number of symbols to process in parallel
                RATE_LIMIT_DELAY = 1.0  # Delay between batches in seconds
                MAX_RETRIES = 2  # Reduced from 3 to 2
                MAX_CONCURRENT_TASKS = 5  # Reduced from 10 to 5
                
                opportunities = []
                total_symbols = len(symbols)
                
                # Create a semaphore to limit concurrent tasks
                semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
                
                async def process_with_semaphore(
    symbol: str) -> Optional[TradingOpportunity]:
                    """Process a symbol with semaphore control."""
                    async with semaphore:
                        logger.debug(f"Processing symbol: {symbol}")
                        result = await self._process_symbol_with_retry(symbol, risk_per_trade, MAX_RETRIES)
                        if result:
                            logger.info(
    f"Found opportunity for {symbol}: {
        result.direction} at {
            result.entry_price}")
                        return result
                
                # Process symbols in batches
                for i in range(0, total_symbols, BATCH_SIZE):
                    batch_symbols = symbols[i:i + BATCH_SIZE]
                    logger.info(
                        f"Processing batch {i // BATCH_SIZE + 1}/{(total_symbols + BATCH_SIZE - 1) // BATCH_SIZE}: {', '.join(batch_symbols)}")
                    
                    # Create tasks for the current batch with semaphore control
                    tasks = []
                    for symbol in batch_symbols:
                        task = asyncio.create_task(
                            process_with_semaphore(symbol))
                        tasks.append(task)
                    
                    # Process batch concurrently with timeout
                    try:
                        batch_results = await asyncio.wait_for(
                            asyncio.gather(*tasks, return_exceptions=True),
                            timeout=30.0  # 30 second timeout per batch
                        )
                    except asyncio.TimeoutError:
                        logger.error(
    f"Batch processing timed out for symbols: {
        ', '.join(batch_symbols)}")
                        continue
                    
                    # Filter out exceptions and add valid opportunities
                    for result in batch_results:
                        if isinstance(result, Exception):
                            logger.error(f"Error processing symbol: {result}")
                            continue
                        if result:
                            opportunities.append(result)
                    
                    # Add delay between batches to respect rate limits
                    if i + BATCH_SIZE < total_symbols:
                        await asyncio.sleep(RATE_LIMIT_DELAY)
                
                # Sort opportunities by score
                opportunities.sort(key=lambda x: x.score, reverse=True)
                
                # Update opportunities dictionary
                self.opportunities = {opp.symbol: opp for opp in opportunities}
                
                logger.info(
    f"Found {
        len(opportunities)} opportunities out of {total_symbols} symbols")
                if opportunities:
                    logger.info(
                        f"Top opportunities: {', '.join([f'{opp.symbol}({opp.score:.2f})' for opp in opportunities[:3]])}")
                return opportunities
                
            except Exception as e:
                logger.error(f"Error scanning opportunities: {e}")
                return []
            
    def _validate_signal(self, signal: Dict) -> SignalValidationResult:
        """Validate a trading signal."""
        errors = []
        warnings = []

        # Required fields based on the signal structure from SignalGenerator
        # Expected fields are 'symbol', 'direction', 'entry', 'take_profit',
        # 'stop_loss', 'confidence', 'indicators'
        required_fields = [
    'symbol',
    'direction',
    'entry',
    'take_profit',
    'stop_loss',
    'confidence',
     'indicators']
        
        # Check for presence of required fields
        for field in required_fields:
            if field not in signal:
                # Use a more informative error message if a level is missing
                if field in ['entry', 'take_profit', 'stop_loss']:
                    errors.append(
    f"Missing required trading level in signal: {field}")
                else:
                    errors.append(f"Missing required field in signal: {field}")

        # If essential fields are missing, stop validation here
        if errors:
            return SignalValidationResult(False, errors, warnings)

        # Validate field types and values
        try:
            if not isinstance(signal['symbol'], str):
                errors.append("Symbol must be a string")

            # Allow both 'LONG' and 'SHORT' for direction
            if signal['direction'] not in ['LONG', 'SHORT']:
                errors.append("Direction must be 'LONG' or 'SHORT'")

            # Validate entry, take_profit, stop_loss
            for level_field in ['entry', 'take_profit', 'stop_loss']:
                # Check if the value is numeric and positive
                value = signal[level_field]
                if not (isinstance(value, (int, float)) and value > 0):
                     # Add a specific check for non-positive values
                     if isinstance(value, (int, float)) and value <= 0:
                         errors.append(
                             f"{level_field.replace('_', ' ').capitalize()} must be a positive number (got {value})")
                     else:
                         errors.append(
    f"{
        level_field.replace(
            '_',
            ' ').capitalize()} must be a number (got {
                type(value).__name__})")

            # Validate confidence (using the key 'confidence')
            confidence_value = signal.get('confidence')
            if not isinstance(confidence_value, (int, float)
                              ) or not 0.0 <= confidence_value <= 1.0:
                # Add a specific message if the value is outside the 0-1 range
                if isinstance(confidence_value, (int, float)):
                    errors.append(
    f"Confidence must be a number between 0 and 1 (got {confidence_value})")
                else:
                    errors.append(
    f"Confidence must be a number (got {
        type(confidence_value).__name__})")

            if not isinstance(signal.get('indicators', {}), dict):
                errors.append("Indicators must be a dictionary")

            # Validate indicators (optional deep validation can be added here)
            # Example: Validate RSI if present
            rsi_value = signal['indicators'].get('rsi')
            if rsi_value is not None:
                if not isinstance(rsi_value, (int, float)
                                  ) or not 0 <= rsi_value <= 100:
                    warnings.append(
    f"RSI value out of normal range (0-100) in indicators (got {rsi_value})")

            # Example: Validate MACD if present
            macd_value = signal['indicators'].get('macd')
            if macd_value is not None:
                 if not isinstance(
    macd_value,
     dict) or 'value' not in macd_value or 'signal' not in macd_value:
                     warnings.append(
                         "MACD indicator missing required fields or is not a dict in indicators")

            # Check for extreme values or inconsistencies (example: stop_loss
            # on wrong side)
            entry = signal['entry']
            stop_loss = signal['stop_loss']
            take_profit = signal['take_profit']

            if signal['direction'] == 'LONG':
                if stop_loss >= entry:
                    errors.append(
                        "LONG trade stop loss must be strictly below entry price")
                # Using >= and <= for TP/SL relative to entry to catch
                # potential issues
                if take_profit <= entry:
                     warnings.append(
                         "LONG trade take profit is not strictly above entry price")
                 # Check if stop_loss is too far from entry (more than entry
                 # itself, e.g., 100% loss potential in one step)
                if entry > 0 and abs(
    entry - stop_loss) / entry > 0.95:  # 95% max distance as a heuristic
                    warnings.append(
    f"LONG trade stop loss is very far from entry price ({
        abs(
            entry -
            stop_loss) /
             entry:.2f}%) - potential data issue or wide range")

            elif signal['direction'] == 'SHORT':
                 if stop_loss <= entry:
                     errors.append(
                         "SHORT trade stop loss must be strictly above entry price")
                 if take_profit >= entry:
                      warnings.append(
                          "SHORT trade take profit is not strictly below entry price")
                 # Check if stop_loss is too far from entry
                 if entry > 0 and abs(entry - stop_loss) / entry > 0.95:
                     warnings.append(
    f"SHORT trade stop loss is very far from entry price ({
        abs(
            entry -
            stop_loss) /
             entry:.2f}%) - potential data issue or wide range")

            # Calculate risk_amount and reward_amount
            risk_amount = abs(entry - stop_loss)
            reward_amount = abs(take_profit - entry)

            # Validate risk_amount and reward_amount
            # Use a small epsilon for floating point comparison if exact zero
            # is too strict
            if risk_amount <= 1e-9:  # Effectively zero
                errors.append(
                    "Risk amount is zero or too small, leading to invalid risk-reward calculation.")
            if reward_amount <= 1e-9:  # Effectively zero
                errors.append(
                    "Reward amount is zero or too small, leading to invalid risk-reward calculation.")

            # Check for extreme confidence value (already handled by type/range
            # check, but can add specific warnings)
            if 0.9 <= confidence_value < 1.0:
                 warnings.append("High confidence value detected (>=0.9)")
            elif confidence_value == 1.0:
                 warnings.append(
                     "Maximum confidence value (1.0) detected - ensure this isn't a default or placeholder")

            # Check for very tight stop loss (potentially due to calculation
            # error or illiquid symbol)
            if entry > 0:
                stop_loss_percentage = abs(entry - stop_loss) / entry
                # Lowering threshold for tight stop loss warning
                if 0 < stop_loss_percentage < 0.001:  # e.g., less than 0.1% from entry
                    warnings.append(
    f"Very tight stop loss detected ({
        stop_loss_percentage:.4f}%) - may be prone to slippage or whipsaw")
                # The existing check for zero distance stop loss is still relevant
                # if stop_loss_percentage == 0:
                # errors.append("Stop loss is at the entry price, resulting in
                # zero risk distance.")

        except Exception as e:
            # Catch any unexpected errors during the validation process itself
            errors.append(
    f"Unexpected error during signal validation: {
        str(e)}")
            logger.error(
    f"Unexpected error during signal validation for {
        signal.get(
            'symbol',
            'UNKNOWN')}: {e}",
             exc_info=True)

        return SignalValidationResult(len(errors) == 0, errors, warnings)

    def _get_cached_signal(self, symbol: str) -> Optional[Dict]:
        """Get a cached signal if it exists and is still valid."""
        if symbol in self.signal_cache:
            cached = self.signal_cache[symbol]
            if datetime.now() < cached.expires_at:
                # Ensure cached signal has required keys for current validation logic
                # If not, treat as invalid cache
                required_keys = [
    'symbol',
    'direction',
    'entry',
    'take_profit',
    'stop_loss',
    'confidence',
     'indicators']
                if all(key in cached.signal for key in required_keys):
                    return cached.signal
                else:
                     logger.warning(
    f"Cached signal for {symbol} is missing required keys. Discarding cache.")
                     del self.signal_cache[symbol]
        return None
        
    def _cache_signal(self, symbol: str, signal: Dict):
        """Cache a signal with expiration."""
        # Ensure the signal being cached has the required structure
        required_keys = [
    'symbol',
    'direction',
    'entry',
    'take_profit',
    'stop_loss',
    'confidence',
     'indicators']
        if not all(key in signal for key in required_keys):
             logger.error(
    f"Attempted to cache a signal for {symbol} missing required keys. Not caching.")
             return  # Do not cache incomplete signals

        expires_at = datetime.now() + timedelta(seconds=self.cache_duration)
        self.signal_cache[symbol] = CachedSignal(
            signal, datetime.now(), expires_at)

        # Also save to disk for persistence
        try:
            cache_file = self.cache_dir / f"{symbol}.json"
            # Ensure the signal structure is valid before writing to disk
            if not self._validate_signal(signal).is_valid:
                 logger.warning(
    f"Attempted to cache an invalid signal for {symbol} to disk. Skipping disk cache.")
                 # Optional: log the validation errors here if needed
            else:
                 with open(cache_file, 'w') as f:
                    json.dump({
                        'signal': signal,
                        'timestamp': datetime.now().isoformat(),
                        'expires_at': expires_at.isoformat()
                    }, f)
        except Exception as e:
            logger.error(
    f"Error saving signal to cache file for {symbol}: {e}")

    async def _process_symbol_with_retry(
    self,
    symbol: str,
    risk_per_trade: float,
     max_retries: int) -> Optional[TradingOpportunity]:
        """Process a symbol with retry logic."""
        for attempt in range(max_retries):
            try:
                # Get market data
                market_data = await self.get_market_conditions(symbol)
                if not market_data:
                    logger.warning(f"No market data available for {symbol}")
                    return None

                # Check data freshness
                if not self.check_data_freshness(market_data):
                    logger.warning(f"Data too old for {symbol}")
                    return None

                # Apply advanced filters
                passed, reasons = self._apply_advanced_filters(market_data)
                if not passed:
                    logger.debug(
    f"Symbol {symbol} excluded by filters: {
        '; '.join(reasons)}")
                    return None

                # Generate signal
                signal = await self.signal_generator.generate_signals(market_data)
                if not signal:
                    logger.debug(f"No signal generated for {symbol}")
                    return None

                # Extract and validate signal data
                extracted_signal = self._extract_signal_data(signal)
                if not extracted_signal:
                    logger.warning(f"Invalid signal data for {symbol}")
                    return None

                # Create opportunity
                opportunity = TradingOpportunity(
                    symbol=extracted_signal['symbol'],
                    direction=extracted_signal['direction'],
                    entry_price=extracted_signal['entry'],
                    take_profit=extracted_signal['take_profit'],
                    stop_loss=extracted_signal['stop_loss'],
                    confidence=extracted_signal['confidence'],
                    market_regime=extracted_signal['market_regime'],
                    indicators=extracted_signal['indicators'],
                    data_freshness=extracted_signal['data_freshness'],
                    timestamp=datetime.fromtimestamp(
                        extracted_signal['timestamp'])
                )

                # Calculate opportunity score
                opportunity.score = self.calculate_opportunity_score(
                    opportunity)

                # Log successful opportunity creation
                logger.info(
    f"Created opportunity for {symbol}: {
        opportunity.direction} at {
            opportunity.entry_price}")

                return opportunity

            except Exception as e:
                logger.error(
    f"Error processing {symbol} (attempt {
        attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)  # Wait before retry
                continue

        return None

    def _apply_advanced_filters(
        self, market_data: Dict) -> Tuple[bool, List[str]]:
        """Apply advanced filters to market data, returning reasons for exclusion."""
        symbol = market_data.get('symbol', 'UNKNOWN')
        reasons = []

        try:
            # Volume filter
            volume_24h = float(market_data.get('ticker_24h', {}).get('volume', 0))
            if volume_24h < self.min_volume_24h:
                reasons.append(f"Low volume: {volume_24h:.2f} < {self.min_volume_24h:.2f}")

            # Spread filter
            spread = float(self._calculate_spread(market_data.get('orderbook', {})))
            if spread > self.max_spread:
                reasons.append(f"Spread too high: {spread:.4f} > {self.max_spread:.4f}")

            # Enhanced liquidity filter with multiple depth ranges
            orderbook = market_data.get('orderbook', {})
            if orderbook:
                try:
                    mid_price = (float(orderbook['asks'][0][0]) + float(orderbook['bids'][0][0])) / 2
                    volatility = float(self.calculate_volatility(market_data.get('klines', [])))
                    
                    # Define depth ranges and their minimum requirements
                    depth_ranges = [
                        (0.001, 0.0025, 10000),  # 0.1% range, minimum $10k
                        (0.0025, 0.005, 20000),  # 0.25% range, minimum $20k
                        (0.005, 0.01, 50000)     # 0.5% range, minimum $50k
                    ]
                    
                    # Adjust requirements based on volatility
                    volatility_factor = 1 + (volatility * 10)
                    
                    # Check each depth range
                    depth_metrics = []
                    for min_range, max_range, min_depth in depth_ranges:
                        range_min = mid_price * (1 - max_range)
                        range_max = mid_price * (1 + max_range)
                        
                        buy_depth = sum(float(qty) for price, qty in orderbook['bids'] if range_min <= float(price) <= mid_price)
                        sell_depth = sum(float(qty) for price, qty in orderbook['asks'] if mid_price <= float(price) <= range_max)
                        avg_depth = (buy_depth + sell_depth) / 2
                        
                        adjusted_min_depth = min_depth * volatility_factor
                        depth_metrics.append({
                            'range': f"{min_range*100:.1f}%-{max_range*100:.1f}%",
                            'depth': avg_depth,
                            'required': adjusted_min_depth,
                            'passed': avg_depth >= adjusted_min_depth
                        })
                    
                    # Log depth metrics
                    depth_log = "; ".join([
                        f"{m['range']}: ${m['depth']:.2f} (req: ${m['required']:.2f})"
                        for m in depth_metrics
                    ])
                    logger.debug(f"Depth metrics for {symbol}: {depth_log}")
                    
                    # Check if any range passes
                    if not any(m['passed'] for m in depth_metrics):
                        reasons.append(
                            f"Insufficient liquidity across all ranges (volatility: {volatility:.4f}): {depth_log}"
                        )
                        return False, reasons
                except (ValueError, TypeError, IndexError) as e:
                    logger.error(f"Error processing orderbook for {symbol}: {e}")
                    reasons.append("Invalid orderbook data")
                    return False, reasons

            # Open interest filter
            open_interest = float(market_data.get('open_interest', 0))
            if open_interest < self.min_open_interest:
                reasons.append(f"Low open interest: {open_interest:.2f} < {self.min_open_interest:.2f}")

            # Market cap filter
            market_cap = float(self._calculate_market_cap(market_data.get('ticker_24h', {})))
            if market_cap < self.min_market_cap:
                reasons.append(f"Low market cap: {market_cap:.2f} < {self.min_market_cap:.2f}")

            # Volatility filter
            volatility = float(self.calculate_volatility(market_data.get('klines', [])))
            if not (self.min_volatility <= volatility <= self.max_volatility):
                reasons.append(f"Volatility out of range: {volatility:.4f} ({self.min_volatility:.4f}-{self.max_volatility:.4f})")

            # Funding rate filter
            funding_rate = float(market_data.get('funding_rate', 0))
            if not (self.min_funding_rate <= funding_rate <= self.max_funding_rate):
                reasons.append(f"Funding rate out of range: {funding_rate:.4f} ({self.min_funding_rate:.4f}-{self.max_funding_rate:.4f})")

            if reasons:
                logger.debug(f"Symbol {symbol} excluded by advanced filters: {'; '.join(reasons)}")
                logger.info(f"Excluded {symbol}: {'; '.join(reasons)}")
                return False, reasons

            return True, []
            
        except Exception as e:
            logger.error(f"Error applying advanced filters for {symbol}: {e}")
            return False, [f"Error in filter application: {str(e)}"]

    def _estimate_slippage(self, orderbook: Dict, order_size: float) -> float:
        """Estimate slippage for a simulated market order."""
        try:
            if not orderbook or 'bids' not in orderbook or 'asks' not in orderbook:
                return float('inf')
                
            # Calculate average price for buying
            buy_price = 0
            remaining_size = order_size
            for price, qty in orderbook['asks']:
                if remaining_size <= 0:
                    break
                executed = min(remaining_size, qty)
                buy_price += price * executed
                remaining_size -= executed
                
            if remaining_size > 0:
                return float('inf')  # Not enough liquidity
                
            avg_buy_price = buy_price / order_size
            
            # Calculate average price for selling
            sell_price = 0
            remaining_size = order_size
            for price, qty in orderbook['bids']:
                if remaining_size <= 0:
                    break
                executed = min(remaining_size, qty)
                sell_price += price * executed
                remaining_size -= executed
                
            if remaining_size > 0:
                return float('inf')  # Not enough liquidity
                
            avg_sell_price = sell_price / order_size
            
            # Calculate slippage as percentage
            mid_price = (orderbook['asks'][0][0] + orderbook['bids'][0][0]) / 2
            buy_slippage = abs(avg_buy_price - mid_price) / mid_price
            sell_slippage = abs(avg_sell_price - mid_price) / mid_price
            
            return max(buy_slippage, sell_slippage)
            
        except Exception as e:
            logger.error(f"Error estimating slippage: {e}")
            return float('inf')
            
    def _check_price_stability(self, ohlcv: List[Dict]) -> bool:
        """Check if price is stable enough for trading."""
        try:
            closes = [float(candle['close']) for candle in ohlcv]
            returns = np.diff(closes) / closes[:-1]
            
            # Check for price gaps
            max_gap = 0.05  # 5% maximum price gap
            if np.max(np.abs(returns)) > max_gap:
                return False
                
            # Check for price stability
            rolling_std = np.std(returns[-20:])  # Last 20 periods
            if rolling_std > 0.02:  # 2% maximum standard deviation
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error checking price stability: {e}")
            return False
            
    def _check_volume_trend(self, ohlcv: List[Dict], signal_direction: Optional[str] = None) -> bool:
        """Check if volume trend is valid for trading."""
        try:
            if not ohlcv or len(ohlcv) < 20:
                return False
                
            # Calculate volume moving averages
            volumes = [float(k['volume']) for k in ohlcv]
            vol_ma5 = sum(volumes[-5:]) / 5
            vol_ma20 = sum(volumes[-20:]) / 20
            
            # Calculate volume coefficient of variation
            vol_cv = statistics.stdev(volumes[-20:]) / statistics.mean(volumes[-20:])
            
            # Check for volume consistency with relaxed threshold
            if vol_cv > 2.0:  # Allow higher coefficient of variation
                logger.warning(f"High volume variation: {vol_cv:.2f}")
                return False
            else:
                # Standard checks for unconfirmed signals
                if vol_ma5 < vol_ma20 * 0.2:  # Require at least 20% of average volume
                    logger.debug(f"Low recent volume: {vol_ma5/vol_ma20:.2%} of average")
                    return False
                
                # Check for volume consistency
                if vol_cv > 1.5:  # Standard threshold for variation
                    logger.debug(f"High volume variation: {vol_cv:.2f}")
                    return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error checking volume trend: {e}")
            return False

    async def initialize(self) -> None:
        """Initialize the symbol discovery process."""
        try:
            logger.info("Initializing symbol discovery...")
            # Ensure exchange client is initialized
            if not self.exchange_client:
                raise ValueError("Exchange client not initialized")
            # Load initial symbols
            await self._load_symbols()
            # If no symbols loaded, try to discover them
            if not self.symbols:
                logger.info("No symbols loaded, attempting discovery...")
                discovered_symbols = await self.discover_symbols()
                if discovered_symbols:
                    self.symbols = set(discovered_symbols)
                    logger.info(f"Discovered {len(self.symbols)} symbols")
                else:
                    # Fallback to static symbols
                    static_symbols = os.getenv('TRADING_SYMBOLS', 'BTCUSDT').split(',')
                    self.symbols = set(static_symbols)
                    logger.info(f"Using fallback static symbols: {', '.join(static_symbols)}")
            logger.info(f"Symbol discovery initialized with {len(self.symbols)} symbols")

        except Exception as e:
            logger.error(f"Error initializing symbol discovery: {e}")
            raise

    async def _load_symbols(self) -> None:
        """Load symbols from the exchange."""
        try:
            symbols = await self.exchange_client.get_all_symbols()
            self.symbols = symbols
            logger.info(f"Loaded {len(self.symbols)} symbols from exchange")
        except Exception as e:
            logger.error(f"Error loading symbols: {e}")
            self.symbols = []

    async def get_symbols(self) -> list:
        """Return the list of discovered symbols."""
        return self.symbols 

    async def get_market_conditions(self, symbol: str) -> Dict:
        """
        Get current market conditions for a symbol.
        
        Args:
            symbol: Trading symbol to analyze
            
        Returns:
            Dict containing market conditions including:
            - trend: str ('bullish', 'bearish', 'neutral')
            - volatility: float (0-1)
            - volume_profile: Dict (volume distribution)
            - liquidity: float (0-1)
            - market_depth: Dict (order book depth)
        """
        try:
            if not symbol:
                return {}
                
            # Get required data
            ticker = await self.exchange_client.get_ticker(symbol)
            klines = await self.exchange_client.get_klines(symbol, interval='1h', limit=24)
            order_book = await self.exchange_client.get_order_book(symbol)
            
            if not ticker or not klines or not order_book:
                return {}
                
            # Calculate trend
            closes = [float(k['close']) for k in klines]
            sma_20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else sum(closes) / len(closes)
            current_price = float(ticker['last'])
            
            trend = 'neutral'
            if current_price > sma_20 * 1.02:
                trend = 'bullish'
            elif current_price < sma_20 * 0.98:
                trend = 'bearish'
                
            # Calculate volatility
            returns = [abs(closes[i] - closes[i-1])/closes[i-1] for i in range(1, len(closes))]
            volatility = sum(returns) / len(returns) if returns else 0
            
            # Calculate volume profile
            volumes = [float(k['volume']) for k in klines]
            avg_volume = sum(volumes) / len(volumes)
            volume_profile = {
                'current': float(ticker['volume']),
                'average': avg_volume,
                'trend': 'increasing' if volumes[-1] > avg_volume else 'decreasing'
            }
            
            # Calculate liquidity
            # Calculate key metrics
            spread = self._calculate_spread(orderbook)
            liquidity = self._calculate_liquidity(orderbook)
            volatility = self.calculate_volatility(market_data.get('ohlcv', []))
            market_cap = self._calculate_market_cap(ticker_24h)
            
            # Get technical indicators
            indicators = self.signal_generator._calculate_indicators(market_data)
            
            # Determine market regime
            regime = self._determine_market_regime(indicators, volatility)
            
            # Calculate trend strength
            trend_strength = self._calculate_trend_strength(indicators)
            
            # Check for market anomalies
            anomalies = self._check_market_anomalies(market_data, indicators)
            
            return {
                'symbol': symbol,
                'timestamp': datetime.now().isoformat(),
                'spread': spread,
                'liquidity': liquidity,
                'volatility': volatility,
                'market_cap': market_cap,
                'regime': regime,
                'trend_strength': trend_strength,
                'anomalies': anomalies,
                'indicators': {
                    'rsi': indicators.get('rsi', 0),
                    'macd': indicators.get('macd', {}),
                    'bb': indicators.get('bb', {}),
                    'adx': indicators.get('adx', 0),
                    'atr': indicators.get('atr', 0)
                },
                'volume': {
                    'current': float(ticker_24h.get('volume', 0)),
                    'change_24h': float(ticker_24h.get('volumeChange', 0)),
                    'trend': self._check_volume_trend(market_data.get('ohlcv', []))
                },
                'price': {
                    'current': float(ticker_24h.get('lastPrice', 0)),
                    'change_24h': float(ticker_24h.get('priceChangePercent', 0)),
                    'high_24h': float(ticker_24h.get('highPrice', 0)),
                    'low_24h': float(ticker_24h.get('lowPrice', 0))
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting market conditions for {symbol}: {e}")
            return {}
            
    def check_data_freshness(self, data: Dict) -> bool:
        """Check if market data is fresh and valid."""
        try:
            if not data:
                return False
                
            # Check timestamp
            timestamp = data.get('timestamp')
            if not timestamp:
                return False
                
            # Convert string timestamp to datetime if needed
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
                
            # Check if data is too old (more than 5 minutes)
            if (datetime.now() - timestamp).total_seconds() > 300:
                logger.warning(f"Data is too old: {(datetime.now() - timestamp).total_seconds()} seconds")
                return False
                
            # Check for required fields
            required_fields = ['symbol', 'price', 'volume', 'indicators']
            for field in required_fields:
                if field not in data:
                    logger.warning(f"Missing required field: {field}")
                    return False
                    
            # Check for valid price
            price = data.get('price', {}).get('current')
            if not price or price <= 0:
                logger.warning(f"Invalid price: {price}")
                return False
                
            # Check for valid volume
            volume = data.get('volume', {}).get('current')
            if not volume or volume < 0:
                logger.warning(f"Invalid volume: {volume}")
                return False
                
            # Check for valid indicators
            indicators = data.get('indicators', {})
            if not indicators:
                logger.warning("Missing indicators")
                return False
                
            # Check for valid RSI
            rsi = indicators.get('rsi')
            if not rsi or not (0 <= rsi <= 100):
                logger.warning(f"Invalid RSI: {rsi}")
                return False
                
            # Check for valid MACD
            macd = indicators.get('macd', {})
            if not macd or not all(k in macd for k in ['histogram', 'signal', 'macd']):
                logger.warning("Invalid MACD data")
                return False
                
            # Check for valid Bollinger Bands
            bb = indicators.get('bb', {})
            if not bb or not all(k in bb for k in ['upper', 'middle', 'lower']):
                logger.warning("Invalid Bollinger Bands data")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error checking data freshness: {e}")
            return False

    def _determine_market_regime(self, indicators: Dict, volatility: float) -> str:
        """Determine the current market regime."""
        try:
            rsi = indicators.get('rsi', 50)
            macd_hist = indicators.get('macd', {}).get('histogram', 0)
            adx = indicators.get('adx', 0)
            
            # High volatility regime
            if volatility > 0.05:  # 5% daily volatility
                return 'high_volatility'
                
            # Strong trend regime
            if adx > 25:
                if macd_hist > 0:
                    return 'strong_uptrend'
                else:
                    return 'strong_downtrend'
                    
            # Range-bound regime
            if 30 <= rsi <= 70:
                return 'range_bound'
                
            # Overbought/Oversold regime
            if rsi > 70:
                return 'overbought'
            elif rsi < 30:
                return 'oversold'
                
            return 'neutral'
            
        except Exception as e:
            logger.error(f"Error determining market regime: {e}")
            return 'unknown'

    def _calculate_trend_strength(self, indicators: Dict) -> float:
        """Calculate the strength of the current trend."""
        try:
            adx = indicators.get('adx', 0)
            macd_hist = abs(indicators.get('macd', {}).get('histogram', 0))
            rsi = indicators.get('rsi', 50)
            
            # Normalize indicators
            adx_score = min(adx / 100, 1.0)  # ADX max is typically 100
            macd_score = min(macd_hist / 0.1, 1.0)  # Normalize MACD histogram
            rsi_score = 1.0 - abs(50 - rsi) / 50  # Distance from neutral RSI
            
            # Weighted average
            return (0.4 * adx_score + 0.4 * macd_score + 0.2 * rsi_score)
            
        except Exception as e:
            logger.error(f"Error calculating trend strength: {e}")
            return 0.0

    def _check_market_anomalies(self, market_data: Dict, indicators: Dict) -> List[str]:
        """Check for market anomalies and unusual conditions."""
        anomalies = []
        try:
            # Check for extreme volatility
            volatility = self.calculate_volatility(market_data.get('ohlcv', []))
            if volatility > 0.1:  # 10% daily volatility
                anomalies.append('extreme_volatility')
                
            # Check for volume spikes
            volume_data = market_data.get('ohlcv', [])
            if len(volume_data) >= 2:
                current_volume = volume_data[-1].get('volume', 0)
                avg_volume = sum(candle.get('volume', 0) for candle in volume_data[:-1]) / (len(volume_data) - 1)
                if current_volume > avg_volume * 3:  # 3x average volume
                    anomalies.append('volume_spike')
                    
            # Check for price gaps
            if len(volume_data) >= 2:
                current_open = volume_data[-1].get('open', 0)
                prev_close = volume_data[-2].get('close', 0)
                if prev_close > 0:
                    gap = abs(current_open - prev_close) / prev_close
                    if gap > 0.05:  # 5% gap
                        anomalies.append('price_gap')
                        
            # Check for extreme RSI
            rsi = indicators.get('rsi', 50)
            if rsi > 80:
                anomalies.append('extreme_overbought')
            elif rsi < 20:
                anomalies.append('extreme_oversold')
                
            # Check for MACD divergence
            macd = indicators.get('macd', {})
            if macd.get('histogram', 0) * macd.get('signal', 0) < 0:
                anomalies.append('macd_divergence')
                
            return anomalies
            
        except Exception as e:
            logger.error(f"Error checking market anomalies: {e}")
            return anomalies 

    def _extract_signal_data(self, signal: Dict) -> Optional[Dict]:
        """Extract and validate signal data with proper type conversion."""
        try:
            if not signal:
                return None
                
            # Extract and convert required fields
            extracted = {
                'symbol': str(signal.get('symbol', '')),
                'direction': str(signal.get('direction', '')),
                'entry': float(signal.get('entry', 0.0)),
                'take_profit': float(signal.get('take_profit', 0.0)),
                'stop_loss': float(signal.get('stop_loss', 0.0)),
                'confidence': float(signal.get('confidence', 0.0)),
                'market_regime': str(signal.get('market_regime', '')),
                'timestamp': float(signal.get('timestamp', 0.0))
            }
            
            # Extract and convert indicators
            indicators = signal.get('indicators', {})
            if isinstance(indicators, dict):
                extracted['indicators'] = {
                    k: float(v) if isinstance(v, (int, float)) else v
                    for k, v in indicators.items()
                }
            else:
                extracted['indicators'] = {}
                
            # Extract and convert data freshness
            freshness = signal.get('data_freshness', {})
            if isinstance(freshness, dict):
                extracted['data_freshness'] = {
                    k: float(v) for k, v in freshness.items()
                }
            else:
                extracted['data_freshness'] = {}
                
            # Validate required fields
            required_fields = ['symbol', 'direction', 'entry', 'take_profit', 'stop_loss', 'confidence']
            missing_fields = [field for field in required_fields if not extracted.get(field)]
            
            if missing_fields:
                logger.warning(f"Missing required fields in signal: {missing_fields}")
                return None
                
            # Validate direction
            if extracted['direction'] not in ['LONG', 'SHORT']:
                logger.warning(f"Invalid direction in signal: {extracted['direction']}")
                return None
                
            # Validate numeric fields
            numeric_fields = ['entry', 'take_profit', 'stop_loss', 'confidence']
            for field in numeric_fields:
                if not isinstance(extracted[field], (int, float)) or extracted[field] <= 0:
                    logger.warning(f"Invalid {field} value in signal: {extracted[field]}")
                    return None
                    
            return extracted
            
        except Exception as e:
            logger.error(f"Error extracting signal data: {e}")
            return None