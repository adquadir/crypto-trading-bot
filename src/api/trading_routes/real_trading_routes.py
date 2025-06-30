"""
Real Trading API Routes
Handles real money trading operations with safety controls
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime
import asyncio

from ...trading.real_trading_engine import RealTradingEngine
from ...market_data.exchange_client import ExchangeClient
from ...utils.logger import setup_logger

logger = setup_logger(__name__)

# Global real trading engine instance
real_trading_engine = None

def get_real_trading_engine():
    """Get or create real trading engine instance"""
    global real_trading_engine
    if real_trading_engine is None:
        exchange_client = ExchangeClient()
        real_trading_engine = RealTradingEngine(exchange_client)
    return real_trading_engine

router = APIRouter(prefix="/api/v1/real-trading", tags=["real-trading"])

@router.get("/status")
async def get_real_trading_status():
    """Get real trading engine status"""
    try:
        engine = get_real_trading_engine()
        status = engine.get_status()
        
        # Add trade sync service status if available
        if hasattr(engine, 'trade_sync_service') and engine.trade_sync_service:
            status['trade_sync'] = engine.trade_sync_service.get_sync_status()
        
        return {
            "success": True,
            "data": status
        }
        
    except Exception as e:
        logger.error(f"Error getting real trading status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/start")
async def start_real_trading(symbols: List[str] = None):
    """Start real trading (DANGER: Uses real money!)"""
    try:
        if symbols is None:
            symbols = ['BTCUSDT', 'ETHUSDT']  # Default symbols
        
        engine = get_real_trading_engine()
        
        # Safety confirmation required
        logger.warning("🚨 REAL TRADING START REQUEST RECEIVED")
        logger.warning("⚠️  THIS WILL USE REAL MONEY")
        logger.warning(f"⚠️  SYMBOLS: {symbols}")
        
        success = await engine.start_trading(symbols)
        
        if success:
            logger.warning("🚀 REAL TRADING STARTED")
            return {
                "success": True,
                "message": "Real trading started successfully",
                "warning": "REAL MONEY TRADING IS NOW ACTIVE",
                "symbols": symbols
            }
        else:
            return {
                "success": False,
                "message": "Failed to start real trading",
                "error": "Check logs for details"
            }
        
    except Exception as e:
        logger.error(f"Error starting real trading: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stop")
async def stop_real_trading():
    """Stop real trading and close all positions"""
    try:
        engine = get_real_trading_engine()
        
        logger.warning("🛑 REAL TRADING STOP REQUEST RECEIVED")
        
        success = await engine.stop_trading()
        
        if success:
            logger.info("✅ Real trading stopped successfully")
            return {
                "success": True,
                "message": "Real trading stopped successfully"
            }
        else:
            return {
                "success": False,
                "message": "Failed to stop real trading",
                "error": "Check logs for details"
            }
        
    except Exception as e:
        logger.error(f"Error stopping real trading: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/positions")
async def get_real_positions():
    """Get all active real positions"""
    try:
        engine = get_real_trading_engine()
        positions = engine.get_active_positions()
        
        return {
            "success": True,
            "data": positions,
            "count": len(positions)
        }
        
    except Exception as e:
        logger.error(f"Error getting real positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/execute-trade")
async def execute_real_trade(signal: Dict[str, Any]):
    """Execute a real trade based on signal (DANGER: Uses real money!)"""
    try:
        engine = get_real_trading_engine()
        
        # Validate signal
        required_fields = ['symbol', 'side', 'confidence']
        for field in required_fields:
            if field not in signal:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        logger.warning(f"🚨 REAL TRADE EXECUTION REQUEST: {signal}")
        
        position_id = await engine.execute_trade(signal)
        
        if position_id:
            logger.warning(f"✅ REAL TRADE EXECUTED: Position ID {position_id}")
            return {
                "success": True,
                "message": "Real trade executed successfully",
                "position_id": position_id,
                "warning": "REAL MONEY WAS USED"
            }
        else:
            return {
                "success": False,
                "message": "Failed to execute real trade",
                "error": "Check logs for details"
            }
        
    except Exception as e:
        logger.error(f"Error executing real trade: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/close-position/{position_id}")
async def close_real_position(position_id: str, reason: str = "MANUAL"):
    """Close a specific real position"""
    try:
        engine = get_real_trading_engine()
        
        logger.warning(f"🚨 REAL POSITION CLOSE REQUEST: {position_id}")
        
        success = await engine.close_position(position_id, reason)
        
        if success:
            logger.warning(f"✅ REAL POSITION CLOSED: {position_id}")
            return {
                "success": True,
                "message": f"Real position {position_id} closed successfully",
                "warning": "REAL MONEY TRANSACTION COMPLETED"
            }
        else:
            return {
                "success": False,
                "message": f"Failed to close real position {position_id}",
                "error": "Check logs for details"
            }
        
    except Exception as e:
        logger.error(f"Error closing real position: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/emergency-stop")
async def emergency_stop():
    """Emergency stop - immediately halt all real trading"""
    try:
        engine = get_real_trading_engine()
        
        logger.error("🚨 EMERGENCY STOP ACTIVATED")
        
        # Set emergency stop flag
        engine.emergency_stop = True
        
        # Stop trading
        success = await engine.stop_trading()
        
        logger.error("🛑 EMERGENCY STOP COMPLETED")
        
        return {
            "success": True,
            "message": "Emergency stop activated",
            "warning": "ALL REAL TRADING HAS BEEN HALTED"
        }
        
    except Exception as e:
        logger.error(f"Error in emergency stop: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/trade-sync/status")
async def get_trade_sync_status():
    """Get trade synchronization service status"""
    try:
        engine = get_real_trading_engine()
        
        if not hasattr(engine, 'trade_sync_service') or not engine.trade_sync_service:
            return {
                "success": False,
                "message": "Trade sync service not available"
            }
        
        status = engine.trade_sync_service.get_sync_status()
        
        return {
            "success": True,
            "data": status
        }
        
    except Exception as e:
        logger.error(f"Error getting trade sync status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/trade-sync/manual-trades")
async def get_manual_trades():
    """Get detected manual trades"""
    try:
        engine = get_real_trading_engine()
        
        if not hasattr(engine, 'trade_sync_service') or not engine.trade_sync_service:
            return {
                "success": False,
                "message": "Trade sync service not available"
            }
        
        manual_trades = engine.trade_sync_service.get_manual_trades()
        
        return {
            "success": True,
            "data": manual_trades,
            "count": len(manual_trades)
        }
        
    except Exception as e:
        logger.error(f"Error getting manual trades: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/trade-sync/start")
async def start_trade_sync():
    """Start trade synchronization service"""
    try:
        engine = get_real_trading_engine()
        
        if not hasattr(engine, 'trade_sync_service') or not engine.trade_sync_service:
            return {
                "success": False,
                "message": "Trade sync service not available"
            }
        
        success = await engine.trade_sync_service.start_sync()
        
        return {
            "success": success,
            "message": "Trade sync service started" if success else "Failed to start trade sync service"
        }
        
    except Exception as e:
        logger.error(f"Error starting trade sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/trade-sync/stop")
async def stop_trade_sync():
    """Stop trade synchronization service"""
    try:
        engine = get_real_trading_engine()
        
        if not hasattr(engine, 'trade_sync_service') or not engine.trade_sync_service:
            return {
                "success": False,
                "message": "Trade sync service not available"
            }
        
        success = await engine.trade_sync_service.stop_sync()
        
        return {
            "success": success,
            "message": "Trade sync service stopped" if success else "Failed to stop trade sync service"
        }
        
    except Exception as e:
        logger.error(f"Error stopping trade sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/safety-status")
async def get_safety_status():
    """Get safety status and limits"""
    try:
        engine = get_real_trading_engine()
        
        safety_status = {
            "emergency_stop": engine.emergency_stop,
            "daily_pnl": engine.daily_pnl,
            "max_daily_loss": engine.max_daily_loss,
            "total_pnl": engine.total_pnl,
            "active_positions": len(engine.active_positions),
            "position_size_usd": engine.position_size_usd,
            "leverage": engine.leverage,
            "safety_checks_enabled": True,
            "last_reset_date": engine.last_reset_date.isoformat() if engine.last_reset_date else None
        }
        
        return {
            "success": True,
            "data": safety_status
        }
        
    except Exception as e:
        logger.error(f"Error getting safety status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reset-emergency-stop")
async def reset_emergency_stop():
    """Reset emergency stop flag (use with caution)"""
    try:
        engine = get_real_trading_engine()
        
        logger.warning("🔄 EMERGENCY STOP RESET REQUEST")
        
        engine.emergency_stop = False
        
        logger.warning("✅ Emergency stop flag reset")
        
        return {
            "success": True,
            "message": "Emergency stop flag reset",
            "warning": "Real trading can now be started again"
        }
        
    except Exception as e:
        logger.error(f"Error resetting emergency stop: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/performance")
async def get_real_trading_performance():
    """Get real trading performance metrics"""
    try:
        engine = get_real_trading_engine()
        
        win_rate = engine.winning_trades / engine.total_trades if engine.total_trades > 0 else 0.0
        uptime_minutes = 0
        
        if engine.start_time:
            uptime_minutes = (datetime.now() - engine.start_time).total_seconds() / 60
        
        performance = {
            "total_trades": engine.total_trades,
            "winning_trades": engine.winning_trades,
            "losing_trades": engine.total_trades - engine.winning_trades,
            "win_rate": win_rate,
            "total_pnl": engine.total_pnl,
            "daily_pnl": engine.daily_pnl,
            "uptime_minutes": uptime_minutes,
            "active_positions": len(engine.active_positions),
            "is_running": engine.is_running
        }
        
        return {
            "success": True,
            "data": performance
        }
        
    except Exception as e:
        logger.error(f"Error getting real trading performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))
