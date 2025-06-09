from typing import Dict, List, Optional, Set, Union, Any
import asyncio
import logging
from datetime import datetime, timedelta
import numpy as np
from dataclasses import dataclass, field
from src.market_data.exchange_client import ExchangeClient
from src.signals.signal_generator import SignalGenerator
import os
from functools import lru_cache
import json
from pathlib import Path
import pandas as pd
from typing import Tuple
import time
from ..strategy.dynamic_config import strategy_config
from ..risk.risk_manager import RiskManager
from ..database.database import Database
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

@dataclass
class TradingOpportunity:
    symbol: str
    direction: str  # 'LONG' or 'SHORT'
    entry_price: float
    take_profit: float
    stop_loss: float
    confidence: float
    leverage: float
    risk_reward: float
    volume_24h: float
    volatility: float
    score: float
    indicators: Dict = field(default_factory=dict)
    reasoning: List[str] = field(default_factory=list)
    # Add new metrics
    book_depth: float = 0.0  # Average depth within 0.25%
    oi_trend: float = 0.0  # Open interest trend over past 10 minutes
    volume_trend: float = 0.0  # Volume trend over past 10 minutes
    slippage: float = 0.0  # Estimated slippage for 0.1 BTC order
    data_freshness: float = 0.0  # Time since last data update in seconds

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
        log_file = log_dir / f"signals_{signal.timestamp.strftime('%Y%m%d')}.jsonl"
        
        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
            
    def update_outcome(self, symbol: str, outcome: str, pnl: float, exit_price: float):
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
            'holding_time': (signal.exit_time - signal.timestamp).total_seconds() / 3600,  # hours
            'score': signal.score,
            'confidence': signal.confidence
        }
        
        log_dir = Path('logs/outcomes')
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"outcomes_{signal.exit_time.strftime('%Y%m%d')}.jsonl"
        
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
            level_signals = [s for s in completed if low <= s.confidence < high]
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
                win_rate = sum(1 for s in signals_above if s.outcome == 'win') / len(signals_above)
                win_rates.append((threshold, win_rate))
                
        optimal_score = max(
            (threshold for threshold, win_rate in win_rates if win_rate >= self.win_rate_threshold),
            default=0.6
        )
        
        # Calculate optimal confidence threshold
        confidences = sorted([s.confidence for s in completed])
        win_rates = []
        for i in range(len(confidences)):
            threshold = confidences[i]
            signals_above = [s for s in completed if s.confidence >= threshold]
            if len(signals_above) >= self.min_samples:
                win_rate = sum(1 for s in signals_above if s.outcome == 'win') / len(signals_above)
                win_rates.append((threshold, win_rate))
                
        optimal_confidence = max(
            (threshold for threshold, win_rate in win_rates if win_rate >= self.win_rate_threshold),
            default=0.6
        )
        
        # Calculate optimal win rate threshold
        win_rates = []
        for i in range(len(scores)):
            threshold = scores[i]
            signals_above = [s for s in completed if s.score >= threshold]
            if len(signals_above) >= self.min_samples:
                win_rate = sum(1 for s in signals_above if s.outcome == 'win') / len(signals_above)
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
    
    def __init__(self, exchange_client_or_config: Union[ExchangeClient, Dict[str, Any]]):
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
        self.update_interval = float(update_interval)  # Convert to float to handle both int and float strings
        
        # Initialize filters
        self.min_volume = self.config.get('min_volume', float(os.getenv('MIN_VOLUME', '1000000')))
        self.min_price = self.config.get('min_price', float(os.getenv('MIN_PRICE', '0.1')))
        self.max_price = self.config.get('max_price', float(os.getenv('MAX_PRICE', '100000')))
        self.min_market_cap = self.config.get('min_market_cap', float(os.getenv('MIN_MARKET_CAP', '10000000')))
        
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
        self.cache_ttl = 5 if self.config.get('scalping_mode', False) else 300  # 5 seconds for scalping, 5 minutes for normal mode
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
        logger.info(f"cache_ttl: {self.cache_ttl} seconds")
        logger.info(f"scalping_mode: {self.config.get('scalping_mode', False)}")
        
        # Cache configuration
        self.cache_dir = Path('cache/signals')
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.signal_cache: Dict[str, CachedSignal] = {}
        self.cache_duration = int(os.getenv('SYMBOL_CACHE_DURATION', '3600'))  # Use SYMBOL_CACHE_DURATION from .env

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
                logger.info(f"Using {len(symbols)} static symbols from configuration: {', '.join(symbols)}")
                return symbols
            else:
                # Dynamic discovery from exchange
                logger.debug("Fetching exchange info for dynamic discovery")
                try:
                    exchange_info = await self.exchange_client.get_exchange_info()
                    logger.debug("Successfully fetched exchange info")
                except Exception as e:
                    logger.error(f"Failed to fetch exchange info: {e}")
                    raise
                
                futures_symbols = [
                    symbol['symbol'] for symbol in exchange_info['symbols']
                    if symbol['status'] == 'TRADING' and symbol['contractType'] == 'PERPETUAL'
                ]
                
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

    async def get_market_data(self, symbol: str) -> Optional[Dict]:
        """Get market data for a symbol with caching."""
        try:
            # Check cache first
            cache_key = f"market_data_{symbol}"
            cached_data = self.cache.get(cache_key)
            required_fields = ['klines', 'ticker_24h', 'orderbook', 'funding_rate', 'open_interest']
            # If we have cached data, check if it has the new structure and is not expired
            if cached_data:
                is_valid = all(field in cached_data and cached_data[field] not in (None, [], {}) for field in required_fields)
                is_fresh = (time.time() - cached_data.get('timestamp', 0)) < self.cache_ttl
                if is_valid and is_fresh:
                    logger.debug(f"Using cached market data for {symbol}")
                    return cached_data
                else:
                    logger.debug(f"Clearing outdated/invalid cache for {symbol}. Valid: {is_valid}, Fresh: {is_fresh}")
                    if cache_key in self.cache:
                        del self.cache[cache_key]

            # Fetch fresh data
            logger.debug(f"Fetching fresh market data for {symbol}")
            klines = await self.exchange_client.get_historical_data(symbol, '1m', limit=100)
            funding_rate = await self.exchange_client.get_funding_rate(symbol)
            ticker = await self.exchange_client.get_ticker_24h(symbol)
            orderbook = await self.exchange_client.get_orderbook(symbol, limit=10)
            open_interest = await self.exchange_client.get_open_interest(symbol)

            # Validate fetched data components
            missing = []
            if klines is None or not klines:
                missing.append('klines')
            if funding_rate is None:
                missing.append('funding_rate')
            if ticker is None:
                missing.append('ticker_24h')
            if orderbook is None or not orderbook.get('bids') or not orderbook.get('asks'):
                missing.append('orderbook')
            if open_interest is None:
                missing.append('open_interest')
            if missing:
                logger.warning(f"Missing or incomplete market data for {symbol}: {missing}. Not caching.")
                return None

            # Structure the data
            market_data = {
                'symbol': symbol, # Add symbol to market data
                'klines': klines,
                'funding_rate': funding_rate,
                'ticker_24h': ticker,
                'orderbook': orderbook,
                'open_interest': open_interest,
                'timestamp': time.time()  # Add timestamp for cache expiration
            }

            # Only cache if all required fields are present and valid
            if all(field in market_data and market_data[field] not in (None, [], {}) for field in required_fields):
                self.cache[cache_key] = market_data
                logger.debug(f"Cached fresh market data for {symbol}")
                return market_data
            else:
                logger.warning(f"Fetched market data for {symbol} is incomplete, not caching. Missing: {[field for field in required_fields if market_data.get(field) in (None, [], {})]}")
                return None

        except Exception as e:
            logger.error(f"Error fetching market data for {symbol}: {str(e)}")
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
            # Calculate liquidity as the sum of (price * quantity) for top 10 levels
            bid_liquidity = sum(float(bid[0]) * float(bid[1]) for bid in orderbook['bids'][:10])
            ask_liquidity = sum(float(ask[0]) * float(ask[1]) for ask in orderbook['asks'][:10])
            
            return (bid_liquidity + ask_liquidity) / 2
        except Exception as e:
            logger.error(f"Error calculating liquidity: {e}")
            return 0.0
            
    def _calculate_market_cap(self, ticker_24h: Dict) -> float:
        """Calculate approximate market cap from 24h data."""
        try:
            # For futures, we'll use 24h quote volume as a proxy for market cap
            # This is an approximation since we don't have circulating supply
            return float(ticker_24h['quoteVolume'])
        except Exception as e:
            logger.error(f"Error calculating market cap: {e}")
            return 0.0

    def calculate_volatility(self, ohlcv: List[Dict]) -> float:
        """Calculate price volatility."""
        closes = [float(candle['close']) for candle in ohlcv]
        returns = np.diff(closes) / closes[:-1]
        return np.std(returns) * np.sqrt(24 * 60)  # Annualized volatility

    def calculate_opportunity_score(self, opportunity: TradingOpportunity) -> float:
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
                
            logger.debug(f"Volume score for {opportunity.symbol}: {volume_score:.2f} (volume: {opportunity.volume_24h:.2f}, threshold: {volume_threshold:.2f})")
            score += volume_score * 0.15
            
            # Risk-reward factor (15%)
            rr_score = min(opportunity.risk_reward / self.min_risk_reward, 3.0)
            logger.debug(f"Risk-reward score for {opportunity.symbol}: {rr_score:.2f} (RR: {opportunity.risk_reward:.2f}, min: {self.min_risk_reward:.2f})")
            score += rr_score * 0.15
            
            # Volatility factor (15% - increased from 10%)
            vol_score = 1.0 - abs(opportunity.volatility - 0.015) / 0.015  # Target 1.5% volatility for scalping
            logger.debug(f"Volatility score for {opportunity.symbol}: {vol_score:.2f} (vol: {opportunity.volatility:.4f})")
            score += vol_score * 0.15
            
            # Leverage factor (5%)
            lev_score = 1.0 - (opportunity.leverage / self.max_leverage)
            logger.debug(f"Leverage score for {opportunity.symbol}: {lev_score:.2f} (lev: {opportunity.leverage:.2f}, max: {self.max_leverage:.2f})")
            score += lev_score * 0.05
            
            # Technical indicators (20% - reduced from 25%)
            tech_score = self._calculate_technical_score(opportunity.indicators)
            logger.debug(f"Technical score for {opportunity.symbol}: {tech_score:.2f}")
            score += tech_score * 0.20
            
            # Apply risk/reward confidence scaling
            if opportunity.risk_reward > 1.5:
                score *= 1.1
                logger.debug(f"Boosting score for {opportunity.symbol} due to good risk/reward ratio")
            elif opportunity.risk_reward < 1.0:
                score *= 0.9
                logger.debug(f"Reducing score for {opportunity.symbol} due to poor risk/reward ratio")
            
            final_score = min(score, 1.0)
            logger.debug(f"Final opportunity score for {opportunity.symbol}: {final_score:.2f}")
            return final_score
            
        except Exception as e:
            logger.error(f"Error calculating opportunity score for {opportunity.symbol}: {e}")
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
                macd_histogram = macd['histogram'] if isinstance(macd, dict) else 0
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
                    logger.warning(f"Bollinger Band middle is zero or near-zero, skipping BB width calculation for technical score.")
            if 'atr' in indicators:
                atr = indicators['atr']
                atr_value = atr.get('value') if isinstance(atr, dict) else atr
                if 0.01 <= atr_value <= 0.03:
                    score += weights['volatility'] * 1.0
            # OBV
            if 'obv' in indicators:
                obv = indicators['obv']
                obv_trend = obv.get('trend') if isinstance(obv, dict) else 'down'
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
                sr_resistance = sr.get('resistance') if isinstance(sr, dict) else 0
                if sr_price > sr_support and sr_price < sr_resistance:
                    score += weights['support_resistance'] * 1.0
            return min(score, 1.0)
        except Exception as e:
            logger.error(f"Error calculating technical score: {e}")
            return 0.0
            
    async def scan_opportunities(self, risk_per_trade: float = 50.0) -> List[TradingOpportunity]:
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
                    logger.info(f"Limiting symbol processing to top {MAX_SYMBOLS_TO_PROCESS} symbols")
                    symbols = symbols[:MAX_SYMBOLS_TO_PROCESS]
                
                logger.info(f"Processing {len(symbols)} symbols: {', '.join(symbols)}")
                
                # Constants for rate limiting and concurrency control
                BATCH_SIZE = 5  # Number of symbols to process in parallel
                RATE_LIMIT_DELAY = 1.0  # Delay between batches in seconds
                MAX_RETRIES = 2  # Reduced from 3 to 2
                MAX_CONCURRENT_TASKS = 5  # Reduced from 10 to 5
                
                opportunities = []
                total_symbols = len(symbols)
                
                # Create a semaphore to limit concurrent tasks
                semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
                
                async def process_with_semaphore(symbol: str) -> Optional[TradingOpportunity]:
                    """Process a symbol with semaphore control."""
                    async with semaphore:
                        logger.debug(f"Processing symbol: {symbol}")
                        result = await self._process_symbol_with_retry(symbol, risk_per_trade, MAX_RETRIES)
                        if result:
                            logger.info(f"Found opportunity for {symbol}: {result.direction} at {result.entry_price}")
                        return result
                
                # Process symbols in batches
                for i in range(0, total_symbols, BATCH_SIZE):
                    batch_symbols = symbols[i:i + BATCH_SIZE]
                    logger.info(f"Processing batch {i//BATCH_SIZE + 1}/{(total_symbols + BATCH_SIZE - 1)//BATCH_SIZE}: {', '.join(batch_symbols)}")
                    
                    # Create tasks for the current batch with semaphore control
                    tasks = []
                    for symbol in batch_symbols:
                        task = asyncio.create_task(process_with_semaphore(symbol))
                        tasks.append(task)
                    
                    # Process batch concurrently with timeout
                    try:
                        batch_results = await asyncio.wait_for(
                            asyncio.gather(*tasks, return_exceptions=True),
                            timeout=30.0  # 30 second timeout per batch
                        )
                    except asyncio.TimeoutError:
                        logger.error(f"Batch processing timed out for symbols: {', '.join(batch_symbols)}")
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
                
                logger.info(f"Found {len(opportunities)} opportunities out of {total_symbols} symbols")
                if opportunities:
                    logger.info(f"Top opportunities: {', '.join([f'{opp.symbol}({opp.score:.2f})' for opp in opportunities[:3]])}")
                return opportunities
                
            except Exception as e:
                logger.error(f"Error scanning opportunities: {e}")
                return []
            
    def _validate_signal(self, signal: Dict) -> SignalValidationResult:
        """Validate a trading signal."""
        errors = []
        warnings = []

        # Required fields based on the signal structure from SignalGenerator
        # Expected fields are 'symbol', 'direction', 'entry', 'take_profit', 'stop_loss', 'confidence', 'indicators'
        required_fields = ['symbol', 'direction', 'entry', 'take_profit', 'stop_loss', 'confidence', 'indicators']
        
        # Check for presence of required fields
        for field in required_fields:
            if field not in signal:
                # Use a more informative error message if a level is missing
                if field in ['entry', 'take_profit', 'stop_loss']:
                    errors.append(f"Missing required trading level in signal: {field}")
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
                         errors.append(f"{level_field.replace('_', ' ').capitalize()} must be a positive number (got {value})")
                     else:
                         errors.append(f"{level_field.replace('_', ' ').capitalize()} must be a number (got {type(value).__name__})")

            # Validate confidence (using the key 'confidence')
            confidence_value = signal.get('confidence')
            if not isinstance(confidence_value, (int, float)) or not 0.0 <= confidence_value <= 1.0:
                # Add a specific message if the value is outside the 0-1 range
                if isinstance(confidence_value, (int, float)):
                    errors.append(f"Confidence must be a number between 0 and 1 (got {confidence_value})")
                else:
                    errors.append(f"Confidence must be a number (got {type(confidence_value).__name__})")

            if not isinstance(signal.get('indicators', {}), dict):
                errors.append("Indicators must be a dictionary")

            # Validate indicators (optional deep validation can be added here)
            # Example: Validate RSI if present
            rsi_value = signal['indicators'].get('rsi')
            if rsi_value is not None:
                if not isinstance(rsi_value, (int, float)) or not 0 <= rsi_value <= 100:
                    warnings.append(f"RSI value out of normal range (0-100) in indicators (got {rsi_value})")

            # Example: Validate MACD if present
            macd_value = signal['indicators'].get('macd')
            if macd_value is not None:
                 if not isinstance(macd_value, dict) or 'value' not in macd_value or 'signal' not in macd_value:
                     warnings.append("MACD indicator missing required fields or is not a dict in indicators")

            # Check for extreme values or inconsistencies (example: stop_loss on wrong side)
            entry = signal['entry']
            stop_loss = signal['stop_loss']
            take_profit = signal['take_profit']

            if signal['direction'] == 'LONG':
                if stop_loss >= entry:
                    errors.append("LONG trade stop loss must be strictly below entry price")
                # Using >= and <= for TP/SL relative to entry to catch potential issues
                if take_profit <= entry:
                     warnings.append("LONG trade take profit is not strictly above entry price")
                 # Check if stop_loss is too far from entry (more than entry itself, e.g., 100% loss potential in one step)
                if entry > 0 and abs(entry - stop_loss) / entry > 0.95: # 95% max distance as a heuristic
                    warnings.append(f"LONG trade stop loss is very far from entry price ({abs(entry - stop_loss) / entry:.2f}%) - potential data issue or wide range")

            elif signal['direction'] == 'SHORT':
                 if stop_loss <= entry:
                     errors.append("SHORT trade stop loss must be strictly above entry price")
                 if take_profit >= entry:
                      warnings.append("SHORT trade take profit is not strictly below entry price")
                 # Check if stop_loss is too far from entry
                 if entry > 0 and abs(entry - stop_loss) / entry > 0.95:
                     warnings.append(f"SHORT trade stop loss is very far from entry price ({abs(entry - stop_loss) / entry:.2f}%) - potential data issue or wide range")

            # Calculate risk_amount and reward_amount
            risk_amount = abs(entry - stop_loss)
            reward_amount = abs(take_profit - entry)

            # Validate risk_amount and reward_amount
            # Use a small epsilon for floating point comparison if exact zero is too strict
            if risk_amount <= 1e-9: # Effectively zero
                errors.append("Risk amount is zero or too small, leading to invalid risk-reward calculation.")
            if reward_amount <= 1e-9: # Effectively zero
                errors.append("Reward amount is zero or too small, leading to invalid risk-reward calculation.")

            # Check for extreme confidence value (already handled by type/range check, but can add specific warnings)
            if 0.9 <= confidence_value < 1.0:
                 warnings.append("High confidence value detected (>=0.9)")
            elif confidence_value == 1.0:
                 warnings.append("Maximum confidence value (1.0) detected - ensure this isn't a default or placeholder")

            # Check for very tight stop loss (potentially due to calculation error or illiquid symbol)
            if entry > 0:
                stop_loss_percentage = abs(entry - stop_loss) / entry
                # Lowering threshold for tight stop loss warning
                if 0 < stop_loss_percentage < 0.001: # e.g., less than 0.1% from entry
                    warnings.append(f"Very tight stop loss detected ({stop_loss_percentage:.4f}%) - may be prone to slippage or whipsaw")
                # The existing check for zero distance stop loss is still relevant
                # if stop_loss_percentage == 0:
                #      errors.append("Stop loss is at the entry price, resulting in zero risk distance.")

        except Exception as e:
            # Catch any unexpected errors during the validation process itself
            errors.append(f"Unexpected error during signal validation: {str(e)}")
            logger.error(f"Unexpected error during signal validation for {signal.get('symbol', 'UNKNOWN')}: {e}", exc_info=True)

        return SignalValidationResult(len(errors) == 0, errors, warnings)

    def _get_cached_signal(self, symbol: str) -> Optional[Dict]:
        """Get a cached signal if it exists and is still valid."""
        if symbol in self.signal_cache:
            cached = self.signal_cache[symbol]
            if datetime.now() < cached.expires_at:
                # Ensure cached signal has required keys for current validation logic
                # If not, treat as invalid cache
                required_keys = ['symbol', 'direction', 'entry', 'take_profit', 'stop_loss', 'confidence', 'indicators']
                if all(key in cached.signal for key in required_keys):
                    return cached.signal
                else:
                     logger.warning(f"Cached signal for {symbol} is missing required keys. Discarding cache.")
                     del self.signal_cache[symbol]
        return None
        
    def _cache_signal(self, symbol: str, signal: Dict):
        """Cache a signal with expiration."""
        # Ensure the signal being cached has the required structure
        required_keys = ['symbol', 'direction', 'entry', 'take_profit', 'stop_loss', 'confidence', 'indicators']
        if not all(key in signal for key in required_keys):
             logger.error(f"Attempted to cache a signal for {symbol} missing required keys. Not caching.")
             return # Do not cache incomplete signals

        expires_at = datetime.now() + timedelta(seconds=self.cache_duration)
        self.signal_cache[symbol] = CachedSignal(signal, datetime.now(), expires_at)

        # Also save to disk for persistence
        try:
            cache_file = self.cache_dir / f"{symbol}.json"
            # Ensure the signal structure is valid before writing to disk
            if not self._validate_signal(signal).is_valid:
                 logger.warning(f"Attempted to cache an invalid signal for {symbol} to disk. Skipping disk cache.")
                 # Optional: log the validation errors here if needed
            else:
                 with open(cache_file, 'w') as f:
                    json.dump({
                        'signal': signal,
                        'timestamp': datetime.now().isoformat(),
                        'expires_at': expires_at.isoformat()
                    }, f)
        except Exception as e:
            logger.error(f"Error saving signal to cache file for {symbol}: {e}")
            
    async def _process_symbol_with_retry(self, symbol: str, risk_per_trade: float, max_retries: int) -> Optional[TradingOpportunity]:
        """Process a single symbol with retry logic."""
        for attempt in range(max_retries):
            try:
                # Fetch fresh market data first to ensure up-to-date volume, volatility, etc.
                market_data = await self.get_market_data(symbol)
                if not market_data:
                    logger.debug(f"No fresh market data for {symbol} before processing signal.")
                    return None

                # Apply advanced filters BEFORE checking cache or generating signal
                if not self._apply_advanced_filters(market_data):
                    logger.debug(f"Symbol {symbol} rejected by advanced filters even with fresh data.")
                    return None

                # Calculate indicators from klines data
                indicators = self._calculate_indicators(market_data.get('klines', []))
                market_data['indicators'] = indicators

                # Now, check cache for a recent signal
                cached_signal = self._get_cached_signal(symbol)

                if cached_signal:
                    logger.debug(f"Using cached signal for {symbol}")
                    signal = cached_signal
                else:
                    # Calculate initial confidence score
                    initial_confidence = self._calculate_confidence_score(market_data, {})

                    # Generate signals using the signal generator
                    signal = self.signal_generator.generate_signals(
                        symbol,
                        market_data,
                        initial_confidence
                    )

                    if not signal:
                        logger.debug(f"No signal generated for {symbol} with fresh data.")
                        return None

                    # Validate the signal
                    validation = self._validate_signal(signal)
                    if not validation.is_valid:
                        logger.warning(f"Invalid signal for {symbol}: {validation.errors}")
                        return None

                    # Cache the signal
                    self._cache_signal(symbol, signal)

                # --- Extract and use the levels provided by the signal generator from the validated signal --- #
                # The signal is now expected to have 'entry', 'take_profit', 'stop_loss', 'confidence', 'direction', 'symbol', and 'indicators'
                try:
                    entry_price = float(signal['entry'])
                    take_profit = float(signal['take_profit'])
                    stop_loss = float(signal['stop_loss'])
                    confidence = float(signal['confidence'])
                    direction = signal['direction']
                    symbol_name = signal['symbol']
                    signal_indicators = signal.get('indicators', {}) # Use indicators from signal
                    reasoning = signal.get('reasoning', []) # Use reasoning from signal

                    # Use volume_24h and volatility from the fresh market_data (fetched earlier)
                    volume_24h = market_data.get('ticker_24h', {}).get('volume', 0.0)
                    volatility = self.calculate_volatility(market_data.get('klines', []))

                except KeyError as e:
                     logger.error(f"Signal dictionary for {symbol} is missing expected key during extraction: {e}. Signal: {signal}")
                     return None # Cannot proceed without essential keys
                except (ValueError, TypeError) as e:
                     logger.error(f"Signal dictionary for {symbol} contains invalid data types during extraction: {e}. Signal: {signal}")
                     return None # Cannot proceed with invalid data

                # Calculate risk-reward ratio based on the provided levels
                risk_amount = abs(entry_price - stop_loss)
                reward_amount = abs(take_profit - entry_price)

                # Avoid division by zero for risk_reward
                risk_reward = reward_amount / risk_amount if risk_amount > 0 else 0.0

                logger.debug(f"Calculated Risk-Reward for {symbol_name} using signal levels: {risk_reward}. Minimum required: {self.min_risk_reward}")

                # Discard if risk-reward is below minimum
                if risk_reward < self.min_risk_reward:
                    logger.info(f"Opportunity for {symbol_name} discarded due to low risk-reward ({risk_reward:.2f} < {self.min_risk_reward:.2f})")
                    return None

                # Calculate leverage for the opportunity object (display/scoring)
                # This is a simplified estimate based on stop loss percentage relative to entry and a hypothetical risk.
                # The actual leverage for a trade execution will be determined by the TradingBot based on position size and account equity.
                leverage = 1.0 # Default minimum leverage
                if entry_price > 0 and abs(entry_price - stop_loss) > 0: # Avoid division by zero
                    # Heuristic: Estimate leverage based on the stop loss percentage. A smaller stop loss allows higher leverage for the same risk amount.
                    # Assuming a small percentage risk of the entry price (e.g., 1%) to get an estimated max leverage for display.
                    stop_loss_percent = abs(entry_price - stop_loss) / entry_price
                    # Estimated max leverage for display: Inverse of stop loss percentage (as a fraction of entry price) * a risk factor (e.g., 0.01 for 1% risk)
                    # This is not a precise calculation for trade execution, just an indication for the opportunity object.
                    estimated_leverage = 1.0 / stop_loss_percent if stop_loss_percent > 0 else self.max_leverage # Inverse of stop loss percentage
                    # Example adjustment: Multiply by a factor representing desired risk % relative to potential 100% loss at SL
                    # This part is complex and depends heavily on overall risk strategy. Let's keep it simple for display.
                    leverage = max(1.0, min(estimated_leverage, self.max_leverage)) # Cap leverage and ensure minimum


                opportunity = TradingOpportunity(
                    symbol=symbol_name,
                    direction=direction,
                    entry_price=entry_price,
                    take_profit=take_profit,
                    stop_loss=stop_loss,
                    confidence=confidence,
                    leverage=leverage, # Use calculated leverage for opportunity object (display/scoring)
                    risk_reward=risk_reward,
                    volume_24h=volume_24h, # From fresh market data
                    volatility=volatility, # From fresh market data
                    score=0.0,  # Will be calculated below
                    indicators=signal_indicators, # Use indicators from the signal
                    reasoning=reasoning
                )

                # Calculate final score based on the complete opportunity object
                opportunity.score = self.calculate_opportunity_score(opportunity)

                # Check if the calculated score meets the minimum confidence requirement
                # Lower min_confidence to 0.3 for scalping
                if opportunity.confidence < 0.3:
                    logger.info(f"Opportunity for {symbol_name} discarded after scoring due to low confidence ({opportunity.confidence:.2f} < 0.3)")
                    return None

                return opportunity

            except Exception as e:
                # Catch exceptions during market data fetch, filtering, signal generation, validation, or opportunity creation
                if attempt < max_retries - 1:
                    logger.warning(f"Retry {attempt + 1}/{max_retries} processing {symbol}: {e}", exc_info=True)
                    await asyncio.sleep(1.0 * (attempt + 1))  # Exponential backoff
                else:
                    logger.error(f"Failed to process {symbol} after {max_retries} attempts: {e}", exc_info=True)
                    return None

        return None

    def _apply_advanced_filters(self, market_data: Dict) -> Tuple[bool, List[str]]:
        """Apply advanced filters to market data, returning reasons for exclusion."""
        symbol = market_data.get('symbol', 'UNKNOWN')
        reasons = []

        # Volume filter
        volume_24h = market_data.get('ticker_24h', {}).get('volume', 0)
        if volume_24h < self.min_volume_24h:
            reasons.append(f"Low volume: {volume_24h:.2f} < {self.min_volume_24h:.2f}")

        # Spread filter
        spread = self._calculate_spread(market_data.get('orderbook', {}))
        if spread > self.max_spread:
            reasons.append(f"Spread too high: {spread:.4f} > {self.max_spread:.4f}")

        # Enhanced liquidity filter with multiple depth ranges
        orderbook = market_data.get('orderbook', {})
        if orderbook:
            mid_price = (orderbook['asks'][0][0] + orderbook['bids'][0][0]) / 2
            volatility = self.calculate_volatility(market_data.get('klines', []))
            
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
                
                buy_depth = sum(qty for price, qty in orderbook['bids'] if range_min <= price <= mid_price)
                sell_depth = sum(qty for price, qty in orderbook['asks'] if mid_price <= price <= range_max)
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

        # Open interest filter and trend check with enhanced metrics
        open_interest = market_data.get('open_interest', 0)
        if open_interest < self.min_open_interest:
            reasons.append(f"Low open interest: {open_interest:.2f} < {self.min_open_interest:.2f}")
        
        # Enhanced OI trend analysis
        oi_data = market_data.get('open_interest_history', [])
        if len(oi_data) >= 10:
            recent_oi = oi_data[-10:]  # Last 10 minutes
            oi_trend = np.polyfit(range(len(recent_oi)), recent_oi, 1)[0]
            oi_change_pct = (recent_oi[-1] - recent_oi[0]) / recent_oi[0]
            
            # Calculate OI volatility
            oi_std = np.std(recent_oi)
            oi_mean = np.mean(recent_oi)
            oi_cv = oi_std / oi_mean if oi_mean > 0 else float('inf')
            
            # Log OI metrics
            logger.debug(
                f"OI metrics for {symbol}: "
                f"trend={oi_trend:.2f}, "
                f"change={oi_change_pct*100:.1f}%, "
                f"CV={oi_cv:.2f}"
            )
            
            if oi_trend < 0:
                if oi_change_pct < -0.05:  # More than 5% decline
                    reasons.append(
                        f"Severe OI decline: {oi_change_pct*100:.1f}% "
                        f"(volatility: {oi_cv:.2f})"
                    )
                    return False, reasons
                elif oi_cv > 0.1:  # High OI volatility
                    reasons.append(
                        f"Unstable OI: {oi_cv:.2f} CV "
                        f"(trend: {oi_change_pct*100:.1f}%)"
                    )
                    # Don't return False for high volatility, just log it

        # Market cap filter
        market_cap = self._calculate_market_cap(market_data.get('ticker_24h', {}))
        if market_cap < self.min_market_cap:
            reasons.append(f"Low market cap: {market_cap:.2f} < {self.min_market_cap:.2f}")

        # Volatility filter
        volatility = self.calculate_volatility(market_data.get('klines', []))
        if not (self.min_volatility <= volatility <= self.max_volatility):
            reasons.append(f"Volatility out of range: {volatility:.4f} ({self.min_volatility:.4f}-{self.max_volatility:.4f})")

        # Funding rate filter
        funding_rate = market_data.get('funding_rate', 0)
        if not (self.min_funding_rate <= funding_rate <= self.max_funding_rate):
            reasons.append(f"Funding rate out of range: {funding_rate:.6f} ({self.min_funding_rate:.6f}-{self.max_funding_rate:.6f})")

        # Volume trend check over past 10 minutes
        volume_data = market_data.get('volume_history', [])
        if len(volume_data) >= 10:
            recent_volume = volume_data[-10:]
            volume_trend = np.polyfit(range(len(recent_volume)), recent_volume, 1)[0]
            
            if volume_trend < 0:
                # Calculate volume trend severity
                volume_change_pct = (recent_volume[-1] - recent_volume[0]) / recent_volume[0]
                if volume_change_pct < -0.1:  # More than 10% decline
                    reasons.append(f"Severe volume decline: {volume_change_pct*100:.1f}%")
                    # Don't return False for severe decline, just log it

        # Price stability filter
        if not self._check_price_stability(market_data.get('klines', [])):
            reasons.append("Price instability")

        # Volume trend filter
        if not self._check_volume_trend(market_data.get('klines', [])):
            reasons.append("Unhealthy volume trend")

        # Estimate slippage for a simulated market order
        if orderbook:
            simulated_order_size = 0.1  # 0.1 BTC or equivalent
            slippage = self._estimate_slippage(orderbook, simulated_order_size)
            if slippage > 0.002:  # 0.2% max slippage
                reasons.append(f"High slippage: {slippage*100:.3f}%")

        if reasons:
            logger.debug(f"Symbol {symbol} excluded by advanced filters: {'; '.join(reasons)}")
            logger.info(f"Excluded {symbol}: {'; '.join(reasons)}")
            return False, reasons

        return True, []

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
        """Check if volume trend is healthy, with relaxed criteria for confirmed signals."""
        try:
            volumes = [float(candle['volume']) for candle in ohlcv]
            
            # Need at least 20 data points for the MA and STD calculations
            if len(volumes) < 20:
                logger.debug("Insufficient data points for volume trend analysis")
                return True  # Allow through if not enough data

            # Calculate volume metrics
            vol_ma5 = np.mean(volumes[-5:])
            vol_ma20 = np.mean(volumes[-20:])
            vol_std = np.std(volumes[-20:])
            vol_mean = np.mean(volumes[-20:])
            
            # Check for volume consistency
            vol_cv = vol_std / vol_mean if vol_mean > 0 else float('inf')
            
            # Additional safeguards
            # 1. Check for sudden volume spikes
            recent_vol_std = np.std(volumes[-5:])
            if recent_vol_std > vol_mean * 2.0:
                logger.warning(f"Sudden volume spike detected: {recent_vol_std/vol_mean:.2f}x average")
                return False

            # 2. Check for volume trend consistency
            vol_trend = np.polyfit(range(len(volumes[-20:])), volumes[-20:], 1)[0]
            if abs(vol_trend) > vol_mean * 0.5:
                logger.warning(f"Extreme volume trend detected: {vol_trend/vol_mean:.2f}x average")
                return False
                
            # 3. Check for volume gaps
            vol_diffs = np.diff(volumes[-5:])
            if np.max(np.abs(vol_diffs)) > vol_mean * 3.0:
                logger.warning(f"Large volume gap detected: {np.max(np.abs(vol_diffs))/vol_mean:.2f}x average")
                return False
            
            if signal_direction:
                # For confirmed signals, only check for extreme volume drops
                if vol_ma5 < vol_ma20 * 0.1:  # Allow up to 90% volume drop
                    logger.warning(f"Extreme volume drop detected: {vol_ma5/vol_ma20:.2%} of average")
                    return False
                
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
        logger.info("Initializing symbol discovery...")
        await self._load_symbols()
        logger.info(f"Symbol discovery initialized with {len(self.symbols)} symbols")

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