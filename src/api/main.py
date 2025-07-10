#!/usr/bin/env python3

import asyncio
import logging
import signal
import sys
import time
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
from src.api.trading_routes.real_trading_routes import router as real_trading_router
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
profit_scraping_engine = None

async def initialize_exchange_client():
    """Initialize exchange client - either works or fails."""
    logger.info("🔗 Initializing exchange client...")
    
    from src.market_data.exchange_client import ExchangeClient
    
    exchange_client = ExchangeClient()
    
    # Test the connection
    try:
        if hasattr(exchange_client, 'get_ticker'):
            await exchange_client.get_ticker('BTCUSDT')
        elif hasattr(exchange_client, 'fetch_ticker'):
            await exchange_client.fetch_ticker('BTC/USDT')
    except Exception as e:
        logger.error(f"Exchange client connection test failed: {e}")
        raise
    
    logger.info("✅ Exchange client initialized successfully")
    return exchange_client

async def initialize_strategy_manager(exchange_client):
    """Initialize strategy manager - either works or fails."""
    logger.info("🎯 Initializing strategy manager...")
    
    from src.strategy.strategy_manager import StrategyManager
    
    if not exchange_client:
        raise ValueError("Exchange client is required for strategy manager")
        
    strategy_manager = StrategyManager(exchange_client)
    logger.info("✅ Strategy manager initialized successfully")
    return strategy_manager

async def initialize_risk_manager(config):
    """Initialize risk manager - either works or fails."""
    logger.info("🛡️ Initializing risk manager...")
    
    from src.risk.risk_manager import RiskManager
    
    risk_manager = RiskManager(config)
    logger.info("✅ Risk manager initialized successfully")
    return risk_manager

async def initialize_signal_tracker():
    """Initialize enhanced signal tracker - either works or fails."""
    logger.info("📡 Initializing enhanced signal tracker...")
    
    from src.signals.enhanced_signal_tracker import EnhancedSignalTracker
    
    tracker = EnhancedSignalTracker()
    logger.info("✅ Enhanced signal tracker initialized successfully")
    return tracker

async def initialize_opportunity_manager(exchange_client, strategy_manager, risk_manager, signal_tracker):
    """Initialize opportunity manager - either works or fails."""
    logger.info("🎯 Initializing opportunity manager...")
    
    from src.opportunity.opportunity_manager import OpportunityManager
    
    # Validate all required components
    if not all([exchange_client, strategy_manager, risk_manager, signal_tracker]):
        raise ValueError("All components are required for opportunity manager")
        
    opportunity_manager = OpportunityManager(
        exchange_client, 
        strategy_manager, 
        risk_manager, 
        signal_tracker
    )
    
    logger.info("✅ Opportunity manager initialized successfully")
    return opportunity_manager

async def initialize_profit_scraping_engine(exchange_client):
    """Initialize profit scraping engine - either works or fails."""
    logger.info("🎯 Initializing profit scraping engine...")
    
    from src.strategies.profit_scraping.profit_scraping_engine import ProfitScrapingEngine
    
    if not exchange_client:
        raise ValueError("Exchange client is required for profit scraping engine")
        
    profit_engine = ProfitScrapingEngine(
        exchange_client=exchange_client,
        paper_trading_engine=None  # Will be connected later
    )
    
    logger.info("✅ Profit scraping engine initialized successfully")
    return profit_engine

async def initialize_paper_trading_engine(config, exchange_client, opportunity_manager, profit_scraping_engine):
    """Initialize enhanced paper trading engine - either works or fails."""
    logger.info("🚀 Initializing enhanced paper trading engine...")
    
    from src.trading.enhanced_paper_trading_engine import EnhancedPaperTradingEngine
    
    # Validate all required components
    if not all([config, exchange_client, opportunity_manager, profit_scraping_engine]):
        raise ValueError("All components are required for paper trading engine")
        
    paper_engine = EnhancedPaperTradingEngine(
        config=config,
        exchange_client=exchange_client
    )
    
    # Connect all components
    logger.info("🔗 Connecting opportunity manager to paper trading engine...")
    paper_engine.connect_opportunity_manager(opportunity_manager)
    
    logger.info("🔗 Connecting profit scraping engine to paper trading engine...")
    paper_engine.connect_profit_scraping_engine(profit_scraping_engine)
    
    # Start the paper trading engine
    await paper_engine.start()
    
    logger.info("✅ Enhanced paper trading engine initialized with all connections")
    return paper_engine

async def initialize_components():
    """Initialize all trading components - either works or fails."""
    global exchange_client, strategy_manager, risk_manager, opportunity_manager, config, realtime_scalping_manager, enhanced_signal_tracker, integrated_profit_manager, paper_trading_engine, profit_scraping_engine
    
    logger.info("🚀 Starting component initialization...")
    
    # Load configuration
    config = load_config()
    
    # Initialize exchange client
    exchange_client = await initialize_exchange_client()
    
    # Initialize strategy manager
    strategy_manager = await initialize_strategy_manager(exchange_client)
    
    # Initialize risk manager
    risk_manager = await initialize_risk_manager(config)
    
    # Initialize enhanced signal tracker
    enhanced_signal_tracker = await initialize_signal_tracker()

    # Initialize opportunity manager
    opportunity_manager = await initialize_opportunity_manager(
        exchange_client, strategy_manager, risk_manager, enhanced_signal_tracker
    )

    # Initialize realtime scalping manager
    logger.info("Initializing realtime scalping manager...")
    from src.signals.realtime_scalping_manager import RealtimeScalpingManager
    from src.api.connection_manager import ConnectionManager
    
    if not all([opportunity_manager, exchange_client]):
        raise ValueError("Missing dependencies for realtime scalping manager")
        
    connection_manager = ConnectionManager()
    realtime_scalping_manager = RealtimeScalpingManager(opportunity_manager, exchange_client, connection_manager)
    logger.info("✅ Realtime scalping manager initialized successfully")
    
    # Initialize profit scraping engine
    profit_scraping_engine = await initialize_profit_scraping_engine(exchange_client)
    
    # Initialize enhanced paper trading engine
    paper_trading_engine = await initialize_paper_trading_engine(
        config, exchange_client, opportunity_manager, profit_scraping_engine
    )
    
    # Initialize monitoring system
    logger.info("Initializing monitoring system...")
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
    logger.info("✅ Monitoring system initialized")
    
    # Initialize integrated profit manager
    logger.info("Initializing integrated profit manager...")
    from src.strategies.flow_trading.integrated_profit_manager import IntegratedProfitManager
    
    if not all([exchange_client, risk_manager]):
        raise ValueError("Missing dependencies for integrated profit manager")
        
    integrated_profit_manager = IntegratedProfitManager(exchange_client, risk_manager)
    logger.info("✅ Integrated profit manager initialized")
    
    # Final validation
    await validate_all_components()
    
    logger.info("🎉 ALL COMPONENTS INITIALIZED SUCCESSFULLY!")

async def validate_all_components():
    """Final validation that all components are properly connected and working."""
    global exchange_client, strategy_manager, risk_manager, opportunity_manager, enhanced_signal_tracker, paper_trading_engine, profit_scraping_engine
    
    logger.info("🔍 Running final component validation...")
    
    # Validate all components exist
    required_components = {
        'exchange_client': exchange_client,
        'strategy_manager': strategy_manager,
        'risk_manager': risk_manager,
        'opportunity_manager': opportunity_manager,
        'enhanced_signal_tracker': enhanced_signal_tracker,
        'profit_scraping_engine': profit_scraping_engine,
        'paper_trading_engine': paper_trading_engine
    }
    
    for name, component in required_components.items():
        if not component:
            raise ValueError(f"{name} validation failed - component is None")
        logger.info(f"✅ {name} validated")
    
    # Validate connections
    if not (hasattr(paper_trading_engine, 'opportunity_manager') and paper_trading_engine.opportunity_manager):
        raise ValueError("Paper trading <-> Opportunity manager connection failed")
    logger.info("✅ Paper trading <-> Opportunity manager connection validated")
    
    if not (hasattr(paper_trading_engine, 'profit_scraping_engine') and paper_trading_engine.profit_scraping_engine):
        raise ValueError("Paper trading <-> Profit scraping connection failed")
    logger.info("✅ Paper trading <-> Profit scraping connection validated")
    
    logger.info("🎯 ALL COMPONENT VALIDATIONS PASSED!")

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
    app.include_router(real_trading_router, prefix="/api/v1")
    app.include_router(backtesting_router, prefix="/api/v1")
    app.include_router(ws_router)

    @app.on_event("startup")
    async def startup_event():
        """Handle startup events"""
        logger.info("🚀 Starting Crypto Trading API...")
        
        # Initialize components - will fail if any component fails
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
        
        # Set paper trading engine for routes
        set_paper_engine(paper_trading_engine)
        
        logger.info("✅ API server started successfully!")

    @app.on_event("shutdown") 
    async def shutdown_event():
        """Handle shutdown events"""
        logger.info("🛑 Shutting down API server...")
        
        # Cleanup components
        if realtime_scalping_manager:
            realtime_scalping_manager.cleanup()
        if paper_trading_engine and hasattr(paper_trading_engine, 'stop'):
            await paper_trading_engine.stop()
        if profit_scraping_engine and hasattr(profit_scraping_engine, 'stop_profit_scraping'):
            await profit_scraping_engine.stop_profit_scraping()

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
                "paper_trading_engine": paper_trading_engine is not None,
                "profit_scraping_engine": profit_scraping_engine is not None,
                "enhanced_signal_tracker": enhanced_signal_tracker is not None
            }
        }

    return app

# Create the app instance
app = create_app()
