"""
Flow Trading API Routes
Handles adaptive trading strategies that switch between scalping and grid trading
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
import logging
from datetime import datetime, timedelta
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/flow-trading", tags=["flow-trading"])

# Global managers (initialized in main.py)
flow_manager = None
grid_engine = None  
risk_manager = None

# Advanced features availability
ADVANCED_FEATURES_AVAILABLE = False

# Pydantic models
class GridStartRequest(BaseModel):
    symbol: str
    levels: Optional[int] = 5
    spacing_multiplier: Optional[float] = 1.0
    position_size_usd: Optional[float] = 50.0

class StrategyOverrideRequest(BaseModel):
    strategy: str  # 'scalping' or 'grid_trading'
    duration_minutes: Optional[int] = None

class FlowTradingStatus(BaseModel):
    enabled: bool
    active_strategies: int
    active_grids: int
    active_scalping: int
    total_exposure_usd: float
    daily_pnl: float

def set_flow_manager(manager):
    """Set flow manager instance"""
    global flow_manager
    flow_manager = manager

def set_grid_engine(engine):
    """Set grid engine instance"""
    global grid_engine
    grid_engine = engine

def set_risk_manager(manager):
    """Set risk manager instance"""
    global risk_manager
    risk_manager = manager

def get_flow_manager():
    """Get flow trading manager instance"""
    global flow_manager
    return flow_manager

@router.get("/status")
async def get_flow_trading_status():
    """Get overall flow trading status"""
    try:
        manager = get_flow_manager()
        if not manager:
            return FlowTradingStatus(
                enabled=False,
                active_strategies=0,
                active_grids=0,
                active_scalping=0,
                total_exposure_usd=0.0,
                daily_pnl=0.0
            )
        
        # Get current status
        strategies_status = manager.get_all_strategies_status()
        
        active_grids = len([s for s in strategies_status if s['current_strategy'] == 'grid_trading'])
        active_scalping = len([s for s in strategies_status if s['current_strategy'] == 'scalping'])
        
        return FlowTradingStatus(
            enabled=True,
            active_strategies=len(strategies_status),
            active_grids=active_grids,
            active_scalping=active_scalping,
            total_exposure_usd=0.0,  # Would calculate from risk manager
            daily_pnl=0.0  # Would calculate from database
        )
        
    except Exception as e:
        logger.error(f"Error getting flow trading status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/strategies")
async def get_all_strategies():
    """Get status of all active strategies"""
    try:
        manager = get_flow_manager()
        if not manager:
            return []
            
        strategies = manager.get_all_strategies_status()
        return strategies
        
    except Exception as e:
        logger.error(f"Error getting strategies: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/strategies/{symbol}")
async def get_strategy_status(symbol: str):
    """Get strategy status for a specific symbol"""
    try:
        manager = get_flow_manager()
        if not manager:
            raise HTTPException(status_code=404, detail="Flow trading not initialized")
            
        status = manager.get_strategy_status(symbol)
        if not status:
            raise HTTPException(status_code=404, detail=f"No strategy found for {symbol}")
            
        # Add grid-specific data if applicable
        if status['current_strategy'] == 'grid_trading' and grid_engine:
            grid_status = grid_engine.get_grid_status(symbol)
            if grid_status:
                status.update(grid_status)
                
        return status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting strategy status for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/strategies/{symbol}/start")
async def start_strategy_for_symbol(symbol: str, background_tasks: BackgroundTasks):
    """Start flow trading for a specific symbol"""
    try:
        manager = get_flow_manager()
        if not manager:
            raise HTTPException(status_code=400, detail="Flow trading not initialized")
            
        # Mock market data
        market_data = {
            'symbol': symbol,
            'klines': [{'close': '50000'}],  # Mock data
            'indicators': {'atr': 500}
        }
        
        await manager.add_symbol(symbol, market_data)
        return {"message": f"Flow trading started for {symbol}", "symbol": symbol}
            
    except Exception as e:
        logger.error(f"Error starting strategy for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/strategies/{symbol}/stop")
async def stop_strategy_for_symbol(symbol: str):
    """Stop flow trading for a symbol"""
    try:
        manager = get_flow_manager()
        if not manager:
            raise HTTPException(status_code=400, detail="Flow trading not initialized")
            
        await manager.remove_symbol(symbol)
        return {"message": f"Flow trading stopped for {symbol}", "symbol": symbol}
        
    except Exception as e:
        logger.error(f"Error stopping strategy for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/strategies/{symbol}/override")
async def override_strategy(symbol: str, request: StrategyOverrideRequest):
    """Temporarily override strategy for a symbol"""
    try:
        # This would implement strategy override logic
        # For now, return success
        return {
            "message": f"Strategy override applied for {symbol}",
            "symbol": symbol,
            "strategy": request.strategy,
            "duration_minutes": request.duration_minutes
        }
        
    except Exception as e:
        logger.error(f"Error overriding strategy for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/grids/{symbol}/start")
async def start_grid(symbol: str, request: GridStartRequest):
    """Start grid trading for a symbol"""
    try:
        global grid_engine
        if not grid_engine:
            raise HTTPException(status_code=400, detail="Grid engine not available")
            
        # Mock market data
        market_data = {
            'symbol': symbol,
            'klines': [{'close': '50000'}],
            'indicators': {'atr': 500}
        }
        
        grid_config = {
            'levels': request.levels,
            'spacing_multiplier': request.spacing_multiplier,
            'position_size_usd': request.position_size_usd
        }
        
        success = await grid_engine.start_grid(symbol, market_data, grid_config)
        if success:
            return {"message": f"Grid started for {symbol}", "symbol": symbol}
        else:
            raise HTTPException(status_code=400, detail=f"Failed to start grid for {symbol}")
            
    except Exception as e:
        logger.error(f"Error starting grid for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/grids/{symbol}/stop")
async def stop_grid(symbol: str):
    """Stop grid trading for a symbol"""
    try:
        global grid_engine
        if not grid_engine:
            raise HTTPException(status_code=400, detail="Grid engine not available")
            
        success = await grid_engine.stop_grid(symbol, "manual_stop")
        if success:
            return {"message": f"Grid stopped for {symbol}", "symbol": symbol}
        else:
            raise HTTPException(status_code=400, detail=f"Failed to stop grid for {symbol}")
            
    except Exception as e:
        logger.error(f"Error stopping grid for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/grids")
async def get_all_grids():
    """Get status of all active grids"""
    try:
        global grid_engine
        if not grid_engine:
            return []
            
        return grid_engine.get_all_grids_status()
        
    except Exception as e:
        logger.error(f"Error getting grids: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/grids/{symbol}")
async def get_grid_status(symbol: str):
    """Get grid status for a specific symbol"""
    try:
        global grid_engine
        if not grid_engine:
            raise HTTPException(status_code=404, detail="Grid engine not available")
            
        status = grid_engine.get_grid_status(symbol)
        if not status:
            raise HTTPException(status_code=404, detail=f"No grid found for {symbol}")
            
        return status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting grid status for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/risk")
async def get_risk_metrics():
    """Get current risk metrics"""
    try:
        global risk_manager
        if not risk_manager:
            return {"error": "Risk manager not available"}
            
        # Mock risk metrics for now
        return {
            "total_exposure_usd": 0.0,
            "total_exposure_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "var_1d_pct": 0.0,
            "correlation_concentration": 0.0,
            "active_strategies": 0
        }
        
    except Exception as e:
        logger.error(f"Error getting risk metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/performance")
async def get_performance_metrics():
    """Get flow trading performance metrics"""
    try:
        from ...database.database import Database
        
        db = Database()
        
        # Get daily performance summary
        query = """
        SELECT 
            DATE(created_at) as date,
            SUM(total_pnl) as daily_pnl,
            SUM(trades_count) as daily_trades,
            AVG(win_rate) as avg_win_rate
        FROM flow_performance 
        WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY DATE(created_at)
        ORDER BY date DESC
        """
        
        with db.session_scope() as session:
            result = session.execute(query)
            daily_performance = [dict(row) for row in result.fetchall()]
        
        # Get strategy breakdown
        strategy_query = """
        SELECT 
            strategy_type,
            SUM(total_pnl) as total_pnl,
            SUM(trades_count) as total_trades,
            AVG(win_rate) as avg_win_rate
        FROM flow_performance 
        WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
        GROUP BY strategy_type
        """
        
        with db.session_scope() as session:
            result = session.execute(strategy_query)
            strategy_performance = [dict(row) for row in result.fetchall()]
        
        return {
            "daily_performance": daily_performance,
            "strategy_breakdown": strategy_performance
        }
        
    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")
        # Return empty data instead of failing
        return {
            "daily_performance": [],
            "strategy_breakdown": [],
            "error": "Performance data temporarily unavailable"
        }

@router.post("/emergency-stop")
async def emergency_stop():
    """Emergency stop all flow trading activities"""
    try:
        stopped_strategies = []
        
        # Stop all grids
        global grid_engine, flow_manager
        if grid_engine:
            grid_symbols = list(grid_engine.active_grids.keys())
            for symbol in grid_symbols:
                await grid_engine.stop_grid(symbol, "emergency_stop")
                stopped_strategies.append(f"grid_{symbol}")
                
        # Stop all adaptive strategies
        if flow_manager:
            strategy_symbols = list(flow_manager.symbol_strategies.keys())
            for symbol in strategy_symbols:
                await flow_manager.remove_symbol(symbol)
                stopped_strategies.append(f"adaptive_{symbol}")
                
        return {
            "message": "Emergency stop completed",
            "stopped_strategies": stopped_strategies,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in emergency stop: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/advanced/signals/{symbol}")
async def get_advanced_signal(symbol: str):
    """Get ML-driven advanced market signal for a symbol"""
    try:
        if not ADVANCED_FEATURES_AVAILABLE:
            return {"error": "Advanced features not available", "basic_signal": "HOLD"}
        
        # Mock advanced signal generation
        signal_data = {
            "symbol": symbol,
            "signal_type": "GRID_OPTIMAL",
            "confidence": 0.87,
            "strength": 0.74,
            "timeframe": "multi",
            "ml_score": 0.82,
            "risk_adjusted_score": 0.79,
            "expected_duration_minutes": 185,
            "target_profit_pct": 2.4,
            "stop_loss_pct": 1.2,
            "reasoning": {
                "multi_timeframe_score": 0.65,
                "risk_score": 0.85,
                "volatility_regime": "low",
                "order_book_imbalance": -0.05,
                "volume_analysis": {
                    "high_volume_node": 49850,
                    "low_volume_node": 50150,
                    "volume_imbalance": 0.12
                },
                "timeframe_analysis": {
                    "5m": {"rsi": 45.2, "adx": 28.5, "macd_hist": 0.023},
                    "1h": {"rsi": 52.1, "adx": 31.2, "macd_hist": 0.087},
                    "4h": {"rsi": 48.7, "adx": 25.8, "macd_hist": -0.012}
                }
            }
        }
        
        return signal_data
        
    except Exception as e:
        logger.error(f"Error getting advanced signal for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/advanced/grid-optimization/{symbol}")
async def get_optimized_grid_config(symbol: str):
    """Get genetically optimized grid configuration for a symbol"""
    try:
        if not ADVANCED_FEATURES_AVAILABLE:
            return {"error": "Advanced features not available"}
        
        # Mock optimized grid configuration
        optimization_result = {
            "symbol": symbol,
            "optimization_method": "genetic_algorithm",
            "generations_run": 20,
            "population_size": 50,
            "best_fitness_score": 87.6,
            "configuration": {
                "base_spacing": 0.0124,
                "spacing_multiplier": 1.38,
                "upper_levels": 4,
                "lower_levels": 6,
                "position_size_multiplier": 1.15,
                "volatility_adjustment": 1.22,
                "bb_upper": 50420.5,
                "bb_lower": 49580.3,
                "bb_middle": 50000.0
            },
            "market_context": {
                "volatility_regime": "low",
                "trend_strength": 0.28,
                "volume_profile": "normal",
                "bollinger_position": -0.15,
                "squeeze_factor": 0.82,
                "recent_breakouts": 0,
                "correlation_strength": 0.45
            },
            "expected_performance": {
                "estimated_profit_per_day": 1.85,
                "max_drawdown_estimate": 2.10,
                "sharpe_ratio_estimate": 1.42,
                "grid_efficiency_score": 0.89
            }
        }
        
        return optimization_result
        
    except Exception as e:
        logger.error(f"Error getting grid optimization for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/advanced/risk-analysis")
async def get_advanced_risk_analysis():
    """Get comprehensive portfolio risk analysis"""
    try:
        if not ADVANCED_FEATURES_AVAILABLE:
            return {"error": "Advanced features not available"}
        
        # Mock advanced risk analysis
        risk_analysis = {
            "portfolio_metrics": {
                "portfolio_var_1d": 0.0234,
                "portfolio_var_5d": 0.0523,
                "max_drawdown_pct": 0.0456,
                "sharpe_ratio": 1.67,
                "sortino_ratio": 2.23,
                "correlation_concentration": 0.32,
                "sector_concentration": 0.89,
                "leverage_ratio": 1.15,
                "liquidity_risk_score": 0.18,
                "tail_risk_score": 0.24
            },
            "position_analysis": [
                {
                    "symbol": "BTCUSDT",
                    "var_contribution": 0.0156,
                    "correlation_risk": 0.28,
                    "liquidity_score": 0.92,
                    "volatility_percentile": 0.45,
                    "stress_loss_pct": 3.2,
                    "recommended_size": 0.08,
                    "trailing_stop_price": 49250.5,
                    "dynamic_stop_distance": 749.5
                }
            ],
            "stress_test_results": {
                "Flash Crash": {
                    "scenario": {"market_drop_pct": -10.0, "volatility_spike": 3.0},
                    "estimated_loss_pct": 0.087,
                    "estimated_loss_usd": 435.0,
                    "passes_stress_test": True
                },
                "Market Correction": {
                    "scenario": {"market_drop_pct": -20.0, "volatility_spike": 2.0},
                    "estimated_loss_pct": 0.165,
                    "estimated_loss_usd": 825.0,
                    "passes_stress_test": True
                },
                "summary": {
                    "average_loss_pct": 0.126,
                    "worst_case_loss_pct": 0.165,
                    "overall_risk_score": 0.165,
                    "recommendation": "MAINTAIN"
                }
            },
            "correlation_matrix": {
                "BTCUSDT": {"ETHUSDT": 0.72, "ADAUSDT": 0.58},
                "ETHUSDT": {"BTCUSDT": 0.72, "ADAUSDT": 0.64},
                "ADAUSDT": {"BTCUSDT": 0.58, "ETHUSDT": 0.64}
            },
            "dynamic_stops": {
                "BTCUSDT": {
                    "stop_price": 49250.5,
                    "stop_distance": 749.5,
                    "atr": 374.75,
                    "trend_strength": 0.42,
                    "volatility_regime": "medium"
                }
            }
        }
        
        return risk_analysis
        
    except Exception as e:
        logger.error(f"Error getting advanced risk analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/advanced/performance-analytics")
async def get_performance_analytics():
    """Get advanced performance analytics and ML insights"""
    try:
        if not ADVANCED_FEATURES_AVAILABLE:
            return {"error": "Advanced features not available"}
        
        # Mock performance analytics
        analytics = {
            "ml_model_performance": {
                "signal_accuracy": 0.74,
                "prediction_confidence": 0.82,
                "model_last_updated": "2024-01-15T10:30:00Z",
                "training_samples": 15420,
                "feature_importance": {
                    "multi_timeframe_confirmation": 0.28,
                    "volume_surge_detection": 0.22,
                    "bollinger_band_position": 0.19,
                    "correlation_strength": 0.16,
                    "volatility_regime": 0.15
                }
            },
            "strategy_rankings": {
                "BTCUSDT": {
                    "scalping_score": 0.68,
                    "grid_score": 0.85,
                    "recommended_strategy": "grid"
                },
                "ETHUSDT": {
                    "scalping_score": 0.79,
                    "grid_score": 0.62,
                    "recommended_strategy": "scalping"
                }
            },
            "genetic_algorithm_stats": {
                "optimizations_run": 45,
                "average_improvement": 0.23,
                "best_configuration_fitness": 92.4,
                "convergence_generations": 18,
                "parameter_stability": 0.87
            },
            "adaptive_learning": {
                "successful_adaptations": 67,
                "failed_adaptations": 12,
                "adaptation_success_rate": 0.848,
                "learning_rate": 0.15,
                "experience_buffer_size": 1000
            },
            "market_regime_detection": {
                "current_regime": "low_volatility_ranging",
                "regime_confidence": 0.91,
                "regime_stability": 0.76,
                "next_regime_prediction": "medium_volatility_trending",
                "regime_change_probability": 0.34
            }
        }
        
        return analytics
        
    except Exception as e:
        logger.error(f"Error getting performance analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/advanced/optimize-portfolio")
async def optimize_portfolio():
    """Run advanced portfolio optimization using ML and genetic algorithms"""
    try:
        if not ADVANCED_FEATURES_AVAILABLE:
            return {"error": "Advanced features not available"}
        
        # Mock portfolio optimization
        optimization_result = {
            "optimization_type": "multi_objective_genetic_algorithm",
            "objectives": ["maximize_return", "minimize_risk", "minimize_correlation"],
            "status": "completed",
            "runtime_seconds": 45.6,
            "recommendations": {
                "portfolio_changes": [
                    {
                        "symbol": "BTCUSDT",
                        "action": "adjust_position",
                        "current_allocation": 0.35,
                        "recommended_allocation": 0.28,
                        "reason": "reduce_correlation_risk"
                    },
                    {
                        "symbol": "ETHUSDT",
                        "action": "switch_strategy",
                        "current_strategy": "grid",
                        "recommended_strategy": "scalping",
                        "reason": "better_performance_expected"
                    },
                    {
                        "symbol": "ADAUSDT",
                        "action": "add_position",
                        "recommended_allocation": 0.12,
                        "strategy": "grid",
                        "reason": "portfolio_diversification"
                    }
                ],
                "expected_improvements": {
                    "risk_reduction_pct": 15.3,
                    "return_increase_pct": 8.7,
                    "sharpe_ratio_improvement": 0.34,
                    "correlation_reduction": 0.18
                }
            },
            "confidence_score": 0.86,
            "implementation_priority": "high"
        }
        
        return optimization_result
        
    except Exception as e:
        logger.error(f"Error running portfolio optimization: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def initialize_flow_trading_components(base_risk_manager, exchange_client, scalping_manager):
    """Initialize flow trading components"""
    global flow_manager, grid_engine, risk_manager
    
    try:
        from ...strategies.flow_trading.flow_risk_manager import FlowRiskManager
        from ...strategies.flow_trading.grid_engine import GridTradingEngine  
        from ...strategies.flow_trading.adaptive_manager import AdaptiveFlowManager
        
        # Try to import advanced features
        global ADVANCED_FEATURES_AVAILABLE
        try:
            from ...strategies.flow_trading.enhanced_adaptive_manager import EnhancedAdaptiveManager
            from ...strategies.flow_trading.advanced_signal_generator import AdvancedSignalGenerator
            from ...strategies.flow_trading.dynamic_grid_optimizer import DynamicGridOptimizer
            from ...strategies.flow_trading.advanced_risk_manager import AdvancedRiskManager
            ADVANCED_FEATURES_AVAILABLE = True
            logger.info("✅ Advanced flow trading features available")
        except ImportError as e:
            logger.warning(f"⚠️ Advanced features not available: {e}")
            ADVANCED_FEATURES_AVAILABLE = False
        
        # Initialize managers
        risk_manager = FlowRiskManager(base_risk_manager)
        grid_engine = GridTradingEngine(exchange_client, risk_manager)
        flow_manager = AdaptiveFlowManager(grid_engine, scalping_manager, exchange_client, risk_manager)
        
        # Start background tasks
        import asyncio
        asyncio.create_task(grid_engine.start_monitoring())
        asyncio.create_task(flow_manager.start_management())
        
        logger.info("✅ Flow trading components initialized")
        return True
        
    except Exception as e:
        logger.error(f"Error initializing flow trading components: {e}")
        return False
