from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Dict
import json
import asyncio
from datetime import datetime
import logging
import traceback
import os
from dotenv import load_dotenv
from src.market_data.exchange_client import ExchangeClient
from src.market_data.symbol_discovery import SymbolDiscovery, TradingOpportunity

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Crypto Trading Bot API",
    description="API for the Crypto Trading Bot Dashboard",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware with specific origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://50.31.0.105:3000"],  # Your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize exchange client
exchange_client = ExchangeClient(
    api_key=os.getenv('BINANCE_API_KEY'),
    api_secret=os.getenv('BINANCE_API_SECRET'),
    testnet=os.getenv('USE_TESTNET', 'False').lower() == 'true'
)

# Initialize symbol discovery
symbol_discovery = SymbolDiscovery(exchange_client)

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.heartbeat_interval = 30  # seconds
        self._lock = asyncio.Lock()  # Add lock for thread safety

    async def connect(self, websocket: WebSocket):
        try:
            await websocket.accept()
            async with self._lock:
                self.active_connections.append(websocket)
            logger.info(f"New WebSocket connection established. Total connections: {len(self.active_connections)}")
            # Send initial connection success message
            await websocket.send_json({
                "type": "connection_status",
                "status": "connected",
                "message": "WebSocket connection established"
            })
        except Exception as e:
            logger.error(f"Error accepting WebSocket connection: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    async def disconnect(self, websocket: WebSocket):
        try:
            async with self._lock:
                if websocket in self.active_connections:
                    self.active_connections.remove(websocket)
                    logger.info(f"WebSocket disconnected. Remaining connections: {len(self.active_connections)}")
        except Exception as e:
            logger.error(f"Error during WebSocket disconnect: {str(e)}")
            logger.error(traceback.format_exc())

    async def broadcast(self, message: dict):
        disconnected = []
        async with self._lock:
            connections = self.active_connections.copy()
        
        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting message: {str(e)}")
                logger.error(traceback.format_exc())
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
            logger.debug("Heartbeat response sent")
        except Exception as e:
            logger.error(f"Error handling heartbeat: {str(e)}")
            logger.error(traceback.format_exc())
            self.disconnect(websocket)

manager = ConnectionManager()

# WebSocket endpoint for live signals
@app.websocket("/ws/signals")
async def websocket_endpoint(websocket: WebSocket):
    try:
        await manager.connect(websocket)
        
        while True:
            try:
                # Check if connection is still active
                if websocket.client_state.DISCONNECTED:
                    logger.info("WebSocket disconnected, breaking message loop")
                    break

                # Wait for messages from client with timeout
                try:
                    data = await asyncio.wait_for(
                        websocket.receive_json(),
                        timeout=manager.heartbeat_interval
                    )
                except asyncio.TimeoutError:
                    # No message received within timeout, continue loop
                    continue
                
                # Handle heartbeat messages
                if data.get("type") == "ping":
                    await manager.handle_heartbeat(websocket, data)
                    continue

                # Handle other message types here
                logger.debug(f"Received message: {data}")

            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON received: {str(e)}")
                try:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Invalid message format"
                    })
                except Exception:
                    break
                continue
            except WebSocketDisconnect:
                logger.info("WebSocket disconnected normally")
                break
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")
                logger.error(traceback.format_exc())
                try:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Internal server error"
                    })
                except Exception:
                    break
                continue

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected normally")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        logger.error(traceback.format_exc())
    finally:
        manager.disconnect(websocket)
        try:
            await websocket.close(code=1000, reason="Connection closed")
        except Exception as e:
            logger.error(f"Error closing WebSocket: {str(e)}")

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

@app.get("/api/trading/opportunities")
async def get_opportunities(
    min_confidence: float = 0.7,
    min_risk_reward: float = 2.0,
    min_volume: float = 1000000,
    limit: int = 10
):
    """Get top trading opportunities."""
    try:
        opportunities = await symbol_discovery.scan_opportunities()
        
        # Filter opportunities
        filtered = [
            opp for opp in opportunities
            if opp.confidence >= min_confidence
            and opp.risk_reward >= min_risk_reward
            and opp.volume_24h >= min_volume
        ]
        
        # Sort by score and limit
        filtered.sort(key=lambda x: x.score, reverse=True)
        top_opportunities = filtered[:limit]
        
        # Broadcast to WebSocket clients
        await manager.broadcast({
            "type": "opportunities_update",
            "data": {
                "opportunities": [
                    {
                        "symbol": opp.symbol,
                        "direction": opp.direction,
                        "entry_price": opp.entry_price,
                        "take_profit": opp.take_profit,
                        "stop_loss": opp.stop_loss,
                        "confidence": opp.confidence,
                        "leverage": opp.leverage,
                        "risk_reward": opp.risk_reward,
                        "volume_24h": opp.volume_24h,
                        "volatility": opp.volatility,
                        "score": opp.score,
                        "indicators": opp.indicators,
                        "reasoning": opp.reasoning
                    }
                    for opp in top_opportunities
                ],
                "total": len(filtered),
                "timestamp": datetime.now().timestamp()
            }
        })
        
        return {
            "opportunities": [
                {
                    "symbol": opp.symbol,
                    "direction": opp.direction,
                    "entry_price": opp.entry_price,
                    "take_profit": opp.take_profit,
                    "stop_loss": opp.stop_loss,
                    "confidence": opp.confidence,
                    "leverage": opp.leverage,
                    "risk_reward": opp.risk_reward,
                    "volume_24h": opp.volume_24h,
                    "volatility": opp.volatility,
                    "score": opp.score,
                    "indicators": opp.indicators,
                    "reasoning": opp.reasoning
                }
                for opp in top_opportunities
            ],
            "total": len(filtered),
            "timestamp": datetime.now().timestamp()
        }
    except Exception as e:
        logger.error(f"Error getting opportunities: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/trading/opportunities/{symbol}")
async def get_symbol_opportunity(symbol: str):
    """Get detailed opportunity information for a specific symbol."""
    try:
        opportunities = await symbol_discovery.scan_opportunities()
        symbol_opportunities = [
            opp for opp in opportunities
            if opp.symbol == symbol
        ]
        
        if not symbol_opportunities:
            raise HTTPException(
                status_code=404,
                detail=f"No opportunities found for {symbol}"
            )
            
        # Get the highest scoring opportunity
        best_opportunity = max(symbol_opportunities, key=lambda x: x.score)
        
        return {
            "symbol": best_opportunity.symbol,
            "direction": best_opportunity.direction,
            "entry_price": best_opportunity.entry_price,
            "take_profit": best_opportunity.take_profit,
            "stop_loss": best_opportunity.stop_loss,
            "confidence": best_opportunity.confidence,
            "leverage": best_opportunity.leverage,
            "risk_reward": best_opportunity.risk_reward,
            "volume_24h": best_opportunity.volume_24h,
            "volatility": best_opportunity.volatility,
            "score": best_opportunity.score,
            "indicators": best_opportunity.indicators,
            "reasoning": best_opportunity.reasoning,
            "timestamp": datetime.now().timestamp()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting symbol opportunity: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/trading/opportunities/stats")
async def get_opportunity_stats():
    """Get statistics about available trading opportunities."""
    try:
        opportunities = await symbol_discovery.scan_opportunities()
        
        # Calculate statistics
        total_opportunities = len(opportunities)
        long_opportunities = len([opp for opp in opportunities if opp.direction == 'LONG'])
        short_opportunities = len([opp for opp in opportunities if opp.direction == 'SHORT'])
        
        avg_confidence = sum(opp.confidence for opp in opportunities) / total_opportunities if total_opportunities > 0 else 0
        avg_risk_reward = sum(opp.risk_reward for opp in opportunities) / total_opportunities if total_opportunities > 0 else 0
        avg_score = sum(opp.score for opp in opportunities) / total_opportunities if total_opportunities > 0 else 0
        
        # Get top symbols by volume
        top_volume_symbols = sorted(
            opportunities,
            key=lambda x: x.volume_24h,
            reverse=True
        )[:5]
        
        # Get top opportunities by score
        top_scored_opportunities = sorted(
            opportunities,
            key=lambda x: x.score,
            reverse=True
        )[:5]
        
        return {
            "total_opportunities": total_opportunities,
            "long_opportunities": long_opportunities,
            "short_opportunities": short_opportunities,
            "avg_confidence": avg_confidence,
            "avg_risk_reward": avg_risk_reward,
            "avg_score": avg_score,
            "top_volume_symbols": [
                {
                    "symbol": opp.symbol,
                    "volume_24h": opp.volume_24h,
                    "direction": opp.direction,
                    "score": opp.score
                }
                for opp in top_volume_symbols
            ],
            "top_scored_opportunities": [
                {
                    "symbol": opp.symbol,
                    "direction": opp.direction,
                    "score": opp.score,
                    "confidence": opp.confidence,
                    "risk_reward": opp.risk_reward
                }
                for opp in top_scored_opportunities
            ],
            "timestamp": datetime.now().timestamp()
        }
    except Exception as e:
        logger.error(f"Error getting opportunity stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 