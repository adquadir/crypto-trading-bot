from fastapi import APIRouter, HTTPException
from typing import Dict, List, Any
import logging
from sqlalchemy import func
from datetime import datetime

from src.utils.config import validate_config
from src.database.database import Database
from src.database.models import Trade

# Configure logging
logger = logging.getLogger(__name__)

# Create router without prefix
router = APIRouter()

# Import the components from main (will be set after initialization)
opportunity_manager = None
exchange_client = None
strategy_manager = None
risk_manager = None

def set_components(opp_mgr, exch_client, strat_mgr, risk_mgr):
    """Set the component instances from main."""
    global opportunity_manager, exchange_client, strategy_manager, risk_manager
    opportunity_manager = opp_mgr
    exchange_client = exch_client
    strategy_manager = strat_mgr
    risk_manager = risk_mgr

@router.get("/health")
async def health_check():
    """Check the health of the trading bot."""
    try:
        if exchange_client and hasattr(exchange_client, 'check_connection'):
            is_healthy = await exchange_client.check_connection()
        else:
            is_healthy = False
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
        if not opportunity_manager:
            return {
                "status": "initializing",
                "data": [],
                "message": "Opportunity manager is still initializing"
            }
            
        # get_opportunities() is synchronous, not async
        opportunities = opportunity_manager.get_opportunities()
        return {
            "status": "success",
            "data": opportunities or []
        }
    except Exception as e:
        logger.error(f"Error getting opportunities: {e}")
        return {
            "status": "error", 
            "data": [],
            "message": f"Error fetching opportunities: {str(e)}"
        }

@router.get("/positions")
async def get_positions():
    """Get current trading positions."""
    try:
        if not exchange_client:
            return {
                "status": "initializing",
                "data": [],
                "message": "Exchange client is still initializing"
            }
            
        positions = await exchange_client.get_open_positions()
        return {
            "status": "success",
            "data": positions or []
        }
    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        return {
            "status": "error",
            "data": [],
            "message": "Error fetching positions"
        }

@router.get("/config")
async def get_config():
    """Get current configuration."""
    try:
        # Return basic config info
        return {
            "status": "success",
            "data": {
                "components_ready": {
                    "opportunity_manager": opportunity_manager is not None,
                    "exchange_client": exchange_client is not None,
                    "strategy_manager": strategy_manager is not None,
                    "risk_manager": risk_manager is not None
                }
            }
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
            
        return {
            "status": "success",
            "message": "Configuration update not implemented yet"
        }
    except Exception as e:
        logger.error(f"Error updating config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
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
        
        stats = {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "win_rate": (winning_trades / total_trades * 100) if total_trades > 0 else 0,
            "total_pnl": total_pnl
        }
        
        return {
            "status": "success",
            "data": stats
        }
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

@router.post("/scan")
async def manual_scan():
    """Manually trigger opportunity scanning."""
    try:
        if not opportunity_manager:
            return {
                "status": "error",
                "message": "Opportunity manager not initialized"
            }
            
        # Trigger a manual scan
        await opportunity_manager.scan_opportunities()
        
        # Get the results
        opportunities = opportunity_manager.get_opportunities()
        
        return {
            "status": "success",
            "message": f"Scan completed, found {len(opportunities)} opportunities",
            "data": opportunities
        }
    except Exception as e:
        logger.error(f"Error during manual scan: {e}")
        return {
            "status": "error",
            "message": f"Scan failed: {str(e)}"
        }

@router.get("/api/v1/trading/scalping-signals")
async def get_scalping_signals():
    """Get precision scalping signals targeting 3-10% capital returns."""
    try:
        if not opportunity_manager:
            return {
                "status": "initializing",
                "message": "Opportunity manager is still initializing",
                "data": []
            }
        
        # Check if scalping opportunities exist
        if hasattr(opportunity_manager, 'scalping_opportunities'):
            scalping_signals = list(opportunity_manager.scalping_opportunities.values())
        else:
            # If no scalping opportunities cached, run a quick scan
            await opportunity_manager.scan_scalping_opportunities()
            scalping_signals = opportunity_manager.get_scalping_opportunities()
        
        if not scalping_signals:
            return {
                "status": "no_signals",
                "message": "No scalping opportunities found",
                "data": [],
                "scan_info": {
                    "strategy_type": "precision_scalping",
                    "target_returns": "3-10% capital",
                    "timeframe": "15m",
                    "last_scan": datetime.now().isoformat()
                }
            }
        
        # Sort by expected capital return (highest first)
        scalping_signals.sort(key=lambda x: x.get('expected_capital_return_pct', 0), reverse=True)
        
        # Calculate summary statistics
        total_signals = len(scalping_signals)
        avg_capital_return = sum(s.get('expected_capital_return_pct', 0) for s in scalping_signals) / total_signals if total_signals > 0 else 0
        avg_leverage = sum(s.get('optimal_leverage', 0) for s in scalping_signals) / total_signals if total_signals > 0 else 0
        
        # Count by scalping type
        scalping_types = {}
        for signal in scalping_signals:
            scalp_type = signal.get('scalping_type', 'unknown')
            scalping_types[scalp_type] = scalping_types.get(scalp_type, 0) + 1
        
        # Enhanced response with scalping-specific metadata
        return {
            "status": "success",
            "message": f"Found {total_signals} precision scalping opportunities",
            "data": scalping_signals,
            "scalping_summary": {
                "total_signals": total_signals,
                "avg_capital_return_pct": round(avg_capital_return, 2),
                "avg_optimal_leverage": round(avg_leverage, 1),
                "scalping_types": scalping_types,
                "strategy_focus": "Capital returns via precise leverage",
                "timeframe": "15m/1h",
                "target_range": "3-10% capital returns"
            },
            "scan_info": {
                "strategy_type": "precision_scalping",
                "last_scan": datetime.now().isoformat(),
                "data_freshness": "real_time"
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting scalping signals: {e}")
        return {
            "status": "error",
            "message": f"Failed to get scalping signals: {str(e)}",
            "data": [],
            "error_details": {
                "error_type": "scalping_fetch_error",
                "timestamp": datetime.now().isoformat()
            }
        }

@router.post("/api/v1/trading/refresh-scalping")
async def refresh_scalping_signals():
    """Manually refresh scalping signals scan."""
    try:
        if not opportunity_manager:
            return {
                "status": "error",
                "message": "Opportunity manager not initialized"
            }
        
        logger.info("Manual scalping refresh requested")
        await opportunity_manager.scan_scalping_opportunities()
        
        scalping_signals = opportunity_manager.get_scalping_opportunities()
        
        return {
            "status": "success",
            "message": f"Scalping scan completed - found {len(scalping_signals)} opportunities",
            "signals_found": len(scalping_signals),
            "refresh_timestamp": datetime.now().isoformat(),
            "next_auto_scan": "60 seconds"
        }
        
    except Exception as e:
        logger.error(f"Error refreshing scalping signals: {e}")
        return {
            "status": "error", 
            "message": f"Failed to refresh scalping signals: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }
