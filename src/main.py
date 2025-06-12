#!/usr/bin/env python3
import asyncio
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn
from src.api.routes import router
from src.trading_bot import trading_bot
from src.market_data.exchange_client import ExchangeClient
from src.api.connection_manager import ConnectionManager
from src.market_data.symbol_discovery import SymbolDiscovery
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="Crypto Trading Bot API")

# Initialize components
exchange_client = ExchangeClient()
symbol_discovery = SymbolDiscovery(exchange_client)
manager = ConnectionManager()

# Include API routes
app.include_router(router, prefix="/api/v1")

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

@app.on_event("startup")
async def startup_event():
    """Initialize the trading bot on startup."""
    try:
        await exchange_client.initialize()
        await trading_bot.initialize()
    except Exception as e:
        logger.error(f"Error initializing trading bot: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown the trading bot on shutdown."""
    try:
        await exchange_client.shutdown()
        await trading_bot.shutdown()
    except Exception as e:
        logger.error(f"Error shutting down trading bot: {e}")
        raise

def main():
    """Run the FastAPI application."""
    try:
        # Run the FastAPI application
        uvicorn.run(
            "src.main:app",
            host="0.0.0.0",
            port=8000,
            reload=False,
            log_level="info"
        )
    except Exception as e:
        logger.error(f"Error running application: {e}")
        raise

if __name__ == "__main__":
    main() 