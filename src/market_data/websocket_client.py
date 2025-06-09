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
        self.connection = None
        self.running = False
        self.ws_url = "wss://stream.binance.com:9443/stream"  # Correct combined stream endpoint
        self.logger = logging.getLogger(__name__)
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
        max_retries = 3
        retry_count = 0
        while retry_count < max_retries:
            try:
                # Create streams for each symbol
                streams = []
                for symbol in self.symbols:
                    symbol_lower = symbol.lower()
                    streams.extend([
                        f"{symbol_lower}@kline_1m",  # 1-minute klines
                        f"{symbol_lower}@trade",     # Trades
                        f"{symbol_lower}@depth20@100ms"  # Order book (20 levels)
                    ])
                
                # Connect to combined stream
                stream_url = f"{self.ws_url}?streams={'/'.join(streams)}"
                
                # Required headers for Binance WebSocket
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Origin': 'https://www.binance.com',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Cache-Control': 'no-cache',
                    'Pragma': 'no-cache'
                }
                
                self.connection = await websockets.connect(
                    stream_url,
                    extra_headers=headers,
                    ping_interval=30,
                    ping_timeout=10,
                    close_timeout=10,
                    max_size=2**20,  # 1MB max message size
                    max_queue=2**10,  # 1024 messages in queue
                    compression=None  # Disable compression as Binance doesn't support it
                )
                logger.info(f"Connected to WebSocket stream: {stream_url}")
                return
            except websockets.exceptions.InvalidStatusCode as e:
                if e.status_code == 451:
                    logger.error(f"WebSocket connection rejected with status code 451. Retrying... (Attempt {retry_count + 1}/{max_retries})")
                    retry_count += 1
                    await asyncio.sleep(2)  # Wait before retrying
                else:
                    logger.error(f"Error connecting to WebSocket: {e}")
                    raise
            except Exception as e:
                logger.error(f"Error connecting to WebSocket: {e}")
                raise
        logger.error("Failed to connect to WebSocket after maximum retries.")
        raise ConnectionError("Failed to connect to WebSocket after maximum retries.")

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