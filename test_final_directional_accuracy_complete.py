#!/usr/bin/env python3

"""
Final Directional Accuracy Test - Complete Implementation
Tests the two critical fixes for directional accuracy:
1. Closed candle analysis (prevents forming candle flip-flops)
2. Direction flip debouncing (prevents rapid direction changes)
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, List, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MockExchangeClient:
    """Mock exchange client for testing"""
    
    async def get_all_symbols(self):
        return ['BTCUSDT', 'ETHUSDT', 'ADAUSDT']
    
    async def get_historical_data(self, symbol, interval, limit):
        # Return mock data that could cause direction flips
        import random
        random.seed(42)  # Consistent test data
        
        klines = []
        base_price = 50000 if symbol == 'BTCUSDT' else 3000
        
        for i in range(limit):
            # Create alternating price movements that could cause flips
            price_change = 0.01 if i % 2 == 0 else -0.01
            price = base_price * (1 + price_change)
            
            klines.append({
                'openTime': int(time.time() * 1000) - (i * 60000),
                'open': price * 0.999,
                'high': price * 1.001,
                'low': price * 0.998,
                'close': price,
                'volume': 1000 + random.randint(-100, 100),
                'closeTime': int(time.time() * 1000) - (i * 60000) + 60000
            })
        
        return list(reversed(klines))

class MockRiskManager:
    def check_risk_limits(self, symbol, market_data):
        return True

class MockStrategyManager:
    pass

async def test_closed_candle_analysis():
    """Test that closed candle analysis prevents forming candle issues"""
    logger.info("🧪 Testing Closed Candle Analysis...")
    
    try:
        from src.opportunity.opportunity_manager import OpportunityManager
        
        # Create mock components
        exchange_client = MockExchangeClient()
        strategy_manager = MockStrategyManager()
        risk_manager = MockRiskManager()
        
        # Initialize opportunity manager
        opportunity_manager = OpportunityManager(
            exchange_client=exchange_client,
            strategy_manager=strategy_manager,
            risk_manager=risk_manager
        )
        
        # Test the _drop_forming_candle method
        test_klines = [
            {'close': 100, 'open': 99},
            {'close': 101, 'open': 100},
            {'close': 102, 'open': 101},  # This would be the "forming" candle
        ]
        
        # Test dropping forming candle
        closed_klines = opportunity_manager._drop_forming_candle(test_klines)
        
        assert len(closed_klines) == 2, f"Expected 2 closed candles, got {len(closed_klines)}"
        assert closed_klines[-1]['close'] == 101, f"Expected last close to be 101, got {closed_klines[-1]['close']}"
        
        logger.info("✅ Closed candle analysis working correctly")
        
        # Test with empty/small datasets
        empty_result = opportunity_manager._drop_forming_candle([])
        assert empty_result == [], "Empty klines should return empty"
        
        single_result = opportunity_manager._drop_forming_candle([{'close': 100}])
        assert single_result == [{'close': 100}], "Single candle should be preserved"
        
        logger.info("✅ Edge cases handled correctly")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Closed candle analysis test failed: {e}")
        return False

async def test_direction_flip_debouncing():
    """Test that direction flip debouncing prevents rapid changes"""
    logger.info("🧪 Testing Direction Flip Debouncing...")
    
    try:
        from src.opportunity.opportunity_manager import OpportunityManager
        
        # Create mock components
        exchange_client = MockExchangeClient()
        strategy_manager = MockStrategyManager()
        risk_manager = MockRiskManager()
        
        # Initialize opportunity manager
        opportunity_manager = OpportunityManager(
            exchange_client=exchange_client,
            strategy_manager=strategy_manager,
            risk_manager=risk_manager
        )
        
        symbol = "BTCUSDT"
        current_time = time.time()
        
        # Test 1: First signal should be accepted
        should_accept_first = opportunity_manager._should_accept_flip(symbol, "LONG", 0.01)
        assert should_accept_first == True, "First signal should be accepted"
        logger.info("✅ First signal accepted correctly")
        
        # Create a signal in the opportunities dict
        opportunity_manager.opportunities[symbol] = {
            'direction': 'LONG',
            'signal_timestamp': current_time,
            'confidence': 0.7
        }
        
        # Test 2: Immediate flip should be rejected (within 60 seconds)
        should_accept_immediate = opportunity_manager._should_accept_flip(symbol, "SHORT", 0.01)
        assert should_accept_immediate == False, "Immediate flip should be rejected"
        logger.info("✅ Immediate flip rejected correctly")
        
        # Test 3: Same direction should be accepted
        should_accept_same = opportunity_manager._should_accept_flip(symbol, "LONG", 0.01)
        assert should_accept_same == True, "Same direction should be accepted"
        logger.info("✅ Same direction accepted correctly")
        
        # Test 4: Flip with insufficient momentum should be rejected
        should_accept_weak = opportunity_manager._should_accept_flip(symbol, "SHORT", 0.0005)  # Very weak momentum
        assert should_accept_weak == False, "Weak momentum flip should be rejected"
        logger.info("✅ Weak momentum flip rejected correctly")
        
        # Test 5: Strong momentum flip should be accepted (if enough time passed)
        # Simulate time passage
        opportunity_manager.opportunities[symbol]['signal_timestamp'] = current_time - 70  # 70 seconds ago
        should_accept_strong = opportunity_manager._should_accept_flip(symbol, "SHORT", 0.005)  # Strong momentum
        assert should_accept_strong == True, "Strong momentum flip after time should be accepted"
        logger.info("✅ Strong momentum flip after time accepted correctly")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Direction flip debouncing test failed: {e}")
        return False

async def test_signal_finalization():
    """Test that signal finalization works correctly"""
    logger.info("🧪 Testing Signal Finalization...")
    
    try:
        from src.opportunity.opportunity_manager import OpportunityManager
        
        # Create mock components
        exchange_client = MockExchangeClient()
        strategy_manager = MockStrategyManager()
        risk_manager = MockRiskManager()
        
        # Initialize opportunity manager
        opportunity_manager = OpportunityManager(
            exchange_client=exchange_client,
            strategy_manager=strategy_manager,
            risk_manager=risk_manager
        )
        
        # Test signal with incorrect TP/SL positioning
        test_signal = {
            'symbol': 'BTCUSDT',
            'direction': 'LONG',
            'entry_price': 50000,
            'take_profit': 49000,  # Wrong! TP should be above entry for LONG
            'stop_loss': 51000,    # Wrong! SL should be below entry for LONG
            'confidence': 0.7
        }
        
        # Apply finalization
        finalized_signal = opportunity_manager._finalize_opportunity(test_signal)
        
        # Check that TP/SL were corrected
        assert finalized_signal['take_profit'] > finalized_signal['entry_price'], "LONG TP should be above entry"
        assert finalized_signal['stop_loss'] < finalized_signal['entry_price'], "LONG SL should be below entry"
        
        logger.info("✅ TP/SL positioning corrected for LONG signal")
        
        # Test SHORT signal
        test_signal_short = {
            'symbol': 'ETHUSDT',
            'direction': 'SHORT',
            'entry_price': 3000,
            'take_profit': 3100,  # Wrong! TP should be below entry for SHORT
            'stop_loss': 2900,    # Wrong! SL should be above entry for SHORT
            'confidence': 0.7
        }
        
        finalized_signal_short = opportunity_manager._finalize_opportunity(test_signal_short)
        
        # Check that TP/SL were corrected
        assert finalized_signal_short['take_profit'] < finalized_signal_short['entry_price'], "SHORT TP should be below entry"
        assert finalized_signal_short['stop_loss'] > finalized_signal_short['entry_price'], "SHORT SL should be above entry"
        
        logger.info("✅ TP/SL positioning corrected for SHORT signal")
        
        # Test that risk/reward is calculated
        assert 'risk_reward' in finalized_signal_short, "Risk/reward should be calculated"
        assert finalized_signal_short['risk_reward'] > 0, "Risk/reward should be positive"
        
        logger.info("✅ Risk/reward calculation working")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Signal finalization test failed: {e}")
        return False

async def test_integrated_signal_generation():
    """Test that the fixes work together in signal generation"""
    logger.info("🧪 Testing Integrated Signal Generation...")
    
    try:
        from src.opportunity.opportunity_manager import OpportunityManager
        
        # Create mock components
        exchange_client = MockExchangeClient()
        strategy_manager = MockStrategyManager()
        risk_manager = MockRiskManager()
        
        # Initialize opportunity manager
        opportunity_manager = OpportunityManager(
            exchange_client=exchange_client,
            strategy_manager=strategy_manager,
            risk_manager=risk_manager
        )
        
        # Enable paper trading mode for testing
        opportunity_manager.set_paper_trading_mode(True)
        
        # Test signal generation with debouncing
        logger.info("Testing signal generation with debouncing...")
        
        # Generate first signal
        await opportunity_manager.scan_opportunities_incremental()
        
        initial_count = len(opportunity_manager.opportunities)
        logger.info(f"Generated {initial_count} initial opportunities")
        
        # Store initial directions
        initial_directions = {}
        for symbol, opp in opportunity_manager.opportunities.items():
            initial_directions[symbol] = opp.get('direction')
            logger.info(f"Initial {symbol}: {opp.get('direction')} (conf: {opp.get('confidence', 0):.2f})")
        
        # Wait a short time and scan again (should be debounced)
        await asyncio.sleep(1)
        await opportunity_manager.scan_opportunities_incremental()
        
        # Check that directions didn't flip rapidly
        flip_count = 0
        for symbol, opp in opportunity_manager.opportunities.items():
            current_direction = opp.get('direction')
            if symbol in initial_directions and initial_directions[symbol] != current_direction:
                flip_count += 1
                logger.warning(f"Direction flip detected for {symbol}: {initial_directions[symbol]} → {current_direction}")
        
        # Some flips might be allowed if they meet criteria, but should be minimal
        flip_rate = flip_count / max(len(initial_directions), 1)
        assert flip_rate < 0.5, f"Too many direction flips: {flip_rate:.1%} (should be < 50%)"
        
        logger.info(f"✅ Direction flip rate acceptable: {flip_rate:.1%}")
        
        # Test that signals have proper structure
        for symbol, opp in opportunity_manager.opportunities.items():
            assert 'direction' in opp, f"Missing direction for {symbol}"
            assert 'entry_price' in opp, f"Missing entry_price for {symbol}"
            assert 'take_profit' in opp, f"Missing take_profit for {symbol}"
            assert 'stop_loss' in opp, f"Missing stop_loss for {symbol}"
            assert 'signal_timestamp' in opp, f"Missing signal_timestamp for {symbol}"
            
            # Check TP/SL positioning
            direction = opp['direction']
            entry = opp['entry_price']
            tp = opp['take_profit']
            sl = opp['stop_loss']
            
            if direction == 'LONG':
                assert tp > entry, f"LONG TP should be above entry for {symbol}"
                assert sl < entry, f"LONG SL should be below entry for {symbol}"
            elif direction == 'SHORT':
                assert tp < entry, f"SHORT TP should be below entry for {symbol}"
                assert sl > entry, f"SHORT SL should be above entry for {symbol}"
        
        logger.info("✅ All signals have proper structure and TP/SL positioning")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Integrated signal generation test failed: {e}")
        return False

async def run_all_tests():
    """Run all directional accuracy tests"""
    logger.info("🚀 Starting Final Directional Accuracy Tests...")
    logger.info("=" * 60)
    
    tests = [
        ("Closed Candle Analysis", test_closed_candle_analysis),
        ("Direction Flip Debouncing", test_direction_flip_debouncing),
        ("Signal Finalization", test_signal_finalization),
        ("Integrated Signal Generation", test_integrated_signal_generation),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        logger.info(f"\n📋 Running: {test_name}")
        logger.info("-" * 40)
        
        try:
            start_time = time.time()
            result = await test_func()
            duration = time.time() - start_time
            
            results[test_name] = {
                'passed': result,
                'duration': duration
            }
            
            status = "✅ PASSED" if result else "❌ FAILED"
            logger.info(f"{status} - {test_name} ({duration:.2f}s)")
            
        except Exception as e:
            results[test_name] = {
                'passed': False,
                'duration': 0,
                'error': str(e)
            }
            logger.error(f"❌ FAILED - {test_name}: {e}")
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("📊 FINAL TEST RESULTS")
    logger.info("=" * 60)
    
    passed_tests = sum(1 for r in results.values() if r['passed'])
    total_tests = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASSED" if result['passed'] else "❌ FAILED"
        duration = result.get('duration', 0)
        logger.info(f"{status} {test_name} ({duration:.2f}s)")
        
        if not result['passed'] and 'error' in result:
            logger.info(f"    Error: {result['error']}")
    
    logger.info("-" * 60)
    logger.info(f"Overall: {passed_tests}/{total_tests} tests passed ({passed_tests/total_tests*100:.1f}%)")
    
    if passed_tests == total_tests:
        logger.info("🎉 ALL DIRECTIONAL ACCURACY FIXES WORKING CORRECTLY!")
        logger.info("✅ Closed candle analysis prevents forming candle flip-flops")
        logger.info("✅ Direction flip debouncing prevents rapid direction changes")
        logger.info("✅ Signal finalization ensures proper TP/SL positioning")
        logger.info("✅ Integrated system maintains directional accuracy")
    else:
        logger.error("❌ Some tests failed - directional accuracy fixes need attention")
    
    return passed_tests == total_tests

if __name__ == "__main__":
    asyncio.run(run_all_tests())
