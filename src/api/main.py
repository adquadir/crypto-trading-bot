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

async def initialize_profit_scraping_engine(exchange_client, paper_trading_engine=None):
    """Initialize profit scraping engine for PAPER TRADING - safe mode."""
    logger.info("🎯 Initializing profit scraping engine for PAPER TRADING...")
    
    try:
        from src.strategies.profit_scraping.profit_scraping_engine import ProfitScrapingEngine
        logger.info("✅ Successfully imported ProfitScrapingEngine")
    except ImportError as e:
        logger.error(f"❌ Failed to import ProfitScrapingEngine: {e}")
        raise
    
    if not exchange_client:
        logger.error("❌ Exchange client is None - cannot initialize profit scraping engine")
        raise ValueError("Exchange client is required for profit scraping engine")
        
    logger.info("🔧 Creating ProfitScrapingEngine instance...")
    
    try:
        # Initialize with PAPER TRADING ENGINE (safe mode)
        profit_engine = ProfitScrapingEngine(
            exchange_client=exchange_client,
            paper_trading_engine=paper_trading_engine,  # Connect to paper trading
            real_trading_engine=None  # No real trading - safe mode
        )
        
        logger.info("✅ Profit scraping engine initialized for PAPER TRADING (safe mode)")
        logger.info(f"✅ Profit scraping engine active: {profit_engine.active}")
        logger.info(f"✅ Profit scraping engine max_symbols: {profit_engine.max_symbols}")
        
        return profit_engine
        
    except Exception as e:
        logger.error(f"❌ Failed to create ProfitScrapingEngine instance: {e}")
        logger.error(f"❌ Error type: {type(e)}")
        import traceback
        logger.error(f"❌ Full traceback: {traceback.format_exc()}")
        raise

async def initialize_paper_trading_engine(config, exchange_client, opportunity_manager, profit_scraping_engine):
    """Initialize enhanced paper trading engine with graceful fallback handling."""
    logger.info("🚀 Initializing enhanced paper trading engine...")
    
    from src.trading.enhanced_paper_trading_engine import EnhancedPaperTradingEngine
    
    # Validate minimum required components
    if not all([config, exchange_client]):
        raise ValueError("Config and exchange client are required for paper trading engine")
    
    # Warn about missing components but don't fail
    if not opportunity_manager:
        logger.warning("⚠️ Opportunity manager not available - some signal sources will be disabled")
    if not profit_scraping_engine:
        logger.warning("⚠️ Profit scraping engine not available - profit scraping signals will be disabled")
        
    paper_engine = EnhancedPaperTradingEngine(
        config=config,
        exchange_client=exchange_client
    )
    
    # Connect available components
    if opportunity_manager:
        logger.info("🔗 Connecting opportunity manager to paper trading engine...")
        paper_engine.connect_opportunity_manager(opportunity_manager)
    else:
        logger.warning("⚠️ Skipping opportunity manager connection - not available")
    
    if profit_scraping_engine:
        logger.info("🔗 Connecting profit scraping engine to paper trading engine...")
        paper_engine.connect_profit_scraping_engine(profit_scraping_engine)
    else:
        logger.warning("⚠️ Skipping profit scraping engine connection - not available")
    
    # Start the paper trading engine
    try:
        await paper_engine.start()
        logger.info("✅ Enhanced paper trading engine started successfully")
    except Exception as e:
        logger.error(f"❌ Failed to start paper trading engine: {e}")
        # Don't raise - allow system to continue with limited functionality
        logger.warning("⚠️ Paper trading engine will run with limited functionality")
    
    logger.info("✅ Enhanced paper trading engine initialized")
    return paper_engine

async def initialize_components():
    """Initialize all trading components with RULE COMPLIANT Pure Profit Scraping Mode enforcement."""
    global exchange_client, strategy_manager, risk_manager, opportunity_manager
    global enhanced_signal_tracker, paper_trading_engine, profit_scraping_engine, realtime_scalping_manager
    
    logger.info("🎯 RULE COMPLIANT: Initializing components in Pure Profit Scraping Mode")
    
    # RULE ENFORCEMENT: Set environment variables to ensure Pure Mode
    import os
    os.environ['PURE_PROFIT_SCRAPING_MODE'] = 'true'
    os.environ['PROFIT_SCRAPING_PRIMARY'] = 'true'
    
    try:
        # Load configuration with RULE COMPLIANT defaults
        config = load_config()
        
        # FORCE Pure Profit Scraping Mode configuration
        config.setdefault('signal_sources', {})
        config['signal_sources'].update({
            'pure_profit_scraping_mode': True,         # RULE COMPLIANT: Default ON
            'profit_scraping_primary': True,           # RULE COMPLIANT: Primary source
            'allow_opportunity_fallback': False,       # RULE COMPLIANT: No fallbacks
            'allow_flow_trading_fallback': False,      # RULE COMPLIANT: No fallbacks
            'adaptive_thresholds': True,
            'multi_timeframe_analysis': True,
            'expanded_symbol_pool': True
        })
        
        # FORCE Paper trading RULE COMPLIANT settings
        config.setdefault('paper_trading', {})
        config['paper_trading'].update({
            'mode': 'pure_profit_scraping',      # RULE COMPLIANT: Mode
            'initial_balance': 10000.0,          # RULE COMPLIANT: $10,000 virtual starting capital
            'risk_per_trade_pct': 0.05,          # RULE COMPLIANT: 5% = $500 per trade
            'max_positions': 20,                 # RULE COMPLIANT: 20 trades starting
            'leverage': 10.0,                    # RULE COMPLIANT: 10x leverage
            'primary_target_dollars': 18.0,      # RULE COMPLIANT: $18 take profit (fee included)
            'absolute_floor_dollars': 15.0,      # RULE COMPLIANT: $15 floor on reversal
            'stop_loss_dollars': 18.0,           # RULE COMPLIANT: $18 stop loss (fee included)
            'pure_3_rule_mode': True,            # RULE COMPLIANT: Pure 3-rule mode
            'enabled': True
        })
        
        logger.info("✅ RULE COMPLIANT: Configuration enforced for Pure Profit Scraping Mode")

        # Initialize exchange client first
        exchange_client = ExchangeClient()
        if not exchange_client:
            raise ValueError("Failed to initialize exchange client - CRITICAL")
        logger.info("✅ Exchange client initialized")

        # Initialize strategy manager
        try:
            strategy_manager = StrategyManager(config)
            logger.info("✅ Strategy manager initialized")
        except Exception as e:
            logger.error(f"❌ Strategy manager initialization failed: {e}")
            strategy_manager = None

        # Initialize risk manager
        try:
            risk_manager = RiskManager(config)
            logger.info("✅ Risk manager initialized")
        except Exception as e:
            logger.error(f"❌ Risk manager initialization failed: {e}")
            risk_manager = None
            
        # Initialize enhanced signal tracker
        try:
            from src.signals.enhanced_signal_tracker import EnhancedSignalTracker
            enhanced_signal_tracker = EnhancedSignalTracker()
            logger.info("✅ Enhanced signal tracker initialized")
        except Exception as e:
            logger.error(f"❌ Enhanced signal tracker initialization failed: {e}")
            enhanced_signal_tracker = None

        # Initialize opportunity manager (FALLBACK ONLY - Not primary in Pure Mode)
        try:
            opportunity_manager = await initialize_opportunity_manager(exchange_client, strategy_manager, risk_manager, enhanced_signal_tracker)
            logger.info("✅ Opportunity manager initialized (FALLBACK ONLY)")
        except Exception as e:
            logger.error(f"❌ Opportunity manager initialization failed: {e}")
            logger.warning("⚠️ Continuing without opportunity manager - Pure Profit Scraping Mode doesn't require it")
            opportunity_manager = None

        # Initialize realtime scalping manager
        try:
            from src.api.realtime_scalping_manager import RealtimeScalpingManager
            
            realtime_scalping_manager = RealtimeScalpingManager(
                exchange_client=exchange_client,
                opportunity_manager=opportunity_manager
            )
            logger.info("✅ Realtime scalping manager initialized")
            
        except ImportError:
            logger.warning("⚠️ RealtimeScalpingManager not available - continuing without it")
            realtime_scalping_manager = None
        except Exception as e:
            logger.error(f"❌ Realtime scalping manager initialization failed: {e}")
            logger.warning("⚠️ Continuing without realtime scalping manager")

            realtime_scalping_manager = None
        
        # CRITICAL: Initialize paper trading engine FIRST (without profit scraping connection)
        try:
            paper_trading_engine = await initialize_paper_trading_engine(
                config, exchange_client, opportunity_manager, None  # No profit scraping engine yet
            )
            logger.info("✅ Paper trading engine initialized")
            
        except Exception as e:
            logger.error(f"❌ CRITICAL: Paper trading engine initialization failed: {e}")
            raise ValueError("Paper trading engine is REQUIRED for Pure Profit Scraping Mode")

        # CRITICAL: Initialize profit scraping engine - MUST SUCCEED
        try:
            logger.info("🎯 CRITICAL: Starting profit scraping engine initialization...")
            logger.info(f"📊 Exchange client available: {exchange_client is not None}")
            logger.info(f"📊 Paper trading engine available: {paper_trading_engine is not None}")
            
            profit_scraping_engine = await initialize_profit_scraping_engine(
                exchange_client, paper_trading_engine
            )
            
            if not profit_scraping_engine:
                raise ValueError("Profit scraping engine initialization returned None")
                
            # CRITICAL: Connect paper trading engine to profit scraping engine (bidirectional)
            if paper_trading_engine and profit_scraping_engine:
                paper_trading_engine.profit_scraping_engine = profit_scraping_engine
                
                # CRITICAL: Start profit scraping immediately
                symbols_to_monitor = [
                    'BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'SOLUSDT', 'XRPUSDT', 
                    'BCHUSDT', 'LTCUSDT', 'TRXUSDT', 'ETCUSDT', 'LINKUSDT',
                    'XLMUSDT', 'XMRUSDT', 'DASHUSDT', 'ZECUSDT', 'XTZUSDT',
                    'BNBUSDT', 'ATOMUSDT', 'ONTUSDT', 'IOTAUSDT', 'BATUSDT', 'VETUSDT'
                ]
                
                scraping_started = await profit_scraping_engine.start_scraping(symbols_to_monitor)
                
                if not scraping_started:
                    raise ValueError("Failed to start profit scraping - CRITICAL")
                    
                if not profit_scraping_engine.active:
                    raise ValueError("Profit scraping engine is not active after start - CRITICAL")
                
                logger.info("✅ CRITICAL: Bidirectional connection established and profit scraping ACTIVE")
                
                # Validate profit scraping is actually working
                if len(profit_scraping_engine.monitored_symbols) == 0:
                    raise ValueError("Profit scraping engine has no monitored symbols - CRITICAL")
                    
                logger.info(f"✅ CRITICAL: Profit scraping monitoring {len(profit_scraping_engine.monitored_symbols)} symbols")
                
            else:
                raise ValueError(f"Cannot establish bidirectional connection - paper_trading_engine: {paper_trading_engine is not None}, profit_scraping_engine: {profit_scraping_engine is not None}")
                
        except Exception as e:
            logger.error(f"❌ CRITICAL: Profit scraping engine initialization failed: {e}")
            raise ValueError(f"RULE VIOLATION: Profit scraping engine MUST be active in Pure Profit Scraping Mode: {e}")

        # FINAL VALIDATION: Ensure profit scraping is active
        if profit_scraping_engine and profit_scraping_engine.active:
            logger.info("🎯 PROFIT SCRAPING ENGINE IS ACTIVE AND RUNNING!")
        else:
            raise ValueError("🚨 RULE VIOLATION: PROFIT SCRAPING ENGINE IS NOT ACTIVE!")
        
        logger.info("🎯 RULE COMPLIANT: All components initialized successfully in Pure Profit Scraping Mode")
        
    except Exception as e:
        logger.error(f"❌ Critical error during component initialization: {e}")
        raise  # Don't continue with broken Pure Profit Scraping Mode

async def validate_all_components():
    """Final validation with graceful handling of missing components."""
    global exchange_client, strategy_manager, risk_manager, opportunity_manager, enhanced_signal_tracker, paper_trading_engine, profit_scraping_engine
    
    logger.info("🔍 Running final component validation...")
    
    # Validate critical components
    if not exchange_client:
        logger.error("❌ Exchange client is missing - this is critical")
        raise ValueError("Exchange client is required for basic functionality")
    logger.info("✅ Exchange client validated")
    
    # Validate optional components
    optional_components = {
        'strategy_manager': strategy_manager,
        'risk_manager': risk_manager,
        'opportunity_manager': opportunity_manager,
        'enhanced_signal_tracker': enhanced_signal_tracker,
        'profit_scraping_engine': profit_scraping_engine,
        'paper_trading_engine': paper_trading_engine
    }
    
    for name, component in optional_components.items():
        if component:
            logger.info(f"✅ {name} validated")
        else:
            logger.warning(f"⚠️ {name} is missing - some functionality will be disabled")
    
    # Validate connections (only if components exist)
    if paper_trading_engine and opportunity_manager:
        if hasattr(paper_trading_engine, 'opportunity_manager') and paper_trading_engine.opportunity_manager:
            logger.info("✅ Paper trading <-> Opportunity manager connection validated")
        else:
            logger.warning("⚠️ Paper trading <-> Opportunity manager connection missing")
    
    if paper_trading_engine and profit_scraping_engine:
        if hasattr(paper_trading_engine, 'profit_scraping_engine') and paper_trading_engine.profit_scraping_engine:
            logger.info("✅ Paper trading <-> Profit scraping connection validated")
        else:
            logger.warning("⚠️ Paper trading <-> Profit scraping connection missing")
    
    # CRITICAL: Validate profit scraping engine is actively running (if it exists)
    if profit_scraping_engine:
        if profit_scraping_engine.active:
            logger.info("✅ Profit scraping engine is ACTIVE and generating signals")
            
            # Validate monitored symbols
            if profit_scraping_engine.monitored_symbols:
                logger.info(f"✅ Profit scraping engine monitoring {len(profit_scraping_engine.monitored_symbols)} symbols: {list(profit_scraping_engine.monitored_symbols)}")
            else:
                logger.warning("⚠️ Profit scraping engine has no monitored symbols")
        else:
            logger.error("❌ Profit scraping engine is not active - no signal generation possible")
    else:
        logger.error("❌ Profit scraping engine is missing - no profit scraping signals will be generated")
    
    logger.info("🎯 COMPONENT VALIDATION COMPLETED!")

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
    app.include_router(real_trading_router)
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
        
        # DIRECT AUTO-START: Start engines immediately after initialization
        logger.info("🚀 Starting auto-start sequence...")
        
        # Start paper trading engine if available
        if paper_trading_engine and not paper_trading_engine.is_running:
            await paper_trading_engine.start()
            logger.info("✅ Paper trading auto-started successfully!")
        elif paper_trading_engine and paper_trading_engine.is_running:
            logger.info("✅ Paper trading already running!")
        else:
            logger.warning("⚠️ Paper trading engine not available for auto-start")
        
        # Set profit scraping engine for routes (use global reference)
        if profit_scraping_engine:
            try:
                from src.api.trading_routes.profit_scraping_routes import set_profit_scraping_engine
                set_profit_scraping_engine(profit_scraping_engine)
                logger.info("✅ Profit scraping engine set for API routes")
            except ImportError:
                logger.warning("⚠️ Could not import set_profit_scraping_engine function")
        
        # CRITICAL AUTO-START: Start profit scraping engine with paper trading
        logger.info("🎯 Checking auto-start conditions...")
        logger.info(f"📊 profit_scraping_engine available: {profit_scraping_engine is not None}")
        logger.info(f"📊 paper_trading_engine available: {paper_trading_engine is not None}")
        
        if profit_scraping_engine and paper_trading_engine:
            try:
                logger.info("✅ Auto-start conditions met - starting profit scraping engine...")
                
                # Get all available Binance futures symbols
                logger.info("🔍 Fetching all Binance futures symbols...")
                all_symbols = await exchange_client.get_all_symbols()
                
                if all_symbols:
                    # Filter for USDT perpetual futures (most liquid)
                    usdt_symbols = [s for s in all_symbols if s.endswith('USDT')]
                    logger.info(f"📊 Found {len(usdt_symbols)} USDT perpetual futures symbols")
                    
                    # Use all symbols (profit scraping engine will limit to max_symbols internally)
                    symbols_to_monitor = usdt_symbols
                else:
                    # Fallback to hardcoded liquid symbols if API fails
                    logger.warning("⚠️ Failed to fetch symbols from API, using fallback list")
                    symbols_to_monitor = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'SOLUSDT', 'DOGEUSDT', 'XRPUSDT', 'LTCUSDT', 'AVAXUSDT', 'DOTUSDT']
                
                logger.info(f"🚀 AUTO-STARTING profit scraping engine for PAPER TRADING with {len(symbols_to_monitor)} symbols...")
                
                # Ensure profit scraping engine is properly connected to paper trading
                if not hasattr(profit_scraping_engine, 'paper_trading_engine') or not profit_scraping_engine.paper_trading_engine:
                    profit_scraping_engine.paper_trading_engine = paper_trading_engine
                    profit_scraping_engine.trading_engine = paper_trading_engine
                    logger.info("🔗 Connected profit scraping engine to paper trading engine")
                else:
                    logger.info("✅ Profit scraping engine already connected to paper trading engine")
                
                # Force start profit scraping with all symbols
                logger.info("🚀 Calling start_scraping method...")
                scraping_started = await profit_scraping_engine.start_scraping(symbols_to_monitor)
                
                if scraping_started:
                    logger.info("✅ PROFIT SCRAPING ENGINE AUTO-STARTED SUCCESSFULLY!")
                    logger.info("🎯 Profit scraping will create positions in paper trading (virtual money)")
                    logger.info(f"📊 Monitoring {len(profit_scraping_engine.monitored_symbols)} symbols (limited by engine max_symbols)")
                    logger.info(f"🔥 First 10 symbols: {list(profit_scraping_engine.monitored_symbols)[:10]}")
                    
                    # Verify it's actually active
                    if profit_scraping_engine.active:
                        logger.info("🎉 CONFIRMED: Profit scraping engine is ACTIVE and running!")
                    else:
                        logger.error("❌ CRITICAL: Profit scraping engine started but not active!")
                else:
                    logger.error("❌ FAILED to auto-start profit scraping engine")
                    logger.error(f"❌ Engine state - active: {profit_scraping_engine.active}, monitored_symbols: {len(profit_scraping_engine.monitored_symbols)}")
                    
            except Exception as e:
                logger.error(f"❌ Exception during profit scraping auto-start: {e}")
                logger.error(f"❌ Error type: {type(e)}")
                import traceback
                logger.error(f"❌ Full traceback: {traceback.format_exc()}")
                
                # Fallback to hardcoded symbols on error
                try:
                    logger.info("🔄 Attempting fallback with hardcoded symbols...")
                    fallback_symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'SOLUSDT', 'DOGEUSDT', 'XRPUSDT', 'LTCUSDT', 'AVAXUSDT', 'DOTUSDT']
                    
                    profit_scraping_engine.paper_trading_engine = paper_trading_engine
                    profit_scraping_engine.trading_engine = paper_trading_engine
                    
                    scraping_started = await profit_scraping_engine.start_scraping(fallback_symbols)
                    if scraping_started:
                        logger.info(f"✅ FALLBACK SUCCESS: Profit scraping started with {len(fallback_symbols)} hardcoded symbols")
                    else:
                        logger.error("❌ FALLBACK FAILED: Could not start profit scraping even with hardcoded symbols")
                except Exception as fallback_error:
                    logger.error(f"❌ FALLBACK ERROR: {fallback_error}")
                    logger.error(f"❌ Fallback error type: {type(fallback_error)}")
                    import traceback
                    logger.error(f"❌ Fallback traceback: {traceback.format_exc()}")
                
        elif not profit_scraping_engine:
            logger.error("❌ No profit scraping engine available for auto-start")
        elif not paper_trading_engine:
            logger.error("❌ No paper trading engine available - cannot start profit scraping")
        else:
            logger.error("❌ Unknown issue preventing profit scraping auto-start")
        
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

# Add Uvicorn startup for direct execution
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
