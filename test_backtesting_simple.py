#!/usr/bin/env python3
"""
🚀 Simple Backtesting Test

Basic test to validate backtesting engine functionality
without complex dependencies.
"""

import asyncio
import logging
from datetime import datetime, timedelta
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.backtesting.backtest_engine import BacktestEngine
from src.backtesting.backtest_runner import BacktestRunner

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_basic_engine():
    """Test basic backtesting engine functionality"""
    print("🔄 Testing Basic Backtesting Engine...")
    
    try:
        engine = BacktestEngine(initial_balance=10000)
        
        # Test with simulated data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        performance = await engine.run_strategy_backtest(
            strategy_name="trend_following",
            symbol="BTCUSDT",
            start_date=start_date,
            end_date=end_date
        )
        
        print(f"✅ Basic engine test passed")
        print(f"   Strategy: trend_following")
        print(f"   Total Return: {performance.total_return:.2%}")
        print(f"   Win Rate: {performance.win_rate:.1%}")
        print(f"   Total Trades: {performance.total_trades}")
        
        return True
        
    except Exception as e:
        print(f"❌ Basic engine test failed: {e}")
        return False

async def test_runner():
    """Test backtesting runner"""
    print("\n🔄 Testing Backtest Runner...")
    
    try:
        runner = BacktestRunner(initial_balance=10000)
        
        performance = await runner.run_quick_backtest(
            strategy="trend_following",
            symbol="BTCUSDT",
            days_back=7
        )
        
        print(f"✅ Runner test passed")
        print(f"   Total Return: {performance.total_return:.2%}")
        print(f"   Sharpe Ratio: {performance.sharpe_ratio:.2f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Runner test failed: {e}")
        return False

async def test_multiple_strategies():
    """Test multiple strategy comparison"""
    print("\n🔄 Testing Multiple Strategies...")
    
    try:
        runner = BacktestRunner()
        
        strategies = ["trend_following", "breakout"]
        comparison = await runner.run_strategy_comparison(
            strategies=strategies,
            symbol="BTCUSDT",
            days_back=7
        )
        
        print(f"✅ Multiple strategy test passed")
        print(f"   Compared {len(comparison)} strategies")
        
        return True
        
    except Exception as e:
        print(f"❌ Multiple strategy test failed: {e}")
        return False

async def test_export():
    """Test result export"""
    print("\n🔄 Testing Export Functionality...")
    
    try:
        runner = BacktestRunner()
        
        # Run a quick test
        await runner.run_quick_backtest("trend_following", "BTCUSDT", days_back=3)
        
        # Export results
        filename = runner.export_all_results("test_export.json")
        
        # Check if file exists
        if os.path.exists(filename):
            file_size = os.path.getsize(filename)
            print(f"✅ Export test passed")
            print(f"   File: {filename}")
            print(f"   Size: {file_size} bytes")
            
            # Clean up
            os.remove(filename)
            return True
        else:
            print(f"❌ Export file not created")
            return False
            
    except Exception as e:
        print(f"❌ Export test failed: {e}")
        return False

async def main():
    """Run simple backtesting tests"""
    print("🚀 SIMPLE BACKTESTING TEST SUITE")
    print("="*50)
    
    tests = [
        ("Basic Engine", test_basic_engine),
        ("Runner", test_runner),
        ("Multiple Strategies", test_multiple_strategies),
        ("Export", test_export)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            success = await test_func()
            results[test_name] = "✅ PASSED" if success else "❌ FAILED"
        except Exception as e:
            print(f"💥 {test_name} crashed: {e}")
            results[test_name] = "💥 CRASHED"
    
    # Summary
    print("\n" + "="*50)
    print("📊 TEST RESULTS")
    print("="*50)
    
    passed = 0
    for test_name, result in results.items():
        print(f"{result} {test_name}")
        if "PASSED" in result:
            passed += 1
    
    total = len(results)
    print(f"\n🎯 {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED! Backtesting engine is working!")
    else:
        print("⚠️ Some tests failed - but basic functionality is available")

if __name__ == "__main__":
    asyncio.run(main()) 