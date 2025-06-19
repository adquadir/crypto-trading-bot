from fastapi import APIRouter, HTTPException
from typing import Dict, List, Any, Optional
import logging
from pydantic import BaseModel
from sqlalchemy import func

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

# Trading mode state
current_trading_mode = "stable"  # Default mode

def set_trading_components(opp_mgr, exch_client, strat_mgr, risk_mgr):
    """Set the component instances from main."""
    global opportunity_manager, exchange_client, strategy_manager, risk_manager
    opportunity_manager = opp_mgr
    exchange_client = exch_client
    strategy_manager = strat_mgr
    risk_manager = risk_mgr

class TradeRequest(BaseModel):
    symbol: str
    side: str  # 'buy' or 'sell'
    amount: float
    price: Optional[float] = None  # Market order if None

class ManualTradeRequest(BaseModel):
    symbol: str
    signal_type: str  # 'LONG' or 'SHORT'
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float
    strategy: str = "manual"

@router.get("/opportunities")
async def get_trading_opportunities():
    """Get current trading opportunities (main trading endpoint)."""
    try:
        if not opportunity_manager:
            return {
                "status": "initializing",
                "message": "Opportunity manager is still initializing",
                "trading_mode": current_trading_mode,
                "data": [],
                "scan_progress": {
                    "in_progress": False,
                    "opportunities_found": 0
                }
            }
            
        # get_opportunities() is synchronous, not async
        opportunities = opportunity_manager.get_opportunities()
        
        return {
            "status": "complete" if opportunities else "scanning",
            "message": f"Found {len(opportunities)} opportunities in {current_trading_mode} mode",
            "trading_mode": current_trading_mode,
            "data": opportunities or [],
            "scan_progress": {
                "in_progress": False,
                "opportunities_found": len(opportunities) if opportunities else 0
            }
        }
    except Exception as e:
        logger.error(f"Error getting trading opportunities: {e}")
        return {
            "status": "error", 
            "message": f"Error fetching opportunities: {str(e)}",
            "trading_mode": current_trading_mode,
            "data": [],
            "scan_progress": {
                "in_progress": False,
                "opportunities_found": 0
            }
        }

@router.get("/mode")
async def get_trading_mode():
    """Get current trading mode."""
    return {
        "status": "success",
        "data": {
            "current_mode": current_trading_mode,
            "available_modes": ["stable", "swing_trading"]
        }
    }

@router.post("/mode/{mode}")
async def set_trading_mode(mode: str):
    """Set trading mode (stable or swing_trading)."""
    global current_trading_mode
    
    if mode not in ["stable", "swing_trading"]:
        raise HTTPException(status_code=400, detail="Invalid mode. Use 'stable' or 'swing_trading'")
    
    current_trading_mode = mode
    
    return {
        "status": "success",
        "message": f"Trading mode set to {mode}",
        "data": {
            "current_mode": current_trading_mode
        }
    }

@router.get("/stats")
async def get_trading_stats():
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
            "total_pnl": total_pnl,
            "trading_mode": current_trading_mode
        }
        
        return {
            "status": "success",
            "data": stats
        }
    except Exception as e:
        logger.error(f"Error getting trading stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

@router.get("/positions")
async def get_trading_positions():
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
        logger.error(f"Error getting trading positions: {e}")
        return {
            "status": "error",
            "data": [],
            "message": "Error fetching positions"
        }

@router.post("/execute_manual_trade")
async def execute_manual_trade(trade_request: ManualTradeRequest):
    """Execute a manual trade."""
    try:
        if not exchange_client:
            raise HTTPException(status_code=503, detail="Exchange client not available")
        
        if not risk_manager:
            raise HTTPException(status_code=503, detail="Risk manager not available")
        
        # Convert signal_type to side
        side = "buy" if trade_request.signal_type.upper() == "LONG" else "sell"
        
        # Calculate position size based on entry price
        # This is a simplified calculation - adjust based on your risk management rules
        position_size = 100.0 / trade_request.entry_price  # $100 position
        
        # Validate trade request with risk manager
        if hasattr(risk_manager, 'validate_trade') and not risk_manager.validate_trade(
            trade_request.symbol, 
            side, 
            position_size
        ):
            raise HTTPException(status_code=400, detail="Trade rejected by risk manager")
        
        # Execute the trade as a limit order
        result = await exchange_client.place_limit_order(
            trade_request.symbol,
            side,
            position_size,
            trade_request.entry_price
        )
        
        return {
            "status": "success",
            "data": result,
            "message": "Manual trade executed successfully"
        }
    except Exception as e:
        logger.error(f"Error executing manual trade: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/execute")
async def execute_trade(trade_request: TradeRequest):
    """Execute a trade."""
    try:
        if not exchange_client:
            raise HTTPException(status_code=503, detail="Exchange client not available")
        
        if not risk_manager:
            raise HTTPException(status_code=503, detail="Risk manager not available")
        
        # Validate trade request with risk manager
        if hasattr(risk_manager, 'validate_trade') and not risk_manager.validate_trade(
            trade_request.symbol, 
            trade_request.side, 
            trade_request.amount
        ):
            raise HTTPException(status_code=400, detail="Trade rejected by risk manager")
        
        # Execute the trade
        if trade_request.price:
            # Limit order
            result = await exchange_client.place_limit_order(
                trade_request.symbol,
                trade_request.side,
                trade_request.amount,
                trade_request.price
            )
        else:
            # Market order
            result = await exchange_client.place_market_order(
                trade_request.symbol,
                trade_request.side,
                trade_request.amount
            )
        
        return {
            "status": "success",
            "data": result,
            "message": "Trade executed successfully"
        }
    except Exception as e:
        logger.error(f"Error executing trade: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/signals")
async def get_trading_signals():
    """Get current trading signals."""
    try:
        if not strategy_manager:
            return {
                "status": "initializing",
                "data": [],
                "message": "Strategy manager is still initializing"
            }
        
        # Get signals from strategy manager
        if hasattr(strategy_manager, 'get_current_signals'):
        signals = await strategy_manager.get_current_signals()
        else:
            # Fallback to opportunities if get_current_signals doesn't exist
            signals = opportunity_manager.get_opportunities() if opportunity_manager else []
        
        return {
            "status": "success",
            "data": signals or []
        }
    except Exception as e:
        logger.error(f"Error getting trading signals: {e}")
        return {
            "status": "error",
            "data": [],
            "message": f"Error fetching signals: {str(e)}"
        }

@router.get("/balance")
async def get_account_balance():
    """Get account balance."""
    try:
        if not exchange_client:
            raise HTTPException(status_code=503, detail="Exchange client not available")
        
        balance = await exchange_client.get_account_balance()
        
        return {
            "status": "success",
            "data": balance
        }
    except Exception as e:
        logger.error(f"Error getting balance: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/orders")
async def get_open_orders():
    """Get open orders."""
    try:
        if not exchange_client:
            raise HTTPException(status_code=503, detail="Exchange client not available")
        
        orders = await exchange_client.get_open_orders()
        
        return {
            "status": "success",
            "data": orders or []
        }
    except Exception as e:
        logger.error(f"Error getting orders: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/orders/{order_id}")
async def cancel_order(order_id: str):
    """Cancel an order."""
    try:
        if not exchange_client:
            raise HTTPException(status_code=503, detail="Exchange client not available")
        
        result = await exchange_client.cancel_order(order_id)
        
        return {
            "status": "success",
            "data": result,
            "message": "Order cancelled successfully"
        }
    except Exception as e:
        logger.error(f"Error cancelling order: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/strategy/start")
async def start_strategy():
    """Start trading strategy."""
    try:
        if not strategy_manager:
            raise HTTPException(status_code=503, detail="Strategy manager not available")
        
        if hasattr(strategy_manager, 'start'):
        await strategy_manager.start()
        
        return {
            "status": "success",
            "message": "Strategy started successfully"
        }
    except Exception as e:
        logger.error(f"Error starting strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/strategy/stop")
async def stop_strategy():
    """Stop trading strategy."""
    try:
        if not strategy_manager:
            raise HTTPException(status_code=503, detail="Strategy manager not available")
        
        if hasattr(strategy_manager, 'stop'):
        await strategy_manager.stop()
        
        return {
            "status": "success",
            "message": "Strategy stopped successfully"
        }
    except Exception as e:
        logger.error(f"Error stopping strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e)) 