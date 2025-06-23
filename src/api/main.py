from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import logging
import os
from dotenv import load_dotenv
from src.market_data.exchange_client import ExchangeClient
from src.strategy.strategy_manager import StrategyManager
from src.risk.risk_manager import RiskManager
from src.opportunity.opportunity_manager import OpportunityManager
from src.signals.enhanced_signal_tracker import enhanced_signal_tracker
from src.api.routes import router as base_router, set_components
from src.api.trading_routes.trading import router as trading_router
from src.api.websocket import router as ws_router, set_websocket_components
from src.api.trading_routes.trading import set_trading_components
from src.utils.config import load_config

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

# Global components
exchange_client = None
strategy_manager = None
risk_manager = None
opportunity_manager = None
config = None

async def initialize_components():
    """Initialize all trading components in the background."""
    global exchange_client, strategy_manager, risk_manager, opportunity_manager, config
    
    try:
        logger.info("Starting component initialization...")
        
        # Load configuration
        logger.info("Loading configuration...")
        config = load_config()
        logger.info("Configuration loaded successfully")
        
        # Initialize enhanced signal tracker FIRST
        logger.info("Initializing enhanced signal tracker...")
        try:
            await enhanced_signal_tracker.initialize()
            logger.info("Enhanced signal tracker initialized successfully")
        except Exception as e:
            logger.error(f"Enhanced signal tracker initialization failed: {e}")
        
        # Initialize exchange client with timeout
        logger.info("Initializing exchange client...")
        try:
            exchange_client = ExchangeClient()
            await asyncio.wait_for(exchange_client.initialize(), timeout=30.0)
            logger.info("Exchange client initialized successfully")
        except asyncio.TimeoutError:
            logger.error("Exchange client initialization timed out")
            exchange_client = None
        except Exception as e:
            logger.error(f"Exchange client initialization failed: {e}")
            exchange_client = None
        
        # Add a small delay to ensure the exchange client is fully ready
        logger.info("Waiting for exchange client to stabilize...")
        await asyncio.sleep(2)
        logger.info("Exchange client stabilized")
        
        # Initialize risk manager with timeout
        logger.info("Initializing risk manager...")
        try:
            risk_manager = RiskManager(config)
            logger.info("Risk manager initialized successfully")
        except Exception as e:
            logger.error(f"Risk manager initialization failed: {e}")
            import traceback
            logger.error(f"Risk manager traceback: {traceback.format_exc()}")
            # Create a minimal risk manager to continue
            risk_manager = None
        
        # Initialize strategy manager with timeout
        logger.info("Initializing strategy manager...")
        try:
            if exchange_client:
                strategy_manager = StrategyManager(exchange_client)
                await strategy_manager.initialize()
                logger.info("Strategy manager initialized successfully")
            else:
                logger.warning("Skipping strategy manager - exchange client failed")
                strategy_manager = None
        except Exception as e:
            logger.error(f"Strategy manager initialization failed: {e}")
            import traceback
            logger.error(f"Strategy manager traceback: {traceback.format_exc()}")
            strategy_manager = None
        
        # Initialize opportunity manager with timeout (now with enhanced signal tracker)
        logger.info("Initializing opportunity manager...")
        try:
            if exchange_client:
                opportunity_manager = OpportunityManager(exchange_client, strategy_manager, risk_manager, enhanced_signal_tracker)
                await asyncio.wait_for(opportunity_manager.initialize(), timeout=30.0)
                logger.info("Opportunity manager initialized successfully")
            else:
                logger.warning("Skipping opportunity manager - exchange client failed")
                opportunity_manager = None
        except asyncio.TimeoutError:
            logger.error("Opportunity manager initialization timed out")
            opportunity_manager = None
        except Exception as e:
            logger.error(f"Opportunity manager initialization failed: {e}")
            import traceback
            logger.error(f"Opportunity manager traceback: {traceback.format_exc()}")
            opportunity_manager = None
        
        # Pass components to WebSocket module (now including enhanced signal tracker)
        logger.info("Setting WebSocket components...")
        set_websocket_components(opportunity_manager, exchange_client, enhanced_signal_tracker)
        logger.info("WebSocket components configured successfully")
        
        # Set components in routes so they can be accessed by API endpoints
        logger.info("Setting route components...")
        set_components(opportunity_manager, exchange_client, strategy_manager, risk_manager)
        set_trading_components(opportunity_manager, exchange_client, strategy_manager, risk_manager)
        logger.info("Components set in routes")
        
        logger.info("All components initialized successfully!")
        
    except Exception as e:
        logger.error(f"Failed to initialize components: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        # Don't raise here as it would crash the API server

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown."""
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    logger.info("API server starting up...")
    
    # Initialize components directly instead of as a background task
    try:
        await initialize_components()
    except Exception as e:
        logger.error(f"Component initialization failed: {e}")
    
    logger.info("API server startup completed")
    
    yield
    
    # Cleanup on shutdown
    logger.info("API server shutting down")
    
    # Close enhanced signal tracker
    try:
        if enhanced_signal_tracker and hasattr(enhanced_signal_tracker, 'close'):
            logger.info("Closing enhanced signal tracker...")
            await enhanced_signal_tracker.close()
    except Exception as e:
        logger.error(f"Error closing enhanced signal tracker: {e}")

# Create FastAPI app with lifespan
app = FastAPI(title="Crypto Trading Bot API", lifespan=lifespan)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(base_router, prefix="/api/v1")  # Base routes (scan, health, etc.)
app.include_router(trading_router, prefix="/api/v1/trading")  # Trading routes with dynamic signals
app.include_router(ws_router)  # No prefix needed since endpoint includes /ws

@app.get("/")
async def root():
    return {"message": "Crypto Trading Bot API is running"} 