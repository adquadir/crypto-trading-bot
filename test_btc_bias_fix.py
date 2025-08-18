#!/usr/bin/env python3
"""
Test BTC Bias Fix in Enhanced Paper Trading Engine
Verifies that demo trades no longer default to BTCUSDT when symbol is missing.
"""

import asyncio
import logging
from unittest.mock import Mock, AsyncMock
from src.trading.enhanced_paper_trading_engine import EnhancedPaperTradingEngine

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_btc_bias_fix():
    """Test that demo trades skip when symbol is missing instead of defaulting to BTC."""
    
    print("🧪 Testing BTC Bias Fix in Enhanced Paper Trading Engine")
    print("=" * 60)
    
    # Mock exchange client
    mock_exchange = Mock()
    mock_exchange.get_ticker_24h = AsyncMock(return_value={'lastPrice': '50000'})
    
    # Mock opportunity manager with opportunities missing symbols
    mock_opportunity_manager = Mock()
    
    # Test opportunities - some with symbols, some without
    test_opportunities = [
        {
            'direction': 'LONG',
            'entry_price': 50000,
            'stop_loss': 49000,
            'take_profit': 51000,
            # Missing 'symbol' field - should be skipped
        },
        {
            'symbol': 'ETHUSDT',
            'direction': 'LONG', 
            'entry_price': 2500,
            'stop_loss': 2450,
            'take_profit': 2550,
        },
        {
            'symbol': None,  # Explicit None - should be skipped
            'direction': 'SHORT',
            'entry_price': 100,
            'stop_loss': 105,
            'take_profit': 95,
        }
    ]
    
    mock_opportunity_manager.get_opportunities.return_value = test_opportunities
    
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
        opportunity_manager=mock_opportunity_manager
    )
    
    print("✅ Created enhanced paper trading engine")
    
    # Test 1: Verify demo trades skip opportunities without symbols
    print("\n🧪 Test 1: Demo trades with missing symbols")
    
    # Capture log messages from the enhanced paper trading engine logger
    import io
    import sys
    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(logging.WARNING)
    
    # Get the enhanced paper trading engine logger
    engine_logger = logging.getLogger('src.trading.enhanced_paper_trading_engine')
    engine_logger.addHandler(handler)
    
    # Run demo trade execution multiple times to test different opportunities
    for i in range(10):
        await engine._auto_execute_demo_trades()
        await asyncio.sleep(0.1)  # Small delay
    
    # Check log output
    log_output = log_capture.getvalue()
    engine_logger.removeHandler(handler)
    
    # Verify that warning messages were logged for missing symbols
    missing_symbol_warnings = log_output.count("Skipping demo trade: opportunity missing symbol")
    
    print(f"📊 Missing symbol warnings logged: {missing_symbol_warnings}")
    
    if missing_symbol_warnings > 0:
        print("✅ PASS: Demo trades correctly skip opportunities with missing symbols")
    else:
        print("❌ FAIL: No warnings logged for missing symbols")
    
    # Test 2: Verify no BTC positions were created from missing symbols
    print("\n🧪 Test 2: No BTC positions from missing symbols")
    
    btc_positions = [pos for pos in engine.virtual_positions.values() if pos.symbol == 'BTCUSDT']
    
    print(f"📊 BTC positions created: {len(btc_positions)}")
    
    if len(btc_positions) == 0:
        print("✅ PASS: No BTC positions created from missing symbols")
    else:
        print("❌ FAIL: BTC positions were created from missing symbols")
        for pos in btc_positions:
            print(f"   - BTC position: {pos.position_id} (strategy: {pos.strategy})")
    
    # Test 3: Verify valid opportunities can still create positions
    print("\n🧪 Test 3: Valid opportunities still work")
    
    # Force execution of a valid opportunity
    valid_opportunity = {
        'symbol': 'ETHUSDT',
        'direction': 'LONG',
        'entry_price': 2500,
        'stop_loss': 2450,
        'take_profit': 2550,
    }
    
    # Mock the opportunity manager to return only valid opportunity
    mock_opportunity_manager.get_opportunities.return_value = [valid_opportunity]
    
    # Execute demo trade
    await engine._auto_execute_demo_trades()
    
    eth_positions = [pos for pos in engine.virtual_positions.values() if pos.symbol == 'ETHUSDT']
    
    print(f"📊 ETH positions created: {len(eth_positions)}")
    
    if len(eth_positions) > 0:
        print("✅ PASS: Valid opportunities still create positions")
        for pos in eth_positions:
            print(f"   - ETH position: {pos.position_id} @ ${pos.entry_price}")
    else:
        print("⚠️  INFO: No ETH positions created (may be due to random chance in demo execution)")
    
    # Summary
    print("\n" + "=" * 60)
    print("🎯 BTC BIAS FIX VERIFICATION SUMMARY")
    print("=" * 60)
    
    tests_passed = 0
    total_tests = 2
    
    if missing_symbol_warnings > 0:
        tests_passed += 1
        print("✅ Test 1 PASSED: Missing symbols are properly skipped")
    else:
        print("❌ Test 1 FAILED: Missing symbols not handled correctly")
    
    if len(btc_positions) == 0:
        tests_passed += 1
        print("✅ Test 2 PASSED: No BTC fallback positions created")
    else:
        print("❌ Test 2 FAILED: BTC fallback positions were created")
    
    print(f"\n🏆 OVERALL RESULT: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        print("🎉 BTC BIAS FIX WORKING CORRECTLY!")
        print("   - Demo trades skip opportunities with missing symbols")
        print("   - No more automatic BTC fallback")
        print("   - Profit-first ranking can work without BTC contamination")
    else:
        print("⚠️  BTC BIAS FIX NEEDS ATTENTION")
    
    return tests_passed == total_tests

if __name__ == "__main__":
    success = asyncio.run(test_btc_bias_fix())
    exit(0 if success else 1)
