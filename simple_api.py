#!/usr/bin/env python3
"""Simple API server with dynamic opportunity manager."""

import asyncio
import sys
import os
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

app = FastAPI(title="Crypto Trading Bot API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def background_refresh():
    """Background task to refresh opportunities periodically."""
    while True:
        try:
            if opportunity_manager:
                print("Background: Refreshing opportunities...")
                await opportunity_manager.scan_opportunities()
                print("Background: Refresh complete")
        except Exception as e:
            print(f"Background refresh error: {e}")
        
        # Wait 60 seconds before next refresh
        await asyncio.sleep(60)

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
    
    # Do initial scan
    print("Doing initial opportunity scan...")
    await opportunity_manager.scan_opportunities()
    
    # Start background refresh task
    asyncio.create_task(background_refresh())
    
    print("✓ All components initialized with background refresh")

@app.get("/")
async def root():
    return {"message": "Crypto Trading Bot API is running", "status": "dynamic"}

@app.get("/api/v1/trading/opportunities")
async def get_opportunities():
    """Get current trading opportunities."""
    if not opportunity_manager:
        return {
            "status": "initializing",
            "data": [],
            "message": "Opportunity manager is still initializing"
        }
    
    try:
        # Get cached opportunities (fast)
        opportunities = opportunity_manager.get_opportunities()
        
        # If no opportunities, do a quick scan
        if not opportunities:
            await opportunity_manager.scan_opportunities()
            opportunities = opportunity_manager.get_opportunities()
        
        return {
            "status": "success",
            "data": opportunities
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
    if not opportunity_manager:
        return {
            "status": "error",
            "message": "Opportunity manager not initialized"
        }
    
    try:
        await opportunity_manager.scan_opportunities()
        opportunities = opportunity_manager.get_opportunities()
        
        return {
            "status": "success",
            "message": f"Scan completed, found {len(opportunities)} opportunities",
            "data": opportunities
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Scan failed: {str(e)}"
        }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 