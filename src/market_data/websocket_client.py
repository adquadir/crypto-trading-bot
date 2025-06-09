import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Callable, Any
import websockets
from datetime import datetime

logger = logging.getLogger(__name__)

class MarketDataWebSocket:
    """WebSocket client for market data streams."""
    
    def __init__(self, exchange_client: 'ExchangeClient', symbols: List[str], cache_ttl: int = 5):
        """Initialize the WebSocket client."""
        self.exchange_client = exchange_client
        self.symbols = symbols
        self.cache_ttl = cache_ttl
        self.ws_url = "wss://stream.binance.com:9443/ws/stream"
        self.connection = None
        self.running = False
        self.logger = logging.getLogger(__name__)
        self.retry_count = 0
        self.max_retries = 3
        self.retry_delay = 2
        self.cache = {}  # Initialize cache
        self.cache_timestamps = {}  # Initialize cache timestamps
        self.connections: Dict[str, websockets.WebSocketClientProtocol] = {}
        self.data_cache: Dict[str, Dict] = {}
        self.last_update: Dict[str, float] = {}
        self.callbacks: Dict[str, List[Callable]] = {
            'kline': [],
            'trade': [],
            'depth': []
        }

    async def connect(self):
        """Connect to the WebSocket stream."""
        try:
            # Create streams for each symbol
            streams = []
            for symbol in self.symbols:
                streams.extend([
                    f"{symbol.lower()}@aggTrade",
                    f"{symbol.lower()}@depth@100ms",
                    f"{symbol.lower()}@kline_1m",
                    f"{symbol.lower()}@ticker"
                ])
            
            # Connect to the combined stream
            stream_url = f"{self.ws_url}?streams={'/'.join(streams)}"
            self.connection = await websockets.connect(
                stream_url,
                ping_interval=30,
                ping_timeout=10,
                close_timeout=10
            )
            self.running = True
            self.retry_count = 0
            self.logger.info(f"WebSocket connected successfully for symbols: {self.symbols}")
            return True
        except Exception as e:
            self.logger.error(f"Error connecting to WebSocket: {e}")
            return False

    async def subscribe(self):
        """Subscribe to Binance streams."""
        streams = []
        for symbol in self.symbols:
            symbol_lower = symbol.lower()
            streams.extend([
                f"{symbol_lower}@kline_1m",  # 1-minute klines
                f"{symbol_lower}@trade",     # Trades
                f"{symbol_lower}@depth20@100ms"  # Order book (20 levels)
            ])
        subscription_message = {
            "method": "SUBSCRIBE",
            "params": streams,
            "id": 1
        }
        await self.connection.send(json.dumps(subscription_message))
        logger.info(f"Subscribed to streams: {streams}")

    async def start(self):
        """Start the WebSocket client."""
        if self.running:
            return
        
        self.running = True
        
        # Start message processing loop
        while self.running:
            try:
                message = await self.connection.recv()
                await self._handle_ws_message(message)
            except websockets.exceptions.ConnectionClosed:
                logger.error("WebSocket connection closed unexpectedly.")
                break
            except Exception as e:
                logger.error(f"Error in WebSocket message loop: {e}")
                break
        
        self.running = False
        logger.info("WebSocket client stopped")

    async def _handle_ws_message(self, message: str):
        """Handle incoming WebSocket messages."""
        try:
            message_dict = json.loads(message)
            
            # Extract stream and data from message
            stream = message_dict.get('stream', '')
            data = message_dict.get('data', {})
            
            # Extract symbol from stream name (e.g., "btcusdt@kline_1m" -> "BTCUSDT")
            symbol = stream.split('@')[0].upper()
            
            # Update cache with new data
            self.cache[symbol] = data
            self.cache_timestamps[symbol] = time.time()
            
            # Process different message types
            if 'e' in data:  # Check if it's a Binance message
                event_type = data['e']
                if event_type == 'kline':
                    await self._handle_kline_message(symbol, data)
                elif event_type == 'trade':
                    await self._handle_trade_message(symbol, data)
                elif event_type == 'depthUpdate':
                    await self._handle_depth_message(symbol, data)
                else:
                    self.logger.debug(f"Unhandled message type: {event_type}")
            else:
                self.logger.warning(f"Received message without event type: {data}")
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse WebSocket message as JSON: {e}")
            self.logger.error(f"Raw message: {message}")
        except Exception as e:
            self.logger.error(f"Error handling WebSocket message: {e}")
            self.logger.error(f"Raw message: {message}")

    async def _handle_kline_message(self, symbol: str, data: Dict[str, Any]) -> None:
        """Handle kline message."""
        try:
            kline_data = {
                'open': float(data['k']['o']),
                'high': float(data['k']['h']),
                'low': float(data['k']['l']),
                'close': float(data['k']['c']),
                'volume': float(data['k']['v']),
                'timestamp': data['k']['t'],
                'is_closed': data['k']['x']
            }
            self.data_cache[f"{symbol}_kline"] = kline_data
            # Notify kline callbacks
            for callback in self.callbacks['kline']:
                await callback(symbol, kline_data)
        except Exception as e:
            self.logger.error(f"Error handling kline message: {e}")

    async def _handle_trade_message(self, symbol: str, data: Dict[str, Any]) -> None:
        """Handle trade message."""
        try:
            trade_data = {
                'price': float(data['p']),
                'quantity': float(data['q']),
                'timestamp': data['T'],
                'is_buyer_maker': data['m']
            }
            self.data_cache[f"{symbol}_trade"] = trade_data
            # Notify trade callbacks
            for callback in self.callbacks['trade']:
                await callback(symbol, trade_data)
        except Exception as e:
            self.logger.error(f"Error handling trade message: {e}")

    async def _handle_depth_message(self, symbol: str, data: Dict[str, Any]) -> None:
        """Handle depth message."""
        try:
            depth_data = {
                'bids': [[float(price), float(qty)] for price, qty in data['bids'][:10]],
                'asks': [[float(price), float(qty)] for price, qty in data['asks'][:10]],
                'timestamp': data['T']
            }
            self.data_cache[f"{symbol}_depth"] = depth_data
            # Notify depth callbacks
            for callback in self.callbacks['depth']:
                await callback(symbol, depth_data)
        except Exception as e:
            self.logger.error(f"Error handling depth message: {e}")

    def register_callback(self, data_type: str, callback: Callable):
        """Register a callback for a specific data type."""
        if data_type in self.callbacks:
            self.callbacks[data_type].append(callback)

    def get_data_freshness(self, symbol: str) -> float:
        """Get the age of the most recent data for a symbol in seconds."""
        if symbol not in self.last_update:
            return float('inf')
        return time.time() - self.last_update[symbol]

    def get_cached_data(self, symbol: str, data_type: str) -> Optional[Dict]:
        """Get cached data for a symbol and data type."""
        cache_key = f"{symbol}_{data_type}"
        if cache_key in self.data_cache:
            # Check if data is stale
            if self.get_data_freshness(symbol) > self.cache_ttl:
                logger.warning(f"Stale data for {symbol} {data_type}: {self.get_data_freshness(symbol):.2f}s old")
            return self.data_cache[cache_key]
        return None

    async def stop(self):
        """Stop the WebSocket client."""
        self.running = False
        if hasattr(self, 'connection'):
            await self.connection.close()
        logger.info("WebSocket client stopped")

    async def close(self):
        """Close the WebSocket connection."""
        try:
            self.running = False  # Stop all background tasks
            if self.connection:
                await self.connection.close()
                self.connection = None
            logger.info("WebSocket connection closed")
        except Exception as e:
            logger.error(f"Error closing WebSocket connection: {e}")
            raise 

    async def _monitor_websocket_heartbeat(self):
        """Monitor WebSocket connection health with periodic heartbeats."""
        while self.running:
            try:
                if self.connection and self.connection.open:
                    # Send ping message
                    await self.connection.ping()
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
            await self.connect()
            
            # Start the WebSocket client in a background task
            asyncio.create_task(self.start())
            
            self.logger.info(f"WebSocket client initialized with {len(self.symbols)} symbols")
        except Exception as e:
            self.logger.error(f"Error initializing WebSocket client: {e}")
            raise 

    def check_connection(self) -> bool:
        """Check if the WebSocket connection is healthy."""
        try:
            # Check if WebSocket is initialized
            if not self.connection:
                logger.error("WebSocket not initialized")
                return False
                
            # Check connection state
            if not self.connection.open:
                logger.error("WebSocket connection is closed")
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
            return (
                self.connection is not None and 
                not self.connection.closed and 
                self.connection._connection and 
                self.connection._connection.is_connected()
            )
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
                await self.connection.ping()
                return True
            except Exception as e:
                logger.error(f"Error sending ping: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Error checking WebSocket connection: {e}")
            return False

    async def reconnect(self) -> bool:
        """
        Attempt to reconnect the WebSocket connection.
        
        Returns:
            bool: True if reconnection was successful
        """
        try:
            logger.info("Attempting to reconnect WebSocket...")
            
            # Close existing connection if any
            if self.connection and not self.connection.closed:
                await self.connection.close()
                
            # Clear connection state
            self.connection = None
            self.last_message_time = None
            self.reconnect_attempts = 0
            
            # Wait before reconnecting
            await asyncio.sleep(self.reconnect_delay)
            
            # Attempt to reconnect
            try:
                await self.initialize(self.symbols)
                logger.info("WebSocket reconnected successfully")
                return True
            except Exception as e:
                logger.error(f"Failed to reconnect WebSocket: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Error during WebSocket reconnection: {e}")
            return False

    async def _handle_connection_error(self) -> None:
        """Handle WebSocket connection errors and attempt reconnection."""
        try:
            logger.warning("Handling WebSocket connection error")
            
            # Increment reconnect attempts
            self.reconnect_attempts += 1
            
            # Calculate backoff delay
            delay = min(
                self.reconnect_delay * (2 ** self.reconnect_attempts),
                self.max_reconnect_delay
            )
            
            logger.info(f"Reconnect attempt {self.reconnect_attempts}, waiting {delay:.1f} seconds")
            await asyncio.sleep(delay)
            
            # Attempt reconnection
            if await self.reconnect():
                self.reconnect_attempts = 0
            else:
                logger.error("Failed to reconnect after maximum attempts")
                
        except Exception as e:
            logger.error(f"Error handling connection error: {e}") 