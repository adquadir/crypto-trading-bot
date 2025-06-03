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
        self.market_data = {}

        self._setup_proxy()
        self._init_client(api_key, api_secret)

    def _setup_proxy(self):
        host = self.proxy_config["host"]
        port = self.proxy_config["port"]
        user = self.proxy_config["user"]
        passwd = self.proxy_config["pass"]
        self.proxy_host = host
        self.proxy_port = port
        self.proxy_auth = BasicAuth(user, passwd)
        self.proxies = {
            "http": f"http://{user}:{passwd}@{host}:{port}",
            "https": f"http://{user}:{passwd}@{host}:{port}"
        }

        for port in self.failover_ports:
            self.proxy_metrics[port] = ProxyMetrics()

    def _init_client(self, api_key: str, api_secret: str):
        self.client = Client(api_key, api_secret, testnet=self.testnet, requests_params={"proxies": self.proxies})

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
            self.proxy_port = best_port
            self.proxy_config["port"] = best_port
            self._setup_proxy()
            self._init_client(
                os.getenv("BINANCE_API_KEY"),
                os.getenv("BINANCE_API_SECRET")
            )

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
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://stream.binance.com:9443/ws",
                    proxy=f"http://{self.proxy_host}:{self.proxy_port}",
                    proxy_auth=self.proxy_auth,
                    timeout=10
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
        else:
            metrics.error_count += 1
            metrics.last_error = datetime.now()
        metrics.total_requests += 1

        if self._should_rotate_proxy():
            await self._rotate_proxy()

    async def _health_check_loop(self):
        while not self._shutdown_event.is_set():
            try:
                await self._check_proxy_health()
            except Exception as e:
                logger.error(f"Health check failed for proxy port {self.proxy_port}: {e}")
            await asyncio.sleep(self.health_check_interval)

    async def initialize(self):
        self.session = aiohttp.ClientSession()
        self.health_check_task = asyncio.create_task(self._health_check_loop())

    async def close(self):
        self._shutdown_event.set()
        if self.health_check_task:
            self.health_check_task.cancel()
            try:
                await self.health_check_task
            except asyncio.CancelledError:
                pass
        if self.session:
            await self.session.close()
        for ws in self.ws_connections.values():
            await ws.close()
