"""
🚀 Backtest Runner - Execute Strategy Backtests

This script provides easy-to-use functions to run backtests
on your trading strategies with different configurations.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict
import pandas as pd

from .backtest_engine import BacktestEngine, StrategyPerformance

logger = logging.getLogger(__name__)

class BacktestRunner:
    """
    🎯 Easy-to-use backtest runner for strategy validation
    """
    
    def __init__(self, initial_balance: float = 10000.0):
        self.engine = BacktestEngine(initial_balance)
        self.results = {}
    
    async def run_quick_backtest(
        self,
        strategy: str = "trend_following",
        symbol: str = "BTCUSDT",
        days_back: int = 30
    ) -> StrategyPerformance:
        """
        🚀 Quick backtest for immediate strategy validation
        
        Args:
            strategy: Strategy to test ('trend_following', 'breakout', 'mean_reversion')
            symbol: Trading pair to test
            days_back: How many days of history to test
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        logger.info(f"🔄 Running quick backtest: {strategy} on {symbol}")
        logger.info(f"📅 Testing last {days_back} days")
        
        performance = await self.engine.run_strategy_backtest(
            strategy, symbol, start_date, end_date
        )
        
        # Store results
        self.results[f"{strategy}_{symbol}"] = performance
        
        # Print summary
        self._print_performance_summary(performance)
        
        return performance
    
    async def run_comprehensive_backtest(
        self,
        strategies: List[str] = None,
        symbols: List[str] = None,
        days_back: int = 90
    ) -> Dict[str, Dict[str, StrategyPerformance]]:
        """
        🎯 Comprehensive backtest across multiple strategies and symbols
        """
        if strategies is None:
            strategies = ['trend_following', 'breakout', 'mean_reversion']
        
        if symbols is None:
            symbols = ['BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'SOLUSDT']
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        logger.info(f"🔄 Running comprehensive backtest")
        logger.info(f"📊 Strategies: {strategies}")
        logger.info(f"💰 Symbols: {symbols}")
        logger.info(f"📅 Period: {days_back} days")
        
        results = await self.engine.run_multi_strategy_backtest(
            strategies, symbols, start_date, end_date
        )
        
        # Store results
        self.results.update({
            f"{strategy}_{symbol}": performance
            for strategy, symbol_results in results.items()
            for symbol, performance in symbol_results.items()
        })
        
        # Print comprehensive summary
        self._print_comprehensive_summary(results)
        
        return results
    
    async def run_market_regime_analysis(
        self,
        strategy: str = "trend_following",
        symbol: str = "BTCUSDT",
        days_back: int = 180
    ) -> Dict[str, Dict[str, float]]:
        """
        📈 Analyze strategy performance across different market conditions
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        logger.info(f"📊 Analyzing {strategy} performance across market regimes")
        
        regime_analysis = await self.engine.market_regime_analysis(
            strategy, symbol, start_date, end_date
        )
        
        # Print regime analysis
        self._print_regime_analysis(regime_analysis)
        
        return regime_analysis
    
    async def run_strategy_comparison(
        self,
        strategies: List[str] = None,
        symbol: str = "BTCUSDT",
        days_back: int = 60
    ) -> pd.DataFrame:
        """
        ⚡ Compare multiple strategies head-to-head
        """
        if strategies is None:
            strategies = ['trend_following', 'breakout', 'mean_reversion']
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        logger.info(f"⚔️ Strategy comparison on {symbol}")
        
        comparison = await self.engine.compare_strategies(
            strategies, symbol, start_date, end_date
        )
        
        # Print comparison table
        print("\n" + "="*80)
        print(f"📊 STRATEGY COMPARISON - {symbol} ({days_back} days)")
        print("="*80)
        print(comparison.to_string(index=False))
        print("="*80)
        
        return comparison
    
    def _print_performance_summary(self, performance: StrategyPerformance):
        """Print formatted performance summary"""
        print("\n" + "="*60)
        print(f"📊 BACKTEST RESULTS - {performance.strategy_name}")
        print("="*60)
        
        print(f"💰 Total Return: {performance.total_return:.1%}")
        print(f"🎯 Win Rate: {performance.win_rate:.1%}")
        print(f"📈 Total Trades: {performance.total_trades}")
        print(f"⚡ Avg Return/Trade: {performance.avg_return_per_trade:.2%}")
        
        print(f"\n📊 Risk Metrics:")
        print(f"   Max Drawdown: {performance.max_drawdown:.1%}")
        print(f"   Sharpe Ratio: {performance.sharpe_ratio:.2f}")
        print(f"   Profit Factor: {performance.profit_factor:.2f}")
        
        print(f"\n🎲 Trade Analysis:")
        print(f"   Avg Winner: ${performance.avg_winning_trade:.2f}")
        print(f"   Avg Loser: ${performance.avg_losing_trade:.2f}")
        print(f"   Best Trade: ${performance.best_trade:.2f}")
        print(f"   Worst Trade: ${performance.worst_trade:.2f}")
        
        print(f"\n⏱️ Duration: {performance.avg_trade_duration:.0f} minutes")
        print(f"🎯 Avg Confidence: {performance.avg_confidence:.1%}")
        
        # Performance rating
        rating = self._calculate_strategy_rating(performance)
        print(f"\n⭐ Strategy Rating: {rating}")
        print("="*60)
    
    def _print_comprehensive_summary(self, results: Dict[str, Dict[str, StrategyPerformance]]):
        """Print comprehensive backtest summary"""
        print("\n" + "="*80)
        print("🎯 COMPREHENSIVE BACKTEST SUMMARY")
        print("="*80)
        
        # Create summary table
        summary_data = []
        
        for strategy, symbol_results in results.items():
            for symbol, performance in symbol_results.items():
                summary_data.append({
                    'Strategy': strategy,
                    'Symbol': symbol,
                    'Win Rate': f"{performance.win_rate:.1%}",
                    'Total Return': f"{performance.total_return:.1%}",
                    'Trades': performance.total_trades,
                    'Sharpe': f"{performance.sharpe_ratio:.2f}",
                    'Max DD': f"{performance.max_drawdown:.1%}",
                    'Rating': self._calculate_strategy_rating(performance)
                })
        
        df = pd.DataFrame(summary_data)
        print(df.to_string(index=False))
        
        # Best performers
        print(f"\n🏆 BEST PERFORMERS:")
        best_return = max(results.items(), 
                         key=lambda x: max(p.total_return for p in x[1].values()))
        best_winrate = max(results.items(), 
                          key=lambda x: max(p.win_rate for p in x[1].values()))
        
        print(f"   Highest Return: {best_return[0]}")
        print(f"   Highest Win Rate: {best_winrate[0]}")
        
        print("="*80)
    
    def _print_regime_analysis(self, regime_analysis: Dict[str, Dict[str, float]]):
        """Print market regime analysis"""
        print("\n" + "="*60)
        print("📈 MARKET REGIME ANALYSIS")
        print("="*60)
        
        for regime, metrics in regime_analysis.items():
            print(f"\n{regime.upper()} Markets:")
            print(f"   Trades: {metrics['trades']}")
            print(f"   Win Rate: {metrics['win_rate']:.1%}")
            print(f"   Avg Return: {metrics['avg_return']:.2%}")
            print(f"   Total P&L: ${metrics['total_pnl']:.2f}")
        
        print("="*60)
    
    def _calculate_strategy_rating(self, performance: StrategyPerformance) -> str:
        """Calculate strategy rating based on performance metrics"""
        score = 0
        
        # Win rate scoring
        if performance.win_rate >= 0.7:
            score += 3
        elif performance.win_rate >= 0.6:
            score += 2
        elif performance.win_rate >= 0.5:
            score += 1
        
        # Return scoring
        if performance.total_return >= 0.2:  # 20%+
            score += 3
        elif performance.total_return >= 0.1:  # 10%+
            score += 2
        elif performance.total_return > 0:
            score += 1
        
        # Sharpe ratio scoring
        if performance.sharpe_ratio >= 2.0:
            score += 3
        elif performance.sharpe_ratio >= 1.0:
            score += 2
        elif performance.sharpe_ratio >= 0.5:
            score += 1
        
        # Profit factor scoring
        if performance.profit_factor >= 2.0:
            score += 2
        elif performance.profit_factor >= 1.5:
            score += 1
        
        # Max drawdown penalty
        if performance.max_drawdown <= 0.05:  # 5%
            score += 1
        elif performance.max_drawdown >= 0.2:  # 20%
            score -= 2
        
        # Convert to rating
        if score >= 10:
            return "⭐⭐⭐⭐⭐ EXCELLENT"
        elif score >= 8:
            return "⭐⭐⭐⭐ VERY GOOD"
        elif score >= 6:
            return "⭐⭐⭐ GOOD"
        elif score >= 4:
            return "⭐⭐ FAIR"
        elif score >= 2:
            return "⭐ POOR"
        else:
            return "❌ AVOID"
    
    def export_all_results(self, filename: str = None) -> str:
        """Export all backtest results"""
        return self.engine.export_results(filename)
    
    def get_best_strategy(self) -> str:
        """Get the best performing strategy from recent backtests"""
        if not self.results:
            return "No backtests run yet"
        
        best_strategy = max(
            self.results.items(),
            key=lambda x: x[1].total_return * x[1].win_rate  # Combined score
        )
        
        return best_strategy[0]

# Convenience functions for quick backtesting
async def quick_backtest(strategy: str = "trend_following", symbol: str = "BTCUSDT") -> StrategyPerformance:
    """🚀 Run a quick backtest with default settings"""
    runner = BacktestRunner()
    return await runner.run_quick_backtest(strategy, symbol)

async def compare_all_strategies(symbol: str = "BTCUSDT") -> pd.DataFrame:
    """⚔️ Compare all available strategies"""
    runner = BacktestRunner()
    return await runner.run_strategy_comparison(symbol=symbol)

async def full_analysis(days_back: int = 90) -> Dict:
    """🎯 Run complete analysis with all strategies and symbols"""
    runner = BacktestRunner()
    
    # Run comprehensive backtest
    results = await runner.run_comprehensive_backtest(days_back=days_back)
    
    # Export results
    filename = runner.export_all_results()
    
    return {
        'results': results,
        'best_strategy': runner.get_best_strategy(),
        'export_file': filename
    }

if __name__ == "__main__":
    # Example usage
    async def main():
        print("🚀 Starting Backtest Analysis...")
        
        # Quick test
        print("\n1. Quick Backtest:")
        await quick_backtest("trend_following", "BTCUSDT")
        
        # Strategy comparison
        print("\n2. Strategy Comparison:")
        await compare_all_strategies("BTCUSDT")
        
        # Full analysis
        print("\n3. Full Analysis:")
        analysis = await full_analysis(60)
        print(f"Best Strategy: {analysis['best_strategy']}")
        print(f"Results exported to: {analysis['export_file']}")
    
    asyncio.run(main()) 