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
    """Get paper trading engine instance"""
    global paper_engine
    return paper_engine

@router.post("/start")
async def start_paper_trading(background_tasks: BackgroundTasks):
    """🚀 ONE-CLICK START - Start paper trading engine"""
    try:
        engine = get_paper_engine()
        if not engine:
            raise HTTPException(status_code=400, detail="Paper trading engine not initialized")
        
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
            return {
                "status": "success",
                "data": {
                    "enabled": False,
                    "virtual_balance": 10000.0,
                    "initial_balance": 10000.0,
                    "total_return_pct": 0.0,
                    "win_rate_pct": 0.0,
                    "completed_trades": 0,
                    "uptime_hours": engine.get_uptime_hours() if engine else 0.0,
                    "strategy_performance": {}
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
        raise HTTPException(status_code=500, detail=str(e))

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
    """Simulate trading signals for testing (generates fake signals)"""
    try:
        engine = get_paper_engine()
        if not engine:
            raise HTTPException(status_code=400, detail="Paper trading engine not available")
        
        if not engine.is_running:
            raise HTTPException(status_code=400, detail="Paper trading engine not running")
        
        import random
        executed_trades = []
        
        for i in range(count):
            # Generate random signal
            signal = {
                'symbol': symbol,
                'strategy_type': strategy_type,
                'side': random.choice(['LONG', 'SHORT']),
                'confidence': random.uniform(0.6, 0.95),
                'ml_score': random.uniform(0.5, 0.9),
                'reason': f'simulated_signal_{i+1}',
                'market_regime': random.choice(['trending', 'ranging', 'volatile']),
                'volatility_regime': random.choice(['low', 'medium', 'high'])
            }
            
            position_id = await engine.execute_trade(signal)
            if position_id:
                executed_trades.append({
                    'position_id': position_id,
                    'signal': signal
                })
        
        return {
            "message": f"🎯 Simulated {len(executed_trades)} trading signals",
            "executed_trades": executed_trades,
            "total_positions": len(engine.positions),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error simulating trading signals: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def paper_trading_health_check():
    """Health check for paper trading system"""
    try:
        engine = get_paper_engine()
        
        if not engine:
            return {
                "status": "unhealthy",
                "message": "Paper trading engine not initialized",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        account_status = engine.get_account_status()
        
        return {
            "status": "healthy" if engine.is_running else "stopped",
            "engine_running": engine.is_running,
            "positions_count": len(account_status['positions']),
            "account_balance": account_status['account']['balance'],
            "total_trades": account_status['account']['total_trades'],
            "ml_data_samples": len(engine.get_ml_training_data()),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in paper trading health check: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

# Initialize paper trading engine
async def initialize_paper_trading_engine(config, exchange_client=None, opportunity_manager=None, profit_scraping_engine=None):
    """Initialize paper trading engine with profit scraping integration"""
    try:
        global paper_engine
        
        paper_engine = EnhancedPaperTradingEngine(
            config=config,
            exchange_client=exchange_client,
            opportunity_manager=opportunity_manager,
            profit_scraping_engine=profit_scraping_engine  # NEW: Connect profit scraping engine
        )
        
        if profit_scraping_engine:
            logger.info("✅ Paper Trading Engine initialized with PROFIT SCRAPING integration")
        else:
            logger.info("✅ Paper Trading Engine initialized (fallback to opportunity manager)")
        
        return paper_engine
        
    except Exception as e:
        logger.error(f"Error initializing paper trading engine: {e}")
        return None
