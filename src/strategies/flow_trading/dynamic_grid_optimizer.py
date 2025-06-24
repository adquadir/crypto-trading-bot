"""
Dynamic Grid Optimizer with Bollinger Band-based spacing and Genetic Algorithm optimization
"""

import numpy as np
import pandas as pd
import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import random
from collections import deque
import json

logger = logging.getLogger(__name__)

@dataclass
class GridConfiguration:
    """Dynamic grid configuration"""
    symbol: str
    base_spacing: float
    spacing_multiplier: float
    upper_levels: int
    lower_levels: int
    position_size_multiplier: float
    volatility_adjustment: float
    bb_upper: float
    bb_lower: float
    bb_middle: float
    optimal_score: float
    created_at: datetime

@dataclass
class MarketRegimeContext:
    """Market regime context for grid optimization"""
    volatility_regime: str  # 'low', 'medium', 'high', 'extreme'
    trend_strength: float
    volume_profile: str  # 'normal', 'surge', 'low'
    bollinger_position: float  # -1 to 1, relative to BB bands
    squeeze_factor: float
    recent_breakouts: int
    correlation_strength: float

class GeneticGridOptimizer:
    """Genetic Algorithm for grid parameter optimization"""
    
    def __init__(self, population_size: int = 50, generations: int = 20):
        self.population_size = population_size
        self.generations = generations
        self.mutation_rate = 0.1
        self.crossover_rate = 0.8
        self.elite_size = 5
        
        # Parameter ranges for optimization
        self.param_ranges = {
            'spacing_multiplier': (0.5, 3.0),
            'levels': (3, 15),
            'position_size_multiplier': (0.5, 2.0),
            'volatility_adjustment': (0.5, 2.0)
        }
    
    def generate_individual(self) -> Dict[str, float]:
        """Generate a random individual (grid configuration)"""
        return {
            'spacing_multiplier': random.uniform(*self.param_ranges['spacing_multiplier']),
            'levels': random.randint(*self.param_ranges['levels']),
            'position_size_multiplier': random.uniform(*self.param_ranges['position_size_multiplier']),
            'volatility_adjustment': random.uniform(*self.param_ranges['volatility_adjustment'])
        }
    
    def fitness_function(self, individual: Dict[str, float], market_context: MarketRegimeContext, historical_performance: List[float]) -> float:
        """Calculate fitness score for an individual configuration"""
        score = 0.0
        
        # Volatility regime fitness
        if market_context.volatility_regime == 'low':
            # Tighter grids for low volatility
            if individual['spacing_multiplier'] < 1.5:
                score += 20
            if individual['levels'] > 8:
                score += 15
        elif market_context.volatility_regime == 'high':
            # Wider grids for high volatility
            if individual['spacing_multiplier'] > 1.5:
                score += 20
            if individual['levels'] < 10:
                score += 15
        
        # Trend strength adjustment
        if market_context.trend_strength < 0.3:  # Ranging market
            score += 25  # Grid trading optimal
            if individual['levels'] > 6:
                score += 10
        else:  # Trending market
            score -= 15  # Grid trading less optimal
            if individual['spacing_multiplier'] > 2.0:
                score += 5  # Wider spacing for trends
        
        # Volume surge adjustment
        if market_context.volume_profile == 'surge':
            if individual['volatility_adjustment'] > 1.2:
                score += 10
        elif market_context.volume_profile == 'low':
            if individual['volatility_adjustment'] < 0.8:
                score += 10
        
        # Bollinger Band position
        if abs(market_context.bollinger_position) > 0.7:  # Near bands
            if individual['spacing_multiplier'] > 1.0:
                score += 15
        else:  # Near middle
            if individual['spacing_multiplier'] < 1.5:
                score += 10
        
        # Historical performance bonus
        if historical_performance:
            avg_performance = np.mean(historical_performance[-10:])  # Last 10 performances
            score += avg_performance * 50  # Scale historical performance
        
        # Squeeze factor adjustment
        if market_context.squeeze_factor > 0.8:  # High squeeze
            score += 20  # Grid trading very optimal
            if individual['levels'] > 8:
                score += 10
        
        # Breakout penalty
        if market_context.recent_breakouts > 2:
            score -= 15  # Recent breakouts indicate less suitability for grid
        
        return max(score, 0)  # Ensure non-negative score
    
    def optimize(self, market_context: MarketRegimeContext, historical_performance: List[float]) -> Dict[str, float]:
        """Run genetic algorithm optimization"""
        # Initialize population
        population = [self.generate_individual() for _ in range(self.population_size)]
        
        for generation in range(self.generations):
            # Calculate fitness for all individuals
            fitness_scores = []
            for individual in population:
                fitness = self.fitness_function(individual, market_context, historical_performance)
                fitness_scores.append((individual, fitness))
            
            # Sort by fitness (descending)
            fitness_scores.sort(key=lambda x: x[1], reverse=True)
            
            # Select elite
            elite = [individual for individual, _ in fitness_scores[:self.elite_size]]
            
            # Create new population
            new_population = elite.copy()
            
            # Generate offspring
            while len(new_population) < self.population_size:
                # Tournament selection
                parent1 = self.tournament_selection(fitness_scores)
                parent2 = self.tournament_selection(fitness_scores)
                
                # Crossover and mutation
                child1, child2 = self.crossover(parent1, parent2)
                child1 = self.mutate(child1)
                child2 = self.mutate(child2)
                
                new_population.extend([child1, child2])
            
            population = new_population[:self.population_size]
        
        # Return best individual
        final_scores = [(ind, self.fitness_function(ind, market_context, historical_performance)) 
                       for ind in population]
        best_individual, best_score = max(final_scores, key=lambda x: x[1])
        
        logger.info(f"GA optimization completed. Best score: {best_score:.2f}")
        return best_individual
    
    def crossover(self, parent1: Dict[str, float], parent2: Dict[str, float]) -> Tuple[Dict[str, float], Dict[str, float]]:
        """Create offspring through crossover"""
        if random.random() > self.crossover_rate:
            return parent1.copy(), parent2.copy()
        
        child1 = {}
        child2 = {}
        
        for key in parent1.keys():
            if random.random() < 0.5:
                child1[key] = parent1[key]
                child2[key] = parent2[key]
            else:
                child1[key] = parent2[key]
                child2[key] = parent1[key]
        
        return child1, child2
    
    def mutate(self, individual: Dict[str, float]) -> Dict[str, float]:
        """Apply mutation to an individual"""
        mutated = individual.copy()
        
        for key in mutated.keys():
            if random.random() < self.mutation_rate:
                if key == 'levels':
                    mutated[key] = random.randint(*self.param_ranges[key])
                else:
                    # Gaussian mutation
                    current_val = mutated[key]
                    min_val, max_val = self.param_ranges[key]
                    std_dev = (max_val - min_val) * 0.1
                    new_val = current_val + random.gauss(0, std_dev)
                    mutated[key] = max(min_val, min(max_val, new_val))
        
        return mutated
    
    def tournament_selection(self, fitness_scores: List[Tuple[Dict[str, float], float]], tournament_size: int = 3) -> Dict[str, float]:
        """Tournament selection for parent selection"""
        tournament = random.sample(fitness_scores, min(tournament_size, len(fitness_scores)))
        winner = max(tournament, key=lambda x: x[1])
        return winner[0]

class DynamicGridOptimizer:
    """Main dynamic grid optimizer with Bollinger Band integration"""
    
    def __init__(self, exchange_client):
        self.exchange_client = exchange_client
        self.genetic_optimizer = GeneticGridOptimizer()
        self.performance_history = {}  # symbol -> List[performance_scores]
        self.regime_history = deque(maxlen=100)
        
        # Bollinger Band configuration
        self.bb_period = 20
        self.bb_std_dev = 2.0
        
    async def optimize_grid_configuration(self, symbol: str, market_data: Dict[str, Any]) -> GridConfiguration:
        """Generate optimized grid configuration based on current market conditions"""
        try:
            # Analyze market regime
            market_context = await self._analyze_market_regime(symbol, market_data)
            
            # Get historical performance
            historical_performance = self.performance_history.get(symbol, [])
            
            # Run genetic algorithm optimization
            optimal_params = self.genetic_optimizer.optimize(market_context, historical_performance)
            
            # Calculate Bollinger Band-based spacing
            bb_data = self._calculate_dynamic_bollinger_bands(market_data)
            
            # Create optimized configuration
            config = self._create_grid_configuration(
                symbol, optimal_params, bb_data, market_context
            )
            
            logger.info(f"Optimized grid for {symbol}: spacing={config.spacing_multiplier:.2f}, levels={config.upper_levels + config.lower_levels}")
            
            return config
            
        except Exception as e:
            logger.error(f"Error optimizing grid configuration for {symbol}: {e}")
            return self._create_default_configuration(symbol)
    
    async def _analyze_market_regime(self, symbol: str, market_data: Dict[str, Any]) -> MarketRegimeContext:
        """Analyze current market regime for grid optimization"""
        try:
            # Extract price data
            close_prices = np.array([float(k['close']) for k in market_data.get('klines', [])])
            volumes = np.array([float(k['volume']) for k in market_data.get('klines', [])])
            
            if len(close_prices) < 50:
                return self._create_default_market_context()
            
            # Volatility analysis
            returns = np.diff(close_prices) / close_prices[:-1]
            volatility = np.std(returns[-20:])  # 20-period volatility
            vol_percentile = self._calculate_volatility_percentile(volatility, close_prices)
            
            # Trend strength (ADX-like calculation)
            trend_strength = self._calculate_trend_strength(close_prices)
            
            # Volume analysis
            avg_volume = np.mean(volumes[-20:])
            recent_volume = np.mean(volumes[-5:])
            volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1.0
            
            if volume_ratio > 1.5:
                volume_profile = 'surge'
            elif volume_ratio < 0.7:
                volume_profile = 'low'
            else:
                volume_profile = 'normal'
            
            # Bollinger Band position
            bb_data = self._calculate_dynamic_bollinger_bands(market_data)
            current_price = close_prices[-1]
            bb_position = self._calculate_bb_position(current_price, bb_data)
            
            # Squeeze factor
            squeeze_factor = self._calculate_squeeze_factor(bb_data, close_prices)
            
            # Recent breakouts
            recent_breakouts = self._count_recent_breakouts(close_prices, bb_data)
            
            # Market correlation (simplified)
            correlation_strength = self._calculate_correlation_strength(close_prices)
            
            # Determine volatility regime
            if vol_percentile > 0.85:
                volatility_regime = 'extreme'
            elif vol_percentile > 0.65:
                volatility_regime = 'high'
            elif vol_percentile > 0.35:
                volatility_regime = 'medium'
            else:
                volatility_regime = 'low'
            
            return MarketRegimeContext(
                volatility_regime=volatility_regime,
                trend_strength=trend_strength,
                volume_profile=volume_profile,
                bollinger_position=bb_position,
                squeeze_factor=squeeze_factor,
                recent_breakouts=recent_breakouts,
                correlation_strength=correlation_strength
            )
            
        except Exception as e:
            logger.error(f"Error analyzing market regime: {e}")
            return self._create_default_market_context()
    
    def _calculate_dynamic_bollinger_bands(self, market_data: Dict[str, Any]) -> Dict[str, float]:
        """Calculate dynamic Bollinger Bands with volatility adjustment"""
        try:
            close_prices = np.array([float(k['close']) for k in market_data.get('klines', [])])
            
            if len(close_prices) < self.bb_period:
                return {'upper': 0, 'lower': 0, 'middle': 0, 'width': 0}
            
            # Calculate standard Bollinger Bands
            sma = np.mean(close_prices[-self.bb_period:])
            std = np.std(close_prices[-self.bb_period:])
            
            # Dynamic multiplier based on volatility regime
            volatility = np.std(np.diff(close_prices[-self.bb_period:]) / close_prices[-self.bb_period:-1])
            vol_percentile = self._calculate_volatility_percentile(volatility, close_prices)
            
            # Adjust standard deviation multiplier
            if vol_percentile > 0.8:
                multiplier = self.bb_std_dev * 1.5  # Wider bands in high volatility
            elif vol_percentile < 0.2:
                multiplier = self.bb_std_dev * 0.7  # Tighter bands in low volatility
            else:
                multiplier = self.bb_std_dev
            
            upper_band = sma + (std * multiplier)
            lower_band = sma - (std * multiplier)
            band_width = (upper_band - lower_band) / sma if sma > 0 else 0
            
            return {
                'upper': upper_band,
                'lower': lower_band,
                'middle': sma,
                'width': band_width
            }
            
        except Exception as e:
            logger.error(f"Error calculating Bollinger Bands: {e}")
            return {'upper': 0, 'lower': 0, 'middle': 0, 'width': 0}
    
    def _calculate_volatility_percentile(self, current_vol: float, price_history: np.ndarray) -> float:
        """Calculate volatility percentile compared to historical volatility"""
        try:
            # Calculate rolling volatility for comparison
            window_size = 20
            volatilities = []
            
            for i in range(window_size, len(price_history)):
                window_returns = np.diff(price_history[i-window_size:i]) / price_history[i-window_size:i-1]
                volatilities.append(np.std(window_returns))
            
            if not volatilities:
                return 0.5
            
            return (np.array(volatilities) <= current_vol).mean()
            
        except Exception as e:
            logger.error(f"Error calculating volatility percentile: {e}")
            return 0.5
    
    def _calculate_trend_strength(self, close_prices: np.ndarray) -> float:
        """Calculate trend strength (0 = ranging, 1 = strong trend)"""
        try:
            if len(close_prices) < 20:
                return 0.0
            
            # Simple trend strength based on price direction consistency
            returns = np.diff(close_prices[-20:])
            positive_returns = np.sum(returns > 0)
            negative_returns = np.sum(returns < 0)
            
            # Calculate directional consistency
            total_moves = len(returns)
            if total_moves == 0:
                return 0.0
            
            direction_ratio = max(positive_returns, negative_returns) / total_moves
            
            # Also consider magnitude of moves
            avg_abs_return = np.mean(np.abs(returns))
            magnitude_factor = min(avg_abs_return * 100, 1.0)  # Cap at 1.0
            
            return direction_ratio * magnitude_factor
            
        except Exception as e:
            logger.error(f"Error calculating trend strength: {e}")
            return 0.0
    
    def _calculate_bb_position(self, current_price: float, bb_data: Dict[str, float]) -> float:
        """Calculate position relative to Bollinger Bands (-1 to 1)"""
        try:
            upper = bb_data['upper']
            lower = bb_data['lower']
            middle = bb_data['middle']
            
            if upper == lower:
                return 0.0
            
            if current_price >= middle:
                # Above middle, scale from 0 to 1
                return (current_price - middle) / (upper - middle) if upper != middle else 0.0
            else:
                # Below middle, scale from -1 to 0
                return (current_price - middle) / (middle - lower) if middle != lower else 0.0
                
        except Exception as e:
            logger.error(f"Error calculating BB position: {e}")
            return 0.0
    
    def _calculate_squeeze_factor(self, bb_data: Dict[str, float], close_prices: np.ndarray) -> float:
        """Calculate Bollinger Band squeeze factor (0 to 1)"""
        try:
            current_width = bb_data['width']
            
            # Calculate historical band widths
            historical_widths = []
            window_size = 20
            
            for i in range(window_size, len(close_prices)):
                window_prices = close_prices[i-window_size:i]
                sma = np.mean(window_prices)
                std = np.std(window_prices)
                width = (2 * std) / sma if sma > 0 else 0
                historical_widths.append(width)
            
            if not historical_widths:
                return 0.0
            
            # Calculate percentile of current width (lower percentile = more squeeze)
            width_percentile = (np.array(historical_widths) <= current_width).mean()
            
            # Convert to squeeze factor (1 = maximum squeeze, 0 = no squeeze)
            return 1.0 - width_percentile
            
        except Exception as e:
            logger.error(f"Error calculating squeeze factor: {e}")
            return 0.0
    
    def _count_recent_breakouts(self, close_prices: np.ndarray, bb_data: Dict[str, float]) -> int:
        """Count recent breakouts from Bollinger Bands"""
        try:
            if len(close_prices) < 10:
                return 0
            
            breakouts = 0
            recent_prices = close_prices[-10:]  # Last 10 periods
            
            # Simple breakout detection (price outside bands)
            upper = bb_data['upper']
            lower = bb_data['lower']
            
            for price in recent_prices:
                if price > upper or price < lower:
                    breakouts += 1
            
            return breakouts
            
        except Exception as e:
            logger.error(f"Error counting breakouts: {e}")
            return 0
    
    def _calculate_correlation_strength(self, close_prices: np.ndarray) -> float:
        """Calculate correlation strength with overall market (simplified)"""
        try:
            # Simplified correlation calculation
            # In reality, this would compare with market indices
            if len(close_prices) < 20:
                return 0.5
            
            returns = np.diff(close_prices[-20:]) / close_prices[-20:-1]
            
            # Simple autocorrelation as proxy for market correlation
            if len(returns) > 1:
                autocorr = np.corrcoef(returns[:-1], returns[1:])[0, 1]
                return abs(autocorr) if not np.isnan(autocorr) else 0.5
            
            return 0.5
            
        except Exception as e:
            logger.error(f"Error calculating correlation: {e}")
            return 0.5
    
    def _create_grid_configuration(self, symbol: str, optimal_params: Dict[str, float], 
                                 bb_data: Dict[str, float], market_context: MarketRegimeContext) -> GridConfiguration:
        """Create final grid configuration"""
        try:
            # Base spacing from Bollinger Band width
            bb_width = bb_data['width']
            base_spacing = bb_width / optimal_params['levels'] if optimal_params['levels'] > 0 else bb_width / 8
            
            # Apply optimization parameters
            spacing_multiplier = optimal_params['spacing_multiplier']
            final_spacing = base_spacing * spacing_multiplier
            
            # Distribute levels based on market context
            total_levels = int(optimal_params['levels'])
            
            if market_context.bollinger_position > 0.3:
                # Price near upper band, favor lower levels
                upper_levels = max(1, int(total_levels * 0.3))
                lower_levels = total_levels - upper_levels
            elif market_context.bollinger_position < -0.3:
                # Price near lower band, favor upper levels
                lower_levels = max(1, int(total_levels * 0.3))
                upper_levels = total_levels - lower_levels
            else:
                # Balanced distribution
                upper_levels = total_levels // 2
                lower_levels = total_levels - upper_levels
            
            return GridConfiguration(
                symbol=symbol,
                base_spacing=base_spacing,
                spacing_multiplier=spacing_multiplier,
                upper_levels=upper_levels,
                lower_levels=lower_levels,
                position_size_multiplier=optimal_params['position_size_multiplier'],
                volatility_adjustment=optimal_params['volatility_adjustment'],
                bb_upper=bb_data['upper'],
                bb_lower=bb_data['lower'],
                bb_middle=bb_data['middle'],
                optimal_score=0.0,  # This would be calculated from GA
                created_at=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Error creating grid configuration: {e}")
            return self._create_default_configuration(symbol)
    
    def _create_default_configuration(self, symbol: str) -> GridConfiguration:
        """Create default grid configuration"""
        return GridConfiguration(
            symbol=symbol,
            base_spacing=0.01,
            spacing_multiplier=1.0,
            upper_levels=5,
            lower_levels=5,
            position_size_multiplier=1.0,
            volatility_adjustment=1.0,
            bb_upper=0,
            bb_lower=0,
            bb_middle=0,
            optimal_score=0.0,
            created_at=datetime.utcnow()
        )
    
    def _create_default_market_context(self) -> MarketRegimeContext:
        """Create default market context"""
        return MarketRegimeContext(
            volatility_regime='medium',
            trend_strength=0.3,
            volume_profile='normal',
            bollinger_position=0.0,
            squeeze_factor=0.5,
            recent_breakouts=0,
            correlation_strength=0.5
        )
    
    def update_performance(self, symbol: str, grid_config: GridConfiguration, performance_score: float):
        """Update performance history for future optimizations"""
        if symbol not in self.performance_history:
            self.performance_history[symbol] = []
        
        self.performance_history[symbol].append(performance_score)
        
        # Keep only recent performance data
        if len(self.performance_history[symbol]) > 50:
            self.performance_history[symbol] = self.performance_history[symbol][-50:]
        
        logger.info(f"Updated performance for {symbol}: {performance_score:.4f}")
    
    def get_optimization_statistics(self, symbol: str) -> Dict[str, Any]:
        """Get optimization statistics for a symbol"""
        performance = self.performance_history.get(symbol, [])
        
        if not performance:
            return {'average_performance': 0, 'best_performance': 0, 'total_optimizations': 0}
        
        return {
            'average_performance': np.mean(performance),
            'best_performance': np.max(performance),
            'worst_performance': np.min(performance),
            'total_optimizations': len(performance),
            'recent_trend': np.mean(performance[-5:]) - np.mean(performance[-10:-5]) if len(performance) >= 10 else 0
        } 