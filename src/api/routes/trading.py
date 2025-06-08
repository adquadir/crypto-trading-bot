from typing import List, Dict, Any
from fastapi import HTTPException
from src.api.routes import router
from src.bot.trading_bot import trading_bot
from src.utils.logger import logger

@router.get("/opportunities", response_model=List[Dict[str, Any]])
async def get_opportunities():
    """Get current trading opportunities.
    
    Returns:
        List[Dict[str, Any]]: List of trading opportunities
    """
    try:
        opportunities = []
        for symbol, opp in trading_bot.opportunities.items():
            opp_dict = opp.to_dict()
            
            # Add data freshness information
            if opp.data_freshness:
                opp_dict['data_freshness'] = {
                    'ohlcv': opp.data_freshness.get('ohlcv', 0),
                    'orderbook': opp.data_freshness.get('orderbook', 0),
                    'ticker': opp.data_freshness.get('ticker', 0),
                    'trades': opp.data_freshness.get('trades', 0),
                    'open_interest': opp.data_freshness.get('open_interest', 0),
                    'funding_rate': opp.data_freshness.get('funding_rate', 0),
                    'volatility': opp.data_freshness.get('volatility', 0)
                }
            
            opportunities.append(opp_dict)
        
        return opportunities
        
    except Exception as e:
        logger.error(f"Error getting opportunities: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Error getting trading opportunities"
        ) 