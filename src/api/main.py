from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import logging
import os
from dotenv import load_dotenv
from src.market_data.exchange_client import ExchangeClient
from src.strategy.strategy_manager import StrategyManager
from src.risk.risk_manager import RiskManager
from src.opportunity.opportunity_manager import OpportunityManager
from src.api.routes import router as trading_router
from src.api.websocket import router as ws_router

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/api.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

app = FastAPI(title="Crypto Trading Bot API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
exchange_client = ExchangeClient()
strategy_manager = StrategyManager(exchange_client)
risk_manager = RiskManager(exchange_client)
opportunity_manager = OpportunityManager(exchange_client, strategy_manager, risk_manager)

# Include routers
app.include_router(trading_router, prefix="/api/v1/trading")
app.include_router(ws_router)  # No prefix needed since endpoint includes /ws

@app.on_event("startup")
async def startup_event():
    """Initialize components on startup."""
    try:
        # Create logs directory if it doesn't exist
        os.makedirs('logs', exist_ok=True)
        
        # Initialize exchange client
        await exchange_client.initialize()
        logger.info("Exchange client initialized")
        
        # Initialize strategy manager and activate strategies
        await strategy_manager.initialize()
        default_strategies = ['scalping', 'swing']
        for strategy_name in default_strategies:
            if strategy_manager.activate_strategy(strategy_name):
                logger.info(f"Activated strategy: {strategy_name}")
            else:
                logger.warning(f"Failed to activate strategy: {strategy_name}")
        
        # Initialize opportunity manager
        await opportunity_manager.initialize()
        logger.info("Opportunity manager initialized")
        
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    try:
        logger.info("API server shutting down")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

@app.get("/")
async def root():
    return {"message": "Crypto Trading Bot API is running"} 