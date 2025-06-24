"""
Enhanced Adaptive Flow Trading Manager
Integrates ML-driven signals, dynamic grid optimization, and advanced risk management
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict, deque
import json

try:
    from .advanced_signal_generator import AdvancedSignalGenerator, MarketSignal
    from .dynamic_grid_optimizer import DynamicGridOptimizer, GridConfiguration
    from .advanced_risk_manager import AdvancedRiskManager, RiskMetrics
except ImportError:
    # For standalone testing
    from advanced_signal_generator import AdvancedSignalGenerator, MarketSignal
    from dynamic_grid_optimizer import DynamicGridOptimizer, GridConfiguration
    from advanced_risk_manager import AdvancedRiskManager, RiskMetrics
# Note: These would be imported from the existing system
# from .grid_engine import GridTradingEngine
# from .flow_risk_manager import FlowRiskManager

logger = logging.getLogger(__name__)

@dataclass
class TradingDecision:
    """Comprehensive trading decision with advanced analytics"""
    symbol: str
    action: str  # 'START_GRID', 'START_SCALPING', 'STOP', 'HOLD', 'ADJUST_GRID'
    signal: MarketSignal
    grid_config: Optional[GridConfiguration]
    position_size: float
    risk_metrics: RiskMetrics
    confidence_score: float
    expected_return: float
    max_risk: float
    reasoning: Dict[str, Any]
    timestamp: datetime

@dataclass
class PerformanceMetrics:
    """Advanced performance tracking"""
    symbol: str
    strategy_type: str
    total_trades: int
    winning_trades: int
    total_pnl: float
    max_drawdown: float
    sharpe_ratio: float
    avg_trade_duration_minutes: int
    avg_return_per_trade: float
    risk_adjusted_return: float
    last_updated: datetime

class StrategyPerformanceTracker:
    """Track and analyze strategy performance"""
    
    def __init__(self):
        self.performance_history = defaultdict(list)  # symbol -> List[PerformanceMetrics]
        self.trade_history = deque(maxlen=1000)
        self.strategy_rankings = {}
        
    def update_performance(self, symbol: str, strategy_type: str, trade_result: Dict[str, Any]):
        """Update performance metrics for a strategy"""
        try:
            # Get existing metrics or create new
            existing_metrics = self.performance_history[symbol]
            if existing_metrics:
                current = existing_metrics[-1]
            else:
                current = PerformanceMetrics(
                    symbol=symbol,
                    strategy_type=strategy_type,
                    total_trades=0,
                    winning_trades=0,
                    total_pnl=0.0,
                    max_drawdown=0.0,
                    sharpe_ratio=0.0,
                    avg_trade_duration_minutes=0,
                    avg_return_per_trade=0.0,
                    risk_adjusted_return=0.0,
                    last_updated=datetime.utcnow()
                )
            
            # Update metrics
            pnl = trade_result.get('pnl', 0)
            duration = trade_result.get('duration_minutes', 0)
            
            new_metrics = PerformanceMetrics(
                symbol=symbol,
                strategy_type=strategy_type,
                total_trades=current.total_trades + 1,
                winning_trades=current.winning_trades + (1 if pnl > 0 else 0),
                total_pnl=current.total_pnl + pnl,
                max_drawdown=min(current.max_drawdown, pnl) if pnl < 0 else current.max_drawdown,
                sharpe_ratio=self._calculate_sharpe_ratio(symbol, current.total_pnl + pnl),
                avg_trade_duration_minutes=int((current.avg_trade_duration_minutes * current.total_trades + duration) / (current.total_trades + 1)),
                avg_return_per_trade=(current.total_pnl + pnl) / (current.total_trades + 1),
                risk_adjusted_return=self._calculate_risk_adjusted_return(symbol, current.total_pnl + pnl),
                last_updated=datetime.utcnow()
            )
            
            self.performance_history[symbol].append(new_metrics)
            self.trade_history.append(trade_result)
            
            # Update strategy rankings
            self._update_strategy_rankings()
            
            logger.info(f"Updated performance for {symbol} {strategy_type}: "
                       f"PnL={new_metrics.total_pnl:.4f}, Win Rate={new_metrics.winning_trades/new_metrics.total_trades:.2%}")
            
        except Exception as e:
            logger.error(f"Error updating performance for {symbol}: {e}")
    
    def get_strategy_ranking(self, symbol: str) -> Dict[str, float]:
        """Get strategy ranking scores for a symbol"""
        return self.strategy_rankings.get(symbol, {
            'scalping_score': 0.5,
            'grid_score': 0.5,
            'recommended_strategy': 'grid'
        })
    
    def _calculate_sharpe_ratio(self, symbol: str, total_pnl: float) -> float:
        """Calculate Sharpe ratio for strategy"""
        try:
            if symbol not in self.performance_history or not self.performance_history[symbol]:
                return 0.0
            
            returns = [trade.get('pnl', 0) for trade in self.trade_history if trade.get('symbol') == symbol]
            if len(returns) < 2:
                return 0.0
            
            import numpy as np
            return_mean = np.mean(returns)
            return_std = np.std(returns)
            
            return return_mean / return_std if return_std > 0 else 0.0
            
        except Exception as e:
            logger.error(f"Error calculating Sharpe ratio: {e}")
            return 0.0
    
    def _calculate_risk_adjusted_return(self, symbol: str, total_pnl: float) -> float:
        """Calculate risk-adjusted return"""
        try:
            if symbol not in self.performance_history or not self.performance_history[symbol]:
                return 0.0
            
            metrics = self.performance_history[symbol][-1]
            if metrics.max_drawdown == 0:
                return total_pnl
            
            return total_pnl / abs(metrics.max_drawdown)
            
        except Exception as e:
            logger.error(f"Error calculating risk-adjusted return: {e}")
            return 0.0
    
    def _update_strategy_rankings(self):
        """Update strategy performance rankings"""
        try:
            for symbol in self.performance_history.keys():
                symbol_history = self.performance_history[symbol]
                if not symbol_history:
                    continue
                
                # Get recent performance for different strategies
                scalping_performance = [m for m in symbol_history if m.strategy_type == 'scalping']
                grid_performance = [m for m in symbol_history if m.strategy_type == 'grid']
                
                scalping_score = 0.5
                grid_score = 0.5
                
                if scalping_performance:
                    recent_scalping = scalping_performance[-1]
                    scalping_score = self._calculate_strategy_score(recent_scalping)
                
                if grid_performance:
                    recent_grid = grid_performance[-1]
                    grid_score = self._calculate_strategy_score(recent_grid)
                
                # Determine recommended strategy
                if scalping_score > grid_score + 0.1:  # 10% threshold
                    recommended = 'scalping'
                elif grid_score > scalping_score + 0.1:
                    recommended = 'grid'
                else:
                    recommended = 'adaptive'  # Close call, use adaptive switching
                
                self.strategy_rankings[symbol] = {
                    'scalping_score': scalping_score,
                    'grid_score': grid_score,
                    'recommended_strategy': recommended
                }
                
        except Exception as e:
            logger.error(f"Error updating strategy rankings: {e}")
    
    def _calculate_strategy_score(self, metrics: PerformanceMetrics) -> float:
        """Calculate composite strategy score"""
        try:
            if metrics.total_trades == 0:
                return 0.5
            
            # Win rate component
            win_rate = metrics.winning_trades / metrics.total_trades
            win_rate_score = win_rate
            
            # Profitability component
            profit_score = min(max(metrics.total_pnl / 100, 0), 1)  # Normalize to 0-1
            
            # Risk-adjusted return component
            risk_adj_score = min(max(metrics.risk_adjusted_return / 10, 0), 1)
            
            # Sharpe ratio component
            sharpe_score = min(max((metrics.sharpe_ratio + 1) / 3, 0), 1)  # Normalize to 0-1
            
            # Composite score
            composite_score = (win_rate_score * 0.3 + 
                             profit_score * 0.3 + 
                             risk_adj_score * 0.2 + 
                             sharpe_score * 0.2)
            
            return min(max(composite_score, 0), 1)
            
        except Exception as e:
            logger.error(f"Error calculating strategy score: {e}")
            return 0.5

class EnhancedAdaptiveManager:
    """Enhanced adaptive flow trading manager with ML integration"""
    
    def __init__(self, grid_engine, scalping_manager, 
                 exchange_client, base_risk_manager):
        self.grid_engine = grid_engine
        self.scalping_manager = scalping_manager
        self.exchange_client = exchange_client
        
        # Initialize advanced components
        self.signal_generator = AdvancedSignalGenerator(exchange_client)
        self.grid_optimizer = DynamicGridOptimizer(exchange_client)
        self.risk_manager = AdvancedRiskManager(base_risk_manager)
        # Initialize performance tracker (simplified version)
        self.performance_history = defaultdict(list)
        self.strategy_rankings = {}
        
        # Active strategies tracking
        self.active_strategies = {}  # symbol -> strategy_info
        self.active_positions = {}   # symbol -> position_info
        self.decision_history = deque(maxlen=500)
        
        # Configuration
        self.min_confidence_threshold = 0.6  # Minimum signal confidence
        self.max_concurrent_strategies = 5   # Maximum concurrent active strategies
        self.rebalance_interval_minutes = 15  # How often to reassess strategies
        self.running = False
        
        # Performance metrics
        self.total_decisions = 0
        self.successful_decisions = 0
        self.total_pnl = 0.0
        
    async def start_management(self):
        """Start the enhanced adaptive management loop"""
        self.running = True
        logger.info("🚀 Enhanced Adaptive Flow Trading Manager started")
        
        while self.running:
            try:
                await self._management_cycle()
                await asyncio.sleep(30)  # Run every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in management cycle: {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    def stop_management(self):
        """Stop the management loop"""
        self.running = False
        logger.info("🛑 Enhanced Adaptive Flow Trading Manager stopped")
    
    async def add_symbol(self, symbol: str, market_data: Dict[str, Any]):
        """Add a symbol for adaptive trading with advanced analysis"""
        try:
            if len(self.active_strategies) >= self.max_concurrent_strategies:
                logger.warning(f"Maximum concurrent strategies reached ({self.max_concurrent_strategies})")
                return False
            
            # Generate advanced market signal
            signal = await self.signal_generator.generate_advanced_signal(symbol)
            
            if signal.confidence < self.min_confidence_threshold:
                logger.info(f"Signal confidence too low for {symbol}: {signal.confidence:.2f}")
                return False
            
            # Assess portfolio risk
            risk_metrics = await self.risk_manager.assess_portfolio_risk(
                self.active_positions, {symbol: market_data}
            )
            
            # Calculate optimal position size
            position_size = await self.risk_manager.calculate_optimal_position_size(
                symbol, signal.confidence, self.active_positions, {symbol: market_data}
            )
            
            # Make trading decision
            decision = await self._make_trading_decision(symbol, signal, market_data, risk_metrics, position_size)
            
            # Execute decision
            success = await self._execute_decision(decision)
            
            if success:
                self.active_strategies[symbol] = {
                    'strategy_type': decision.action.lower().replace('start_', ''),
                    'signal': signal,
                    'grid_config': decision.grid_config,
                    'position_size': position_size,
                    'start_time': datetime.utcnow(),
                    'last_rebalance': datetime.utcnow()
                }
                
                self.decision_history.append(decision)
                self.total_decisions += 1
                
                logger.info(f"✅ Started {decision.action} for {symbol} with confidence {signal.confidence:.2f}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error adding symbol {symbol}: {e}")
            return False
    
    async def remove_symbol(self, symbol: str):
        """Remove a symbol from adaptive trading"""
        try:
            if symbol in self.active_strategies:
                strategy_info = self.active_strategies[symbol]
                
                # Stop the active strategy
                if strategy_info['strategy_type'] == 'grid':
                    await self.grid_engine.stop_grid(symbol, "manual_removal")
                elif strategy_info['strategy_type'] == 'scalping':
                    # Stop scalping (would implement in scalping manager)
                    pass
                
                # Calculate final performance
                start_time = strategy_info['start_time']
                duration = (datetime.utcnow() - start_time).total_seconds() / 60
                
                # Update performance tracking
                trade_result = {
                    'symbol': symbol,
                    'strategy_type': strategy_info['strategy_type'],
                    'duration_minutes': duration,
                    'pnl': 0.0,  # Would calculate actual P&L
                    'confidence': strategy_info['signal'].confidence,
                    'end_reason': 'manual_removal'
                }
                
                # Update performance tracking (simplified)
                if symbol not in self.performance_history:
                    self.performance_history[symbol] = []
                self.performance_history[symbol].append(trade_result)
                
                # Remove from active tracking
                del self.active_strategies[symbol]
                if symbol in self.active_positions:
                    del self.active_positions[symbol]
                
                logger.info(f"🛑 Removed {symbol} from adaptive trading")
                
        except Exception as e:
            logger.error(f"Error removing symbol {symbol}: {e}")
    
    async def _management_cycle(self):
        """Main management cycle - reassess and rebalance strategies"""
        try:
            if not self.active_strategies:
                return
            
            logger.debug(f"Running management cycle for {len(self.active_strategies)} active strategies")
            
            for symbol in list(self.active_strategies.keys()):
                await self._reassess_strategy(symbol)
            
            # Portfolio-level rebalancing
            await self._rebalance_portfolio()
            
        except Exception as e:
            logger.error(f"Error in management cycle: {e}")
    
    async def _reassess_strategy(self, symbol: str):
        """Reassess and potentially adjust strategy for a symbol"""
        try:
            strategy_info = self.active_strategies[symbol]
            
            # Check if it's time for rebalancing
            time_since_rebalance = datetime.utcnow() - strategy_info['last_rebalance']
            if time_since_rebalance.total_seconds() < self.rebalance_interval_minutes * 60:
                return
            
            # Get fresh market data
            market_data = await self._get_market_data(symbol)
            if not market_data:
                return
            
            # Generate new signal
            new_signal = await self.signal_generator.generate_advanced_signal(symbol)
            
            # Get strategy performance ranking
            ranking = self.performance_tracker.get_strategy_ranking(symbol)
            current_strategy = strategy_info['strategy_type']
            
            # Decide if strategy change is needed
            should_change = await self._should_change_strategy(
                symbol, current_strategy, new_signal, ranking, market_data
            )
            
            if should_change:
                # Execute strategy change
                await self._change_strategy(symbol, new_signal, market_data)
            else:
                # Update existing strategy parameters
                await self._update_strategy_parameters(symbol, new_signal, market_data)
            
            strategy_info['last_rebalance'] = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Error reassessing strategy for {symbol}: {e}")
    
    async def _make_trading_decision(self, symbol: str, signal: MarketSignal, 
                                   market_data: Dict[str, Any], risk_metrics: RiskMetrics, 
                                   position_size: float) -> TradingDecision:
        """Make comprehensive trading decision using all available information"""
        try:
            # Get strategy performance ranking
            ranking = self.performance_tracker.get_strategy_ranking(symbol)
            
            # Determine optimal action based on signal and market conditions
            if signal.signal_type == 'GRID_OPTIMAL':
                action = 'START_GRID'
                # Generate optimized grid configuration
                grid_config = await self.grid_optimizer.optimize_grid_configuration(symbol, market_data)
            elif signal.signal_type in ['BUY', 'SELL']:
                action = 'START_SCALPING'
                grid_config = None
            else:  # HOLD
                action = 'HOLD'
                grid_config = None
            
            # Override based on strategy ranking if available
            if ranking['recommended_strategy'] == 'scalping' and action == 'START_GRID':
                action = 'START_SCALPING'
                grid_config = None
            elif ranking['recommended_strategy'] == 'grid' and action == 'START_SCALPING':
                action = 'START_GRID'
                grid_config = await self.grid_optimizer.optimize_grid_configuration(symbol, market_data)
            
            # Calculate expected return and risk
            expected_return = signal.target_profit_pct * signal.confidence
            max_risk = signal.stop_loss_pct
            
            # Confidence score combining signal confidence and strategy ranking
            strategy_score = ranking.get(f"{action.lower().replace('start_', '')}_score", 0.5)
            confidence_score = (signal.confidence * 0.7 + strategy_score * 0.3)
            
            # Create comprehensive reasoning
            reasoning = {
                'signal_reasoning': signal.reasoning,
                'risk_assessment': risk_metrics.__dict__,
                'strategy_ranking': ranking,
                'market_regime': market_data.get('market_regime', 'unknown'),
                'position_sizing_factors': {
                    'base_size': position_size,
                    'signal_confidence': signal.confidence,
                    'risk_adjustment': risk_metrics.portfolio_var_1d
                }
            }
            
            return TradingDecision(
                symbol=symbol,
                action=action,
                signal=signal,
                grid_config=grid_config,
                position_size=position_size,
                risk_metrics=risk_metrics,
                confidence_score=confidence_score,
                expected_return=expected_return,
                max_risk=max_risk,
                reasoning=reasoning,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Error making trading decision for {symbol}: {e}")
            # Return default HOLD decision
            return TradingDecision(
                symbol=symbol,
                action='HOLD',
                signal=signal,
                grid_config=None,
                position_size=0.0,
                risk_metrics=risk_metrics,
                confidence_score=0.0,
                expected_return=0.0,
                max_risk=0.0,
                reasoning={'error': str(e)},
                timestamp=datetime.utcnow()
            )
    
    async def _execute_decision(self, decision: TradingDecision) -> bool:
        """Execute a trading decision"""
        try:
            if decision.action == 'START_GRID':
                if decision.grid_config:
                    # Mock market data for grid engine
                    mock_market_data = {
                        'symbol': decision.symbol,
                        'klines': [{'close': '50000'}],
                        'indicators': {'atr': 500}
                    }
                    
                    success = await self.grid_engine.start_grid(
                        decision.symbol, 
                        mock_market_data,
                        {
                            'levels': decision.grid_config.upper_levels + decision.grid_config.lower_levels,
                            'spacing_multiplier': decision.grid_config.spacing_multiplier,
                            'position_size_usd': decision.position_size * 1000  # Convert to USD
                        }
                    )
                    return success
                else:
                    logger.error(f"No grid configuration for {decision.symbol}")
                    return False
                    
            elif decision.action == 'START_SCALPING':
                # Start scalping strategy
                # This would integrate with the scalping manager
                logger.info(f"Starting scalping for {decision.symbol}")
                return True
                
            elif decision.action == 'HOLD':
                logger.info(f"Holding position for {decision.symbol}")
                return True
                
            else:
                logger.warning(f"Unknown action: {decision.action}")
                return False
                
        except Exception as e:
            logger.error(f"Error executing decision for {decision.symbol}: {e}")
            return False
    
    async def _should_change_strategy(self, symbol: str, current_strategy: str, 
                                    new_signal: MarketSignal, ranking: Dict[str, float], 
                                    market_data: Dict[str, Any]) -> bool:
        """Determine if strategy should be changed"""
        try:
            # Signal-based change
            if new_signal.signal_type == 'GRID_OPTIMAL' and current_strategy != 'grid':
                return new_signal.confidence > 0.8  # High confidence required for change
            
            if new_signal.signal_type in ['BUY', 'SELL'] and current_strategy != 'scalping':
                return new_signal.confidence > 0.8
            
            # Performance-based change
            recommended = ranking['recommended_strategy']
            if recommended != current_strategy and recommended != 'adaptive':
                current_score = ranking.get(f'{current_strategy}_score', 0.5)
                recommended_score = ranking.get(f'{recommended}_score', 0.5)
                
                # Change if recommended strategy significantly outperforms
                return recommended_score > current_score + 0.2
            
            return False
            
        except Exception as e:
            logger.error(f"Error determining strategy change for {symbol}: {e}")
            return False
    
    async def _change_strategy(self, symbol: str, new_signal: MarketSignal, market_data: Dict[str, Any]):
        """Change strategy for a symbol"""
        try:
            logger.info(f"🔄 Changing strategy for {symbol} based on new signal: {new_signal.signal_type}")
            
            # Stop current strategy
            await self.remove_symbol(symbol)
            
            # Start new strategy
            await self.add_symbol(symbol, market_data)
            
        except Exception as e:
            logger.error(f"Error changing strategy for {symbol}: {e}")
    
    async def _update_strategy_parameters(self, symbol: str, new_signal: MarketSignal, 
                                        market_data: Dict[str, Any]):
        """Update parameters of existing strategy"""
        try:
            strategy_info = self.active_strategies[symbol]
            
            if strategy_info['strategy_type'] == 'grid':
                # Update grid parameters if needed
                if new_signal.confidence > 0.8:  # High confidence for parameter updates
                    new_grid_config = await self.grid_optimizer.optimize_grid_configuration(symbol, market_data)
                    
                    # Compare with current configuration and update if significantly different
                    current_config = strategy_info['grid_config']
                    if self._should_update_grid_config(current_config, new_grid_config):
                        # Stop and restart grid with new configuration
                        await self.grid_engine.stop_grid(symbol, "parameter_update")
                        
                        mock_market_data = {
                            'symbol': symbol,
                            'klines': [{'close': '50000'}],
                            'indicators': {'atr': 500}
                        }
                        
                        await self.grid_engine.start_grid(symbol, mock_market_data, {
                            'levels': new_grid_config.upper_levels + new_grid_config.lower_levels,
                            'spacing_multiplier': new_grid_config.spacing_multiplier,
                            'position_size_usd': strategy_info['position_size'] * 1000
                        })
                        
                        strategy_info['grid_config'] = new_grid_config
                        logger.info(f"📊 Updated grid configuration for {symbol}")
            
            # Update signal information
            strategy_info['signal'] = new_signal
            
        except Exception as e:
            logger.error(f"Error updating strategy parameters for {symbol}: {e}")
    
    def _should_update_grid_config(self, current: GridConfiguration, new: GridConfiguration) -> bool:
        """Determine if grid configuration should be updated"""
        if not current or not new:
            return True
        
        # Check for significant changes
        spacing_change = abs(current.spacing_multiplier - new.spacing_multiplier) / current.spacing_multiplier
        levels_change = abs((current.upper_levels + current.lower_levels) - (new.upper_levels + new.lower_levels))
        
        return spacing_change > 0.2 or levels_change > 2  # 20% spacing change or 2+ level change
    
    async def _rebalance_portfolio(self):
        """Perform portfolio-level rebalancing"""
        try:
            if not self.active_strategies:
                return
            
            # Assess overall portfolio risk
            risk_metrics = await self.risk_manager.assess_portfolio_risk(
                self.active_positions, {}
            )
            
            # Check risk limits
            if risk_metrics.portfolio_var_1d > self.risk_manager.max_portfolio_var:
                logger.warning(f"⚠️ Portfolio VaR exceeded: {risk_metrics.portfolio_var_1d:.4f}")
                await self._reduce_portfolio_risk()
            
            # Check correlation concentration
            if risk_metrics.correlation_concentration > self.risk_manager.max_correlation_concentration:
                logger.warning(f"⚠️ Correlation concentration too high: {risk_metrics.correlation_concentration:.4f}")
                await self._reduce_correlation_risk()
            
        except Exception as e:
            logger.error(f"Error in portfolio rebalancing: {e}")
    
    async def _reduce_portfolio_risk(self):
        """Reduce portfolio risk by stopping worst-performing strategies"""
        try:
            # Sort strategies by performance
            strategy_performance = []
            for symbol, strategy_info in self.active_strategies.items():
                ranking = self.performance_tracker.get_strategy_ranking(symbol)
                current_strategy = strategy_info['strategy_type']
                score = ranking.get(f'{current_strategy}_score', 0.5)
                strategy_performance.append((symbol, score))
            
            # Sort by score (ascending - worst first)
            strategy_performance.sort(key=lambda x: x[1])
            
            # Stop worst performing strategy
            if strategy_performance:
                worst_symbol = strategy_performance[0][0]
                logger.info(f"🛑 Stopping worst performing strategy: {worst_symbol}")
                await self.remove_symbol(worst_symbol)
                
        except Exception as e:
            logger.error(f"Error reducing portfolio risk: {e}")
    
    async def _reduce_correlation_risk(self):
        """Reduce correlation risk by stopping most correlated strategies"""
        try:
            # This would implement correlation-based strategy stopping
            # For now, stop the most recent strategy
            if self.active_strategies:
                most_recent = max(self.active_strategies.items(), 
                                key=lambda x: x[1]['start_time'])
                symbol = most_recent[0]
                logger.info(f"🛑 Stopping most recent strategy to reduce correlation: {symbol}")
                await self.remove_symbol(symbol)
                
        except Exception as e:
            logger.error(f"Error reducing correlation risk: {e}")
    
    async def _get_market_data(self, symbol: str) -> Dict[str, Any]:
        """Get fresh market data for a symbol"""
        try:
            # Mock market data - replace with real data fetching
            return {
                'symbol': symbol,
                'klines': [{'close': '50000', 'volume': '1000'}] * 100,
                'indicators': {'atr': 500},
                'market_regime': 'ranging'
            }
        except Exception as e:
            logger.error(f"Error getting market data for {symbol}: {e}")
            return {}
    
    def get_all_strategies_status(self) -> List[Dict[str, Any]]:
        """Get status of all active strategies"""
        try:
            status_list = []
            
            for symbol, strategy_info in self.active_strategies.items():
                uptime = (datetime.utcnow() - strategy_info['start_time']).total_seconds() / 60
                ranking = self.performance_tracker.get_strategy_ranking(symbol)
                
                status = {
                    'symbol': symbol,
                    'current_strategy': strategy_info['strategy_type'],
                    'market_regime': strategy_info['signal'].reasoning.get('volatility_regime', 'unknown'),
                    'last_switch': strategy_info['start_time'].timestamp(),
                    'switch_count': 1,  # Would track actual switches
                    'performance_score': ranking.get(f"{strategy_info['strategy_type']}_score", 0.0),
                    'uptime_minutes': uptime,
                    'confidence': strategy_info['signal'].confidence,
                    'position_size': strategy_info['position_size']
                }
                
                status_list.append(status)
            
            return status_list
            
        except Exception as e:
            logger.error(f"Error getting strategies status: {e}")
            return []
    
    def get_strategy_status(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get status for a specific strategy"""
        try:
            if symbol not in self.active_strategies:
                return None
            
            strategy_info = self.active_strategies[symbol]
            uptime = (datetime.utcnow() - strategy_info['start_time']).total_seconds() / 60
            ranking = self.performance_tracker.get_strategy_ranking(symbol)
            
            return {
                'symbol': symbol,
                'current_strategy': strategy_info['strategy_type'],
                'market_regime': strategy_info['signal'].reasoning.get('volatility_regime', 'unknown'),
                'last_switch': strategy_info['start_time'].timestamp(),
                'switch_count': 1,
                'performance_score': ranking.get(f"{strategy_info['strategy_type']}_score", 0.0),
                'uptime_minutes': uptime,
                'confidence': strategy_info['signal'].confidence,
                'position_size': strategy_info['position_size'],
                'signal_details': strategy_info['signal'].__dict__,
                'grid_config': strategy_info['grid_config'].__dict__ if strategy_info['grid_config'] else None
            }
            
        except Exception as e:
            logger.error(f"Error getting strategy status for {symbol}: {e}")
            return None
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get overall performance summary"""
        try:
            return {
                'total_decisions': self.total_decisions,
                'successful_decisions': self.successful_decisions,
                'success_rate': self.successful_decisions / self.total_decisions if self.total_decisions > 0 else 0,
                'total_pnl': self.total_pnl,
                'active_strategies': len(self.active_strategies),
                'decision_history_length': len(self.decision_history),
                'strategy_rankings': dict(self.performance_tracker.strategy_rankings)
            }
            
        except Exception as e:
            logger.error(f"Error getting performance summary: {e}")
            return {} 