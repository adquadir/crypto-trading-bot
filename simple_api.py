#!/usr/bin/env python3
"""Simple API server with dynamic opportunity manager."""

import asyncio
import sys
import os
import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from dotenv import load_dotenv
from pydantic import BaseModel

# Add src to path
sys.path.append('src')

from market_data.exchange_client import ExchangeClient
from strategy.strategy_manager import StrategyManager
from risk.risk_manager import RiskManager
from opportunity.opportunity_manager import OpportunityManager
from utils.config import load_config

# Load environment
load_dotenv()

# Global components
opportunity_manager = None

# Global variables for background processing
_background_scan_task = None
_last_scan_start = 0
_scan_in_progress = False
_trading_mode = "stable"  # Default mode: "stable", "swing_trading"

class ManualTradeRequest(BaseModel):
    symbol: str
    signal_type: str  # 'LONG' or 'SHORT'
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float
    strategy: str = "manual"

app = FastAPI(title="Crypto Trading Bot API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def _background_scan_opportunities():
    """Background task to scan opportunities incrementally."""
    global _scan_in_progress, _trading_mode
    
    try:
        print(f"🚀 Background incremental scan started (mode: {_trading_mode})")
        _scan_in_progress = True
        
        if _trading_mode == "swing_trading":
            await opportunity_manager.scan_opportunities_incremental_swing()
        else:
            await opportunity_manager.scan_opportunities_incremental()
            
        print(f"✅ Background incremental scan completed (mode: {_trading_mode})")
    except Exception as e:
        print(f"❌ Background scan failed: {e}")
    finally:
        _scan_in_progress = False

async def background_refresh():
    """Background task to refresh opportunities periodically."""
    global _background_scan_task, _last_scan_start, _scan_in_progress
    
    while True:
        try:
            if opportunity_manager:
                current_time = time.time()
                
                # Check if we need to start a new scan (every 5 minutes or if no scan running)
                should_start_new_scan = (
                    not _scan_in_progress or 
                    (current_time - _last_scan_start) > 300 or  # 5 minutes
                    (_background_scan_task and _background_scan_task.done())
                )
                
                if should_start_new_scan:
                    print("🔄 Starting background incremental scan...")
                    _last_scan_start = current_time
                    
                    # Start background scan without waiting
                    _background_scan_task = asyncio.create_task(_background_scan_opportunities())
                    
        except Exception as e:
            print(f"Background refresh error: {e}")
        
        # Wait 30 seconds before checking again
        await asyncio.sleep(30)

@app.on_event("startup")
async def startup_event():
    """Initialize components on startup."""
    global opportunity_manager
    
    print("Initializing components...")
    
    # Load configuration
    config = load_config()
    
    # Initialize components
    exchange_client = ExchangeClient()
    await exchange_client.initialize()
    
    try:
        risk_manager = RiskManager(config)
    except Exception as e:
        print(f"Risk manager failed: {e}")
        risk_manager = None
    
    try:
        strategy_manager = StrategyManager(exchange_client)
        await strategy_manager.initialize()
    except Exception as e:
        print(f"Strategy manager failed: {e}")
        strategy_manager = None
    
    # Initialize opportunity manager
    opportunity_manager = OpportunityManager(exchange_client, strategy_manager, risk_manager)
    await opportunity_manager.initialize()
    
    # Start background refresh task
    asyncio.create_task(background_refresh())
    
    print("✓ All components initialized with incremental background refresh")

@app.get("/")
async def root():
    return {"message": "Crypto Trading Bot API is running", "status": "incremental"}

@app.get("/api/v1/test")
async def test_connection():
    """Simple test endpoint to verify API connectivity."""
    return {
        "status": "success",
        "message": "API connection is working",
        "timestamp": time.time()
    }

@app.get("/api/v1/trading/opportunities")
async def get_opportunities():
    """Get current trading opportunities with incremental results."""
    global _background_scan_task, _last_scan_start, _scan_in_progress, _trading_mode
    
    if not opportunity_manager:
        return {
            "status": "initializing",
            "data": [],
            "message": "Opportunity manager is still initializing"
        }
    
    try:
        current_time = time.time()
        
        # Check if we need to start a new scan (every 30 seconds or if no scan running)
        should_start_new_scan = (
            not _scan_in_progress or 
            (current_time - _last_scan_start) > 30 or
            (_background_scan_task and _background_scan_task.done())
        )
        
        if should_start_new_scan:
            print(f"🔄 Starting background opportunity scan (mode: {_trading_mode})...")
            _last_scan_start = current_time
            _scan_in_progress = True
            
            # Start background scan without waiting
            _background_scan_task = asyncio.create_task(_background_scan_opportunities())
        
        # Always return current opportunities (even if empty or partial)
        opportunities = opportunity_manager.get_opportunities()
        
        # Determine status based on scan state
        if not _scan_in_progress:
            status = "complete"
            message = f"Found {len(opportunities)} opportunities using {_trading_mode} mode"
        elif len(opportunities) == 0:
            status = "scanning"
            message = f"Scanning for opportunities using {_trading_mode} mode... Please wait"
        else:
            status = "partial"
            message = f"Scan in progress ({_trading_mode} mode) - showing {len(opportunities)} opportunities found so far"
        
        return {
            "status": status,
            "data": opportunities,
            "message": message,
            "trading_mode": _trading_mode,
            "scan_progress": {
                "in_progress": _scan_in_progress,
                "last_scan_start": _last_scan_start,
                "opportunities_found": len(opportunities)
            }
        }
        
    except Exception as e:
        return {
            "status": "error",
            "data": [],
            "message": f"Error getting opportunities: {str(e)}",
            "trading_mode": _trading_mode
        }

@app.post("/api/v1/trading/scan")
async def manual_scan():
    """Manually trigger opportunity scanning."""
    global _background_scan_task, _last_scan_start, _scan_in_progress
    
    if not opportunity_manager:
        return {
            "status": "error",
            "message": "Opportunity manager not initialized"
        }
    
    try:
        print("🔄 Manual scan triggered...")
        _last_scan_start = time.time()
        _scan_in_progress = True
        
        # Start incremental scan
        _background_scan_task = asyncio.create_task(_background_scan_opportunities())
        
        # Return immediately with current opportunities
        opportunities = opportunity_manager.get_opportunities()
        
        return {
            "status": "scanning",
            "message": f"Incremental scan started - showing {len(opportunities)} current opportunities",
            "data": opportunities,
            "scan_progress": {
                "in_progress": _scan_in_progress,
                "last_scan_start": _last_scan_start,
                "opportunities_found": len(opportunities)
            }
        }
    except Exception as e:
        _scan_in_progress = False
        return {
            "status": "error",
            "message": f"Scan failed: {str(e)}"
        }

@app.get("/api/v1/trading/mode")
async def get_trading_mode():
    """Get current trading mode."""
    global _trading_mode
    return {
        "status": "success",
        "trading_mode": _trading_mode,
        "available_modes": ["stable", "swing_trading"],
        "mode_descriptions": {
            "stable": "Conservative signals with ATR-based TP/SL and signal persistence",
            "swing_trading": "Advanced multi-strategy voting with structure-based TP/SL for 5-10% moves"
        }
    }

@app.post("/api/v1/trading/mode/{mode}")
async def set_trading_mode(mode: str):
    """Set trading mode and trigger new scan."""
    global _trading_mode, _background_scan_task, _last_scan_start, _scan_in_progress
    
    if mode not in ["stable", "swing_trading"]:
        return {
            "status": "error",
            "message": f"Invalid mode '{mode}'. Available modes: stable, swing_trading"
        }
    
    if not opportunity_manager:
        return {
            "status": "error",
            "message": "Opportunity manager not initialized"
        }
    
    try:
        old_mode = _trading_mode
        _trading_mode = mode
        
        # Clear existing opportunities when switching modes
        opportunity_manager.opportunities.clear()
        
        print(f"🔄 Trading mode changed from '{old_mode}' to '{mode}' - starting new scan...")
        _last_scan_start = time.time()
        _scan_in_progress = True
        
        # Start new scan with new mode
        _background_scan_task = asyncio.create_task(_background_scan_opportunities())
        
        return {
            "status": "success",
            "message": f"Trading mode changed to '{mode}' and new scan started",
            "old_mode": old_mode,
            "new_mode": mode,
            "scan_progress": {
                "in_progress": _scan_in_progress,
                "last_scan_start": _last_scan_start
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to change trading mode: {str(e)}"
        }

@app.post("/api/v1/trading/execute_manual_trade")
async def execute_manual_trade(trade_request: ManualTradeRequest):
    """Execute a manual trade based on signal data."""
    try:
        print(f"Manual trade request received: {trade_request.dict()}")
        
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
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        
        print(f"Manual trade simulated: {trade_data}")
        
        return {
            "status": "success",
            "message": f"Manual trade for {trade_request.symbol} has been simulated (actual trading disabled)",
            "trade": trade_data
        }
        
    except Exception as e:
        print(f"Error executing manual trade: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error executing manual trade: {str(e)}"
        )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 