#!/usr/bin/env python3
"""
Direct Test BTC Bias Fix in Enhanced Paper Trading Engine
Tests the exact code path that was fixed to ensure missing symbols are handled correctly.
"""

import asyncio
import logging
from unittest.mock import Mock, AsyncMock
from src.trading.enhanced_paper_trading_engine import EnhancedPaperTradingEngine

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_btc_bias_fix_direct():
    """Direct test of the BTC bias fix by forcing missing symbol scenarios."""
    
    print("🧪 Direct Testing BTC Bias Fix in Enhanced Paper Trading Engine")
    print("=" * 70)
    
    # Mock exchange client
    mock_exchange = Mock()
    mock_exchange.get_ticker_24h = AsyncMock(return_value={'lastPrice': '50000'})
    
    # Create paper trading engine
    config = {
        'paper_trading': {
            'initial_balance': 10000.0,
            'fees': {'rate': 0.0004},
            'slippage': {'rate': 0.0003},
            'latency': {'ms': 50}
        }
    }
    
    engine = EnhancedPaperTradingEngine(
        config=config,
        exchange_client=mock_exchange,
        opportunity_manager=None  # No opportunity manager for direct testing
    )
    
    print("✅ Created enhanced paper trading engine")
    
    # Test 1: Direct test of signal creation with missing symbol
    print("\n🧪 Test 1: Signal creation with missing symbol")
    
    # Capture warnings from the engine logger
    import io
    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(logging.WARNING)
    
    engine_logger = logging.getLogger('src.trading.enhanced_paper_trading_engine')
    engine_logger.addHandler(handler)
    
    # Create a signal with missing symbol (simulating the old behavior)
    test_signal_missing = {
        'direction': 'LONG',
        'entry_price': 50000,
        'stop_loss': 49000,
        'take_profit': 51000,
        'strategy': 'test',
        'signal_id': 'test_missing',
        'optimal_leverage': 2.0,
        'tp_net_usd': 0.0,
        'sl_net_usd': 0.0,
        'floor_net_usd': 0.0
        # Missing 'symbol' field
    }
    
    # Test the execute_virtual_trade method directly
    position_id = await engine.execute_virtual_trade(test_signal_missing, 500.0)
    
    # Check log output
    log_output = log_capture.getvalue()
    engine_logger.removeHandler(handler)
    
    print(f"📊 Position ID returned: {position_id}")
    print(f"📊 Log output captured: {repr(log_output)}")
    
    if position_id is None:
        print("✅ PASS: Missing symbol signal correctly rejected")
    else:
        print("❌ FAIL: Missing symbol signal was accepted")
    
    # Test 2: Signal with None symbol
    print("\n🧪 Test 2: Signal creation with None symbol")
    
    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(logging.WARNING)
    engine_logger.addHandler(handler)
    
    test_signal_none = {
        'symbol': None,  # Explicit None
        'direction': 'LONG',
        'entry_price': 50000,
        'stop_loss': 49000,
        'take_profit': 51000,
        'strategy': 'test',
        'signal_id': 'test_none',
        'optimal_leverage': 2.0,
        'tp_net_usd': 0.0,
        'sl_net_usd': 0.0,
        'floor_net_usd': 0.0
    }
    
    position_id_none = await engine.execute_virtual_trade(test_signal_none, 500.0)
    
    log_output_none = log_capture.getvalue()
    engine_logger.removeHandler(handler)
    
    print(f"📊 Position ID returned: {position_id_none}")
    print(f"📊 Log output captured: {repr(log_output_none)}")
    
    if position_id_none is None:
        print("✅ PASS: None symbol signal correctly rejected")
    else:
        print("❌ FAIL: None symbol signal was accepted")
    
    # Test 3: Signal with empty string symbol
    print("\n🧪 Test 3: Signal creation with empty string symbol")
    
    test_signal_empty = {
        'symbol': '',  # Empty string
        'direction': 'LONG',
        'entry_price': 50000,
        'stop_loss': 49000,
        'take_profit': 51000,
        'strategy': 'test',
        'signal_id': 'test_empty',
        'optimal_leverage': 2.0,
        'tp_net_usd': 0.0,
        'sl_net_usd': 0.0,
        'floor_net_usd': 0.0
    }
    
    position_id_empty = await engine.execute_virtual_trade(test_signal_empty, 500.0)
    
    print(f"📊 Position ID returned: {position_id_empty}")
    
    if position_id_empty is None:
        print("✅ PASS: Empty symbol signal correctly rejected")
    else:
        print("❌ FAIL: Empty symbol signal was accepted")
    
    # Test 4: Valid signal should still work
    print("\n🧪 Test 4: Valid signal should work")
    
    test_signal_valid = {
        'symbol': 'ETHUSDT',
        'direction': 'LONG',
        'entry_price': 2500,
        'stop_loss': 2450,
        'take_profit': 2550,
        'strategy': 'test',
        'signal_id': 'test_valid',
        'optimal_leverage': 2.0,
        'tp_net_usd': 0.0,
        'sl_net_usd': 0.0,
        'floor_net_usd': 0.0
    }
    
    position_id_valid = await engine.execute_virtual_trade(test_signal_valid, 500.0)
    
    print(f"📊 Position ID returned: {position_id_valid}")
    
    if position_id_valid is not None:
        print("✅ PASS: Valid signal correctly accepted")
        print(f"   - Position created: {position_id_valid}")
    else:
        print("❌ FAIL: Valid signal was rejected")
    
    # Test 5: Check no BTC positions were created
    print("\n🧪 Test 5: No BTC positions from invalid signals")
    
    btc_positions = [pos for pos in engine.virtual_positions.values() if pos.symbol == 'BTCUSDT']
    
    print(f"📊 BTC positions created: {len(btc_positions)}")
    
    if len(btc_positions) == 0:
        print("✅ PASS: No BTC fallback positions created")
    else:
        print("❌ FAIL: BTC fallback positions were created")
        for pos in btc_positions:
            print(f"   - BTC position: {pos.position_id} (strategy: {pos.strategy})")
    
    # Summary
    print("\n" + "=" * 70)
    print("🎯 DIRECT BTC BIAS FIX VERIFICATION SUMMARY")
    print("=" * 70)
    
    tests_passed = 0
    total_tests = 5
    
    if position_id is None:
        tests_passed += 1
        print("✅ Test 1 PASSED: Missing symbol signal rejected")
    else:
        print("❌ Test 1 FAILED: Missing symbol signal accepted")
    
    if position_id_none is None:
        tests_passed += 1
        print("✅ Test 2 PASSED: None symbol signal rejected")
    else:
        print("❌ Test 2 FAILED: None symbol signal accepted")
    
    if position_id_empty is None:
        tests_passed += 1
        print("✅ Test 3 PASSED: Empty symbol signal rejected")
    else:
        print("❌ Test 3 FAILED: Empty symbol signal accepted")
    
    if position_id_valid is not None:
        tests_passed += 1
        print("✅ Test 4 PASSED: Valid signal accepted")
    else:
        print("❌ Test 4 FAILED: Valid signal rejected")
    
    if len(btc_positions) == 0:
        tests_passed += 1
        print("✅ Test 5 PASSED: No BTC fallback positions")
    else:
        print("❌ Test 5 FAILED: BTC fallback positions created")
    
    print(f"\n🏆 OVERALL RESULT: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        print("🎉 BTC BIAS FIX WORKING PERFECTLY!")
        print("   - Invalid symbols are properly rejected")
        print("   - No more automatic BTC fallback")
        print("   - Valid signals still work correctly")
        print("   - Profit-first ranking can work without BTC contamination")
    else:
        print("⚠️  BTC BIAS FIX NEEDS ATTENTION")
    
    return tests_passed == total_tests

if __name__ == "__main__":
    success = asyncio.run(test_btc_bias_fix_direct())
    exit(0 if success else 1)
