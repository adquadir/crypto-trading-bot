from typing import Dict, List, Optional, Set, Tuple
import asyncio
import logging
from datetime import datetime, timedelta
import aiohttp
from aiohttp import BasicAuth
from binance.client import Client
from binance.exceptions import BinanceAPIException
from binance.streams import BinanceSocketManager
import time
from functools import wraps
import os
from dotenv import load_dotenv
import statistics
from dataclasses import dataclass
from collections import deque

logger = logging.getLogger(__name__)

@dataclass
class ProxyMetrics:
    """Store metrics for proxy performance."""
    response_times: deque = deque(maxlen=100)
    error_count: int = 0
    last_error: Optional[datetime] = None
    last_success: Optional[datetime] = None
    total_requests: int = 0
    successful_requests: int = 0

def rate_limit(max_calls: int, period: float):
    """Rate limiting decorator."""
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
        proxy_config: Optional[Dict[str, str]] = None
    ):
        self.symbols = symbol_set or {'BTCUSDT'}
        self.testnet = testnet
        self.proxy_metrics = {}
        self.health_check_interval = 60
        self.rotation_threshold = 0.8
        self._shutdown_event = asyncio.Event()
        self.session = None
        self.health_check_task = None

        self.proxy_list = proxy_list or ['10001', '10002', '10003']
        self.failover_ports = failover_ports or ['10001', '10002', '10003']
        self.proxy_config = proxy_config or {
            'host': os.getenv('PROXY_HOST', 'isp.decodo.com'),
            'port': os.getenv('PROXY_PORT', '10001'),
            'user': os.getenv('PROXY_USER', 'sp6qilmhb3'),
            'pass': os.getenv('PROXY_PASS', 'y2ok7Y3FEygM~rs7de')
        }

        self._setup_proxy()
        self._init_client(api_key, api_secret)
        self._setup_websocket()
        self.market_data = {}
        self.health_check_task = asyncio.create_task(self._health_check_loop())

    def _setup_proxy(self):
        self.proxy_host = self.proxy_config['host']
        self.proxy_port = self.proxy_config['port']
        self.proxy_user = self.proxy_config['user']
        self.proxy_pass = self.proxy_config['pass']

        self.proxy_auth = BasicAuth(self.proxy_user, self.proxy_pass)
        proxy_auth = f"{self.proxy_user}:{self.proxy_pass}@{self.proxy_host}:{self.proxy_port}"
        self.proxies = {
            "http": f"http://{proxy_auth}",
            "https": f"http://{proxy_auth}"
        }

        self.current_port_index = 0
        for port in self.failover_ports:
            self.proxy_metrics[port] = ProxyMetrics()

        logger.info(f"Proxy configuration initialized with host: {self.proxy_host}")

    # Rest of the file remains unchanged
