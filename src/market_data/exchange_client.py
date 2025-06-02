from typing import Dict, List, Optional
import asyncio
import logging
from datetime import datetime
import aiohttp
from binance.client import Client
from binance.exceptions import BinanceAPIException
from binance.websockets import BinanceSocketManager

logger = logging.getLogger(__name__)

class ExchangeClient:
    def __init__(self, api_key: str, api_secret: str):
        self.client = Client(api_key, api_secret)
        self.ws_manager = None
        self.connections = []
        self.market_data = {}
        
    async def initialize(self):
        """Initialize WebSocket connections for real-time data."""
        self.ws_manager = BinanceSocketManager(self.client)
        
        # Subscribe to order book updates
        self.connections.append(
            self.ws_manager.start_depth_socket('BTCUSDT', self._handle_orderbook)
        )
        
        # Subscribe to funding rate updates
        self.connections.append(
            self.ws_manager.start_futures_socket(self._handle_funding_rate)
        )
        
        # Start the socket manager
        self.ws_manager.start()
        
    async def _handle_orderbook(self, msg: Dict):
        """Handle incoming order book updates."""
        try:
            symbol = msg['s']
            self.market_data[symbol] = {
                'orderbook': {
                    'bids': msg['b'],
                    'asks': msg['a'],
                    'timestamp': datetime.now().timestamp()
                }
            }
        except Exception as e:
            logger.error(f"Error handling orderbook: {e}")
            
    async def _handle_funding_rate(self, msg: Dict):
        """Handle incoming funding rate updates."""
        try:
            symbol = msg['s']
            if 'orderbook' not in self.market_data.get(symbol, {}):
                self.market_data[symbol] = {'orderbook': {}}
            
            self.market_data[symbol]['funding_rate'] = {
                'rate': float(msg['r']),
                'timestamp': datetime.now().timestamp()
            }
        except Exception as e:
            logger.error(f"Error handling funding rate: {e}")
            
    async def get_market_data(self, symbol: str) -> Dict:
        """Get current market data for a symbol."""
        try:
            # Get current price
            ticker = self.client.futures_symbol_ticker(symbol=symbol)
            
            # Get open interest
            open_interest = self.client.futures_open_interest(symbol=symbol)
            
            # Get funding rate
            funding_rate = self.client.futures_funding_rate(symbol=symbol)
            
            return {
                'price': float(ticker['price']),
                'open_interest': float(open_interest['openInterest']),
                'funding_rate': float(funding_rate[0]['fundingRate']),
                'timestamp': datetime.now().timestamp()
            }
        except BinanceAPIException as e:
            logger.error(f"Error fetching market data: {e}")
            return {}
            
    async def get_historical_data(
        self,
        symbol: str,
        interval: str,
        limit: int = 500
    ) -> List[Dict]:
        """Get historical klines/candlestick data."""
        try:
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
            logger.error(f"Error fetching historical data: {e}")
            return []
            
    async def close(self):
        """Close all WebSocket connections."""
        if self.ws_manager:
            self.ws_manager.close()
        for conn in self.connections:
            await conn.close() 