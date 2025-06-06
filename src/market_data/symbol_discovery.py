from typing import Dict, List, Optional, Set
import asyncio
import logging
from datetime import datetime, timedelta
import numpy as np
from dataclasses import dataclass
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
    indicators: Dict
    reasoning: List[str]

@dataclass
class SignalValidationResult:
    is_valid: bool
    errors: List[str]
    warnings: List[str]

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
                
                # Apply filters
                filtered_symbols = []
                for symbol in futures_symbols:
                    market_data = await self.get_market_data(symbol)
                    if market_data and self._apply_advanced_filters(market_data):
                        filtered_symbols.append(symbol)
                        
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
        
        # Required fields
        required_fields = ['symbol', 'direction', 'price', 'confidence', 'indicators']
        for field in required_fields:
            if field not in signal:
                errors.append(f"Missing required field: {field}")
                
        if errors:
            return SignalValidationResult(False, errors, warnings)
            
        # Validate field types and values
        try:
            if not isinstance(signal['symbol'], str):
                errors.append("Symbol must be a string")
                
            if signal['direction'] not in ['LONG', 'SHORT']:
                errors.append("Direction must be 'LONG' or 'SHORT'")
                
            if not isinstance(signal['price'], (int, float)) or signal['price'] <= 0:
                errors.append("Price must be a positive number")
                
            if not isinstance(signal['confidence'], (int, float)) or not 0 <= signal['confidence'] <= 1:
                errors.append("Confidence must be a number between 0 and 1")
                
            if not isinstance(signal['indicators'], dict):
                errors.append("Indicators must be a dictionary")
                
            # Validate indicators
            if 'rsi' in signal['indicators']:
                rsi = signal['indicators']['rsi']
                if not isinstance(rsi, (int, float)) or not 0 <= rsi <= 100:
                    warnings.append("RSI value out of normal range (0-100)")
                    
            if 'macd' in signal['indicators']:
                macd = signal['indicators']['macd']
                if not isinstance(macd, dict) or 'value' not in macd or 'signal' not in macd:
                    warnings.append("MACD indicator missing required fields")
                    
            # Check for extreme values
            if signal['confidence'] > 0.9:
                warnings.append("Unusually high confidence value")
                
            if 'volatility' in signal['indicators']:
                vol = signal['indicators']['volatility']
                if vol > 0.1:  # 10% volatility
                    warnings.append("High volatility detected")
                    
        except Exception as e:
            errors.append(f"Error validating signal: {str(e)}")
            
        return SignalValidationResult(len(errors) == 0, errors, warnings)
        
    def _get_cached_signal(self, symbol: str) -> Optional[Dict]:
        """Get a cached signal if it exists and is still valid."""
        if symbol in self.signal_cache:
            cached = self.signal_cache[symbol]
            if datetime.now() < cached.expires_at:
                return cached.signal
            del self.signal_cache[symbol]
        return None
        
    def _cache_signal(self, symbol: str, signal: Dict):
        """Cache a signal with expiration."""
        expires_at = datetime.now() + timedelta(seconds=self.cache_duration)
        self.signal_cache[symbol] = CachedSignal(signal, datetime.now(), expires_at)
        
        # Also save to disk for persistence
        try:
            cache_file = self.cache_dir / f"{symbol}.json"
            with open(cache_file, 'w') as f:
                json.dump({
                    'signal': signal,
                    'timestamp': datetime.now().isoformat(),
                    'expires_at': expires_at.isoformat()
                }, f)
        except Exception as e:
            logger.error(f"Error saving signal to cache file: {e}")
            
    async def _process_symbol_with_retry(self, symbol: str, risk_per_trade: float, max_retries: int) -> Optional[TradingOpportunity]:
        """Process a single symbol with retry logic."""
        for attempt in range(max_retries):
            try:
                # Check cache first
                cached_signal = self._get_cached_signal(symbol)
                if cached_signal:
                    logger.debug(f"Using cached signal for {symbol}")
                    signal = cached_signal
                else:
                    # Get market data
                    market_data = await self.get_market_data(symbol)
                    if not market_data:
                        logger.debug(f"No market data for {symbol}")
                        return None

                    # Apply advanced filters
                    if not self._apply_advanced_filters(market_data):
                        logger.debug(f"Symbol {symbol} rejected by advanced filters.")
                        return None

                    # Format market data for signal generation
                    formatted_market_data = {
                        'price': float(market_data['ohlcv'][-1]['close']),
                        'funding_rate': float(market_data['funding_rate']),
                        'open_interest': float(market_data.get('open_interest', 0)),
                        'symbol': market_data['symbol'],
                        'volume_24h': float(market_data['volume_24h']),
                        'indicators': market_data.get('indicators', {})
                    }

                    # Generate signal
                    signal = self.signal_generator.generate_signals(
                        formatted_market_data,
                        market_data.get('indicators', {})
                    )

                    if not signal:
                        logger.debug(f"No signal generated for {symbol}")
                        return None

                    # Validate signal
                    validation = self._validate_signal(signal)
                    if not validation.is_valid:
                        logger.error(f"Invalid signal for {symbol}: {validation.errors}")
                        return None

                    if validation.warnings:
                        logger.warning(f"Signal warnings for {symbol}: {validation.warnings}")

                    # Cache valid signal
                    self._cache_signal(symbol, signal)

                # Check confidence after potential caching
                logger.debug(f"Signal confidence for {symbol}: {signal.get('confidence')}")
                if signal.get('confidence', 0) < self.min_confidence:
                    logger.debug(f"Signal for {symbol} discarded due to low confidence ({signal.get('confidence')} < {self.min_confidence})")
                    return None

                # Calculate volatility
                volatility = self.calculate_volatility(market_data['ohlcv'])
                
                # Calculate position parameters
                entry_price = float(signal['price'])
                direction = signal['direction']
                
                # Calculate stop loss and take profit
                atr = volatility * entry_price  # Using volatility as ATR proxy
                stop_loss = entry_price - (2 * atr) if direction == 'LONG' else entry_price + (2 * atr)
                take_profit = entry_price + (4 * atr) if direction == 'LONG' else entry_price - (4 * atr)
                
                # Calculate leverage based on risk
                risk_amount = abs(entry_price - stop_loss)
                leverage = min(risk_per_trade / risk_amount, self.max_leverage)
                
                # Calculate risk-reward ratio
                risk_reward = abs(take_profit - entry_price) / abs(entry_price - stop_loss)
                
                logger.debug(f"Calculated Risk-Reward for {symbol}: {risk_reward}. Minimum required: {self.min_risk_reward}")

                if risk_reward < self.min_risk_reward:
                    logger.debug(f"Opportunity for {symbol} discarded due to low risk-reward ({risk_reward} < {self.min_risk_reward})")
                    return None
                
                opportunity = TradingOpportunity(
                    symbol=market_data['symbol'],
                    direction=direction,
                    entry_price=entry_price,
                    take_profit=take_profit,
                    stop_loss=stop_loss,
                    confidence=signal['confidence'],
                    leverage=leverage,
                    risk_reward=risk_reward,
                    volume_24h=market_data['volume_24h'],
                    volatility=volatility,
                    score=0.0,  # Will be calculated below
                    indicators=signal.get('indicators', {}),
                    reasoning=signal.get('reasoning', [])
                )
                
                # Calculate final score
                opportunity.score = self.calculate_opportunity_score(opportunity)
                
                return opportunity
                
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Retry {attempt + 1}/{max_retries} for {symbol}: {e}")
                    await asyncio.sleep(1.0 * (attempt + 1))  # Exponential backoff
                else:
                    logger.error(f"Failed to process {symbol} after {max_retries} attempts: {e}")
                    return None
                    
        return None

    def _apply_advanced_filters(self, market_data: Dict) -> bool:
        """Apply advanced filters to market data."""
        try:
            symbol = market_data.get('symbol', 'UNKNOWN')

            # Volume filter
            if market_data['volume_24h'] < self.min_volume_24h:
                logger.debug(f"{symbol} rejected by volume filter: {market_data['volume_24h']} < {self.min_volume_24h}")
                return False
                
            # Spread filter
            spread = market_data.get('spread', float('inf')) # Use a high default if missing
            if spread > self.max_spread:
                logger.debug(f"{symbol} rejected by spread filter: {spread} > {self.max_spread}")
                return False
                
            # Liquidity filter
            liquidity = market_data.get('liquidity', 0) # Use 0 default if missing
            if liquidity < self.min_liquidity:
                logger.debug(f"{symbol} rejected by liquidity filter: {liquidity} < {self.min_liquidity}")
                return False
                
            # Volatility filter
            # Note: calculate_volatility handles potential errors internally and returns 0 on failure
            volatility = self.calculate_volatility(market_data['ohlcv'])
            if not (self.min_volatility <= volatility <= self.max_volatility):
                logger.debug(f"{symbol} rejected by volatility filter: {volatility} out of range ({self.min_volatility}-{self.max_volatility})")
                return False
                
            # Market cap filter
            market_cap = market_data.get('market_cap', 0) # Use 0 default if missing
            if market_cap < self.min_market_cap:
                logger.debug(f"{symbol} rejected by market cap filter: {market_cap} < {self.min_market_cap}")
                return False
                
            # Funding rate filter
            funding_rate = market_data.get('funding_rate', 0) # Use 0 default if missing
            if not (self.min_funding_rate <= funding_rate <= self.max_funding_rate):
                logger.debug(f"{symbol} rejected by funding rate filter: {funding_rate} out of range ({self.min_funding_rate}-{self.max_funding_rate})")
                return False
                
            # Open interest filter
            open_interest = market_data.get('open_interest', 0) # Use 0 default if missing
            if open_interest < self.min_open_interest:
                logger.debug(f"{symbol} rejected by open interest filter: {open_interest} < {self.min_open_interest}")
                return False
                
            # Price stability filter
            # Note: _check_price_stability handles potential errors internally and returns False on failure
            if not self._check_price_stability(market_data['ohlcv']):
                logger.debug(f"{symbol} rejected by price stability filter.")
                return False
                
            # Volume trend filter
            # Note: _check_volume_trend handles potential errors internally and returns False on failure
            if not self._check_volume_trend(market_data['ohlcv']):
                logger.debug(f"{symbol} rejected by volume trend filter.")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error applying advanced filters for {symbol}: {e}")
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
            
            # Calculate volume moving averages
            vol_ma5 = np.mean(volumes[-5:])
            vol_ma20 = np.mean(volumes[-20:])
            
            # Volume should be increasing or stable
            if vol_ma5 < vol_ma20 * 0.8:  # 20% decline threshold
                return False
                
            # Check for volume consistency
            vol_std = np.std(volumes[-20:])
            vol_mean = np.mean(volumes[-20:])
            if vol_std / vol_mean > 0.5:  # 50% coefficient of variation threshold
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
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return np.concatenate(([np.nan], rsi))
        
    def _calculate_stochastic(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> np.ndarray:
        """Calculate Stochastic Oscillator."""
        lowest_low = self._calculate_sma(lows, period)
        highest_high = self._calculate_sma(highs, period)
        
        k = 100 * ((closes - lowest_low) / (highest_high - lowest_low))
        return k
        
    def _calculate_atr(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> np.ndarray:
        """Calculate Average True Range."""
        tr1 = np.abs(highs[1:] - lows[1:])
        tr2 = np.abs(highs[1:] - closes[:-1])
        tr3 = np.abs(lows[1:] - closes[:-1])
        
        tr = np.maximum(np.maximum(tr1, tr2), tr3)
        atr = self._calculate_sma(tr, period)
        return np.concatenate(([np.nan], atr))
        
    def _calculate_obv(self, closes: np.ndarray, volumes: np.ndarray) -> np.ndarray:
        """Calculate On-Balance Volume."""
        obv = np.zeros_like(closes)
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
        
        vwap = np.cumsum(typical_prices * volumes) / np.cumsum(volumes)
        return vwap
        
    def _calculate_adx(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Calculate Average Directional Index."""
        # Calculate True Range
        tr1 = np.abs(highs[1:] - lows[1:])
        tr2 = np.abs(highs[1:] - closes[:-1])
        tr3 = np.abs(lows[1:] - closes[:-1])
        tr = np.maximum(np.maximum(tr1, tr2), tr3)
        
        # Calculate Directional Movement
        up_move = highs[1:] - highs[:-1]
        down_move = lows[:-1] - lows[1:]
        
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
        
        # Calculate smoothed values
        tr_smoothed = self._calculate_sma(tr, period)
        plus_di = 100 * self._calculate_sma(plus_dm, period) / tr_smoothed
        minus_di = 100 * self._calculate_sma(minus_dm, period) / tr_smoothed
        
        # Calculate ADX
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = self._calculate_sma(dx, period)
        
        return adx, plus_di, minus_di
        
    def _calculate_cci(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 20) -> np.ndarray:
        """Calculate Commodity Channel Index."""
        typical_price = (highs + lows + closes) / 3
        sma = self._calculate_sma(typical_price, period)
        mean_deviation = np.abs(typical_price - sma)
        mean_deviation_sma = self._calculate_sma(mean_deviation, period)
        
        cci = (typical_price - sma) / (0.015 * mean_deviation_sma)
        return cci 