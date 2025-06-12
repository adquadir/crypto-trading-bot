from typing import List, Dict, Any
from fastapi import HTTPException
from src.api.routes import router
from src.trading_bot import trading_bot
from src.utils.logger import logger

@router.get("/opportunities")
async def get_opportunities():
    """Get current trading opportunities."""
    try:
        # Get opportunities directly from symbol discovery
        opportunities = await trading_bot.symbol_discovery.scan_opportunities()
        return {
            "status": "success",
            "data": [opp.to_dict() for opp in opportunities]
        }
    except Exception as e:
        logger.error(f"Error getting opportunities: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Error getting trading opportunities"
        ) 