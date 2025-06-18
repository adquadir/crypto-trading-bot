import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Callable, Any
import websockets
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class MarketDataWebSocket:
    """WebSocket client for market data streams using websockets."""
    
    def __init__(self, exchange_client: 'ExchangeClient', symbols: List[str], cache_ttl: int = 5):
        """Initialize the WebSocket client."""
        self.exchange_client = exchange_client
        self.symbols = symbols
        self.cache_ttl = cache_ttl
        self.ws_url = "wss://fstream.binance.com/ws"
        self.connections: Dict[str, websockets.WebSocketClientProtocol] = {}
        self.running = False
        self.logger = logging.getLogger(__name__)
        self.retry_count = 0
        self.max_retries = 3
        self.retry_delay = 2
        self.cache = {}
        self.cache_timestamps = {}
        self.data_cache: Dict[str, Dict] = {}
        self.last_update: Dict[str, float] = {}
        self.callbacks: Dict[str, List[Callable]] = {
            'kline': [],
            'trade': [],
            'depth': []
        }
        self.proxy = {
            'host': os.getenv('PROXY_HOST'),
            'port': os.getenv('PROXY_PORT'),
            'username': os.getenv('PROXY_USER'),
            'password': os.getenv('PROXY_PASS')
        }

    def _get_ws_url(self, symbol):
        """Get the correct WebSocket URL for Binance Futures."""
        return f"wss://fstream.binance.com/ws/{symbol.lower()}@trade"

    async def _handle_message(self, message: str, symbol: str):
        """Handle incoming WebSocket message."""
        try:
            message_dict = json.loads(message)
            self.cache[symbol] = message_dict
            self.cache_timestamps[symbol] = time.time()
            if 'e' in message_dict:
                event_type = message_dict['e']
                if event_type == 'trade':
                    for callback in self.callbacks['trade']:
                        await callback(symbol, message_dict)
        except Exception as e:
            self.logger.error(f"Error handling WebSocket message: {e}")

    async def _connect_symbol(self, symbol: str):
        """Connect to WebSocket for a specific symbol."""
        try:
            ws_url = self._get_ws_url(symbol)
            
            # Configure proxy
            proxy_url = None
            if self.proxy['host'] and self.proxy['port']:
                proxy_url = f"http://{self.proxy['host']}:{self.proxy['port']}"
                if self.proxy['username'] and self.proxy['password']:
                    proxy_url = f"http://{self.proxy['username']}:{self.proxy['password']}@{self.proxy['host']}:{self.proxy['port']}"
                logger.info(f"WebSocket proxy configured: {self.proxy['host']}:{self.proxy['port']}")
            
            # Create headers
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            api_key = os.getenv('BINANCE_API_KEY')
            if api_key:
                headers['X-MBX-APIKEY'] = api_key
            
            # Connect to WebSocket
            async with websockets.connect(
                ws_url,
                extra_headers=headers,
                proxy=proxy_url
            ) as websocket:
                self.connections[symbol] = websocket
                logger.info(f"WebSocket connection established for {symbol}")
                
                while self.running:
                    try:
                        message = await websocket.recv()
                        await self._handle_message(message, symbol)
                    except websockets.exceptions.ConnectionClosed:
                        logger.warning(f"WebSocket connection closed for {symbol}")
                        break
                    except Exception as e:
                        logger.error(f"Error in WebSocket connection for {symbol}: {e}")
                        break
                        
        except Exception as e:
            logger.error(f"Error connecting to WebSocket for {symbol}: {e}")
            raise

    async def initialize(self, symbols: List[str] = None):
        """Initialize WebSocket connections."""
        try:
            if symbols:
                self.symbols = symbols
                
            if not self.symbols:
                logger.warning("No symbols provided for WebSocket connection")
                return
                
            self.running = True
            
            # Connect to each symbol in parallel
            tasks = [self._connect_symbol(symbol) for symbol in self.symbols]
            await asyncio.gather(*tasks)
            
            logger.info(f"WebSocket connections initialized for symbols: {self.symbols}")
            
        except Exception as e:
            logger.error(f"Error initializing WebSocket connections: {e}")
            raise

    def register_callback(self, data_type: str, callback: Callable):
        """Register a callback for a specific data type."""
        if data_type in self.callbacks:
            self.callbacks[data_type].append(callback)

    def get_cached_data(self, symbol: str, data_type: str) -> Optional[Dict]:
        """Get cached data for a symbol and data type."""
        cache_key = f"{symbol}_{data_type}"
        if cache_key in self.data_cache:
            if self.get_data_freshness(symbol) > self.cache_ttl:
                logger.warning(f"Stale data for {symbol} {data_type}: {self.get_data_freshness(symbol):.2f}s old")
            return self.data_cache[cache_key]
        return None

    def get_data_freshness(self, symbol: str) -> float:
        """Get the age of the most recent data for a symbol in seconds."""
        if symbol not in self.last_update:
            return float('inf')
        return time.time() - self.last_update[symbol]

    async def stop(self):
        """Stop the WebSocket client."""
        self.running = False
        for ws in self.connections.values():
            await ws.close()
        self.logger.info("WebSocket client stopped")

    async def close(self):
        """Close the WebSocket connection."""
        try:
            self.running = False
            for ws in self.connections.values():
                await ws.close()
            self.connections.clear()
            logger.info("WebSocket connection closed")
        except Exception as e:
            logger.error(f"Error closing WebSocket connection: {e}")
            raise

    async def _monitor_websocket_heartbeat(self):
        """Monitor WebSocket connection health with periodic heartbeats."""
        while self.running:
            try:
                for symbol, ws in self.connections.items():
                    if ws.open:
                        await ws.ping()
                        logger.debug(f"WebSocket heartbeat ping sent for {symbol}")
                    else:
                        logger.warning(f"WebSocket connection not open for {symbol}, attempting to reconnect")
                        await self._connect_symbol(symbol)
            except Exception as e:
                logger.error(f"Error in WebSocket heartbeat: {e}")
            await asyncio.sleep(30)  # Send heartbeat every 30 seconds

    async def check_connection(self) -> bool:
        """Check if WebSocket connections are healthy."""
        try:
            if not self.connections:
                logger.warning("No WebSocket connections established")
                return False
                
            for symbol, ws in self.connections.items():
                if not ws.open:
                    logger.warning(f"WebSocket connection not open for {symbol}")
                    return False
                    
            return True
            
        except Exception as e:
            logger.error(f"Error checking WebSocket connection: {e}")
            return False

    async def reconnect(self) -> bool:
        """Reconnect all WebSocket connections."""
        try:
            logger.info("Attempting to reconnect all WebSocket connections...")
            
            # Close existing connections
            await self.close()
            
            # Reinitialize connections
            await self.initialize()
            
            logger.info("Successfully reconnected all WebSocket connections")
            return True
            
        except Exception as e:
            logger.error(f"Error reconnecting WebSocket connections: {e}")
            return False

    def update_symbols(self, symbols: List[str]) -> None:
        """Update the list of symbols to monitor.
        
        Args:
            symbols: List of trading symbols to monitor
        """
        if not symbols:
            logger.warning("No symbols provided for WebSocket update")
            return
            
        self.symbols = set(symbols)
        logger.info(f"WebSocket symbols updated to: {self.symbols}")
        
        # If WebSocket is already connected, reconnect with new symbols
        if self.is_connected():
            self.connect() 

    async def _setup_symbol_websocket(self, symbol: str, proxy_url: Optional[str] = None) -> None:
        """Set up WebSocket connection for a symbol."""
        try:
            # Create WebSocket client for the symbol
            ws_client = MarketDataWebSocket(
                exchange_client=self.exchange_client,
                symbols=[symbol],
                cache_ttl=5
            )
            
            # Configure proxy if available
            if proxy_url:
                ws_client.proxy = proxy_url
            
            # Connect to WebSocket (not async)
            ws_client.connect()
            
            # Store the client
            self.ws_clients[symbol] = ws_client
            logger.info(f"WebSocket client started for {symbol}")
        except Exception as e:
            logger.error(f"Error setting up WebSocket for {symbol}: {e}")
            raise 
