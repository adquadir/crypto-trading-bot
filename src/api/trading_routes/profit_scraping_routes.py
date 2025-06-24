"""
Profit Scraping API Routes
RESTful endpoints for managing the dynamic profit scraping system
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
import logging
from datetime import datetime
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profit-scraping", tags=["profit-scraping"])

# Global profit scraper instance
profit_scraper = None

class StartScrapingRequest(BaseModel):
    symbols: List[str]
    max_symbols: int = 10

def set_profit_scraper(scraper):
    """Set profit scraper instance"""
    global profit_scraper
    profit_scraper = scraper

@router.post("/start")
async def start_profit_scraping(request: StartScrapingRequest):
    """Start dynamic profit scraping"""
    try:
        global profit_scraper
        if not profit_scraper:
            raise HTTPException(status_code=503, detail="Profit scraper not initialized")
        
        symbols = request.symbols[:request.max_symbols]
        await profit_scraper.start(symbols)
        
        return {
            "message": f"Started profit scraping on {len(symbols)} symbols",
            "symbols": symbols,
            "status": profit_scraper.get_status()
        }
        
    except Exception as e:
        logger.error(f"Error starting profit scraping: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stop")
async def stop_profit_scraping():
    """Stop profit scraping"""
    try:
        global profit_scraper
        if not profit_scraper:
            raise HTTPException(status_code=503, detail="Profit scraper not initialized")
        
        profit_scraper.stop()
        return {"message": "Profit scraping stopped"}
        
    except Exception as e:
        logger.error(f"Error stopping profit scraping: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_scraping_status():
    """Get current profit scraping status"""
    try:
        global profit_scraper
        if not profit_scraper:
            return {"running": False, "message": "Not initialized"}
        
        return profit_scraper.get_status()
        
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/trades/recent")
async def get_recent_trades(limit: int = 20):
    """Get recent trades"""
    try:
        global profit_scraper
        if not profit_scraper:
            return {"trades": [], "message": "Not initialized"}
        
        trades = profit_scraper.get_recent_trades(limit)
        return {"trades": trades, "count": len(trades)}
        
    except Exception as e:
        logger.error(f"Error getting trades: {e}")
        raise HTTPException(status_code=500, detail=str(e))
