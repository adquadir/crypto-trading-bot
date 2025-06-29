#!/usr/bin/env python3

import asyncio
import logging
import signal
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Core imports
from src.api.routes import router as base_router, set_components
from src.api.trading_routes.trading import router as trading_router
from src.api.trading_routes.flow_trading_routes import router as flow_trading_router
from src.api.trading_routes.profit_scraping_routes import router as profit_scraping_router
from src.api.trading_routes.signal_tracking_routes import router as signal_tracking_router
from src.api.trading_routes.paper_trading_routes import router as paper_trading_router, initialize_paper_trading_engine, set_paper_engine
from src.api.backtesting_routes import router as backtesting_router
from src.api.websocket import router as ws_router, set_websocket_components
from src.api.trading_routes.trading import set_trading_components
from src.utils.config import load_config
from src.monitoring.flow_trading_monitor import initialize_monitor
from src.database.database import Database

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global component references
exchange_client = None
strategy_manager = None
risk_manager = None
opportunity_manager = None
config = None
realtime_scalping_manager = None
enhanced_signal_tracker = None
integrated_profit_manager = None
paper_trading_engine = None
profit_scraping_engine = None  # NEW: Profit scraping engine

async def initialize_components():
    """Initialize all trading components in the background."""
    global exchange_client, strategy_manager, risk_manager, opportunity_manager, config, realtime_scalping_manager, enhanced_signal_tracker, integrated_profit_manager, paper_trading_engine, profit_scraping_engine
    
    try:
        logger.info("Initializing components...")
        
        # Load configuration
        config = load_config()
        
        # Initialize exchange client
        logger.info("Initializing exchange client...")
        try:
            from src.market_data.exchange_client import ExchangeClient
            exchange_client = ExchangeClient()
            logger.info("Exchange client initialized successfully")
        except Exception as e:
            logger.error(f"Exchange client initialization failed: {e}")
            exchange_client = None
        
        # Initialize strategy manager
        logger.info("Initializing strategy manager...")
        try:
            from src.strategy.strategy_manager import StrategyManager
            if exchange_client:
                strategy_manager = StrategyManager(exchange_client)
                logger.info("Strategy manager initialized successfully")
            else:
                logger.warning("Skipping strategy manager - exchange client failed")
                strategy_manager = None
        except Exception as e:
            logger.error(f"Strategy manager initialization failed: {e}")
            strategy_manager = None
        
        # Initialize risk manager
        logger.info("Initializing risk manager...")
        try:
            from src.risk.risk_manager import RiskManager
            risk_manager = RiskManager(config)
            logger.info("Risk manager initialized successfully")
        except Exception as e:
            logger.error(f"Risk manager initialization failed: {e}")
            risk_manager = None
        
        # Initialize enhanced signal tracker FIRST
        logger.info("Initializing enhanced signal tracker...")
        try:
            from src.signals.enhanced_signal_tracker import EnhancedSignalTracker
            enhanced_signal_tracker = EnhancedSignalTracker()
            await enhanced_signal_tracker.initialize()
            logger.info("Enhanced signal tracker initialized successfully")
        except Exception as e:
            logger.error(f"Enhanced signal tracker initialization failed: {e}")
            enhanced_signal_tracker = None

        # Initialize opportunity manager WITH enhanced signal tracker
        logger.info("Initializing opportunity manager...")
        try:
            from src.opportunity.opportunity_manager import OpportunityManager
            if exchange_client and strategy_manager and risk_manager:
                # Initialize WITH enhanced_signal_tracker from the start
                opportunity_manager = OpportunityManager(
                    exchange_client, 
                    strategy_manager, 
                    risk_manager, 
                    enhanced_signal_tracker=enhanced_signal_tracker
                )
                logger.info("Opportunity manager initialized successfully with enhanced signal tracker")
            else:
                logger.warning("Skipping opportunity manager - missing dependencies")
                opportunity_manager = None
        except Exception as e:
            logger.error(f"Opportunity manager initialization failed: {e}")
            opportunity_manager = None

        # Initialize realtime scalping manager
        logger.info("Initializing realtime scalping manager...")
        try:
            from src.signals.realtime_scalping_manager import RealtimeScalpingManager
            from src.api.connection_manager import ConnectionManager
            if opportunity_manager and exchange_client:
                connection_manager = ConnectionManager()
                realtime_scalping_manager = RealtimeScalpingManager(opportunity_manager, exchange_client, connection_manager)
                logger.info("Realtime scalping manager initialized successfully")
            else:
                logger.warning("Skipping realtime scalping - missing dependencies")
                realtime_scalping_manager = None
        except Exception as e:
            logger.error(f"Realtime scalping manager initialization failed: {e}")
            realtime_scalping_manager = None
        
        # Initialize profit scraping engine
        logger.info("🎯 Initializing PROFIT SCRAPING ENGINE...")
        try:
            from src.strategies.profit_scraping.profit_scraping_engine import ProfitScrapingEngine
            profit_scraping_engine = ProfitScrapingEngine(
                exchange_client=exchange_client,
                paper_trading_engine=None  # Will be set after paper trading engine is created
            )
            logger.info("🎯 Profit scraping engine initialized successfully")
        except Exception as e:
            logger.error(f"🎯 Profit scraping engine initialization failed: {e}")
            profit_scraping_engine = None
        
        # Initialize enhanced paper trading engine WITH profit scraping
        logger.info("Initializing enhanced paper trading engine...")
        try:
            # Load paper trading config with defaults
            paper_config = config.get('paper_trading', {}) if config else {}
            paper_config.setdefault('initial_balance', 10000.0)
            paper_config.setdefault('enabled', True)
            
            paper_trading_engine = await initialize_paper_trading_engine(
                {'paper_trading': paper_config}, 
                exchange_client,  # Can be None
                opportunity_manager,  # Can be None
                profit_scraping_engine  # NEW: Connect profit scraping engine
            )
            
            if paper_trading_engine:
                set_paper_engine(paper_trading_engine)
                logger.info("🟢 Enhanced paper trading engine initialized")
            else:
                logger.warning("🟡 Paper trading engine initialization failed")
                
        except Exception as e:
            logger.error(f"Paper trading engine initialization failed: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            paper_trading_engine = None
        
        # Initialize monitoring system
        logger.info("Initializing monitoring system...")
        try:
            db = Database()
            monitor = initialize_monitor(db)
            
            # Start monitoring with all components
            components = {
                'exchange_client': exchange_client,
                'strategy_manager': strategy_manager,
                'risk_manager': risk_manager,
                'opportunity_manager': opportunity_manager,
                'realtime_scalping_manager': realtime_scalping_manager,
                'enhanced_signal_tracker': enhanced_signal_tracker,
                'integrated_profit_manager': integrated_profit_manager,
                'paper_trading_engine': paper_trading_engine
            }
            
            await monitor.start_monitoring(components)
            logger.info("🟢 Monitoring system initialized")
            
        except Exception as e:
            logger.error(f"Monitoring system initialization failed: {e}")
        
        # Flow trading components are initialized via their router
        logger.info("🟢 Flow trading components ready")
        
        # Initialize integrated profit manager
        logger.info("Initializing integrated profit manager...")
        try:
            from src.strategies.flow_trading.integrated_profit_manager import IntegratedProfitManager
            if exchange_client and risk_manager:
                integrated_profit_manager = IntegratedProfitManager(exchange_client, risk_manager)
                logger.info("🟢 Integrated profit manager initialized")
            else:
                logger.warning("Skipping profit manager - missing dependencies")
                integrated_profit_manager = None
        except Exception as e:
            logger.error(f"Integrated profit manager initialization failed: {e}")
            integrated_profit_manager = None
        
        logger.info("All components initialized successfully!")
        
    except Exception as e:
        logger.error(f"Component initialization failed: {e}")
        raise e

def create_app():
    """Create and configure FastAPI application"""
    
    app = FastAPI(
        title="Crypto Trading Bot API", 
        description="Advanced cryptocurrency trading bot with real-time scalping and flow trading",
        version="2.0.0"
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers with proper prefixes
    app.include_router(base_router, prefix="/api/v1")
    app.include_router(trading_router, prefix="/api/v1/trading")
    app.include_router(flow_trading_router, prefix="/api/v1")
    app.include_router(profit_scraping_router, prefix="/api/v1")
    app.include_router(signal_tracking_router, prefix="/api/v1")
    app.include_router(paper_trading_router, prefix="/api/v1")
    app.include_router(backtesting_router, prefix="/api/v1")
    app.include_router(ws_router)

    @app.on_event("startup")
    async def startup_event():
        """Handle startup events"""
        logger.info("🚀 Starting Crypto Trading API...")
        
        # Initialize components in background
        await initialize_components()
        
        # Set component references for other modules
        set_components(
            opportunity_manager, 
            exchange_client,
            strategy_manager,
            risk_manager,
            realtime_scalping_manager,
            enhanced_signal_tracker
        )
        
        set_trading_components(
            opportunity_manager,
            exchange_client, 
            strategy_manager,
            risk_manager,
            paper_trading_engine
        )
        
        set_websocket_components(
            opportunity_manager,
            exchange_client,
            scalping_manager=realtime_scalping_manager
        )
        
        logger.info("✅ API server started successfully!")

    @app.on_event("shutdown") 
    async def shutdown_event():
        """Handle shutdown events"""
        logger.info("🛑 Shutting down API server...")
        
        # Cleanup components
        try:
            if realtime_scalping_manager:
                realtime_scalping_manager.cleanup()
        except Exception as e:
            logger.warning(f"Cleanup error: {e}")

    @app.get("/")
    async def root():
        return {"message": "Crypto Trading Bot API", "version": "2.0.0", "status": "running"}

    @app.get("/health")
    async def health_check():
        return {
            "status": "healthy",
            "components": {
                "exchange_client": exchange_client is not None,
                "strategy_manager": strategy_manager is not None,
                "risk_manager": risk_manager is not None,
                "opportunity_manager": opportunity_manager is not None,
                "realtime_scalping": realtime_scalping_manager is not None,
                "integrated_profit_manager": integrated_profit_manager is not None,
                "paper_trading_engine": paper_trading_engine is not None
            }
        }

    return app

# Create the app instance
app = create_app()
