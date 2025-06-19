#!/usr/bin/env python3
"""Simple API server with dynamic opportunity manager."""

import asyncio
import sys
import os
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from dotenv import load_dotenv

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
    global _scan_in_progress
    
    try:
        print("🚀 Background incremental scan started")
        _scan_in_progress = True
        await opportunity_manager.scan_opportunities_incremental()
        print("✅ Background incremental scan completed")
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
    global _background_scan_task, _last_scan_start, _scan_in_progress
    
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
            print("🔄 Starting background opportunity scan...")
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
        return {
            "status": "error",
            "data": [],
            "message": f"Error getting opportunities: {str(e)}"
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

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 