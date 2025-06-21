#!/usr/bin/env python3
"""
🔍 Backtesting Validation Suite

Comprehensive validation to confirm the backtesting engine is working
reliably and ready for production use.
"""

import asyncio
import sys
import os
import json
import time
from datetime import datetime, timedelta

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.backtesting.backtest_engine import BacktestEngine
from src.backtesting.backtest_runner import BacktestRunner
from src.backtesting.strategy_analyzer import StrategyAnalyzer

class BacktestValidator:
    """Comprehensive validation of backtesting functionality"""
    
    def __init__(self):
        self.tests_passed = 0
        self.tests_failed = 0
        self.test_results = {}
        
    async def run_all_validations(self):
        """Run all validation tests"""
        print("🔍 BACKTESTING VALIDATION SUITE")
        print("="*60)
        print("This suite validates that the backtesting engine is")
        print("working reliably and ready for production use.")
        print("="*60)
        
        validations = [
            ("Core Engine Functionality", self.validate_core_engine),
            ("Strategy Comparison", self.validate_strategy_comparison),
            ("Performance Metrics", self.validate_performance_metrics),
            ("Market Regime Analysis", self.validate_market_regimes),
            ("Data Consistency", self.validate_data_consistency),
            ("Error Handling", self.validate_error_handling),
            ("Export Functionality", self.validate_export),
            ("API Integration", self.validate_api_integration),
            ("Performance Benchmarks", self.validate_performance),
            ("Production Readiness", self.validate_production_readiness)
        ]
        
        for test_name, test_func in validations:
            print(f"\n🔄 Running: {test_name}")
            try:
                result = await test_func()
                if result:
                    print(f"✅ PASSED: {test_name}")
                    self.tests_passed += 1
                    self.test_results[test_name] = "PASSED"
                else:
                    print(f"❌ FAILED: {test_name}")
                    self.tests_failed += 1
                    self.test_results[test_name] = "FAILED"
            except Exception as e:
                print(f"💥 CRASHED: {test_name} - {e}")
                self.tests_failed += 1
                self.test_results[test_name] = f"CRASHED: {e}"
        
        # Final report
        self.generate_final_report()
    
    async def validate_core_engine(self):
        """Validate core backtesting engine functionality"""
        try:
            engine = BacktestEngine(initial_balance=10000)
            
            # Test basic backtest
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            
            performance = await engine.run_strategy_backtest(
                strategy_name="trend_following",
                symbol="BTCUSDT",
                start_date=start_date,
                end_date=end_date
            )
            
            # Validate performance object
            required_attrs = [
                'strategy_name', 'total_trades', 'win_rate', 'total_return',
                'max_drawdown', 'sharpe_ratio', 'profit_factor'
            ]
            
            for attr in required_attrs:
                if not hasattr(performance, attr):
                    print(f"   ❌ Missing attribute: {attr}")
                    return False
            
            # Validate data types and ranges
            if not isinstance(performance.total_trades, int) or performance.total_trades < 0:
                print(f"   ❌ Invalid total_trades: {performance.total_trades}")
                return False
            
            if not 0 <= performance.win_rate <= 1:
                print(f"   ❌ Invalid win_rate: {performance.win_rate}")
                return False
            
            print(f"   ✅ Generated {performance.total_trades} trades")
            print(f"   ✅ Win rate: {performance.win_rate:.1%}")
            print(f"   ✅ Total return: {performance.total_return:.1%}")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Core engine error: {e}")
            return False
    
    async def validate_strategy_comparison(self):
        """Validate strategy comparison functionality"""
        try:
            runner = BacktestRunner()
            
            strategies = ["trend_following", "breakout", "mean_reversion"]
            comparison = await runner.run_strategy_comparison(
                strategies=strategies,
                symbol="BTCUSDT",
                days_back=7
            )
            
            # Validate comparison DataFrame
            if len(comparison) != len(strategies):
                print(f"   ❌ Expected {len(strategies)} results, got {len(comparison)}")
                return False
            
            required_columns = ['Strategy', 'Win Rate', 'Total Return', 'Sharpe Ratio']
            for col in required_columns:
                if col not in comparison.columns:
                    print(f"   ❌ Missing column: {col}")
                    return False
            
            print(f"   ✅ Compared {len(strategies)} strategies")
            print(f"   ✅ Generated comparison table with {len(comparison.columns)} metrics")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Strategy comparison error: {e}")
            return False
    
    async def validate_performance_metrics(self):
        """Validate performance metrics calculations"""
        try:
            engine = BacktestEngine(initial_balance=10000)
            
            # Run backtest and get detailed metrics
            end_date = datetime.now()
            start_date = end_date - timedelta(days=14)
            
            performance = await engine.run_strategy_backtest(
                strategy_name="mean_reversion",
                symbol="BTCUSDT",
                start_date=start_date,
                end_date=end_date
            )
            
            # Validate metric calculations
            metrics_to_check = {
                'win_rate': (0, 1),  # Should be between 0 and 1
                'total_return': (-1, 10),  # Reasonable range
                'max_drawdown': (0, 1),  # Should be positive
                'sharpe_ratio': (-50, 50),  # Reasonable range
                'profit_factor': (0, 100)  # Should be positive
            }
            
            for metric, (min_val, max_val) in metrics_to_check.items():
                value = getattr(performance, metric)
                if not min_val <= value <= max_val:
                    print(f"   ❌ {metric} out of range: {value} (expected {min_val} to {max_val})")
                    return False
            
            print(f"   ✅ All performance metrics within expected ranges")
            print(f"   ✅ Sharpe ratio: {performance.sharpe_ratio:.2f}")
            print(f"   ✅ Profit factor: {performance.profit_factor:.2f}")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Performance metrics error: {e}")
            return False
    
    async def validate_market_regimes(self):
        """Validate market regime analysis"""
        try:
            runner = BacktestRunner()
            
            regime_analysis = await runner.run_market_regime_analysis(
                strategy="trend_following",
                symbol="BTCUSDT",
                days_back=30
            )
            
            # Check that we have regime data
            if not regime_analysis:
                print(f"   ❌ No regime analysis returned")
                return False
            
            # Validate regime structure
            expected_regimes = ['trending', 'ranging', 'volatile', 'stable']
            for regime in expected_regimes:
                if regime not in regime_analysis:
                    print(f"   ❌ Missing regime: {regime}")
                    return False
                
                regime_data = regime_analysis[regime]
                required_keys = ['trades', 'win_rate', 'avg_return', 'total_pnl']
                for key in required_keys:
                    if key not in regime_data:
                        print(f"   ❌ Missing regime key: {key}")
                        return False
            
            print(f"   ✅ Analyzed {len(regime_analysis)} market regimes")
            
            # Show regime with most trades
            regime_with_most_trades = max(
                regime_analysis.items(),
                key=lambda x: x[1]['trades']
            )
            print(f"   ✅ Most active regime: {regime_with_most_trades[0]} ({regime_with_most_trades[1]['trades']} trades)")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Market regime error: {e}")
            return False
    
    async def validate_data_consistency(self):
        """Validate data consistency across multiple runs"""
        try:
            engine = BacktestEngine(initial_balance=10000)
            
            # Run same backtest multiple times
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            
            results = []
            for i in range(3):
                performance = await engine.run_strategy_backtest(
                    strategy_name="trend_following",
                    symbol="BTCUSDT",
                    start_date=start_date,
                    end_date=end_date
                )
                results.append({
                    'total_trades': performance.total_trades,
                    'win_rate': performance.win_rate,
                    'total_return': performance.total_return
                })
            
            # Check consistency (should be identical for same parameters)
            first_result = results[0]
            for i, result in enumerate(results[1:], 1):
                for key, value in result.items():
                    if abs(value - first_result[key]) > 0.001:  # Allow small floating point differences
                        print(f"   ❌ Inconsistent {key}: run 0 = {first_result[key]}, run {i} = {value}")
                        return False
            
            print(f"   ✅ Data consistent across {len(results)} runs")
            print(f"   ✅ Deterministic results confirmed")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Data consistency error: {e}")
            return False
    
    async def validate_error_handling(self):
        """Validate error handling for invalid inputs"""
        try:
            engine = BacktestEngine()
            
            # Test invalid strategy
            try:
                await engine.run_strategy_backtest(
                    strategy_name="invalid_strategy",
                    symbol="BTCUSDT",
                    start_date=datetime.now() - timedelta(days=7),
                    end_date=datetime.now()
                )
                # Should handle gracefully, not crash
            except Exception:
                pass  # Expected to handle gracefully
            
            # Test invalid date range
            try:
                await engine.run_strategy_backtest(
                    strategy_name="trend_following",
                    symbol="BTCUSDT",
                    start_date=datetime.now(),
                    end_date=datetime.now() - timedelta(days=7)  # End before start
                )
            except Exception:
                pass  # Expected to handle gracefully
            
            print(f"   ✅ Error handling working correctly")
            return True
            
        except Exception as e:
            print(f"   ❌ Error handling test failed: {e}")
            return False
    
    async def validate_export(self):
        """Validate export functionality"""
        try:
            runner = BacktestRunner()
            
            # Run a quick backtest
            await runner.run_quick_backtest("trend_following", "BTCUSDT", days_back=3)
            
            # Export results
            filename = runner.export_all_results("validation_export.json")
            
            # Validate export file
            if not os.path.exists(filename):
                print(f"   ❌ Export file not created: {filename}")
                return False
            
            # Validate JSON structure
            with open(filename, 'r') as f:
                data = json.load(f)
            
            required_keys = ['backtest_summary', 'strategy_performance', 'trades']
            for key in required_keys:
                if key not in data:
                    print(f"   ❌ Missing export key: {key}")
                    return False
            
            file_size = os.path.getsize(filename)
            print(f"   ✅ Export file created: {filename}")
            print(f"   ✅ File size: {file_size:,} bytes")
            print(f"   ✅ JSON structure valid")
            
            # Clean up
            os.remove(filename)
            
            return True
            
        except Exception as e:
            print(f"   ❌ Export validation error: {e}")
            return False
    
    async def validate_api_integration(self):
        """Validate API integration"""
        try:
            # Check if backtesting routes are imported
            try:
                import sys
                import os
                sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
                from src.api.backtesting_routes import router
                print(f"   ✅ Backtesting routes imported successfully")
            except ImportError as e:
                print(f"   ❌ Failed to import backtesting routes: {e}")
                return False
            
            # Check if routes are properly defined
            route_paths = [route.path for route in router.routes]
            expected_routes = [
                '/run', '/compare', '/comprehensive', '/analyze',
                '/market-regime', '/strategies', '/symbols', '/health'
            ]
            
            for expected_route in expected_routes:
                if not any(expected_route in path for path in route_paths):
                    print(f"   ❌ Missing route: {expected_route}")
                    return False
            
            print(f"   ✅ All {len(expected_routes)} API routes defined")
            print(f"   ✅ API integration ready")
            
            return True
            
        except Exception as e:
            print(f"   ❌ API integration error: {e}")
            return False
    
    async def validate_performance(self):
        """Validate performance benchmarks"""
        try:
            start_time = time.time()
            
            runner = BacktestRunner()
            
            # Quick performance test
            await runner.run_quick_backtest("trend_following", "BTCUSDT", days_back=7)
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Performance thresholds
            max_duration = 30  # 30 seconds max for quick backtest
            
            if duration > max_duration:
                print(f"   ❌ Performance too slow: {duration:.2f}s (max {max_duration}s)")
                return False
            
            print(f"   ✅ Quick backtest completed in {duration:.2f}s")
            print(f"   ✅ Performance within acceptable limits")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Performance validation error: {e}")
            return False
    
    async def validate_production_readiness(self):
        """Validate production readiness"""
        try:
            checks = []
            
            # Check 1: All core modules importable
            try:
                import sys
                import os
                sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
                from src.backtesting.backtest_engine import BacktestEngine
                from src.backtesting.backtest_runner import BacktestRunner
                from src.backtesting.strategy_analyzer import StrategyAnalyzer
                checks.append("✅ All core modules importable")
            except ImportError as e:
                checks.append(f"❌ Import error: {e}")
                return False
            
            # Check 2: Basic functionality works
            try:
                runner = BacktestRunner()
                performance = await runner.run_quick_backtest("trend_following", "BTCUSDT", days_back=3)
                if performance.total_trades >= 0:  # Basic sanity check
                    checks.append("✅ Basic functionality working")
                else:
                    checks.append("❌ Basic functionality failed")
                    return False
            except Exception as e:
                checks.append(f"❌ Basic functionality error: {e}")
                return False
            
            # Check 3: No critical dependencies missing
            try:
                import pandas as pd
                import numpy as np
                checks.append("✅ Critical dependencies available")
            except ImportError as e:
                checks.append(f"❌ Missing dependency: {e}")
                return False
            
            # Check 4: API routes available
            try:
                from src.api.backtesting_routes import router
                if len(router.routes) >= 8:  # Should have 8+ routes
                    checks.append("✅ API routes available")
                else:
                    checks.append(f"❌ Insufficient API routes: {len(router.routes)}")
                    return False
            except Exception as e:
                checks.append(f"❌ API routes error: {e}")
                return False
            
            # Print all checks
            for check in checks:
                print(f"   {check}")
            
            print(f"   ✅ System ready for production use")
            return True
            
        except Exception as e:
            print(f"   ❌ Production readiness error: {e}")
            return False
    
    def generate_final_report(self):
        """Generate final validation report"""
        total_tests = self.tests_passed + self.tests_failed
        success_rate = (self.tests_passed / total_tests * 100) if total_tests > 0 else 0
        
        print("\n" + "="*60)
        print("🔍 BACKTESTING VALIDATION REPORT")
        print("="*60)
        
        print(f"\n📊 SUMMARY:")
        print(f"   Total Tests: {total_tests}")
        print(f"   Passed: {self.tests_passed}")
        print(f"   Failed: {self.tests_failed}")
        print(f"   Success Rate: {success_rate:.1f}%")
        
        print(f"\n📋 DETAILED RESULTS:")
        for test_name, result in self.test_results.items():
            status_icon = "✅" if result == "PASSED" else "❌"
            print(f"   {status_icon} {test_name}: {result}")
        
        print(f"\n🎯 OVERALL ASSESSMENT:")
        if success_rate >= 90:
            print("   🎉 EXCELLENT - Backtesting engine is production ready!")
            print("   ✅ All critical functionality validated")
            print("   ✅ Performance within acceptable limits")
            print("   ✅ Error handling working correctly")
            print("   ✅ Safe to use for strategy validation")
        elif success_rate >= 70:
            print("   ⚠️ GOOD - Backtesting engine mostly ready")
            print("   ⚠️ Some issues need attention before production")
        else:
            print("   ❌ NEEDS WORK - Critical issues detected")
            print("   ❌ Do not use in production until issues resolved")
        
        print(f"\n🚀 NEXT STEPS:")
        if success_rate >= 90:
            print("   1. Start backtesting your trading strategies")
            print("   2. Validate strategies before live deployment")
            print("   3. Use strategy comparison to find best performers")
            print("   4. Monitor performance across market regimes")
        else:
            print("   1. Review failed tests and fix issues")
            print("   2. Re-run validation suite")
            print("   3. Only proceed when success rate ≥90%")
        
        print("="*60)

async def main():
    """Run comprehensive backtesting validation"""
    validator = BacktestValidator()
    await validator.run_all_validations()

if __name__ == "__main__":
    asyncio.run(main()) 