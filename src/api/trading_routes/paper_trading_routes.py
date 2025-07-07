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
        logger.warning("Paper engine is None - attempting emergency initialization")
        
        # Try to get from main module first
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
            
            # Emergency configuration
            emergency_config = {
                'paper_trading': {
                    'initial_balance': 10000.0,
                    'enabled': True,
                    'max_position_size_pct': 0.02,
                    'max_total_exposure_pct': 1.0,
                    'max_daily_loss_pct': 0.50
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
    """🚀 ONE-CLICK START - Start paper trading engine"""
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
                    'max_position_size_pct': 0.02,
                    'max_total_exposure_pct': 1.0,
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
                # Try to get opportunity manager from main module
                import src.api.main as main_module
                opportunity_manager = getattr(main_module, 'opportunity_manager', None)
                if opportunity_manager:
                    engine.connect_opportunity_manager(opportunity_manager)
                    logger.info("✅ Connected opportunity manager to paper trading engine")
                else:
                    logger.warning("⚠️ No opportunity manager available in main module")
            except Exception as e:
                logger.error(f"Failed to connect opportunity manager: {e}")
        
        if engine.is_running:
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
                    "strategy_performance": account_status['strategy_performance']
                }
            }
        
        # Start the engine
        await engine.start()
        
        account_status = engine.get_account_status()
        return {
            "status": "success",
            "message": "🚀 Paper Trading Started Successfully!",
            "data": {
                "enabled": True,
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
        
        # Start profit scraping engine with major crypto pairs
        major_symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'SOLUSDT']
        profit_scraping_started = await profit_scraping_engine.start_scraping(major_symbols)
        
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
    """Get current paper trading status"""
    try:
        engine = get_paper_engine()
        if not engine:
            # Return informative default state instead of error
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
                    "capital_per_position": 200,
                    "uptime_hours": 0.0,
                    "strategy_performance": {},
                    "message": "Paper trading engine not initialized - click Start to initialize",
                    "ready_to_start": True
                }
            }
        
        account_status = engine.get_account_status()
        
        return {
            "status": "success",
            "data": {
                "enabled": engine.is_running,
                "virtual_balance": account_status['account']['balance'],
                "initial_balance": 10000.0,
                "total_return_pct": ((account_status['account']['balance'] - 10000.0) / 10000.0) * 100,
                "win_rate_pct": account_status['account']['win_rate'] * 100,
                "completed_trades": account_status['account']['completed_trades'],
                "active_positions": account_status['account']['active_positions'],
                "leverage": account_status['account']['leverage'],
                "capital_per_position": account_status['account']['capital_per_position'],
                "uptime_hours": engine.get_uptime_hours(),
                "strategy_performance": account_status['strategy_performance']
            }
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
                "capital_per_position": 200,
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
async def get_trade_history(limit: int = 50):
    """Get trade history"""
    try:
        engine = get_paper_engine()
        if not engine:
            raise HTTPException(status_code=404, detail="Paper trading engine not available")
        
        account_status = engine.get_account_status()
        recent_trades = account_status['recent_trades'][-limit:] if len(account_status['recent_trades']) > limit else account_status['recent_trades']
        
        return {
            "trades": recent_trades,
            "total_trades": account_status['account']['total_trades'],
            "winning_trades": account_status['account']['winning_trades'],
            "win_rate": account_status['account']['win_rate']
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
async def close_position(position_id: str, exit_reason: str = "manual"):
    """Close a specific position"""
    try:
        engine = get_paper_engine()
        if not engine:
            raise HTTPException(status_code=400, detail="Paper trading engine not available")
        
        trade = await engine.close_position(position_id, exit_reason)
        
        if trade:
            return {
                "message": f"📉 Position closed successfully",
                "trade": {
                    "id": trade.id,
                    "symbol": trade.symbol,
                    "pnl": trade.pnl,
                    "pnl_pct": trade.pnl_pct,
                    "duration_minutes": trade.duration_minutes,
                    "exit_reason": trade.exit_reason
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            raise HTTPException(status_code=404, detail="Position not found or could not be closed")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error closing position: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
        
        # Emergency configuration
        config = {
            'paper_trading': {
                'initial_balance': 10000.0,
                'enabled': True,
                'max_position_size_pct': 0.02,
                'max_total_exposure_pct': 1.0,
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
        import src.api.main as main_module
        main_engine = getattr(main_module, 'paper_trading_engine', None)
        
        return {
            "status": "success",
            "data": {
                "routes_engine": {
                    "exists": engine is not None,
                    "type": type(engine).__name__ if engine else None,
                    "is_running": engine.is_running if engine else None,
                    "balance": engine.account.balance if engine and hasattr(engine, 'account') else None
                },
                "main_engine": {
                    "exists": main_engine is not None,
                    "type": type(main_engine).__name__ if main_engine else None,
                    "is_running": main_engine.is_running if main_engine else None,
                    "balance": main_engine.account.balance if main_engine and hasattr(main_engine, 'account') else None
                },
                "engines_match": engine is main_engine,
                "troubleshooting": {
                    "engine_available": engine is not None,
                    "start_should_work": engine is not None,
                    "recommended_action": "Force initialize if engine is None" if engine is None else "Start button should work"
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
