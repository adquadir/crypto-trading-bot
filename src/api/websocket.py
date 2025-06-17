from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
import os
import logging
from dotenv import load_dotenv
from src.market_data.exchange_client import ExchangeClient
from src.market_data.opportunity_analyzer import OpportunityAnalyzer
from src.api.websocket_client import WebsocketClient
from src.api.connection_manager import ConnectionManager

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

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize connection manager
manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time trading signals."""
    try:
        # Verify API key
        api_key = os.getenv("API_KEY")
        if not api_key:
            logger.warning("API_KEY environment variable not set")
            await websocket.close(code=1008, reason="API key not configured")
            return

        # Log only the length and validation status, never the actual key
        logger.info(f"Client connected with API key of length {len(api_key)}")
        
        # Initialize components
        exchange_client = ExchangeClient()
        opportunity_analyzer = OpportunityAnalyzer()
        websocket_client = WebsocketClient()
        connection_manager = ConnectionManager()

        await manager.connect(websocket)
        logger.info("WebSocket connection established")
        try:
            while True:
                # Send formatted opportunities to the client
                opportunities = await opportunity_analyzer.get_opportunities()
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
