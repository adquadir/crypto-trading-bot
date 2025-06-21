#!/usr/bin/env python3
"""
🎯 Backtesting Demo - Live Demonstration

This script shows the backtesting engine in action with real examples.
"""

import asyncio
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.backtesting.backtest_runner import BacktestRunner

async def demo_single_strategy():
    """Demo: Test a single strategy"""
    print("🚀 DEMO 1: Single Strategy Backtest")
    print("="*50)
    
    runner = BacktestRunner(initial_balance=10000)
    
    print("Testing Trend Following strategy on BTCUSDT...")
    performance = await runner.run_quick_backtest(
        strategy="trend_following",
        symbol="BTCUSDT",
        days_back=14
    )
    
    print(f"\n📊 RESULTS:")
    print(f"   💰 Total Return: {performance.total_return:.1%}")
    print(f"   🎯 Win Rate: {performance.win_rate:.1%}")
    print(f"   📈 Total Trades: {performance.total_trades}")
    print(f"   ⚡ Avg Return/Trade: {performance.avg_return_per_trade:.2%}")
    print(f"   📉 Max Drawdown: {performance.max_drawdown:.1%}")
    print(f"   📊 Sharpe Ratio: {performance.sharpe_ratio:.2f}")
    
    # Strategy rating
    if performance.win_rate > 0.6 and performance.total_return > 0.1:
        print(f"   ⭐ Rating: EXCELLENT - Deploy immediately!")
    elif performance.win_rate > 0.5 and performance.total_return > 0:
        print(f"   ⭐ Rating: GOOD - Consider deployment")
    else:
        print(f"   ⭐ Rating: NEEDS WORK - Don't deploy yet")

async def demo_strategy_comparison():
    """Demo: Compare multiple strategies"""
    print("\n\n⚔️ DEMO 2: Strategy Battle Royale")
    print("="*50)
    
    runner = BacktestRunner()
    
    strategies = ["trend_following", "breakout", "mean_reversion"]
    print(f"Comparing {len(strategies)} strategies on BTCUSDT...")
    
    comparison = await runner.run_strategy_comparison(
        strategies=strategies,
        symbol="BTCUSDT",
        days_back=14
    )
    
    print(f"\n🏆 STRATEGY COMPARISON RESULTS:")
    print(comparison.to_string(index=False))
    
    # Find winner
    best_return = comparison.loc[comparison['Total Return'].str.rstrip('%').astype(float).idxmax()]
    best_winrate = comparison.loc[comparison['Win Rate'].str.rstrip('%').astype(float).idxmax()]
    
    print(f"\n🥇 WINNERS:")
    print(f"   💰 Highest Return: {best_return['Strategy']} ({best_return['Total Return']})")
    print(f"   🎯 Highest Win Rate: {best_winrate['Strategy']} ({best_winrate['Win Rate']})")

async def demo_market_regime_analysis():
    """Demo: Market regime analysis"""
    print("\n\n📈 DEMO 3: Market Regime Analysis")
    print("="*50)
    
    runner = BacktestRunner()
    
    print("Analyzing Trend Following across different market conditions...")
    
    regime_analysis = await runner.run_market_regime_analysis(
        strategy="trend_following",
        symbol="BTCUSDT",
        days_back=30
    )
    
    print(f"\n🌍 MARKET REGIME PERFORMANCE:")
    for regime, metrics in regime_analysis.items():
        if metrics['trades'] > 0:
            print(f"   {regime.upper():<12} | "
                  f"Trades: {metrics['trades']:<3} | "
                  f"Win Rate: {metrics['win_rate']:.1%} | "
                  f"Avg Return: {metrics['avg_return']:.2%}")
    
    # Find best regime
    best_regime = max(
        [(k, v) for k, v in regime_analysis.items() if v['trades'] > 0],
        key=lambda x: x[1]['win_rate']
    )
    
    print(f"\n🎯 BEST MARKET CONDITIONS:")
    print(f"   Strategy performs best in {best_regime[0].upper()} markets")
    print(f"   Win Rate: {best_regime[1]['win_rate']:.1%}")
    print(f"   Avg Return: {best_regime[1]['avg_return']:.2%}")

async def demo_comprehensive_analysis():
    """Demo: Full comprehensive analysis"""
    print("\n\n🎯 DEMO 4: Comprehensive Analysis")
    print("="*50)
    
    runner = BacktestRunner()
    
    strategies = ["trend_following", "breakout"]
    symbols = ["BTCUSDT", "ETHUSDT"]
    
    print(f"Running comprehensive analysis...")
    print(f"   Strategies: {strategies}")
    print(f"   Symbols: {symbols}")
    print(f"   Period: 14 days")
    
    results = await runner.run_comprehensive_backtest(
        strategies=strategies,
        symbols=symbols,
        days_back=14
    )
    
    print(f"\n📊 COMPREHENSIVE RESULTS:")
    
    # Summary table
    for strategy, symbol_results in results.items():
        print(f"\n   {strategy.upper()}:")
        for symbol, performance in symbol_results.items():
            print(f"      {symbol}: {performance.win_rate:.1%} win rate, "
                  f"{performance.total_return:.1%} return")
    
    # Best overall
    best_combo = None
    best_score = -999
    
    for strategy, symbol_results in results.items():
        for symbol, performance in symbol_results.items():
            score = performance.total_return * performance.win_rate
            if score > best_score:
                best_score = score
                best_combo = (strategy, symbol, performance)
    
    if best_combo:
        strategy, symbol, perf = best_combo
        print(f"\n🏆 BEST COMBINATION:")
        print(f"   Strategy: {strategy}")
        print(f"   Symbol: {symbol}")
        print(f"   Win Rate: {perf.win_rate:.1%}")
        print(f"   Return: {perf.total_return:.1%}")
        print(f"   Score: {best_score:.4f}")

async def demo_export_results():
    """Demo: Export functionality"""
    print("\n\n💾 DEMO 5: Export Results")
    print("="*50)
    
    runner = BacktestRunner()
    
    # Run a quick test
    print("Running backtest for export...")
    await runner.run_quick_backtest("trend_following", "BTCUSDT", days_back=7)
    
    # Export results
    filename = runner.export_all_results("demo_backtest_results.json")
    
    print(f"✅ Results exported to: {filename}")
    
    # Check file
    if os.path.exists(filename):
        file_size = os.path.getsize(filename)
        print(f"📁 File size: {file_size:,} bytes")
        
        # Show sample of content
        with open(filename, 'r') as f:
            content = f.read()[:200]
            print(f"📄 Sample content: {content}...")
        
        print(f"🔗 You can now analyze this data in Excel, Python, or any JSON viewer")
        
        # Clean up demo file
        os.remove(filename)
        print(f"🧹 Demo file cleaned up")

async def main():
    """Run all backtesting demos"""
    print("🎯 BACKTESTING ENGINE LIVE DEMO")
    print("="*60)
    print("This demo shows the backtesting engine capabilities")
    print("using simulated market data for demonstration.")
    print("="*60)
    
    demos = [
        demo_single_strategy,
        demo_strategy_comparison,
        demo_market_regime_analysis,
        demo_comprehensive_analysis,
        demo_export_results
    ]
    
    for i, demo in enumerate(demos, 1):
        try:
            await demo()
        except Exception as e:
            print(f"❌ Demo {i} failed: {e}")
    
    print("\n" + "="*60)
    print("🎉 DEMO COMPLETE!")
    print("="*60)
    print("Key Takeaways:")
    print("✅ Backtesting validates strategies before live trading")
    print("✅ Compare multiple strategies to find the best")
    print("✅ Analyze performance across market conditions")
    print("✅ Export results for further analysis")
    print("✅ Make data-driven trading decisions")
    print("\n🚀 Ready to backtest your own strategies!")

if __name__ == "__main__":
    asyncio.run(main()) 