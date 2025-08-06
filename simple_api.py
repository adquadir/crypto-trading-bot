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
from src.api.routes import set_components
from src.api.trading_routes.paper_trading_routes import initialize_paper_trading_engine, set_paper_engine
from src.opportunity.opportunity_manager import OpportunityManager
from src.signals.realtime_scalping_manager import RealtimeScalpingManager
from src.signals.enhanced_signal_tracker import EnhancedSignalTracker
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
enhanced_signal_tracker = None
flow_manager = None
grid_engine = None
paper_trading_engine = None

async def initialize_all_components():
    """Initialize all trading components"""
    global opportunity_manager, realtime_scalping_manager, enhanced_signal_tracker, flow_manager, grid_engine, paper_trading_engine
    
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
        
        # Initialize enhanced signal tracker
        logger.info("Initializing enhanced signal tracker...")
        enhanced_signal_tracker = EnhancedSignalTracker()
        # Initialize in background to avoid blocking
        asyncio.create_task(enhanced_signal_tracker.initialize())
        logger.info("✅ Enhanced signal tracker initialized (async)")
        
        # Attach enhanced signal tracker to opportunity manager
        if opportunity_manager:
            opportunity_manager.enhanced_signal_tracker = enhanced_signal_tracker
            logger.info("✅ Enhanced signal tracker attached to opportunity manager")
        
        # Initialize realtime scalping manager
        logger.info("Initializing realtime scalping manager...")
        from src.api.connection_manager import ConnectionManager
        connection_manager = ConnectionManager()
        realtime_scalping_manager = RealtimeScalpingManager(opportunity_manager, exchange_client, connection_manager)
        # Start in background to avoid blocking HTTP server startup
        asyncio.create_task(realtime_scalping_manager.start())
        logger.info("✅ Realtime scalping manager initialized and starting (async)")
        
        # Initialize paper trading engine with PROFIT SCRAPING INTEGRATION (RULE COMPLIANT)
        logger.info("Initializing enhanced paper trading engine with PROFIT SCRAPING...")
        try:
            # Load paper trading config with defaults
            paper_config = config.get('paper_trading', {}) if config else {}
            paper_config.setdefault('initial_balance', 10000.0)
            paper_config.setdefault('enabled', True)
            
            # RULE COMPLIANT: Initialize paper trading engine
            paper_trading_engine = await initialize_paper_trading_engine(
                config={'paper_trading': paper_config},
                exchange_client=exchange_client,
                flow_trading_strategy='adaptive'
            )
            
            if paper_trading_engine:
                logger.info("✅ Enhanced paper trading engine initialized")
                
                # CRITICAL: Initialize and connect profit scraping engine (RULE COMPLIANT)
                logger.info("🎯 Initializing profit scraping engine (MAIN SIGNAL SOURCE)...")
                try:
                    from src.strategies.profit_scraping.profit_scraping_engine import ProfitScrapingEngine
                    
                    # Initialize profit scraping engine with paper trading connection
                    profit_scraping_engine = ProfitScrapingEngine(
                        exchange_client=exchange_client,
                        paper_trading_engine=paper_trading_engine,
                        real_trading_engine=None  # Paper trading only
                    )
                    
                    # Connect profit scraping to paper trading engine
                    paper_trading_engine.connect_profit_scraping_engine(profit_scraping_engine)
                    logger.info("✅ Profit scraping engine connected to paper trading (RULE COMPLIANT)")
                    
                    # RULE COMPLIANCE: Start profit scraping with active monitoring
                    logger.info("🎯 Starting profit scraping engine (MAIN SIGNAL SOURCE)...")
                    symbols_to_monitor = [
                        'BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'SOLUSDT', 'XRPUSDT', 
                        'BCHUSDT', 'LTCUSDT', 'TRXUSDT', 'ETCUSDT', 'LINKUSDT',
                        'XLMUSDT', 'XMRUSDT', 'DASHUSDT', 'ZECUSDT', 'XTZUSDT',
                        'BNBUSDT', 'ATOMUSDT', 'ONTUSDT', 'IOTAUSDT', 'BATUSDT', 'VETUSDT'
                    ]
                    
                    profit_scraping_started = await profit_scraping_engine.start_scraping(symbols_to_monitor)
                    
                    if profit_scraping_started:
                        logger.info("✅ RULE COMPLIANT: Profit scraping engine started and active")
                        logger.info("✅ RULE COMPLIANT: Profit scraping is now the main source of signals")
                    else:
                        logger.error("❌ RULE VIOLATION: Failed to start profit scraping engine!")
                        logger.error("❌ RULE VIOLATION: Profit scraping should be the main source of signals!")
                    
                except Exception as profit_error:
                    logger.error(f"❌ RULE VIOLATION: Failed to initialize profit scraping engine: {profit_error}")
                    logger.error("❌ RULE VIOLATION: Paper trading will not have proper signal source!")
                
                # Connect opportunity manager as secondary/fallback source
                if opportunity_manager:
                    paper_trading_engine.connect_opportunity_manager(opportunity_manager)
                    logger.info("✅ Opportunity manager connected as fallback source")
                
                # Store globally
                set_paper_engine(paper_trading_engine)
                logger.info("✅ Paper trading engine set globally")
                
            else:
                logger.error("❌ Failed to initialize enhanced paper trading engine")
                
        except Exception as paper_error:
            logger.error(f"❌ Paper trading engine initialization error: {paper_error}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
        
        # Flow trading components are initialized via their router
        logger.info("✅ Flow trading components ready")
        
        # Set WebSocket dependencies - PROPERLY pass all components
        set_websocket_components(
            opportunity_manager, 
            exchange_client,
            enhanced_signal_tracker,
            realtime_scalping_manager,
            flow_manager,
            grid_engine
        )
        
        # Set components to routes
        set_components(
            opportunity_manager, 
            exchange_client,
            strategy_manager,
            risk_manager,
            realtime_scalping_manager,
            enhanced_signal_tracker
        )
        
        logger.info("✅ All components initialized successfully!")
        
        # Auto-start paper trading after all components are ready
        logger.info("🚀 Auto-starting paper trading...")
        try:
            # Wait a moment for everything to be fully ready
            await asyncio.sleep(2)
            
            # Start paper trading directly without HTTP request
            if paper_trading_engine and not paper_trading_engine.is_running:
                await paper_trading_engine.start()
                logger.info("✅ Paper trading auto-started successfully!")
            elif paper_trading_engine and paper_trading_engine.is_running:
                logger.info("✅ Paper trading already running!")
            else:
                logger.warning("⚠️ Paper trading engine not available for auto-start")
        except Exception as e:
            logger.warning(f"⚠️ Paper trading auto-start error: {e}")
        
    except Exception as e:
        logger.error(f"❌ Component initialization failed: {e}")
        raise

@asynccontextmanager
async def lifespan(app):
    """Manage application lifespan"""
    try:
        # Startup - initialize components in background to avoid blocking HTTP server
        asyncio.create_task(initialize_all_components())
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
                await realtime_scalping_manager.stop()
            if enhanced_signal_tracker:
                await enhanced_signal_tracker.close()
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
