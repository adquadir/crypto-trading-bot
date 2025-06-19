#!/usr/bin/env python3
"""Simple API server with mode filtering."""

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

# Smart caching for different trading modes
_stable_signals = {}
_swing_signals = {}
_stable_last_scan = 0
_swing_last_scan = 0
_signal_freshness_threshold = 120  # 2 minutes - signals are considered fresh for this long

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
    """Background task to scan opportunities based on current mode."""
    global _scan_in_progress, _trading_mode, _stable_signals, _swing_signals, _stable_last_scan, _swing_last_scan
    
    try:
        print(f"🚀 Background scan started (mode: {_trading_mode})")
        _scan_in_progress = True
        
        if _trading_mode == "swing_trading":
            await opportunity_manager.scan_opportunities_incremental_swing()
            # Cache swing signals separately
            signals = opportunity_manager.get_opportunities()
            _swing_signals = signals.copy() if isinstance(signals, list) else list(signals.values())
            _swing_last_scan = time.time()
            print(f"✅ Swing scan completed - cached {len(_swing_signals)} signals")
        else:
            await opportunity_manager.scan_opportunities_incremental()
            # Cache stable signals separately  
            signals = opportunity_manager.get_opportunities()
            _stable_signals = signals.copy() if isinstance(signals, list) else list(signals.values())
            _stable_last_scan = time.time()
            print(f"✅ Stable scan completed - cached {len(_stable_signals)} signals")
            
        print(f"✅ Background scan completed (mode: {_trading_mode})")
    except Exception as e:
        print(f"❌ Background scan failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        _scan_in_progress = False

def _are_signals_fresh(mode: str) -> bool:
    """Check if cached signals for the given mode are still fresh."""
    current_time = time.time()
    if mode == "swing_trading":
        return (current_time - _swing_last_scan) < _signal_freshness_threshold
    else:
        return (current_time - _stable_last_scan) < _signal_freshness_threshold

def _get_cached_signals(mode: str) -> list:
    """Get cached signals for the given mode."""
    if mode == "swing_trading":
        return _swing_signals.copy() if _swing_signals else []
    else:
        return _stable_signals.copy() if _stable_signals else []

def _should_trigger_scan(mode: str) -> bool:
    """Determine if we should trigger a new scan for the given mode."""
    # Always scan if no signals cached yet
    if mode == "swing_trading" and not _swing_signals:
        return True
    if mode == "stable" and not _stable_signals:
        return True
    
    # Scan if signals are stale
    if not _are_signals_fresh(mode):
        return True
        
    # Don't scan if fresh signals exist
    return False

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
                    print(f"🔄 Starting background scan (mode: {_trading_mode})...")
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
    
    print("✓ All components initialized")

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
    """Get current trading opportunities with smart caching."""
    global _background_scan_task, _last_scan_start, _scan_in_progress, _trading_mode
    
    if not opportunity_manager:
        return {
            "status": "initializing",
            "data": [],
            "message": "Opportunity manager is still initializing"
        }
    
    try:
        current_time = time.time()
        
        # Smart caching: First check if we have fresh cached signals
        if _are_signals_fresh(_trading_mode):
            cached_signals = _get_cached_signals(_trading_mode)
            
            print(f"✅ Returning {len(cached_signals)} fresh cached {_trading_mode} signals")
            
            return {
                "status": "complete",
                "data": cached_signals,
                "message": f"Found {len(cached_signals)} {_trading_mode} signals (cached)",
                "trading_mode": _trading_mode,
                "scan_progress": {
                    "in_progress": False,
                    "opportunities_found": len(cached_signals),
                    "cache_age_seconds": current_time - (_swing_last_scan if _trading_mode == "swing_trading" else _stable_last_scan)
                }
            }
        
        # No fresh cache - check if we should trigger a scan
        should_scan = _should_trigger_scan(_trading_mode)
        
        if should_scan and not _scan_in_progress:
            print(f"🔄 Starting scan (mode: {_trading_mode}) - no fresh cache available...")
            _last_scan_start = current_time
            _scan_in_progress = True
            
            # Start background scan without waiting
            _background_scan_task = asyncio.create_task(_background_scan_opportunities())
        
        # Get any existing opportunities (from live opportunity_manager or cache)
        live_opportunities = opportunity_manager.get_opportunities()
        cached_opportunities = _get_cached_signals(_trading_mode)
        
        # Use live if available, otherwise use cached
        if live_opportunities:
            all_opportunities = live_opportunities
            source = "live"
        else:
            all_opportunities = cached_opportunities
            source = "cached"
        
        # Filter opportunities to only show signals that match the current mode
        filtered_opportunities = []
        for opp in all_opportunities:
            # Determine if this is a swing signal or stable signal based on strategy
            is_swing_signal = (
                opp.get('strategy') in ['swing_trading', 'swing_basic'] or
                opp.get('strategy_type') in ['swing_trading', 'swing_basic'] or
                opp.get('signal_id', '').find('swing') != -1 or
                opp.get('is_stable_signal', True) == False
            )
            
            # Only include signals that match the current mode
            if _trading_mode == "swing_trading" and is_swing_signal:
                # This is a swing signal and we're in swing mode
                opp['trading_mode'] = 'swing_trading'
                opp['signal_source'] = f'{source}_swing_trading_scan'
                filtered_opportunities.append(opp)
            elif _trading_mode == "stable" and not is_swing_signal:
                # This is a stable signal and we're in stable mode
                opp['trading_mode'] = 'stable'
                opp['signal_source'] = f'{source}_stable_scan'
                filtered_opportunities.append(opp)
            # If signal doesn't match current mode, exclude it
        
        all_opportunities = filtered_opportunities
        
        # Determine status based on scan state
        if not _scan_in_progress:
            if len(all_opportunities) > 0:
                status = "complete"
                message = f"Found {len(all_opportunities)} {_trading_mode} signals ({source})"
            else:
                status = "complete"
                message = f"No {_trading_mode} signals found"
        elif len(all_opportunities) == 0:
            status = "scanning"
            message = f"Scanning for {_trading_mode} signals... Please wait"
        else:
            status = "partial"
            message = f"Scan in progress - showing {len(all_opportunities)} {_trading_mode} signals found so far ({source})"
        
        return {
            "status": status,
            "data": all_opportunities,
            "message": message,
            "trading_mode": _trading_mode,
            "scan_progress": {
                "in_progress": _scan_in_progress,
                "opportunities_found": len(all_opportunities)
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
    global _background_scan_task, _last_scan_start, _scan_in_progress, _trading_mode
    
    if not opportunity_manager:
        return {
            "status": "error",
            "message": "Opportunity manager not initialized"
        }
    
    try:
        print(f"🔄 Manual scan triggered (mode: {_trading_mode})...")
        _last_scan_start = time.time()
        _scan_in_progress = True
        
        # Start incremental scan
        _background_scan_task = asyncio.create_task(_background_scan_opportunities())
        
        # Return immediately with current opportunities that match the mode
        all_opportunities = opportunity_manager.get_opportunities()
        opportunities = []
        for opp in all_opportunities:
            # Determine if this is a swing signal or stable signal based on strategy
            is_swing_signal = (
                opp.get('strategy') in ['swing_trading', 'swing_basic'] or
                opp.get('strategy_type') in ['swing_trading', 'swing_basic'] or
                opp.get('signal_id', '').find('swing') != -1 or
                opp.get('is_stable_signal', True) == False
            )
            
            # Only include signals that match the current mode
            if _trading_mode == "swing_trading" and is_swing_signal:
                opp['trading_mode'] = 'swing_trading'
                opp['signal_source'] = 'swing_trading_scan'
                opportunities.append(opp)
            elif _trading_mode == "stable" and not is_swing_signal:
                opp['trading_mode'] = 'stable'
                opp['signal_source'] = 'stable_scan'
                opportunities.append(opp)
        
        return {
            "status": "scanning",
            "message": f"Manual {_trading_mode} scan started - showing {len(opportunities)} current signals",
            "data": opportunities,
            "trading_mode": _trading_mode,
            "scan_progress": {
                "in_progress": _scan_in_progress,
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
    """Set trading mode with smart caching - returns cached signals immediately if fresh."""
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
        current_time = time.time()
        
        print(f"🔄 Trading mode changed from '{old_mode}' to '{mode}'")
        
        # Smart caching: Check if we have fresh signals for this mode
        if _are_signals_fresh(mode):
            cached_signals = _get_cached_signals(mode)
            print(f"✅ Returning {len(cached_signals)} fresh cached {mode} signals (no scan needed)")
            
            return {
                "status": "success",
                "message": f"Trading mode changed to '{mode}' - showing {len(cached_signals)} cached signals",
                "old_mode": old_mode,
                "new_mode": mode,
                "cached_signals": len(cached_signals),
                "scan_needed": False,
                "signals_age_seconds": current_time - (_swing_last_scan if mode == "swing_trading" else _stable_last_scan)
            }
        else:
            # No fresh signals - trigger background scan but return immediately
            print(f"⚠️ No fresh {mode} signals cached - triggering background scan...")
            
            # Don't clear existing opportunities - let the scan populate them
            _last_scan_start = current_time
            _scan_in_progress = True
            
            # Start new scan with new mode
            _background_scan_task = asyncio.create_task(_background_scan_opportunities())
            
            # Return any existing signals while scan runs in background
            existing_signals = _get_cached_signals(mode)
            
            return {
                "status": "success", 
                "message": f"Trading mode changed to '{mode}' - scanning for fresh signals in background",
                "old_mode": old_mode,
                "new_mode": mode,
                "cached_signals": len(existing_signals),
                "scan_needed": True,
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
        
        trade_data = {
            "symbol": trade_request.symbol,
            "signal_type": trade_request.signal_type,
            "entry_price": trade_request.entry_price,
            "stop_loss": trade_request.stop_loss,
            "take_profit": trade_request.take_profit,
            "confidence": trade_request.confidence,
            "strategy": trade_request.strategy,
            "status": "simulated",
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

@app.get("/api/v1/trading/positions")
async def get_positions():
    """Get current trading positions."""
    try:
        # For now, return simulated positions data
        # In a real implementation, this would fetch actual positions from the exchange
        positions = [
            {
                "id": "pos_001",
                "symbol": "BTCUSDT",
                "side": "LONG",
                "size": 0.001,
                "entry_price": 45000.0,
                "current_price": 45500.0,
                "unrealized_pnl": 0.5,
                "unrealized_pnl_percent": 1.11,
                "margin": 45.0,
                "leverage": 1.0,
                "status": "open",
                "created_at": "2025-01-19T18:00:00Z"
            }
        ]
        
        return {
            "status": "success",
            "data": positions,
            "message": f"Retrieved {len(positions)} positions (simulated)",
            "total_positions": len(positions),
            "total_unrealized_pnl": sum(p["unrealized_pnl"] for p in positions)
        }
        
    except Exception as e:
        return {
            "status": "error",
            "data": [],
            "message": f"Error getting positions: {str(e)}"
        }

@app.get("/api/v1/trading/stats")
async def get_trading_stats():
    """Get trading statistics and performance metrics."""
    try:
        # For now, return simulated stats data
        # In a real implementation, this would calculate actual trading statistics
        current_time = time.time()
        
        stats = {
            "account_balance": 10000.0,
            "available_balance": 9500.0,
            "total_unrealized_pnl": 50.0,
            "total_realized_pnl": 150.0,
            "total_trades": 25,
            "winning_trades": 15,
            "losing_trades": 10,
            "win_rate": 60.0,
            "profit_factor": 1.8,
            "max_drawdown": -2.5,
            "current_drawdown": -0.5,
            "daily_pnl": 25.0,
            "weekly_pnl": 125.0,
            "monthly_pnl": 450.0,
            "trading_mode": _trading_mode,
            "active_signals": len(opportunity_manager.get_opportunities()) if opportunity_manager else 0,
            "last_updated": current_time
        }
        
        return {
            "status": "success",
            "data": stats,
            "message": "Trading statistics retrieved successfully (simulated)",
            "timestamp": current_time
        }
        
    except Exception as e:
        return {
            "status": "error",
            "data": {},
            "message": f"Error getting trading stats: {str(e)}"
        }

# Legacy aliases for old incorrect paths (to eliminate 404s from cached frontend)
@app.get("/api/v1/stats")
async def get_stats_legacy():
    """Legacy alias for /api/v1/trading/stats to eliminate 404s."""
    return await get_trading_stats()

@app.get("/api/v1/positions") 
async def get_positions_legacy():
    """Legacy alias for /api/v1/trading/positions to eliminate 404s."""
    return await get_positions()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 