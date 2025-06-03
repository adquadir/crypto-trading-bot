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
from dataclasses import dataclass
from collections import deque

logger = logging.getLogger(__name__)

@dataclass
class ProxyMetrics:
    response_times: deque = deque(maxlen=100)
    error_count: int = 0
    last_error: Optional[datetime] = None
    last_success: Optional[datetime] = None
    total_requests: int = 0
    successful_requests: int = 0

def rate_limit(max_calls: int, period: float):
    min_interval = period / max_calls
    last_reset = time.time()
    calls = 0

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            nonlocal last_reset, calls
            current_time = time.time()
            if current_time - last_reset >= period:
                calls = 0
                last_reset = current_time
            if calls >= max_calls:
                sleep_time = min_interval - (current_time - last_reset)
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                calls = 0
                last_reset = time.time()
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

        self.proxy_list = proxy_list or ['10001', '10002', '10003']
        self.failover_ports = failover_ports or ['10001', '10002', '10003']
        self.current_port_index = 0
        self.proxy_config = proxy_config or {
            "host": os.getenv('PROXY_HOST', 'isp.decodo.com'),
            "port": os.getenv('PROXY_PORT', '10001'),
            "user": os.getenv('PROXY_USER', 'sp6qilmhb3'),
            "pass": os.getenv('PROXY_PASS', 'y2ok7Y3FEygM~rs7de')
        }

        self._setup_proxy()
        self._init_client(api_key, api_secret)

    def _setup_proxy(self):
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

    @rate_limit(max_calls=10, period=1.0)
    async def get_historical_data(self, symbol: str, interval: str, limit: int) -> List[Dict]:
        """Fetch historical market data (OHLCV) from Binance."""
        try:
            logger.debug(f"Fetching {limit} {interval} candles for {symbol}")
            
            klines = self.client.get_klines(
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
            
            logger.debug(f"Retrieved {len(formatted_data)} valid data points for {symbol}")
            return formatted_data
            
        except BinanceAPIException as e:
            logger.error(f"Binance API error for {symbol}: {e.status_code} - {e.message}")
            await self._handle_connection_error()
            return []
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