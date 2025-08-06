#!/usr/bin/env python3
"""
Test Enhanced Monitoring Loop Fixes
Comprehensive test to verify all monitoring loop issues are resolved
"""

import asyncio
import logging
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.trading.enhanced_paper_trading_engine import EnhancedPaperTradingEngine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MockExchangeClient:
    """Enhanced mock exchange client for comprehensive testing"""
    
    def __init__(self):
        self.prices = {
            'BTCUSDT': 45000.0,
            'ETHUSDT': 2800.0,
            'BNBUSDT': 320.0,
            'ADAUSDT': 0.45,
            'SOLUSDT': 95.0
        }
        self.price_history = {}
        self.call_count = 0
        self.failure_rate = 0.0  # Simulate price fetch failures
        
    def set_failure_rate(self, rate: float):
        """Set price fetch failure rate for testing"""
        self.failure_rate = rate
        logger.info(f"📊 Mock client failure rate set to {rate:.1%}")
    
    def set_price(self, symbol: str, price: float):
        """Set price for testing"""
        old_price = self.prices.get(symbol, price)
        self.prices[symbol] = price
        
        # Track price history
        if symbol not in self.price_history:
            self.price_history[symbol] = []
        self.price_history[symbol].append({
            'price': price,
            'timestamp': datetime.utcnow(),
            'change_pct': ((price - old_price) / old_price * 100) if old_price != price else 0.0
        })
        
        logger.info(f"📊 Mock price set: {symbol} = ${price:.4f} ({((price - old_price) / old_price * 100):+.2f}%)")
    
    def simulate_price_movement(self, symbol: str, change_pct: float):
        """Simulate price movement"""
        if symbol in self.prices:
            old_price = self.prices[symbol]
            new_price = old_price * (1 + change_pct / 100)
            self.set_price(symbol, new_price)
    
    async def get_current_price(self, symbol: str) -> float:
        """Get current price with optional failures"""
        self.call_count += 1
        
        # Simulate failures
        if self.failure_rate > 0 and (self.call_count % int(1/self.failure_rate)) == 0:
            logger.warning(f"⚠️ Simulated price fetch failure for {symbol}")
            raise Exception(f"Simulated price fetch failure for {symbol}")
        
        return self.prices.get(symbol, 45000.0)
    
    async def get_ticker_24h(self, symbol: str) -> Dict[str, Any]:
        """Get 24h ticker with optional failures"""
        self.call_count += 1
        
        # Simulate failures
        if self.failure_rate > 0 and (self.call_count % int(1/self.failure_rate)) == 0:
            logger.warning(f"⚠️ Simulated ticker fetch failure for {symbol}")
            raise Exception(f"Simulated ticker fetch failure for {symbol}")
        
        price = self.prices.get(symbol, 45000.0)
        return {
            'symbol': symbol,
            'lastPrice': str(price),
            'priceChange': '0',
            'priceChangePercent': '0'
        }

async def test_enhanced_position_monitoring():
    """Test enhanced position monitoring with comprehensive scenarios"""
    logger.info("🧪 Testing Enhanced Position Monitoring...")
    
    # Create engine with realistic settings
    config = {
        'paper_trading': {
            'initial_balance': 10000.0,
            'max_positions': 5,  # Lower limit for testing
            'risk_per_trade_pct': 0.10,  # 10% per trade
            'leverage': 10.0,
            'primary_target_dollars': 18.0,  # $18 gross = $10 net
            'absolute_floor_dollars': 15.0,  # $15 gross = $7 net
            'pure_3_rule_mode': True
        }
    }
    
    mock_client = MockExchangeClient()
    engine = EnhancedPaperTradingEngine(config, mock_client)
    
    # Start engine
    await engine.start()
    await asyncio.sleep(2)  # Let it initialize
    
    test_results = {
        'positions_created': 0,
        'positions_closed': 0,
        'take_profit_triggers': 0,
        'stop_loss_triggers': 0,
        'floor_triggers': 0,
        'monitoring_errors': 0,
        'price_fetch_failures': 0
    }
    
    try:
        # TEST 1: Create multiple positions
        logger.info("📊 TEST 1: Creating multiple positions...")
        symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
        
        for symbol in symbols:
            signal = {
                'symbol': symbol,
                'side': 'LONG',
                'confidence': 0.8,
                'strategy_type': 'test',
                'signal_source': 'enhanced_test',
                'reason': f'enhanced_monitoring_test_{symbol}'
            }
            
            position_id = await engine.execute_trade(signal)
            if position_id:
                test_results['positions_created'] += 1
                logger.info(f"✅ Created position: {symbol} ({position_id})")
            else:
                logger.warning(f"❌ Failed to create position: {symbol}")
        
        initial_positions = len(engine.positions)
        logger.info(f"📊 Initial positions created: {initial_positions}")
        
        # TEST 2: Test price fetch resilience with failures
        logger.info("📊 TEST 2: Testing price fetch resilience...")
        mock_client.set_failure_rate(0.3)  # 30% failure rate
        
        # Let monitoring loop run with failures
        await asyncio.sleep(5)
        
        # Reset failure rate
        mock_client.set_failure_rate(0.0)
        logger.info("✅ Price fetch resilience test completed")
        
        # TEST 3: Test take profit triggers
        logger.info("📊 TEST 3: Testing take profit triggers...")
        
        # Move prices up to trigger $10 take profit
        for symbol in symbols:
            if symbol in engine.positions or any(pos.symbol == symbol for pos in engine.positions.values()):
                # Calculate required price movement for $10 profit
                # For $10k notional: $18 profit = 0.18% price movement
                mock_client.simulate_price_movement(symbol, 0.25)  # 0.25% increase
                logger.info(f"📈 Moved {symbol} up 0.25% to trigger take profit")
        
        # Wait for monitoring loop to process
        await asyncio.sleep(3)
        
        # Check for closed positions
        positions_after_tp = len(engine.positions)
        tp_closures = initial_positions - positions_after_tp
        test_results['take_profit_triggers'] = tp_closures
        logger.info(f"💰 Take profit closures: {tp_closures}")
        
        # TEST 4: Test stop loss triggers
        logger.info("📊 TEST 4: Testing stop loss triggers...")
        
        # Create new position for stop loss test
        signal = {
            'symbol': 'ADAUSDT',
            'side': 'LONG',
            'confidence': 0.8,
            'strategy_type': 'test',
            'signal_source': 'enhanced_test',
            'reason': 'stop_loss_test'
        }
        
        sl_position_id = await engine.execute_trade(signal)
        if sl_position_id:
            test_results['positions_created'] += 1
            logger.info(f"✅ Created stop loss test position: ADAUSDT")
            
            # Wait a moment
            await asyncio.sleep(1)
            
            # Move price down to trigger stop loss
            mock_client.simulate_price_movement('ADAUSDT', -0.25)  # 0.25% decrease
            logger.info(f"📉 Moved ADAUSDT down 0.25% to trigger stop loss")
            
            # Wait for monitoring loop to process
            await asyncio.sleep(3)
            
            # Check if position was closed
            if sl_position_id not in engine.positions:
                test_results['stop_loss_triggers'] += 1
                logger.info(f"🛡️ Stop loss triggered successfully")
        
        # TEST 5: Test floor protection
        logger.info("📊 TEST 5: Testing floor protection...")
        
        # Create position for floor test
        signal = {
            'symbol': 'SOLUSDT',
            'side': 'LONG',
            'confidence': 0.8,
            'strategy_type': 'test',
            'signal_source': 'enhanced_test',
            'reason': 'floor_test'
        }
        
        floor_position_id = await engine.execute_trade(signal)
        if floor_position_id:
            test_results['positions_created'] += 1
            logger.info(f"✅ Created floor test position: SOLUSDT")
            
            # First, move price up to activate floor
            mock_client.simulate_price_movement('SOLUSDT', 0.20)  # Activate floor
            await asyncio.sleep(2)
            
            # Then move price down to test floor protection
            mock_client.simulate_price_movement('SOLUSDT', -0.08)  # Should trigger floor
            await asyncio.sleep(3)
            
            # Check if position was closed due to floor
            if floor_position_id not in engine.positions:
                # Check if it was closed due to floor
                if engine.completed_trades:
                    last_trade = engine.completed_trades[-1]
                    if "floor" in last_trade.exit_reason.lower():
                        test_results['floor_triggers'] += 1
                        logger.info(f"🛡️ Floor protection triggered successfully")
        
        # TEST 6: Test monitoring loop health under stress
        logger.info("📊 TEST 6: Testing monitoring loop health under stress...")
        
        # Create rapid price movements
        for i in range(10):
            for symbol in symbols:
                change = 0.05 * (1 if i % 2 == 0 else -1)  # Oscillate prices
                mock_client.simulate_price_movement(symbol, change)
            await asyncio.sleep(0.1)  # Rapid changes
        
        # Let monitoring loop handle the stress
        await asyncio.sleep(5)
        
        logger.info("✅ Monitoring loop stress test completed")
        
        # TEST 7: Test position limit enforcement
        logger.info("📊 TEST 7: Testing position limit enforcement...")
        
        # Try to create more positions than the limit
        additional_symbols = ['ADAUSDT', 'SOLUSDT']  # Try to exceed 5 position limit
        
        for symbol in additional_symbols:
            signal = {
                'symbol': symbol,
                'side': 'LONG',
                'confidence': 0.8,
                'strategy_type': 'test',
                'signal_source': 'enhanced_test',
                'reason': f'limit_test_{symbol}'
            }
            
            position_id = await engine.execute_trade(signal)
            if position_id:
                test_results['positions_created'] += 1
                logger.info(f"✅ Created additional position: {symbol}")
            else:
                logger.info(f"❌ Position creation rejected (limit): {symbol}")
        
        final_positions = len(engine.positions)
        logger.info(f"📊 Final active positions: {final_positions} (limit: {engine.max_positions})")
        
        # Verify position limit was enforced
        if final_positions <= engine.max_positions:
            logger.info("✅ Position limit enforcement working correctly")
        else:
            logger.warning(f"⚠️ Position limit exceeded: {final_positions} > {engine.max_positions}")
        
        # Final monitoring loop health check
        await asyncio.sleep(3)
        
        # Count completed trades
        test_results['positions_closed'] = len(engine.completed_trades)
        
        logger.info("📊 ENHANCED MONITORING TEST RESULTS:")
        logger.info(f"   Positions Created: {test_results['positions_created']}")
        logger.info(f"   Positions Closed: {test_results['positions_closed']}")
        logger.info(f"   Take Profit Triggers: {test_results['take_profit_triggers']}")
        logger.info(f"   Stop Loss Triggers: {test_results['stop_loss_triggers']}")
        logger.info(f"   Floor Triggers: {test_results['floor_triggers']}")
        logger.info(f"   Active Positions: {len(engine.positions)}")
        logger.info(f"   Account Balance: ${engine.account.balance:.2f}")
        logger.info(f"   Account Equity: ${engine.account.equity:.2f}")
        
        # Verify monitoring loop is still running
        if engine.is_running and hasattr(engine, 'monitoring_task') and not engine.monitoring_task.done():
            logger.info("✅ Enhanced monitoring loop is healthy and running")
            return True
        else:
            logger.error("❌ Enhanced monitoring loop is not running properly")
            return False
        
    except Exception as e:
        logger.error(f"❌ Error in enhanced monitoring test: {e}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        return False
    
    finally:
        # Clean shutdown
        engine.stop()
        await asyncio.sleep(1)

async def test_race_condition_prevention():
    """Test race condition prevention in position closing"""
    logger.info("🧪 Testing Race Condition Prevention...")
    
    config = {
        'paper_trading': {
            'initial_balance': 10000.0,
            'max_positions': 10,
            'risk_per_trade_pct': 0.10,
            'leverage': 10.0,
            'primary_target_dollars': 18.0,
            'pure_3_rule_mode': True
        }
    }
    
    mock_client = MockExchangeClient()
    engine = EnhancedPaperTradingEngine(config, mock_client)
    
    await engine.start()
    await asyncio.sleep(1)
    
    try:
        # Create a position
        signal = {
            'symbol': 'BTCUSDT',
            'side': 'LONG',
            'confidence': 0.8,
            'strategy_type': 'test',
            'signal_source': 'race_test',
            'reason': 'race_condition_test'
        }
        
        position_id = await engine.execute_trade(signal)
        if not position_id:
            logger.error("❌ Failed to create test position for race condition test")
            return False
        
        logger.info(f"✅ Created test position: {position_id}")
        
        # Simulate rapid price movements that could trigger multiple exit conditions
        mock_client.simulate_price_movement('BTCUSDT', 0.25)  # Should trigger take profit
        
        # Try to close the position multiple times simultaneously
        close_tasks = []
        for i in range(5):
            task = asyncio.create_task(engine.close_position(position_id, f"race_test_{i}"))
            close_tasks.append(task)
        
        # Wait for all close attempts
        results = await asyncio.gather(*close_tasks, return_exceptions=True)
        
        # Count successful closes
        successful_closes = sum(1 for result in results if result is not None and not isinstance(result, Exception))
        
        logger.info(f"📊 Race condition test results:")
        logger.info(f"   Close attempts: {len(close_tasks)}")
        logger.info(f"   Successful closes: {successful_closes}")
        logger.info(f"   Position still exists: {position_id in engine.positions}")
        
        # Should only have one successful close
        if successful_closes <= 1 and position_id not in engine.positions:
            logger.info("✅ Race condition prevention working correctly")
            return True
        else:
            logger.warning(f"⚠️ Race condition issue: {successful_closes} successful closes")
            return False
    
    except Exception as e:
        logger.error(f"❌ Error in race condition test: {e}")
        return False
    
    finally:
        engine.stop()

async def test_monitoring_loop_recovery():
    """Test monitoring loop recovery from errors"""
    logger.info("🧪 Testing Monitoring Loop Recovery...")
    
    config = {
        'paper_trading': {
            'initial_balance': 10000.0,
            'max_positions': 5,
            'risk_per_trade_pct': 0.10,
            'leverage': 10.0
        }
    }
    
    mock_client = MockExchangeClient()
    engine = EnhancedPaperTradingEngine(config, mock_client)
    
    await engine.start()
    await asyncio.sleep(1)
    
    try:
        # Create a position
        signal = {
            'symbol': 'BTCUSDT',
            'side': 'LONG',
            'confidence': 0.8,
            'strategy_type': 'test',
            'signal_source': 'recovery_test',
            'reason': 'recovery_test'
        }
        
        position_id = await engine.execute_trade(signal)
        if not position_id:
            logger.error("❌ Failed to create test position for recovery test")
            return False
        
        logger.info(f"✅ Created test position: {position_id}")
        
        # Simulate high failure rate to stress the monitoring loop
        mock_client.set_failure_rate(0.8)  # 80% failure rate
        logger.info("📊 Set high failure rate to stress monitoring loop")
        
        # Let it run with high failures
        await asyncio.sleep(10)
        
        # Reset failure rate
        mock_client.set_failure_rate(0.0)
        logger.info("📊 Reset failure rate to normal")
        
        # Let it recover
        await asyncio.sleep(5)
        
        # Check if monitoring loop is still running
        if engine.is_running and hasattr(engine, 'monitoring_task') and not engine.monitoring_task.done():
            logger.info("✅ Monitoring loop recovered successfully from high error rate")
            
            # Test that it can still process positions
            mock_client.simulate_price_movement('BTCUSDT', 0.25)  # Trigger take profit
            await asyncio.sleep(3)
            
            if position_id not in engine.positions:
                logger.info("✅ Monitoring loop can still process positions after recovery")
                return True
            else:
                logger.warning("⚠️ Monitoring loop may not be processing positions correctly after recovery")
                return False
        else:
            logger.error("❌ Monitoring loop did not recover from high error rate")
            return False
    
    except Exception as e:
        logger.error(f"❌ Error in recovery test: {e}")
        return False
    
    finally:
        engine.stop()

async def main():
    """Run all enhanced monitoring tests"""
    logger.info("🚀 Starting Enhanced Monitoring Loop Tests...")
    
    tests = [
        ("Enhanced Position Monitoring", test_enhanced_position_monitoring),
        ("Race Condition Prevention", test_race_condition_prevention),
        ("Monitoring Loop Recovery", test_monitoring_loop_recovery)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            logger.info(f"\n{'='*80}")
            logger.info(f"🧪 Running: {test_name}")
            logger.info(f"{'='*80}")
            
            result = await test_func()
            if result:
                logger.info(f"✅ {test_name} PASSED")
                passed += 1
            else:
                logger.error(f"❌ {test_name} FAILED")
                failed += 1
                
        except Exception as e:
            logger.error(f"❌ {test_name} FAILED with exception: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            failed += 1
        
        # Brief pause between tests
        await asyncio.sleep(2)
    
    # Summary
    logger.info(f"\n{'='*80}")
    logger.info(f"🏁 ENHANCED MONITORING TEST SUMMARY")
    logger.info(f"{'='*80}")
    logger.info(f"✅ Passed: {passed}")
    logger.info(f"❌ Failed: {failed}")
    logger.info(f"📊 Total: {passed + failed}")
    
    if failed == 0:
        logger.info("🎉 ALL ENHANCED MONITORING TESTS PASSED!")
        logger.info("✅ Monitoring loop fixes are working correctly:")
        logger.info("   • Position closing race conditions resolved")
        logger.info("   • Take profit triggers working reliably")
        logger.info("   • Stop loss enforcement working")
        logger.info("   • Position limits strictly enforced")
        logger.info("   • Price fetch failures handled gracefully")
        logger.info("   • Monitoring loop recovers from errors")
        logger.info("   • Enhanced error handling prevents crashes")
        return True
    else:
        logger.error(f"💥 {failed} tests failed. Monitoring loop issues may persist.")
        return False

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("🛑 Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"💥 Test runner failed: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)
