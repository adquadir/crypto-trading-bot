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
                    "uptime_hours": 0.0,
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
                "uptime_hours": 0.0,
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
                "uptime_hours": 0.0,
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
                    "uptime_hours": 0.0,
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
                "uptime_hours": 0.0,
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
    """Get detailed performance analytics"""
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
        
        # Get trades from the last 7 days
        end_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        for i in range(7):
            day_start = end_date - timedelta(days=i)
            day_end = day_start + timedelta(days=1)
            
            # Get trades for this day
            day_trades = [
                t for t in account_status['recent_trades'] 
                if day_start <= datetime.fromisoformat(t['exit_time'].replace('Z', '+00:00').replace('+00:00', '')) < day_end
            ]
            
            # Calculate real daily P&L and trade count
            daily_pnl = sum(t.get('pnl', 0) for t in day_trades)
            trade_count = len(day_trades)
            
            daily_performance.append({
                "timestamp": day_start.isoformat(),
                "daily_pnl": daily_pnl,
                "total_trades": trade_count
            })
        
        # Reverse to show oldest to newest
        daily_performance.reverse()
        
        return {
            "status": "success",
            "data": {
                "daily_performance": daily_performance,
                "account_performance": account,
                "strategy_performance": account_status['strategy_performance']
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting performance analytics: {e}")
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
async def initialize_paper_trading_engine(config, exchange_client=None, opportunity_manager=None):
    """Initialize paper trading engine"""
    try:
        global paper_engine
        
        paper_engine = EnhancedPaperTradingEngine(
            config=config,
            exchange_client=exchange_client,
            opportunity_manager=opportunity_manager
        )
        
        logger.info("✅ Paper Trading Engine initialized and ready")
        return paper_engine
        
    except Exception as e:
        logger.error(f"Error initializing paper trading engine: {e}")
        return None
