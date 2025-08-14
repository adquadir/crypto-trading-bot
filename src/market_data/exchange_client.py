# File: src/market_data/exchange_client.py
from typing import Dict, List, Optional, Set, Tuple, Any
import asyncio
import logging
from datetime import datetime, timedelta
import aiohttp
from aiohttp import BasicAuth
from binance.client import Client
from binance.exceptions import BinanceAPIException
import time
from functools import wraps
import os
import statistics
from dataclasses import dataclass, field
from collections import deque
import json
from pathlib import Path
import random
import numpy as np
from src.market_data.websocket_client import MarketDataWebSocket
from src.market_data.config import config
import ccxt
from urllib.parse import urlparse
import pandas as pd
from src.utils.config import load_config
import hmac
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    data: any
    timestamp: datetime = field(default_factory=datetime.now)
    expires_at: datetime = field(default_factory=datetime.now)


@dataclass
class ProxyMetrics:
    response_times: deque = field(default_factory=lambda: deque(maxlen=100))
    error_count: int = 0
    error_418_count: int = 0
    last_error: Optional[datetime] = None
    last_success: Optional[datetime] = None
    last_418_error: Optional[datetime] = None
    total_requests: int = 0
    successful_requests: int = 0
    blocked_until: Optional[datetime] = None


class CacheManager:
    def __init__(self, cache_dir: str = "cache", ttl: int = 60):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.memory_cache: Dict[str, CacheEntry] = {}
        self.ttl = ttl
        
    def get(self, key: str, max_age: int = 300) -> Optional[any]:
        """Get data from cache if not expired."""
        # Check memory cache first
        if key in self.memory_cache:
            entry = self.memory_cache[key]
            if datetime.now() < entry.expires_at:
                return entry.data
            del self.memory_cache[key]
            
        # Check disk cache
        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                    timestamp = datetime.fromisoformat(data['timestamp'])
                    if datetime.now() - timestamp < timedelta(seconds=max_age):
                        # Update memory cache
                        self.memory_cache[key] = CacheEntry(
                            data=data['data'],
                            timestamp=timestamp,
                            expires_at=timestamp + timedelta(seconds=max_age)
                        )
                        return data['data']
            except Exception as e:
                logger.error(f"Error reading cache file {key}: {e}")
        return None
        
    def set(self, key: str, data: any, max_age: int = 300):
        """Store data in both memory and disk cache."""
        expires_at = datetime.now() + timedelta(seconds=max_age)
        entry = CacheEntry(
            data=data,
            timestamp=datetime.now(),
            expires_at=expires_at)
        
        # Update memory cache
        self.memory_cache[key] = entry
        
        # Update disk cache
        try:
            cache_file = self.cache_dir / f"{key}.json"
            with open(cache_file, 'w') as f:
                json.dump({
                    'data': data,
                    'timestamp': entry.timestamp.isoformat()
                }, f)
        except Exception as e:
            logger.error(f"Error writing cache file {key}: {e}")


def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except BinanceAPIException as e:
                    last_exception = e
                    if e.status_code == 418:  # IP ban - rotate proxy immediately
                        logger.warning(f"418 IP ban detected, rotating proxy immediately")
                        # Check if the first argument has _rotate_proxy method (ExchangeClient instance)
                        if args and hasattr(args[0], '_rotate_proxy'):
                            try:
                                await args[0]._rotate_proxy()
                                # Update proxy metrics for 418 error
                                if hasattr(args[0], '_update_proxy_metrics_418'):
                                    args[0]._update_proxy_metrics_418()
                            except Exception as rotate_error:
                                logger.error(f"Error rotating proxy on 418: {rotate_error}")
                        # Still apply some delay but shorter than normal backoff
                        await asyncio.sleep(base_delay)
                    elif e.status_code == 429:  # Rate limit - use normal backoff
                        delay = base_delay * (2 ** attempt)
                        logger.warning(f"Rate limit hit, retrying in {delay}s")
                        await asyncio.sleep(delay)
                    else:
                        raise
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        logger.debug(f"Error in {func.__name__}, retrying in {delay}s: {e}")
                        await asyncio.sleep(delay)
                    else:
                        raise
            raise last_exception
        return wrapper
    return decorator


def rate_limit(limit: int = 10, period: float = 1.0):
    """Rate limiting decorator."""
    last_reset = time.time()
    calls = 0
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            nonlocal last_reset, calls
            
            current_time = time.time()
            if current_time - last_reset >= period:
                last_reset = current_time
                calls = 0
                
            if calls >= limit:
                sleep_time = period - (current_time - last_reset)
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                last_reset = time.time()
                calls = 0
                
            calls += 1
            return await func(*args, **kwargs)
        return wrapper
    return decorator


class ExchangeClient:
    """Client for interacting with cryptocurrency exchange APIs."""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config if config is not None else load_config()
        self.initialized = False
        self.retry_delay = 1.0
        self.max_retries = 1  # Reduced from 3 to minimize log spam
        self.base_url = "https://fapi.binance.com"  # Binance Futures API
        self.ws_url = "wss://fstream.binance.com/ws"
        self.testnet = os.getenv('USE_TESTNET', 'false').lower() == 'true'
        
        # Initialize proxy configuration
        self.proxy_host = os.getenv('PROXY_HOST', '')
        self.proxy_port = str(os.getenv('PROXY_PORT', ''))
        self.proxy_user = os.getenv('PROXY_USER', '')
        self.proxy_pass = os.getenv('PROXY_PASS', '')
        
        # Set up proxy URL for aiohttp
        self.proxy_url = None
        # Check for proxy configuration in the proxy section or from environment
        use_proxy = (
            self.config.get('proxy', {}).get('USE_PROXY', False) or 
            os.getenv('USE_PROXY', 'false').lower() == 'true'
        )
        
        if use_proxy:
            if self.proxy_host and self.proxy_port:
                self.proxy_url = f"http://{self.proxy_host}:{self.proxy_port}"
                if self.proxy_user and self.proxy_pass:
                    self.proxy_url = f"http://{self.proxy_user}:{self.proxy_pass}@{self.proxy_host}:{self.proxy_port}"
                logger.info(f"Proxy configured: {self.proxy_host}:{self.proxy_port}")
                logger.info(f"Full proxy URL: {self.proxy_url}")
            else:
                logger.warning("USE_PROXY is enabled but proxy host or port not configured")
        else:
            logger.info("Proxy not enabled")
        
        # API credentials
        self.api_key = os.getenv('BINANCE_API_KEY')
        self.api_secret = os.getenv('BINANCE_API_SECRET')
        
        # Initialize clients
        self.client = None
        self.futures_client = None
        self.exchange = None
        self.ccxt_client = None  # Add this line to fix the missing attribute
        
        # Initialize WebSocket tracking
        self.ws_clients = {}
        self.ws_last_message = {}
        self.symbols = self.config.get('symbols', ['BTCUSDT'])
        self.ws_manager = None
        self.cache_manager = CacheManager()
        self.cache = self.cache_manager  # Alias for convenience
        self.proxy_metrics = ProxyMetrics()
        
        self.logger = logging.getLogger(__name__)
        self.scalping_mode = self.config.get('scalping_mode', False)
        
        # Initialize proxy rotation
        self.proxy_metrics = {}
        self.rotation_threshold = self.config.get('proxy', {}).get('rotation_threshold', 0.8)
        self.health_check_interval = 60
        self._shutdown_event = asyncio.Event()
        
        # 418 Error handling configuration
        self.rotation_on_418 = self.config.get('proxy', {}).get('rotation_on_418', True)
        self.proxy_cooldown_minutes = self.config.get('proxy', {}).get('proxy_cooldown_after_418_minutes', 30)
        self.max_418_errors = self.config.get('proxy', {}).get('max_418_errors_per_proxy', 3)

        # Load proxy configuration
        self.proxy_list = self.config.get(
            'proxy_ports', os.getenv(
                'PROXY_LIST', '10001,10002,10003').split(','))
        self.failover_ports = self.config.get(
            'failover_ports', os.getenv(
                'FAILOVER_PORTS', '10001,10002,10003').split(','))
        self.current_port_index = 0
        
        # Initialize data structures
        self.open_interest_history = {}
        self.history_length = 24
        self.last_trade_price = {}
        self.volatility_metrics = {}
        self.funding_rates = {}
        self.data_freshness = {}
        self.last_proxy_rotation = 0
        self.rate_limit_errors = 0
        self.last_rate_limit_error = 0
        self.rate_limit_backoff = 1.0  # Initial backoff in seconds
        self.max_rate_limit_backoff = 60.0  # Maximum backoff in seconds

        # Initialize running state
        self.running = False
        self._reconnecting = False

        # Initialize cache TTLs
        self.cache_ttls = {
            'funding_rate': 300,  # 5 minutes
            'volatility': 60,     # 1 minute
            'ticker': 30,         # 30 seconds
            'orderbook': 5        # 5 seconds
        }
        
        # Initialize proxy authentication flag
        self.proxy_auth = bool(self.proxy_user and self.proxy_pass)

    async def _init_client(self):
        """Initialize the Binance client with proper configuration."""
        try:
            # Prepare requests parameters for proxy configuration
            requests_params = {}
            if self.proxy_url:
                requests_params['proxies'] = {
                    'http': self.proxy_url,
                    'https': self.proxy_url
                }
                logger.info(f"Proxy configured for Binance clients: {self.proxy_url}")
            
            # Initialize Binance client with proxy configuration
            self.client = Client(
                api_key=self.api_key,
                api_secret=self.api_secret,
                testnet=self.testnet,
                requests_params=requests_params
            )
            
            # Initialize futures client with proxy configuration
            self.futures_client = Client(
                api_key=self.api_key,
                api_secret=self.api_secret,
                testnet=self.testnet,
                requests_params=requests_params
            )
            
            # Initialize ccxt for private endpoints
            await self._initialize_exchange()
            
            logger.info("Binance clients initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing Binance clients: {e}")
            raise

    async def initialize(self):
        """Initialize the exchange client."""
        try:
            # Initialize Binance clients first
            await self._init_client()
            
            # Initialize exchange (ccxt) - CRITICAL for position fetching
            await self._initialize_exchange()
            
            # Initialize WebSocket connections
            symbols = self.config.get('symbols', ['BTCUSDT'])
            self.ws_manager = MarketDataWebSocket(self, symbols)
            await self.ws_manager.initialize()
            
            # Set running state to True before starting background tasks
            self.running = True
            
            # Start health check loop
            asyncio.create_task(self._health_check_loop())
            
            self.initialized = True
            logger.info(f"Exchange client initialized with symbols: {symbols}")
            
        except Exception as e:
            logger.error(f"Error initializing exchange client: {e}")
            raise

    async def reconnect(self) -> bool:
        """Reconnect to the exchange."""
        try:
            logger.info("Attempting to reconnect to exchange...")
            
            # Close existing connections
            await self.close()
            
            # Reinitialize clients
            await self._init_client()
            
            # Reinitialize WebSocket connections
            if self.ws_manager:
                await self.ws_manager.initialize()
            
            # Set running state and initialization flag
            self.running = True
            self.initialized = True
            logger.info("Successfully reconnected to exchange")
            return True
            
        except Exception as e:
            logger.error(f"Error reconnecting to exchange: {e}")
            return False

    async def check_connection(self) -> bool:
        """Check if the exchange connection is healthy."""
        try:
            if not self.client or not self.futures_client:
                logger.error("Exchange API connection check failed: Clients not initialized")
                return False
                
            # Test connection using a simple API call
            await self._make_request('GET', '/fapi/v1/ping')
            return True
            
        except Exception as e:
            logger.error(f"Exchange API connection check failed: {e}")
            return False

    async def _make_request(self, method: str, endpoint: str, params: Dict = None, signed: bool = False) -> Dict:
        """Make an HTTP request to the exchange API with robust retry logic and 418 proxy rotation."""
        params = params or {}
        max_retries = 5
        base_delay = 0.5
        
        for attempt in range(max_retries):
            try:
                url = f"{self.base_url}{endpoint}"
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                
                if signed:
                    if not self.api_key or not self.api_secret:
                        raise ValueError("API key and secret required for signed requests")
                    headers['X-MBX-APIKEY'] = self.api_key
                    params['timestamp'] = int(time.time() * 1000)
                    params['signature'] = self._generate_signature(params)
                
                # Format proxy URL with authentication
                proxy_url = None
                if self.proxy_host and self.proxy_port:
                    proxy_url = f"http://{self.proxy_host}:{self.proxy_port}"
                    if self.proxy_user and self.proxy_pass:
                        proxy_url = f"http://{self.proxy_user}:{self.proxy_pass}@{self.proxy_host}:{self.proxy_port}"
                
                # Use aiohttp for better async performance
                timeout = aiohttp.ClientTimeout(total=10)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.request(
                        method=method,
                        url=url,
                        params=params,
                        headers=headers,
                        proxy=proxy_url
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            return data
                        elif response.status == 418:  # IP ban - rotate proxy immediately
                            logger.warning(f"HTTP 418 for {endpoint}, attempt {attempt + 1}/{max_retries}")
                            if self.rotation_on_418:
                                logger.warning(f"🔄 418 IP ban detected, rotating proxy immediately")
                                try:
                                    # Update proxy metrics for 418 error
                                    self._update_proxy_metrics_418()
                                    # Rotate to a different proxy
                                    await self._rotate_proxy()
                                    logger.info(f"✅ Proxy rotated due to 418 error, retrying with new proxy")
                                except Exception as rotate_error:
                                    logger.error(f"❌ Error rotating proxy on 418: {rotate_error}")
                            # Short delay before retry with new proxy
                            await asyncio.sleep(base_delay)
                            continue
                        elif response.status == 429:  # Rate limit
                            retry_after = int(response.headers.get('Retry-After', base_delay * (2 ** attempt)))
                            logger.warning(f"Rate limited, retrying in {retry_after}s")
                            await asyncio.sleep(retry_after)
                            continue
                        else:
                            logger.warning(f"HTTP {response.status} for {endpoint}, attempt {attempt + 1}/{max_retries}")
                            if attempt == max_retries - 1:
                                raise Exception(f"HTTP {response.status} after {max_retries} attempts")
                            await asyncio.sleep(base_delay * (2 ** attempt))
                            continue
                            
            except asyncio.TimeoutError:
                logger.warning(f"Timeout for {endpoint}, attempt {attempt + 1}/{max_retries}")
                if attempt == max_retries - 1:
                    raise Exception(f"Timeout after {max_retries} attempts")
                await asyncio.sleep(base_delay * (2 ** attempt))
                continue
            except Exception as e:
                logger.warning(f"Request error for {endpoint}: {e}, attempt {attempt + 1}/{max_retries}")
                if attempt == max_retries - 1:
                    raise Exception(f"Request failed after {max_retries} attempts: {e}")
                await asyncio.sleep(base_delay * (2 ** attempt))
                continue
        
        raise Exception(f"All {max_retries} attempts failed for {endpoint}")

    def _generate_signature(self, params: Dict) -> str:
        """Generate HMAC SHA256 signature for signed requests."""
        query_string = '&'.join([f"{key}={value}" for key, value in params.items() if key != 'signature'])
        return hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    async def get_all_symbols(self):
        """Get all available trading symbols from the exchange using aiohttp."""
        try:
            data = await self._make_request('GET', '/fapi/v1/exchangeInfo')
            symbols = [s['symbol'] for s in data['symbols'] 
                      if s['contractType'] == 'PERPETUAL' and s['status'] == 'TRADING']
            logger.info(f"Retrieved {len(symbols)} trading symbols: {symbols[:10]} ...")
            return symbols
        except Exception as e:
            logger.error(f"Error getting symbols: {e}")
            return []

    async def get_ticker_24h(self, symbol: str) -> Dict:
        """Get 24-hour ticker data for a symbol with robust fallback."""
        try:
            # Try direct REST API first
            params = {'symbol': symbol}
            ticker = await self._make_request('GET', '/fapi/v1/ticker/24hr', params)
            if ticker and ticker.get('lastPrice'):
                return ticker
        except Exception as e:
            logger.warning(f"Direct REST API failed for {symbol}: {e}")
        
        try:
            # Try CCXT client as fallback
            if self.ccxt_client:
                ticker_data = await asyncio.to_thread(
                    self.ccxt_client.fetch_ticker,
                    symbol=symbol
                )
                if ticker_data and ticker_data.get('last'):
                    return {
                        'symbol': symbol,
                        'lastPrice': str(ticker_data['last']),
                        'priceChange': str(ticker_data.get('change', 0)),
                        'priceChangePercent': str(ticker_data.get('percentage', 0)),
                        'volume': str(ticker_data.get('baseVolume', 0)),
                        'quoteVolume': str(ticker_data.get('quoteVolume', 0))
                    }
        except Exception as e:
            logger.warning(f"CCXT fallback failed for {symbol}: {e}")
        
        try:
            # Try WebSocket cached data as final fallback
            if symbol in self.last_trade_price:
                price = self.last_trade_price[symbol]
                return {
                    'symbol': symbol,
                    'lastPrice': str(price),
                    'priceChange': '0',
                    'priceChangePercent': '0',
                    'volume': '0',
                    'quoteVolume': '0'
                }
        except Exception as e:
            logger.warning(f"WebSocket cache fallback failed for {symbol}: {e}")
        
        # If all methods fail, raise exception - no mock prices
        raise Exception(f"All price fetching methods failed for {symbol}")

    async def get_orderbook(self, symbol: str, limit: int = 10) -> Dict:
        """Get orderbook data for a symbol."""
        try:
            params = {'symbol': symbol, 'limit': limit}
            return await self._make_request('GET', '/fapi/v1/depth', params)
        except Exception as e:
            logger.error(f"Error getting orderbook for {symbol}: {e}")
            raise

    async def get_funding_rate(self, symbol: str) -> Dict:
        """Get current funding rate for a symbol."""
        try:
            params = {'symbol': symbol}
            return await self._make_request('GET', '/fapi/v1/premiumIndex', params)
        except Exception as e:
            logger.error(f"Error getting funding rate for {symbol}: {e}")
            raise

    async def get_open_interest(self, symbol: str) -> Dict:
        """Get open interest for a symbol."""
        try:
            params = {'symbol': symbol}
            return await self._make_request('GET', '/fapi/v1/openInterest', params)
        except Exception as e:
            logger.error(f"Error getting open interest for {symbol}: {e}")
            raise

    async def get_klines(self, symbol: str, interval: str = '1m', limit: int = 100) -> List[Dict]:
        """Get kline/candlestick data for a symbol."""
        try:
            params = {
                'symbol': symbol,
                'interval': interval,
                'limit': limit
            }
            return await self._make_request('GET', '/fapi/v1/klines', params)
        except Exception as e:
            logger.error(f"Error getting klines for {symbol}: {e}")
            raise

    async def get_account(self) -> Dict:
        """Get account information."""
        try:
            return await self._make_request('GET', '/fapi/v2/account', signed=True)
        except Exception as e:
            logger.error(f"Error getting account info: {e}")
            raise

    async def get_position(self, symbol: str) -> Dict:
        """Get position information for a symbol."""
        try:
            params = {'symbol': symbol}
            return await self._make_request('GET', '/fapi/v2/positionRisk', params, signed=True)
        except Exception as e:
            logger.error(f"Error getting position for {symbol}: {e}")
            raise

    async def place_order(self, symbol: str, side: str, order_type: str, 
                         quantity: float, price: Optional[float] = None,
                         stop_price: Optional[float] = None,
                         reduce_only: bool = False) -> Dict:
        """Place an order."""
        try:
            params = {
                'symbol': symbol,
                'side': side,
                'type': order_type,
                'quantity': quantity,
                'reduceOnly': reduce_only
            }
            if price:
                params['price'] = price
            if stop_price:
                params['stopPrice'] = stop_price
            return await self._make_request('POST', '/fapi/v1/order', params, signed=True)
        except Exception as e:
            logger.error(f"Error placing order for {symbol}: {e}")
            raise

    def _setup_proxy(self):
        """Set up proxy configuration."""
        try:
            if self.proxy_host and self.proxy_port:
                proxy_url = f"http://{self.proxy_host}:{self.proxy_port}"
                if self.proxy_auth:
                    proxy_url = f"http://{self.proxy_user}:{self.proxy_pass}@{self.proxy_host}:{self.proxy_port}"
                
                self.proxy_config = {
                    'http': proxy_url,
                    'https': proxy_url
                }
                self.proxies = self.proxy_config
                logger.info(f"Proxy configured: {self.proxy_host}:{self.proxy_port}")
            else:
                logger.warning("Proxy enabled but host or port not configured")
                self.proxies = None
        except Exception as e:
            logger.error(f"Error setting up proxy: {e}")
            self.proxies = None

    def _handle_rate_limit_error(self):
        """Handle rate limit errors with exponential backoff."""
        current_time = time.time()
        self.rate_limit_errors += 1
        
        # Reset backoff if last error was more than 5 minutes ago
        if current_time - self.last_rate_limit_error > 300:
            self.rate_limit_errors = 1
            self.rate_limit_backoff = 1.0
        
        # Calculate exponential backoff
        self.rate_limit_backoff = min(
            self.rate_limit_backoff * 2,
            self.max_rate_limit_backoff
        )
        
        self.last_rate_limit_error = current_time
        logger.warning(
            f"Rate limit error #{self.rate_limit_errors}. "
            f"Backing off for {self.rate_limit_backoff:.1f} seconds"
        )
        
        # Sleep with the calculated backoff
        time.sleep(self.rate_limit_backoff)

    @retry_with_backoff(max_retries=1)  # Reduced from 3 to 1
    @rate_limit(limit=3, period=1.0)  # Reduced to 3 requests per second
    async def get_historical_data(self, symbol: str, interval: str, limit: int = 100) -> List[Dict]:
        """Get historical klines/candlestick data."""
        try:
            if not self.ccxt_client:
                raise ConnectionError("CCXT client not initialized")
                
            # Map interval to CCXT timeframe
            timeframe_map = {
                '1m': '1m',
                '3m': '3m',
                '5m': '5m',
                '15m': '15m',
                '30m': '30m',
                '1h': '1h',
                '2h': '2h',
                '4h': '4h',
                '6h': '6h',
                '8h': '8h',
                '12h': '12h',
                '1d': '1d',
                '3d': '3d',
                '1w': '1w',
                '1M': '1M'
            }
            
            timeframe = timeframe_map.get(interval)
            if not timeframe:
                raise ValueError(f"Invalid interval: {interval}")
                
            # Get OHLCV data using CCXT
            ohlcv = await asyncio.to_thread(
                self.ccxt_client.fetch_ohlcv,
                symbol=symbol,
                timeframe=timeframe,
                limit=limit
            )
            
            # Reset rate limit backoff on successful request
            self.rate_limit_errors = 0
            self.rate_limit_backoff = 1.0
            
            # Format response to match Binance structure exactly
            return [{
                'openTime': candle[0],
                'open': float(candle[1]),
                'high': float(candle[2]),
                'low': float(candle[3]),
                'close': float(candle[4]),
                'volume': float(candle[5]),
                'closeTime': candle[0] + self._get_interval_milliseconds(interval),
                'quoteAssetVolume': 0.0,  # Not provided by CCXT
                'numberOfTrades': 0,  # Not provided by CCXT
                'takerBuyBaseAssetVolume': 0.0,  # Not provided by CCXT
                'takerBuyQuoteAssetVolume': 0.0,  # Not provided by CCXT
                'ignore': 0.0
            } for candle in ohlcv]
            
        except ccxt.RateLimitExceeded as e:
            logger.warning(f"Rate limit exceeded while fetching historical data: {e}")
            self._handle_rate_limit_error()
            raise
        except ccxt.NetworkError as e:
            logger.debug(f"Network error while fetching historical data: {e}")
            raise
        except ccxt.ExchangeError as e:
            logger.debug(f"Exchange error while fetching historical data: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching historical data for {symbol}: {e}")
            raise

    def _get_interval_milliseconds(self, interval: str) -> int:
        """Convert interval string to milliseconds."""
        unit = interval[-1]
        value = int(interval[:-1])
        
        if unit == 'm':
            return value * 60 * 1000
        elif unit == 'h':
            return value * 60 * 60 * 1000
        elif unit == 'd':
            return value * 24 * 60 * 60 * 1000
        elif unit == 'w':
            return value * 7 * 24 * 60 * 60 * 1000
        elif unit == 'M':
            return value * 30 * 24 * 60 * 60 * 1000
        else:
            raise ValueError(f"Invalid interval unit: {unit}")

    def _should_rotate_proxy(self) -> bool:
        """Check if proxy should be rotated based on error rates and 418 errors."""
        if self.proxy_port not in self.proxy_metrics:
            return False
            
        metrics = self.proxy_metrics[self.proxy_port]
        if metrics.total_requests < 10:
            return False
            
        # Check if proxy is temporarily blocked due to 418 errors
        if metrics.blocked_until and datetime.now() < metrics.blocked_until:
            return True
            
        error_rate = metrics.error_count / metrics.total_requests
        avg_response = statistics.mean(
            metrics.response_times) if metrics.response_times else float('inf')
        
        # Immediate rotation if too many 418 errors
        if metrics.error_418_count >= 3:
            return True
            
        return error_rate > self.rotation_threshold or avg_response > 1.0

    def _update_proxy_metrics_418(self):
        """Update proxy metrics specifically for 418 errors."""
        try:
            if self.proxy_port not in self.proxy_metrics:
                self.proxy_metrics[self.proxy_port] = ProxyMetrics()
                
            metrics = self.proxy_metrics[self.proxy_port]
            metrics.error_418_count += 1
            metrics.last_418_error = datetime.now()
            
            # Block proxy temporarily if too many 418 errors
            if metrics.error_418_count >= self.max_418_errors:
                # Block for configured minutes after max 418 errors
                metrics.blocked_until = datetime.now() + timedelta(minutes=self.proxy_cooldown_minutes)
                logger.warning(f"Proxy {self.proxy_port} blocked for {self.proxy_cooldown_minutes} minutes due to {metrics.error_418_count} 418 errors")
                
        except Exception as e:
            logger.error(f"Error updating proxy metrics for 418: {e}")

    async def _find_best_proxy(self):
        """Find the best proxy port based on health metrics and avoiding blocked proxies."""
        if not hasattr(self, 'proxy_list') or not self.proxy_list:
            return str(os.getenv('PROXY_PORT', '10001'))
        
        available_proxies = []
        current_time = datetime.now()
        
        # Filter out blocked proxies and collect available ones with their scores
        for port in self.proxy_list:
            port_str = str(port)
            if port_str in self.proxy_metrics:
                metrics = self.proxy_metrics[port_str]
                
                # Skip if proxy is temporarily blocked
                if metrics.blocked_until and current_time < metrics.blocked_until:
                    logger.debug(f"Skipping blocked proxy {port_str} until {metrics.blocked_until}")
                    continue
                
                # Calculate proxy score (lower is better)
                score = self._calculate_proxy_score(metrics)
                available_proxies.append((port_str, score))
            else:
                # New proxy, give it a chance
                available_proxies.append((port_str, 0))
        
        if not available_proxies:
            # All proxies are blocked, use round-robin as fallback
            logger.warning("All proxies are blocked, using round-robin fallback")
            self.current_port_index = (self.current_port_index + 1) % len(self.proxy_list)
            return str(self.proxy_list[self.current_port_index])
        
        # Sort by score and pick the best one
        available_proxies.sort(key=lambda x: x[1])
        best_proxy = available_proxies[0][0]
        
        logger.debug(f"Selected proxy {best_proxy} with score {available_proxies[0][1]}")
        return best_proxy

    def _calculate_proxy_score(self, metrics: ProxyMetrics) -> float:
        """Calculate a score for proxy selection (lower is better)."""
        try:
            # Base score starts at 0
            score = 0.0
            
            # Penalize 418 errors heavily
            score += metrics.error_418_count * 10
            
            # Penalize general errors
            if metrics.total_requests > 0:
                error_rate = metrics.error_count / metrics.total_requests
                score += error_rate * 5
            
            # Penalize slow response times
            if metrics.response_times:
                avg_response_time = statistics.mean(metrics.response_times)
                score += avg_response_time
            
            # Bonus for recent successful requests
            if metrics.last_success:
                minutes_since_success = (datetime.now() - metrics.last_success).total_seconds() / 60
                if minutes_since_success < 10:  # Recent success within 10 minutes
                    score -= 1.0
            
            return score
            
        except Exception as e:
            logger.error(f"Error calculating proxy score: {e}")
            return float('inf')  # Return worst score on error

    async def _rotate_proxy(self):
        """Rotate to the best available proxy."""
        try:
            best_port = await self._find_best_proxy()
            if best_port != self.proxy_port:
                old_port = self.proxy_port
                logger.info(f"🔄 Rotating proxy from {old_port} to {best_port}")
                
                # Update proxy port
                self.proxy_port = str(best_port)
                
                # Update proxy URL
                if self.proxy_host and self.proxy_port:
                    self.proxy_url = f"http://{self.proxy_host}:{self.proxy_port}"
                    if self.proxy_user and self.proxy_pass:
                        self.proxy_url = f"http://{self.proxy_user}:{self.proxy_pass}@{self.proxy_host}:{self.proxy_port}"
                
                # Reinitialize clients with new proxy
                await self._init_client()
                
                logger.info(f"✅ Proxy rotation complete: {old_port} → {best_port}")
            else:
                logger.debug(f"Proxy rotation not needed, already using best proxy: {self.proxy_port}")
                
        except Exception as e:
            logger.error(f"❌ Error during proxy rotation: {e}")
            raise

    async def _reinitialize_websockets(self):
        """Close and reopen all websocket connections."""
        for symbol, ws in list(self.ws_clients.items()):
            try:
                await ws.close()
                del self.ws_clients[symbol]
                await self._initialize_websocket(symbol)
            except Exception as e:
                logger.error(f"Error reinitializing websocket for {symbol}: {e}")

    async def _initialize_websocket(self, symbol: str) -> None:
        try:
            # Create WebSocket client with the correct parameters
            ws_client = MarketDataWebSocket(self, [symbol], cache_ttl=5)
            
            # Register the unified handler for all event types
            ws_client.register_callback("kline", self._handle_ws_message)
            ws_client.register_callback("trade", self._handle_ws_message)
            ws_client.register_callback("depth", self._handle_ws_message)
            
            # Store client
            self.ws_clients[symbol] = ws_client
            
            # Connect and subscribe to channels
            ws_client.connect()
            
            # Start heartbeat monitoring
            self.ws_last_message[symbol] = time.time()
            asyncio.create_task(self._monitor_websocket_heartbeat())
            
            logger.info(f"WebSocket initialized for {symbol}")
            
        except Exception as e:
            logger.error(f"Error initializing WebSocket for {symbol}: {str(e)}")
            raise

    async def _update_funding_rates(self):
        """Background task to update funding rates."""
        while True:
            try:
                for symbol in self.symbols:
                    funding_rate = await self.get_funding_rate(symbol)
                    if funding_rate:
                        self.cache.set(symbol, {
                            'funding_rate': {
                                'value': funding_rate,
                                'timestamp': time.time()
                            }
                        })
                await asyncio.sleep(self.cache_ttls['funding_rate'])
            except Exception as e:
                self.logger.error(f"Error updating funding rates: {str(e)}")
                await asyncio.sleep(5)

    async def _update_volatility_metrics(self):
        """Update volatility metrics for all symbols."""
        while True:
            try:
                for symbol in self.symbols:
                    await self._update_volatility(symbol)
                await asyncio.sleep(60)  # Update every minute
            except Exception as e:
                logger.error(f"Error updating volatility metrics: {e}")
                await asyncio.sleep(5)  # Wait before retrying

    async def close(self):
        """Close all connections and stop background tasks."""
        try:
            self.running = False
            if self.ws_manager:
                await self.ws_manager.stop()
            logger.info("Exchange client stopped")
        except Exception as e:
            logger.error(f"Error stopping exchange client: {e}")
            raise

    def _get_next_proxy(self) -> str:
        """Get next proxy in rotation."""
        proxy = self.proxy_list[self.current_port_index]
        self.current_port_index = (
            self.current_port_index + 1) % len(self.proxy_list)
        return proxy

    async def _handle_ws_message(self, message):
        """Handle incoming WebSocket messages."""
        try:
            if not message:
                return
                
            # Process message based on type
            if 'e' in message:
                event_type = message['e']
                if event_type == 'kline':
                    await self._handle_kline_update(message['s'], message)
                elif event_type == 'trade':
                    await self._handle_trade_update(message['s'], message)
                elif event_type == 'depth':
                    await self._handle_depth_update(message['s'], message)
                    
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")

    async def _handle_ws_error(self, error):
        """Handle WebSocket errors."""
        try:
            logger.error(f"WebSocket error: {error}")
            await self._handle_connection_error()
        except Exception as e:
            logger.error(f"Error handling WebSocket error: {e}")

    async def _handle_ws_close(self, close_status_code, close_msg):
        """Handle WebSocket connection close."""
        try:
            logger.warning(
                f"WebSocket connection closed: {close_status_code} - {close_msg}")
            await self._handle_connection_error()
        except Exception as e:
            logger.error(f"Error handling WebSocket close: {e}")

    async def _monitor_websocket_heartbeat(self):
        """Monitor WebSocket heartbeat."""
        while self.running:
            try:
                for symbol, ws_client in self.ws_clients.items():
                    if ws_client and ws_client.connection:
                        await ws_client.connection.ping()
                        logger.debug(f"Sent ping to WebSocket for {symbol}")
                await asyncio.sleep(30)  # Send ping every 30 seconds
            except Exception as e:
                logger.error(f"Error in WebSocket heartbeat: {e}")
                await asyncio.sleep(5)  # Wait before retrying

    async def _update_volatility(self, symbol):
        """Update volatility metrics for a symbol."""
        try:
            klines = await self._fetch_ohlcv_rest(symbol, '1h')
            if klines and len(klines) >= 20:
                closes = [float(k['close']) for k in klines[-20:]]
                returns = np.diff(closes) / closes[:-1]
                vol = np.std(returns) * np.sqrt(24 * 60)  # Annualized
                self.cache.set(f"{symbol}_volatility", vol, max_age=300)
        except Exception as e:
            logger.error(f"Error updating volatility for {symbol}: {e}")

    async def _fetch_ohlcv_rest(self, symbol, timeframe):
        """Fetch OHLCV data from REST API."""
        try:
            klines = await asyncio.to_thread(self.client.futures_klines, symbol=symbol, interval=timeframe, limit=100)
            formatted_data = [{
                'timestamp': int(k[0]),
                'open': float(k[1]),
                'high': float(k[2]),
                'low': float(k[3]),
                'close': float(k[4]),
                'volume': float(k[5]),
                'close_time': int(k[6]),
                'quote_volume': float(k[7]),
                'trades': int(k[8]),
                'taker_buy_base': float(k[9]),
                'taker_buy_quote': float(k[10])
            } for k in klines]
            return formatted_data
        except Exception as e:
            logger.error(f"Error fetching OHLCV data for {symbol}: {e}")
            return None

    async def _fetch_ticker_rest(self, symbol):
        """Fetch ticker data from REST API."""
        try:
            ticker = await asyncio.to_thread(self.client.futures_ticker, symbol=symbol)
            return {
                'symbol': ticker['symbol'],
                'priceChange': float(ticker['priceChange']),
                'priceChangePercent': float(ticker['priceChangePercent']),
                'weightedAvgPrice': float(ticker['weightedAvgPrice']),
                'lastPrice': float(ticker['lastPrice']),
                'lastQty': float(ticker['lastQty']),
                'openPrice': float(ticker['openPrice']),
                'highPrice': float(ticker['highPrice']),
                'lowPrice': float(ticker['lowPrice']),
                'volume': float(ticker['volume']),
                'quoteVolume': float(ticker['quoteVolume']),
                'openTime': int(ticker['openTime']),
                'closeTime': int(ticker['closeTime']),
                'firstId': int(ticker['firstId']),
                'lastId': int(ticker['lastId']),
                'count': int(ticker['count'])
            }
        except Exception as e:
            logger.error(f"Error fetching ticker data for {symbol}: {e}")
            return None

    async def _fetch_orderbook_rest(self, symbol):
        """Fetch orderbook data from REST API."""
        try:
            orderbook = await asyncio.to_thread(self.client.futures_order_book, symbol=symbol, limit=10)
            return {
                'bids': [[float(price), float(qty)] for price, qty in orderbook['bids']],
                'asks': [[float(price), float(qty)] for price, qty in orderbook['asks']]
            }
        except Exception as e:
            logger.error(f"Error fetching orderbook data for {symbol}: {e}")
            return None

    def get_data_freshness(self, symbol: str) -> Dict[str, int]:
        """Get data freshness timestamps for a symbol.
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Dict[str, int]: Timestamps of when each data type was last updated
        """
        try:
            if symbol not in self.data_freshness:
                return {}
                
            return self.data_freshness[symbol]
            
        except Exception as e:
            logger.error(
                f"Error getting data freshness for {symbol}: {str(e)}")
            return {}
            
    def _update_data_freshness(self, symbol: str, data_type: str) -> None:
        """Update data freshness timestamp for a symbol and data type.
        
        Args:
            symbol: Trading pair symbol
            data_type: Type of data (ohlcv, orderbook, etc.)
        """
        try:
            if symbol not in self.data_freshness:
                self.data_freshness[symbol] = {}
                
            self.data_freshness[symbol][data_type] = int(time.time() * 1000)
            
        except Exception as e:
            logger.error(
                f"Error updating data freshness for {symbol} {data_type}: {str(e)}")
            
    def _get_cached_data(self, key: str) -> Optional[Dict]:
        """Get data from cache."""
        return self.cache.get(key)

    def _cache_data(self, key: str, data: Dict, ttl: int = 60):
        """Cache data with TTL."""
        self.cache.set(key, data, ttl)

    async def get_market_data(self, symbol: str) -> Dict[str, Any]:
        """Get market data for a symbol."""
        try:
            # Get orderbook
            orderbook = await self.get_orderbook(symbol)
            
            # Get 24h ticker
            ticker = await self.get_ticker_24h(symbol)
            
            # Get klines for volatility calculation
            klines = await self.get_klines(symbol, '1m', 20)
            
            # Calculate basic metrics from available data
            price = float(ticker.get('lastPrice', 0)) if ticker else 0
            volume = float(ticker.get('volume', 0)) if ticker else 0
            
            # Calculate volatility from recent klines
            volatility = 0.0
            if klines and len(klines) >= 2:
                closes = [float(k[4]) for k in klines]  # Close prices
                if len(closes) >= 2:
                    returns = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, len(closes))]
                    volatility = sum(abs(r) for r in returns) / len(returns) if returns else 0.0
            
            # Calculate spread from orderbook
            spread = 0.0
            if orderbook and orderbook.get('bids') and orderbook.get('asks'):
                best_bid = float(orderbook['bids'][0][0]) if orderbook['bids'] else 0
                best_ask = float(orderbook['asks'][0][0]) if orderbook['asks'] else 0
                if best_bid > 0 and best_ask > 0:
                    spread = (best_ask - best_bid) / best_ask * 100  # Spread as percentage
            
            # Combine all data
            market_data = {
                'symbol': symbol,
                'price': price,
                'volume': volume,
                'volatility': volatility,
                'spread': spread,
                'orderbook': orderbook,
                'ticker': ticker,
                'klines': klines
            }
            
            return market_data
        except Exception as e:
            logger.error(f"Error getting market data for {symbol}: {e}")
            return {}

    async def _initialize_exchange(self):
        """Initialize the exchange client with proper configuration (no public ccxt calls)."""
        try:
            # Only initialize ccxt for private endpoints (orders, balances, etc.)
            exchange_config = {
                'enableRateLimit': True,
                'apiKey': self.api_key,          # 🔐 add
                'secret': self.api_secret,       # 🔐 add
                'options': {
                    'defaultType': 'future',  # Use futures market
                    'adjustForTimeDifference': True,
                },
                'headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
            }
            # If you ever run testnet, also map Futures testnet URL:
            if self.testnet:
                exchange_config.setdefault('urls', {}).setdefault('api', {})['fapi'] = 'https://testnet.binancefuture.com/fapi'

            # Check for proxy configuration in the proxy section or from environment
            use_proxy = (
                self.config.get('proxy', {}).get('USE_PROXY', False) or 
                os.getenv('USE_PROXY', 'false').lower() == 'true'
            )
            
            if use_proxy:
                proxy_url = f"http://{self.proxy_host}:{self.proxy_port}"
                if self.proxy_user and self.proxy_pass:
                    proxy_url = f"http://{self.proxy_user}:{self.proxy_pass}@{self.proxy_host}:{self.proxy_port}"
                # Use only one proxy method to avoid conflicts
                exchange_config['proxy'] = proxy_url
                logger.info(f"Proxy configured for exchange: {self.proxy_host}:{self.proxy_port}")
                logger.info(f"Full proxy URL: {proxy_url}")
            logger.info(f"Initializing ccxt with API credentials: {exchange_config}")
            self.exchange = ccxt.binance(exchange_config)
            self.ccxt_client = self.exchange  # Alias for compatibility
            logger.info("Exchange client initialized with API credentials for private endpoints")
        except Exception as e:
            logger.error(f"Error initializing exchange: {e}")
            raise

    async def stop(self):
        """Stop the exchange client and WebSocket manager."""
        try:
            self.running = False
            if self.ws_manager:
                await self.ws_manager.stop()
            logger.info("Exchange client stopped")
        except Exception as e:
            logger.error(f"Error stopping exchange client: {e}")
            raise

    async def _handle_kline_update(self, symbol: str, kline_data: dict):
        """Handle kline update from WebSocket."""
        # Update the last trade price
        self.last_trade_price[symbol] = float(kline_data['k']['c'])
        logger.debug(
            f"Updated last trade price for {symbol}: {
                self.last_trade_price[symbol]}")

    async def _check_proxy_health(self):
        """Check the health of the current proxy."""
        try:
            if not self.proxy_host or not self.proxy_port:
                logger.warning("No proxy configured for health check")
                return False
                
            # Test proxy connection
            proxy_url = f"http://{self.proxy_host}:{self.proxy_port}"
            if self.proxy_auth:
                proxy_url = f"http://{self.proxy_user}:{self.proxy_pass}@{self.proxy_host}:{self.proxy_port}"
            
            # Use shorter timeout to prevent hanging
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    f"{self.base_url}/api/v3/time",
                    proxy=proxy_url
                ) as response:
                    if response.status == 200:
                        logger.debug("Proxy health check passed")  # Changed to debug to reduce log spam
                        return True
                    else:
                        logger.warning(f"Proxy health check failed: HTTP {response.status}")
                        return False
                        
        except asyncio.TimeoutError:
            logger.warning("Proxy health check timed out")
            return False
        except aiohttp.ClientError as e:
            logger.warning(f"Proxy health check failed: {type(e).__name__}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Proxy health check error: {type(e).__name__}: {str(e)}")
            return False

    async def _health_check_loop(self):
        """Monitor the health of the proxy and reconnect if necessary."""
        consecutive_failures = 0
        max_failures = 3  # Maximum consecutive failures before giving up
        
        while self.running:
            try:
                if not await self._check_proxy_health():
                    consecutive_failures += 1
                    logger.warning(f"Proxy health check failed ({consecutive_failures}/{max_failures})")
                    
                    if consecutive_failures >= max_failures:
                        logger.error(f"Proxy health check failed {max_failures} times consecutively. Stopping health checks.")
                        break
                    
                    # Only attempt reconnection if not already reconnecting
                    if not hasattr(self, '_reconnecting') or not self._reconnecting:
                        logger.warning("Attempting to reconnect...")
                        await self._handle_connection_error()
                else:
                    # Reset failure counter on successful health check
                    if consecutive_failures > 0:
                        logger.info("Proxy health check recovered")
                        consecutive_failures = 0
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error in health check loop: {type(e).__name__}: {str(e)}")
                await asyncio.sleep(60)  # Continue checking despite errors

    async def _handle_connection_error(self):
        """Handle connection errors by reconnecting."""
        if self._reconnecting:
            logger.debug("Reconnection already in progress, skipping...")
            return
            
        try:
            self._reconnecting = True
            logger.info("Handling connection error...")
            await self.close()
            await asyncio.sleep(2)  # Brief pause before reconnecting
            await self.initialize()
            logger.info("Connection error handled successfully")
        except Exception as e:
            logger.error(f"Failed to handle connection error: {type(e).__name__}: {str(e)}")
        finally:
            self._reconnecting = False

    async def _test_proxy_connection(self) -> bool:
        """Test the proxy connection."""
        try:
            if not self.proxy_host or not self.proxy_port:
                logger.warning("No proxy configured for connection test")
                return False
                
            # Test proxy connection
            proxy_url = f"http://{self.proxy_host}:{self.proxy_port}"
            if self.proxy_auth:
                proxy_url = f"http://{self.proxy_user}:{self.proxy_pass}@{self.proxy_host}:{self.proxy_port}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/api/v3/time",
                    proxy=proxy_url,
                    timeout=10
                ) as response:
                    if response.status == 200:
                        logger.info("Proxy connection test successful")
                        return True
                    else:
                        logger.warning(f"Proxy connection test failed: {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"Error testing proxy connection: {e}")
            return False

    def _get_cache_ttl(
            self,
            data_type: str,
            scalping_mode: bool = False) -> int:
        """Get the cache TTL for a specific data type."""
        # Placeholder for cache TTL logic
        return 60  # Default TTL in seconds

    async def _setup_symbol_websocket(self, symbol: str) -> None:
        """Set up WebSocket connection for a symbol."""
        try:
            # Create WebSocket client for the symbol
            ws_client = MarketDataWebSocket(
                exchange_client=self,
                symbols=[symbol],
                cache_ttl=5
            )
            
            # Connect to WebSocket
            ws_client.connect()
            
            # Store the client
            self.ws_clients[symbol] = ws_client
            logger.info(f"WebSocket client started for {symbol}")
        except Exception as e:
            logger.error(f"Error setting up WebSocket for {symbol}: {e}")
            raise

    def _init_ws_manager(self):
        """Initialize the WebSocket manager."""
        try:
            # Initialize WebSocket manager with correct parameters
            self.ws_manager = MarketDataWebSocket(
                exchange_client=self,
                symbols=self.symbols,
                cache_ttl=int(os.getenv('CACHE_TTL', '60'))
            )
            logger.info("WebSocket manager initialized")
        except Exception as e:
            logger.error(f"Error initializing WebSocket manager: {e}")
            raise

    @retry_with_backoff(max_retries=3)
    @rate_limit(limit=3, period=1.0)
    async def get_open_positions(self) -> List[Dict]:
        """Get all open positions."""
        try:
            if not self.ccxt_client:
                raise ConnectionError("CCXT client not initialized")
                
            # Get all positions using CCXT
            positions = await asyncio.to_thread(
                self.ccxt_client.fetch_positions
            )
            
            if not positions:
                return []
                
            # Filter and format open positions
            open_positions = []
            for pos in positions:
                if float(pos.get('contracts', 0)) != 0:
                    open_positions.append({
                        'symbol': pos.get('symbol'),
                        'positionAmt': float(pos.get('contracts', 0)),
                        'entryPrice': float(pos.get('entryPrice', 0)),
                        'markPrice': float(pos.get('markPrice', 0)),
                        'unRealizedProfit': float(pos.get('unrealizedPnl', 0)),
                        'liquidationPrice': float(pos.get('liquidationPrice', 0)),
                        'leverage': float(pos.get('leverage', 0)),
                        'marginType': pos.get('marginMode', 'cross'),
                        'updateTime': pos.get('timestamp', 0)
                    })
                    
            return open_positions
            
        except ccxt.NetworkError as e:
            logger.error(f"Network error while fetching positions: {e}")
            raise
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error while fetching positions: {e}")
            raise
        except Exception as e:
            logger.error(f"Error getting open positions: {e}")
            return []

    async def get_ohlcv(self, symbol: str, timeframe: str = '1m', limit: int = 100) -> List[Dict]:
        """Alias for get_klines to maintain compatibility with other parts of the codebase."""
        return await self.get_klines(symbol=symbol, interval=timeframe, limit=limit)

    async def get_recent_trades(self, symbol: str, since: datetime) -> List[Dict]:
        """Get recent trades for a symbol since a specific time"""
        try:
            if not self.ccxt_client:
                logger.error("CCXT client not initialized")
                return []
            
            # Convert datetime to timestamp
            since_timestamp = int(since.timestamp() * 1000)
            
            # Fetch recent trades using CCXT
            trades = await asyncio.to_thread(
                self.ccxt_client.fetch_my_trades,
                symbol=symbol,
                since=since_timestamp,
                limit=100
            )
            
            logger.debug(f"Fetched {len(trades)} recent trades for {symbol}")
            return trades
            
        except Exception as e:
            logger.error(f"Error fetching recent trades for {symbol}: {e}")
            return []

    async def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for a symbol"""
        try:
            ticker = await self.get_ticker_24h(symbol)
            if ticker and 'lastPrice' in ticker:
                return float(ticker['lastPrice'])
            return None
            
        except Exception as e:
            logger.error(f"Error getting current price for {symbol}: {e}")
            return None

    async def create_market_order(self, symbol: str, side: str, amount: float) -> Optional[Dict]:
        """Create a market order"""
        try:
            if not self.ccxt_client:
                logger.error("CCXT client not initialized")
                return None
            
            # Execute market order using CCXT
            order = await asyncio.to_thread(
                self.ccxt_client.create_market_order,
                symbol=symbol,
                side=side.lower(),
                amount=amount
            )
            
            logger.info(f"Market order created: {order.get('id')} - {side} {amount} {symbol}")
            return order
            
        except Exception as e:
            logger.error(f"Error creating market order: {e}")
            return None

    async def get_account_balance(self) -> Optional[Dict]:
        """Return a normalized futures balance dict."""
        # 1) Prefer signed REST: /fapi/v2/account (exact fields we need)
        try:
            acct = await self.get_account()  # uses _make_request(..., signed=True)
            return {
                # Binance futures canonical fields:
                "totalWalletBalance": float(acct.get("totalWalletBalance", 0.0)),
                "availableBalance": float(acct.get("availableBalance", 0.0)),
                "totalInitialMargin": float(acct.get("totalInitialMargin", 0.0)),
                "totalMaintMargin": float(acct.get("totalMaintMargin", 0.0)),
                # Friendly aliases (optional) for route normalizers that look for these
                "total": float(acct.get("totalWalletBalance", 0.0)),
                "available": float(acct.get("availableBalance", 0.0)),
                "initial_margin": float(acct.get("totalInitialMargin", 0.0)),
                "maintenance_margin": float(acct.get("totalMaintMargin", 0.0)),
            }
        except Exception as e_rest:
            logger.warning(f"REST account fallback failed, trying CCXT: {e_rest}")

        # 2) CCXT fallback with normalization of nested dicts
        try:
            if not self.ccxt_client:
                logger.error("CCXT client not initialized")
                return None
            bal = await asyncio.to_thread(self.ccxt_client.fetch_balance)

            def pick_num(d, key, *prefer):
                v = d.get(key)
                if isinstance(v, (int, float, str)) and v not in (None, ""):
                    try: return float(v)
                    except: pass
                if isinstance(v, dict):
                    for cur in (*prefer, "USDT", "USD"):
                        if cur in v and v[cur] is not None:
                            try: return float(v[cur])
                            except: pass
                    nums = [x for x in v.values() if isinstance(x, (int, float))]
                    if nums: return float(sum(nums))
                return 0.0

            total = pick_num(bal, "total")
            free  = pick_num(bal, "free")
            info  = bal.get("info", {}) if isinstance(bal, dict) else {}

            return {
                "totalWalletBalance": float(info.get("totalWalletBalance", total)),
                "availableBalance":  float(info.get("availableBalance", free)),
                "totalInitialMargin": float(info.get("totalInitialMargin", 0.0)),
                "totalMaintMargin":   float(info.get("totalMaintMargin", 0.0)),
                "total": float(info.get("totalWalletBalance", total)),
                "available": float(info.get("availableBalance", free)),
                "initial_margin": float(info.get("totalInitialMargin", 0.0)),
                "maintenance_margin": float(info.get("totalMaintMargin", 0.0)),
            }
        except Exception as e_ccxt:
            logger.error(f"Error getting account balance via CCXT: {e_ccxt}")
            return None
