from typing import Dict, List, Optional, Set
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

class SymbolDiscovery:
    def __init__(self, exchange_client: ExchangeClient):
        self.exchange_client = exchange_client
        self.signal_generator = SignalGenerator()
        self.opportunities: Dict[str, TradingOpportunity] = {}
        self.last_update = datetime.now()
        self.update_interval = int(os.getenv('SYMBOL_UPDATE_INTERVAL', '3600'))  # Default 1 hour
        self._update_task = None
        
        # Load configuration from environment
        self.min_volume_24h = float(os.getenv('MIN_24H_VOLUME', '1000000'))
        self.min_confidence = float(os.getenv('MIN_CONFIDENCE', '0.7'))
        self.min_risk_reward = float(os.getenv('MIN_RISK_REWARD', '2.0'))
        self.max_leverage = float(os.getenv('MAX_LEVERAGE', '20.0'))
        
        # Advanced filtering parameters
        self.min_market_cap = float(os.getenv('MIN_MARKET_CAP', '100000000'))
        self.max_spread = float(os.getenv('MAX_SPREAD', '0.002'))
        self.min_liquidity = float(os.getenv('MIN_LIQUIDITY', '500000'))
        self.max_correlation = float(os.getenv('MAX_CORRELATION', '0.7'))
        self.min_volatility = float(os.getenv('MIN_VOLATILITY', '0.01'))
        self.max_volatility = float(os.getenv('MAX_VOLATILITY', '0.05'))
        self.min_funding_rate = float(os.getenv('MIN_FUNDING_RATE', '-0.0001'))
        self.max_funding_rate = float(os.getenv('MAX_FUNDING_RATE', '0.0001'))
        self.min_open_interest = float(os.getenv('MIN_OPEN_INTEREST', '1000000'))
        self.max_symbols = int(os.getenv('MAX_SYMBOLS', '50'))
        
        # Cache configuration
        self.cache_dir = Path('cache/signals')
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.signal_cache: Dict[str, CachedSignal] = {}
        self.cache_duration = int(os.getenv('SIGNAL_CACHE_DURATION', '300'))  # 5 minutes default
        
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
                self.last_update = datetime.now()
                logger.info(f"Symbol list updated at {self.last_update}")
                await asyncio.sleep(self.update_interval)
            except Exception as e:
                logger.error(f"Error in symbol update loop: {e}")
                await asyncio.sleep(60)  # Wait a minute before retrying
                
    async def discover_symbols(self) -> List[str]:
        """Fetch available futures trading pairs based on configuration mode."""
        try:
            discovery_mode = os.getenv('SYMBOL_DISCOVERY_MODE', 'static')
            
            if discovery_mode == 'static':
                # Use symbols from configuration
                symbols = os.getenv('TRADING_SYMBOLS', 'BTCUSDT').split(',')
                logger.info(f"Using {len(symbols)} static symbols from configuration")
                return symbols
            else:
                # Dynamic discovery from exchange
                exchange_info = await self.exchange_client.get_exchange_info()
                futures_symbols = [
                    symbol['symbol'] for symbol in exchange_info['symbols']
                    if symbol['status'] == 'TRADING' and symbol['contractType'] == 'PERPETUAL'
                ]
                
                logger.debug(f"Initial perpetual trading symbols found: {len(futures_symbols)}")
                
                # Apply filters
                filtered_symbols = []
                for symbol in futures_symbols:
                    logger.debug(f"Processing symbol for advanced filtering: {symbol}")
                    market_data = await self.get_market_data(symbol)
                    if market_data:
                        logger.debug(f"Market data fetched for {symbol}.")
                        if self._apply_advanced_filters(market_data):
                            logger.debug(f"Symbol {symbol} passed advanced filters.")
                            filtered_symbols.append(symbol)
                        else:
                            logger.debug(f"Symbol {symbol} failed advanced filters.")
                    else:
                        logger.debug(f"Failed to fetch market data for {symbol}.")
                
                # Limit number of symbols if configured
                if len(filtered_symbols) > self.max_symbols:
                    filtered_symbols = filtered_symbols[:self.max_symbols]
                    
                logger.info(f"Discovered {len(filtered_symbols)} trading pairs after filtering")
                return filtered_symbols
                
        except Exception as e:
            logger.error(f"Error discovering symbols: {e}")
            # Fallback to static symbols on error
            symbols = os.getenv('TRADING_SYMBOLS', 'BTCUSDT').split(',')
            logger.warning(f"Falling back to {len(symbols)} static symbols due to error")
            return symbols

    async def get_market_data(self, symbol: str) -> Optional[Dict]:
        """Fetch comprehensive market data for a symbol."""
        try:
            # Get OHLCV data
            ohlcv = await self.exchange_client.get_historical_data(
                symbol, interval="1m", limit=200
            )
            
            # Get funding rate
            funding_rate = await self.exchange_client.get_funding_rate(symbol)
            
            # Get 24h statistics
            ticker_24h = await self.exchange_client.get_ticker_24h(symbol)
            
            # Get order book
            orderbook = await self.exchange_client.get_orderbook(symbol, limit=10)
            
            # Calculate spread from orderbook
            spread = self._calculate_spread(orderbook)
            
            # Calculate liquidity from orderbook
            liquidity = self._calculate_liquidity(orderbook)
            
            # Calculate market cap (approximate)
            market_cap = self._calculate_market_cap(ticker_24h)
            
            # Calculate open interest
            open_interest = await self.exchange_client.get_open_interest(symbol)
            
            # Calculate volatility
            volatility = self.calculate_volatility(ohlcv)
            
            # Calculate price stability
            price_stability = self._check_price_stability(ohlcv)
            
            # Calculate volume trend
            volume_trend = self._check_volume_trend(ohlcv)
            
            # Calculate technical indicators
            indicators = self._calculate_indicators(ohlcv)
            
            return {
                'symbol': symbol,
                'ohlcv': ohlcv,
                'funding_rate': funding_rate,
                'volume_24h': float(ticker_24h['volume']),
                'price_change_24h': float(ticker_24h['priceChangePercent']),
                'orderbook': orderbook,
                'spread': spread,
                'liquidity': liquidity,
                'market_cap': market_cap,
                'open_interest': open_interest,
                'volatility': volatility,
                'price_stability': price_stability,
                'volume_trend': volume_trend,
                'last_price': float(ticker_24h['lastPrice']),
                'high_24h': float(ticker_24h['highPrice']),
                'low_24h': float(ticker_24h['lowPrice']),
                'quote_volume': float(ticker_24h['quoteVolume']),
                'indicators': indicators
            }
        except Exception as e:
            logger.error(f"Error fetching market data for {symbol}: {e}")
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
            volume_score = min(opportunity.volume_24h / self.min_volume_24h, 2.0)
            score += volume_score * 0.15
            
            # Risk-reward factor (15%)
            rr_score = min(opportunity.risk_reward / self.min_risk_reward, 3.0)
            score += rr_score * 0.15
            
            # Volatility factor (10%)
            vol_score = 1.0 - abs(opportunity.volatility - 0.03) / 0.03  # Target 3% volatility
            score += vol_score * 0.1
            
            # Leverage factor (5%)
            lev_score = 1.0 - (opportunity.leverage / self.max_leverage)
            score += lev_score * 0.05
            
            # Technical indicators (25%)
            tech_score = self._calculate_technical_score(opportunity.indicators)
            score += tech_score * 0.25
            
            return min(score, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating opportunity score: {e}")
            return 0.0
            
    def _calculate_technical_score(self, indicators: Dict) -> float:
        """Calculate score based on technical indicators."""
        try:
            score = 0.0
            weights = {
                'trend': 0.25,      # Reduced from 0.3 to accommodate new indicators
                'momentum': 0.20,   # Reduced from 0.25
                'volatility': 0.15, # Reduced from 0.2
                'volume': 0.10,     # Reduced from 0.15
                'support_resistance': 0.10,
                'trend_strength': 0.10,  # New weight for ADX
                'oscillators': 0.10      # New weight for CCI and other oscillators
            }
            
            # Trend indicators
            if 'macd' in indicators:
                macd = indicators['macd']
                if macd['value'] > macd['signal'] and macd['histogram'] > 0:
                    score += weights['trend'] * 1.0
                elif macd['value'] < macd['signal'] and macd['histogram'] < 0:
                    score += weights['trend'] * 1.0
                    
            if 'ema' in indicators:
                ema = indicators['ema']
                if ema['fast'] > ema['slow']:
                    score += weights['trend'] * 0.5
                    
            # Ichimoku Cloud
            if 'ichimoku' in indicators:
                ichimoku = indicators['ichimoku']
                price = ichimoku['price']
                tenkan = ichimoku['tenkan']
                kijun = ichimoku['kijun']
                senkou_a = ichimoku['senkou_a']
                senkou_b = ichimoku['senkou_b']
                
                # Strong bullish signal
                if (price > tenkan > kijun and 
                    price > senkou_a > senkou_b):
                    score += weights['trend'] * 1.0
                # Strong bearish signal
                elif (price < tenkan < kijun and 
                      price < senkou_a < senkou_b):
                    score += weights['trend'] * 1.0
                # Moderate signal
                elif (price > tenkan and price > kijun) or (price < tenkan and price < kijun):
                    score += weights['trend'] * 0.5
                    
            # Momentum indicators
            if 'rsi' in indicators:
                rsi = indicators['rsi']
                if rsi < 30 or rsi > 70:  # Oversold or overbought
                    score += weights['momentum'] * 1.0
                elif 40 <= rsi <= 60:  # Neutral
                    score += weights['momentum'] * 0.5
                    
            if 'stoch' in indicators:
                stoch = indicators['stoch']
                if stoch['k'] < 20 or stoch['k'] > 80:
                    score += weights['momentum'] * 0.5
                    
            # CCI (Commodity Channel Index)
            if 'cci' in indicators:
                cci = indicators['cci']
                if cci > 100:  # Overbought
                    score += weights['oscillators'] * 1.0
                elif cci < -100:  # Oversold
                    score += weights['oscillators'] * 1.0
                elif abs(cci) < 50:  # Neutral
                    score += weights['oscillators'] * 0.3
                    
            # ADX (Average Directional Index)
            if 'adx' in indicators:
                adx = indicators['adx']
                di_plus = indicators.get('di_plus', 0)
                di_minus = indicators.get('di_minus', 0)
                
                # Strong trend
                if adx > 25:
                    score += weights['trend_strength'] * 1.0
                    # Direction confirmation
                    if di_plus > di_minus:
                        score += weights['trend'] * 0.5
                    elif di_minus > di_plus:
                        score += weights['trend'] * 0.5
                # Moderate trend
                elif adx > 20:
                    score += weights['trend_strength'] * 0.5
                    
            # Volatility indicators
            if 'bb' in indicators:
                bb = indicators['bb']
                bb_width = (bb['upper'] - bb['lower']) / bb['middle']
                if bb_width < 0.02:  # Tight bands
                    score += weights['volatility'] * 1.0
                elif bb_width < 0.05:  # Moderate bands
                    score += weights['volatility'] * 0.5
                    
            if 'atr' in indicators:
                atr = indicators['atr']
                if 0.01 <= atr <= 0.03:  # Ideal volatility range
                    score += weights['volatility'] * 1.0
                    
            # Volume indicators
            if 'obv' in indicators:
                obv = indicators['obv']
                if obv['trend'] == 'up':
                    score += weights['volume'] * 1.0
                    
            if 'vwap' in indicators:
                vwap = indicators['vwap']
                if vwap['price'] > vwap['value']:
                    score += weights['volume'] * 0.5
                    
            # Support/Resistance
            if 'sr' in indicators:
                sr = indicators['sr']
                if sr['price'] > sr['support'] and sr['price'] < sr['resistance']:
                    score += weights['support_resistance'] * 1.0
                    
            return min(score, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating technical score: {e}")
            return 0.0
            
    async def scan_opportunities(self, risk_per_trade: float = 50.0) -> List[TradingOpportunity]:
        """Scan all symbols for trading opportunities with rate limiting and batch processing."""
        try:
            # Get all available symbols
            symbols = await self.discover_symbols()
            
            # Constants for rate limiting and concurrency control
            BATCH_SIZE = 5  # Number of symbols to process in parallel
            RATE_LIMIT_DELAY = 1.0  # Delay between batches in seconds
            MAX_RETRIES = 3  # Maximum number of retries for failed requests
            MAX_CONCURRENT_TASKS = 10  # Maximum number of concurrent tasks
            
            opportunities = []
            total_symbols = len(symbols)
            
            # Create a semaphore to limit concurrent tasks
            semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
            
            async def process_with_semaphore(symbol: str) -> Optional[TradingOpportunity]:
                """Process a symbol with semaphore control."""
                async with semaphore:
                    return await self._process_symbol_with_retry(symbol, risk_per_trade, MAX_RETRIES)
            
            # Process symbols in batches
            for i in range(0, total_symbols, BATCH_SIZE):
                batch_symbols = symbols[i:i + BATCH_SIZE]
                logger.info(f"Processing batch {i//BATCH_SIZE + 1}/{(total_symbols + BATCH_SIZE - 1)//BATCH_SIZE}")
                
                # Create tasks for the current batch with semaphore control
                tasks = []
                for symbol in batch_symbols:
                    task = asyncio.create_task(process_with_semaphore(symbol))
                    tasks.append(task)
                
                # Process batch concurrently
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                
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
                    
                    # Check if we need to pause for rate limiting
                    if len(opportunities) > 0 and len(opportunities) % 50 == 0:
                        logger.info("Rate limit pause: waiting 5 seconds...")
                        await asyncio.sleep(5)  # Additional pause every 50 opportunities
            
            # Sort opportunities by score
            opportunities.sort(key=lambda x: x.score, reverse=True)
            
            # Update opportunities dictionary
            self.opportunities = {opp.symbol: opp for opp in opportunities}
            
            logger.info(f"Found {len(opportunities)} opportunities out of {total_symbols} symbols")
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
                # Check for zero distance stop loss which indicates an error in strategy calculation
                if stop_loss_percentage == 0:
                     errors.append("Stop loss is at the entry price, resulting in zero risk distance.")

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

                # Now, check cache for a recent signal
                cached_signal = self._get_cached_signal(symbol)

                if cached_signal:
                    logger.debug(f"Using cached signal for {symbol}")
                    signal = cached_signal
                else:
                    # Generate signal using the fresh market_data and indicators
                    indicators = market_data.get('indicators', {})
                    # The signal_generator is expected to return a confidence score based on its logic.
                    # We pass a placeholder/default if not available from market data, but the generator should override it.
                    initial_confidence = market_data.get('confidence', 0.5) # Use confidence from market data or default

                    signal = self.signal_generator.generate_signals(
                        symbol,
                        indicators,
                        initial_confidence # Pass initial confidence
                    )

                    if not signal:
                        logger.debug(f"No signal generated for {symbol} with fresh data.")
                        return None

                    # Validate the newly generated signal structure and basic values
                    validation = self._validate_signal(signal)
                    if not validation.is_valid:
                        for error in validation.errors:
                             logger.error(f"Newly generated signal validation failed for {symbol}: {error}. Signal: {signal}")
                        return None

                    if validation.warnings:
                        for warning in validation.warnings:
                            logger.warning(f"Newly generated signal validation warning for {symbol}: {warning}")

                    # Cache valid signal (will only cache if validation passed and required keys are present)
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
                    volume_24h = market_data.get('volume_24h', 0.0)
                    volatility = market_data.get('volatility', 0.0)
                     # Recalculate volatility from fresh market data ohlcv if necessary (safety check)
                    if volatility == 0.0 and 'ohlcv' in market_data and market_data['ohlcv']:
                         volatility = self.calculate_volatility(market_data['ohlcv'])

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
                    logger.debug(f"Opportunity for {symbol_name} discarded due to low risk-reward ({risk_reward} < {self.min_risk_reward})")
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
                # This is a redundancy if min_confidence filter is applied earlier, but good for clarity
                if opportunity.confidence < self.min_confidence:
                     logger.debug(f"Opportunity for {symbol_name} discarded after scoring due to low confidence ({opportunity.confidence} < {self.min_confidence})")
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

    def _apply_advanced_filters(self, market_data: Dict) -> bool:
        """Apply advanced filters to market data."""
        try:
            symbol = market_data.get('symbol', 'UNKNOWN')
            reasons = []

            # Volume filter
            if market_data['volume_24h'] < self.min_volume_24h:
                reasons.append(f"Low volume: {market_data['volume_24h']} < {self.min_volume_24h}")

            # Spread filter
            spread = market_data.get('spread', float('inf')) # Use a high default if missing
            if spread > self.max_spread:
                reasons.append(f"Spread too high: {spread} > {self.max_spread}")

            # Liquidity filter
            liquidity = market_data.get('liquidity', 0) # Use 0 default if missing
            if liquidity < self.min_liquidity:
                reasons.append(f"Low liquidity: {liquidity} < {self.min_liquidity}")

            # Market cap filter
            market_cap = market_data.get('market_cap', 0) # Use 0 default if missing
            if market_cap < self.min_market_cap:
                reasons.append(f"Low market cap: {market_cap} < {self.min_market_cap}")

            # Volatility filter
            # Note: calculate_volatility handles potential errors internally and returns 0 on failure
            volatility = self.calculate_volatility(market_data['ohlcv'])
            if not (self.min_volatility <= volatility <= self.max_volatility):
                reasons.append(f"Volatility out of range: {volatility} ({self.min_volatility}-{self.max_volatility})")

            # Funding rate filter
            funding_rate = market_data.get('funding_rate', 0) # Use 0 default if missing
            if not (self.min_funding_rate <= funding_rate <= self.max_funding_rate):
                reasons.append(f"Funding rate out of range: {funding_rate} ({self.min_funding_rate}-{self.max_funding_rate})")

            # Open interest filter
            open_interest = market_data.get('open_interest', 0) # Use 0 default if missing
            if open_interest < self.min_open_interest:
                reasons.append(f"Low open interest: {open_interest} < {self.min_open_interest}")

            # Price stability filter
            # Note: _check_price_stability handles potential errors internally and returns False on failure
            if not self._check_price_stability(market_data['ohlcv']):
                reasons.append("Price instability")

            # Volume trend filter
            # Note: _check_volume_trend handles potential errors internally and returns False on failure
            if not self._check_volume_trend(market_data['ohlcv']):
                reasons.append("Unhealthy volume trend")

            if reasons:
                logger.debug(f"Excluded {symbol}: {'; '.join(reasons)}")
                return False

            return True

        except Exception as e:
            logger.error(f"Error applying advanced filters for {symbol}: {e}")
            # If an error occurs during filtering a symbol, we should probably exclude it
            logger.debug(f"Excluded {symbol} due to error during filtering.")
            return False
            
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
            
    def _check_volume_trend(self, ohlcv: List[Dict]) -> bool:
        """Check if volume trend is healthy."""
        try:
            volumes = [float(candle['volume']) for candle in ohlcv]
            
            # Need at least 20 data points for the MA and STD calculations
            if len(volumes) < 20:
                # If insufficient data, assume healthy for now or return False based on desired behavior
                # Returning True to allow symbols through if not enough data to strictly fail
                return True # Or False, depending on desired strictness with limited data

            # Calculate volume moving averages
            vol_ma5 = np.mean(volumes[-5:])
            vol_ma20 = np.mean(volumes[-20:])
            
            # Volume should be increasing or stable
            # Relaxing the threshold from 0.8 to 0.5
            if vol_ma5 < vol_ma20 * 0.5:  # Allow recent volume to be as low as 50% of the 20-period average
                return False
                
            # Check for volume consistency (lower coefficient of variation indicates more consistent volume)
            # Relaxing the threshold from 0.5 to 1.0
            vol_std = np.std(volumes[-20:])
            vol_mean = np.mean(volumes[-20:])
            if vol_mean > 0 and (vol_std / vol_mean) > 1.0:  # Allow higher coefficient of variation (more inconsistency)
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error checking volume trend: {e}")
            return False

    def get_top_opportunities(self, count: int = 5) -> List[TradingOpportunity]:
        """Get the top N trading opportunities."""
        opportunities = list(self.opportunities.values())
        opportunities.sort(key=lambda x: x.score, reverse=True)
        return opportunities[:count]

    async def update_opportunities(self, risk_per_trade: float = 50.0):
        """Update opportunities periodically."""
        while True:
            try:
                await self.scan_opportunities(risk_per_trade)
                await asyncio.sleep(60)  # Update every minute
            except Exception as e:
                logger.error(f"Error updating opportunities: {e}")
                await asyncio.sleep(5)  # Wait before retrying 

    def _calculate_indicators(self, ohlcv: List[Dict]) -> Dict:
        """Calculate technical indicators from OHLCV data."""
        try:
            # Extract price and volume data
            closes = np.array([float(candle['close']) for candle in ohlcv])
            highs = np.array([float(candle['high']) for candle in ohlcv])
            lows = np.array([float(candle['low']) for candle in ohlcv])
            volumes = np.array([float(candle['volume']) for candle in ohlcv])
            
            # Calculate MACD
            ema12 = self._calculate_ema(closes, 12)
            ema26 = self._calculate_ema(closes, 26)
            macd_line = ema12 - ema26
            signal_line = self._calculate_ema(macd_line, 9)
            macd_histogram = macd_line - signal_line
            
            # Calculate RSI
            rsi = self._calculate_rsi(closes)
            
            # Calculate Bollinger Bands
            bb_middle = self._calculate_sma(closes, 20)
            bb_std = np.std(closes[-20:])
            bb_upper = bb_middle + (2 * bb_std)
            bb_lower = bb_middle - (2 * bb_std)
            
            # Calculate Stochastic Oscillator
            stoch_k = self._calculate_stochastic(highs, lows, closes)
            stoch_d = self._calculate_sma(stoch_k, 3)
            
            # Calculate ATR
            atr = self._calculate_atr(highs, lows, closes)
            
            # Calculate OBV (On-Balance Volume)
            obv = self._calculate_obv(closes, volumes)
            
            # Calculate VWAP
            vwap = self._calculate_vwap(ohlcv)
            
            # Calculate ADX
            adx, di_plus, di_minus = self._calculate_adx(highs, lows, closes)
            
            # Calculate CCI
            cci = self._calculate_cci(highs, lows, closes)
            
            return {
                'macd': {
                    'value': float(macd_line[-1]),
                    'signal': float(signal_line[-1]),
                    'histogram': float(macd_histogram[-1])
                },
                'rsi': float(rsi[-1]),
                'bollinger_bands': {
                    'upper': float(bb_upper[-1]),
                    'middle': float(bb_middle[-1]),
                    'lower': float(bb_lower[-1])
                },
                'stochastic': {
                    'k': float(stoch_k[-1]),
                    'd': float(stoch_d[-1])
                },
                'atr': float(atr[-1]),
                'obv': {
                    'value': float(obv[-1]),
                    'trend': 'up' if obv[-1] > obv[-2] else 'down'
                },
                'vwap': {
                    'value': float(vwap[-1]),
                    'price': float(closes[-1])
                },
                'adx': float(adx[-1]),
                'di_plus': float(di_plus[-1]),
                'di_minus': float(di_minus[-1]),
                'cci': float(cci[-1]),
                'volatility': float(np.std(closes[-20:]) / np.mean(closes[-20:]))
            }
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return {}
            
    def _calculate_ema(self, data: np.ndarray, period: int) -> np.ndarray:
        """Calculate Exponential Moving Average."""
        return np.array(pd.Series(data).ewm(span=period, adjust=False).mean())
        
    def _calculate_sma(self, data: np.ndarray, period: int) -> np.ndarray:
        """Calculate Simple Moving Average."""
        return np.array(pd.Series(data).rolling(window=period).mean())
        
    def _calculate_rsi(self, data: np.ndarray, period: int = 14) -> np.ndarray:
        """Calculate Relative Strength Index."""
        delta = np.diff(data)
        gain = (delta > 0) * delta
        loss = (delta < 0) * -delta
        
        avg_gain = self._calculate_sma(gain, period)
        avg_loss = self._calculate_sma(loss, period)
        
        rs = np.zeros_like(avg_gain) # Initialize rs array
        
        # Handle division by zero for avg_loss
        # If avg_loss is 0, RSI is 100 (if avg_gain > 0) or undefined (if avg_gain is also 0).
        # If avg_gain is 0 and avg_loss is not 0, RSI is 0.

        # Use np.errstate to suppress warnings for division by zero temporarily
        with np.errstate(divide='ignore', invalid='ignore'):
            # Where avg_loss is 0:
            #   If avg_gain is > 0, rs is inf (RSI=100)
            #   If avg_gain is 0, rs is nan (RSI=50 traditionally, or undefined)
            rs = np.where(avg_loss == 0, 
                          np.where(avg_gain == 0, np.nan, np.inf), 
                          avg_gain / avg_loss)
        
        rsi = 100 - (100 / (1 + rs))
        
        # Handle cases where rs is inf (RSI should be 100)
        rsi = np.where(rs == np.inf, 100.0, rsi)
        
        return np.concatenate(([np.nan] * (period + 1), rsi[period:])) # Adjust length for initial NaNs
        
    def _calculate_stochastic(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> np.ndarray:
        """Calculate Stochastic Oscillator."""
        lowest_low = self._calculate_sma(lows, period)
        highest_high = self._calculate_sma(highs, period)
        
        # Avoid division by zero when highest_high - lowest_low is zero
        denominator = highest_high - lowest_low
        k = np.where(denominator == 0, np.nan, 100 * ((closes - lowest_low) / denominator))
        return k
        
    def _calculate_atr(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> np.ndarray:
        """Calculate Average True Range."""
        tr1 = np.abs(highs[1:] - lows[1:])
        tr2 = np.abs(highs[1:] - closes[:-1])
        tr3 = np.abs(lows[1:] - closes[:-1])
        
        tr = np.maximum(np.maximum(tr1, tr2), tr3)
        atr = self._calculate_sma(tr, period)
        return np.concatenate(([np.nan], atr)) # Add nan for the first period
        
    def _calculate_obv(self, closes: np.ndarray, volumes: np.ndarray) -> np.ndarray:
        """Calculate On-Balance Volume."""
        obv = np.zeros_like(closes, dtype=float) # Ensure float type
        if len(closes) > 0:
            obv[0] = volumes[0]
            
            for i in range(1, len(closes)):
                if closes[i] > closes[i-1]:
                    obv[i] = obv[i-1] + volumes[i]
                elif closes[i] < closes[i-1]:
                    obv[i] = obv[i-1] - volumes[i]
                else:
                    obv[i] = obv[i-1]
                
        return obv
        
    def _calculate_vwap(self, ohlcv: List[Dict]) -> np.ndarray:
        """Calculate Volume Weighted Average Price."""
        typical_prices = np.array([
            (float(candle['high']) + float(candle['low']) + float(candle['close'])) / 3
            for candle in ohlcv
        ])
        volumes = np.array([float(candle['volume']) for candle in ohlcv])
        
        cumulative_volumes = np.cumsum(volumes)
        
        # Handle division by zero for cumulative_volumes
        vwap = np.where(cumulative_volumes == 0, np.nan, np.cumsum(typical_prices * volumes) / cumulative_volumes)
        return vwap
        
    def _calculate_adx(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Calculate Average Directional Index."""
        # Calculate True Range
        tr1 = np.abs(highs[1:] - lows[1:])
        tr2 = np.abs(highs[1:] - closes[:-1])
        tr3 = np.abs(lows[1:] - closes[:-1])
        
        tr = np.maximum(np.maximum(tr1, tr2), tr3)
        tr_smoothed = self._calculate_sma(tr, period)
        
        # Calculate Directional Movement
        up_move = highs[1:] - highs[:-1]
        down_move = lows[:-1] - lows[1:]
        
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
        
        plus_di = np.where(tr_smoothed == 0, np.nan, 100 * self._calculate_sma(plus_dm, period) / tr_smoothed)
        minus_di = np.where(tr_smoothed == 0, np.nan, 100 * self._calculate_sma(minus_dm, period) / tr_smoothed)
        
        # Calculate ADX
        # Avoid division by zero for plus_di + minus_di
        di_sum = plus_di + minus_di
        dx = np.where(di_sum == 0, np.nan, 100 * np.abs(plus_di - minus_di) / di_sum)
        adx = self._calculate_sma(dx, period)
        
        return adx, plus_di, minus_di
        
    def _calculate_cci(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 20) -> np.ndarray:
        """Calculate Commodity Channel Index."""
        typical_price = (highs + lows + closes) / 3
        sma = self._calculate_sma(typical_price, period)
        mean_deviation = np.abs(typical_price - sma)
        mean_deviation_sma = self._calculate_sma(mean_deviation, period)
        
        # Avoid division by zero for mean_deviation_sma
        cci = np.where(mean_deviation_sma == 0, np.nan, (typical_price - sma) / (0.015 * mean_deviation_sma))
        return cci 