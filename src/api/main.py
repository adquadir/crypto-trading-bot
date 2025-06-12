from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func
from datetime import datetime
import asyncio
import numpy as np
import logging

from src.database.database import SessionLocal, get_db
from src.models import TradingSignal, Trade
from src.api.connection_manager import ConnectionManager
from src.market_data.symbol_discovery import SymbolDiscovery
from src.market_data.exchange_client import ExchangeClient

# Initialize FastAPI app
app = FastAPI(title="Crypto Trading API")

# Initialize components
manager = ConnectionManager()
exchange_client = ExchangeClient()
symbol_discovery = SymbolDiscovery(exchange_client)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.websocket("/ws/signals")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time trading signals."""
    try:
    await manager.connect(websocket)
        logger.info(f"WebSocket connection accepted for: {websocket.client}")
    try:
        while True:
            # Get latest opportunities
                opportunities = await symbol_discovery.scan_opportunities()
                
                # Format opportunities for WebSocket
                formatted_opportunities = []
                for opp in opportunities:
                    formatted_opp = {
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
                    "reasoning": opp.reasoning,
                        "book_depth": opp.book_depth,
                        "oi_trend": opp.oi_trend,
                        "volume_trend": opp.volume_trend,
                        "slippage": opp.slippage,
                        "data_freshness": opp.data_freshness
                    }
                    formatted_opportunities.append(formatted_opp)
                
                # Send opportunities to client
                await websocket.send_json({
                    "type": "opportunities",
                    "data": formatted_opportunities,
                    "timestamp": datetime.utcnow().isoformat()
                })
            
                # Wait before sending next update
                await asyncio.sleep(1)
    except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected: {websocket.client}")
        manager.disconnect(websocket)
    except Exception as e:
            logger.error(f"Error in WebSocket connection: {str(e)}")
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Error accepting WebSocket connection: {str(e)}")
        try:
            await websocket.close()
        except:
            pass 