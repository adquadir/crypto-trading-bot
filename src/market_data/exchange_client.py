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
        scalping_mode: bool = False,
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
        self._stale_data_alerts = {}  # Track stale data alerts
        self._alert_threshold = 3  # Number of consecutive stale data occurrences before alert
        self.scalping_mode = scalping_mode
        self.base_url = "https://testnet.binance.vision/api" if testnet else "https://api.binance.com/api"
        self.ws_base_url = "wss://testnet.binance.vision/ws" if testnet else "wss://stream.binance.com:9443/ws"

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

        # Initialize WebSocket client
        self.ws_client = None
        self.ws_symbols = set()
        
        # Cache TTLs (in seconds)
        if scalping_mode:
            self.cache_ttls = {
                'ohlcv': 5,  # 5 seconds for scalping
                'orderbook': 2,  # 2 seconds for scalping
                'ticker': 2,  # 2 seconds for scalping
                'trades': 2,  # 2 seconds for scalping
                'open_interest': 5,  # 5 seconds for scalping
                'funding_rate': 60,  # 1 minute for scalping
                'volatility': 60  # 1 minute for scalping
            }
        else:
            self.cache_ttls = {
                'ohlcv': config.get('ohlcv_cache_ttl', 60),  # Default 1 minute
                'orderbook': config.get('orderbook_cache_ttl', 5),  # Default 5 seconds
                'ticker': config.get('ticker_cache_ttl', 5),  # Default 5 seconds
                'trades': config.get('trades_cache_ttl', 5),  # Default 5 seconds
                'open_interest': config.get('open_interest_cache_ttl', 60),  # Default 1 minute
                'funding_rate': config.get('funding_rate_cache_ttl', 300),  # Default 5 minutes
                'volatility': config.get('volatility_cache_ttl', 300)  # Default 5 minutes
            }

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
                f"{self.ws_base_url}/{symbol.lower()}@depth",
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
                    f"{self.base_url}/v3/ping",
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

    async def initialize(self, symbols):
        """Initialize the exchange client with a set of symbols."""
        self.symbols = set(symbols)
        self.logger.info(f"Initialized ExchangeClient with {len(self.symbols)} symbols")
        
        # Initialize cache for each symbol
        for symbol in self.symbols:
            self.cache[symbol] = {
                'ohlcv': {},
                'orderbook': {},
                'ticker': {},
                'trades': {},
                'open_interest': {},
                'funding_rate': {},
                'volatility': {}
            }
        
        # Start background tasks
        asyncio.create_task(self._update_funding_rates())
        asyncio.create_task(self._update_volatility())
        
        return True

    async def _update_funding_rates(self):
        """Background task to update funding rates."""
        while True:
            try:
                for symbol in self.symbols:
                    funding_rate = await self.get_funding_rate(symbol)
                    if funding_rate:
                        self.cache[symbol]['funding_rate'] = {
                            'value': funding_rate,
                            'timestamp': time.time()
                        }
                await asyncio.sleep(self.cache_ttls['funding_rate'])
            except Exception as e:
                self.logger.error(f"Error updating funding rates: {str(e)}")
                await asyncio.sleep(5)

    async def _update_volatility(self):
        """Background task to update volatility metrics."""
        while True:
            try:
                for symbol in self.symbols:
                    volatility = await self.calculate_volatility(symbol)
                    if volatility:
                        self.cache[symbol]['volatility'] = {
                            'value': volatility,
                            'timestamp': time.time()
                        }
                await asyncio.sleep(self.cache_ttls['volatility'])
            except Exception as e:
                self.logger.error(f"Error updating volatility: {str(e)}")
                await asyncio.sleep(5)

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

    async def initialize(self, symbols: List[str]):
        """Initialize the exchange client with WebSocket streaming."""
        try:
            # Initialize WebSocket client
            self.ws_client = MarketDataWebSocket(
                self,
                symbols,
                cache_ttl=min(self.cache_ttls.values())  # Use smallest TTL
            )
            
            # Register callbacks
            self.ws_client.register_callback('kline', self._handle_kline_update)
            self.ws_client.register_callback('trade', self._handle_trade_update)
            self.ws_client.register_callback('depth', self._handle_depth_update)
            
            # Start WebSocket client
            asyncio.create_task(self.ws_client.start())
            logger.info("WebSocket client initialized")
            
        except Exception as e:
            logger.error(f"Error initializing exchange client: {e}")
            raise

    async def _handle_kline_update(self, symbol: str, data: Dict):
        """Handle WebSocket kline updates."""
        try:
            cache_key = f"{symbol}_ohlcv"
            self.cache[symbol]['ohlcv'] = data
            self.cache_timestamps[cache_key] = time.time()
            logger.debug(f"Updated OHLCV cache for {symbol}")
        except Exception as e:
            logger.error(f"Error handling kline update: {e}")

    async def _handle_trade_update(self, symbol: str, data: Dict):
        """Handle WebSocket trade updates."""
        try:
            cache_key = f"{symbol}_ticker"
            self.cache[symbol]['ticker'] = data
            self.cache_timestamps[cache_key] = time.time()
            logger.debug(f"Updated ticker cache for {symbol}")
        except Exception as e:
            logger.error(f"Error handling trade update: {e}")

    async def _handle_depth_update(self, symbol: str, data: Dict):
        """Handle WebSocket order book updates."""
        try:
            cache_key = f"{symbol}_orderbook"
            self.cache[symbol]['orderbook'] = data
            self.cache_timestamps[cache_key] = time.time()
            logger.debug(f"Updated orderbook cache for {symbol}")
        except Exception as e:
            logger.error(f"Error handling depth update: {e}")

    def _get_cache_ttl(self, data_type: str, is_scalping: bool = False) -> float:
        """Get the appropriate cache TTL based on data type and trading mode."""
        try:
            if is_scalping:
                ttl = self.cache_ttls.get(data_type, self.cache_ttls['ohlcv'])
            else:
                ttl = self.cache_ttls[data_type]
                
            # Adjust TTL based on market volatility
            if data_type in ['orderbook', 'ticker']:
                volatility = self._get_market_volatility()
                if volatility > 0.02:  # High volatility
                    ttl *= 0.5  # Reduce TTL by half
                elif volatility < 0.005:  # Low volatility
                    ttl *= 1.5  # Increase TTL by 50%
                    
            return ttl
            
        except Exception as e:
            logger.error(f"Error getting cache TTL: {e}")
            return self.cache_ttls[data_type]  # Return default TTL on error
            
    def _get_market_volatility(self) -> float:
        """Calculate current market volatility."""
        try:
            if not hasattr(self, '_volatility_cache'):
                self._volatility_cache = {}
                self._volatility_timestamp = 0
                
            # Update volatility cache every 5 minutes
            current_time = time.time()
            if current_time - self._volatility_timestamp > 300:
                self._volatility_cache = {}
                self._volatility_timestamp = current_time
                
            # Calculate average volatility across tracked symbols
            volatilities = []
            for symbol in self.symbols:
                if symbol in self._volatility_cache:
                    volatilities.append(self._volatility_cache[symbol])
                else:
                    # Calculate volatility from recent price data
                    klines = self.cache[symbol]['ohlcv']
                    if klines and len(klines) >= 20:
                        closes = [float(k['close']) for k in klines[-20:]]
                        returns = np.diff(closes) / closes[:-1]
                        vol = np.std(returns) * np.sqrt(24 * 60)  # Annualized
                        self._volatility_cache[symbol] = vol
                        volatilities.append(vol)
                        
            return np.mean(volatilities) if volatilities else 0.01  # Default to 1% if no data
            
        except Exception as e:
            logger.error(f"Error calculating market volatility: {e}")
            return 0.01  # Default to 1% on error
            
    def _validate_data_quality(self, data: Any, data_type: str) -> bool:
        """Validate data quality based on type."""
        try:
            if data_type == 'orderbook':
                if not isinstance(data, dict) or 'bids' not in data or 'asks' not in data:
                    return False
                if not data['bids'] or not data['asks']:
                    return False
                # Check spread
                best_bid = float(data['bids'][0][0])
                best_ask = float(data['asks'][0][0])
                spread = (best_ask - best_bid) / best_bid
                if spread > 0.01:  # 1% spread threshold
                    return False
                    
            elif data_type == 'ticker':
                if not isinstance(data, dict) or 'lastPrice' not in data:
                    return False
                # Check price change sanity
                if 'priceChangePercent' in data:
                    change = abs(float(data['priceChangePercent']))
                    if change > 100:  # 100% change threshold
                        return False
                        
            elif data_type == 'ohlcv':
                if not isinstance(data, list) or len(data) < 2:
                    return False
                # Check for gaps
                for i in range(1, len(data)):
                    if data[i][0] - data[i-1][0] > 60000:  # 1 minute gap
                        return False
                        
            return True
            
        except Exception as e:
            logger.error(f"Error validating data quality: {e}")
            return False
            
    def _check_data_consistency(self, data: Any, data_type: str) -> bool:
        """Check data consistency based on type."""
        try:
            if data_type == 'orderbook':
                # Check bid/ask ordering
                bids = [float(bid[0]) for bid in data['bids']]
                asks = [float(ask[0]) for ask in data['asks']]
                if not all(bids[i] >= bids[i+1] for i in range(len(bids)-1)):
                    return False
                if not all(asks[i] <= asks[i+1] for i in range(len(asks)-1)):
                    return False
                    
            elif data_type == 'ticker':
                # Check price consistency
                if 'lastPrice' in data and 'highPrice' in data and 'lowPrice' in data:
                    last = float(data['lastPrice'])
                    high = float(data['highPrice'])
                    low = float(data['lowPrice'])
                    if not (low <= last <= high):
                        return False
                        
            elif data_type == 'ohlcv':
                # Check OHLC consistency
                for candle in data:
                    if not (candle[3] <= candle[1] and candle[4] >= candle[2]):  # High >= Open/Close >= Low
                        return False
                        
            return True
            
        except Exception as e:
            logger.error(f"Error checking data consistency: {e}")
            return False

    async def get_ohlcv(self, symbol: str, timeframe: str = '1m', is_scalping: bool = False) -> Optional[Dict]:
        """Get OHLCV data with WebSocket fallback."""
        cache_key = f"{symbol}_ohlcv"
        
        # Check WebSocket cache first
        if self.ws_client:
            ws_data = self.ws_client.get_cached_data(symbol, 'kline')
            if ws_data and self._is_cache_valid(cache_key, 'ohlcv', is_scalping):
                return ws_data
        
        # Fallback to REST API if needed
        try:
            # Implement REST API call here
            data = await self._fetch_ohlcv_rest(symbol, timeframe)
            if data:
                self.cache[symbol]['ohlcv'] = data
                self.cache_timestamps[cache_key] = time.time()
            return data
        except Exception as e:
            logger.error(f"Error fetching OHLCV data: {e}")
            return None

    async def get_ticker(self, symbol: str, is_scalping: bool = False) -> Optional[Dict]:
        """Get ticker data with WebSocket fallback."""
        cache_key = f"{symbol}_ticker"
        
        # Check WebSocket cache first
        if self.ws_client:
            ws_data = self.ws_client.get_cached_data(symbol, 'trade')
            if ws_data and self._is_cache_valid(cache_key, 'ticker', is_scalping):
                return ws_data
        
        # Fallback to REST API if needed
        try:
            # Implement REST API call here
            data = await self._fetch_ticker_rest(symbol)
            if data:
                self.cache[symbol]['ticker'] = data
                self.cache_timestamps[cache_key] = time.time()
            return data
        except Exception as e:
            logger.error(f"Error fetching ticker data: {e}")
            return None

    async def get_orderbook(self, symbol: str, is_scalping: bool = False) -> Optional[Dict]:
        """Get order book data with WebSocket fallback."""
        cache_key = f"{symbol}_orderbook"
        
        # Check WebSocket cache first
        if self.ws_client:
            ws_data = self.ws_client.get_cached_data(symbol, 'depth')
            if ws_data and self._is_cache_valid(cache_key, 'orderbook', is_scalping):
                return ws_data
        
        # Fallback to REST API if needed
        try:
            # Implement REST API call here
            data = await self._fetch_orderbook_rest(symbol)
            if data:
                self.cache[symbol]['orderbook'] = data
                self.cache_timestamps[cache_key] = time.time()
            return data
        except Exception as e:
            logger.error(f"Error fetching orderbook data: {e}")
            return None

    def get_data_freshness(self, symbol: str, data_type: str) -> float:
        """Get the age of the most recent data in seconds."""
        if self.ws_client:
            return self.ws_client.get_data_freshness(symbol)
            
        cache_key = f"{symbol}_{data_type}"
        if cache_key in self.cache_timestamps:
            return time.time() - self.cache_timestamps[cache_key]
        return float('inf')

    async def stop(self):
        """Stop the exchange client and WebSocket connection."""
        if self.ws_client:
            await self.ws_client.stop()
        logger.info("Exchange client stopped")

    def _check_stale_data(self, symbol: str, data_type: str, age: float) -> None:
        """Check for stale data and trigger alerts if necessary."""
        try:
            key = f"{symbol}_{data_type}"
            if age > self.cache_ttls[data_type]:
                if key not in self._stale_data_alerts:
                    self._stale_data_alerts[key] = {
                        'count': 1,
                        'last_alert': time.time(),
                        'max_age': age
                    }
                else:
                    self._stale_data_alerts[key]['count'] += 1
                    self._stale_data_alerts[key]['max_age'] = max(age, self._stale_data_alerts[key]['max_age'])
                    
                # Check if we should trigger an alert
                if self._stale_data_alerts[key]['count'] >= self._alert_threshold:
                    # Only alert if we haven't alerted in the last 5 minutes
                    if time.time() - self._stale_data_alerts[key]['last_alert'] > 300:
                        logger.warning(
                            f"Persistent stale data detected for {symbol} {data_type}: "
                            f"{self._stale_data_alerts[key]['count']} occurrences, "
                            f"max age {self._stale_data_alerts[key]['max_age']:.1f}s"
                        )
                        self._stale_data_alerts[key]['last_alert'] = time.time()
            else:
                # Reset counter if data is fresh
                if key in self._stale_data_alerts:
                    del self._stale_data_alerts[key]
                    
        except Exception as e:
            logger.error(f"Error checking stale data: {e}")
            
    def _is_cache_valid(self, cache_key: str, data_type: str, is_scalping: bool = False) -> bool:
        """Check if cached data is still valid with enhanced validation."""
        try:
            if cache_key not in self.cache or cache_key not in self.cache_timestamps:
                return False
                
            ttl = self._get_cache_ttl(data_type, is_scalping)
            age = time.time() - self.cache_timestamps[cache_key]
            
            # Check for stale data and trigger alerts
            symbol = cache_key.split('_')[0]
            self._check_stale_data(symbol, data_type, age)
            
            # Check data quality
            data = self.cache[symbol][data_type]
            if not self._validate_data_quality(data, data_type):
                logger.warning(f"Poor data quality for {cache_key}")
                return False
                
            # Check for stale data
            if age > ttl:
                logger.warning(f"Cache expired for {cache_key}: {age:.2f}s old (TTL: {ttl}s)")
                return False
                
            # Check for data consistency
            if not self._check_data_consistency(data, data_type):
                logger.warning(f"Inconsistent data for {cache_key}")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error validating cache: {e}")
            return False