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
    last_error: Optional[datetime] = None
    last_success: Optional[datetime] = None
    total_requests: int = 0
    successful_requests: int = 0


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
                    if e.status_code in [429, 418]:  # Rate limit or IP ban
                        delay = base_delay * (2 ** attempt)
                        logger.warning(f"Rate limit hit, retrying in {delay}s")
                        await asyncio.sleep(delay)
                    else:
                        raise
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(f"Error in {func.__name__}, retrying in {delay}s: {e}")
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
        self.max_retries = 3
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
        if self.config.get('USE_PROXY', False):
            if self.proxy_host and self.proxy_port:
                self.proxy_url = f"http://{self.proxy_host}:{self.proxy_port}"
                if self.proxy_user and self.proxy_pass:
                    self.proxy_url = f"http://{self.proxy_user}:{self.proxy_pass}@{self.proxy_host}:{self.proxy_port}"
                logger.info(f"Proxy configured: {self.proxy_host}:{self.proxy_port}")
                logger.info(f"Full proxy URL: {self.proxy_url}")
        
        # API credentials
        self.api_key = os.getenv('BINANCE_API_KEY')
        self.api_secret = os.getenv('BINANCE_API_SECRET')
        
        # Initialize clients
        self.client = None
        self.futures_client = None
        self.exchange = None
        
        # Initialize WebSocket tracking
        self.ws_connections = {}
        self.ws_manager = None
        self.cache_manager = CacheManager()
        self.proxy_metrics = ProxyMetrics()
        
        self.logger = logging.getLogger(__name__)
        self.scalping_mode = self.config.get('scalping_mode', False)
        
        # Initialize proxy rotation
        self.proxy_metrics = {}
        self.rotation_threshold = 0.8
        self.health_check_interval = 60
        self._shutdown_event = asyncio.Event()

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

    async def _init_client(self):
        """Initialize the Binance client with proper configuration."""
        try:
            # Initialize Binance client
            self.client = Client(
                api_key=self.api_key,
                api_secret=self.api_secret,
                testnet=self.testnet
            )
            
            # Initialize futures client
            self.futures_client = Client(
                api_key=self.api_key,
                api_secret=self.api_secret,
                testnet=self.testnet
            )
            
            # Set up proxy if enabled
            if self.proxy_url:
                self.client.proxies = {
                    'http': self.proxy_url,
                    'https': self.proxy_url
                }
                self.futures_client.proxies = {
                    'http': self.proxy_url,
                    'https': self.proxy_url
                }
                logger.info(f"Proxy configured for Binance clients: {self.proxy_url}")
            
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
            
            # Initialize WebSocket connections
            symbols = self.config.get('symbols', ['BTCUSDT'])
            self.ws_manager = MarketDataWebSocket(self, symbols)
            await self.ws_manager.initialize()
            
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
        """Make an HTTP request to the exchange API."""
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
            
            async with aiohttp.ClientSession() as session:
                if method.upper() == 'GET':
                    async with session.get(url, params=params, headers=headers, proxy=proxy_url, timeout=10) as resp:
                        if resp.status != 200:
                            error_text = await resp.text()
                            logger.error(f"API request failed: {resp.status} {error_text}")
                            raise Exception(f"API request failed: {resp.status} {error_text}")
                        return await resp.json()
                elif method.upper() == 'POST':
                    async with session.post(url, json=params, headers=headers, proxy=proxy_url, timeout=10) as resp:
                        if resp.status != 200:
                            error_text = await resp.text()
                            logger.error(f"API request failed: {resp.status} {error_text}")
                            raise Exception(f"API request failed: {resp.status} {error_text}")
                        return await resp.json()
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                    
        except Exception as e:
            logger.error(f"Error making API request: {e}")
            raise

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
        """Get 24-hour ticker data for a symbol."""
        try:
            params = {'symbol': symbol}
            return await self._make_request('GET', '/fapi/v1/ticker/24hr', params)
        except Exception as e:
            logger.error(f"Error getting 24h ticker for {symbol}: {e}")
            raise

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

    @retry_with_backoff(max_retries=3)
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
            logger.error(f"Network error while fetching historical data: {e}")
            raise
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error while fetching historical data: {e}")
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
        metrics = self.proxy_metrics[self.proxy_port]
        if metrics.total_requests < 10:
            return False
        error_rate = metrics.error_count / metrics.total_requests
        avg_response = statistics.mean(
            metrics.response_times) if metrics.response_times else float('inf')
        return error_rate > self.rotation_threshold or avg_response > 1.0

    async def _find_best_proxy(self):
        """Find the best proxy port based on latency (placeholder: just rotate through the list)."""
        # Always return a port string from the proxy list
        if hasattr(self, 'proxy_list') and self.proxy_list:
            # Simple round-robin for now
            self.current_port_index = (
                self.current_port_index + 1) % len(self.proxy_list)
            return str(self.proxy_list[self.current_port_index])
        return str(os.getenv('PROXY_PORT', '10001'))

    async def _rotate_proxy(self):
        best_port = await self._find_best_proxy()
        if best_port != self.proxy_port:
            logger.info(f"Rotating proxy from {self.proxy_port} to {best_port}")
            self.proxy_port = best_port
            if not isinstance(self.proxy_port, str) or not self.proxy_port.isdigit():
                logger.error(f"Proxy port is not a valid string: {self.proxy_port}")
                raise ValueError(f"Proxy port is not a valid string: {self.proxy_port}")
            self.proxy_config["port"] = str(best_port)
            self._setup_proxy()
            self._init_client()
            await self._reinitialize_websockets()

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
            
            # Get recent trades
            trades = await self.get_recent_trades(symbol)
            
            # Get klines
            klines = await self.get_historical_data(symbol)
            
            # Combine all data
            market_data = {
                'orderbook': orderbook,
                'ticker': ticker,
                'trades': trades,
                'klines': klines.to_dict() if not klines.empty else {}
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
                'options': {
                    'defaultType': 'future',  # Use futures market
                    'adjustForTimeDifference': True,
                },
                'headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
            }
            if self.config.get('USE_PROXY', False):
                proxy_url = f"http://{self.proxy_host}:{self.proxy_port}"
                if self.proxy_user and self.proxy_pass:
                    proxy_url = f"http://{self.proxy_user}:{self.proxy_pass}@{self.proxy_host}:{self.proxy_port}"
                exchange_config['proxies'] = {
                    'http': proxy_url,
                    'https': proxy_url
                }
                exchange_config['proxy'] = proxy_url
                logger.info(f"Proxy configured for exchange: {self.proxy_host}:{self.proxy_port}")
                logger.info(f"Full proxy URL: {proxy_url}")
            logger.info(f"Initializing ccxt for private endpoints only: {exchange_config}")
            self.exchange = ccxt.binance(exchange_config)
            logger.info("Exchange client initialized for private endpoints only (no public ccxt calls)")
        except Exception as e:
            logger.error(f"Error initializing exchange: {e}")
            raise

    async def stop(self):
        """Stop the exchange client and WebSocket manager."""
        try:
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
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/api/v3/time",
                    proxy=proxy_url,
                    timeout=10
                ) as response:
                    if response.status == 200:
                        logger.info("Proxy health check passed")
                        return True
                    else:
                        logger.warning(f"Proxy health check failed: {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"Error checking proxy health: {e}")
            return False

    async def _health_check_loop(self):
        """Monitor the health of the proxy and reconnect if necessary."""
        while self.running:
            if not await self._check_proxy_health():
                logger.warning(
                    "Proxy health check failed. Attempting to reconnect...")
                await self._handle_connection_error()
            await asyncio.sleep(60)  # Check every minute

    async def _handle_connection_error(self):
        """Handle connection errors by reconnecting."""
        logger.info("Handling connection error...")
        await self.close()
        await self.initialize()

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
