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
from .websocket_client import MarketDataWebSocket
from .config import config
import ccxt

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
    def __init__(self, cache_dir: str = "cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.memory_cache: Dict[str, CacheEntry] = {}
        
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
        entry = CacheEntry(data=data, timestamp=datetime.now(), expires_at=expires_at)
        
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
    def __init__(self, config: Dict[str, Any]):
        """Initialize the exchange client."""
        self.config = config
        self.api_key = config['api_key']
        self.api_secret = config['api_secret']
        self.base_url = config['base_url']
        self.ws_url = config['ws_url']
        
        # Proxy configuration
        self.proxy = None
        if config.get('proxy'):
            proxy_config = config['proxy']
            self.proxy = f"http://{proxy_config['host']}:{proxy_config['port']}"
            if 'username' in proxy_config and 'password' in proxy_config:
                self.proxy_auth = aiohttp.BasicAuth(
                    proxy_config['username'],
                    proxy_config['password']
                )
        
        self.session = None
        self.ws_clients = {}
        self.running = False
        self.health_check_task = None
        self.funding_rates_task = None
        self.cache = CacheManager()
        self.cache_timestamps = {}
        self.symbols = config.get('symbols', ['BTCUSDT'])
        self.logger = logging.getLogger(__name__)
        self.symbol_discovery = None  # Initialize as None, will be set up when needed
        self.testnet = config.get('testnet', False)
        
        # Initialize WebSocket-related attributes
        self.ws_subscriptions = {}
        self.ws_last_message = {}
        self._stale_data_alerts = {}
        self._alert_threshold = 3
        self.scalping_mode = config.get('scalping_mode', False)
        
        # Initialize proxy rotation
        self.proxy_metrics = {}
        self.rotation_threshold = 0.8
        self.health_check_interval = 60
        self._shutdown_event = asyncio.Event()
        
        # Load proxy configuration
        self.proxy_list = config.get('proxy_ports', os.getenv('PROXY_LIST', '10001,10002,10003').split(','))
        self.failover_ports = config.get('failover_ports', os.getenv('FAILOVER_PORTS', '10001,10002,10003').split(','))
        self.current_port_index = 0
        
        # Initialize client
        self._init_client(self.api_key, self.api_secret)
        
        # Cache TTLs (in seconds)
        self.cache_ttls = {
            'ohlcv': 5 if self.scalping_mode else 300,  # 5s or 5min
            'orderbook': 2 if self.scalping_mode else 60,  # 2s or 1min
            'ticker': 2 if self.scalping_mode else 60,  # 2s or 1min
            'trades': 2 if self.scalping_mode else 60,  # 2s or 1min
            'open_interest': 5 if self.scalping_mode else 300,  # 5s or 5min
            'funding_rate': 300 if self.scalping_mode else 3600,  # 5min or 1h
            'volatility': 300 if self.scalping_mode else 3600  # 5min or 1h
        }
        
        # Initialize data structures
        self.open_interest_history = {}
        self.history_length = 24

    def _setup_proxy(self):
        """Setup proxy configuration."""
        if not self.proxy_config:
            logger.warning("No proxy configuration available")
            return

        host = self.proxy_config["host"]
        port = self.proxy_config["port"]
        user = self.proxy_config["user"]
        passwd = self.proxy_config["pass"]
        
        self.proxy_host = host
        self.proxy_port = port
        self.proxy_user = user
        self.proxy_pass = passwd
        self.proxy_auth = BasicAuth(user, passwd)
        self.proxies = {
            "http": f"http://{user}:{passwd}@{host}:{port}",
            "https": f"http://{user}:{passwd}@{host}:{port}"
        }

        for port in self.failover_ports:
            self.proxy_metrics[port] = ProxyMetrics()

    def _init_client(self, api_key: str, api_secret: str):
        self.client = Client(api_key, api_secret, testnet=self.testnet, requests_params={"proxies": self.proxies})

    async def test_proxy_connection(self):
        """Test and log proxy connection details."""
        logger.info("=== Proxy Connection Test ===")
        logger.info(f"Current proxy: {self.proxy_host}:{self.proxy_port}")
        
        # Test direct connection without proxy
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.binance.com/api/v3/ping") as resp:
                    logger.info("Direct connection test (no proxy): SUCCESS")
        except Exception as e:
            logger.warning(f"Direct connection failed: {str(e)}")
        
        # Test proxy connection
        try:
            success = await self._test_proxy_connection()
            if success:
                logger.info("Proxy connection test: SUCCESS")
            else:
                logger.error("Proxy connection test: FAILED")
        except Exception as e:
            logger.error(f"Proxy test error: {str(e)}")
        
        logger.info(f"Available proxy ports: {self.proxy_list}")
        logger.info("=== End Proxy Test ===")

    @retry_with_backoff(max_retries=3)
    @rate_limit(limit=10, period=1.0)
    async def get_exchange_info(self) -> Dict:
        """Fetch exchange information including all available trading pairs."""
        try:
            # --- Temporarily disable cache check to force fresh fetch ---
            # cache_key = 'exchange_info'
            # cached_data = self.cache.get(cache_key, max_age=3600)  # Cache for 1 hour
            # if cached_data:
            #     logger.debug("Using cached exchange info from memory/disk.")
            #     if 'symbols' in cached_data:
            #         cached_perpetual_symbols = [s for s in cached_data['symbols'] if s.get('contractType') == 'PERPETUAL' and s.get('status') == 'TRADING']
            #         logger.debug(f"Cached data contains {len(cached_perpetual_symbols)} TRADING perpetual symbols.")
            #     return cached_data

            logger.debug("Cache check skipped. Fetching exchange info from exchange...")
            # Fetch from exchange
            # Use the Binance Client instance which is configured with the proxy
            exchange_info = await asyncio.to_thread(self.client.futures_exchange_info) # Ensure futures endpoint is used

            logger.debug("Successfully fetched exchange info from exchange.")
            # Log the number of perpetual symbols found in the fetched data
            if 'symbols' in exchange_info:
                fetched_perpetual_symbols = [s for s in exchange_info['symbols'] if s.get('contractType') == 'PERPETUAL' and s.get('status') == 'TRADING']
                logger.debug(f"Fetched data contains {len(fetched_perpetual_symbols)} TRADING perpetual symbols.")

            # Cache the fetched data (still cache, but don't read from it for this call)
            # self.cache.set(cache_key, exchange_info, max_age=3600)

            return exchange_info
        except Exception as e:
            logger.error(f"Error fetching exchange info: {e}")
            raise # Re-raise the exception to be caught by retry decorator or calling function

    @retry_with_backoff(max_retries=3)
    @rate_limit(limit=10, period=1.0)
    async def get_ticker_24h(self, symbol: str) -> Dict:
        """Fetch 24-hour ticker statistics for a symbol."""
        try:
            cache_key = f"ticker_24h_{symbol}"
            max_age = self._get_cache_ttl('ticker', self.scalping_mode)
            
            # Check cache first
            cached_data = self.cache.get(cache_key, max_age=max_age)
            if cached_data:
                logger.debug(f"Using cached 24h ticker for {symbol}")
                return cached_data

            logger.debug(f"Fetching 24h ticker for {symbol}")
            
            # Get 24h ticker from Binance
            ticker = await asyncio.to_thread(self.client.futures_ticker, symbol=symbol)
            
            if not ticker:
                logger.warning(f"No ticker data for {symbol}")
                return {}
                
            result = {
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
            
            # Cache the result
            self.cache.set(cache_key, result, max_age=60)
            
            return result
            
        except BinanceAPIException as e:
            logger.error(f"Binance API error for {symbol}: {e}")
            # Try with different proxy
            self.client.proxies = {'http': self._get_next_proxy(), 'https': self._get_next_proxy()}
            ticker = await asyncio.to_thread(self.client.futures_ticker, symbol=symbol)
            
            if not ticker:
                logger.warning(f"No ticker data for {symbol}")
                return {}
                
            result = {
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
            
            # Cache the result
            self.cache.set(cache_key, result, max_age=60)
            
            return result
        except Exception as e:
            logger.error(f"Unexpected error fetching ticker for {symbol}: {str(e)}")
            return {}

    @retry_with_backoff(max_retries=3)
    @rate_limit(limit=10, period=1.0)
    async def get_orderbook(self, symbol: str, limit: int = 10) -> Dict:
        """Fetch order book data for a symbol."""
        try:
            cache_key = f"orderbook_{symbol}_{limit}"
            max_age = self._get_cache_ttl('orderbook', self.scalping_mode)
            
            # Check cache first
            cached_data = self.cache.get(cache_key, max_age=max_age)
            if cached_data:
                logger.debug(f"Using cached orderbook for {symbol}")
                return cached_data

            logger.debug(f"Fetching orderbook for {symbol} (limit: {limit})")
            
            # Get orderbook from Binance
            depth = await asyncio.to_thread(self.client.futures_order_book, symbol=symbol, limit=limit)
            
            if not depth:
                logger.warning(f"No orderbook data for {symbol}")
                return {'bids': [], 'asks': []}
                
            result = {
                'bids': [[float(price), float(qty)] for price, qty in depth['bids']],
                'asks': [[float(price), float(qty)] for price, qty in depth['asks']],
                'lastUpdateId': depth['lastUpdateId']
            }
            
            # Cache the result
            self.cache.set(cache_key, result, max_age=5)
            
            return result
            
        except BinanceAPIException as e:
            logger.error(f"Binance API error for {symbol}: {e}")
            # Try with different proxy
            self.client.proxies = {'http': self._get_next_proxy(), 'https': self._get_next_proxy()}
            depth = await asyncio.to_thread(self.client.futures_order_book, symbol=symbol, limit=limit)
            
            if not depth:
                logger.warning(f"No orderbook data for {symbol}")
                return {'bids': [], 'asks': []}
                
            result = {
                'bids': [[float(price), float(qty)] for price, qty in depth['bids']],
                'asks': [[float(price), float(qty)] for price, qty in depth['asks']],
                'lastUpdateId': depth['lastUpdateId']
            }
            
            # Cache the result
            self.cache.set(cache_key, result, max_age=5)
            
            return result
        except Exception as e:
            logger.error(f"Unexpected error fetching orderbook for {symbol}: {str(e)}")
            return {'bids': [], 'asks': []}

    @retry_with_backoff(max_retries=3)
    @rate_limit(limit=10, period=1.0)
    async def get_funding_rate(self, symbol: str) -> float:
        """Fetch current funding rate for a symbol."""
        try:
            # Check cache first
            cache_key = f'funding_rate_{symbol}'
            cached_data = self.cache.get(cache_key, max_age=300)  # Cache for 5 minutes
            if cached_data is not None:
                logger.debug(f"Using cached funding rate for {symbol}")
                return cached_data

            logger.debug(f"Fetching funding rate for {symbol}")
            
            # Get funding rate from Binance
            funding_rate = await asyncio.to_thread(self.client.futures_funding_rate, symbol=symbol)
            
            if not funding_rate:
                logger.warning(f"No funding rate data for {symbol}")
                return 0.0
                
            result = float(funding_rate[0]['fundingRate'])
            
            # Cache the result
            self.cache.set(cache_key, result, max_age=300)
            
            return result
            
        except BinanceAPIException as e:
            logger.error(f"Binance API error for {symbol}: {e}")
            # Try with different proxy
            self.client.proxies = {'http': self._get_next_proxy(), 'https': self._get_next_proxy()}
            funding_rate = await asyncio.to_thread(self.client.futures_funding_rate, symbol=symbol)
            
            if not funding_rate:
                logger.warning(f"No funding rate data for {symbol}")
                return 0.0
                
            result = float(funding_rate[0]['fundingRate'])
            
            # Cache the result
            self.cache.set(cache_key, result, max_age=300)
            
            return result
        except Exception as e:
            logger.error(f"Unexpected error fetching funding rate for {symbol}: {str(e)}")
            return 0.0

    @retry_with_backoff(max_retries=3)
    @rate_limit(limit=10, period=1.0)
    async def get_open_interest(self, symbol: str) -> float:
        """Fetch open interest for a symbol."""
        try:
            cache_key = f"open_interest_{symbol}"
            max_age = self._get_cache_ttl('open_interest', self.scalping_mode)
            
            # Check cache first
            cached_data = self.cache.get(cache_key, max_age=max_age)
            if cached_data is not None:
                logger.debug(f"Using cached open interest for {symbol}")
                return cached_data

            logger.debug(f"Fetching open interest for {symbol}")
            
            # Get open interest from Binance
            open_interest = await asyncio.to_thread(self.client.futures_open_interest, symbol=symbol)
            
            if not open_interest:
                logger.warning(f"No open interest data for {symbol}")
                return 0.0
                
            result = float(open_interest['openInterest'])
            
            # Cache the result
            self.cache.set(cache_key, result, max_age=60)
            
            return result
            
        except BinanceAPIException as e:
            logger.error(f"Binance API error for {symbol}: {e}")
            # Try with different proxy
            self.client.proxies = {'http': self._get_next_proxy(), 'https': self._get_next_proxy()}
            open_interest = await asyncio.to_thread(self.client.futures_open_interest, symbol=symbol)
            
            if not open_interest:
                logger.warning(f"No open interest data for {symbol}")
                return 0.0
                
            result = float(open_interest['openInterest'])
            
            # Cache the result
            self.cache.set(cache_key, result, max_age=60)
            
            return result
        except Exception as e:
            logger.error(f"Unexpected error fetching open interest for {symbol}: {str(e)}")
            return 0.0

    @retry_with_backoff(max_retries=3)
    @rate_limit(limit=10, period=1.0)
    async def get_historical_data(self, symbol: str, interval: str, limit: int) -> List[Dict]:
        """Fetch historical market data (OHLCV) from Binance."""
        try:
            cache_key = f"historical_{symbol}_{interval}_{limit}"
            max_age = self._get_cache_ttl('ohlcv', self.scalping_mode)
            
            # Check cache first
            cached_data = self.cache.get(cache_key, max_age=max_age)
            if cached_data:
                logger.debug(f"Using cached historical data for {symbol}")
                return cached_data

            logger.debug(f"Fetching {limit} {interval} candles for {symbol}")
            
            klines = await asyncio.to_thread(
                self.client.futures_klines,
                symbol=symbol,
                interval=interval,
                limit=limit
            )
            
            formatted_data = []
            for k in klines:
                try:
                    formatted_data.append({
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
                    })
                except (IndexError, ValueError) as e:
                    logger.warning(f"Malformed kline data: {k}. Error: {str(e)}")
                    continue
            
            if not formatted_data:
                logger.warning(f"No valid data points received for {symbol}")
                return []
            
            # Cache the result
            self.cache.set(cache_key, formatted_data, max_age=60)
            
            logger.debug(f"Retrieved {len(formatted_data)} valid data points for {symbol}")
            return formatted_data
            
        except BinanceAPIException as e:
            logger.error(f"Binance API error for {symbol}: {e}")
            # Try with different proxy
            self.client.proxies = {'http': self._get_next_proxy(), 'https': self._get_next_proxy()}
            klines = await asyncio.to_thread(
                self.client.futures_klines,
                symbol=symbol,
                interval=interval,
                limit=limit
            )
            
            formatted_data = []
            for k in klines:
                try:
                    formatted_data.append({
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
                    })
                except (IndexError, ValueError) as e:
                    logger.warning(f"Malformed kline data: {k}. Error: {str(e)}")
                    continue
            
            if not formatted_data:
                logger.warning(f"No valid data points received for {symbol}")
                return []
            
            # Cache the result
            self.cache.set(cache_key, formatted_data, max_age=60)
            
            logger.debug(f"Retrieved {len(formatted_data)} valid data points for {symbol}")
            return formatted_data
        except Exception as e:
            logger.error(f"Unexpected error fetching data for {symbol}: {str(e)}")
            return []
            
    def _should_rotate_proxy(self) -> bool:
        metrics = self.proxy_metrics[self.proxy_port]
        if metrics.total_requests < 10:
            return False
        error_rate = metrics.error_count / metrics.total_requests
        avg_response = statistics.mean(metrics.response_times) if metrics.response_times else float('inf')
        return error_rate > self.rotation_threshold or avg_response > 1.0

    async def _rotate_proxy(self):
        best_port = self._find_best_proxy()
        if best_port != self.proxy_port:
            logger.info(f"Rotating proxy from {self.proxy_port} to {best_port}")
            self.proxy_port = best_port
            self.proxy_config["port"] = best_port
            self._setup_proxy()
            self._init_client(
                os.getenv("BINANCE_API_KEY"),
                os.getenv("BINANCE_API_SECRET")
            )
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
            await ws_client.connect()
            
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

    async def _update_volatility_metrics(self) -> None:
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
        """Close all WebSocket connections."""
        for symbol, ws_client in self.ws_clients.items():
            if ws_client:
                await ws_client.close()
        logger.info("Exchange client shutdown complete")

    def _get_next_proxy(self) -> str:
        """Get next proxy in rotation."""
        proxy = self.proxy_list[self.current_port_index]
        self.current_port_index = (self.current_port_index + 1) % len(self.proxy_list)
        return proxy

    async def _handle_ws_message(self, message):
        try:
            event_type = message.get("e")
            symbol = message.get("s")

            if event_type == "kline":
                await self._handle_kline_update(symbol, message["k"])
            elif event_type == "depthUpdate":
                self.order_books[symbol] = message  # or parse bids/asks here
            elif event_type == "trade":
                self.last_trade_price[symbol] = float(message["p"])

            self.ws_last_message[symbol] = time.time()

        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")

    async def _handle_ws_error(self, error):
        """Handle WebSocket errors."""
        logger.error(f"WebSocket error: {error}")

    async def _handle_ws_close(self, close_status_code, close_msg):
        """Handle WebSocket close events."""
        logger.info(f"WebSocket closed with status {close_status_code}: {close_msg}")

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
            logger.error(f"Error getting data freshness for {symbol}: {str(e)}")
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
            logger.error(f"Error updating data freshness for {symbol} {data_type}: {str(e)}")
            
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
            klines = await self.get_klines(symbol)
            
            # Combine all data
            market_data = {
                'orderbook': orderbook,
                'ticker': ticker,
                'trades': trades,
                'klines': klines
            }
            
            return market_data
        except Exception as e:
            logger.error(f"Error getting market data for {symbol}: {e}")
            return {}

    async def get_all_symbols(self):
        # Replace this with actual logic to fetch symbols from the exchange
        return ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    async def initialize(self):
        """Initialize the exchange client."""
        try:
            # Initialize symbol discovery if needed
            if self.symbol_discovery is None:
                from src.market_data.symbol_discovery import SymbolDiscovery
                self.symbol_discovery = SymbolDiscovery(self.config)
                await self.symbol_discovery.start()
            
            # Update symbols from discovery if in dynamic mode
            if self.config.get('symbol_discovery_mode', 'static') == 'dynamic':
                self.symbols = await self.symbol_discovery.get_symbols()
            
            self.running = True
            self.logger.info(f"Initialized exchange client with {len(self.symbols)} symbols.")
            
            # Start background tasks
            self.health_check_task = asyncio.create_task(self._monitor_health())
            self.funding_rates_task = asyncio.create_task(self._monitor_funding_rates())
            
            return True
        except Exception as e:
            self.logger.error(f"Error initializing exchange client: {e}")
            return False

    async def shutdown(self):
        """Shutdown the exchange client."""
        try:
            self.running = False
            
            # Cancel background tasks
            if hasattr(self, 'health_check_task'):
                self.health_check_task.cancel()
            if hasattr(self, 'funding_rates_task'):
                self.funding_rates_task.cancel()
            
            # Close all WebSocket connections
            for symbol, ws_client in self.ws_clients.items():
                try:
                    await ws_client.close()
                except Exception as e:
                    logger.error(f"Error closing WebSocket for {symbol}: {e}")
            
            self.ws_clients.clear()
            logger.info("Exchange client shutdown complete")
        except Exception as e:
            logger.error(f"Error during exchange client shutdown: {e}")
            raise

    async def _handle_kline_update(self, symbol: str, kline_data: dict):
        """Handle kline update from WebSocket."""
        # Update the last trade price
        self.last_trade_price[symbol] = float(kline_data['k']['c'])
        logger.debug(f"Updated last trade price for {symbol}: {self.last_trade_price[symbol]}")

    async def _check_proxy_health(self):
        """Check the health of the current proxy."""
        try:
            proxy_url = f"http://{self.proxy_host}:{self.proxy_port}" if self.proxy_host and self.proxy_port else None
            async with aiohttp.ClientSession() as session:
                async with session.get('https://api.binance.com/api/v3/ping', proxy=proxy_url) as response:
                    return response.status == 200
        except Exception as e:
            logger.error(f"Error checking proxy health: {e}")
            return False

    async def _health_check_loop(self):
        """Monitor the health of the proxy and reconnect if necessary."""
        while self.running:
            if not await self._check_proxy_health():
                logger.warning("Proxy health check failed. Attempting to reconnect...")
                await self._handle_connection_error()
            await asyncio.sleep(60)  # Check every minute

    async def _handle_connection_error(self):
        """Handle connection errors by reconnecting."""
        logger.info("Handling connection error...")
        await self.close()
        await self.initialize()

    async def _find_best_proxy(self):
        """Find the best proxy based on latency."""
        # Placeholder for proxy selection logic
        return "http://example-proxy.com:8080"

    async def _test_proxy_connection(self) -> bool:
        """Test proxy connection."""
        if not self.proxy:
            return True
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    'https://api.binance.com/api/v3/ping',
                    proxy=self.proxy,
                    proxy_auth=self.proxy_auth,
                    timeout=10
                ) as response:
                    return response.status == 200
        except Exception as e:
            self.logger.error(f"Error testing proxy connection: {e}")
            return False

    def _get_cache_ttl(self, data_type: str, scalping_mode: bool = False) -> int:
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
            await ws_client.connect()
            
            # Start the WebSocket client in a background task
            asyncio.create_task(ws_client.start())
            
            # Store the client
            self.ws_clients[symbol] = ws_client
            logger.info(f"WebSocket client started for {symbol}")
        except Exception as e:
            logger.error(f"Error setting up WebSocket for {symbol}: {e}")
            raise