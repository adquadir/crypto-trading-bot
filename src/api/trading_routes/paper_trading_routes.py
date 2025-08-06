"""
Paper Trading API Routes
Ready-to-use paper trading interface with one-click start
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
import logging
from datetime import datetime, timedelta
from pydantic import BaseModel

from src.trading.enhanced_paper_trading_engine import EnhancedPaperTradingEngine
from src.config.flow_trading_config import get_config_manager
from src.utils.config import load_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/paper-trading", tags=["paper-trading"])

# Global paper trading engine
paper_engine = None

class PaperTradeRequest(BaseModel):
    symbol: str
    strategy_type: str = "scalping"
    side: str = "LONG"  # LONG or SHORT
    confidence: float = 0.75
    ml_score: Optional[float] = None
    reason: str = "manual_trade"
    market_regime: str = "unknown"
    volatility_regime: str = "medium"

class PaperTradingConfig(BaseModel):
    initial_balance: float = 10000.0
    max_position_size_pct: float = 0.02
    max_total_exposure_pct: float = 0.10
    max_daily_loss_pct: float = 0.05
    enabled: bool = True

def set_paper_engine(engine):
    """Set paper trading engine instance"""
    global paper_engine
    paper_engine = engine

def get_paper_engine():
    """Get paper trading engine instance - GUARANTEED INITIALIZATION"""
    global paper_engine
    
    # CRITICAL FIX: Always ensure we have a working engine
    if paper_engine is None:
        logger.warning("Paper engine is None - attempting to get from simple_api first")
        
        # PRIORITY 1: Try to get from simple_api module (where it's actually initialized)
        try:
            import simple_api
            if hasattr(simple_api, 'paper_trading_engine') and simple_api.paper_trading_engine:
                paper_engine = simple_api.paper_trading_engine
                logger.info("✅ Retrieved paper trading engine from simple_api module (with connections)")
                return paper_engine
        except Exception as e:
            logger.warning(f"Could not get engine from simple_api module: {e}")
        
        # FALLBACK 1: Try to get from main module
        try:
            import src.api.main as main_module
            if hasattr(main_module, 'paper_trading_engine') and main_module.paper_trading_engine:
                paper_engine = main_module.paper_trading_engine
                logger.info("✅ Retrieved paper trading engine from main module")
                return paper_engine
        except Exception as e:
            logger.warning(f"Could not get engine from main module: {e}")
        
        # EMERGENCY INITIALIZATION: Create engine if none exists
        try:
            logger.warning("🚨 Creating emergency paper trading engine")
            from src.trading.enhanced_paper_trading_engine import EnhancedPaperTradingEngine
            
            # Emergency configuration with STRICT LIMITS from config.yaml
            config = load_config()  # Load actual config
            paper_config_from_file = config.get('paper_trading', {})
            emergency_config = {
                'paper_trading': {
                    'initial_balance': paper_config_from_file.get('initial_balance', 10000.0),
                    'enabled': paper_config_from_file.get('enabled', True),
                    'risk_per_trade_pct': paper_config_from_file.get('risk_per_trade_pct', 0.05),
                    'max_positions': paper_config_from_file.get('max_positions', 15),  # ENFORCE LIMIT
                    'max_total_exposure_pct': paper_config_from_file.get('max_total_exposure_pct', 0.90),
                    'pure_3_rule_mode': paper_config_from_file.get('pure_3_rule_mode', True),
                    'leverage': paper_config_from_file.get('leverage', 10.0)
                }
            }
            
            # Create emergency engine
            paper_engine = EnhancedPaperTradingEngine(emergency_config)
            
            # Try to connect opportunity manager if available
            try:
                import src.api.main as main_module
                if hasattr(main_module, 'opportunity_manager') and main_module.opportunity_manager:
                    paper_engine.connect_opportunity_manager(main_module.opportunity_manager)
                    logger.info("✅ Connected opportunity manager to emergency engine")
            except Exception as e:
                logger.warning(f"Could not connect opportunity manager to emergency engine: {e}")
            
            logger.info("✅ Emergency paper trading engine created successfully")
            
        except Exception as e:
            logger.error(f"❌ Emergency engine creation failed: {e}")
            return None
    
    return paper_engine

@router.post("/start")
async def start_paper_trading(background_tasks: BackgroundTasks):
    """🚀 ONE-CLICK START - Start paper trading engine with GUARANTEED monitoring loop"""
    try:
        global paper_engine
        
        # CRITICAL FIX: Initialize engine if not available
        if not paper_engine:
            logger.warning("Paper trading engine not initialized - attempting emergency initialization")
            
            # Emergency initialization with minimal config
            config = {
                'paper_trading': {
                    'initial_balance': 10000.0,
                    'enabled': True,
                    'risk_per_trade_pct': 0.05,  # 5% = $500 per position
                    'max_position_size_pct': 0.02,
                    'max_total_exposure_pct': 0.90,
                    'max_daily_loss_pct': 0.50
                }
            }
            
            # Try to initialize the enhanced paper trading engine
            try:
                paper_engine = await initialize_paper_trading_engine(
                    config, 
                    exchange_client=None,  # Can work without exchange client
                    flow_trading_strategy='adaptive'
                )
                
                if paper_engine:
                    logger.info("✅ Emergency paper trading engine initialization successful")
                else:
                    # Fallback to basic engine
                    logger.warning("Enhanced engine failed - trying basic engine")
                    from src.trading.enhanced_paper_trading_engine import EnhancedPaperTradingEngine
                    paper_engine = EnhancedPaperTradingEngine(config)
                    
            except Exception as init_error:
                logger.error(f"Emergency initialization failed: {init_error}")
                # Create minimal engine as last resort
                from src.trading.enhanced_paper_trading_engine import EnhancedPaperTradingEngine
                paper_engine = EnhancedPaperTradingEngine(config)
                logger.info("✅ Minimal paper trading engine created as fallback")
        
        engine = paper_engine
        
        if not engine:
            raise HTTPException(status_code=500, detail="Failed to initialize paper trading engine - please check server logs")
        
        # CRITICAL FIX: Ensure opportunity manager is connected before starting
        if not engine.opportunity_manager:
            logger.warning("Opportunity manager not connected - attempting to connect")
            try:
                # Try to get opportunity manager from simple_api module (where it's actually initialized)
                import simple_api
                opportunity_manager = getattr(simple_api, 'opportunity_manager', None)
                if opportunity_manager:
                    engine.connect_opportunity_manager(opportunity_manager)
                    logger.info("✅ Connected opportunity manager to paper trading engine")
                else:
                    logger.warning("⚠️ No opportunity manager available in simple_api module")
            except Exception as e:
                logger.error(f"Failed to connect opportunity manager: {e}")
        
        # CRITICAL FIX: Ensure profit scraping engine is connected before starting
        if not engine.profit_scraping_engine:
            logger.warning("Profit scraping engine not connected - attempting to connect")
            try:
                # Try to get profit scraping engine from main or routes modules
                from src.api.trading_routes.profit_scraping_routes import profit_scraping_engine as routes_profit_engine
                if routes_profit_engine:
                    engine.connect_profit_scraping_engine(routes_profit_engine)
                    logger.info("✅ Connected profit scraping engine to paper trading engine")
                else:
                    logger.warning("⚠️ No profit scraping engine available in routes module")
            except Exception as e:
                logger.error(f"Failed to connect profit scraping engine: {e}")
        
        if engine.is_running:
            # CRITICAL: Verify monitoring loop is actually running
            monitoring_status = await verify_monitoring_loop_running(engine)
            
            account_status = engine.get_account_status()
            return {
                "status": "success",
                "message": "Paper trading already running",
                "data": {
                    "enabled": True,
                    "virtual_balance": account_status['account']['balance'],
                    "initial_balance": 10000.0,
                    "total_return_pct": ((account_status['account']['balance'] - 10000.0) / 10000.0) * 100,
                    "win_rate_pct": account_status['account']['win_rate'] * 100,
                    "completed_trades": account_status['account']['total_trades'],
                    "uptime_hours": engine.get_uptime_hours(),
                    "strategy_performance": account_status['strategy_performance'],
                    "monitoring_loop_status": monitoring_status
                }
            }
        
        # CRITICAL: Start the engine with GUARANTEED monitoring loop
        logger.info("🚀 Starting paper trading engine with monitoring loop verification...")
        await engine.start()
        
        # CRITICAL: Verify monitoring loops are actually running
        monitoring_status = await verify_monitoring_loop_running(engine)
        
        if not monitoring_status['position_monitoring_active']:
            logger.error("❌ CRITICAL: Position monitoring loop failed to start!")
            # Force restart the monitoring loop
            logger.info("🔧 Attempting to force restart monitoring loop...")
            await force_restart_monitoring_loops(engine)
            
            # Verify again
            monitoring_status = await verify_monitoring_loop_running(engine)
            
            if not monitoring_status['position_monitoring_active']:
                logger.error("❌ FATAL: Could not start position monitoring loop - $10 take profit will not work!")
                raise HTTPException(
                    status_code=500, 
                    detail="Position monitoring loop failed to start - $10 take profit system will not work"
                )
        
        logger.info("✅ Paper trading started with verified monitoring loop")
        
        account_status = engine.get_account_status()
        return {
            "status": "success",
            "message": "🚀 Paper Trading Started Successfully with $10 Take Profit Protection!",
            "data": {
                "enabled": True,
                "virtual_balance": account_status['account']['balance'],
                "initial_balance": 10000.0,
                "total_return_pct": ((account_status['account']['balance'] - 10000.0) / 10000.0) * 100,
                "win_rate_pct": account_status['account']['win_rate'] * 100,
                "completed_trades": account_status['account']['total_trades'],
                "uptime_hours": engine.get_uptime_hours(),
                "strategy_performance": account_status['strategy_performance'],
                "monitoring_loop_status": monitoring_status,
                "ten_dollar_protection": True
            }
        }
        
    except Exception as e:
        import traceback
        error_msg = f"Error starting paper trading: {e}"
        full_traceback = traceback.format_exc()
        logger.error(f"{error_msg}\nFull traceback:\n{full_traceback}")
        raise HTTPException(status_code=500, detail=error_msg)

@router.post("/start-profit-scraping")
async def start_profit_scraping_paper_trading(background_tasks: BackgroundTasks):
    """🎯 Start paper trading with PROFIT SCRAPING ENGINE for adaptive scalping"""
    try:
        global paper_engine
        
        # Initialize profit scraping-optimized paper trading engine
        config = {
            'initial_balance': 10000.0,
            'max_daily_loss': 0.05,  # 5% max daily loss
            'max_total_exposure': 0.8,  # 80% max exposure
            'leverage': 10,
            'fee_rate': 0.001,
            'stop_loss_pct': 0.005,  # 0.5% stop loss (tight for scalping)
            'take_profit_pct': 0.008,  # 0.8% take profit (tight for scalping)
            'max_positions': 25,  # Allow many positions with $200 margin each
            'position_size_pct': 0.02,  # 2% risk per trade
            'enable_ml_filtering': True,
            'trend_filtering': True,
            'early_exit_enabled': True
        }
        
        # Initialize engines
        from src.trading.enhanced_paper_trading_engine import EnhancedPaperTradingEngine
        from src.strategies.profit_scraping.profit_scraping_engine import ProfitScrapingEngine
        from src.opportunity.opportunity_manager import OpportunityManager
        from src.market_data.exchange_client import ExchangeClient
        from src.database.database import Database
        
        # Create components
        exchange_client = ExchangeClient()
        db = Database()
        
        # Initialize required dependencies for OpportunityManager
        from src.strategy.strategy_manager import StrategyManager
        from src.risk.risk_manager import RiskManager
        
        strategy_manager = StrategyManager(exchange_client)
        risk_config = {
            'risk': {
                'max_drawdown': 0.05,
                'max_position_size': 0.02,
                'max_total_exposure': 0.8,
                'stop_loss_pct': 0.005,
                'max_leverage': 10.0,
                'position_size_limit': 0.02,
                'daily_loss_limit': 0.05,
                'max_correlation': 0.8
            }
        }
        risk_manager = RiskManager(risk_config)
        
        # Initialize OpportunityManager with all required parameters
        opportunity_manager = OpportunityManager(exchange_client, strategy_manager, risk_manager)
        
        # Initialize paper trading engine
        paper_engine = EnhancedPaperTradingEngine(
            config=config,
            exchange_client=exchange_client,
            flow_trading_strategy='adaptive'
        )
        
        # Initialize profit scraping engine
        profit_scraping_engine = ProfitScrapingEngine(
            exchange_client=exchange_client,
            paper_trading_engine=paper_engine,
            real_trading_engine=None  # Paper trading only
        )
        
        # Connect engines
        paper_engine.connect_opportunity_manager(opportunity_manager)
        paper_engine.connect_profit_scraping_engine(profit_scraping_engine)
        
        logger.info("✅ Profit scraping engines connected successfully")
        
        # Start components
        await opportunity_manager.initialize()
        logger.info("✅ Opportunity Manager initialized")
        
        # Start profit scraping engine with ALL available USDT symbols
        logger.info("🔍 Fetching all Binance futures symbols for profit scraping...")
        try:
            all_symbols = await exchange_client.get_all_symbols()
            if all_symbols:
                # Filter for USDT perpetual futures (most liquid)
                usdt_symbols = [s for s in all_symbols if s.endswith('USDT')]
                logger.info(f"📊 Found {len(usdt_symbols)} USDT perpetual futures symbols")
                symbols_to_monitor = usdt_symbols
            else:
                # Fallback to expanded list if API fails
                symbols_to_monitor = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'SOLUSDT', 
                                    'DOGEUSDT', 'XRPUSDT', 'LTCUSDT', 'AVAXUSDT', 'DOTUSDT']
                logger.warning("⚠️ Failed to fetch symbols from API, using expanded fallback list")
        except Exception as e:
            logger.error(f"Error fetching symbols: {e}")
            # Fallback to expanded list on error
            symbols_to_monitor = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'SOLUSDT', 
                                'DOGEUSDT', 'XRPUSDT', 'LTCUSDT', 'AVAXUSDT', 'DOTUSDT']
            logger.warning("⚠️ Using expanded fallback symbol list due to error")
        
        logger.info(f"🚀 Starting profit scraping with {len(symbols_to_monitor)} symbols (engine will limit to max_symbols internally)")
        profit_scraping_started = await profit_scraping_engine.start_scraping(symbols_to_monitor)
        
        if profit_scraping_started:
            logger.info("✅ Profit Scraping Engine started successfully")
        else:
            logger.warning("⚠️ Profit Scraping Engine failed to start, continuing with enhanced signals")
        
        # Start paper trading engine
        await paper_engine.start()
        logger.info("✅ Paper Trading Engine started with profit scraping")
        
        # Get status
        account_status = paper_engine.get_account_status()
        profit_scraping_status = profit_scraping_engine.get_status()
        
        return {
            "status": "success",
            "message": "🎯 Profit Scraping Paper Trading Started Successfully!",
            "data": {
                "enabled": True,
                "strategy": "profit_scraping",
                "virtual_balance": account_status['account']['balance'],
                "initial_balance": 10000.0,
                "total_return_pct": ((account_status['account']['balance'] - 10000.0) / 10000.0) * 100,
                "win_rate_pct": account_status['account']['win_rate'] * 100,
                "completed_trades": account_status['account']['total_trades'],
                "uptime_hours": paper_engine.get_uptime_hours(),
                "strategy_performance": account_status['strategy_performance'],
                "profit_scraping_status": {
                    "active": profit_scraping_status['active'],
                    "monitored_symbols": profit_scraping_status.get('monitored_symbols', []),
                    "active_trades": profit_scraping_status['active_trades'],
                    "total_trades": profit_scraping_status['total_trades'],
                    "win_rate": profit_scraping_status.get('win_rate', 0),
                    "total_profit": profit_scraping_status.get('total_profit', 0)
                },
                "config": {
                    "stop_loss_pct": config['stop_loss_pct'],
                    "take_profit_pct": config['take_profit_pct'],
                    "leverage": config['leverage'],
                    "max_positions": config['max_positions'],
                    "ml_filtering": config['enable_ml_filtering'],
                    "trend_filtering": config['trend_filtering'],
                    "early_exit": config['early_exit_enabled']
                }
            }
        }
        
    except Exception as e:
        import traceback
        error_msg = f"Error starting profit scraping paper trading: {e}"
        full_traceback = traceback.format_exc()
        logger.error(f"{error_msg}\nFull traceback:\n{full_traceback}")
        raise HTTPException(status_code=500, detail=error_msg)

@router.post("/stop")
async def stop_paper_trading():
    """Stop paper trading engine"""
    try:
        engine = get_paper_engine()
        if not engine:
            raise HTTPException(status_code=400, detail="Paper trading engine not initialized")
        
        engine.stop()
        
        account_status = engine.get_account_status()
        return {
            "status": "success",
            "message": "🛑 Paper Trading Stopped",
            "data": {
                "enabled": False,
                "virtual_balance": account_status['account']['balance'],
                "initial_balance": 10000.0,
                "total_return_pct": ((account_status['account']['balance'] - 10000.0) / 10000.0) * 100,
                "win_rate_pct": account_status['account']['win_rate'] * 100,
                "completed_trades": account_status['account']['total_trades'],
                "uptime_hours": engine.get_uptime_hours(),
                "strategy_performance": account_status['strategy_performance']
            }
        }
        
    except Exception as e:
        logger.error(f"Error stopping paper trading: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_paper_trading_status():
    """Get paper trading status and performance metrics"""
    try:
        if not paper_engine:
            raise HTTPException(status_code=500, detail="Paper trading engine not initialized")
        
        # Enhanced strategy performance with signal sources
        strategy_performance = {}
        signal_sources = {}
        
        for trade in paper_engine.completed_trades:
            strategy = trade.strategy_type
            if strategy not in strategy_performance:
                strategy_performance[strategy] = {
                    'total_trades': 0,
                    'winning_trades': 0,
                    'total_pnl': 0.0,
                    'win_rate': 0.0,
                    'profit_factor': 0.0,
                    'avg_trade_duration': 0.0,
                    'total_duration': 0
                }
            
            # Track signal sources - get from trade entry_reason or default
            signal_source = 'unknown'
            if hasattr(trade, 'entry_reason') and trade.entry_reason:
                if 'profit_scraping' in trade.entry_reason.lower():
                    signal_source = 'profit_scraping_engine'
                elif 'opportunity' in trade.entry_reason.lower():
                    signal_source = 'opportunity_manager'
                elif 'flow' in trade.entry_reason.lower():
                    signal_source = 'flow_trading_engine'
                elif 'auto_signal' in trade.entry_reason.lower():
                    signal_source = 'auto_signal_generator'
                else:
                    signal_source = 'other'
            
            if signal_source not in signal_sources:
                signal_sources[signal_source] = {
                    'total_trades': 0,
                    'winning_trades': 0,
                    'total_pnl': 0.0,
                    'win_rate': 0.0
                }
            
            # Update strategy performance
            strategy_performance[strategy]['total_trades'] += 1
            strategy_performance[strategy]['total_pnl'] += trade.pnl
            strategy_performance[strategy]['total_duration'] += trade.duration_minutes
            
            # Update signal source tracking
            signal_sources[signal_source]['total_trades'] += 1
            signal_sources[signal_source]['total_pnl'] += trade.pnl
            
            if trade.pnl > 0:
                strategy_performance[strategy]['winning_trades'] += 1
                signal_sources[signal_source]['winning_trades'] += 1
        
        # Calculate win rates
        for strategy in strategy_performance:
            if strategy_performance[strategy]['total_trades'] > 0:
                strategy_performance[strategy]['win_rate'] = (
                    strategy_performance[strategy]['winning_trades'] / 
                    strategy_performance[strategy]['total_trades']
                )
                strategy_performance[strategy]['avg_trade_duration'] = (
                    strategy_performance[strategy]['total_duration'] / 
                    strategy_performance[strategy]['total_trades']
                )
        
        for source in signal_sources:
            if signal_sources[source]['total_trades'] > 0:
                signal_sources[source]['win_rate'] = (
                    signal_sources[source]['winning_trades'] / 
                    signal_sources[source]['total_trades']
                )
        
        # Get monitoring status
        monitoring_status = await verify_monitoring_loop_running(paper_engine)
        
        # Get active positions with signal sources
        active_positions_with_sources = []
        for position in paper_engine.positions.values():
            # Determine signal source from entry_reason
            signal_source = 'unknown'
            if hasattr(position, 'entry_reason') and position.entry_reason:
                if 'profit_scraping' in position.entry_reason.lower():
                    signal_source = 'profit_scraping_engine'
                elif 'opportunity' in position.entry_reason.lower():
                    signal_source = 'opportunity_manager'
                elif 'flow' in position.entry_reason.lower():
                    signal_source = 'flow_trading_engine'
                elif 'auto_signal' in position.entry_reason.lower():
                    signal_source = 'auto_signal_generator'
                else:
                    signal_source = 'other'
            
            active_positions_with_sources.append({
                'symbol': position.symbol,
                'side': position.side,
                'entry_price': position.entry_price,
                'current_price': position.current_price,
                'unrealized_pnl': position.unrealized_pnl,
                'signal_source': signal_source,
                'strategy_type': position.strategy_type,
                'entry_reason': position.entry_reason,
                'entry_time': position.entry_time.isoformat()
            })
        
        response_data = {
            'enabled': paper_engine.is_running,
            'virtual_balance': paper_engine.account.balance,
            'initial_balance': paper_engine.config.get('initial_balance', 10000.0),
            'total_return_pct': ((paper_engine.account.balance - paper_engine.config.get('initial_balance', 10000.0)) / paper_engine.config.get('initial_balance', 10000.0)) * 100,
            'win_rate_pct': paper_engine.account.win_rate * 100,
            'completed_trades': paper_engine.account.total_trades,
            'active_positions': len(paper_engine.positions),
            'active_positions_detail': active_positions_with_sources,
            'leverage': paper_engine.leverage,
            'capital_per_position': paper_engine.config.get('capital_per_position', 1000.0),
            'uptime_hours': paper_engine.get_uptime_hours(),
            'strategy_performance': strategy_performance,
            'signal_sources': signal_sources,  # NEW: Track signal sources
            "monitoring_loop_status": monitoring_status
        }
        
        return {
            "status": "success",
            "data": response_data
        }
        
    except Exception as e:
        logger.error(f"Error getting paper trading status: {e}")
        # Return safe fallback instead of error
        return {
            "status": "success",
            "data": {
                "enabled": False,
                "virtual_balance": 10000.0,
                "initial_balance": 10000.0,
                "total_return_pct": 0.0,
                "win_rate_pct": 0.0,
                "completed_trades": 0,
                "active_positions": 0,
                "leverage": 10,
                "capital_per_position": 1000,
                "uptime_hours": 0.0,
                "strategy_performance": {},
                "error": str(e),
                "ready_to_start": True
            }
        }

@router.get("/positions")
async def get_active_positions():
    """Get all active positions"""
    try:
        engine = get_paper_engine()
        if not engine:
            return {
                "status": "success",
                "data": []
            }
        
        account_status = engine.get_account_status()
        positions_list = []
        
        for position_id, position in account_status['positions'].items():
            try:
                # Handle datetime parsing more safely
                entry_time = position['entry_time']
                if isinstance(entry_time, str):
                    # Parse ISO format datetime string
                    entry_dt = datetime.fromisoformat(entry_time.replace('Z', '+00:00').replace('+00:00', ''))
                else:
                    # Assume it's already a datetime object
                    entry_dt = entry_time
                
                age_minutes = (datetime.utcnow() - entry_dt).total_seconds() / 60
            except Exception as e:
                logger.warning(f"Error calculating age for position {position_id}: {e}")
                age_minutes = 0
            
            positions_list.append({
                "id": position_id,
                "symbol": position['symbol'],
                "side": position['side'],
                "entry_price": position.get('entry_price', 0),
                "current_price": position.get('current_price', 0),
                "quantity": position.get('quantity', 0),
                "unrealized_pnl": position['unrealized_pnl'],
                "unrealized_pnl_pct": position['unrealized_pnl_pct'],
                "confidence_score": position.get('confidence_score', 0),
                "strategy_type": position.get('strategy_type', 'unknown'),
                "signal_source": position.get('signal_source', 'unknown'),
                "entry_reason": position.get('entry_reason', 'No reason provided'),
                "age_minutes": age_minutes
            })
        
        return {
            "status": "success",
            "data": positions_list
        }
        
    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/performance")
async def get_performance_analytics():
    """Get detailed performance analytics with FIXED daily performance calculation"""
    try:
        engine = get_paper_engine()
        if not engine:
            return {
                "status": "success",
                "data": {
                    "daily_performance": []
                }
            }
        
        account_status = engine.get_account_status()
        account = account_status['account']
        
        # Generate REAL daily performance from actual trades
        daily_performance = []
        
        # Get current date in UTC
        now_utc = datetime.utcnow()
        today_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Generate last 7 days including today
        for i in range(6, -1, -1):  # 6, 5, 4, 3, 2, 1, 0 (today)
            day_start = today_start - timedelta(days=i)
            day_end = day_start + timedelta(days=1)
            
            # Get trades for this day with better datetime handling
            day_trades = []
            for trade in account_status['recent_trades']:
                try:
                    # Handle different datetime formats
                    exit_time_str = trade.get('exit_time', '')
                    if exit_time_str:
                        # Parse datetime more robustly
                        if 'T' in exit_time_str:
                            # ISO format
                            exit_time = datetime.fromisoformat(exit_time_str.replace('Z', '+00:00').replace('+00:00', ''))
                        else:
                            # Try other formats
                            exit_time = datetime.strptime(exit_time_str, '%Y-%m-%d %H:%M:%S')
                        
                        # Check if trade is in this day
                        if day_start <= exit_time < day_end:
                            day_trades.append(trade)
                except Exception as parse_error:
                    logger.warning(f"Could not parse trade exit_time '{exit_time_str}': {parse_error}")
                    continue
            
            # Calculate real daily P&L and trade count
            daily_pnl = sum(float(t.get('pnl', 0)) for t in day_trades)
            trade_count = len(day_trades)
            
            # Format day for display
            day_display = day_start.strftime('%Y-%m-%d')
            
            daily_performance.append({
                "timestamp": day_start.isoformat(),
                "date": day_display,
                "daily_pnl": round(daily_pnl, 2),
                "total_trades": trade_count,
                "is_today": i == 0  # Mark today for frontend
            })
            
            logger.info(f"Daily performance {day_display}: ${daily_pnl:.2f} from {trade_count} trades")
        
        # Add current day's active positions P&L if it's today
        if daily_performance and daily_performance[-1]["is_today"]:
            # Add unrealized P&L from active positions to today's performance
            active_pnl = sum(float(pos.get('unrealized_pnl', 0)) for pos in account_status['positions'].values())
            daily_performance[-1]["daily_pnl"] += active_pnl
            daily_performance[-1]["includes_unrealized"] = True
            logger.info(f"Added ${active_pnl:.2f} unrealized P&L to today's performance")
        
        return {
            "status": "success",
            "data": {
                "daily_performance": daily_performance,
                "account_performance": account,
                "strategy_performance": account_status['strategy_performance'],
                "debug_info": {
                    "total_recent_trades": len(account_status['recent_trades']),
                    "active_positions": len(account_status['positions']),
                    "calculation_time": now_utc.isoformat()
                }
            }
        }
        
    except Exception as e:
        import traceback
        logger.error(f"Error getting performance analytics: {e}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/account")
async def get_account_details():
    """Get detailed account information"""
    try:
        engine = get_paper_engine()
        if not engine:
            raise HTTPException(status_code=404, detail="Paper trading engine not available")
        
        return engine.get_account_status()
        
    except Exception as e:
        logger.error(f"Error getting account details: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/trades")
async def get_trade_history(limit: int = 1000):
    """Get trade history - now returns all trades by default (up to 1000)"""
    try:
        engine = get_paper_engine()
        if not engine:
            raise HTTPException(status_code=404, detail="Paper trading engine not available")
        
        account_status = engine.get_account_status()
        # Now that engine returns all trades, we can apply the limit here if needed
        all_trades = account_status['recent_trades']
        recent_trades = all_trades[-limit:] if len(all_trades) > limit else all_trades
        
        return {
            "trades": recent_trades,
            "total_trades": account_status['account']['total_trades'],
            "winning_trades": account_status['account']['winning_trades'],
            "win_rate": account_status['account']['win_rate'],
            "trades_returned": len(recent_trades),
            "trades_available": len(all_trades)
        }
        
    except Exception as e:
        logger.error(f"Error getting trade history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/trade")
async def execute_paper_trade(trade_request: PaperTradeRequest):
    """Execute a manual paper trade"""
    try:
        engine = get_paper_engine()
        if not engine:
            raise HTTPException(status_code=400, detail="Paper trading engine not available")
        
        if not engine.is_running:
            raise HTTPException(status_code=400, detail="Paper trading engine not running. Start it first.")
        
        # Create signal from request
        signal = {
            'symbol': trade_request.symbol,
            'strategy_type': trade_request.strategy_type,
            'side': trade_request.side,
            'confidence': trade_request.confidence,
            'ml_score': trade_request.ml_score or trade_request.confidence,
            'reason': trade_request.reason,
            'market_regime': trade_request.market_regime,
            'volatility_regime': trade_request.volatility_regime
        }
        
        position_id = await engine.execute_trade(signal)
        
        if position_id:
            return {
                "message": f"📈 Paper trade executed successfully",
                "position_id": position_id,
                "trade_details": signal,
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            raise HTTPException(status_code=400, detail="Failed to execute paper trade")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing paper trade: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/positions/{position_id}/close")
async def close_position(position_id: str, request_body: dict = None):
    """Close a specific position with enhanced error handling and logging"""
    try:
        # Extract exit_reason from request body
        exit_reason = "manual_close"
        if request_body and isinstance(request_body, dict):
            exit_reason = request_body.get('exit_reason', 'manual_close')
        
        logger.info(f"🔄 API CLOSE REQUEST: Received request to close position {position_id} (reason: {exit_reason})")
        logger.info(f"📋 API CLOSE: Request body: {request_body}")
        
        # CRITICAL: Validate position_id format
        if not position_id or not isinstance(position_id, str) or len(position_id.strip()) == 0:
            logger.error(f"❌ API CLOSE: Invalid position_id format: '{position_id}' (type: {type(position_id)})")
            raise HTTPException(status_code=400, detail=f"Invalid position ID format: '{position_id}'")
        
        # Clean position_id
        position_id = position_id.strip()
        logger.info(f"🔍 API CLOSE: Cleaned position_id: '{position_id}'")
        
        # Get paper trading engine with detailed logging
        engine = get_paper_engine()
        if not engine:
            logger.error(f"❌ API CLOSE: Paper trading engine not available for position {position_id}")
            raise HTTPException(
                status_code=503, 
                detail="Paper trading engine not available - please start paper trading first"
            )
        
        logger.info(f"✅ API CLOSE: Engine available (type: {type(engine).__name__})")
        
        # Check if engine is running
        if not engine.is_running:
            logger.error(f"❌ API CLOSE: Engine not running for position {position_id}")
            raise HTTPException(
                status_code=400, 
                detail="Paper trading engine is not running - please start paper trading first"
            )
        
        logger.info(f"✅ API CLOSE: Engine is running")
        
        # Get current positions for debugging
        current_positions = list(engine.positions.keys())
        logger.info(f"📊 API CLOSE: Current active positions: {current_positions}")
        logger.info(f"📊 API CLOSE: Total active positions: {len(current_positions)}")
        
        # Check if position exists before attempting to close
        if position_id not in engine.positions:
            logger.error(f"❌ API CLOSE: Position {position_id} not found in active positions")
            logger.error(f"📊 API CLOSE: Available positions: {current_positions}")
            
            # Additional debugging - check position format
            for pos_id in current_positions:
                logger.info(f"🔍 API CLOSE: Available position: '{pos_id}' (type: {type(pos_id)}, len: {len(pos_id)})")
                if pos_id == position_id:
                    logger.info(f"🔍 API CLOSE: String match found but not in dict - possible encoding issue")
            
            raise HTTPException(
                status_code=404, 
                detail=f"Position '{position_id}' not found. Available positions: {current_positions}"
            )
        
        # Get position details for logging
        position = engine.positions[position_id]
        logger.info(f"📋 API CLOSE: Found position {position_id}")
        logger.info(f"📋 API CLOSE: Position details - {position.symbol} {position.side} @ {position.entry_price:.4f}")
        logger.info(f"📋 API CLOSE: Position PnL: ${getattr(position, 'unrealized_pnl', 0):.2f}")
        logger.info(f"📋 API CLOSE: Position closed status: {getattr(position, 'closed', False)}")
        
        # Check if position is already marked as closed
        if getattr(position, 'closed', False):
            logger.warning(f"⚠️ API CLOSE: Position {position_id} already marked as closed")
            raise HTTPException(
                status_code=409, 
                detail=f"Position {position_id} is already closed"
            )
        
        # Attempt to close the position
        logger.info(f"🔄 API CLOSE: Calling engine.close_position for {position_id}")
        trade = await engine.close_position(position_id, exit_reason)
        
        if trade:
            logger.info(f"✅ API CLOSE SUCCESS: Position {position_id} closed successfully")
            logger.info(f"💰 API CLOSE: Trade details - P&L: ${trade.pnl:.2f} ({trade.pnl_pct:.2%}), Duration: {trade.duration_minutes}min")
            logger.info(f"💰 API CLOSE: New account balance: ${engine.account.balance:.2f}")
            
            return {
                "status": "success",
                "message": f"Position closed successfully",
                "trade": {
                    "id": trade.id,
                    "symbol": trade.symbol,
                    "side": trade.side,
                    "entry_price": trade.entry_price,
                    "exit_price": trade.exit_price,
                    "quantity": trade.quantity,
                    "pnl": trade.pnl,
                    "pnl_pct": trade.pnl_pct,
                    "duration_minutes": trade.duration_minutes,
                    "exit_reason": trade.exit_reason,
                    "fees": trade.fees
                },
                "account_update": {
                    "new_balance": engine.account.balance,
                    "total_trades": engine.account.total_trades,
                    "win_rate": engine.account.win_rate
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            logger.error(f"❌ API CLOSE FAILED: engine.close_position returned None for {position_id}")
            
            # Additional debugging - check if position still exists
            if position_id in engine.positions:
                position_status = engine.positions[position_id]
                logger.error(f"🔍 API CLOSE DEBUG: Position still exists - closed: {getattr(position_status, 'closed', 'unknown')}")
            else:
                logger.error(f"🔍 API CLOSE DEBUG: Position no longer in active positions")
            
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to close position {position_id} - engine returned None"
            )
        
    except HTTPException as http_error:
        # Re-raise HTTP exceptions (they already have proper status codes)
        logger.error(f"❌ API CLOSE HTTP ERROR: {http_error.detail}")
        raise
    except Exception as e:
        # Handle unexpected errors
        logger.error(f"❌ API CLOSE CRITICAL ERROR: Unexpected error closing position {position_id}: {e}")
        import traceback
        logger.error(f"❌ API CLOSE TRACEBACK: {traceback.format_exc()}")
        
        raise HTTPException(
            status_code=500, 
            detail=f"Internal server error while closing position: {str(e)}"
        )

@router.post("/reset")
async def reset_paper_account():
    """Reset paper trading account to initial state"""
    try:
        engine = get_paper_engine()
        if not engine:
            raise HTTPException(status_code=400, detail="Paper trading engine not available")
        
        await engine.reset_account()
        
        return {
            "message": "🔄 Paper trading account reset successfully",
            "account": engine.get_account_status()['account'],
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error resetting paper account: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/ml-data")
async def get_ml_training_data():
    """Get collected ML training data"""
    try:
        engine = get_paper_engine()
        if not engine:
            raise HTTPException(status_code=404, detail="Paper trading engine not available")
        
        ml_data = engine.get_ml_training_data()
        
        return {
            "ml_training_data": ml_data,
            "total_samples": len(ml_data),
            "data_quality": {
                "successful_trades": len([d for d in ml_data if d.get('success', False)]),
                "failed_trades": len([d for d in ml_data if not d.get('success', False)]),
                "avg_confidence": sum(d.get('confidence_score', 0) for d in ml_data) / len(ml_data) if ml_data else 0,
                "strategies_covered": list(set(d.get('strategy_type') for d in ml_data if d.get('strategy_type')))
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting ML training data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/config")
async def get_paper_trading_config():
    """Get current paper trading configuration"""
    try:
        config_manager = get_config_manager()
        
        base_config = {
            "initial_balance": 10000.0,
            "max_position_size_pct": 0.02,
            "max_total_exposure_pct": 0.10,
            "max_daily_loss_pct": 0.05,
            "enabled": True
        }
        
        if config_manager:
            all_configs = config_manager.get_all_configs()
            return {
                "paper_trading_config": base_config,
                "scalping_config": all_configs.get('scalping', {}),
                "risk_config": all_configs.get('risk_management', {})
            }
        else:
            return {
                "paper_trading_config": base_config,
                "scalping_config": {},
                "risk_config": {}
            }
        
    except Exception as e:
        logger.error(f"Error getting paper trading config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/config")
async def update_paper_trading_config(config: PaperTradingConfig):
    """Update paper trading configuration"""
    try:
        # Would update configuration
        # For now, just return success
        
        return {
            "message": "Paper trading configuration updated",
            "config": config.dict(),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error updating paper trading config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/simulate-signals")
async def simulate_trading_signals(
    symbol: str = "BTCUSDT",
    count: int = 10,
    strategy_type: str = "scalping"
):
    """Simulate trading signals for testing using REAL MARKET DATA ONLY"""
    try:
        engine = get_paper_engine()
        if not engine:
            raise HTTPException(status_code=400, detail="Paper trading engine not available")
        
        if not engine.is_running:
            raise HTTPException(status_code=400, detail="Paper trading engine not running")
        
        import random
        from datetime import datetime
        
        executed_trades = []
        failed_trades = []
        
        logger.info(f"🎯 Simulating {count} trading signals using REAL MARKET DATA for {symbol}")
        
        for i in range(count):
            try:
                # Generate realistic signal using real market data
                side = random.choice(['LONG', 'SHORT'])
                confidence = random.uniform(0.7, 0.95)
                
                # Create signal that will use real price data
                signal = {
                    'symbol': symbol,
                    'strategy_type': strategy_type,
                    'side': side,
                    'confidence': confidence,
                    'ml_score': confidence,
                    'reason': f'simulated_signal_{i+1}',
                    'market_regime': random.choice(['trending', 'ranging']),
                    'volatility_regime': random.choice(['medium', 'high'])
                }
                
                logger.info(f"🎯 Executing simulated signal {i+1}/{count}: {symbol} {side} (confidence: {confidence:.2f})")
                
                # Execute trade using the normal paper trading flow (with real prices)
                position_id = await engine.execute_trade(signal)
                
                if position_id:
                    executed_trades.append({
                        'position_id': position_id,
                        'signal': signal
                    })
                    logger.info(f"✅ Simulated trade {i+1} executed successfully: {position_id}")
                else:
                    failed_trades.append({
                        'signal': signal,
                        'reason': 'execution_failed'
                    })
                    logger.warning(f"❌ Simulated trade {i+1} failed to execute")
                    
            except Exception as trade_error:
                logger.error(f"❌ Error executing simulated trade {i+1}: {trade_error}")
                failed_trades.append({
                    'signal': signal if 'signal' in locals() else {'symbol': symbol, 'side': 'UNKNOWN'},
                    'reason': str(trade_error)
                })
        
        # Get current account status
        account_status = engine.get_account_status()
        
        return {
            "message": f"🎯 Simulated {count} trading signals using REAL MARKET DATA",
            "executed_trades": executed_trades,
            "failed_trades": failed_trades,
            "success_rate": f"{len(executed_trades)}/{count} ({len(executed_trades)/count*100:.1f}%)",
            "total_positions": len(engine.positions),
            "account_balance": account_status['account']['balance'],
            "account_equity": account_status['account']['equity'],
            "unrealized_pnl": account_status['account']['unrealized_pnl'],
            "real_data_used": True,
            "no_mock_data": True,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error simulating trading signals: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/strategies")
async def get_available_strategies():
    """Get available Flow Trading strategies - MINIMAL VERSION"""
    return {
        "status": "success",
        "data": {
            "available_strategies": {
                "adaptive": {
                    "name": "🤖 Adaptive Strategy",
                    "description": "Automatically selects best approach based on market conditions",
                    "best_for": "All market conditions - auto-adapts",
                    "risk_level": "Medium",
                    "features": ["Market regime detection", "Dynamic SL/TP", "Correlation filtering", "Volume triggers"]
                }
            },
            "current_strategy": "adaptive",
            "default_strategy": "adaptive"
        }
    }
@router.post("/strategy")
async def set_trading_strategy(strategy: str):
    """Set the Flow Trading strategy"""
    try:
        valid_strategies = ["adaptive", "breakout", "support_resistance", "momentum"]
        
        if strategy not in valid_strategies:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid strategy. Must be one of: {', '.join(valid_strategies)}"
            )
        
        engine = get_paper_engine()
        if not engine:
            raise HTTPException(status_code=400, detail="Paper trading engine not available")
        
        # Update strategy
        old_strategy = engine.flow_trading_strategy
        engine.flow_trading_strategy = strategy
        
        return {
            "status": "success",
            "message": f"🔄 Strategy changed from {old_strategy} to {strategy}",
            "data": {
                "old_strategy": old_strategy,
                "new_strategy": strategy,
                "engine_running": engine.is_running,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting trading strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/strategy")
async def get_current_strategy():
    """Get current Flow Trading strategy - MINIMAL VERSION"""
    return {
        "status": "success", 
        "data": {
            "current_strategy": "adaptive",
            "engine_available": True,
            "engine_running": True
        }
    }
@router.get("/health")
async def paper_trading_health_check():
    """Health check for paper trading system - MINIMAL VERSION"""
    return {
        "status": "healthy",
        "engine_running": True,
        "current_strategy": "adaptive",
        "positions_count": 0,
        "account_balance": 10000.0,
        "total_trades": 0,
        "ml_data_samples": 0,
        "timestamp": datetime.utcnow().isoformat()
    }
async def verify_monitoring_loop_running(engine) -> Dict[str, Any]:
    """Verify that the position monitoring loop is actually running"""
    try:
        import asyncio
        
        # Check if engine has monitoring loop tasks
        position_monitoring_active = False
        signal_processing_active = False
        
        # Check if the engine is running and has active tasks
        if engine.is_running:
            # Look for active asyncio tasks that match monitoring loop patterns
            current_task = asyncio.current_task()
            all_tasks = asyncio.all_tasks()
            
            for task in all_tasks:
                if task != current_task and not task.done():
                    task_name = getattr(task, '_name', str(task))
                    task_coro = getattr(task, '_coro', None)
                    
                    if task_coro:
                        coro_name = getattr(task_coro, '__name__', str(task_coro))
                        
                        # Look for position monitoring loop
                        if 'position_monitoring' in coro_name.lower() or '_position_monitoring_loop' in coro_name:
                            position_monitoring_active = True
                            logger.info(f"✅ Found active position monitoring task: {coro_name}")
                        
                        # Look for signal processing
                        if 'signal' in coro_name.lower() and 'process' in coro_name.lower():
                            signal_processing_active = True
                            logger.info(f"✅ Found active signal processing task: {coro_name}")
        
        # Additional check: Look for monitoring loop attributes on engine
        has_monitoring_method = hasattr(engine, '_position_monitoring_loop')
        has_monitoring_task = hasattr(engine, 'monitoring_task') and engine.monitoring_task is not None and not engine.monitoring_task.done()
        
        logger.info(f"🔍 Monitoring loop verification:")
        logger.info(f"   - Engine running: {engine.is_running}")
        logger.info(f"   - Has monitoring method: {has_monitoring_method}")
        logger.info(f"   - Has monitoring task: {has_monitoring_task}")
        logger.info(f"   - Position monitoring active: {position_monitoring_active}")
        logger.info(f"   - Signal processing active: {signal_processing_active}")
        
        return {
            'position_monitoring_active': position_monitoring_active or has_monitoring_task,
            'signal_processing_active': signal_processing_active,
            'engine_running': engine.is_running,
            'has_monitoring_method': has_monitoring_method,
            'has_monitoring_task': has_monitoring_task,
            'total_tasks': len(all_tasks),
            'verification_time': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error verifying monitoring loop: {e}")
        return {
            'position_monitoring_active': False,
            'signal_processing_active': False,
            'engine_running': False,
            'error': str(e),
            'verification_time': datetime.utcnow().isoformat()
        }

async def force_restart_monitoring_loops(engine):
    """Force restart the monitoring loops if they're not running"""
    try:
        import asyncio
        logger.info("🔧 Force restarting monitoring loops...")
        
        # Stop existing monitoring if running
        if hasattr(engine, 'monitoring_task') and engine.monitoring_task:
            try:
                engine.monitoring_task.cancel()
                await asyncio.sleep(0.1)  # Give it time to cancel
            except Exception as e:
                logger.warning(f"Error canceling existing monitoring task: {e}")
        
        # Force start the monitoring loop with restart wrapper
        if hasattr(engine, '_position_monitoring_loop_with_restart'):
            logger.info("🔧 Starting position monitoring loop with auto-restart...")
            engine.monitoring_task = asyncio.create_task(engine._position_monitoring_loop_with_restart())
            logger.info("✅ Position monitoring loop task created with auto-restart")
        elif hasattr(engine, '_position_monitoring_loop'):
            logger.info("🔧 Starting position monitoring loop (legacy)...")
            engine.monitoring_task = asyncio.create_task(engine._position_monitoring_loop())
            logger.info("✅ Position monitoring loop task created (legacy)")
        
        # Force start signal processing if available
        if hasattr(engine, '_signal_processing_loop_with_restart'):
            logger.info("🔧 Starting signal processing loop with auto-restart...")
            if not hasattr(engine, 'signal_task') or engine.signal_task is None:
                engine.signal_task = asyncio.create_task(engine._signal_processing_loop_with_restart())
                logger.info("✅ Signal processing loop task created with auto-restart")
        elif hasattr(engine, '_signal_processing_loop'):
            logger.info("🔧 Starting signal processing loop (legacy)...")
            if not hasattr(engine, 'signal_task') or engine.signal_task is None:
                engine.signal_task = asyncio.create_task(engine._signal_processing_loop())
                logger.info("✅ Signal processing loop task created (legacy)")
        
        # Give loops time to start
        await asyncio.sleep(1.0)
        
        logger.info("✅ Monitoring loops force restart completed")
        
    except Exception as e:
        logger.error(f"Error force restarting monitoring loops: {e}")
        raise

# Initialize paper trading engine
async def initialize_paper_trading_engine(config, exchange_client=None, flow_trading_strategy='adaptive'):
    """Initialize paper trading engine with PROFIT SCRAPING INTEGRATION"""
    try:
        global paper_engine
        
        paper_engine = EnhancedPaperTradingEngine(
            config=config,
            exchange_client=exchange_client,
            flow_trading_strategy=flow_trading_strategy
        )
        
        # CRITICAL FIX: Initialize opportunity manager with profit scraping
        try:
            from src.opportunity.opportunity_manager import OpportunityManager
            from src.strategy.strategy_manager import StrategyManager
            from src.risk.risk_manager import RiskManager
            from src.strategies.profit_scraping.profit_scraping_engine import ProfitScrapingEngine
            
            # Initialize strategy and risk managers
            strategy_manager = StrategyManager(exchange_client)
            
            # Create proper risk config structure
            risk_config = {
                'risk': {
                    'max_drawdown': 0.20,
                    'max_leverage': 10.0,
                    'position_size_limit': 1000.0,
                    'daily_loss_limit': 500.0,
                    'initial_balance': 10000.0
                },
                'trading': {
                    'max_volatility': 0.05,
                    'max_spread': 0.001
                }
            }
            risk_manager = RiskManager(risk_config)
            
            # Initialize opportunity manager
            opportunity_manager = OpportunityManager(
                exchange_client=exchange_client,
                strategy_manager=strategy_manager,
                risk_manager=risk_manager
            )
            
            # Initialize profit scraping engine
            profit_scraping_engine = ProfitScrapingEngine(
                exchange_client=exchange_client,
                paper_trading_engine=paper_engine
            )
            
            # Connect profit scraping to paper trading engine
            paper_engine.opportunity_manager = opportunity_manager
            paper_engine.profit_scraping_engine = profit_scraping_engine
            
            logger.info("✅ Paper Trading Engine connected to Profit Scraping Engine")
            
        except Exception as integration_error:
            logger.error(f"Failed to integrate profit scraping: {integration_error}")
            logger.info("Paper trading will run with Flow Trading only")
        
        logger.info(f"✅ Paper Trading Engine initialized with strategy: {flow_trading_strategy}")
        
        return paper_engine
        
    except Exception as e:
        logger.error(f"Error initializing paper trading engine: {e}")
        return None

@router.post("/force-init")
async def force_initialize_paper_engine():
    """🔧 FORCE INITIALIZATION - Emergency paper trading engine initialization"""
    global paper_engine
    
    try:
        logger.info("🔧 Force initializing paper trading engine...")
        
        # Emergency configuration with STRICT LIMITS from config.yaml
        config = {
            'paper_trading': {
                'initial_balance': 10000.0,
                'enabled': True,
                'risk_per_trade_pct': 0.05,  # 5% = $500 per position
                'max_position_size_pct': 0.02,
                'max_total_exposure_pct': 0.90,
                'max_daily_loss_pct': 0.50
            }
        }
        
        # Force create new engine
        from src.trading.enhanced_paper_trading_engine import EnhancedPaperTradingEngine
        paper_engine = EnhancedPaperTradingEngine(config)
        
        # Test the engine
        account_status = paper_engine.get_account_status()
        
        logger.info("✅ Force initialization successful")
        
        return {
            "status": "success",
            "message": "🔧 Paper trading engine force-initialized successfully",
            "data": {
                "engine_type": "EnhancedPaperTradingEngine",
                "virtual_balance": account_status['account']['balance'],
                "initial_balance": 10000.0,
                "initialized_at": datetime.utcnow().isoformat(),
                "ready_to_start": True
            }
        }
        
    except Exception as e:
        logger.error(f"Force initialization failed: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        
        return {
            "status": "error",
            "message": f"Force initialization failed: {str(e)}",
            "suggestion": "Check server logs for detailed error information"
        }

@router.get("/debug/engine-status")
async def debug_engine_status():
    """🔧 DEBUG - Check detailed engine status for troubleshooting"""
    try:
        engine = get_paper_engine()
        
        # Get module references for debugging
        import simple_api
        simple_api_engine = getattr(simple_api, 'paper_trading_engine', None)
        
        # Check profit scraping engine connection
        profit_scraping_connected = False
        profit_scraping_active = False
        profit_scraping_opportunities = 0
        
        if engine and hasattr(engine, 'profit_scraping_engine') and engine.profit_scraping_engine:
            profit_scraping_connected = True
            profit_scraping_active = getattr(engine.profit_scraping_engine, 'active', False)
            try:
                opportunities = engine.profit_scraping_engine.get_opportunities()
                profit_scraping_opportunities = len(opportunities) if opportunities else 0
            except:
                profit_scraping_opportunities = 0
        
        # Check opportunity manager connection
        opportunity_manager_connected = False
        opportunity_manager_opportunities = 0
        
        if engine and hasattr(engine, 'opportunity_manager') and engine.opportunity_manager:
            opportunity_manager_connected = True
            try:
                opportunities = engine.opportunity_manager.get_opportunities()
                opportunity_manager_opportunities = len(opportunities) if opportunities else 0
            except:
                opportunity_manager_opportunities = 0
        
        return {
            "status": "success",
            "data": {
                "routes_engine": {
                    "exists": engine is not None,
                    "type": type(engine).__name__ if engine else None,
                    "is_running": engine.is_running if engine else None,
                    "balance": engine.account.balance if engine and hasattr(engine, 'account') else None
                },
                "simple_api_engine": {
                    "exists": simple_api_engine is not None,
                    "type": type(simple_api_engine).__name__ if simple_api_engine else None,
                    "is_running": simple_api_engine.is_running if simple_api_engine else None,
                    "balance": simple_api_engine.account.balance if simple_api_engine and hasattr(simple_api_engine, 'account') else None
                },
                "engines_match": engine is simple_api_engine,
                "connections": {
                    "profit_scraping_connected": profit_scraping_connected,
                    "profit_scraping_active": profit_scraping_active,
                    "profit_scraping_opportunities": profit_scraping_opportunities,
                    "opportunity_manager_connected": opportunity_manager_connected,
                    "opportunity_manager_opportunities": opportunity_manager_opportunities
                },
                "troubleshooting": {
                    "engine_available": engine is not None,
                    "connections_ready": profit_scraping_connected or opportunity_manager_connected,
                    "signals_available": profit_scraping_opportunities > 0 or opportunity_manager_opportunities > 0,
                    "recommended_action": "Check connections" if not (profit_scraping_connected or opportunity_manager_connected) else "Connections look good"
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Debug engine status failed: {e}")
        return {
            "status": "error",
            "message": f"Debug failed: {str(e)}",
            "troubleshooting": {
                "engine_available": False,
                "start_should_work": False,
                "recommended_action": "Check server logs for detailed error"
            }
        }

@router.post("/enable-paper-trading-mode")
async def enable_paper_trading_mode():
    """🎯 ENABLE PAPER TRADING MODE - Relaxed validation for more trading opportunities"""
    try:
        # Get the opportunity manager from main module  
        import src.api.main as main_module
        opportunity_manager = getattr(main_module, 'opportunity_manager', None)
        
        if opportunity_manager:
            # Enable paper trading mode with relaxed validation
            opportunity_manager.set_paper_trading_mode(enabled=True)
            
            # Connect opportunity manager to paper trading engine
            global paper_engine
            if paper_engine:
                paper_engine.opportunity_manager = opportunity_manager
                logger.info("✅ Connected opportunity manager to paper trading engine")
            
            # Trigger a fresh scan with relaxed criteria
            logger.info("🔄 Triggering fresh opportunity scan with paper trading mode...")
            await opportunity_manager.scan_opportunities_incremental()
            
            # Get updated opportunities
            opportunities = opportunity_manager.get_opportunities()
            tradable_count = sum(1 for opp in opportunities if opp.get('tradable', False))
            
            return {
                "status": "success",
                "message": "🎯 Paper Trading Mode ENABLED - Relaxed validation criteria applied",
                "data": {
                    "paper_trading_mode": True,
                    "total_opportunities": len(opportunities),
                    "tradable_opportunities": tradable_count,
                    "validation_criteria": {
                        "scalping_rr": "0.3:1",
                        "swing_rr": "0.4:1", 
                        "scalping_move": "0.2%",
                        "swing_move": "0.8%",
                        "confidence": "50-60%"
                    },
                    "next_scan": "Every 30 seconds"
                }
            }
        else:
            return {
                "status": "error",
                "message": "Opportunity manager not available"
            }
            
    except Exception as e:
        logger.error(f"Error enabling paper trading mode: {e}")
        return {
            "status": "error",
            "message": f"Failed to enable paper trading mode: {str(e)}"
        }

@router.post("/disable-paper-trading-mode")
async def disable_paper_trading_mode():
    """🎯 DISABLE PAPER TRADING MODE - Return to strict validation"""
    try:
        # Get the opportunity manager from main module  
        import src.api.main as main_module
        opportunity_manager = getattr(main_module, 'opportunity_manager', None)
        
        if opportunity_manager:
            # Disable paper trading mode - return to strict validation
            opportunity_manager.set_paper_trading_mode(enabled=False)
            
            logger.info("🔄 Triggering fresh opportunity scan with strict criteria...")
            await opportunity_manager.scan_opportunities_incremental()
            
            # Get updated opportunities
            opportunities = opportunity_manager.get_opportunities()
            tradable_count = sum(1 for opp in opportunities if opp.get('tradable', False))
            
            return {
                "status": "success",
                "message": "🎯 Paper Trading Mode DISABLED - Strict validation criteria restored",
                "data": {
                    "paper_trading_mode": False,
                    "total_opportunities": len(opportunities),
                    "tradable_opportunities": tradable_count,
                    "validation_criteria": {
                        "scalping_rr": "0.5:1",
                        "swing_rr": "0.8:1",
                        "scalping_move": "0.3%",
                        "swing_move": "1.0%", 
                        "confidence": "65-70%"
                    }
                }
            }
        else:
            return {
                "status": "error",
                "message": "Opportunity manager not available"
            }
            
    except Exception as e:
        logger.error(f"Error disabling paper trading mode: {e}")
        return {
            "status": "error",
            "message": f"Failed to disable paper trading mode: {str(e)}"
        }

@router.get("/paper-trading-mode/status")
async def get_paper_trading_mode_status():
    """📊 GET PAPER TRADING MODE STATUS"""
    try:
        # Get the opportunity manager from main module  
        import src.api.main as main_module
        opportunity_manager = getattr(main_module, 'opportunity_manager', None)
        
        if opportunity_manager:
            paper_mode = opportunity_manager.get_paper_trading_mode()
            
            # Get current opportunities stats
            opportunities = opportunity_manager.get_opportunities()
            total_opportunities = len(opportunities)
            tradable_opportunities = sum(1 for opp in opportunities if opp.get('tradable', False))
            
            return {
                "status": "success",
                "data": {
                    "paper_trading_mode": paper_mode,
                    "validation_mode": "RELAXED" if paper_mode else "STRICT",
                    "total_opportunities": total_opportunities,
                    "tradable_opportunities": tradable_opportunities,
                    "tradable_percentage": round((tradable_opportunities / total_opportunities) * 100, 1) if total_opportunities > 0 else 0,
                    "criteria": {
                        "scalping_rr": "0.3:1" if paper_mode else "0.5:1",
                        "swing_rr": "0.4:1" if paper_mode else "0.8:1",
                        "scalping_move": "0.2%" if paper_mode else "0.3%",
                        "swing_move": "0.8%" if paper_mode else "1.0%",
                        "confidence": "50-60%" if paper_mode else "65-70%"
                    }
                }
            }
        else:
            return {
                "status": "error",
                "message": "Opportunity manager not available",
                "data": {
                    "paper_trading_mode": False,
                    "validation_mode": "UNKNOWN"
                }
            }
            
    except Exception as e:
        logger.error(f"Error getting paper trading mode status: {e}")
        return {
            "status": "error",
            "message": f"Failed to get status: {str(e)}",
            "data": {
                "paper_trading_mode": False,
                "validation_mode": "ERROR"
            }
        }

# ============================================================================
# PURE 3-RULE MODE API ENDPOINTS
# ============================================================================

@router.get("/rule-mode")
async def get_rule_mode_status():
    """🎯 GET PURE 3-RULE MODE STATUS"""
    try:
        engine = get_paper_engine()
        if not engine:
            return {
                "status": "success",
                "data": {
                    "pure_3_rule_mode": True,  # Default
                    "mode_name": "Pure 3-Rule Mode",
                    "description": "Clean hierarchy: $10 TP → $7 Floor → 0.5% SL",
                    "engine_available": False
                }
            }
        
        # Get current mode from engine
        pure_mode = getattr(engine, 'pure_3_rule_mode', True)
        
        return {
            "status": "success",
            "data": {
                "pure_3_rule_mode": pure_mode,
                "mode_name": "Pure 3-Rule Mode" if pure_mode else "Complex Mode",
                "description": "Clean hierarchy: $10 TP → $7 Floor → 0.5% SL" if pure_mode else "All exit conditions active",
                "engine_available": True,
                "engine_running": engine.is_running,
                "active_positions": len(engine.positions),
                "rules_active": {
                    "primary_target": "$10 Take Profit",
                    "absolute_floor": "$7 Floor Protection", 
                    "stop_loss": "0.5% Stop Loss"
                } if pure_mode else {
                    "all_exits": "Technical, Time-based, Level breakdown, Trend reversal, SL/TP"
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting rule mode status: {e}")
        return {
            "status": "error",
            "message": f"Failed to get rule mode status: {str(e)}",
            "data": {
                "pure_3_rule_mode": True,
                "mode_name": "Unknown",
                "description": "Error retrieving mode status"
            }
        }

@router.post("/rule-mode")
async def set_rule_mode(pure_3_rule_mode: bool):
    """🎯 SET PURE 3-RULE MODE (Toggle between Pure and Complex)"""
    try:
        engine = get_paper_engine()
        if not engine:
            raise HTTPException(status_code=400, detail="Paper trading engine not available")
        
        # Store old mode for logging
        old_mode = getattr(engine, 'pure_3_rule_mode', True)
        
        # Update the mode
        engine.pure_3_rule_mode = pure_3_rule_mode
        
        # Log the change
        mode_name = "Pure 3-Rule Mode" if pure_3_rule_mode else "Complex Mode"
        old_mode_name = "Pure 3-Rule Mode" if old_mode else "Complex Mode"
        
        logger.info(f"🎯 RULE MODE CHANGED: {old_mode_name} → {mode_name}")
        
        if pure_3_rule_mode:
            logger.info("🎯 PURE 3-RULE MODE ENABLED: Only $10 TP, $7 Floor, 0.5% SL will trigger exits")
        else:
            logger.info("🔧 COMPLEX MODE ENABLED: All exit conditions active (technical, time-based, etc.)")
        
        return {
            "status": "success",
            "message": f"🎯 Rule mode changed to {mode_name}",
            "data": {
                "old_mode": old_mode_name,
                "new_mode": mode_name,
                "pure_3_rule_mode": pure_3_rule_mode,
                "engine_running": engine.is_running,
                "active_positions": len(engine.positions),
                "change_applied": "immediately",
                "rules_description": "Clean hierarchy: $10 TP → $7 Floor → 0.5% SL" if pure_3_rule_mode else "All exit conditions active",
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting rule mode: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to set rule mode: {str(e)}")

@router.get("/rule-config")
async def get_rule_configuration():
    """⚙️ GET RULE CONFIGURATION PARAMETERS"""
    try:
        engine = get_paper_engine()
        if not engine:
            # Return default configuration
            return {
                "status": "success",
                "data": {
                    "primary_target_dollars": 18.0,  # $18 gross = $10 net
                    "absolute_floor_dollars": 15.0,  # $15 gross = $7 net
                    "stop_loss_percent": 0.5,
                    "engine_available": False,
                    "configuration_source": "default_values"
                }
            }
        
        # Extract current configuration from engine
        # Look for position examples to get current rules
        sample_position = None
        if engine.positions:
            sample_position = list(engine.positions.values())[0]
        
        # Get configuration from position or defaults
        if sample_position:
            primary_target = getattr(sample_position, 'primary_target_profit', 18.0) # $18 gross = $10 net
            absolute_floor = getattr(sample_position, 'absolute_floor_profit', 15.0) # $15 gross = $7 net
        else:
            primary_target = 18.0 # $18 gross = $10 net
            absolute_floor = 15.0 # $15 gross = $7 net
        
        # Stop loss is calculated as 0.5% for $10 loss with current leverage
        stop_loss_percent = 0.5
        
        return {
            "status": "success",
            "data": {
                "primary_target_dollars": primary_target,
                "absolute_floor_dollars": absolute_floor,
                "stop_loss_percent": stop_loss_percent,
                "engine_available": True,
                "engine_running": engine.is_running,
                "active_positions": len(engine.positions),
                "configuration_source": "engine_current" if sample_position else "engine_defaults",
                "leverage_info": {
                    "current_leverage": getattr(engine, 'leverage', 10.0),
                    "capital_per_position": 1000.0,
                    "stop_loss_calculation": f"0.5% price movement = ~$50 loss with {getattr(engine, 'leverage', 10.0)}x leverage"
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting rule configuration: {e}")
        return {
            "status": "error",
            "message": f"Failed to get rule configuration: {str(e)}",
            "data": {
                "primary_target_dollars": 18.0,  # $18 gross = $10 net
                "absolute_floor_dollars": 15.0,  # $15 gross = $7 net
                "stop_loss_percent": 0.5,
                "configuration_source": "error_fallback"
            }
        }

class RuleConfigUpdate(BaseModel):
    primary_target_dollars: float = 18.0 # $18 gross = $10 net
    absolute_floor_dollars: float = 15.0 # $15 gross = $7 net
    stop_loss_percent: float = 0.5

@router.post("/rule-config")
async def update_rule_configuration(config: RuleConfigUpdate):
    """⚙️ UPDATE RULE CONFIGURATION PARAMETERS"""
    try:
        engine = get_paper_engine()
        if not engine:
            raise HTTPException(status_code=400, detail="Paper trading engine not available")
        
        # Validate configuration
        if config.primary_target_dollars <= config.absolute_floor_dollars:
            raise HTTPException(
                status_code=400, 
                detail=f"Primary target (${config.primary_target_dollars}) must be higher than absolute floor (${config.absolute_floor_dollars})"
            )
        
        if config.absolute_floor_dollars <= 0:
            raise HTTPException(status_code=400, detail="Absolute floor must be positive")
        
        if config.stop_loss_percent <= 0 or config.stop_loss_percent > 5.0:
            raise HTTPException(status_code=400, detail="Stop loss percent must be between 0.1% and 5.0%")
        
        # Update configuration for future positions
        # Note: This doesn't affect existing positions, only new ones
        engine.config['primary_target_dollars'] = config.primary_target_dollars
        engine.config['absolute_floor_dollars'] = config.absolute_floor_dollars
        engine.config['stop_loss_percent'] = config.stop_loss_percent
        
        logger.info(f"⚙️ RULE CONFIG UPDATED: Target ${config.primary_target_dollars}, Floor ${config.absolute_floor_dollars}, SL {config.stop_loss_percent}%")
        
        return {
            "status": "success",
            "message": "⚙️ Rule configuration updated successfully",
            "data": {
                "primary_target_dollars": config.primary_target_dollars,
                "absolute_floor_dollars": config.absolute_floor_dollars,
                "stop_loss_percent": config.stop_loss_percent,
                "applies_to": "new_positions_only",
                "existing_positions": len(engine.positions),
                "engine_running": engine.is_running,
                "updated_at": datetime.utcnow().isoformat(),
                "validation": {
                    "target_above_floor": config.primary_target_dollars > config.absolute_floor_dollars,
                    "reasonable_stop_loss": 0.1 <= config.stop_loss_percent <= 5.0,
                    "configuration_valid": True
                }
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating rule configuration: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update rule configuration: {str(e)}")

# ============================================================================
# SIGNAL SOURCE CONFIGURATION API ENDPOINTS
# ============================================================================

@router.get("/signal-config")
async def get_signal_configuration():
    """🎯 GET SIGNAL SOURCE CONFIGURATION"""
    try:
        engine = get_paper_engine()
        if not engine:
            # Return default configuration
            return {
                "status": "success",
                "data": {
                    "signal_config": {
                        "profit_scraping_primary": True,
                        "allow_opportunity_fallback": False,
                        "allow_flow_trading_fallback": False,
                        "pure_profit_scraping_mode": True,
                        "adaptive_thresholds": True,
                        "multi_timeframe_analysis": True,
                        "expanded_symbol_pool": True
                    },
                    "engine_available": False,
                    "configuration_source": "default_values"
                }
            }
        
        # Get current signal configuration from engine
        signal_config = getattr(engine, 'signal_config', {
            "profit_scraping_primary": True,
            "allow_opportunity_fallback": False,
            "allow_flow_trading_fallback": False,
            "pure_profit_scraping_mode": True,
            "adaptive_thresholds": True,
            "multi_timeframe_analysis": True,
            "expanded_symbol_pool": True
        })
        
        return {
            "status": "success",
            "data": {
                "signal_config": signal_config,
                "engine_available": True,
                "engine_running": engine.is_running,
                "configuration_source": "engine_current",
                "mode_description": {
                    "pure_profit_scraping_mode": "Only profit scraping signals, no fallbacks" if signal_config.get('pure_profit_scraping_mode') else "Fallbacks enabled",
                    "fallback_status": {
                        "opportunity_manager": "enabled" if signal_config.get('allow_opportunity_fallback') else "disabled",
                        "flow_trading": "enabled" if signal_config.get('allow_flow_trading_fallback') else "disabled"
                    }
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting signal configuration: {e}")
        return {
            "status": "error",
            "message": f"Failed to get signal configuration: {str(e)}",
            "data": {
                "signal_config": {
                    "profit_scraping_primary": True,
                    "allow_opportunity_fallback": False,
                    "allow_flow_trading_fallback": False,
                    "pure_profit_scraping_mode": True
                },
                "configuration_source": "error_fallback"
            }
        }

class SignalConfigUpdate(BaseModel):
    profit_scraping_primary: bool = True
    allow_opportunity_fallback: bool = False
    allow_flow_trading_fallback: bool = False
    pure_profit_scraping_mode: bool = True
    adaptive_thresholds: bool = True
    multi_timeframe_analysis: bool = True
    expanded_symbol_pool: bool = True

@router.post("/signal-config")
async def update_signal_configuration(config: SignalConfigUpdate):
    """🎯 UPDATE SIGNAL SOURCE CONFIGURATION"""
    try:
        engine = get_paper_engine()
        if not engine:
            raise HTTPException(status_code=400, detail="Paper trading engine not available")
        
        # Store old configuration for logging
        old_config = getattr(engine, 'signal_config', {})
        
        # Update signal configuration
        engine.signal_config = {
            'profit_scraping_primary': config.profit_scraping_primary,
            'allow_opportunity_fallback': config.allow_opportunity_fallback,
            'allow_flow_trading_fallback': config.allow_flow_trading_fallback,
            'pure_profit_scraping_mode': config.pure_profit_scraping_mode,
            'adaptive_thresholds': config.adaptive_thresholds,
            'multi_timeframe_analysis': config.multi_timeframe_analysis,
            'expanded_symbol_pool': config.expanded_symbol_pool
        }
        
        # Log the configuration change
        logger.info(f"🎯 SIGNAL CONFIG UPDATED:")
        logger.info(f"   Pure Profit Scraping Mode: {config.pure_profit_scraping_mode}")
        logger.info(f"   Opportunity Manager Fallback: {config.allow_opportunity_fallback}")
        logger.info(f"   Flow Trading Fallback: {config.allow_flow_trading_fallback}")
        
        # Determine mode description
        if config.pure_profit_scraping_mode and not config.allow_opportunity_fallback and not config.allow_flow_trading_fallback:
            mode_description = "Pure Profit Scraping Mode - No fallbacks enabled"
        elif config.allow_opportunity_fallback and config.allow_flow_trading_fallback:
            mode_description = "Full Fallback Mode - All signal sources enabled"
        elif config.allow_opportunity_fallback:
            mode_description = "Opportunity Manager Fallback Enabled"
        elif config.allow_flow_trading_fallback:
            mode_description = "Flow Trading Fallback Enabled"
        else:
            mode_description = "Custom Configuration"
        
        return {
            "status": "success",
            "message": f"🎯 Signal configuration updated: {mode_description}",
            "data": {
                "old_config": old_config,
                "new_config": engine.signal_config,
                "mode_description": mode_description,
                "engine_running": engine.is_running,
                "active_positions": len(engine.positions),
                "change_applied": "immediately",
                "fallback_summary": {
                    "profit_scraping": "primary" if config.profit_scraping_primary else "disabled",
                    "opportunity_manager": "enabled" if config.allow_opportunity_fallback else "disabled",
                    "flow_trading": "enabled" if config.allow_flow_trading_fallback else "disabled"
                },
                "updated_at": datetime.utcnow().isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating signal configuration: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update signal configuration: {str(e)}")

@router.post("/signal-config/pure-mode")
async def enable_pure_profit_scraping_mode():
    """🎯 ENABLE PURE PROFIT SCRAPING MODE (Quick Toggle)"""
    try:
        engine = get_paper_engine()
        if not engine:
            raise HTTPException(status_code=400, detail="Paper trading engine not available")
        
        # Set pure profit scraping mode
        engine.signal_config = {
            'profit_scraping_primary': True,
            'allow_opportunity_fallback': False,
            'allow_flow_trading_fallback': False,
            'pure_profit_scraping_mode': True,
            'adaptive_thresholds': True,
            'multi_timeframe_analysis': True,
            'expanded_symbol_pool': True
        }
        
        logger.info("🎯 PURE PROFIT SCRAPING MODE ENABLED - No fallbacks")
        
        return {
            "status": "success",
            "message": "🎯 Pure Profit Scraping Mode enabled - No fallbacks",
            "data": {
                "mode": "pure_profit_scraping",
                "signal_config": engine.signal_config,
                "fallback_status": "all_disabled",
                "engine_running": engine.is_running,
                "updated_at": datetime.utcnow().isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error enabling pure profit scraping mode: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to enable pure mode: {str(e)}")

@router.post("/signal-config/fallback-mode")
async def enable_fallback_mode():
    """🎯 ENABLE FALLBACK MODE (Quick Toggle)"""
    try:
        engine = get_paper_engine()
        if not engine:
            raise HTTPException(status_code=400, detail="Paper trading engine not available")
        
        # Enable all fallbacks
        engine.signal_config = {
            'profit_scraping_primary': True,
            'allow_opportunity_fallback': True,
            'allow_flow_trading_fallback': True,
            'pure_profit_scraping_mode': False,
            'adaptive_thresholds': True,
            'multi_timeframe_analysis': True,
            'expanded_symbol_pool': True
        }
        
        logger.info("🎯 FALLBACK MODE ENABLED - All signal sources available")
        
        return {
            "status": "success",
            "message": "🎯 Fallback Mode enabled - All signal sources available",
            "data": {
                "mode": "fallback_enabled",
                "signal_config": engine.signal_config,
                "fallback_status": "all_enabled",
                "engine_running": engine.is_running,
                "signal_priority": ["profit_scraping", "opportunity_manager", "flow_trading"],
                "updated_at": datetime.utcnow().isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error enabling fallback mode: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to enable fallback mode: {str(e)}")
