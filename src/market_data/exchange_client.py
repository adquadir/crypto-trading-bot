# File: src/market_data/exchange_client.py
from typing import Dict, List, Optional, Set, Tuple
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
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        symbol_set: Optional[Set[str]] = None,
        testnet: bool = False,
        proxy_list: Optional[List[str]] = None,
        failover_ports: Optional[List[str]] = None,
        proxy_config: Optional[Dict[str, str]] = None,
    ):
        self.symbols = symbol_set or {'BTCUSDT'}
        self.testnet = testnet
        self.proxy_metrics = {}
        self.rotation_threshold = 0.8
        self.health_check_interval = 60
        self._shutdown_event = asyncio.Event()
        self.session = None
        self.health_check_task = None
        self.ws_connections = {}
        self.cache = CacheManager()

        # Load proxy configuration from environment variables
        self.proxy_list = proxy_list or os.getenv('PROXY_PORTS', '10001,10002,10003').split(',')
        self.failover_ports = failover_ports or os.getenv('FAILOVER_PORTS', '10001,10002,10003').split(',')
        self.current_port_index = 0
        self.proxy_config = proxy_config or {
            "host": os.getenv('PROXY_HOST'),
            "port": os.getenv('PROXY_PORT'),
            "user": os.getenv('PROXY_USER'),
            "pass": os.getenv('PROXY_PASS')
        }

        # Validate proxy configuration
        if not all([self.proxy_config["host"], self.proxy_config["port"], 
                   self.proxy_config["user"], self.proxy_config["pass"]]):
            logger.warning("Incomplete proxy configuration. Some proxy settings are missing.")
            self.proxy_config = None
        else:
            self._setup_proxy()
            
        self._init_client(api_key, api_secret)

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
            # Check cache first
            cache_key = 'exchange_info'
            cached_data = self.cache.get(cache_key, max_age=3600)  # Cache for 1 hour
            if cached_data:
                logger.debug("Using cached exchange info")
                return cached_data

            logger.debug("Fetching exchange information")
            
            # Get exchange info from Binance
            exchange_info = await asyncio.to_thread(self.client.get_exchange_info)
            
            # Filter for perpetual futures only
            futures_symbols = [
                symbol for symbol in exchange_info['symbols']
                if symbol['status'] == 'TRADING' and
                symbol.get('contractType') == 'PERPETUAL'
            ]
            
            result = {
                'symbols': futures_symbols,
                'timezone': exchange_info.get('timezone', 'UTC'),
                'serverTime': exchange_info.get('serverTime', int(time.time() * 1000))
            }
            
            # Cache the result
            self.cache.set(cache_key, result, max_age=3600)
            
            logger.info(f"Found {len(futures_symbols)} active perpetual futures pairs")
            return result
            
        except BinanceAPIException as e:
            logger.error(f"Binance API error: {e}")
            # Try with different proxy
            self.client.proxies = {'http': self._get_next_proxy(), 'https': self._get_next_proxy()}
            exchange_info = await asyncio.to_thread(self.client.get_exchange_info)
            
            # Filter for perpetual futures only
            futures_symbols = [
                symbol for symbol in exchange_info['symbols']
                if symbol['status'] == 'TRADING' and
                symbol.get('contractType') == 'PERPETUAL'
            ]
            
            result = {
                'symbols': futures_symbols,
                'timezone': exchange_info.get('timezone', 'UTC'),
                'serverTime': exchange_info.get('serverTime', int(time.time() * 1000))
            }
            
            # Cache the result
            self.cache.set(cache_key, result, max_age=3600)
            
            logger.info(f"Found {len(futures_symbols)} active perpetual futures pairs")
            return result
        except Exception as e:
            logger.error(f"Unexpected error fetching exchange info: {str(e)}")
            return {'symbols': [], 'timezone': 'UTC', 'serverTime': int(time.time() * 1000)}

    @retry_with_backoff(max_retries=3)
    @rate_limit(limit=10, period=1.0)
    async def get_ticker_24h(self, symbol: str) -> Dict:
        """Fetch 24-hour ticker statistics for a symbol."""
        try:
            # Check cache first
            cache_key = f'ticker_24h_{symbol}'
            cached_data = self.cache.get(cache_key, max_age=60)  # Cache for 1 minute
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
            # Check cache first
            cache_key = f'orderbook_{symbol}_{limit}'
            cached_data = self.cache.get(cache_key, max_age=5)  # Cache for 5 seconds
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
            # Check cache first
            cache_key = f'open_interest_{symbol}'
            cached_data = self.cache.get(cache_key, max_age=60)  # Cache for 1 minute
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
            # Check cache first
            cache_key = f'historical_{symbol}_{interval}_{limit}'
            cached_data = self.cache.get(cache_key, max_age=60)  # Cache for 1 minute
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
        for symbol, ws in list(self.ws_connections.items()):
            try:
                await ws.close()
                del self.ws_connections[symbol]
                await self._setup_symbol_websocket(symbol)
            except Exception as e:
                logger.error(f"Error reinitializing websocket for {symbol}: {e}")

    async def _setup_symbol_websocket(self, symbol: str):
        """Setup websocket for a specific symbol."""
        try:
            ws = await self.session.ws_connect(
                f"wss://stream.binance.com:9443/ws/{symbol.lower()}@depth",
                proxy=f"http://{self.proxy_host}:{self.proxy_port}",
                proxy_auth=self.proxy_auth,
                timeout=aiohttp.ClientTimeout(total=10)
            )
            self.ws_connections[symbol] = ws
            logger.info(f"Websocket connected for {symbol}")
        except Exception as e:
            logger.error(f"Failed to setup websocket for {symbol}: {e}")

    async def _handle_connection_error(self):
        """Handle connection errors by rotating proxy."""
        logger.warning("Handling connection error - rotating proxy")
        await self._rotate_proxy()

    def _find_best_proxy(self) -> str:
        best_port = self.proxy_port
        best_score = float('-inf')
        for port, metrics in self.proxy_metrics.items():
            if metrics.total_requests < 10:
                continue
            error_rate = metrics.error_count / metrics.total_requests
            avg_resp = statistics.mean(metrics.response_times) if metrics.response_times else float('inf')
            score = -(error_rate + avg_resp)
            if score > best_score:
                best_score = score
                best_port = port
        return best_port

    async def _test_proxy_connection(self) -> bool:
        """Test if the current proxy is working by making a simple HTTP request."""
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    "https://api.binance.com/api/v3/ping",
                    proxy=f"http://{self.proxy_host}:{self.proxy_port}",
                    proxy_auth=self.proxy_auth
                ) as response:
                    return response.status == 200
        except Exception as e:
            logger.error(f"Proxy test failed: {e}")
            return False

    async def _check_proxy_health(self):
        start = time.time()
        success = await self._test_proxy_connection()
        duration = time.time() - start

        metrics = self.proxy_metrics[self.proxy_port]
        if success:
            metrics.response_times.append(duration)
            metrics.successful_requests += 1
            metrics.last_success = datetime.now()
            logger.debug(f"Proxy health check successful (response time: {duration:.2f}s)")
        else:
            metrics.error_count += 1
            metrics.last_error = datetime.now()
            logger.warning("Proxy health check failed")
        metrics.total_requests += 1

        if self._should_rotate_proxy():
            await self._rotate_proxy()

    async def _health_check_loop(self):
        while not self._shutdown_event.is_set():
            try:
                await self._check_proxy_health()
            except Exception as e:
                logger.error(f"Health check failed: {e}")
            await asyncio.sleep(self.health_check_interval)

    async def initialize(self):
        """Initialize the exchange client and verify API keys."""
        try:
            logger.info("Initializing exchange client...")
            
            # Test API key validity
            try:
                account_info = self.client.get_account()
                if 'balances' not in account_info:
                    raise ValueError("Invalid API response - check key permissions")
                logger.info("API keys validated successfully")
                logger.debug(f"Account permissions: {account_info.get('permissions', 'N/A')}")
            except BinanceAPIException as e:
                logger.error(f"API Key Error: {e.status_code} - {e.message}")
                if e.status_code == 401:
                    logger.error("Invalid API keys - please check your .env file")
                raise
            
            self.session = aiohttp.ClientSession()
            self.health_check_task = asyncio.create_task(self._health_check_loop())
            logger.info("Exchange client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize exchange client: {str(e)}")
            raise
            
    async def close(self):
        """Clean up resources."""
        self._shutdown_event.set()
        if self.health_check_task:
            self.health_check_task.cancel()
            try:
                await self.health_check_task
            except asyncio.CancelledError:
                pass
        if self.session:
            await self.session.close()
        for symbol, ws in self.ws_connections.items():
            try:
                await ws.close()
                logger.debug(f"Closed websocket for {symbol}")
            except Exception as e:
                logger.error(f"Error closing websocket for {symbol}: {e}")
        logger.info("Exchange client shutdown complete")

    def _get_next_proxy(self) -> str:
        """Get next proxy in rotation."""
        proxy = self.proxy_list[self.current_port_index]
        self.current_port_index = (self.current_port_index + 1) % len(self.proxy_list)
        return proxy

    @retry_with_backoff(max_retries=3)
    @rate_limit(limit=10, period=1.0)
    async def get_market_data(self, symbol: str) -> Dict:
        """Fetch comprehensive market data for a symbol."""
        try:
            # Get OHLCV data
            ohlcv = await self.get_historical_data(symbol, interval="1m", limit=200)
            
            # Get funding rate
            funding_rate = await self.get_funding_rate(symbol)
            
            # Get 24h statistics
            ticker_24h = await self.get_ticker_24h(symbol)
            
            # Get order book
            orderbook = await self.get_orderbook(symbol, limit=10)
            
            # Calculate spread from orderbook
            spread = 0.0
            if orderbook['bids'] and orderbook['asks']:
                best_bid = float(orderbook['bids'][0][0])
                best_ask = float(orderbook['asks'][0][0])
                spread = (best_ask - best_bid) / best_bid
            
            # Calculate liquidity from orderbook
            liquidity = 0.0
            if orderbook['bids'] and orderbook['asks']:
                bid_liquidity = sum(float(bid[0]) * float(bid[1]) for bid in orderbook['bids'][:10])
                ask_liquidity = sum(float(ask[0]) * float(ask[1]) for ask in orderbook['asks'][:10])
                liquidity = (bid_liquidity + ask_liquidity) / 2
            
            # Get open interest
            open_interest = await self.get_open_interest(symbol)
            
            # Calculate volatility from OHLCV data
            volatility = 0.0
            if ohlcv:
                closes = [float(candle['close']) for candle in ohlcv]
                returns = np.diff(closes) / closes[:-1]
                volatility = np.std(returns) * np.sqrt(24 * 60)  # Annualized volatility
            
            return {
                'symbol': symbol,
                'ohlcv': ohlcv,
                'funding_rate': funding_rate,
                'volume_24h': float(ticker_24h.get('volume', 0)),
                'price_change_24h': float(ticker_24h.get('priceChangePercent', 0)),
                'orderbook': orderbook,
                'spread': spread,
                'liquidity': liquidity,
                'open_interest': open_interest,
                'volatility': volatility,
                'last_price': float(ticker_24h.get('lastPrice', 0)),
                'high_24h': float(ticker_24h.get('highPrice', 0)),
                'low_24h': float(ticker_24h.get('lowPrice', 0)),
                'quote_volume': float(ticker_24h.get('quoteVolume', 0))
            }
            
        except Exception as e:
            logger.error(f"Error fetching market data for {symbol}: {e}")
            return {}