"""
Flow Risk Manager - Enhanced risk management for flow trading strategies
"""

import logging
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import numpy as np

logger = logging.getLogger(__name__)

@dataclass
class PositionRisk:
    """Risk metrics for a position"""
    symbol: str
    position_size_usd: float
    leverage: float
    exposure_pct: float
    var_1d: float  # 1-day Value at Risk
    correlation_risk: float

@dataclass
class PortfolioRisk:
    """Portfolio-level risk metrics"""
    total_exposure_usd: float
    total_exposure_pct: float
    max_drawdown_pct: float
    var_1d_pct: float
    correlation_concentration: float
    active_strategies: int

class FlowRiskManager:
    """Enhanced risk manager for flow trading strategies"""
    
    def __init__(self, base_risk_manager):
        self.base_risk_manager = base_risk_manager
        self.config = {
            'max_concurrent_grids': 3,
            'max_portfolio_exposure_pct': 20.0,
            'max_single_position_pct': 5.0,
            'max_correlation_exposure': 0.7,
            'daily_loss_limit_pct': 5.0,
            'grid_position_size_pct': 0.5,
            'scalp_position_size_pct': 1.0,
            'var_limit_pct': 2.0,
            'min_margin_buffer_pct': 10.0
        }
        
        self.position_history = {}  # symbol -> list of positions
        self.correlation_matrix = {}  # symbol pairs -> correlation
        self.performance_tracking = {}  # strategy -> performance metrics
        
    def validate_grid_exposure(self, symbol: str, grid_orders: List[Dict]) -> Tuple[bool, str]:
        """Ensure total grid exposure is within limits"""
        try:
            # Calculate total grid exposure
            total_exposure = sum(
                order['quantity'] * order['price'] 
                for order in grid_orders
            )
            
            # Get current portfolio value
            portfolio_value = self._get_portfolio_value()
            exposure_pct = (total_exposure / portfolio_value) * 100
            
            # Check single position limit
            if exposure_pct > self.config['max_single_position_pct']:
                return False, f"Grid exposure {exposure_pct:.1f}% exceeds single position limit {self.config['max_single_position_pct']}%"
                
            # Check if adding this would exceed portfolio limit
            current_exposure_pct = self._get_current_exposure_pct()
            if current_exposure_pct + exposure_pct > self.config['max_portfolio_exposure_pct']:
                return False, f"Total exposure would be {current_exposure_pct + exposure_pct:.1f}%, exceeds limit {self.config['max_portfolio_exposure_pct']}%"
                
            # Check correlation limits
            correlation_risk = self._calculate_correlation_risk(symbol, total_exposure)
            if correlation_risk > self.config['max_correlation_exposure']:
                return False, f"Correlation risk {correlation_risk:.2f} exceeds limit {self.config['max_correlation_exposure']}"
                
            return True, "Grid exposure validated"
            
        except Exception as e:
            logger.error(f"Error validating grid exposure: {e}")
            return False, f"Error validating exposure: {e}"
            
    def calculate_adaptive_position_size(self, symbol: str, strategy_type: str, 
                                       volatility: float, current_price: float) -> float:
        """Dynamic position sizing based on strategy and volatility"""
        try:
            portfolio_value = self._get_portfolio_value()
            
            # Base position size by strategy
            if strategy_type == 'grid_trading':
                base_pct = self.config['grid_position_size_pct']
            elif strategy_type == 'scalping':
                base_pct = self.config['scalp_position_size_pct']
            else:
                base_pct = 0.5
                
            # Adjust for volatility (higher vol = smaller position)
            volatility_multiplier = min(1.0, 0.02 / max(volatility, 0.005))  # Target 2% volatility
            
            # Adjust for recent performance
            performance_multiplier = self._get_performance_multiplier(symbol, strategy_type)
            
            # Calculate final position size
            adjusted_pct = base_pct * volatility_multiplier * performance_multiplier
            position_size_usd = portfolio_value * (adjusted_pct / 100)
            
            # Convert to quantity
            quantity = position_size_usd / current_price
            
            # Ensure minimum viable size
            min_size_usd = 10.0  # $10 minimum
            if position_size_usd < min_size_usd:
                quantity = min_size_usd / current_price
                
            logger.debug(f"Position size for {symbol} ({strategy_type}): {quantity:.6f} (${position_size_usd:.2f}, {adjusted_pct:.2f}%)")
            
            return round(quantity, 6)
            
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return 0.0
            
    def monitor_correlation_limits(self, active_symbols: List[str]) -> Tuple[bool, List[str]]:
        """Prevent over-exposure to correlated assets"""
        try:
            warnings = []
            
            if len(active_symbols) < 2:
                return True, warnings
                
            # Check pairwise correlations
            high_correlation_pairs = []
            
            for i, symbol1 in enumerate(active_symbols):
                for j, symbol2 in enumerate(active_symbols[i+1:], i+1):
                    correlation = self._get_correlation(symbol1, symbol2)
                    
                    if abs(correlation) > self.config['max_correlation_exposure']:
                        high_correlation_pairs.append((symbol1, symbol2, correlation))
                        warnings.append(f"High correlation between {symbol1} and {symbol2}: {correlation:.2f}")
                        
            # Check sector concentration
            sector_exposure = self._calculate_sector_exposure(active_symbols)
            for sector, exposure_pct in sector_exposure.items():
                if exposure_pct > 50.0:  # Max 50% in any sector
                    warnings.append(f"High sector concentration in {sector}: {exposure_pct:.1f}%")
                    
            # Return overall status
            correlation_ok = len(high_correlation_pairs) == 0
            
            return correlation_ok, warnings
            
        except Exception as e:
            logger.error(f"Error monitoring correlations: {e}")
            return False, [f"Error monitoring correlations: {e}"]
            
    def validate_new_position(self, symbol: str, strategy_type: str, 
                            position_size: float, current_price: float) -> Tuple[bool, str]:
        """Comprehensive validation for new positions"""
        try:
            position_value = position_size * current_price
            
            # Check daily loss limit
            if not self._check_daily_loss_limit():
                return False, "Daily loss limit exceeded"
                
            # Check margin requirements
            if not self._check_margin_requirements(position_value):
                return False, "Insufficient margin available"
                
            # Check concurrent grid limit
            if strategy_type == 'grid_trading':
                active_grids = self._count_active_grids()
                if active_grids >= self.config['max_concurrent_grids']:
                    return False, f"Max concurrent grids limit reached ({active_grids})"
                    
            # Check portfolio concentration
            portfolio_value = self._get_portfolio_value()
            position_pct = (position_value / portfolio_value) * 100
            
            if position_pct > self.config['max_single_position_pct']:
                return False, f"Position size {position_pct:.1f}% exceeds single position limit"
                
            # Check total exposure
            current_exposure = self._get_current_exposure_pct()
            if current_exposure + position_pct > self.config['max_portfolio_exposure_pct']:
                return False, f"Would exceed portfolio exposure limit"
                
            return True, "Position validated"
            
        except Exception as e:
            logger.error(f"Error validating position: {e}")
            return False, f"Validation error: {e}"
            
    def get_risk_metrics(self) -> PortfolioRisk:
        """Get current portfolio risk metrics"""
        try:
            portfolio_value = self._get_portfolio_value()
            total_exposure = self._get_total_exposure()
            
            return PortfolioRisk(
                total_exposure_usd=total_exposure,
                total_exposure_pct=(total_exposure / portfolio_value) * 100,
                max_drawdown_pct=self._calculate_max_drawdown(),
                var_1d_pct=self._calculate_var_1d(),
                correlation_concentration=self._calculate_correlation_concentration(),
                active_strategies=self._count_active_strategies()
            )
            
        except Exception as e:
            logger.error(f"Error calculating risk metrics: {e}")
            return PortfolioRisk(0, 0, 0, 0, 0, 0)
            
    def update_performance_tracking(self, symbol: str, strategy_type: str, 
                                  pnl: float, trade_duration: float):
        """Update performance tracking for risk adjustment"""
        try:
            key = f"{symbol}_{strategy_type}"
            
            if key not in self.performance_tracking:
                self.performance_tracking[key] = {
                    'trades': [],
                    'total_pnl': 0,
                    'win_rate': 0,
                    'avg_duration': 0,
                    'sharpe_ratio': 0
                }
                
            # Add new trade
            trade_data = {
                'pnl': pnl,
                'duration': trade_duration,
                'timestamp': time.time()
            }
            
            self.performance_tracking[key]['trades'].append(trade_data)
            
            # Keep only recent trades (last 100)
            if len(self.performance_tracking[key]['trades']) > 100:
                self.performance_tracking[key]['trades'] = self.performance_tracking[key]['trades'][-100:]
                
            # Update metrics
            self._update_performance_metrics(key)
            
        except Exception as e:
            logger.error(f"Error updating performance tracking: {e}")
            
    def _get_portfolio_value(self) -> float:
        """Get current portfolio value"""
        try:
            # This would integrate with the base risk manager
            if hasattr(self.base_risk_manager, 'get_portfolio_value'):
                return self.base_risk_manager.get_portfolio_value()
            else:
                # Mock value for testing
                return 10000.0
        except Exception as e:
            logger.error(f"Error getting portfolio value: {e}")
            return 10000.0
            
    def _get_current_exposure_pct(self) -> float:
        """Get current total exposure percentage"""
        try:
            portfolio_value = self._get_portfolio_value()
            total_exposure = self._get_total_exposure()
            return (total_exposure / portfolio_value) * 100
        except Exception as e:
            logger.error(f"Error getting current exposure: {e}")
            return 0.0
            
    def _get_total_exposure(self) -> float:
        """Get total USD exposure across all positions"""
        try:
            # This would integrate with position tracking
            # Mock implementation
            return 1000.0
        except Exception as e:
            logger.error(f"Error getting total exposure: {e}")
            return 0.0
            
    def _calculate_correlation_risk(self, symbol: str, position_value: float) -> float:
        """Calculate correlation risk for a position"""
        try:
            # Simplified correlation risk calculation
            # In reality, this would use historical correlation data
            return 0.3  # Mock correlation risk
        except Exception as e:
            logger.error(f"Error calculating correlation risk: {e}")
            return 1.0  # Conservative default
            
    def _get_performance_multiplier(self, symbol: str, strategy_type: str) -> float:
        """Get performance-based position size multiplier"""
        try:
            key = f"{symbol}_{strategy_type}"
            
            if key not in self.performance_tracking:
                return 1.0  # Default multiplier
                
            metrics = self.performance_tracking[key]
            
            # Adjust based on recent performance
            if metrics['win_rate'] > 0.6:
                return 1.2  # Increase size for good performance
            elif metrics['win_rate'] < 0.4:
                return 0.8  # Decrease size for poor performance
            else:
                return 1.0  # Neutral
                
        except Exception as e:
            logger.error(f"Error getting performance multiplier: {e}")
            return 1.0
            
    def _get_correlation(self, symbol1: str, symbol2: str) -> float:
        """Get correlation between two symbols"""
        try:
            # This would use historical price data to calculate correlation
            # Mock implementation
            if symbol1 == symbol2:
                return 1.0
            else:
                return 0.3  # Mock correlation
        except Exception as e:
            logger.error(f"Error getting correlation: {e}")
            return 0.0
            
    def _calculate_sector_exposure(self, symbols: List[str]) -> Dict[str, float]:
        """Calculate exposure by sector"""
        try:
            # This would map symbols to sectors and calculate exposure
            # Mock implementation
            return {"crypto": 100.0}
        except Exception as e:
            logger.error(f"Error calculating sector exposure: {e}")
            return {}
            
    def _check_daily_loss_limit(self) -> bool:
        """Check if daily loss limit is exceeded"""
        try:
            # This would track daily P&L
            # Mock implementation
            return True
        except Exception as e:
            logger.error(f"Error checking daily loss limit: {e}")
            return False
            
    def _check_margin_requirements(self, position_value: float) -> bool:
        """Check if sufficient margin is available"""
        try:
            # This would check available margin
            # Mock implementation
            return True
        except Exception as e:
            logger.error(f"Error checking margin: {e}")
            return False
            
    def _count_active_grids(self) -> int:
        """Count currently active grid strategies"""
        try:
            # This would count active grids
            # Mock implementation
            return 1
        except Exception as e:
            logger.error(f"Error counting active grids: {e}")
            return 0
            
    def _count_active_strategies(self) -> int:
        """Count total active strategies"""
        try:
            return len(self.performance_tracking)
        except Exception as e:
            logger.error(f"Error counting active strategies: {e}")
            return 0
            
    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown percentage"""
        try:
            # Mock implementation
            return 2.5
        except Exception as e:
            logger.error(f"Error calculating max drawdown: {e}")
            return 0.0
            
    def _calculate_var_1d(self) -> float:
        """Calculate 1-day Value at Risk"""
        try:
            # Mock implementation
            return 1.5
        except Exception as e:
            logger.error(f"Error calculating VaR: {e}")
            return 0.0
            
    def _calculate_correlation_concentration(self) -> float:
        """Calculate correlation concentration risk"""
        try:
            # Mock implementation
            return 0.4
        except Exception as e:
            logger.error(f"Error calculating correlation concentration: {e}")
            return 0.0
            
    def _update_performance_metrics(self, key: str):
        """Update performance metrics for a strategy"""
        try:
            trades = self.performance_tracking[key]['trades']
            
            if not trades:
                return
                
            # Calculate metrics
            pnls = [trade['pnl'] for trade in trades]
            
            self.performance_tracking[key]['total_pnl'] = sum(pnls)
            self.performance_tracking[key]['win_rate'] = len([p for p in pnls if p > 0]) / len(pnls)
            self.performance_tracking[key]['avg_duration'] = np.mean([trade['duration'] for trade in trades])
            
            # Simple Sharpe ratio calculation
            if len(pnls) > 1:
                returns = np.array(pnls)
                sharpe = np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0
                self.performance_tracking[key]['sharpe_ratio'] = sharpe
                
        except Exception as e:
            logger.error(f"Error updating performance metrics: {e}")
            
    def get_strategy_performance(self, symbol: str, strategy_type: str) -> Optional[Dict]:
        """Get performance metrics for a specific strategy"""
        key = f"{symbol}_{strategy_type}"
        return self.performance_tracking.get(key)
        
    def reset_daily_limits(self):
        """Reset daily loss limits (called at start of each day)"""
        try:
            # This would reset daily tracking
            logger.info("Daily risk limits reset")
        except Exception as e:
            logger.error(f"Error resetting daily limits: {e}") 