from typing import List, Dict, Any
from fastapi import HTTPException
from pydantic import BaseModel
from src.api.routes import router
from src.utils.logger import logger
import asyncio
import time

# Import the global components
opportunity_manager = None
exchange_client = None
strategy_manager = None
risk_manager = None

def set_trading_components(opp_mgr, exch_client, strat_mgr, risk_mgr):
    """Set the component instances for trading routes."""
    global opportunity_manager, exchange_client, strategy_manager, risk_manager
    opportunity_manager = opp_mgr
    exchange_client = exch_client
    strategy_manager = strat_mgr
    risk_manager = risk_mgr

class ManualTradeRequest(BaseModel):
    symbol: str
    signal_type: str  # 'LONG' or 'SHORT'
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float
    strategy: str = "manual"

# Global variables for background processing
_background_scan_task = None
_last_scan_start = 0
_scan_in_progress = False

@router.get("/opportunities")
async def get_opportunities():
    """Get current trading opportunities with incremental results."""
    global _background_scan_task, _last_scan_start, _scan_in_progress
    
    try:
        if not opportunity_manager:
            return {
                "status": "initializing",
                "data": [],
                "message": "Opportunity manager is still initializing"
            }
        
        current_time = time.time()
        
        # Check if we need to start a new scan (every 30 seconds or if no scan running)
        should_start_new_scan = (
            not _scan_in_progress or 
            (current_time - _last_scan_start) > 30 or
            (_background_scan_task and _background_scan_task.done())
        )
        
        if should_start_new_scan:
            logger.info("🔄 Starting background opportunity scan...")
            _last_scan_start = current_time
            _scan_in_progress = True
            
            # Start background scan without waiting
            _background_scan_task = asyncio.create_task(_background_scan_opportunities())
        
        # Always return current opportunities (even if empty or partial)
        opportunities = opportunity_manager.get_opportunities()
        
        # Determine status based on scan state
        if not _scan_in_progress:
            status = "complete"
            message = f"Found {len(opportunities)} opportunities"
        elif len(opportunities) == 0:
            status = "scanning"
            message = "Scanning for opportunities... Please wait"
        else:
            status = "partial"
            message = f"Scan in progress - showing {len(opportunities)} opportunities found so far"
        
        return {
            "status": status,
            "data": opportunities,
            "message": message,
            "scan_progress": {
                "in_progress": _scan_in_progress,
                "last_scan_start": _last_scan_start,
                "opportunities_found": len(opportunities)
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting opportunities: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Error getting trading opportunities"
        )

async def _background_scan_opportunities():
    """Background task to scan opportunities incrementally."""
    global _scan_in_progress
    
    try:
        logger.info("🚀 Background scan started")
        await opportunity_manager.scan_opportunities_incremental()
        logger.info("✅ Background scan completed")
    except Exception as e:
        logger.error(f"❌ Background scan failed: {e}")
    finally:
        _scan_in_progress = False

@router.post("/execute_manual_trade")
async def execute_manual_trade(trade_request: ManualTradeRequest):
    """Execute a manual trade based on signal data."""
    try:
        logger.info(f"Manual trade request received: {trade_request.dict()}")
        
        # For now, just log the trade request since actual trading is disabled
        # In the future, this would interface with the trading engine
        
        trade_data = {
            "symbol": trade_request.symbol,
            "signal_type": trade_request.signal_type,
            "entry_price": trade_request.entry_price,
            "stop_loss": trade_request.stop_loss,
            "take_profit": trade_request.take_profit,
            "confidence": trade_request.confidence,
            "strategy": trade_request.strategy,
            "status": "simulated",  # For now, all trades are simulated
            "timestamp": "2024-01-01T00:00:00Z"
        }
        
        logger.info(f"Manual trade simulated: {trade_data}")
        
        return {
            "status": "success",
            "message": f"Manual trade for {trade_request.symbol} has been simulated (actual trading disabled)",
            "trade": trade_data
        }
        
    except Exception as e:
        logger.error(f"Error executing manual trade: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error executing manual trade: {str(e)}"
        ) 