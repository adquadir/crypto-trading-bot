from typing import List, Dict, Any
from fastapi import HTTPException
from pydantic import BaseModel
from src.api.routes import router
from src.utils.logger import logger

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

@router.get("/opportunities")
async def get_opportunities():
    """Get current trading opportunities."""
    try:
        # Get opportunities from the opportunity manager which has our dynamic signal generation
        if opportunity_manager:
            # Scan for new opportunities using our enhanced system
            await opportunity_manager.scan_opportunities()
            opportunities = opportunity_manager.get_opportunities()
            return {
                "status": "success",
                "data": opportunities
            }
        else:
            return {
                "status": "initializing",
                "data": [],
                "message": "Opportunity manager is still initializing"
            }
    except Exception as e:
        logger.error(f"Error getting opportunities: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Error getting trading opportunities"
        )

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