"""
Real Trading API Routes
Handles real money trading operations with OpportunityManager integration
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime
import asyncio
import yaml

from ...trading.real_trading_engine import RealTradingEngine
from ...market_data.exchange_client import ExchangeClient
from ...utils.logger import setup_logger

logger = setup_logger(__name__)

# Global real trading engine instance
real_trading_engine = None

def get_real_trading_engine():
    """Get or create real trading engine instance with auto-connected OpportunityManager"""
    global real_trading_engine
    if real_trading_engine is None:
        # Load configuration
        try:
            with open('config/config.yaml', 'r') as f:
                config = yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            config = {}
        
        exchange_client = ExchangeClient()
        real_trading_engine = RealTradingEngine(config, exchange_client)
        
        # Auto-connect OpportunityManager
        try:
            from ...opportunity.opportunity_manager import OpportunityManager
            opportunity_manager = OpportunityManager()
            real_trading_engine.connect_opportunity_manager(opportunity_manager)
            logger.info("✅ OpportunityManager auto-connected to Real Trading Engine")
        except Exception as e:
            logger.warning(f"Could not auto-connect OpportunityManager: {e}")
    
    return real_trading_engine

class StartPayload(BaseModel):
    symbols: Optional[List[str]] = None

router = APIRouter(prefix="/api/v1/real-trading", tags=["real-trading"])

@router.get("/status")
async def get_real_trading_status():
    """Get real trading engine status"""
    try:
        engine = get_real_trading_engine()
        status = engine.get_status()
        
        # 🔧 Compatibility aliases for the frontend
        status.setdefault("active", status.get("is_running", False))
        status.setdefault("is_running", status.get("active", False))
        
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
async def start_real_trading(payload: StartPayload):
    """Start real trading (DANGER: Uses real money!)"""
    try:
        symbols = payload.symbols or ['BTCUSDT', 'ETHUSDT']  # Default symbols
        
        engine = get_real_trading_engine()
        
        # Safety confirmation required
        logger.warning("🚨 REAL TRADING START REQUEST RECEIVED")
        logger.warning("⚠️  THIS WILL USE REAL MONEY")
        logger.warning(f"⚠️  SYMBOLS: {symbols}")
        logger.warning("⚠️  USING OPPORTUNITY MANAGER SIGNALS ONLY")
        
        success = await engine.start_trading(symbols)
        
        if success:
            logger.warning("🚀 REAL TRADING STARTED")
            return {
                "success": True,
                "message": "Real trading started successfully",
                "warning": "REAL MONEY TRADING IS NOW ACTIVE",
                "symbols": symbols,
                "signal_source": "opportunity_manager_only",
                "stake_per_trade": engine.stake_usd,
                "max_positions": engine.max_positions
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

@router.get("/completed-trades")
async def get_completed_trades():
    """Get all completed real trades"""
    try:
        engine = get_real_trading_engine()
        trades = engine.get_completed_trades()
        
        return {
            "success": True,
            "data": trades,
            "count": len(trades)
        }
        
    except Exception as e:
        logger.error(f"Error getting completed trades: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/close-position/{position_id}")
async def close_real_position(position_id: str, reason: str = "MANUAL"):
    """Close a specific real position (idempotent)"""
    try:
        engine = get_real_trading_engine()
        
        # Check if position exists
        pos = engine.positions.get(position_id)
        if not pos:
            return {
                "success": False,
                "message": f"Position {position_id} not found",
                "error": "Position does not exist"
            }, 404
        
        logger.warning(f"🚨 REAL POSITION CLOSE REQUEST: {position_id} ({pos.symbol})")
        
        # 🔒 Idempotent guard: if already flat on exchange, just mark closed locally
        if not await engine._has_open_position_on_exchange(pos.symbol):
            logger.info(f"🔒 IDEMPOTENT: Position {pos.symbol} already flat on exchange")
            await engine._mark_position_closed(position_id, reason="already_flat")
            return {
                "success": True,
                "message": f"Real position {position_id} was already closed on exchange",
                "idempotent": True,
                "warning": "Position was already flat - marked as closed locally"
            }
        
        # Otherwise do the normal market close
        success = await engine._market_close_position(position_id, reason)
        
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

@router.post("/connect-opportunity-manager")
async def connect_opportunity_manager():
    """Connect OpportunityManager to real trading engine"""
    try:
        engine = get_real_trading_engine()
        
        # Import and create OpportunityManager
        from ...opportunity.opportunity_manager import OpportunityManager
        
        # Create OpportunityManager instance
        opportunity_manager = OpportunityManager()
        
        # Connect to real trading engine
        engine.connect_opportunity_manager(opportunity_manager)
        
        logger.info("🔗 OpportunityManager connected to Real Trading Engine")
        
        return {
            "success": True,
            "message": "OpportunityManager connected successfully",
            "info": "Real trading engine will now receive signals from OpportunityManager"
        }
        
    except Exception as e:
        logger.error(f"Error connecting OpportunityManager: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/opportunity-manager/status")
async def get_opportunity_manager_status():
    """Get OpportunityManager connection status"""
    try:
        engine = get_real_trading_engine()
        
        has_opportunity_manager = engine.opportunity_manager is not None
        
        status = {
            "connected": has_opportunity_manager,
            "opportunities_available": 0,
            "last_update": None
        }
        
        if has_opportunity_manager:
            try:
                opportunities = engine.opportunity_manager.get_opportunities() or []
                if isinstance(opportunities, dict):
                    # Count opportunities in dict format
                    total_opps = sum(len(opp_list) for opp_list in opportunities.values())
                    status["opportunities_available"] = total_opps
                elif isinstance(opportunities, list):
                    status["opportunities_available"] = len(opportunities)
                
                # Get last update time if available
                if hasattr(engine.opportunity_manager, 'last_update'):
                    status["last_update"] = engine.opportunity_manager.last_update
                    
            except Exception as e:
                logger.warning(f"Error getting opportunity status: {e}")
        
        return {
            "success": True,
            "data": status
        }
        
    except Exception as e:
        logger.error(f"Error getting OpportunityManager status: {e}")
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
            "active_positions": len(engine.positions),
            "stake_usd": engine.stake_usd,
            "max_positions": engine.max_positions,
            "pure_3_rule_mode": engine.pure_3_rule_mode,
            "primary_target_dollars": engine.primary_target_dollars,
            "absolute_floor_dollars": engine.absolute_floor_dollars,
            "stop_loss_percent": engine.stop_loss_percent * 100,
            "safety_checks_enabled": True,
            "last_reset_date": engine.last_reset_date.isoformat() if engine.last_reset_date else None,
            "signal_sources": list(engine.accept_sources)
        }

        # 🔹 NEW: real account balance pull (Binance Futures/Spot abstraction)
        try:
            # Prefer a cached method if you add one later; for now use the client directly
            bal = await engine.exchange_client.get_account_balance()
            # Try common keys first; fall back to Binance futures fields
            total = float(
                bal.get("total")
                or bal.get("wallet") 
                or bal.get("walletBalance", 0.0)
            )
            available = float(
                bal.get("available")
                or bal.get("free")
                or bal.get("availableBalance", 0.0)
            )
            initial_margin = float(
                bal.get("initial_margin")
                or bal.get("totalInitialMargin", 0.0)
            )
            maint_margin = float(
                bal.get("maintenance_margin")
                or bal.get("totalMaintMargin", 0.0)
            )

            safety_status.update({
                "balance_total_usd": total,
                "available_usd": available,
                "initial_margin_usd": initial_margin,
                "maint_margin_usd": maint_margin,
            })
        except Exception as e:
            # Keep endpoint resilient; just omit balance if the call fails
            logger.warning(f"Could not fetch account balance: {e}")
        
        return {
            "success": True,
            "data": safety_status
        }
        
    except Exception as e:
        logger.error(f"Error getting safety status: {e}")
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
            "active_positions": len(engine.positions),
            "is_running": engine.is_running,
            "completed_trades": len(engine.completed_trades),
            "stake_per_trade": engine.stake_usd,
            "max_positions": engine.max_positions
        }
        
        return {
            "success": True,
            "data": performance
        }
        
    except Exception as e:
        logger.error(f"Error getting real trading performance: {e}")
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
