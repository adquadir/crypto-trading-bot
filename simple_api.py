#!/usr/bin/env python3

import asyncio
import logging
import signal
import sys
import uvicorn
from pathlib import Path
from contextlib import asynccontextmanager

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.api.main import app
from src.api.websocket import set_websocket_components
from src.opportunity.opportunity_manager import OpportunityManager
from src.signals.realtime_scalping_manager import RealtimeScalpingManager
from src.api.trading_routes.flow_trading_routes import initialize_flow_trading_components
from src.market_data.exchange_client import ExchangeClient
from src.risk.risk_manager import RiskManager
from src.strategy.strategy_manager import StrategyManager
from src.utils.config import load_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global components
opportunity_manager = None
realtime_scalping_manager = None
flow_manager = None
grid_engine = None

async def initialize_all_components():
    """Initialize all trading components"""
    global opportunity_manager, realtime_scalping_manager, flow_manager, grid_engine
    
    try:
        logger.info("🚀 Initializing trading components...")
        
        # Initialize exchange client first
        logger.info("Initializing exchange client...")
        exchange_client = ExchangeClient()
        logger.info("✅ Exchange client initialized")
        
        # Initialize strategy manager
        logger.info("Initializing strategy manager...")
        strategy_manager = StrategyManager(exchange_client)
        logger.info("✅ Strategy manager initialized")
        
        # Initialize risk manager
        logger.info("Initializing risk manager...")
        config = load_config()
        risk_manager = RiskManager(config)
        logger.info("✅ Risk manager initialized")
        
        # Initialize opportunity manager with required dependencies
        logger.info("Initializing opportunity manager...")
        opportunity_manager = OpportunityManager(exchange_client, strategy_manager, risk_manager)
        logger.info("✅ Opportunity manager initialized")
        
        # Initialize realtime scalping manager
        logger.info("Initializing realtime scalping manager...")
        from src.api.connection_manager import ConnectionManager
        connection_manager = ConnectionManager()
        realtime_scalping_manager = RealtimeScalpingManager(opportunity_manager, exchange_client, connection_manager)
        logger.info("✅ Realtime scalping manager initialized")
        
        # Initialize flow trading components
        logger.info("Initializing flow trading components...")
        try:
            flow_success = await initialize_flow_trading_components(
                risk_manager, 
                exchange_client, 
                realtime_scalping_manager
            )
            
            if flow_success:
                logger.info("✅ Flow trading components initialized")
                
                # Get references to initialized components
                from src.api.trading_routes.flow_trading_routes import get_flow_manager
                flow_manager = get_flow_manager()
                logger.info(f"Flow manager retrieved: {flow_manager is not None}")
                
            else:
                logger.warning("⚠️ Flow trading initialization failed")
                
        except Exception as e:
            logger.error(f"❌ Flow trading initialization error: {e}")
        
        # Set WebSocket dependencies
        set_websocket_components(
            opportunity_manager, 
            realtime_scalping_manager
        )
        
        logger.info("✅ All components initialized successfully!")
        
    except Exception as e:
        logger.error(f"❌ Component initialization failed: {e}")
        raise

@asynccontextmanager
async def lifespan(app):
    """Manage application lifespan"""
    try:
        # Startup
        await initialize_all_components()
        logger.info("🚀 API server ready!")
        yield
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        raise
    finally:
        # Shutdown
        logger.info("🛑 Shutting down API server...")
        
        # Cleanup components
        try:
            if realtime_scalping_manager:
                realtime_scalping_manager.cleanup()
                
        except Exception as e:
            logger.warning(f"Cleanup error: {e}")

# Apply lifespan to app
app.router.lifespan_context = lifespan

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)

def main():
    """Main entry point"""
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("🚀 Starting Crypto Trading API...")
    
    try:
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            log_level="info",
            access_log=True,
            lifespan="on"
        )
    except Exception as e:
        logger.error(f"❌ Server failed to start: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 