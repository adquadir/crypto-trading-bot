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
from typing import Optional

# Add src to path
sys.path.append('src')

from market_data.exchange_client import ExchangeClient
from strategy.strategy_manager import StrategyManager
from risk.risk_manager import RiskManager
from opportunity.opportunity_manager import OpportunityManager
from utils.config import load_config
from src.signals.enhanced_signal_tracker import enhanced_signal_tracker

# Import backtesting routes
try:
    from src.api.backtesting_routes import router as backtesting_router
    BACKTESTING_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Backtesting routes not available: {e}")
    backtesting_router = None
    BACKTESTING_AVAILABLE = False

# Import signal tracking routes
try:
    from src.api.trading_routes.signal_tracking_routes import router as signal_tracking_router
    SIGNAL_TRACKING_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Signal tracking routes not available: {e}")
    signal_tracking_router = None
    SIGNAL_TRACKING_AVAILABLE = False

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
_stable_signals = []
_swing_signals = []
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

class SignalPerformanceRequest(BaseModel):
    days_back: int = 7
    strategy: Optional[str] = None
    symbol: Optional[str] = None

class CriteriaAdjustmentRequest(BaseModel):
    strategy: str
    min_confidence: Optional[float] = None
    min_risk_reward: Optional[float] = None
    max_volatility: Optional[float] = None
    min_volume_ratio: Optional[float] = None

app = FastAPI(title="Crypto Trading Bot API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include backtesting routes if available
if BACKTESTING_AVAILABLE and backtesting_router:
    app.include_router(backtesting_router)
    print("✅ Backtesting routes enabled")
else:
    print("⚠️ Backtesting routes disabled")

# Include signal tracking routes if available
if SIGNAL_TRACKING_AVAILABLE and signal_tracking_router:
    app.include_router(signal_tracking_router)
    print("✅ Signal tracking routes enabled")
else:
    print("⚠️ Signal tracking routes disabled")

async def _background_scan_opportunities():
    """Background task to scan opportunities based on current mode."""
    global _scan_in_progress, _trading_mode, _stable_signals, _swing_signals, _stable_last_scan, _swing_last_scan
    
    try:
        print(f"🚀 Background scan started (mode: {_trading_mode})")
        _scan_in_progress = True
        
        if _trading_mode == "swing_trading":
            await opportunity_manager.scan_opportunities_incremental_swing()
            # Cache swing signals separately - get ALL opportunities and filter for swing
            all_signals = opportunity_manager.get_opportunities()
            swing_only = []
            for signal in all_signals:
                is_swing_signal = (
                    signal.get('strategy') in ['swing_trading', 'swing_basic'] or
                    signal.get('strategy_type') in ['swing_trading', 'swing_basic'] or
                    signal.get('signal_id', '').find('swing') != -1 or
                    signal.get('is_stable_signal', True) == False
                )
                if is_swing_signal:
                    swing_only.append(signal)
            
            _swing_signals = swing_only.copy()
            _swing_last_scan = time.time()
            print(f"✅ Swing scan completed - cached {len(_swing_signals)} swing signals from {len(all_signals)} total")
        else:
            await opportunity_manager.scan_opportunities_incremental()
            # Cache stable signals separately - get ALL opportunities and filter for stable
            all_signals = opportunity_manager.get_opportunities()
            stable_only = []
            for signal in all_signals:
                is_swing_signal = (
                    signal.get('strategy') in ['swing_trading', 'swing_basic'] or
                    signal.get('strategy_type') in ['swing_trading', 'swing_basic'] or
                    signal.get('signal_id', '').find('swing') != -1 or
                    signal.get('is_stable_signal', True) == False
                )
                if not is_swing_signal:  # Stable signals are NOT swing signals
                    stable_only.append(signal)
            
            _stable_signals = stable_only.copy()
            _stable_last_scan = time.time()
            print(f"✅ Stable scan completed - cached {len(_stable_signals)} stable signals from {len(all_signals)} total")
            
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
    
    # Initialize enhanced signal tracker FIRST
    await enhanced_signal_tracker.initialize()
    
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
    print("🎯 Enhanced signal tracker monitoring real-time PnL")

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
        
        # Check if we have any cached signals (even if not fresh)
        cached_signals = _get_cached_signals(_trading_mode)
        
        # No fresh cache - check if we should trigger a scan
        should_scan = _should_trigger_scan(_trading_mode)
        
        if should_scan and not _scan_in_progress:
            print(f"🔄 Starting scan (mode: {_trading_mode}) - no fresh cache available...")
            _last_scan_start = current_time
            _scan_in_progress = True
            
            # Start background scan without waiting
            _background_scan_task = asyncio.create_task(_background_scan_opportunities())
        
        # Get any existing opportunities (from live opportunity_manager, or use cached as fallback)
        live_opportunities = opportunity_manager.get_opportunities()
        
        # Prefer live signals, but fall back to cached if no live signals
        if live_opportunities:
            all_opportunities = live_opportunities
            source = "live"
        elif cached_signals:
            all_opportunities = cached_signals
            source = "cached"
        else:
            all_opportunities = []
            source = "none"
        
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
    global _trading_mode, _background_scan_task, _last_scan_start, _scan_in_progress, _stable_signals, _swing_signals, _stable_last_scan, _swing_last_scan
    
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
        current_time = time.time()
        
        # IMMEDIATE PRESERVATION: Save current signals before switching
        if opportunity_manager:
            current_signals = opportunity_manager.get_opportunities()
            if current_signals:
                # Filter and save current signals to appropriate cache
                for signal in current_signals:
                    is_swing_signal = (
                        signal.get('strategy') in ['swing_trading', 'swing_basic'] or
                        signal.get('strategy_type') in ['swing_trading', 'swing_basic'] or
                        signal.get('signal_id', '').find('swing') != -1 or
                        signal.get('is_stable_signal', True) == False
                    )
                    
                    if is_swing_signal:
                        # Add to swing cache if not already there
                        if signal not in _swing_signals:
                            _swing_signals.append(signal)
                    else:
                        # Add to stable cache if not already there
                        if signal not in _stable_signals:
                            _stable_signals.append(signal)
                
                # Update last scan times
                if old_mode == "swing_trading":
                    _swing_last_scan = current_time
                    print(f"💾 Preserved {len([s for s in current_signals if s.get('strategy') in ['swing_trading', 'swing_basic']])} swing signals before mode switch")
                else:
                    _stable_last_scan = current_time  
                    print(f"💾 Preserved {len([s for s in current_signals if s.get('strategy') not in ['swing_trading', 'swing_basic']])} stable signals before mode switch")
        
        _trading_mode = mode
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
            # Check if we have ANY cached signals (even if not fresh)
            existing_signals = _get_cached_signals(mode)
            
            if existing_signals:
                print(f"📦 Returning {len(existing_signals)} cached {mode} signals while triggering refresh scan...")
                
                # Start background scan to refresh
                _last_scan_start = current_time
                _scan_in_progress = True
                _background_scan_task = asyncio.create_task(_background_scan_opportunities())
                
                return {
                    "status": "success",
                    "message": f"Trading mode changed to '{mode}' - showing {len(existing_signals)} cached signals (refreshing in background)",
                    "old_mode": old_mode,
                    "new_mode": mode,
                    "cached_signals": len(existing_signals),
                    "scan_needed": True,
                    "scan_progress": {
                        "in_progress": _scan_in_progress,
                        "last_scan_start": _last_scan_start
                    }
                }
            else:
                # No cached signals - trigger background scan
                print(f"⚠️ No {mode} signals cached - triggering background scan...")
                
                _last_scan_start = current_time
                _scan_in_progress = True
                _background_scan_task = asyncio.create_task(_background_scan_opportunities())
                
                return {
                    "status": "success", 
                    "message": f"Trading mode changed to '{mode}' - scanning for signals in background",
                    "old_mode": old_mode,
                    "new_mode": mode,
                    "cached_signals": 0,
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
        
        # Get environment variable to determine if real trading is enabled
        ENABLE_REAL_TRADING = os.getenv('ENABLE_REAL_TRADING', 'false').lower() == 'true'
        
        if ENABLE_REAL_TRADING:
            # Real trading mode - calculate proper position sizing for scalping
            try:
                # Validate signal data
                if not all([trade_request.symbol, trade_request.entry_price, trade_request.stop_loss, trade_request.take_profit]):
                    raise ValueError("Missing required trade parameters")
                
                # Calculate risk and position sizing for scalping
                entry_price = trade_request.entry_price
                stop_loss = trade_request.stop_loss
                take_profit = trade_request.take_profit
                
                # Calculate risk per share
                risk_per_share = abs(entry_price - stop_loss)
                reward_per_share = abs(take_profit - entry_price)
                
                if risk_per_share <= 0:
                    raise ValueError("Invalid stop loss - must be different from entry price")
                
                # Risk management: Use 1-2% of account balance for scalping
                account_balance = 10000.0  # This should come from exchange API in real implementation
                risk_amount = account_balance * 0.02  # 2% max risk for scalping
                
                # Calculate position size
                position_size = risk_amount / risk_per_share
                position_value = position_size * entry_price
                
                # Scalping leverage calculation (based on signal's optimal leverage)
                leverage = 1.0  # Default, should use signal's optimal leverage
                if hasattr(trade_request, 'leverage'):
                    leverage = min(trade_request.leverage, 10.0)  # Max 10x for safety
                
                # Calculate expected profit
                expected_profit = reward_per_share * position_size
                expected_return_pct = (expected_profit / risk_amount) * 100
                
                trade_data = {
                    "trade_id": f"scalp_{trade_request.symbol}_{int(time.time())}",
                    "symbol": trade_request.symbol,
                    "signal_type": trade_request.signal_type,
                    "entry_price": entry_price,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "position_size": round(position_size, 6),
                    "position_value": round(position_value, 2),
                    "leverage": leverage,
                    "risk_amount": round(risk_amount, 2),
                    "expected_profit": round(expected_profit, 2),
                    "expected_return_pct": round(expected_return_pct, 2),
                    "confidence": trade_request.confidence,
                    "strategy": trade_request.strategy,
                    "status": "placed",
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                }
                
                print(f"Real trading order would be placed: {trade_data}")
                
                # Track this signal in enhanced tracker
                signal_for_tracking = {
                    'symbol': trade_request.symbol,
                    'strategy': trade_request.strategy,
                    'direction': trade_request.signal_type,
                    'entry_price': entry_price,
                    'stop_loss': stop_loss,
                    'take_profit': take_profit,
                    'confidence': trade_request.confidence
                }
                
                tracking_id = await enhanced_signal_tracker.track_signal(
                    signal_for_tracking, 
                    position_size
                )
                
                return {
                    "status": "success",
                    "message": f"Scalping trade for {trade_request.symbol} calculated for real execution (DEMO: actual trading disabled for safety)",
                    "trade": trade_data,
                    "trading_mode": "REAL_CALCULATION",
                    "tracking_id": tracking_id,
                    "note": "Set ENABLE_REAL_TRADING=true to enable actual order placement"
                }
                
            except Exception as calc_error:
                return {
                    "status": "error",
                    "message": f"Position sizing calculation failed: {str(calc_error)}",
                    "trading_mode": "REAL_CALCULATION_ERROR"
                }
        else:
            # Simulation mode (default for safety)
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
                "message": f"Manual trade for {trade_request.symbol} has been simulated (trading mode: SIMULATION)",
                "trade": trade_data,
                "trading_mode": "SIMULATION",
                "note": "Set ENABLE_REAL_TRADING=true to enable real trading"
            }
        
    except Exception as e:
        print(f"Error executing manual trade: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error executing manual trade: {str(e)}"
        )

@app.get("/api/v1/trading/status")
async def get_trading_status():
    """Get current trading status and configuration."""
    try:
        ENABLE_REAL_TRADING = os.getenv('ENABLE_REAL_TRADING', 'false').lower() == 'true'
        
        return {
            "status": "success",
            "data": {
                "real_trading_enabled": ENABLE_REAL_TRADING,
                "trading_mode": "REAL" if ENABLE_REAL_TRADING else "SIMULATION",
                "api_key_configured": bool(os.getenv('BINANCE_API_KEY')),
                "risk_per_trade_pct": float(os.getenv('RISK_PER_TRADE_PCT', '2.0')),
                "max_leverage": float(os.getenv('MAX_LEVERAGE', '10.0')),
                "account_balance": 10000.0,  # Would be fetched from exchange in real mode
                "available_balance": 9500.0,
                "currency": "USDT"
            },
            "message": f"Trading mode: {'REAL' if ENABLE_REAL_TRADING else 'SIMULATION'}",
            "configuration": {
                "note": "Set ENABLE_REAL_TRADING=true to enable real trading",
                "safety": "Simulation mode active for safety by default"
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error getting trading status: {str(e)}"
        }

# Store simulated positions in memory (in production, use database)
_simulated_positions = {}

@app.get("/api/v1/trading/positions")
async def get_positions():
    """Get current trading positions (simulated and real)."""
    try:
        ENABLE_REAL_TRADING = os.getenv('ENABLE_REAL_TRADING', 'false').lower() == 'true'
        
        if ENABLE_REAL_TRADING:
            # In real mode, fetch actual positions from exchange
            # For now, return simulated data
            positions = []
        else:
            # Return simulated positions for demonstration
            positions = list(_simulated_positions.values())
            
            # Add some example positions if none exist
            if not positions:
                sample_positions = [
                    {
                        "position_id": "sim_btc_001",
                        "symbol": "BTCUSDT",
                        "side": "LONG",
                        "size": 0.002,
                        "entry_price": 45000.0,
                        "current_price": 45500.0,
                        "unrealized_pnl": 1.0,
                        "unrealized_pnl_percent": 1.11,
                        "leverage": 5.0,
                        "margin_used": 18.0,
                        "liquidation_price": 42000.0,
                        "stop_loss": 44000.0,
                        "take_profit": 47000.0,
                        "strategy": "scalping",
                        "status": "open",
                        "created_at": "2025-01-19T18:00:00Z",
                        "type": "simulated"
                    }
                ]
                positions = sample_positions
        
        # Calculate summary
        total_unrealized_pnl = sum(p.get("unrealized_pnl", 0) for p in positions)
        open_positions = len([p for p in positions if p.get("status") == "open"])
        
        return {
            "status": "success",
            "data": positions,
            "message": f"Retrieved {len(positions)} positions",
            "summary": {
                "total_positions": len(positions),
                "open_positions": open_positions,
                "total_unrealized_pnl": round(total_unrealized_pnl, 2),
                "trading_mode": "REAL" if ENABLE_REAL_TRADING else "SIMULATION"
            }
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

@app.get("/api/v1/debug/cache")
async def debug_cache_status():
    """Debug endpoint to check cache status."""
    global _stable_signals, _swing_signals, _stable_last_scan, _swing_last_scan, _trading_mode
    
    current_time = time.time()
    
    return {
        "current_mode": _trading_mode,
        "stable_cache": {
            "signal_count": len(_stable_signals) if isinstance(_stable_signals, list) else 0,
            "last_scan": _stable_last_scan,
            "age_seconds": current_time - _stable_last_scan if _stable_last_scan > 0 else "never",
            "is_fresh": _are_signals_fresh("stable"),
            "sample_symbols": [s.get('symbol', 'unknown') for s in (_stable_signals[:3] if isinstance(_stable_signals, list) else [])]
        },
        "swing_cache": {
            "signal_count": len(_swing_signals) if isinstance(_swing_signals, list) else 0,
            "last_scan": _swing_last_scan,
            "age_seconds": current_time - _swing_last_scan if _swing_last_scan > 0 else "never",
            "is_fresh": _are_signals_fresh("swing_trading"),
            "sample_symbols": [s.get('symbol', 'unknown') for s in (_swing_signals[:3] if isinstance(_swing_signals, list) else [])]
        },
        "opportunity_manager": {
            "live_signals": len(opportunity_manager.get_opportunities()) if opportunity_manager else 0,
            "sample_symbols": [s.get('symbol', 'unknown') for s in (opportunity_manager.get_opportunities()[:3] if opportunity_manager else [])]
        }
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

@app.get("/api/v1/trading/scalping-signals")
async def get_scalping_signals():
    """Get scalping trading signals focused on capital returns."""
    if not opportunity_manager:
        return {
            "status": "initializing",
            "data": [],
            "message": "Opportunity manager is still initializing"
        }
    
    try:
        # Get scalping opportunities
        scalping_signals = opportunity_manager.get_scalping_opportunities()
        
        if not scalping_signals:
            return {
                "status": "complete",
                "data": [],
                "message": "No scalping signals found",
                "summary": {
                    "total_signals": 0,
                    "high_priority_signals": 0,
                    "avg_capital_return_pct": 0,
                    "max_capital_return_pct": 0,
                    "avg_optimal_leverage": 0
                }
            }
        
        # Calculate summary statistics
        capital_returns = [signal.get('expected_capital_return_pct', 0) for signal in scalping_signals]
        leverages = [signal.get('optimal_leverage', 0) for signal in scalping_signals]
        high_priority_count = len([s for s in scalping_signals if s.get('expected_capital_return_pct', 0) >= 7])
        
        summary = {
            "total_signals": len(scalping_signals),
            "high_priority_signals": high_priority_count,
            "avg_capital_return_pct": round(sum(capital_returns) / len(capital_returns), 2) if capital_returns else 0,
            "max_capital_return_pct": round(max(capital_returns), 2) if capital_returns else 0,
            "avg_optimal_leverage": round(sum(leverages) / len(leverages), 1) if leverages else 0
        }
        
        return {
            "status": "complete",
            "data": scalping_signals,
            "message": f"Found {len(scalping_signals)} scalping signals",
            "summary": summary
        }
        
    except Exception as e:
        return {
            "status": "error",
            "data": [],
            "message": f"Error getting scalping signals: {str(e)}",
            "summary": {
                "total_signals": 0,
                "high_priority_signals": 0,
                "avg_capital_return_pct": 0,
                "max_capital_return_pct": 0,
                "avg_optimal_leverage": 0
            }
        }

@app.post("/api/v1/trading/refresh-scalping")
async def refresh_scalping_signals():
    """Manually refresh scalping signals scan."""
    if not opportunity_manager:
        return {
            "status": "error",
            "message": "Opportunity manager not initialized"
        }
    
    try:
        print("🔄 Manual scalping scan triggered...")
        
        # Trigger scalping scan
        await opportunity_manager.scan_scalping_opportunities()
        
        # Get updated signals
        scalping_signals = opportunity_manager.get_scalping_opportunities()
        
        # Calculate summary statistics
        capital_returns = [signal.get('expected_capital_return_pct', 0) for signal in scalping_signals]
        leverages = [signal.get('optimal_leverage', 0) for signal in scalping_signals]
        high_priority_count = len([s for s in scalping_signals if s.get('expected_capital_return_pct', 0) >= 7])
        
        summary = {
            "total_signals": len(scalping_signals),
            "high_priority_signals": high_priority_count,
            "avg_capital_return_pct": round(sum(capital_returns) / len(capital_returns), 2) if capital_returns else 0,
            "max_capital_return_pct": round(max(capital_returns), 2) if capital_returns else 0,
            "avg_optimal_leverage": round(sum(leverages) / len(leverages), 1) if leverages else 0
        }
        
        return {
            "status": "success",
            "message": f"Scalping scan completed - found {len(scalping_signals)} signals",
            "data": scalping_signals,
            "summary": summary
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Scalping scan failed: {str(e)}",
            "data": [],
            "summary": {
                "total_signals": 0,
                "high_priority_signals": 0,
                "avg_capital_return": 0,
                "max_capital_return": 0
            }
        }

# Signal Quality Assessment Endpoints

@app.get("/api/v1/signals/quality-check")
async def check_signal_quality():
    """Check current signal quality before trading"""
    try:
        if not opportunity_manager:
            return {
                "status": "error",
                "message": "Opportunity manager not initialized"
            }
        
        signals = opportunity_manager.get_opportunities()
        
        if not signals:
            return {
                "status": "no_signals",
                "message": "No signals available",
                "recommendation": "Wait for signal generation"
            }
        
        # Quality assessment
        high_quality = []
        medium_quality = []
        low_quality = []
        
        for signal in signals:
            quality_score, quality_level, issues = assess_signal_quality(signal)
            
            signal_info = {
                'symbol': signal.get('symbol'),
                'strategy': signal.get('strategy'),
                'direction': signal.get('direction'),
                'confidence': signal.get('confidence', 0),
                'quality_score': quality_score,
                'issues': issues
            }
            
            if quality_level == 'HIGH':
                high_quality.append(signal_info)
            elif quality_level == 'MEDIUM':
                medium_quality.append(signal_info)
            else:
                low_quality.append(signal_info)
        
        total = len(signals)
        high_pct = len(high_quality) / total * 100 if total > 0 else 0
        
        # Adaptive trading recommendation - ALWAYS trade to learn!
        if len(signals) >= 3:
            recommendation = "ADAPTIVE LEARNING MODE"
            risk_per_trade = "$10-20 (learning phase)"
            emoji = "🧠"
        elif len(signals) >= 1:
            recommendation = "SINGLE SIGNAL TESTING"
            risk_per_trade = "$5-10 (micro testing)"
            emoji = "🔬"
        else:
            recommendation = "NO SIGNALS AVAILABLE"
            risk_per_trade = "Wait for signal generation"
            emoji = "⏳"
            risk_per_trade = "Wait for signal generation"
            emoji = "⏳"
        
        return {
            "status": "success",
            "message": f"Quality assessment complete - {len(signals)} signals analyzed",
            "quality_summary": {
                "high_quality": len(high_quality),
                "medium_quality": len(medium_quality),
                "low_quality": len(low_quality),
                "high_quality_percentage": round(high_pct, 1)
            },
            "recommendation": {
                "action": recommendation,
                "emoji": emoji,
                "risk_per_trade": risk_per_trade,
                "reason": f"{len(high_quality)} high-quality signals available"
            },
            "signal_details": {
                "high_quality": high_quality[:5],  # Show top 5
                "medium_quality": medium_quality[:3],  # Show top 3
                "low_quality": low_quality[:2]  # Show worst 2
            }
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Quality check failed: {str(e)}"
        }

def assess_signal_quality(signal: dict) -> tuple:
    """Assess individual signal quality"""
    
    issues = []
    quality_points = 0
    max_points = 10
    
    # Check confidence
    confidence = signal.get('confidence', 0)
    if confidence >= 0.8:
        quality_points += 3
    elif confidence >= 0.7:
        quality_points += 2
        issues.append(f"Moderate confidence ({confidence:.1%})")
    elif confidence >= 0.6:
        quality_points += 1
        issues.append(f"Low confidence ({confidence:.1%})")
    else:
        issues.append(f"Very low confidence ({confidence:.1%})")
    
    # Check volatility
    volatility = signal.get('volatility', 0)
    if volatility <= 0.06:
        quality_points += 2
    elif volatility <= 0.08:
        quality_points += 1
        issues.append(f"High volatility ({volatility:.1%})")
    else:
        issues.append(f"Very high volatility ({volatility:.1%})")
    
    # Check volume ratio
    volume_ratio = signal.get('volume_ratio', 0)
    if volume_ratio >= 1.2:
        quality_points += 2
    elif volume_ratio >= 1.0:
        quality_points += 1
        issues.append(f"Low volume surge ({volume_ratio:.2f}x)")
    else:
        issues.append(f"No volume surge ({volume_ratio:.2f}x)")
    
    # Check risk/reward
    entry = signal.get('entry_price', signal.get('entry', 0))
    tp = signal.get('take_profit', 0)
    sl = signal.get('stop_loss', 0)
    
    if entry and tp and sl:
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        rr_ratio = reward / risk if risk > 0 else 0
        
        if rr_ratio >= 1.5:
            quality_points += 2
        elif rr_ratio >= 1.2:
            quality_points += 1
            issues.append(f"Low R:R ratio ({rr_ratio:.2f})")
        else:
            issues.append(f"Poor R:R ratio ({rr_ratio:.2f})")
    else:
        issues.append("Missing price levels")
    
    # Bonus points for strategy type
    strategy = signal.get('strategy', '')
    if 'trend_following' in strategy and confidence > 0.8:
        quality_points += 1  # Trend following with high confidence
    
    # Calculate quality level
    quality_score = (quality_points / max_points) * 100
    
    if quality_score >= 70:
        quality_level = 'HIGH'
    elif quality_score >= 50:
        quality_level = 'MEDIUM'
    else:
        quality_level = 'LOW'
    
    return quality_score, quality_level, issues

# Enhanced Signal Tracking Endpoints

@app.post("/api/v1/signals/track")
async def track_signal_manually(signal_data: dict):
    """Manually add a signal to enhanced tracking"""
    try:
        signal_id = await enhanced_signal_tracker.track_signal(signal_data)
        
        return {
            "status": "success",
            "message": "Signal added to enhanced tracking",
            "signal_id": signal_id
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to track signal: {str(e)}"
        }

@app.get("/api/v1/signals/performance")
async def get_signal_performance(days_back: int = 7, strategy: str = None, symbol: str = None):
    """Get comprehensive signal performance analysis"""
    try:
        performance = await enhanced_signal_tracker.get_performance_summary(days_back)
        
        if not performance:
            return {
                "status": "no_data",
                "message": "No performance data available",
                "data": {}
            }
        
        return {
            "status": "success",
            "message": f"Performance analysis for last {days_back} days",
            "data": performance
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to get performance: {str(e)}",
            "data": {}
        }

@app.get("/api/v1/signals/golden")
async def get_golden_signals(limit: int = 20):
    """Get golden signals (quick 3% gainers)"""
    try:
        golden_signals = await enhanced_signal_tracker.get_golden_signals(limit)
        
        # Calculate insights
        insights = {
            "total_golden": len(golden_signals),
            "avg_time_to_3pct": sum(g['time_to_3pct_minutes'] for g in golden_signals) / len(golden_signals) if golden_signals else 0,
            "best_strategies": {},
            "best_symbols": {}
        }
        
        # Group by strategy and symbol
        for signal in golden_signals:
            strategy = signal['strategy']
            symbol = signal['symbol']
            
            if strategy not in insights['best_strategies']:
                insights['best_strategies'][strategy] = 0
            insights['best_strategies'][strategy] += 1
            
            if symbol not in insights['best_symbols']:
                insights['best_symbols'][symbol] = 0
            insights['best_symbols'][symbol] += 1
        
        return {
            "status": "success",
            "message": f"Found {len(golden_signals)} golden signals",
            "data": golden_signals,
            "insights": insights
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to get golden signals: {str(e)}",
            "data": []
        }

@app.get("/api/v1/signals/live-tracking")
async def get_live_tracking_status():
    """Get current live tracking status"""
    try:
        active_count = len(enhanced_signal_tracker.active_signals)
        
        # Get summary of active signals
        active_summary = []
        for signal_id, signal_data in enhanced_signal_tracker.active_signals.items():
            current_price = enhanced_signal_tracker.price_cache.get(signal_data['symbol'], 0)
            
            # Calculate current PnL
            if current_price > 0:
                entry_price = signal_data['entry_price']
                direction = signal_data['direction']
                
                if direction == 'LONG':
                    pnl_pct = (current_price - entry_price) / entry_price
                else:
                    pnl_pct = (entry_price - current_price) / entry_price
            else:
                pnl_pct = 0
            
            active_summary.append({
                'signal_id': signal_id[:8] + '...',
                'symbol': signal_data['symbol'],
                'strategy': signal_data['strategy'],
                'direction': signal_data['direction'],
                'age_minutes': int((datetime.now() - signal_data['entry_time']).total_seconds() / 60),
                'current_pnl_pct': round(pnl_pct * 100, 2),
                'targets_hit': signal_data['targets_hit'],
                'max_profit_pct': round(signal_data['max_profit'] * 100, 2)
            })
        
        return {
            "status": "success",
            "message": f"Tracking {active_count} signals in real-time",
            "data": {
                "active_signals_count": active_count,
                "price_cache_symbols": len(enhanced_signal_tracker.price_cache),
                "active_signals": active_summary
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to get tracking status: {str(e)}",
            "data": {}
        }

@app.post("/api/v1/signals/adjust-criteria")
async def adjust_signal_criteria(request: CriteriaAdjustmentRequest):
    """Adjust signal criteria based on performance analysis"""
    try:
        # This would integrate with your signal generation to loosen/tighten criteria
        # For now, return suggested adjustments based on performance
        
        # Get recent performance for the strategy
        performance = await enhanced_signal_tracker.get_performance_summary(days_back=7)
        
        # Find performance for this specific strategy
        strategy_performance = None
        for strat in performance.get('by_strategy', []):
            if strat['strategy'] == request.strategy:
                strategy_performance = strat
                break
        
        if not strategy_performance:
            return {
                "status": "no_data",
                "message": f"No performance data for strategy: {request.strategy}",
                "suggestions": []
            }
        
        suggestions = []
        
        # Analyze performance and suggest adjustments
        hit_rate_3pct = strategy_performance['hit_3pct'] / max(strategy_performance['total'], 1)
        
        if hit_rate_3pct < 0.3:  # Less than 30% hit rate
            suggestions.append({
                "type": "loosen_criteria",
                "reason": f"Hit rate too low ({hit_rate_3pct:.1%})",
                "suggestion": "Consider lowering min_confidence or increasing max_volatility"
            })
        elif hit_rate_3pct > 0.7:  # Greater than 70% hit rate
            suggestions.append({
                "type": "tighten_criteria", 
                "reason": f"Hit rate very high ({hit_rate_3pct:.1%})",
                "suggestion": "Consider raising min_confidence to capture higher quality signals"
            })
        
        # Check golden signal ratio
        golden_ratio = strategy_performance['golden'] / max(strategy_performance['total'], 1)
        if golden_ratio < 0.1:  # Less than 10% golden signals
            suggestions.append({
                "type": "optimize_timing",
                "reason": f"Low golden signal ratio ({golden_ratio:.1%})",
                "suggestion": "Consider adjusting entry timing or risk/reward ratios"
            })
        
        return {
            "status": "success",
            "message": f"Analysis complete for {request.strategy}",
            "performance": strategy_performance,
            "suggestions": suggestions,
            "current_criteria": {
                "min_confidence": request.min_confidence,
                "min_risk_reward": request.min_risk_reward,
                "max_volatility": request.max_volatility,
                "min_volume_ratio": request.min_volume_ratio
            }
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to analyze criteria: {str(e)}",
            "suggestions": []
        }

@app.get("/api/v1/signals/backtest-report")
async def get_backtest_report(strategy: str = None, days_back: int = 30):
    """Get comprehensive backtest report based on real signal tracking"""
    try:
        performance = await enhanced_signal_tracker.get_performance_summary(days_back)
        
        if not performance:
            return {
                "status": "no_data", 
                "message": "No data available for backtest report"
            }
        
        overall = performance['overall']
        
        # Calculate key metrics
        total_signals = overall['total_signals']
        win_rate_3pct = (overall['signals_3pct'] / max(total_signals, 1)) * 100
        win_rate_5pct = (overall['signals_5pct'] / max(total_signals, 1)) * 100
        stop_rate = (overall['signals_stopped'] / max(total_signals, 1)) * 100
        golden_rate = (overall['golden_signals'] / max(total_signals, 1)) * 100
        
        # Performance grades
        grade_3pct = "A" if win_rate_3pct > 60 else "B" if win_rate_3pct > 40 else "C" if win_rate_3pct > 25 else "D"
        grade_golden = "A" if golden_rate > 15 else "B" if golden_rate > 10 else "C" if golden_rate > 5 else "D"
        
        report = {
            "period": f"Last {days_back} days",
            "total_signals_tested": total_signals,
            "performance_metrics": {
                "3pct_hit_rate": round(win_rate_3pct, 1),
                "5pct_hit_rate": round(win_rate_5pct, 1), 
                "stop_loss_rate": round(stop_rate, 1),
                "golden_signal_rate": round(golden_rate, 1),
                "avg_time_to_3pct": round(overall['avg_time_to_3pct'], 1),
                "avg_max_profit": round(overall['avg_max_profit'] * 100, 2)
            },
            "performance_grades": {
                "3pct_performance": grade_3pct,
                "golden_signals": grade_golden,
                "overall": grade_3pct if grade_3pct in ['A', 'B'] and grade_golden in ['A', 'B'] else 'C'
            },
            "strategy_rankings": sorted(performance['by_strategy'], key=lambda x: x['golden'], reverse=True),
            "recommendations": []
        }
        
        # Add recommendations
        if win_rate_3pct < 30:
            report["recommendations"].append("⚠️ Low 3% hit rate - consider loosening signal criteria")
        if golden_rate < 5:
            report["recommendations"].append("⚠️ Very few golden signals - review entry timing and R:R ratios")
        if win_rate_3pct > 70:
            report["recommendations"].append("✅ High performance - consider tightening criteria for quality")
        if golden_rate > 15:
            report["recommendations"].append("🌟 Excellent golden signal rate - current settings are optimal")
        
        return {
            "status": "success",
            "message": "Backtest report generated from real signal tracking",
            "report": report
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to generate backtest report: {str(e)}"
        }

# Adaptive Trading System Endpoints

@app.get("/api/v1/signals/adaptive-assessment")
async def adaptive_signal_assessment():
    """Adaptive assessment that encourages learning from all market conditions"""
    try:
        if not opportunity_manager:
            return {
                "status": "error",
                "message": "Opportunity manager not initialized"
            }
        
        signals = opportunity_manager.get_opportunities()
        
        if not signals:
            return {
                "status": "no_signals",
                "message": "No signals available - waiting for signal generation",
                "recommendation": {
                    "action": "WAIT FOR SIGNALS",
                    "emoji": "⏳",
                    "approach": "Patient signal generation"
                }
            }
        
        # Adaptive market analysis
        market_analysis = analyze_current_market_regime(signals)
        
        # Adaptive risk sizing based on market conditions
        risk_recommendation = calculate_adaptive_risk(market_analysis, len(signals))
        
        # Learning opportunities in each signal
        learning_opportunities = []
        for signal in signals[:5]:  # Analyze top 5
            learning_value = assess_learning_potential(signal, market_analysis)
            learning_opportunities.append(learning_value)
        
        return {
            "status": "success",
            "message": f"Adaptive analysis complete - {len(signals)} signals for learning",
            "market_regime": market_analysis,
            "adaptive_strategy": {
                "approach": "CONTINUOUS LEARNING",
                "philosophy": "Adapt to ANY market conditions",
                "emoji": "🧠",
                "action": risk_recommendation["action"],
                "risk_per_trade": risk_recommendation["risk_amount"],
                "reasoning": risk_recommendation["reasoning"]
            },
            "learning_opportunities": learning_opportunities,
            "data_collection_priority": {
                "high_volatility_learning": market_analysis["volatility_regime"] == "high",
                "volume_pattern_learning": market_analysis["volume_regime"] == "unusual",
                "trend_adaptation_learning": market_analysis["trend_strength"] < 0.5,
                "scalping_optimization": True
            }
        }
        
    except Exception as e:
        return {
            "status": "error", 
            "message": f"Adaptive assessment failed: {str(e)}"
        }

def analyze_current_market_regime(signals: list) -> dict:
    """Analyze what type of market regime we're in"""
    
    volatilities = [s.get('volatility', 0) for s in signals]
    volumes = [s.get('volume_ratio', 0) for s in signals]
    confidences = [s.get('confidence', 0) for s in signals]
    
    avg_volatility = sum(volatilities) / len(volatilities) if volatilities else 0
    avg_volume = sum(volumes) / len(volumes) if volumes else 0
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0
    
    # Determine regime characteristics
    volatility_regime = "high" if avg_volatility > 0.08 else "medium" if avg_volatility > 0.04 else "low"
    volume_regime = "high" if avg_volume > 1.5 else "normal" if avg_volume > 0.8 else "low"
    confidence_regime = "high" if avg_confidence > 0.8 else "medium" if avg_confidence > 0.6 else "low"
    
    # Market characterization
    if volatility_regime == "high" and volume_regime in ["high", "normal"]:
        market_type = "VOLATILE_ACTIVE"
        characteristics = "High volatility with volume - excellent for adaptive scalping"
    elif volatility_regime == "high" and volume_regime == "low":
        market_type = "VOLATILE_THIN"
        characteristics = "High volatility, low volume - learn gap/spike patterns"
    elif volatility_regime == "low" and volume_regime == "high":
        market_type = "STEADY_ACTIVE"
        characteristics = "Low volatility, high volume - perfect for mean reversion learning"
    else:
        market_type = "MIXED_CONDITIONS"
        characteristics = "Mixed conditions - excellent for multi-strategy learning"
    
    return {
        "market_type": market_type,
        "characteristics": characteristics,
        "volatility_regime": volatility_regime,
        "volume_regime": volume_regime,
        "confidence_regime": confidence_regime,
        "avg_volatility": round(avg_volatility * 100, 2),
        "avg_volume_ratio": round(avg_volume, 2),
        "avg_confidence": round(avg_confidence * 100, 1),
        "learning_potential": "HIGH"  # Always high - we learn from everything!
    }

def calculate_adaptive_risk(market_analysis: dict, signal_count: int) -> dict:
    """Calculate adaptive risk based on market conditions and learning goals"""
    
    base_risk = 10  # $10 base learning amount
    
    # Adjust based on market regime
    volatility_multiplier = {
        "high": 0.5,    # Lower risk in high vol, but still trade to learn
        "medium": 0.75,
        "low": 1.0
    }.get(market_analysis["volatility_regime"], 0.75)
    
    # More signals = more learning opportunities = slightly higher total exposure
    signal_multiplier = min(1.5, 1.0 + (signal_count - 1) * 0.1)
    
    # Calculate adaptive risk
    risk_amount = base_risk * volatility_multiplier * signal_multiplier
    risk_amount = max(5, min(25, risk_amount))  # Between $5-25
    
    # Action recommendation
    if market_analysis["market_type"] == "VOLATILE_ACTIVE":
        action = "ACTIVE LEARNING"
        reasoning = f"High volatility + volume = great scalping learning data. Risk ${risk_amount:.0f} per signal to capture this regime."
    elif market_analysis["market_type"] == "VOLATILE_THIN":
        action = "CAUTIOUS LEARNING"
        reasoning = f"High volatility + low volume = learn gap patterns. Risk ${risk_amount:.0f} per signal for safe data collection."
    elif market_analysis["market_type"] == "STEADY_ACTIVE":
        action = "SYSTEMATIC LEARNING"
        reasoning = f"Stable conditions + volume = perfect for mean reversion learning. Risk ${risk_amount:.0f} per signal."
    else:
        action = "ADAPTIVE LEARNING"
        reasoning = f"Mixed conditions = learn multiple patterns. Risk ${risk_amount:.0f} per signal for comprehensive data."
    
    return {
        "action": action,
        "risk_amount": f"${risk_amount:.0f}",
        "reasoning": reasoning,
        "total_exposure": f"${risk_amount * min(signal_count, 3):.0f}"  # Max 3 concurrent
    }

def assess_learning_potential(signal: dict, market_analysis: dict) -> dict:
    """Assess what we can learn from each signal"""
    
    symbol = signal.get('symbol', 'Unknown')
    strategy = signal.get('strategy', 'Unknown')
    confidence = signal.get('confidence', 0)
    volatility = signal.get('volatility', 0)
    
    learning_aspects = []
    
    # What can we learn from this specific signal?
    if volatility > 0.1:
        learning_aspects.append("High volatility scalping patterns")
    if confidence > 0.85:
        learning_aspects.append("High confidence signal validation")
    if 'trend_following' in strategy:
        learning_aspects.append("Trend following in current regime")
    if 'mean_reversion' in strategy:
        learning_aspects.append("Mean reversion effectiveness")
    
    # Market regime specific learning
    if market_analysis["volatility_regime"] == "high":
        learning_aspects.append("Volatile market adaptation")
    if market_analysis["volume_regime"] == "low":
        learning_aspects.append("Low volume execution patterns")
    
    learning_value = "HIGH" if len(learning_aspects) >= 3 else "MEDIUM" if len(learning_aspects) >= 2 else "BASIC"
    
    return {
        "symbol": symbol,
        "strategy": strategy,
        "confidence_pct": round(confidence * 100, 1),
        "volatility_pct": round(volatility * 100, 1),
        "learning_value": learning_value,
        "learning_aspects": learning_aspects,
        "recommendation": f"Trade with ${calculate_adaptive_risk(market_analysis, 1)['risk_amount']} to learn {', '.join(learning_aspects[:2])}"
    }

@app.post("/api/v1/signals/enable-adaptive-mode")
async def enable_adaptive_mode():
    """Enable adaptive learning mode that trades in all conditions"""
    try:
        # Set adaptive risk parameters
        adaptive_config = {
            "mode": "ADAPTIVE_LEARNING",
            "philosophy": "Learn and profit from ANY market conditions",
            "risk_strategy": "Small amounts across all signals for maximum learning",
            "adaptation_period": "7-14 days to build market-specific models",
            "success_metrics": [
                "Data collection completeness",
                "Pattern recognition accuracy", 
                "Market regime adaptation speed",
                "Profitability across conditions"
            ]
        }
        
        return {
            "status": "success",
            "message": "Adaptive learning mode enabled",
            "configuration": adaptive_config,
            "next_steps": [
                "1. Start trading all signals with small amounts ($5-20)",
                "2. Let enhanced tracking collect performance data",
                "3. System will adapt criteria for current market regime",
                "4. After 7 days, review what works in these conditions",
                "5. Scale up successful patterns, optimize unsuccessful ones"
            ],
            "mindset_shift": {
                "from": "Wait for perfect conditions",
                "to": "Adapt and profit from current conditions",
                "result": "All-weather trading system"
            }
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to enable adaptive mode: {str(e)}"
        }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 