"""
Parameter optimization using genetic algorithms and grid search
to optimize strategy parameters for current market conditions.
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime, timedelta
import asyncio
import json
from pathlib import Path
import random
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class OptimizationResult:
    """Results from parameter optimization."""
    best_params: Dict
    best_score: float
    all_results: List[Dict]
    optimization_time: float
    generations: int
    population_size: int

class ParameterOptimizer:
    """Optimizes strategy parameters using genetic algorithms."""
    
    def __init__(self, backtester, exchange_client):
        self.backtester = backtester
        self.exchange_client = exchange_client
        
        # GA parameters
        self.population_size = 50
        self.generations = 20
        self.mutation_rate = 0.1
        self.crossover_rate = 0.8
        self.elite_size = 5
        
        # Optimization bounds for different strategies
        self.parameter_bounds = {
            'macd': {
                'fast_period': (8, 20),
                'slow_period': (20, 35),
                'signal_period': (5, 15),
                'entry_threshold': (0.001, 0.05),
                'exit_threshold': (0.0005, 0.02)
            },
            'rsi': {
                'period': (10, 20),
                'overbought': (65, 80),
                'oversold': (20, 35),
                'entry_threshold': (0.01, 0.05),
                'exit_threshold': (0.005, 0.02)
            },
            'bollinger': {
                'period': (15, 25),
                'std_dev': (1.5, 2.5),
                'entry_threshold': (0.01, 0.04),
                'exit_threshold': (0.005, 0.02)
            },
            'candle_cluster': {
                'lookback_window': (8, 15),
                'tight_range_factor': (1.5, 3.0),
                'small_body_factor': (0.3, 0.7),
                'target_profit_min': (15, 40),
                'target_profit_max': (25, 50)
            }
        }
        
        # Fitness function weights
        self.fitness_weights = {
            'win_rate': 0.4,
            'profit_factor': 0.3,
            'sharpe_ratio': 0.2,
            'max_drawdown': -0.1  # Negative weight (lower is better)
        }
        
    async def optimize_strategy_parameters(
        self,
        strategy_name: str,
        symbols: List[str],
        optimization_period_days: int = 30,
        validation_period_days: int = 7
    ) -> OptimizationResult:
        """
        Optimize parameters for a specific strategy.
        
        Args:
            strategy_name: Name of strategy to optimize
            symbols: List of symbols to test on
            optimization_period_days: Days of data for optimization
            validation_period_days: Days of data for validation
        """
        logger.info(f"Starting parameter optimization for {strategy_name}")
        start_time = datetime.now()
        
        if strategy_name not in self.parameter_bounds:
            raise ValueError(f"No parameter bounds defined for strategy: {strategy_name}")
            
        # Get historical data for optimization and validation
        opt_end = datetime.now() - timedelta(days=validation_period_days)
        opt_start = opt_end - timedelta(days=optimization_period_days)
        
        val_start = opt_end
        val_end = datetime.now()
        
        logger.info(f"Optimization period: {opt_start} to {opt_end}")
        logger.info(f"Validation period: {val_start} to {val_end}")
        
        # Initialize population
        population = self._initialize_population(strategy_name)
        
        # Evolution loop
        best_individual = None
        best_score = float('-inf')
        all_results = []
        
        for generation in range(self.generations):
            logger.info(f"Generation {generation + 1}/{self.generations}")
            
            # Evaluate population
            fitness_scores = await self._evaluate_population(
                population, strategy_name, symbols, opt_start, opt_end
            )
            
            # Track all results
            for individual, score in zip(population, fitness_scores):
                all_results.append({
                    'generation': generation + 1,
                    'parameters': individual.copy(),
                    'fitness_score': score
                })
            
            # Find best individual
            generation_best_idx = np.argmax(fitness_scores)
            generation_best_score = fitness_scores[generation_best_idx]
            
            if generation_best_score > best_score:
                best_score = generation_best_score
                best_individual = population[generation_best_idx].copy()
                
            logger.info(f"Generation {generation + 1} best score: {generation_best_score:.4f}")
            
            # Create next generation
            if generation < self.generations - 1:
                population = self._create_next_generation(population, fitness_scores)
                
        # Validate best parameters
        logger.info("Validating best parameters...")
        validation_score = await self._validate_parameters(
            best_individual, strategy_name, symbols, val_start, val_end
        )
        
        optimization_time = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"Optimization complete. Best score: {best_score:.4f}, "
                   f"Validation score: {validation_score:.4f}")
        
        return OptimizationResult(
            best_params=best_individual,
            best_score=best_score,
            all_results=all_results,
            optimization_time=optimization_time,
            generations=self.generations,
            population_size=self.population_size
        )
        
    def _initialize_population(self, strategy_name: str) -> List[Dict]:
        """Initialize random population within parameter bounds."""
        population = []
        bounds = self.parameter_bounds[strategy_name]
        
        for _ in range(self.population_size):
            individual = {}
            for param, (min_val, max_val) in bounds.items():
                if isinstance(min_val, int) and isinstance(max_val, int):
                    individual[param] = random.randint(min_val, max_val)
                else:
                    individual[param] = random.uniform(min_val, max_val)
            population.append(individual)
            
        return population
        
    async def _evaluate_population(
        self,
        population: List[Dict],
        strategy_name: str,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime
    ) -> List[float]:
        """Evaluate fitness of entire population."""
        fitness_scores = []
        
        # Use ThreadPoolExecutor for parallel evaluation
        with ThreadPoolExecutor(max_workers=4) as executor:
            tasks = []
            
            for individual in population:
                task = asyncio.create_task(
                    self._evaluate_individual(
                        individual, strategy_name, symbols, start_date, end_date
                    )
                )
                tasks.append(task)
                
            # Wait for all evaluations to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Error evaluating individual: {result}")
                    fitness_scores.append(0.0)
                else:
                    fitness_scores.append(result)
                    
        return fitness_scores
        
    async def _evaluate_individual(
        self,
        parameters: Dict,
        strategy_name: str,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime
    ) -> float:
        """Evaluate fitness of a single individual."""
        try:
            # Create temporary strategy config with these parameters
            temp_config = self._create_temp_strategy_config(strategy_name, parameters)
            
            # Run backtest with these parameters
            backtest_results = await self._run_backtest_with_params(
                temp_config, symbols, start_date, end_date
            )
            
            # Calculate fitness score
            fitness_score = self._calculate_fitness_score(backtest_results)
            
            return fitness_score
            
        except Exception as e:
            logger.debug(f"Error evaluating individual: {e}")
            return 0.0
            
    def _create_temp_strategy_config(self, strategy_name: str, parameters: Dict) -> Dict:
        """Create temporary strategy configuration with given parameters."""
        base_config = {
            'name': f"{strategy_name}_temp",
            'type': strategy_name,
            'parameters': parameters.copy()
        }
        
        # Add default parameters that aren't being optimized
        defaults = {
            'max_position_size': 0.1,
            'max_leverage': 2.0,
            'risk_per_trade': 0.02,
            'confidence_threshold': 0.6
        }
        
        for key, value in defaults.items():
            if key not in base_config['parameters']:
                base_config['parameters'][key] = value
                
        return base_config
        
    async def _run_backtest_with_params(
        self,
        strategy_config: Dict,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """Run backtest with specific parameters."""
        try:
            # This would integrate with your existing backtester
            # For now, simulate some results
            
            # Calculate some metrics based on parameters
            # This is a simplified version - you'd use your actual backtester
            
            total_trades = random.randint(10, 50)
            win_rate = random.uniform(0.3, 0.7)
            winning_trades = int(total_trades * win_rate)
            
            avg_win = random.uniform(20, 100)
            avg_loss = random.uniform(-50, -10)
            
            total_pnl = (winning_trades * avg_win) + ((total_trades - winning_trades) * avg_loss)
            
            profit_factor = abs((winning_trades * avg_win) / ((total_trades - winning_trades) * avg_loss)) if total_trades > winning_trades else 1.0
            
            returns = [random.uniform(-5, 5) for _ in range(total_trades)]
            sharpe_ratio = np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0
            
            max_drawdown = random.uniform(0.05, 0.25)
            
            return {
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'win_rate': win_rate,
                'total_pnl': total_pnl,
                'profit_factor': profit_factor,
                'sharpe_ratio': sharpe_ratio,
                'max_drawdown': max_drawdown
            }
            
        except Exception as e:
            logger.error(f"Error running backtest: {e}")
            return {}
            
    def _calculate_fitness_score(self, backtest_results: Dict) -> float:
        """Calculate fitness score from backtest results."""
        try:
            if not backtest_results:
                return 0.0
                
            score = 0.0
            
            # Win rate component
            win_rate = backtest_results.get('win_rate', 0)
            score += win_rate * self.fitness_weights['win_rate']
            
            # Profit factor component (normalize to 0-1)
            profit_factor = backtest_results.get('profit_factor', 0)
            normalized_pf = min(1.0, profit_factor / 3.0)  # Cap at 3.0
            score += normalized_pf * self.fitness_weights['profit_factor']
            
            # Sharpe ratio component (normalize to 0-1)
            sharpe_ratio = backtest_results.get('sharpe_ratio', 0)
            normalized_sharpe = max(0, min(1.0, (sharpe_ratio + 1) / 3))  # Map [-1,2] to [0,1]
            score += normalized_sharpe * self.fitness_weights['sharpe_ratio']
            
            # Max drawdown component (lower is better)
            max_drawdown = backtest_results.get('max_drawdown', 0)
            score += max_drawdown * self.fitness_weights['max_drawdown']
            
            # Minimum trades penalty
            total_trades = backtest_results.get('total_trades', 0)
            if total_trades < 10:
                score *= 0.5  # Penalize if too few trades
                
            return max(0.0, score)
            
        except Exception as e:
            logger.error(f"Error calculating fitness score: {e}")
            return 0.0
            
    def _create_next_generation(
        self, 
        population: List[Dict], 
        fitness_scores: List[float]
    ) -> List[Dict]:
        """Create next generation using selection, crossover, and mutation."""
        next_generation = []
        
        # Sort by fitness (descending)
        sorted_indices = np.argsort(fitness_scores)[::-1]
        
        # Elitism - keep best individuals
        for i in range(self.elite_size):
            next_generation.append(population[sorted_indices[i]].copy())
            
        # Fill rest with crossover and mutation
        while len(next_generation) < self.population_size:
            # Selection (tournament selection)
            parent1 = self._tournament_selection(population, fitness_scores)
            parent2 = self._tournament_selection(population, fitness_scores)
            
            # Crossover
            if random.random() < self.crossover_rate:
                child1, child2 = self._crossover(parent1, parent2)
            else:
                child1, child2 = parent1.copy(), parent2.copy()
                
            # Mutation
            child1 = self._mutate(child1, list(parent1.keys())[0])  # Get strategy name from first param
            child2 = self._mutate(child2, list(parent1.keys())[0])
            
            next_generation.extend([child1, child2])
            
        # Trim to exact population size
        return next_generation[:self.population_size]
        
    def _tournament_selection(
        self, 
        population: List[Dict], 
        fitness_scores: List[float],
        tournament_size: int = 3
    ) -> Dict:
        """Tournament selection for parent selection."""
        tournament_indices = random.sample(range(len(population)), tournament_size)
        tournament_fitness = [fitness_scores[i] for i in tournament_indices]
        winner_idx = tournament_indices[np.argmax(tournament_fitness)]
        return population[winner_idx].copy()
        
    def _crossover(self, parent1: Dict, parent2: Dict) -> Tuple[Dict, Dict]:
        """Single-point crossover."""
        child1, child2 = parent1.copy(), parent2.copy()
        
        params = list(parent1.keys())
        if len(params) > 1:
            crossover_point = random.randint(1, len(params) - 1)
            
            for i, param in enumerate(params):
                if i >= crossover_point:
                    child1[param], child2[param] = child2[param], child1[param]
                    
        return child1, child2
        
    def _mutate(self, individual: Dict, strategy_name: str) -> Dict:
        """Mutate individual parameters."""
        mutated = individual.copy()
        bounds = self.parameter_bounds.get(strategy_name, {})
        
        for param in mutated:
            if random.random() < self.mutation_rate:
                if param in bounds:
                    min_val, max_val = bounds[param]
                    if isinstance(min_val, int) and isinstance(max_val, int):
                        mutated[param] = random.randint(min_val, max_val)
                    else:
                        # Gaussian mutation around current value
                        current_val = mutated[param]
                        mutation_range = (max_val - min_val) * 0.1  # 10% of range
                        new_val = current_val + random.gauss(0, mutation_range)
                        mutated[param] = max(min_val, min(max_val, new_val))
                        
        return mutated
        
    async def _validate_parameters(
        self,
        parameters: Dict,
        strategy_name: str,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime
    ) -> float:
        """Validate optimized parameters on out-of-sample data."""
        try:
            validation_results = await self._evaluate_individual(
                parameters, strategy_name, symbols, start_date, end_date
            )
            return validation_results
            
        except Exception as e:
            logger.error(f"Error validating parameters: {e}")
            return 0.0
            
    def save_optimization_results(self, result: OptimizationResult, filename: str = None):
        """Save optimization results to file."""
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"optimization_results_{timestamp}.json"
            
        results_dir = Path('data/optimization_results')
        results_dir.mkdir(parents=True, exist_ok=True)
        
        filepath = results_dir / filename
        
        # Convert to serializable format
        serializable_result = {
            'best_params': result.best_params,
            'best_score': result.best_score,
            'all_results': result.all_results,
            'optimization_time': result.optimization_time,
            'generations': result.generations,
            'population_size': result.population_size,
            'timestamp': datetime.now().isoformat()
        }
        
        with open(filepath, 'w') as f:
            json.dump(serializable_result, f, indent=2)
            
        logger.info(f"Optimization results saved to {filepath}")
        return filepath
        
    def grid_search_optimization(
        self,
        strategy_name: str,
        param_grids: Dict[str, List],
        symbols: List[str],
        start_date: datetime,
        end_date: datetime
    ) -> OptimizationResult:
        """Alternative optimization using grid search."""
        logger.info(f"Starting grid search optimization for {strategy_name}")
        start_time = datetime.now()
        
        # Generate all parameter combinations
        param_names = list(param_grids.keys())
        param_values = list(param_grids.values())
        
        from itertools import product
        all_combinations = list(product(*param_values))
        
        logger.info(f"Testing {len(all_combinations)} parameter combinations")
        
        best_params = None
        best_score = float('-inf')
        all_results = []
        
        for i, combination in enumerate(all_combinations):
            params = dict(zip(param_names, combination))
            
            # Evaluate this combination
            score = asyncio.run(self._evaluate_individual(
                params, strategy_name, symbols, start_date, end_date
            ))
            
            all_results.append({
                'combination': i + 1,
                'parameters': params,
                'fitness_score': score
            })
            
            if score > best_score:
                best_score = score
                best_params = params.copy()
                
            if (i + 1) % 10 == 0:
                logger.info(f"Completed {i + 1}/{len(all_combinations)} combinations")
                
        optimization_time = (datetime.now() - start_time).total_seconds()
        
        return OptimizationResult(
            best_params=best_params,
            best_score=best_score,
            all_results=all_results,
            optimization_time=optimization_time,
            generations=1,  # Grid search is single generation
            population_size=len(all_combinations)
        ) 