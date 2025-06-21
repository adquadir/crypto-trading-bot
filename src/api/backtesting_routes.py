"""
🚀 Backtesting API Routes

Provides REST API endpoints for backtesting functionality:
- Run backtests
- Compare strategies
- Get analysis results
- Export results
"""

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import asyncio
import logging

from ..backtesting.backtest_runner import BacktestRunner
from ..backtesting.strategy_analyzer import StrategyAnalyzer

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/v1/backtesting", tags=["backtesting"])

# Global instances
backtest_runner = BacktestRunner()
strategy_analyzer = StrategyAnalyzer()

# Pydantic models
class BacktestRequest(BaseModel):
    strategy: str
    symbol: str
    days_back: int = 30
    initial_balance: float = 10000.0

class MultiBacktestRequest(BaseModel):
    strategies: List[str]
    symbols: List[str]
    days_back: int = 30
    initial_balance: float = 10000.0

class StrategyComparisonRequest(BaseModel):
    strategies: List[str]
    symbol: str
    days_back: int = 30

class MarketRegimeRequest(BaseModel):
    strategy: str
    symbol: str
    days_back: int = 180

# Store running backtests
running_backtests = {}

@router.post("/run")
async def run_backtest(request: BacktestRequest):
    """
    🚀 Run a single strategy backtest
    
    Returns immediate results for quick backtests.
    """
    try:
        logger.info(f"🔄 Running backtest: {request.strategy} on {request.symbol}")
        
        # Create new runner with specified balance
        runner = BacktestRunner(request.initial_balance)
        
        # Run backtest
        performance = await runner.run_quick_backtest(
            strategy=request.strategy,
            symbol=request.symbol,
            days_back=request.days_back
        )
        
        return {
            "success": True,
            "strategy": request.strategy,
            "symbol": request.symbol,
            "period_days": request.days_back,
            "performance": {
                "total_return": performance.total_return,
                "win_rate": performance.win_rate,
                "total_trades": performance.total_trades,
                "avg_return_per_trade": performance.avg_return_per_trade,
                "max_drawdown": performance.max_drawdown,
                "sharpe_ratio": performance.sharpe_ratio,
                "profit_factor": performance.profit_factor,
                "avg_trade_duration": performance.avg_trade_duration,
                "best_trade": performance.best_trade,
                "worst_trade": performance.worst_trade
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Backtest failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/compare")
async def compare_strategies(request: StrategyComparisonRequest):
    """
    ⚔️ Compare multiple strategies on the same symbol
    """
    try:
        logger.info(f"⚔️ Comparing strategies on {request.symbol}")
        
        runner = BacktestRunner()
        comparison_df = await runner.run_strategy_comparison(
            strategies=request.strategies,
            symbol=request.symbol,
            days_back=request.days_back
        )
        
        # Convert DataFrame to dict for JSON response
        comparison_data = comparison_df.to_dict('records')
        
        return {
            "success": True,
            "symbol": request.symbol,
            "period_days": request.days_back,
            "comparison": comparison_data
        }
        
    except Exception as e:
        logger.error(f"❌ Strategy comparison failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/comprehensive")
async def run_comprehensive_backtest(
    request: MultiBacktestRequest,
    background_tasks: BackgroundTasks
):
    """
    🎯 Run comprehensive backtest across multiple strategies and symbols
    
    This is a long-running operation, so it returns a task ID immediately
    and runs the backtest in the background.
    """
    try:
        # Generate task ID
        task_id = f"backtest_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Store task info
        running_backtests[task_id] = {
            "status": "running",
            "started_at": datetime.now(),
            "progress": 0,
            "total_tests": len(request.strategies) * len(request.symbols),
            "results": None
        }
        
        # Start background task
        background_tasks.add_task(
            run_comprehensive_backtest_task,
            task_id,
            request
        )
        
        return {
            "success": True,
            "task_id": task_id,
            "status": "started",
            "message": "Comprehensive backtest started. Use /status/{task_id} to check progress."
        }
        
    except Exception as e:
        logger.error(f"❌ Comprehensive backtest failed to start: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def run_comprehensive_backtest_task(task_id: str, request: MultiBacktestRequest):
    """Background task for comprehensive backtesting"""
    try:
        runner = BacktestRunner(request.initial_balance)
        
        # Update progress
        running_backtests[task_id]["status"] = "running"
        
        results = await runner.run_comprehensive_backtest(
            strategies=request.strategies,
            symbols=request.symbols,
            days_back=request.days_back
        )
        
        # Convert results to JSON-serializable format
        json_results = {}
        for strategy, symbol_results in results.items():
            json_results[strategy] = {}
            for symbol, performance in symbol_results.items():
                json_results[strategy][symbol] = {
                    "total_return": performance.total_return,
                    "win_rate": performance.win_rate,
                    "total_trades": performance.total_trades,
                    "sharpe_ratio": performance.sharpe_ratio,
                    "max_drawdown": performance.max_drawdown,
                    "profit_factor": performance.profit_factor
                }
        
        # Update task status
        running_backtests[task_id].update({
            "status": "completed",
            "completed_at": datetime.now(),
            "progress": 100,
            "results": json_results,
            "best_strategy": runner.get_best_strategy()
        })
        
        logger.info(f"✅ Comprehensive backtest {task_id} completed")
        
    except Exception as e:
        logger.error(f"❌ Comprehensive backtest {task_id} failed: {e}")
        running_backtests[task_id].update({
            "status": "failed",
            "error": str(e),
            "completed_at": datetime.now()
        })

@router.get("/status/{task_id}")
async def get_backtest_status(task_id: str):
    """
    📊 Get status of a running backtest
    """
    if task_id not in running_backtests:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task_info = running_backtests[task_id]
    
    return {
        "task_id": task_id,
        "status": task_info["status"],
        "progress": task_info.get("progress", 0),
        "started_at": task_info["started_at"],
        "completed_at": task_info.get("completed_at"),
        "results": task_info.get("results"),
        "best_strategy": task_info.get("best_strategy"),
        "error": task_info.get("error")
    }

@router.post("/analyze")
async def analyze_strategy(
    strategy: str,
    symbol: str,
    days_back: int = 90
):
    """
    🔍 Run detailed strategy analysis
    """
    try:
        logger.info(f"🔍 Analyzing {strategy} on {symbol}")
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        analysis = await strategy_analyzer.analyze_strategy_performance(
            strategy_name=strategy,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date
        )
        
        # Convert analysis to JSON-serializable format
        json_analysis = {
            "basic_performance": {
                "total_return": analysis["basic_performance"].total_return,
                "win_rate": analysis["basic_performance"].win_rate,
                "total_trades": analysis["basic_performance"].total_trades,
                "sharpe_ratio": analysis["basic_performance"].sharpe_ratio,
                "max_drawdown": analysis["basic_performance"].max_drawdown,
                "profit_factor": analysis["basic_performance"].profit_factor
            },
            "insights": analysis.get("insights", []),
            "market_condition_analysis": analysis.get("market_condition_analysis", {}),
            "risk_metrics": analysis.get("risk_metrics", {}),
            "trade_distribution": analysis.get("trade_distribution", {})
        }
        
        return {
            "success": True,
            "strategy": strategy,
            "symbol": symbol,
            "period_days": days_back,
            "analysis": json_analysis
        }
        
    except Exception as e:
        logger.error(f"❌ Strategy analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/market-regime")
async def analyze_market_regimes(request: MarketRegimeRequest):
    """
    📈 Analyze strategy performance across market regimes
    """
    try:
        logger.info(f"📈 Analyzing market regimes for {request.strategy}")
        
        runner = BacktestRunner()
        regime_analysis = await runner.run_market_regime_analysis(
            strategy=request.strategy,
            symbol=request.symbol,
            days_back=request.days_back
        )
        
        return {
            "success": True,
            "strategy": request.strategy,
            "symbol": request.symbol,
            "period_days": request.days_back,
            "regime_analysis": regime_analysis
        }
        
    except Exception as e:
        logger.error(f"❌ Market regime analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/strategies")
async def get_available_strategies():
    """
    📋 Get list of available strategies for backtesting
    """
    strategies = [
        {
            "name": "swing_basic",
            "description": "Basic swing trading using momentum and structure",
            "risk_level": "Medium",
            "typical_win_rate": "55-65%",
            "best_market_conditions": "Trending and ranging markets"
        },
        {
            "name": "swing_aggressive",
            "description": "Aggressive swing trading with tighter entries",
            "risk_level": "High",
            "typical_win_rate": "50-60%",
            "best_market_conditions": "Volatile markets"
        },
        {
            "name": "swing_conservative",
            "description": "Conservative swing trading with safer entries",
            "risk_level": "Low",
            "typical_win_rate": "60-70%",
            "best_market_conditions": "Stable trending markets"
        },
        {
            "name": "trend_following",
            "description": "Follows market trends using moving averages",
            "risk_level": "Medium",
            "typical_win_rate": "60-70%",
            "best_market_conditions": "Trending markets"
        },
        {
            "name": "mean_reversion",
            "description": "Trades reversals from extreme levels",
            "risk_level": "Low",
            "typical_win_rate": "55-65%",
            "best_market_conditions": "Ranging markets"
        },
        {
            "name": "structure_trading",
            "description": "Trades based on market structure levels",
            "risk_level": "Medium",
            "typical_win_rate": "65-75%",
            "best_market_conditions": "All market conditions"
        }
    ]
    
    return {
        "success": True,
        "strategies": strategies
    }

@router.get("/symbols")
async def get_supported_symbols():
    """
    💰 Get ALL available trading symbols for backtesting
    """
    try:
        # Import the exchange client to get all available symbols
        from ..market_data.exchange_client import ExchangeClient
        
        exchange_client = ExchangeClient()
        
        # Get all symbols from the exchange
        exchange_info = await exchange_client.get_exchange_info()
        
        if exchange_info and 'symbols' in exchange_info:
            symbols = []
            for symbol_info in exchange_info['symbols']:
                if symbol_info['status'] == 'TRADING' and symbol_info['quoteAsset'] == 'USDT':
                    symbols.append({
                        "symbol": symbol_info['symbol'],
                        "name": symbol_info['baseAsset'],
                        "category": "Crypto"
                    })
            
            return {
                "success": True,
                "symbols": symbols[:100],  # Limit to first 100 for performance
                "total_available": len(symbols),
                "note": "All USDT trading pairs are supported for backtesting"
            }
        else:
            # Fallback to a reasonable list if exchange info fails
            fallback_symbols = [
                {"symbol": "BTCUSDT", "name": "Bitcoin", "category": "Major"},
                {"symbol": "ETHUSDT", "name": "Ethereum", "category": "Major"},
                {"symbol": "ADAUSDT", "name": "Cardano", "category": "Altcoin"},
                {"symbol": "SOLUSDT", "name": "Solana", "category": "Altcoin"},
                {"symbol": "XRPUSDT", "name": "XRP", "category": "Altcoin"},
                {"symbol": "BCHUSDT", "name": "Bitcoin Cash", "category": "Major"},
                {"symbol": "LTCUSDT", "name": "Litecoin", "category": "Major"},
                {"symbol": "DOTUSDT", "name": "Polkadot", "category": "Altcoin"},
                {"symbol": "SUNUSDT", "name": "Sun", "category": "Altcoin"},
                {"symbol": "RVNUSDT", "name": "Ravencoin", "category": "Altcoin"}
            ]
            
            return {
                "success": True,
                "symbols": fallback_symbols,
                "note": "Fallback symbol list - all symbols should work for backtesting"
            }
            
    except Exception as e:
        logger.error(f"❌ Failed to get symbols: {e}")
        
        # Return basic fallback
        return {
            "success": True,
            "symbols": [
                {"symbol": "BTCUSDT", "name": "Bitcoin", "category": "Major"},
                {"symbol": "ETHUSDT", "name": "Ethereum", "category": "Major"},
                {"symbol": "SUNUSDT", "name": "Sun", "category": "Altcoin"},
                {"symbol": "RVNUSDT", "name": "Ravencoin", "category": "Altcoin"}
            ],
            "note": "Basic fallback - all symbols should work for backtesting"
        }

@router.delete("/cleanup")
async def cleanup_old_tasks():
    """
    🧹 Clean up old completed backtest tasks
    """
    try:
        cutoff_time = datetime.now() - timedelta(hours=24)
        
        tasks_to_remove = []
        for task_id, task_info in running_backtests.items():
            completed_at = task_info.get("completed_at")
            if completed_at and completed_at < cutoff_time:
                tasks_to_remove.append(task_id)
        
        for task_id in tasks_to_remove:
            del running_backtests[task_id]
        
        return {
            "success": True,
            "cleaned_up": len(tasks_to_remove),
            "remaining_tasks": len(running_backtests)
        }
        
    except Exception as e:
        logger.error(f"❌ Cleanup failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health_check():
    """
    🏥 Health check for backtesting service
    """
    return {
        "success": True,
        "service": "backtesting",
        "status": "healthy",
        "running_tasks": len(running_backtests),
        "timestamp": datetime.now()
    } 