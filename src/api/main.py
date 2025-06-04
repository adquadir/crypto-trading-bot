from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Dict
import json
import asyncio
from datetime import datetime

app = FastAPI(
    title="Crypto Trading Bot API",
    description="API for the Crypto Trading Bot Dashboard",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root endpoint
@app.get("/")
async def root():
    return JSONResponse({
        "status": "online",
        "message": "Crypto Trading Bot API is running",
        "version": "1.0.0",
        "endpoints": {
            "api": "/api/trading/*",
            "websocket": "/ws/signals",
            "documentation": "/docs"
        }
    })

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)

manager = ConnectionManager()

# WebSocket endpoint for live signals
@app.websocket("/ws/signals")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Simulate live signal updates
            signal = {
                "timestamp": datetime.now().isoformat(),
                "symbol": "BTCUSDT",
                "signal": "BUY",
                "confidence": 0.85,
                "indicators": {
                    "macd": {"value": 0.5, "signal": 0.3},
                    "rsi": 65,
                    "bb": {"upper": 50000, "middle": 48000, "lower": 46000}
                }
            }
            await websocket.send_json(signal)
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# REST endpoints
@app.get("/api/trading/signals")
async def get_signals():
    return {
        "signals": [
            {
                "timestamp": datetime.now().isoformat(),
                "symbol": "BTCUSDT",
                "signal": "BUY",
                "confidence": 0.85,
                "indicators": {
                    "macd": {"value": 0.5, "signal": 0.3},
                    "rsi": 65,
                    "bb": {"upper": 50000, "middle": 48000, "lower": 46000}
                }
            }
        ]
    }

@app.get("/api/trading/pnl")
async def get_pnl():
    return {
        "total_pnl": 1234.56,
        "daily_pnl": 234.56,
        "win_rate": 0.65,
        "trades": [
            {
                "symbol": "BTCUSDT",
                "entry_price": 48000,
                "exit_price": 49000,
                "pnl": 1000,
                "timestamp": datetime.now().isoformat()
            }
        ]
    }

@app.get("/api/trading/stats")
async def get_stats():
    return {
        "total_trades": 100,
        "win_rate": 0.65,
        "avg_win": 234.56,
        "avg_loss": -123.45,
        "profit_factor": 1.89,
        "max_drawdown": 0.15,
        "sharpe_ratio": 1.5
    }

@app.get("/api/trading/positions")
async def get_positions():
    return {
        "positions": [
            {
                "symbol": "BTCUSDT",
                "size": 0.1,
                "entry_price": 48000,
                "current_price": 49000,
                "pnl": 100,
                "leverage": 3
            }
        ]
    }

@app.get("/api/trading/strategies")
async def get_strategies():
    return {
        "strategies": [
            {
                "name": "MACD Crossover",
                "active": True,
                "performance": {
                    "win_rate": 0.65,
                    "profit_factor": 1.89,
                    "sharpe_ratio": 1.5
                }
            }
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 