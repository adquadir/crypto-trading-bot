#!/usr/bin/env python3
"""
🚀 Backtesting Engine Test Suite

This script demonstrates the backtesting engine capabilities:
- Strategy performance testing
- Market regime analysis
- Strategy comparison
- Parameter optimization
"""

import asyncio
import logging
from datetime import datetime, timedelta
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.backtesting.backtest_runner import BacktestRunner, quick_backtest, compare_all_strategies
from src.backtesting.strategy_analyzer import StrategyAnalyzer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_quick_backtest():
    """Test quick backtesting functionality"""
    print("\n" + "="*60)
    print("🚀 TESTING QUICK BACKTEST")
    print("="*60)
    
    try:
        # Test trend following strategy
        performance = await quick_backtest("trend_following", "BTCUSDT")
        
        print(f"✅ Quick backtest completed successfully")
        print(f"📊 Strategy: trend_following")
        print(f"💰 Return: {performance.total_return:.1%}")
        print(f"🎯 Win Rate: {performance.win_rate:.1%}")
        
        return True
        
    except Exception as e:
        print(f"❌ Quick backtest failed: {e}")
        return False

async def test_strategy_comparison():
    """Test strategy comparison functionality"""
    print("\n" + "="*60)
    print("⚔️ TESTING STRATEGY COMPARISON")
    print("="*60)
    
    try:
        comparison_df = await compare_all_strategies("BTCUSDT")
        
        print(f"✅ Strategy comparison completed")
        print(f"📊 Compared {len(comparison_df)} strategies")
        
        return True
        
    except Exception as e:
        print(f"❌ Strategy comparison failed: {e}")
        return False

async def test_comprehensive_backtest():
    """Test comprehensive backtesting across multiple strategies and symbols"""
    print("\n" + "="*60)
    print("🎯 TESTING COMPREHENSIVE BACKTEST")
    print("="*60)
    
    try:
        runner = BacktestRunner(initial_balance=10000)
        
        strategies = ['trend_following', 'breakout', 'mean_reversion']
        symbols = ['BTCUSDT', 'ETHUSDT']
        
        results = await runner.run_comprehensive_backtest(
            strategies=strategies,
            symbols=symbols,
            days_back=30  # Shorter period for testing
        )
        
        print(f"✅ Comprehensive backtest completed")
        print(f"📊 Tested {len(strategies)} strategies on {len(symbols)} symbols")
        
        # Show best performer
        best_strategy = runner.get_best_strategy()
        print(f"🏆 Best strategy: {best_strategy}")
        
        return True
        
    except Exception as e:
        print(f"❌ Comprehensive backtest failed: {e}")
        return False

async def test_market_regime_analysis():
    """Test market regime analysis"""
    print("\n" + "="*60)
    print("📈 TESTING MARKET REGIME ANALYSIS")
    print("="*60)
    
    try:
        runner = BacktestRunner()
        
        regime_analysis = await runner.run_market_regime_analysis(
            strategy="trend_following",
            symbol="BTCUSDT",
            days_back=60
        )
        
        print(f"✅ Market regime analysis completed")
        print(f"📊 Analyzed {len(regime_analysis)} market regimes")
        
        return True
        
    except Exception as e:
        print(f"❌ Market regime analysis failed: {e}")
        return False

async def test_strategy_analyzer():
    """Test detailed strategy analysis"""
    print("\n" + "="*60)
    print("🔍 TESTING STRATEGY ANALYZER")
    print("="*60)
    
    try:
        analyzer = StrategyAnalyzer()
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        analysis = await analyzer.analyze_strategy_performance(
            strategy_name="trend_following",
            symbol="BTCUSDT",
            start_date=start_date,
            end_date=end_date
        )
        
        print(f"✅ Strategy analysis completed")
        print(f"📊 Generated {len(analysis)} analysis components")
        
        # Show insights
        insights = analysis.get('insights', [])
        if insights:
            print(f"💡 Generated {len(insights)} insights")
            for insight in insights[:3]:  # Show first 3
                print(f"   • {insight}")
        
        # Generate report
        report = analyzer.generate_report("trend_following_BTCUSDT")
        print(f"📝 Generated analysis report ({len(report)} characters)")
        
        return True
        
    except Exception as e:
        print(f"❌ Strategy analysis failed: {e}")
        return False

async def test_parameter_optimization():
    """Test parameter optimization"""
    print("\n" + "="*60)
    print("🔧 TESTING PARAMETER OPTIMIZATION")
    print("="*60)
    
    try:
        analyzer = StrategyAnalyzer()
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        # Test optimization of a hypothetical parameter
        optimization = await analyzer.optimize_parameters(
            strategy_name="trend_following",
            symbol="BTCUSDT",
            parameter_name="atr_multiplier",
            parameter_range=[1.5, 2.0, 2.5, 3.0],
            start_date=start_date,
            end_date=end_date
        )
        
        print(f"✅ Parameter optimization completed")
        print(f"🔧 Optimized parameter: {optimization.parameter_name}")
        print(f"🎯 Best value: {optimization.best_value}")
        print(f"📊 Best performance: {optimization.best_performance:.4f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Parameter optimization failed: {e}")
        return False

async def test_export_functionality():
    """Test result export functionality"""
    print("\n" + "="*60)
    print("💾 TESTING EXPORT FUNCTIONALITY")
    print("="*60)
    
    try:
        runner = BacktestRunner()
        
        # Run a quick backtest to generate results
        await runner.run_quick_backtest("trend_following", "BTCUSDT")
        
        # Export results
        export_file = runner.export_all_results("test_backtest_results.json")
        
        print(f"✅ Export completed")
        print(f"📁 Results exported to: {export_file}")
        
        # Check if file exists
        if os.path.exists(export_file):
            file_size = os.path.getsize(export_file)
            print(f"📊 File size: {file_size} bytes")
            
            # Clean up test file
            os.remove(export_file)
            print(f"🧹 Cleaned up test file")
        
        return True
        
    except Exception as e:
        print(f"❌ Export test failed: {e}")
        return False

async def run_performance_benchmark():
    """Benchmark backtesting performance"""
    print("\n" + "="*60)
    print("⚡ PERFORMANCE BENCHMARK")
    print("="*60)
    
    try:
        start_time = datetime.now()
        
        # Run multiple backtests to measure performance
        runner = BacktestRunner()
        
        # Test 1: Single strategy, single symbol
        await runner.run_quick_backtest("trend_following", "BTCUSDT")
        
        # Test 2: Multiple strategies
        await runner.run_strategy_comparison(["trend_following", "breakout"])
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print(f"✅ Performance benchmark completed")
        print(f"⏱️ Total time: {duration:.2f} seconds")
        print(f"🚀 Average time per backtest: {duration/2:.2f} seconds")
        
        return True
        
    except Exception as e:
        print(f"❌ Performance benchmark failed: {e}")
        return False

async def main():
    """Run all backtesting tests"""
    print("🚀 BACKTESTING ENGINE TEST SUITE")
    print("="*80)
    
    tests = [
        ("Quick Backtest", test_quick_backtest),
        ("Strategy Comparison", test_strategy_comparison),
        ("Comprehensive Backtest", test_comprehensive_backtest),
        ("Market Regime Analysis", test_market_regime_analysis),
        ("Strategy Analyzer", test_strategy_analyzer),
        ("Parameter Optimization", test_parameter_optimization),
        ("Export Functionality", test_export_functionality),
        ("Performance Benchmark", run_performance_benchmark)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n🔄 Running {test_name}...")
        try:
            success = await test_func()
            results[test_name] = "✅ PASSED" if success else "❌ FAILED"
        except Exception as e:
            print(f"💥 {test_name} crashed: {e}")
            results[test_name] = "💥 CRASHED"
    
    # Final summary
    print("\n" + "="*80)
    print("📊 TEST RESULTS SUMMARY")
    print("="*80)
    
    passed = sum(1 for result in results.values() if "PASSED" in result)
    total = len(results)
    
    for test_name, result in results.items():
        print(f"{result} {test_name}")
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED! Backtesting engine is ready for production.")
    else:
        print("⚠️ Some tests failed. Review the output above for details.")
    
    print("="*80)

if __name__ == "__main__":
    asyncio.run(main()) 