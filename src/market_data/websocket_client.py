import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Callable
import websockets
from datetime import datetime

logger = logging.getLogger(__name__)

class MarketDataWebSocket:
    def __init__(self, exchange_client, symbols: List[str], cache_ttl: int = 5):
        """Initialize the WebSocket client."""
        self.exchange_client = exchange_client
        self.symbols = symbols
        self.cache_ttl = cache_ttl
        self.connection = None
        self.running = False
        self.ws_url = "wss://stream.binance.com:9443/ws/stream"  # Updated WebSocket URL
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
                self.connection = await websockets.connect(stream_url)
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
        await self.connect()
        await self.subscribe()  # Subscribe to streams after connecting
        self.running = True  # Set running to True before entering the loop
        while self.running:
            try:
                message = await self.connection.recv()
                await self._handle_message(message)
            except websockets.exceptions.ConnectionClosed:
                logger.error("WebSocket connection closed unexpectedly.")
                break
            except Exception as e:
                logger.error(f"Error in WebSocket message processing: {e}")
                break

    async def _handle_message(self, message: str):
        """Process incoming WebSocket message."""
        try:
            message_dict = json.loads(message)
            stream = message_dict.get('stream', '')
            data = message_dict.get('data', {})

            if not stream or not data:
                return

            # Extract symbol and data type from stream name
            symbol = stream.split('@')[0].upper()
            data_type = stream.split('@')[1]

            # Update cache with timestamp
            current_time = time.time()
            self.last_update[symbol] = current_time

            if data_type.startswith('kline'):
                # Process kline data
                kline = data['k']
                self.data_cache[f"{symbol}_kline"] = {
                    'open': float(kline['o']),
                    'high': float(kline['h']),
                    'low': float(kline['l']),
                    'close': float(kline['c']),
                    'volume': float(kline['v']),
                    'timestamp': kline['t'],
                    'is_closed': kline['x']
                }
                # Notify kline callbacks
                for callback in self.callbacks['kline']:
                    await callback(symbol, self.data_cache[f"{symbol}_kline"])

            elif data_type == 'trade':
                # Process trade data
                self.data_cache[f"{symbol}_trade"] = {
                    'price': float(data['p']),
                    'quantity': float(data['q']),
                    'timestamp': data['T'],
                    'is_buyer_maker': data['m']
                }
                # Notify trade callbacks
                for callback in self.callbacks['trade']:
                    await callback(symbol, self.data_cache[f"{symbol}_trade"])

            elif data_type.startswith('depth'):
                # Process order book data
                self.data_cache[f"{symbol}_depth"] = {
                    'bids': [[float(price), float(qty)] for price, qty in data['bids'][:10]],
                    'asks': [[float(price), float(qty)] for price, qty in data['asks'][:10]],
                    'timestamp': data['T']
                }
                # Notify depth callbacks
                for callback in self.callbacks['depth']:
                    await callback(symbol, self.data_cache[f"{symbol}_depth"])

        except Exception as e:
            logger.error(f"Error processing message: {e}")

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