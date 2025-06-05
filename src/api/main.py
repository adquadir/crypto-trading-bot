from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Dict
import json
import asyncio
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Crypto Trading Bot API",
    description="API for the Crypto Trading Bot Dashboard",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your frontend URL
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
        self.heartbeat_interval = 30  # seconds

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"New WebSocket connection. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Remaining connections: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting message: {e}")
                disconnected.append(connection)

        # Clean up disconnected clients
        for connection in disconnected:
            self.disconnect(connection)

    async def handle_heartbeat(self, websocket: WebSocket, data: dict):
        try:
            # Echo back the timestamp for latency calculation
            await websocket.send_json({
                "type": "pong",
                "timestamp": data.get("timestamp")
            })
        except Exception as e:
            logger.error(f"Error handling heartbeat: {e}")
            self.disconnect(websocket)

manager = ConnectionManager()

# WebSocket endpoint for live signals
@app.websocket("/ws/signals")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            try:
                # Wait for messages from client
                data = await websocket.receive_json()
                
                # Handle heartbeat messages
                if data.get("type") == "ping":
                    await manager.handle_heartbeat(websocket, data)
                    continue

                # Handle other message types here
                logger.debug(f"Received message: {data}")

            except json.JSONDecodeError:
                logger.error("Invalid JSON received")
                continue
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                continue

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
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

@app.get("/api/trading/settings")
async def get_settings():
    return {
        "maxPositionSize": 0.1,
        "maxLeverage": 3.0,
        "riskPerTrade": 0.02,
        "maxOpenTrades": 5,
        "maxCorrelation": 0.7,
        "minRiskReward": 2.0,
        "maxDailyLoss": 0.05,
        "maxDrawdown": 0.15
    }

@app.post("/api/trading/settings")
async def update_settings(settings: dict):
    # In a real implementation, you would save these settings
    return {"status": "success", "message": "Settings updated"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 