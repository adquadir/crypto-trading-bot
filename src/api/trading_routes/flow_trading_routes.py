"""
Flow Trading API Routes
Advanced flow trading strategies with dynamic switching and grid trading
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import asyncio
import logging
from datetime import datetime, timedelta
import random

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/flow-trading", tags=["flow-trading"])

# Global state for flow trading
flow_trading_state = {
    "active_strategies": 0,
    "active_scalping": 0,
    "active_grids": 0,
    "total_exposure_usd": 0.0,
    "daily_pnl": 0.0,
    "start_time": None
}

# Mock data storage
active_strategies = []
active_grids = []
risk_metrics = {}
performance_data = {}

class GridConfig(BaseModel):
    symbol: str
    levels: int = 5
    spacing_multiplier: float = 1.0
    position_size_usd: float = 50.0

@router.get("/status")
async def get_flow_trading_status():
    """Get current flow trading status"""
    try:
        # Update active counts
        flow_trading_state["active_strategies"] = len(active_strategies)
        flow_trading_state["active_grids"] = len(active_grids)
        flow_trading_state["active_scalping"] = len([s for s in active_strategies if s.get("current_strategy") == "scalping"])
        
        return {
            "status": "success",
            "data": flow_trading_state
        }
    except Exception as e:
        logger.error(f"Error getting flow trading status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/strategies")
async def get_active_strategies():
    """Get all active trading strategies"""
    try:
        # Generate mock strategies if none exist
        if not active_strategies:
            generate_mock_strategies()
        
        return {
            "status": "success",
            "data": active_strategies
        }
    except Exception as e:
        logger.error(f"Error getting active strategies: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/strategies/{symbol}/start")
async def start_strategy(symbol: str, background_tasks: BackgroundTasks):
    """Start flow trading strategy for a symbol"""
    try:
        # Check if strategy already exists
        existing = next((s for s in active_strategies if s["symbol"] == symbol), None)
        if existing:
            return {
                "status": "error",
                "message": f"Strategy for {symbol} already active"
            }
        
        # Create new strategy
        new_strategy = {
            "symbol": symbol,
            "current_strategy": "scalping",
            "market_regime": "ranging",
            "uptime_minutes": 0.0,
            "switch_count": 0,
            "performance_score": 0.0,
            "start_time": datetime.now(),
            "last_switch": datetime.now()
        }
        
        active_strategies.append(new_strategy)
        
        # Start background monitoring
        background_tasks.add_task(monitor_strategy, symbol)
        
        return {
            "status": "success",
            "message": f"Flow trading started for {symbol}",
            "data": new_strategy
        }
    except Exception as e:
        logger.error(f"Error starting strategy for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/strategies/{symbol}/stop")
async def stop_strategy(symbol: str):
    """Stop flow trading strategy for a symbol"""
    try:
        # Remove strategy
        global active_strategies
        active_strategies = [s for s in active_strategies if s["symbol"] != symbol]
        
        return {
            "status": "success",
            "message": f"Flow trading stopped for {symbol}"
        }
    except Exception as e:
        logger.error(f"Error stopping strategy for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/grids")
async def get_active_grids():
    """Get all active grid trading instances"""
    try:
        # Generate mock grids if none exist
        if not active_grids:
            generate_mock_grids()
        
        return {
            "status": "success",
            "data": active_grids
        }
    except Exception as e:
        logger.error(f"Error getting active grids: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/grids/{symbol}/start")
async def start_grid(symbol: str, config: GridConfig, background_tasks: BackgroundTasks):
    """Start grid trading for a symbol"""
    try:
        # Check if grid already exists
        existing = next((g for g in active_grids if g["symbol"] == symbol), None)
        if existing:
            return {
                "status": "error",
                "message": f"Grid for {symbol} already active"
            }
        
        # Create new grid
        base_price = random.uniform(20000, 70000) if symbol == "BTCUSDT" else random.uniform(1500, 4000)
        grid_spacing = base_price * 0.001 * config.spacing_multiplier  # 0.1% spacing
        
        new_grid = {
            "symbol": symbol,
            "center_price": round(base_price, 4),
            "grid_spacing": round(grid_spacing, 6),
            "total_levels": config.levels,
            "active_orders": config.levels,
            "filled_orders": 0,
            "total_profit": 0.0,
            "uptime_minutes": 0.0,
            "position_size_usd": config.position_size_usd,
            "start_time": datetime.now()
        }
        
        active_grids.append(new_grid)
        
        # Start background grid monitoring
        background_tasks.add_task(monitor_grid, symbol)
        
        return {
            "status": "success",
            "message": f"Grid trading started for {symbol}",
            "data": new_grid
        }
    except Exception as e:
        logger.error(f"Error starting grid for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/grids/{symbol}/stop")
async def stop_grid(symbol: str):
    """Stop grid trading for a symbol"""
    try:
        # Remove grid
        global active_grids
        active_grids = [g for g in active_grids if g["symbol"] != symbol]
        
        return {
            "status": "success",
            "message": f"Grid trading stopped for {symbol}"
        }
    except Exception as e:
        logger.error(f"Error stopping grid for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/risk")
async def get_risk_metrics():
    """Get current risk metrics"""
    try:
        if not risk_metrics:
            generate_mock_risk_metrics()
        
        return {
            "status": "success",
            "data": risk_metrics
        }
    except Exception as e:
        logger.error(f"Error getting risk metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/performance")
async def get_performance_data():
    """Get performance analytics"""
    try:
        if not performance_data:
            generate_mock_performance_data()
        
        return {
            "status": "success",
            "data": performance_data
        }
    except Exception as e:
        logger.error(f"Error getting performance data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/emergency-stop")
async def emergency_stop():
    """Emergency stop all flow trading activities"""
    try:
        global active_strategies, active_grids
        
        stopped_strategies = len(active_strategies)
        stopped_grids = len(active_grids)
        
        active_strategies.clear()
        active_grids.clear()
        
        # Reset state
        flow_trading_state.update({
            "active_strategies": 0,
            "active_scalping": 0,
            "active_grids": 0,
            "total_exposure_usd": 0.0
        })
        
        return {
            "status": "success",
            "message": f"Emergency stop executed. Stopped {stopped_strategies} strategies and {stopped_grids} grids",
            "data": {
                "stopped_strategies": stopped_strategies,
                "stopped_grids": stopped_grids,
                "timestamp": datetime.now().isoformat()
            }
        }
    except Exception as e:
        logger.error(f"Error executing emergency stop: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Background monitoring tasks
async def monitor_strategy(symbol: str):
    """Background task to monitor and update strategy"""
    while any(s["symbol"] == symbol for s in active_strategies):
        try:
            await asyncio.sleep(30)  # Update every 30 seconds
            
            # Find and update strategy
            strategy = next((s for s in active_strategies if s["symbol"] == symbol), None)
            if not strategy:
                break
            
            # Update uptime
            uptime_delta = datetime.now() - strategy["start_time"]
            strategy["uptime_minutes"] = uptime_delta.total_seconds() / 60
            
            # Randomly switch strategies
            if random.random() > 0.9:  # 10% chance to switch
                strategies = ["scalping", "grid_trading", "disabled"]
                new_strategy = random.choice([s for s in strategies if s != strategy["current_strategy"]])
                strategy["current_strategy"] = new_strategy
                strategy["switch_count"] += 1
                strategy["last_switch"] = datetime.now()
            
            # Update market regime
            regimes = ["trending_up", "trending_down", "ranging", "high_volatility"]
            if random.random() > 0.8:  # 20% chance to change regime
                strategy["market_regime"] = random.choice(regimes)
            
            # Update performance score
            strategy["performance_score"] += random.uniform(-0.1, 0.2)
            
        except Exception as e:
            logger.error(f"Error monitoring strategy {symbol}: {e}")
            await asyncio.sleep(10)

async def monitor_grid(symbol: str):
    """Background task to monitor and update grid"""
    while any(g["symbol"] == symbol for g in active_grids):
        try:
            await asyncio.sleep(20)  # Update every 20 seconds
            
            # Find and update grid
            grid = next((g for g in active_grids if g["symbol"] == symbol), None)
            if not grid:
                break
            
            # Update uptime
            uptime_delta = datetime.now() - grid["start_time"]
            grid["uptime_minutes"] = uptime_delta.total_seconds() / 60
            
            # Simulate order fills
            if random.random() > 0.7:  # 30% chance of order fill
                if grid["active_orders"] > 0:
                    grid["active_orders"] -= 1
                    grid["filled_orders"] += 1
                    
                    # Add profit from filled order
                    profit = random.uniform(0.5, 3.0)
                    grid["total_profit"] += profit
                    
                    # Sometimes add new orders
                    if random.random() > 0.5:
                        grid["active_orders"] += 1
            
        except Exception as e:
            logger.error(f"Error monitoring grid {symbol}: {e}")
            await asyncio.sleep(10)

def generate_mock_strategies():
    """Generate mock strategy data"""
    symbols = ["BTCUSDT", "ETHUSDT", "ADAUSDT", "BNBUSDT"]
    strategies = ["scalping", "grid_trading", "disabled"]
    regimes = ["trending_up", "trending_down", "ranging", "high_volatility"]
    
    for symbol in symbols[:2]:  # Start with 2 symbols
        strategy = {
            "symbol": symbol,
            "current_strategy": random.choice(strategies),
            "market_regime": random.choice(regimes),
            "uptime_minutes": round(random.uniform(10, 300), 1),
            "switch_count": random.randint(0, 5),
            "performance_score": round(random.uniform(-2.0, 5.0), 2),
            "start_time": datetime.now() - timedelta(minutes=random.uniform(10, 300)),
            "last_switch": datetime.now() - timedelta(minutes=random.uniform(1, 60))
        }
        active_strategies.append(strategy)

def generate_mock_grids():
    """Generate mock grid data"""
    symbols = ["BTCUSDT", "ETHUSDT"]
    
    for symbol in symbols:
        base_price = random.uniform(20000, 70000) if symbol == "BTCUSDT" else random.uniform(1500, 4000)
        grid_spacing = base_price * 0.001
        
        grid = {
            "symbol": symbol,
            "center_price": round(base_price, 4),
            "grid_spacing": round(grid_spacing, 6),
            "total_levels": random.randint(3, 7),
            "active_orders": random.randint(2, 5),
            "filled_orders": random.randint(0, 10),
            "total_profit": round(random.uniform(-5.0, 25.0), 4),
            "uptime_minutes": round(random.uniform(30, 500), 1),
            "position_size_usd": 50.0,
            "start_time": datetime.now() - timedelta(minutes=random.uniform(30, 500))
        }
        active_grids.append(grid)

def generate_mock_risk_metrics():
    """Generate mock risk metrics"""
    global risk_metrics
    
    total_exposure = sum(g["position_size_usd"] * g["active_orders"] for g in active_grids)
    total_exposure += len(active_strategies) * 100  # Assume $100 per strategy
    
    risk_metrics = {
        "total_exposure_usd": round(total_exposure, 2),
        "total_exposure_pct": round(total_exposure / 10000 * 100, 1),  # Assume $10k portfolio
        "max_drawdown_pct": round(random.uniform(1.0, 8.0), 1),
        "active_strategies": len(active_strategies),
        "correlation_concentration": round(random.uniform(0.3, 0.8), 2),
        "var_1d": round(random.uniform(50, 200), 2),
        "sharpe_ratio": round(random.uniform(0.8, 2.2), 2),
        "last_updated": datetime.now().isoformat()
    }

def generate_mock_performance_data():
    """Generate mock performance data"""
    global performance_data
    
    # Generate daily performance for last 30 days
    daily_performance = []
    for i in range(30):
        date = datetime.now() - timedelta(days=i)
        daily_performance.append({
            "date": date.strftime("%Y-%m-%d"),
            "daily_pnl": round(random.uniform(-20.0, 50.0), 2),
            "daily_trades": random.randint(5, 25),
            "avg_win_rate": round(random.uniform(0.55, 0.80), 3)
        })
    
    # Generate strategy breakdown
    strategies = ["scalping", "grid_trading", "momentum"]
    strategy_breakdown = []
    for strategy in strategies:
        strategy_breakdown.append({
            "strategy_type": strategy,
            "total_pnl": round(random.uniform(-10.0, 100.0), 2),
            "total_trades": random.randint(20, 150),
            "avg_win_rate": round(random.uniform(0.50, 0.75), 3)
        })
    
    performance_data = {
        "daily_performance": daily_performance,
        "strategy_breakdown": strategy_breakdown,
        "total_pnl_7d": round(sum(d["daily_pnl"] for d in daily_performance[:7]), 2),
        "total_trades_7d": sum(d["daily_trades"] for d in daily_performance[:7]),
        "avg_win_rate_7d": round(sum(d["avg_win_rate"] for d in daily_performance[:7]) / 7, 3),
        "last_updated": datetime.now().isoformat()
    }
