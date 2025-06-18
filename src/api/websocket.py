from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException
import asyncio
import json
import os
import logging
from dotenv import load_dotenv
from src.market_data.exchange_client import ExchangeClient
from src.opportunity.opportunity_manager import OpportunityManager
from src.market_data.websocket_client import MarketDataWebSocket
from src.api.connection_manager import ConnectionManager
from urllib.parse import parse_qs

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/web_interface.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter()

# Initialize connection manager
manager = ConnectionManager()

async def validate_api_key(api_key: str) -> bool:
    """Validate the provided API key against the environment variable."""
    expected_key = os.getenv("API_KEY")
    if not expected_key:
        logger.warning("API_KEY environment variable not set")
        return False
    return api_key == expected_key

@router.websocket("/ws")
@router.websocket("/ws/signals")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time trading signals."""
    try:
        # Accept the connection first
        await websocket.accept()
        
        # Get query parameters from the URL
        query_string = websocket.url.query
        query_params = parse_qs(query_string)
        
        # Extract and validate API key
        api_key = query_params.get('api_key', [None])[0]
        if not api_key:
            logger.warning(f"Missing API key from {websocket.client.host}")
            await websocket.close(code=1008, reason="Missing API key")
            return
            
        if not await validate_api_key(api_key):
            logger.warning(f"Invalid API key attempt from {websocket.client.host}")
            await websocket.close(code=1008, reason="Invalid API key")
            return

        # Log only the validation status
        logger.info(f"Client connected with valid API key from {websocket.client.host}")
        
        # Initialize components
        exchange_client = ExchangeClient()
        opportunity_manager = OpportunityManager(exchange_client)
        market_data_ws = MarketDataWebSocket()
        connection_manager = ConnectionManager()

        await manager.connect(websocket)
        logger.info("WebSocket connection established")
        try:
            while True:
                # Send formatted opportunities to the client
                opportunities = await opportunity_manager.get_opportunities()
                if opportunities:
                    formatted_opportunities = [
                        {
                            'symbol': opp['symbol'],
                            'side': opp['side'],
                            'entry_price': opp['entry_price'],
                            'stop_loss': opp['stop_loss'],
                            'take_profit': opp['take_profit'],
                            'confidence': opp['confidence']
                        }
                        for opp in opportunities
                    ]
                    await websocket.send_json(formatted_opportunities)
                await asyncio.sleep(1)  # Send updates every second
        except WebSocketDisconnect:
            manager.disconnect(websocket)
            logger.info("WebSocket connection closed")
    except Exception as e:
        logger.error(f"Error in WebSocket connection: {e}")
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except:
            pass
