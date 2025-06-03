from typing import Dict, List, Optional, Set
import asyncio
import logging
from datetime import datetime
import aiohttp
from binance.client import Client
from binance.exceptions import BinanceAPIException
from binance.streams import BinanceSocketManager
import time
from functools import wraps

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
    def __init__(self, api_key: str, api_secret: str, symbols: Set[str] = {'BTCUSDT'}):
        self.client = Client(api_key, api_secret)
        self.ws_manager = None
        self.connections = []
        self.market_data = {}
        self.symbols = symbols
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 1  # seconds
        
    async def initialize(self):
        """Initialize WebSocket connections for real-time data."""
        try:
            self.ws_manager = BinanceSocketManager(self.client)
            
            for symbol in self.symbols:
                # Subscribe to order book updates
                self.connections.append(
                    self.ws_manager.start_depth_socket(symbol, self._handle_orderbook)
                )
                
                # Subscribe to funding rate updates
                self.connections.append(
                    self.ws_manager.start_futures_socket(self._handle_funding_rate)
                )
                
                # Initialize market data structure
                self.market_data[symbol] = {
                    'orderbook': {},
                    'funding_rate': {},
                    'last_update': None
                }
            
            # Start the socket manager
            self.ws_manager.start()
            self.reconnect_attempts = 0
            logger.info(f"Successfully initialized WebSocket connections for {len(self.symbols)} symbols")
            
        except Exception as e:
            logger.error(f"Error initializing WebSocket connections: {e}")
            await self._handle_reconnection()
            
    async def _handle_reconnection(self):
        """Handle WebSocket reconnection logic."""
        if self.reconnect_attempts < self.max_reconnect_attempts:
            self.reconnect_attempts += 1
            delay = self.reconnect_delay * (2 ** (self.reconnect_attempts - 1))  # Exponential backoff
            logger.info(f"Attempting to reconnect in {delay} seconds (attempt {self.reconnect_attempts}/{self.max_reconnect_attempts})")
            await asyncio.sleep(delay)
            await self.initialize()
        else:
            logger.error("Max reconnection attempts reached. Please check your connection and API credentials.")
            
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
    async def get_market_data(self, symbol: str) -> Dict:
        """Get current market data for a symbol."""
        try:
            if symbol not in self.symbols:
                raise ValueError(f"Symbol {symbol} not in configured symbols")
                
            # Get current price
            ticker = self.client.futures_symbol_ticker(symbol=symbol)
            
            # Get open interest
            open_interest = self.client.futures_open_interest(symbol=symbol)
            
            # Get funding rate
            funding_rate = self.client.futures_funding_rate(symbol=symbol)
            
            data = {
                'price': float(ticker['price']),
                'open_interest': float(open_interest['openInterest']),
                'funding_rate': float(funding_rate[0]['fundingRate']),
                'timestamp': datetime.now().timestamp()
            }
            
            # Update market data
            self.market_data[symbol].update(data)
            self.market_data[symbol]['last_update'] = datetime.now().timestamp()
            
            return data
            
        except BinanceAPIException as e:
            logger.error(f"Error fetching market data for {symbol}: {e}")
            return {}
            
    @rate_limit(max_calls=1200, period=60)
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
            
    async def close(self):
        """Close all WebSocket connections."""
        try:
            if self.ws_manager:
                self.ws_manager.close()
            for conn in self.connections:
                await conn.close()
            logger.info("Successfully closed all WebSocket connections")
        except Exception as e:
            logger.error(f"Error closing WebSocket connections: {e}")
            
    def get_latest_data(self, symbol: str) -> Optional[Dict]:
        """Get the latest market data from memory."""
        if symbol not in self.market_data:
            return None
        return self.market_data[symbol] 