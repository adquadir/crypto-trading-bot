import asyncio
import logging
import time
import os
import statistics
from typing import Dict, List, Optional, Set
from datetime import datetime
from dataclasses import dataclass
from collections import deque
from aiohttp import BasicAuth, ClientSession
from binance.client import Client
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

@dataclass
class ProxyMetrics:
    response_times: deque = deque(maxlen=100)
    error_count: int = 0
    last_error: Optional[datetime] = None
    last_success: Optional[datetime] = None
    total_requests: int = 0
    successful_requests: int = 0

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

        for port in self.failover_ports:
            self.proxy_metrics[port] = ProxyMetrics()
        self.current_port_index = 0
        logger.info(f"Proxy configuration initialized with host: {self.proxy_host}")

    def _init_client(self, api_key: str, api_secret: str):
        try:
            self.client = Client(
                api_key,
                api_secret,
                testnet=self.testnet,
                requests_params={"proxies": self.proxies}
            )
            logger.info("Binance client initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing Binance client: {e}")
            raise

    def _setup_websocket(self):
        self.ws_url = "wss://stream.binance.com:9443/ws"
        self.ws_connections = {}

    async def _health_check_loop(self):
        try:
            while not self._shutdown_event.is_set():
                await self._check_proxy_health()
                await asyncio.sleep(self.health_check_interval)
        except asyncio.CancelledError:
            logger.info("Health check loop cancelled")
        except Exception as e:
            logger.exception(f"Error in health check loop: {e}")

    async def _check_proxy_health(self):
        port = self.proxy_port
        metrics = self.proxy_metrics[port]
        try:
            start = time.time()
            async with self.session.get("https://api.binance.com/api/v3/ping", proxy=f"http://{self.proxy_host}:{port}", proxy_auth=self.proxy_auth) as response:
                if response.status == 200:
                    duration = time.time() - start
                    metrics.response_times.append(duration)
                    metrics.successful_requests += 1
                    metrics.last_success = datetime.now()
                else:
                    raise Exception(f"Bad response: {response.status}")
        except Exception as e:
            metrics.error_count += 1
            metrics.last_error = datetime.now()
            logger.warning(f"Health check failed for proxy port {port}: {e}")
        finally:
            metrics.total_requests += 1
