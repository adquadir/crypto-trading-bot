from typing import Dict, List, Optional, Set
import asyncio
import logging
from datetime import datetime
import aiohttp
from aiohttp import BasicAuth
from binance.client import Client
from binance.exceptions import BinanceAPIException
from binance.streams import BinanceSocketManager
import time
from functools import wraps
import os
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

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
        testnet: bool = False
    ):
        """Initialize the exchange client with proxy support."""
        self.symbols = symbol_set or {'BTCUSDT'}
        self.testnet = testnet
        self._setup_proxy()
        self._init_client(api_key, api_secret)
        self._setup_websocket()
        self.market_data = {}  # Initialize market data dictionary
        
    def _setup_proxy(self):
        """Set up proxy configuration."""
        # Load proxy settings from environment or use defaults
        self.proxy_host = os.getenv('PROXY_HOST', 'isp.decodo.com')
        self.proxy_port = os.getenv('PROXY_PORT', '10001')
        self.proxy_user = os.getenv('PROXY_USER', 'sp6qilmhb3')
        self.proxy_pass = os.getenv('PROXY_PASS', 'y2ok7Y3FEygM~rs7de')
        
        # Construct proxy URLs
        proxy_auth = f"{self.proxy_user}:{self.proxy_pass}@{self.proxy_host}:{self.proxy_port}"
        self.proxies = {
            "http": f"http://{proxy_auth}",
            "https": f"http://{proxy_auth}"
        }
        
        # Failover proxy ports
        self.failover_ports = ['10002', '10003']
        self.current_port_index = 0
        
    def _init_client(self, api_key: str, api_secret: str):
        """Initialize the Binance client with proxy settings."""
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
        """Set up WebSocket connection for real-time data."""
        self.ws_url = "wss://stream.binance.com:9443/ws"
        self.ws_connections = {}
        
    async def initialize(self):
        """Initialize the client and test connection."""
        try:
            # Test connection
            await self._test_connection()
            
            # Initialize WebSocket connections for each symbol
            for symbol in self.symbols:
                await self._setup_symbol_websocket(symbol)
                
            logger.info("Exchange client initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing exchange client: {e}")
            raise
            
    async def _test_connection(self):
        """Test the connection to the exchange."""
        try:
            # Test REST API via requests
            self.client.ping()

            # Test WebSocket connectivity using aiohttp with proxy auth
            proxy_auth = BasicAuth(self.proxy_user, self.proxy_pass)

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.ws_url,
                    proxy=f"http://{self.proxy_host}:{self.proxy_port}",
                    proxy_auth=proxy_auth
                ) as response:
                    if response.status != 200:
                        raise ConnectionError("WebSocket connection test failed")

            logger.info("Connection test successful")

        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            await self._handle_connection_error()
            raise
            
    async def _handle_connection_error(self):
        """Handle connection errors and attempt failover."""
        if self.current_port_index < len(self.failover_ports):
            # Try next failover port
            self.proxy_port = self.failover_ports[self.current_port_index]
            self.current_port_index += 1
            
            # Update proxy configuration
            self._setup_proxy()
            
            # Reinitialize client with fresh API credentials
            api_key = os.getenv("BINANCE_API_KEY")
            api_secret = os.getenv("BINANCE_API_SECRET")
            self._init_client(api_key, api_secret)
            
            logger.info(f"Switched to failover port: {self.proxy_port}")
        else:
            logger.error("All failover ports exhausted")
            raise ConnectionError("Failed to establish connection with all proxy ports")
            
    async def _setup_symbol_websocket(self, symbol: str):
        """Set up WebSocket connection for a specific symbol."""
        try:
            stream_name = f"{symbol.lower()}@kline_1m"
            ws_url = f"{self.ws_url}/{stream_name}"
            
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(
                    ws_url,
                    proxy=self.proxies['http']
                ) as ws:
                    self.ws_connections[symbol] = ws
                    logger.info(f"WebSocket connection established for {symbol}")
        except Exception as e:
            logger.error(f"Error setting up WebSocket for {symbol}: {e}")
            raise
            
    async def get_market_data(self, symbol: str) -> Optional[Dict]:
        """Get market data for a symbol."""
        try:
            # Get klines (candlestick data)
            klines = self.client.get_klines(
                symbol=symbol,
                interval=Client.KLINE_INTERVAL_1MINUTE,
                limit=100
            )
            
            # Get order book
            depth = self.client.get_order_book(symbol=symbol, limit=10)
            
            # Get 24hr ticker
            ticker = self.client.get_ticker(symbol=symbol)
            
            return {
                'symbol': symbol,
                'timestamp': datetime.now().timestamp(),
                'klines': klines,
                'orderbook': depth,
                'ticker': ticker
            }
        except BinanceAPIException as e:
            logger.error(f"Binance API error for {symbol}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error getting market data for {symbol}: {e}")
            return None
            
    async def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None
    ) -> Optional[Dict]:
        """Place an order on the exchange."""
        try:
            params = {
                'symbol': symbol,
                'side': side,
                'type': order_type,
                'quantity': quantity
            }
            
            if price:
                params['price'] = price
            if stop_price:
                params['stopPrice'] = stop_price
                
            order = self.client.create_order(**params)
            logger.info(f"Order placed successfully: {order}")
            return order
        except BinanceAPIException as e:
            logger.error(f"Error placing order: {e}")
            return None
            
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get open orders for a symbol or all symbols."""
        try:
            if symbol:
                orders = self.client.get_open_orders(symbol=symbol)
            else:
                orders = self.client.get_open_orders()
            return orders
        except BinanceAPIException as e:
            logger.error(f"Error getting open orders: {e}")
            return []
            
    async def cancel_order(self, symbol: str, order_id: int) -> bool:
        """Cancel an order."""
        try:
            self.client.cancel_order(symbol=symbol, orderId=order_id)
            logger.info(f"Order {order_id} cancelled successfully")
            return True
        except BinanceAPIException as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            return False
            
    async def close(self):
        """Close all connections."""
        try:
            # Close WebSocket connections
            for symbol, ws in self.ws_connections.items():
                await ws.close()
            self.ws_connections.clear()
            
            logger.info("Exchange client closed successfully")
        except Exception as e:
            logger.error(f"Error closing exchange client: {e}")
            raise
            
    async def _handle_orderbook(self, msg: Dict):
        """Handle incoming order book updates."""
        try:
            symbol = msg['s']
            if symbol not in self.market_data:
                return
                
            self.market_data[symbol]['orderbook'] = {
                'bids': msg['b'],
                'asks': msg['a'],
                'timestamp': datetime.now().timestamp()
            }
            self.market_data[symbol]['last_update'] = datetime.now().timestamp()
            
        except Exception as e:
            logger.error(f"Error handling orderbook for {symbol}: {e}")
            
    async def _handle_funding_rate(self, msg: Dict):
        """Handle incoming funding rate updates."""
        try:
            symbol = msg['s']
            if symbol not in self.market_data:
                return
                
            self.market_data[symbol]['funding_rate'] = {
                'rate': float(msg['r']),
                'timestamp': datetime.now().timestamp()
            }
            self.market_data[symbol]['last_update'] = datetime.now().timestamp()
            
        except Exception as e:
            logger.error(f"Error handling funding rate for {symbol}: {e}")
            
    @rate_limit(max_calls=1200, period=60)  # 1200 calls per minute
    async def get_historical_data(
        self,
        symbol: str,
        interval: str,
        limit: int = 500
    ) -> List[Dict]:
        """Get historical klines/candlestick data."""
        try:
            if symbol not in self.symbols:
                raise ValueError(f"Symbol {symbol} not in configured symbols")
                
            klines = self.client.futures_klines(
                symbol=symbol,
                interval=interval,
                limit=limit
            )
            
            return [{
                'timestamp': k[0],
                'open': float(k[1]),
                'high': float(k[2]),
                'low': float(k[3]),
                'close': float(k[4]),
                'volume': float(k[5])
            } for k in klines]
            
        except BinanceAPIException as e:
            logger.error(f"Error fetching historical data for {symbol}: {e}")
            return []
            
    def get_latest_data(self, symbol: str) -> Optional[Dict]:
        """Get the latest market data from memory."""
        if symbol not in self.market_data:
            return None
        return self.market_data[symbol] 