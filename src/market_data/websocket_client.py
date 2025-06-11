import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Callable, Any
import websocket
import threading
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class MarketDataWebSocket:
    """WebSocket client for market data streams using websocket-client."""
    
    def __init__(self, exchange_client: 'ExchangeClient', symbols: List[str], cache_ttl: int = 5):
        """Initialize the WebSocket client."""
        self.exchange_client = exchange_client
        self.symbols = symbols
        self.cache_ttl = cache_ttl
        self.ws_url = "wss://fstream.binance.com/ws"  # Reverted to correct single-symbol endpoint
        self.connection = None
        self.running = False
        self.logger = logging.getLogger(__name__)
        self.retry_count = 0
        self.max_retries = 3
        self.retry_delay = 2
        self.cache = {}  # Initialize cache
        self.cache_timestamps = {}  # Initialize cache timestamps
        self.connections: Dict[str, websocket.WebSocketApp] = {}
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
        self.threads = []

    def _get_ws_url(self, symbol):
        # Binance Futures WebSocket URL format for single-symbol streams
        return f"{self.ws_url}/{symbol.lower()}@trade"

    def _on_message(self, ws, message):
        try:
            message_dict = json.loads(message)
            symbol = message_dict.get('s', '').upper()
            self.cache[symbol] = message_dict
            self.cache_timestamps[symbol] = time.time()
            if 'e' in message_dict:
                event_type = message_dict['e']
                if event_type == 'trade':
                    for callback in self.callbacks['trade']:
                        callback(symbol, message_dict)
            # Add more event handling as needed
        except Exception as e:
            self.logger.error(f"Error handling WebSocket message: {e}")

    def _on_error(self, ws, error):
        self.logger.error(f"WebSocket error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        self.logger.info(f"WebSocket closed: {close_status_code} - {close_msg}")

    def _on_open(self, ws):
        self.logger.info("WebSocket connection opened.")

    def connect(self):
        """Connect to the WebSocket stream."""
        try:
            if not self.symbols:
                logger.warning("No symbols provided for WebSocket connection")
                return
                
            # Convert symbols set to list if needed
            symbols_list = list(self.symbols) if isinstance(self.symbols, set) else self.symbols
            
            # Create headers with API key if available
            headers = {}
            api_key = os.getenv('BINANCE_API_KEY')
            if api_key:
                headers['X-MBX-APIKEY'] = api_key
            
            # Add user agent
            headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            
            # Create WebSocket connection with headers
            self.connection = websocket.WebSocketApp(
                self._get_ws_url(symbols_list[0]),  # Use first symbol for now
                header=headers,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
                on_open=self._on_open
            )
            
            # Start WebSocket connection in a separate thread
            self.ws_thread = threading.Thread(target=self.connection.run_forever)
            self.ws_thread.daemon = True
            self.ws_thread.start()
            
            logger.info(f"WebSocket connection started for {symbols_list[0]}")
            
        except Exception as e:
            logger.error(f"Error connecting to WebSocket: {e}")
            raise

    def register_callback(self, data_type: str, callback: Callable):
        """Register a callback for a specific data type."""
        if data_type in self.callbacks:
            self.callbacks[data_type].append(callback)

    def get_cached_data(self, symbol: str, data_type: str) -> Optional[Dict]:
        """Get cached data for a symbol and data type."""
        cache_key = f"{symbol}_{data_type}"
        if cache_key in self.data_cache:
            # Check if data is stale
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
            ws.close()
        self.logger.info("WebSocket client stopped")

    async def close(self):
        """Close the WebSocket connection."""
        try:
            self.running = False  # Stop all background tasks
            for ws in self.connections.values():
                ws.close()
            self.connections.clear()
            logger.info("WebSocket connection closed")
        except Exception as e:
            logger.error(f"Error closing WebSocket connection: {e}")
            raise 

    async def _monitor_websocket_heartbeat(self):
        """Monitor WebSocket connection health with periodic heartbeats."""
        while self.running:
            try:
                for ws in self.connections.values():
                    if ws.sock and ws.sock.connected:
                    # Send ping message
                        ws.sock.send("ping")
                    logger.debug("WebSocket heartbeat ping sent")
                else:
                    logger.warning("WebSocket connection not open, skipping heartbeat")
            except Exception as e:
                logger.error(f"Error in WebSocket heartbeat: {e}")
                # If we can't send a heartbeat, the connection might be dead
                self.running = False
                break
            
            # Wait before next heartbeat
            await asyncio.sleep(30)  # Send heartbeat every 30 seconds 

    async def initialize(self, symbols: Optional[List[str]] = None) -> None:
        """Initialize the WebSocket client with optional symbols."""
        try:
            # Update symbols if provided
            if symbols is not None:
                self.symbols = symbols
            # Initialize cache and timestamps
            self.cache = {}
            self.cache_timestamps = {}
            self.data_cache = {}
            self.callbacks = {
                'kline': [],
                'trade': [],
                'depth': []
            }
            # Connect to WebSocket
            self.connect()
            # Start the WebSocket client in a background task
            asyncio.create_task(self._monitor_websocket_heartbeat())
            self.logger.info(f"WebSocket client initialized with {len(self.symbols)} symbols")
        except Exception as e:
            self.logger.error(f"Error initializing WebSocket client: {e}")
            raise 

    def check_connection(self) -> bool:
        """Check if the WebSocket connection is healthy."""
        try:
            # Check if WebSocket is initialized
            if not self.connections:
                logger.error("WebSocket not initialized")
                return False
                
            # Check connection state
            for ws in self.connections.values():
                if not ws.sock or not ws.sock.connected:
                    logger.error(f"WebSocket connection for {ws.url} is closed")
                return False
                
            # Check last message time
            if hasattr(self, '_last_message_time'):
                time_since_last = (datetime.now() - self._last_message_time).total_seconds()
                if time_since_last > 30:  # No messages for 30 seconds
                    logger.warning(f"No messages received for {time_since_last} seconds")
                    return False
                    
            # Check heartbeat
            if hasattr(self, '_last_heartbeat'):
                time_since_heartbeat = (datetime.now() - self._last_heartbeat).total_seconds()
                if time_since_heartbeat > 10:  # No heartbeat for 10 seconds
                    logger.warning(f"No heartbeat received for {time_since_heartbeat} seconds")
                    return False
                    
            # Check error count
            if hasattr(self, '_error_count') and self._error_count > 5:
                logger.error(f"Too many errors: {self._error_count}")
                return False
                
            # Check subscription status
            if hasattr(self, '_subscriptions'):
                for symbol, status in self._subscriptions.items():
                    if not status.get('active', False):
                        logger.warning(f"Subscription inactive for {symbol}")
                        return False
                        
            return True
            
        except Exception as e:
            logger.error(f"Error checking WebSocket connection: {e}")
            return False 

    def is_connected(self) -> bool:
        """Check if the WebSocket connection is active."""
        try:
            return all(ws.sock and ws.sock.connected for ws in self.connections.values())
        except Exception as e:
            logger.error(f"Error checking WebSocket connection: {e}")
            return False

    async def check_connection(self) -> bool:
        """
        Check if the WebSocket connection is healthy and responsive.
        
        Returns:
            bool: True if connection is healthy
        """
        try:
            if not self.is_connected():
                logger.warning("WebSocket connection is not active")
                return False
                
            # Check if we've received any messages recently
            if self.last_message_time:
                time_since_last = time.time() - self.last_message_time
                if time_since_last > self.heartbeat_interval * 2:
                    logger.warning(f"No messages received for {time_since_last:.1f} seconds")
                    return False
                    
            # Check if we can send a ping
            try:
                for ws in self.connections.values():
                    ws.sock.send("ping")
                return True
            except Exception as e:
                logger.error(f"Error sending ping: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Error checking WebSocket connection: {e}")
            return False

    async def reconnect(self) -> bool:
        """Attempt to reconnect the WebSocket connection."""
        try:
            logger.info("Attempting to reconnect WebSocket...")
            
            # Close existing connection
            await self.close()
            
            # Reinitialize connection
            await self.initialize(self.symbols)
            
            # Verify connection
            if not self.is_connected():
                logger.error("Failed to reconnect WebSocket")
                return False
                
            logger.info("Successfully reconnected WebSocket")
            return True
            
        except Exception as e:
            logger.error(f"Error reconnecting WebSocket: {e}")
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