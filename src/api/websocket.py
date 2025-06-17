from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
import logging
import asyncio
from datetime import datetime
import os
from dotenv import load_dotenv

from src.api.connection_manager import ConnectionManager
from src.market_data.symbol_discovery import SymbolDiscovery
from src.market_data.exchange_client import ExchangeClient

load_dotenv()

logger = logging.getLogger(__name__)

# Initialize connection manager
manager = ConnectionManager()

# Initialize exchange client and symbol discovery
exchange_client = ExchangeClient()
symbol_discovery = SymbolDiscovery(exchange_client)

# Initialize components
async def initialize_components():
    await exchange_client.initialize()
    await symbol_discovery.initialize()

# Create initialization task
asyncio.create_task(initialize_components())

router = APIRouter()

API_KEY = os.getenv("API_KEY")
if not API_KEY:
    logger.warning("API_KEY environment variable is not set! WebSocket authentication will fail.")

@router.websocket("/ws/signals")
async def websocket_endpoint(websocket: WebSocket, api_key: str = Query(None)):
    """WebSocket endpoint for real-time trading signals."""
    try:
        # Verify API key
        logger.info(f"Received API key from client: '{api_key}'")
        logger.info(f"Received API key type: {type(api_key)}")
        logger.info(f"Received API key length: {len(api_key) if api_key else 0}")
        logger.info(f"Expected API key: '{API_KEY}'")
        logger.info(f"Expected API key type: {type(API_KEY)}")
        logger.info(f"Expected API key length: {len(API_KEY)}")

        if not api_key:
            logger.warning("No API key provided")
            await websocket.close(code=4003, reason="No API key provided")
            return

        # Trim whitespace and newlines from received API key
        api_key = api_key.strip()
        logger.info(f"Trimmed API key: '{api_key}'")
        logger.info(f"Trimmed API key length: {len(api_key)}")

        if api_key != API_KEY:
            logger.warning(f"API key mismatch. Received: '{api_key}', Expected: '{API_KEY}'")
            logger.warning(f"API key comparison result: {api_key == API_KEY}")
            await websocket.close(code=4003, reason="Invalid API key")
            return

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
