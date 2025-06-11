from fastapi import APIRouter, HTTPException
from typing import Dict, List, Any
import logging
from sqlalchemy import func

from trading_bot import trading_bot
from utils.config import validate_config
from database.database import Database
from database.models import Trade

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

@router.get("/health")
async def health_check():
    """Check the health of the trading bot."""
    try:
        is_healthy = await trading_bot._health_check()
        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "message": "Trading bot is running" if is_healthy else "Trading bot is not healthy"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/opportunities")
async def get_opportunities():
    """Get current trading opportunities."""
    try:
        # Get opportunities from the opportunity manager
        opportunities = trading_bot.opportunity_manager.get_opportunities()
        return {
            "status": "success",
            "data": opportunities
        }
    except Exception as e:
        logger.error(f"Error getting opportunities: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/positions")
async def get_positions():
    """Get current trading positions."""
    try:
        positions = trading_bot.position_levels
        return {
            "status": "success",
            "data": positions
        }
    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/config")
async def get_config():
    """Get current configuration."""
    try:
        return {
            "status": "success",
            "data": trading_bot.config
        }
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/config")
async def update_config(config: Dict[str, Any]):
    """Update configuration."""
    try:
        if not validate_config(config):
            raise HTTPException(status_code=400, detail="Invalid configuration")
            
        trading_bot.config = config
        return {
            "status": "success",
            "message": "Configuration updated successfully"
        }
    except Exception as e:
        logger.error(f"Error updating config: {e}")
        raise HTTPException(status_code=500, detail=str(e)) 

@router.get("/trading/stats")
async def get_stats():
    """Get trading statistics."""
    try:
        db = Database()
        session = db.SessionLocal()
        
        # Get total trades
        total_trades = session.query(Trade).count()
        
        # Get winning trades
        winning_trades = session.query(Trade).filter(Trade.pnl > 0).count()
        
        # Get total PnL
        total_pnl = session.query(func.sum(Trade.pnl)).scalar() or 0
        
        # Get average trade duration
        avg_duration = session.query(func.avg(Trade.duration)).scalar() or 0
        
        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "win_rate": (winning_trades / total_trades * 100) if total_trades > 0 else 0,
            "total_pnl": total_pnl,
            "avg_duration": avg_duration
        }
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close() 