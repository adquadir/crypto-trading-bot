from typing import List, Dict
from fastapi import WebSocket
import json
import asyncio
from datetime import datetime

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.user_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.user_connections[client_id] = websocket

    def disconnect(self, websocket: WebSocket, client_id: str):
        self.active_connections.remove(websocket)
        if client_id in self.user_connections:
            del self.user_connections[client_id]

    async def send_personal_message(self, message: dict, client_id: str):
        if client_id in self.user_connections:
            await self.user_connections[client_id].send_json(message)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)

    async def broadcast_trading_signal(self, signal: dict):
        """Broadcast a trading signal to all connected clients."""
        message = {
            "type": "trading_signal",
            "data": signal,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.broadcast(message)

    async def broadcast_pnl_update(self, pnl: dict):
        """Broadcast a PnL update to all connected clients."""
        message = {
            "type": "pnl_update",
            "data": pnl,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.broadcast(message)

    async def broadcast_orderbook_update(self, symbol: str, orderbook: dict):
        """Broadcast an orderbook update to all connected clients."""
        message = {
            "type": "orderbook_update",
            "data": {
                "symbol": symbol,
                "orderbook": orderbook
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.broadcast(message)

    async def broadcast_trade(self, trade: dict):
        """Broadcast a trade to all connected clients."""
        message = {
            "type": "trade",
            "data": trade,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.broadcast(message)

# Create a global connection manager instance
manager = ConnectionManager() 