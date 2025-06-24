"""
Advanced Correlation-Aware Risk Management System for Flow Trading
"""

import numpy as np
import pandas as pd
import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict, deque
import json

logger = logging.getLogger(__name__)

@dataclass
class RiskMetrics:
    """Advanced risk metrics"""
    portfolio_var_1d: float  # 1-day Value at Risk
    portfolio_var_5d: float  # 5-day Value at Risk
    max_drawdown_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    correlation_concentration: float  # Concentration risk from correlations
    sector_concentration: float
    leverage_ratio: float
    liquidity_risk_score: float
    tail_risk_score: float  # Risk of extreme events

@dataclass
class PositionRisk:
    """Risk assessment for individual positions"""
    symbol: str
    position_size_usd: float
    var_contribution: float  # Contribution to portfolio VaR
    correlation_risk: float  # Risk from correlations
    liquidity_score: float
    volatility_percentile: float
    stress_loss_pct: float  # Potential loss in stress scenario
    recommended_size: float
    trailing_stop_price: float
    dynamic_stop_distance: float

@dataclass
class MarketStressScenario:
    """Market stress testing scenario"""
    name: str
    market_drop_pct: float
    volatility_spike_multiplier: float
    correlation_increase: float
    liquidity_decrease_pct: float
    duration_days: int

class CorrelationAnalyzer:
    """Advanced correlation analysis for portfolio risk"""
    
    def __init__(self, lookback_days: int = 252):
        self.lookback_days = lookback_days
        self.correlation_cache = {}
        self.correlation_history = deque(maxlen=100)
        
    def calculate_rolling_correlations(self, returns_matrix: pd.DataFrame) -> pd.DataFrame:
        """Calculate rolling correlations between assets"""
        try:
            # Calculate correlations with different time windows
            correlation_matrices = {}
            
            for window in [30, 60, 252]:  # 1 month, 2 months, 1 year
                if len(returns_matrix) >= window:
                    corr_matrix = returns_matrix.rolling(window=window).corr()
                    correlation_matrices[f'{window}d'] = corr_matrix.iloc[-len(returns_matrix.columns):]
            
            # Return most recent correlation matrix
            if correlation_matrices:
                return correlation_matrices[f'{min(correlation_matrices.keys())}']
            else:
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"Error calculating correlations: {e}")
            return pd.DataFrame()
    
    def detect_correlation_regime_changes(self, current_correlations: pd.DataFrame) -> Dict[str, float]:
        """Detect significant changes in correlation regime"""
        try:
            if current_correlations.empty or not self.correlation_history:
                return {'regime_change_score': 0.0, 'stability_score': 1.0}
            
            # Compare with historical average
            historical_avg = np.mean([corr for corr in self.correlation_history], axis=0)
            
            # Calculate regime change metrics
            current_avg_corr = np.nanmean(current_correlations.values)
            historical_avg_corr = np.nanmean(historical_avg) if len(historical_avg) > 0 else 0
            
            regime_change_score = abs(current_avg_corr - historical_avg_corr)
            
            # Calculate stability (lower variance = higher stability)
            recent_correlations = list(self.correlation_history)[-10:] if len(self.correlation_history) >= 10 else list(self.correlation_history)
            if len(recent_correlations) > 1:
                correlation_variance = np.var([np.nanmean(corr) for corr in recent_correlations])
                stability_score = max(0, 1 - correlation_variance * 10)  # Scale to 0-1
            else:
                stability_score = 1.0
            
            # Store current correlations
            self.correlation_history.append(current_correlations.values)
            
            return {
                'regime_change_score': regime_change_score,
                'stability_score': stability_score,
                'current_avg_correlation': current_avg_corr
            }
            
        except Exception as e:
            logger.error(f"Error detecting correlation regime changes: {e}")
            return {'regime_change_score': 0.0, 'stability_score': 1.0}
    
    def calculate_concentration_risk(self, correlations: pd.DataFrame, position_weights: Dict[str, float]) -> float:
        """Calculate portfolio concentration risk from correlations"""
        try:
            if correlations.empty or not position_weights:
                return 0.0
            
            # Convert weights to array in same order as correlation matrix
            symbols = list(correlations.columns)
            weights = np.array([position_weights.get(symbol, 0) for symbol in symbols])
            
            if np.sum(weights) == 0:
                return 0.0
            
            # Normalize weights
            weights = weights / np.sum(weights)
            
            # Calculate portfolio variance using correlation matrix
            # Assume equal volatility for simplification
            portfolio_variance = np.dot(weights, np.dot(correlations.values, weights))
            
            # Compare to uncorrelated portfolio (concentration = how much worse than uncorrelated)
            uncorrelated_variance = np.sum(weights ** 2)  # Assumes uncorrelated assets
            
            concentration_ratio = portfolio_variance / uncorrelated_variance if uncorrelated_variance > 0 else 1.0
            
            # Scale to 0-1 (1 = maximum concentration)
            return min(concentration_ratio - 1, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating concentration risk: {e}")
            return 0.0

class DynamicStopLossManager:
    """Dynamic trailing stop loss with market-aware adjustments"""
    
    def __init__(self):
        self.position_stops = {}  # symbol -> stop data
        self.volatility_cache = {}
        self.trend_cache = {}
        
    def calculate_dynamic_stop(self, symbol: str, entry_price: float, current_price: float, 
                             market_data: Dict[str, Any], position_type: str = 'LONG') -> Dict[str, float]:
        """Calculate dynamic stop loss based on market conditions"""
        try:
            # Extract price data
            close_prices = np.array([float(k['close']) for k in market_data.get('klines', [])])
            
            if len(close_prices) < 20:
                return self._default_stop_calculation(entry_price, current_price, position_type)
            
            # Calculate ATR for volatility-based stops
            atr = self._calculate_atr(close_prices)
            
            # Calculate trend strength
            trend_strength = self._calculate_trend_strength(close_prices)
            
            # Calculate volatility regime
            volatility_regime = self._calculate_volatility_regime(close_prices)
            
            # Dynamic stop distance based on market conditions
            base_stop_distance = atr * 2.0  # Base ATR multiplier
            
            # Adjust for trend strength
            if trend_strength > 0.7:  # Strong trend
                trend_multiplier = 1.5  # Wider stops in strong trends
            elif trend_strength < 0.3:  # Weak trend/ranging
                trend_multiplier = 0.8  # Tighter stops in ranging markets
            else:
                trend_multiplier = 1.0
            
            # Adjust for volatility
            if volatility_regime == 'high':
                volatility_multiplier = 1.3
            elif volatility_regime == 'low':
                volatility_multiplier = 0.7
            else:
                volatility_multiplier = 1.0
            
            # Final stop distance
            dynamic_stop_distance = base_stop_distance * trend_multiplier * volatility_multiplier
            
            # Calculate stop price
            if position_type == 'LONG':
                stop_price = current_price - dynamic_stop_distance
                # Ensure stop only moves up for long positions
                if symbol in self.position_stops:
                    previous_stop = self.position_stops[symbol]['stop_price']
                    stop_price = max(stop_price, previous_stop)
            else:  # SHORT
                stop_price = current_price + dynamic_stop_distance
                # Ensure stop only moves down for short positions
                if symbol in self.position_stops:
                    previous_stop = self.position_stops[symbol]['stop_price']
                    stop_price = min(stop_price, previous_stop)
            
            # Store stop data
            stop_data = {
                'stop_price': stop_price,
                'stop_distance': dynamic_stop_distance,
                'atr': atr,
                'trend_strength': trend_strength,
                'volatility_regime': volatility_regime,
                'last_updated': datetime.utcnow()
            }
            
            self.position_stops[symbol] = stop_data
            
            return stop_data
            
        except Exception as e:
            logger.error(f"Error calculating dynamic stop for {symbol}: {e}")
            return self._default_stop_calculation(entry_price, current_price, position_type)
    
    def _calculate_atr(self, close_prices: np.ndarray, period: int = 14) -> float:
        """Calculate Average True Range"""
        try:
            if len(close_prices) < period + 1:
                return np.std(np.diff(close_prices)) if len(close_prices) > 1 else close_prices[-1] * 0.02
            
            # Simplified ATR calculation
            price_changes = np.abs(np.diff(close_prices))
            atr = np.mean(price_changes[-period:])
            
            return atr
            
        except Exception as e:
            logger.error(f"Error calculating ATR: {e}")
            return close_prices[-1] * 0.02  # 2% default
    
    def _calculate_trend_strength(self, close_prices: np.ndarray) -> float:
        """Calculate trend strength (0 = no trend, 1 = strong trend)"""
        try:
            if len(close_prices) < 20:
                return 0.5
            
            # Calculate moving averages
            short_ma = np.mean(close_prices[-10:])
            long_ma = np.mean(close_prices[-20:])
            
            # Calculate trend direction consistency
            recent_changes = np.diff(close_prices[-10:])
            positive_changes = np.sum(recent_changes > 0)
            negative_changes = np.sum(recent_changes < 0)
            
            direction_consistency = max(positive_changes, negative_changes) / len(recent_changes)
            
            # Calculate magnitude of trend
            ma_divergence = abs(short_ma - long_ma) / long_ma if long_ma > 0 else 0
            magnitude_factor = min(ma_divergence * 100, 1.0)
            
            return direction_consistency * magnitude_factor
            
        except Exception as e:
            logger.error(f"Error calculating trend strength: {e}")
            return 0.5
    
    def _calculate_volatility_regime(self, close_prices: np.ndarray) -> str:
        """Determine volatility regime"""
        try:
            if len(close_prices) < 20:
                return 'medium'
            
            returns = np.diff(close_prices) / close_prices[:-1]
            current_vol = np.std(returns[-10:])
            historical_vol = np.std(returns[-20:])
            
            vol_ratio = current_vol / historical_vol if historical_vol > 0 else 1.0
            
            if vol_ratio > 1.5:
                return 'high'
            elif vol_ratio < 0.7:
                return 'low'
            else:
                return 'medium'
                
        except Exception as e:
            logger.error(f"Error calculating volatility regime: {e}")
            return 'medium'
    
    def _default_stop_calculation(self, entry_price: float, current_price: float, position_type: str) -> Dict[str, float]:
        """Default stop calculation when market data is insufficient"""
        default_stop_pct = 0.02  # 2% default stop
        
        if position_type == 'LONG':
            stop_price = current_price * (1 - default_stop_pct)
        else:
            stop_price = current_price * (1 + default_stop_pct)
        
        return {
            'stop_price': stop_price,
            'stop_distance': abs(current_price - stop_price),
            'atr': current_price * default_stop_pct,
            'trend_strength': 0.5,
            'volatility_regime': 'medium',
            'last_updated': datetime.utcnow()
        }

class AdvancedRiskManager:
    """Main advanced risk management system"""
    
    def __init__(self, base_risk_manager):
        self.base_risk_manager = base_risk_manager
        self.correlation_analyzer = CorrelationAnalyzer()
        self.stop_manager = DynamicStopLossManager()
        
        # Risk configuration
        self.max_portfolio_var = 0.03  # 3% daily VaR limit
        self.max_correlation_concentration = 0.4  # 40% max concentration risk
        self.max_single_position_risk = 0.1  # 10% max single position risk
        self.max_sector_concentration = 0.3  # 30% max sector concentration
        
        # Performance tracking
        self.risk_metrics_history = deque(maxlen=252)  # 1 year of daily metrics
        self.stress_test_results = {}
        
        # Stress testing scenarios
        self.stress_scenarios = [
            MarketStressScenario("Flash Crash", -10.0, 3.0, 0.8, 50.0, 1),
            MarketStressScenario("Market Correction", -20.0, 2.0, 0.5, 30.0, 30),
            MarketStressScenario("Crypto Winter", -50.0, 2.5, 0.6, 60.0, 180),
            MarketStressScenario("Liquidity Crisis", -15.0, 2.0, 0.9, 80.0, 7)
        ]
    
    async def assess_portfolio_risk(self, positions: Dict[str, Dict], market_data: Dict[str, Dict]) -> RiskMetrics:
        """Comprehensive portfolio risk assessment"""
        try:
            if not positions:
                return self._create_empty_risk_metrics()
            
            # Calculate returns matrix for correlation analysis
            returns_matrix = self._calculate_returns_matrix(market_data)
            
            # Calculate correlations
            correlations = self.correlation_analyzer.calculate_rolling_correlations(returns_matrix)
            
            # Calculate position weights
            total_value = sum(pos.get('value_usd', 0) for pos in positions.values())
            position_weights = {symbol: pos.get('value_usd', 0) / total_value 
                              for symbol, pos in positions.items()} if total_value > 0 else {}
            
            # Portfolio VaR calculation
            portfolio_var_1d, portfolio_var_5d = self._calculate_portfolio_var(
                positions, returns_matrix, correlations
            )
            
            # Maximum drawdown
            max_drawdown = self._calculate_max_drawdown(positions)
            
            # Sharpe and Sortino ratios
            sharpe_ratio, sortino_ratio = self._calculate_risk_adjusted_returns(positions)
            
            # Correlation concentration risk
            correlation_concentration = self.correlation_analyzer.calculate_concentration_risk(
                correlations, position_weights
            )
            
            # Sector concentration (simplified - would need sector classification)
            sector_concentration = self._calculate_sector_concentration(positions)
            
            # Leverage ratio
            leverage_ratio = self._calculate_leverage_ratio(positions)
            
            # Liquidity risk
            liquidity_risk_score = self._calculate_liquidity_risk(positions, market_data)
            
            # Tail risk (extreme event risk)
            tail_risk_score = self._calculate_tail_risk(returns_matrix, positions)
            
            risk_metrics = RiskMetrics(
                portfolio_var_1d=portfolio_var_1d,
                portfolio_var_5d=portfolio_var_5d,
                max_drawdown_pct=max_drawdown,
                sharpe_ratio=sharpe_ratio,
                sortino_ratio=sortino_ratio,
                correlation_concentration=correlation_concentration,
                sector_concentration=sector_concentration,
                leverage_ratio=leverage_ratio,
                liquidity_risk_score=liquidity_risk_score,
                tail_risk_score=tail_risk_score
            )
            
            # Store metrics history
            self.risk_metrics_history.append(risk_metrics)
            
            return risk_metrics
            
        except Exception as e:
            logger.error(f"Error assessing portfolio risk: {e}")
            return self._create_empty_risk_metrics()
    
    async def calculate_optimal_position_size(self, symbol: str, signal_confidence: float, 
                                           current_positions: Dict[str, Dict], market_data: Dict[str, Dict]) -> float:
        """Calculate optimal position size using advanced risk management"""
        try:
            # Base position size from risk limits
            base_size = self.max_single_position_risk
            
            # Adjust for signal confidence
            confidence_multiplier = signal_confidence
            
            # Adjust for correlation risk
            correlation_multiplier = await self._calculate_correlation_adjustment(
                symbol, current_positions, market_data
            )
            
            # Adjust for volatility
            volatility_multiplier = self._calculate_volatility_adjustment(symbol, market_data)
            
            # Adjust for liquidity
            liquidity_multiplier = self._calculate_liquidity_adjustment(symbol, market_data)
            
            # Portfolio concentration adjustment
            concentration_multiplier = self._calculate_concentration_adjustment(current_positions)
            
            # Final position size
            optimal_size = (base_size * confidence_multiplier * correlation_multiplier * 
                          volatility_multiplier * liquidity_multiplier * concentration_multiplier)
            
            # Apply absolute limits
            optimal_size = min(optimal_size, self.max_single_position_risk)
            optimal_size = max(optimal_size, 0.01)  # Minimum 1%
            
            logger.info(f"Optimal position size for {symbol}: {optimal_size:.4f} "
                       f"(confidence={confidence_multiplier:.2f}, corr={correlation_multiplier:.2f}, "
                       f"vol={volatility_multiplier:.2f}, liq={liquidity_multiplier:.2f})")
            
            return optimal_size
            
        except Exception as e:
            logger.error(f"Error calculating optimal position size for {symbol}: {e}")
            return 0.05  # Default 5%
    
    async def run_stress_tests(self, positions: Dict[str, Dict], market_data: Dict[str, Dict]) -> Dict[str, Dict]:
        """Run comprehensive stress tests on the portfolio"""
        try:
            stress_results = {}
            
            for scenario in self.stress_scenarios:
                scenario_loss = await self._simulate_stress_scenario(scenario, positions, market_data)
                
                stress_results[scenario.name] = {
                    'scenario': scenario.__dict__,
                    'estimated_loss_pct': scenario_loss,
                    'estimated_loss_usd': scenario_loss * sum(pos.get('value_usd', 0) for pos in positions.values()),
                    'passes_stress_test': scenario_loss < 0.25  # Pass if loss < 25%
                }
            
            # Overall stress test score
            avg_loss = np.mean([result['estimated_loss_pct'] for result in stress_results.values()])
            max_loss = max([result['estimated_loss_pct'] for result in stress_results.values()])
            
            stress_results['summary'] = {
                'average_loss_pct': avg_loss,
                'worst_case_loss_pct': max_loss,
                'overall_risk_score': min(max_loss, 1.0),
                'recommendation': 'REDUCE_RISK' if max_loss > 0.3 else 'MAINTAIN' if max_loss > 0.15 else 'INCREASE_RISK'
            }
            
            self.stress_test_results = stress_results
            return stress_results
            
        except Exception as e:
            logger.error(f"Error running stress tests: {e}")
            return {'error': str(e)}
    
    def _calculate_returns_matrix(self, market_data: Dict[str, Dict]) -> pd.DataFrame:
        """Calculate returns matrix from market data"""
        try:
            returns_data = {}
            
            for symbol, data in market_data.items():
                if 'klines' in data and data['klines']:
                    prices = [float(k['close']) for k in data['klines']]
                    if len(prices) > 1:
                        returns = np.diff(prices) / prices[:-1]
                        returns_data[symbol] = returns
            
            if returns_data:
                # Align all returns to same length
                min_length = min(len(returns) for returns in returns_data.values())
                aligned_returns = {symbol: returns[-min_length:] for symbol, returns in returns_data.items()}
                return pd.DataFrame(aligned_returns)
            else:
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"Error calculating returns matrix: {e}")
            return pd.DataFrame()
    
    def _calculate_portfolio_var(self, positions: Dict[str, Dict], returns_matrix: pd.DataFrame, 
                               correlations: pd.DataFrame, confidence_level: float = 0.05) -> Tuple[float, float]:
        """Calculate Portfolio Value at Risk"""
        try:
            if returns_matrix.empty or not positions:
                return 0.0, 0.0
            
            # Calculate portfolio returns
            total_value = sum(pos.get('value_usd', 0) for pos in positions.values())
            if total_value == 0:
                return 0.0, 0.0
            
            weights = np.array([positions.get(symbol, {}).get('value_usd', 0) / total_value 
                              for symbol in returns_matrix.columns])
            
            # Portfolio returns
            portfolio_returns = np.dot(returns_matrix.values, weights)
            
            # Calculate VaR using historical simulation
            var_1d = np.percentile(portfolio_returns, confidence_level * 100) * -1
            
            # Scale to 5-day VaR (assuming independence - simplified)
            var_5d = var_1d * np.sqrt(5)
            
            return var_1d, var_5d
            
        except Exception as e:
            logger.error(f"Error calculating portfolio VaR: {e}")
            return 0.0, 0.0
    
    def _calculate_max_drawdown(self, positions: Dict[str, Dict]) -> float:
        """Calculate maximum drawdown (simplified)"""
        try:
            # This would typically use historical P&L data
            # For now, use a simplified calculation based on position volatilities
            
            total_volatility = 0
            for symbol, pos in positions.items():
                position_vol = pos.get('volatility', 0.02)  # Default 2% daily vol
                position_weight = pos.get('value_usd', 0)
                total_volatility += position_vol * position_weight
            
            total_value = sum(pos.get('value_usd', 0) for pos in positions.values())
            avg_volatility = total_volatility / total_value if total_value > 0 else 0
            
            # Estimate max drawdown as 3x daily volatility (simplified)
            estimated_max_drawdown = avg_volatility * 3
            
            return min(estimated_max_drawdown, 0.5)  # Cap at 50%
            
        except Exception as e:
            logger.error(f"Error calculating max drawdown: {e}")
            return 0.1
    
    def _calculate_risk_adjusted_returns(self, positions: Dict[str, Dict]) -> Tuple[float, float]:
        """Calculate Sharpe and Sortino ratios (simplified)"""
        try:
            # This would typically use historical returns
            # For now, use simplified calculation
            
            total_return = sum(pos.get('unrealized_pnl_pct', 0) for pos in positions.values())
            total_positions = len(positions)
            avg_return = total_return / total_positions if total_positions > 0 else 0
            
            # Estimate volatility
            total_vol = sum(pos.get('volatility', 0.02) for pos in positions.values())
            avg_vol = total_vol / total_positions if total_positions > 0 else 0.02
            
            # Risk-free rate (simplified)
            risk_free_rate = 0.02  # 2% annual
            
            # Sharpe ratio
            sharpe_ratio = (avg_return - risk_free_rate) / avg_vol if avg_vol > 0 else 0
            
            # Sortino ratio (simplified - assume downside deviation = 0.7 * total volatility)
            downside_vol = avg_vol * 0.7
            sortino_ratio = (avg_return - risk_free_rate) / downside_vol if downside_vol > 0 else 0
            
            return sharpe_ratio, sortino_ratio
            
        except Exception as e:
            logger.error(f"Error calculating risk-adjusted returns: {e}")
            return 0.0, 0.0
    
    async def _calculate_correlation_adjustment(self, symbol: str, current_positions: Dict[str, Dict], 
                                              market_data: Dict[str, Dict]) -> float:
        """Calculate position size adjustment based on correlations"""
        try:
            if not current_positions or symbol not in market_data:
                return 1.0
            
            # Get returns for correlation calculation
            symbol_returns = self._get_symbol_returns(symbol, market_data)
            
            correlation_penalties = []
            for existing_symbol in current_positions.keys():
                if existing_symbol != symbol and existing_symbol in market_data:
                    existing_returns = self._get_symbol_returns(existing_symbol, market_data)
                    
                    if len(symbol_returns) > 10 and len(existing_returns) > 10:
                        # Align returns
                        min_length = min(len(symbol_returns), len(existing_returns))
                        corr = np.corrcoef(symbol_returns[-min_length:], existing_returns[-min_length:])[0, 1]
                        
                        if not np.isnan(corr):
                            # Higher correlation = lower multiplier
                            position_weight = current_positions[existing_symbol].get('value_usd', 0)
                            correlation_penalty = abs(corr) * position_weight * 0.001  # Scale penalty
                            correlation_penalties.append(correlation_penalty)
            
            if correlation_penalties:
                total_penalty = sum(correlation_penalties)
                # Convert to multiplier (1.0 = no penalty, 0.5 = 50% reduction)
                multiplier = max(0.5, 1.0 - total_penalty)
                return multiplier
            
            return 1.0
            
        except Exception as e:
            logger.error(f"Error calculating correlation adjustment: {e}")
            return 1.0
    
    def _get_symbol_returns(self, symbol: str, market_data: Dict[str, Dict]) -> np.ndarray:
        """Get returns for a symbol from market data"""
        try:
            if symbol in market_data and 'klines' in market_data[symbol]:
                prices = [float(k['close']) for k in market_data[symbol]['klines']]
                if len(prices) > 1:
                    return np.diff(prices) / prices[:-1]
            return np.array([])
        except Exception as e:
            logger.error(f"Error getting returns for {symbol}: {e}")
            return np.array([])
    
    def _calculate_sector_concentration(self, positions: Dict[str, Dict]) -> float:
        """Calculate sector concentration (simplified)"""
        # In a real implementation, this would classify symbols by sector
        # For now, treat all crypto as same sector
        return 1.0 if len(positions) > 0 else 0.0
    
    def _calculate_leverage_ratio(self, positions: Dict[str, Dict]) -> float:
        """Calculate leverage ratio"""
        try:
            total_notional = sum(pos.get('notional_value', pos.get('value_usd', 0)) for pos in positions.values())
            total_equity = sum(pos.get('value_usd', 0) for pos in positions.values())
            
            return total_notional / total_equity if total_equity > 0 else 1.0
            
        except Exception as e:
            logger.error(f"Error calculating leverage ratio: {e}")
            return 1.0
    
    def _calculate_liquidity_risk(self, positions: Dict[str, Dict], market_data: Dict[str, Dict]) -> float:
        """Calculate liquidity risk score"""
        try:
            if not positions:
                return 0.0
            
            liquidity_scores = []
            for symbol, pos in positions.items():
                if symbol in market_data and 'klines' in market_data[symbol]:
                    # Use volume as proxy for liquidity
                    volumes = [float(k['volume']) for k in market_data[symbol]['klines']]
                    if volumes:
                        avg_volume = np.mean(volumes[-20:])  # 20-period average
                        recent_volume = np.mean(volumes[-5:])  # Recent 5-period average
                        
                        # Liquidity score based on volume stability and magnitude
                        volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1.0
                        
                        # Score: 1 = high liquidity, 0 = low liquidity
                        if volume_ratio > 0.8 and avg_volume > 1000:  # Stable, high volume
                            liquidity_score = 0.9
                        elif volume_ratio > 0.5:  # Moderate liquidity
                            liquidity_score = 0.6
                        else:  # Low liquidity
                            liquidity_score = 0.3
                        
                        liquidity_scores.append(liquidity_score)
            
            # Return average liquidity risk (1 - liquidity_score)
            if liquidity_scores:
                avg_liquidity = np.mean(liquidity_scores)
                return 1.0 - avg_liquidity
            else:
                return 0.5  # Medium risk if no data
                
        except Exception as e:
            logger.error(f"Error calculating liquidity risk: {e}")
            return 0.5
    
    def _calculate_tail_risk(self, returns_matrix: pd.DataFrame, positions: Dict[str, Dict]) -> float:
        """Calculate tail risk (extreme event risk)"""
        try:
            if returns_matrix.empty:
                return 0.0
            
            # Calculate portfolio returns
            total_value = sum(pos.get('value_usd', 0) for pos in positions.values())
            if total_value == 0:
                return 0.0
            
            weights = np.array([positions.get(symbol, {}).get('value_usd', 0) / total_value 
                              for symbol in returns_matrix.columns])
            
            portfolio_returns = np.dot(returns_matrix.values, weights)
            
            # Calculate tail risk metrics
            var_95 = np.percentile(portfolio_returns, 5)  # 5th percentile
            var_99 = np.percentile(portfolio_returns, 1)  # 1st percentile
            
            # Expected shortfall (average of worst 5% outcomes)
            worst_5pct = portfolio_returns[portfolio_returns <= var_95]
            expected_shortfall = np.mean(worst_5pct) if len(worst_5pct) > 0 else var_95
            
            # Tail risk score (higher = more tail risk)
            tail_risk = abs(expected_shortfall) * 10  # Scale to 0-1 range roughly
            
            return min(tail_risk, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating tail risk: {e}")
            return 0.0
    
    def _calculate_volatility_adjustment(self, symbol: str, market_data: Dict[str, Dict]) -> float:
        """Calculate position size adjustment based on volatility"""
        try:
            if symbol not in market_data:
                return 1.0
            
            returns = self._get_symbol_returns(symbol, market_data)
            if len(returns) < 10:
                return 1.0
            
            volatility = np.std(returns)
            
            # Higher volatility = smaller position
            if volatility > 0.05:  # > 5% daily volatility
                return 0.7
            elif volatility > 0.03:  # > 3% daily volatility
                return 0.85
            else:
                return 1.0
                
        except Exception as e:
            logger.error(f"Error calculating volatility adjustment: {e}")
            return 1.0
    
    def _calculate_liquidity_adjustment(self, symbol: str, market_data: Dict[str, Dict]) -> float:
        """Calculate position size adjustment based on liquidity"""
        try:
            if symbol not in market_data or 'klines' not in market_data[symbol]:
                return 1.0
            
            volumes = [float(k['volume']) for k in market_data[symbol]['klines']]
            if not volumes:
                return 1.0
            
            avg_volume = np.mean(volumes[-20:])
            
            # Higher volume = higher liquidity = can take larger position
            if avg_volume > 10000:  # High volume
                return 1.0
            elif avg_volume > 5000:  # Medium volume
                return 0.8
            else:  # Low volume
                return 0.6
                
        except Exception as e:
            logger.error(f"Error calculating liquidity adjustment: {e}")
            return 1.0
    
    def _calculate_concentration_adjustment(self, current_positions: Dict[str, Dict]) -> float:
        """Calculate adjustment based on portfolio concentration"""
        try:
            if not current_positions:
                return 1.0
            
            # If we already have many positions, reduce new position sizes
            num_positions = len(current_positions)
            
            if num_positions > 10:
                return 0.7
            elif num_positions > 5:
                return 0.85
            else:
                return 1.0
                
        except Exception as e:
            logger.error(f"Error calculating concentration adjustment: {e}")
            return 1.0
    
    def _create_empty_risk_metrics(self) -> RiskMetrics:
        """Create empty risk metrics for error cases"""
        return RiskMetrics(
            portfolio_var_1d=0.0,
            portfolio_var_5d=0.0,
            max_drawdown_pct=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            correlation_concentration=0.0,
            sector_concentration=0.0,
            leverage_ratio=1.0,
            liquidity_risk_score=0.0,
            tail_risk_score=0.0
        ) 