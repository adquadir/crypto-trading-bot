#!/usr/bin/env python3
"""
Test script to verify directional accuracy fixes are working correctly.
This tests the direction normalization and TP/SL orientation fixes.
"""

import asyncio
import logging
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.opportunity.opportunity_manager import OpportunityManager
from src.trading.enhanced_paper_trading_engine import EnhancedPaperTradingEngine
from src.market_data.exchange_client import ExchangeClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_direction_normalization():
    """Test that direction normalization works correctly."""
    print("\n" + "="*80)
    print("🧪 TESTING DIRECTION NORMALIZATION")
    print("="*80)
    
    # Create a mock opportunity manager to test direction normalization
    exchange_client = ExchangeClient()
    opportunity_manager = OpportunityManager(exchange_client, None, None)
    
    # Test various direction inputs
    test_cases = [
        ("LONG", "LONG"),
        ("BUY", "LONG"),
        ("BULL", "LONG"),
        ("UP", "LONG"),
        ("long", "LONG"),
        ("buy", "LONG"),
        ("SHORT", "SHORT"),
        ("SELL", "SHORT"),
        ("BEAR", "SHORT"),
        ("DOWN", "SHORT"),
        ("short", "SHORT"),
        ("sell", "SHORT"),
        ("UNKNOWN", "UNKNOWN"),
        ("", "UNKNOWN"),
        (None, "UNKNOWN"),
    ]
    
    print("Testing direction normalization:")
    all_passed = True
    
    for input_dir, expected_dir in test_cases:
        normalized = opportunity_manager._normalize_direction(input_dir)
        status = "✅ PASS" if normalized == expected_dir else "❌ FAIL"
        print(f"  {input_dir!r:10} → {normalized:8} (expected: {expected_dir:8}) {status}")
        if normalized != expected_dir:
            all_passed = False
    
    print(f"\nDirection normalization test: {'✅ ALL PASSED' if all_passed else '❌ SOME FAILED'}")
    return all_passed

async def test_tp_sl_orientation():
    """Test that TP/SL orientation is fixed correctly."""
    print("\n" + "="*80)
    print("🧪 TESTING TP/SL ORIENTATION FIXES")
    print("="*80)
    
    # Create a mock opportunity manager
    exchange_client = ExchangeClient()
    opportunity_manager = OpportunityManager(exchange_client, None, None)
    
    # Test cases: (direction, entry, tp, sl, expected_tp, expected_sl)
    test_cases = [
        # LONG positions - TP should be above entry, SL should be below entry
        ("LONG", 100.0, 105.0, 95.0, 105.0, 95.0),  # Correct orientation
        ("LONG", 100.0, 95.0, 105.0, 105.0, 95.0),  # Swapped - should fix
        ("LONG", 100.0, 90.0, 110.0, 100.05, 99.95),  # Both wrong - should fix
        
        # SHORT positions - TP should be below entry, SL should be above entry
        ("SHORT", 100.0, 95.0, 105.0, 95.0, 105.0),  # Correct orientation
        ("SHORT", 100.0, 105.0, 95.0, 95.0, 105.0),  # Swapped - should fix
        ("SHORT", 100.0, 110.0, 90.0, 99.95, 100.05),  # Both wrong - should fix
    ]
    
    print("Testing TP/SL orientation fixes:")
    all_passed = True
    
    for direction, entry, tp_in, sl_in, expected_tp, expected_sl in test_cases:
        tp_out, sl_out = opportunity_manager._fix_tp_sl_for_direction(direction, entry, tp_in, sl_in)
        
        # Check if TP/SL are correctly oriented
        tp_correct = (direction == "LONG" and tp_out > entry) or (direction == "SHORT" and tp_out < entry)
        sl_correct = (direction == "LONG" and sl_out < entry) or (direction == "SHORT" and sl_out > entry)
        
        status = "✅ PASS" if tp_correct and sl_correct else "❌ FAIL"
        print(f"  {direction:5} Entry:{entry:6.2f} TP:{tp_in:6.2f}→{tp_out:6.2f} SL:{sl_in:6.2f}→{sl_out:6.2f} {status}")
        
        if not (tp_correct and sl_correct):
            all_passed = False
            print(f"    Expected: TP {'>' if direction == 'LONG' else '<'} {entry}, SL {'<' if direction == 'LONG' else '>'} {entry}")
    
    print(f"\nTP/SL orientation test: {'✅ ALL PASSED' if all_passed else '❌ SOME FAILED'}")
    return all_passed

async def test_opportunity_finalization():
    """Test that opportunity finalization works correctly."""
    print("\n" + "="*80)
    print("🧪 TESTING OPPORTUNITY FINALIZATION")
    print("="*80)
    
    # Create a mock opportunity manager
    exchange_client = ExchangeClient()
    opportunity_manager = OpportunityManager(exchange_client, None, None)
    
    # Test cases with various direction formats and TP/SL orientations
    test_opportunities = [
        {
            "symbol": "BTCUSDT",
            "direction": "BUY",  # Should normalize to LONG
            "entry_price": 50000,
            "take_profit": 45000,  # Wrong side - should fix
            "stop_loss": 55000,    # Wrong side - should fix
            "confidence": 0.8
        },
        {
            "symbol": "ETHUSDT", 
            "direction": "SELL",  # Should normalize to SHORT
            "entry_price": 3000,
            "take_profit": 3200,  # Wrong side - should fix
            "stop_loss": 2800,    # Wrong side - should fix
            "confidence": 0.7
        },
        {
            "symbol": "ADAUSDT",
            "direction": "LONG",  # Already correct
            "entry_price": 1.0,
            "take_profit": 1.05,  # Correct side
            "stop_loss": 0.95,    # Correct side
            "confidence": 0.6
        }
    ]
    
    print("Testing opportunity finalization:")
    all_passed = True
    
    for i, opp in enumerate(test_opportunities):
        print(f"\nTest case {i+1}: {opp['symbol']}")
        print(f"  Input:  Direction={opp['direction']:4} Entry={opp['entry_price']:6.0f} TP={opp['take_profit']:6.0f} SL={opp['stop_loss']:6.0f}")
        
        # Finalize the opportunity
        finalized = opportunity_manager._finalize_opportunity(opp.copy())
        
        # Check results
        direction = finalized['direction']
        entry = finalized['entry_price']
        tp = finalized['take_profit']
        sl = finalized['stop_loss']
        
        # Verify direction normalization
        direction_correct = direction in ['LONG', 'SHORT']
        
        # Verify TP/SL orientation
        if direction == 'LONG':
            tp_correct = tp > entry
            sl_correct = sl < entry
        elif direction == 'SHORT':
            tp_correct = tp < entry
            sl_correct = sl > entry
        else:
            tp_correct = sl_correct = False
        
        # Verify risk/reward calculation
        rr = finalized.get('risk_reward', 0)
        expected_rr = abs(tp - entry) / abs(entry - sl) if abs(entry - sl) > 0 else 0
        rr_correct = abs(rr - expected_rr) < 0.01
        
        all_correct = direction_correct and tp_correct and sl_correct and rr_correct
        status = "✅ PASS" if all_correct else "❌ FAIL"
        
        print(f"  Output: Direction={direction:5} Entry={entry:6.0f} TP={tp:6.0f} SL={sl:6.0f} R/R={rr:.2f} {status}")
        
        if not all_correct:
            all_passed = False
            if not direction_correct:
                print(f"    ❌ Direction not normalized properly")
            if not tp_correct:
                print(f"    ❌ Take profit on wrong side of entry")
            if not sl_correct:
                print(f"    ❌ Stop loss on wrong side of entry")
            if not rr_correct:
                print(f"    ❌ Risk/reward calculation incorrect: got {rr:.2f}, expected {expected_rr:.2f}")
    
    print(f"\nOpportunity finalization test: {'✅ ALL PASSED' if all_passed else '❌ SOME FAILED'}")
    return all_passed

async def test_paper_trading_direction_normalization():
    """Test that paper trading engine normalizes directions correctly."""
    print("\n" + "="*80)
    print("🧪 TESTING PAPER TRADING DIRECTION NORMALIZATION")
    print("="*80)
    
    # Create mock config and exchange client
    config = {
        'paper_trading': {
            'initial_balance': 10000,
            'fees': {'rate': 0.0004},
            'slippage': {'rate': 0.0003},
            'latency': {'ms': 50}
        }
    }
    
    # Mock exchange client that returns a fixed price
    class MockExchangeClient:
        async def get_ticker_24h(self, symbol):
            return {'lastPrice': '50000.0'}
    
    exchange_client = MockExchangeClient()
    paper_engine = EnhancedPaperTradingEngine(config, exchange_client)
    
    # Test signals with various direction formats
    test_signals = [
        {'symbol': 'BTCUSDT', 'direction': 'BUY', 'entry_price': 50000, 'strategy': 'test'},
        {'symbol': 'ETHUSDT', 'direction': 'BULL', 'entry_price': 3000, 'strategy': 'test'},
        {'symbol': 'ADAUSDT', 'direction': 'UP', 'entry_price': 1.0, 'strategy': 'test'},
        {'symbol': 'SOLUSDT', 'direction': 'SELL', 'entry_price': 100, 'strategy': 'test'},
        {'symbol': 'XRPUSDT', 'direction': 'BEAR', 'entry_price': 0.5, 'strategy': 'test'},
        {'symbol': 'DOTUSDT', 'direction': 'DOWN', 'entry_price': 10, 'strategy': 'test'},
    ]
    
    print("Testing paper trading direction normalization:")
    all_passed = True
    
    for signal in test_signals:
        original_direction = signal['direction']
        
        # Execute the trade (this will normalize the direction internally)
        position_id = await paper_engine.execute_virtual_trade(signal, 500.0)
        
        if position_id:
            # Check the stored position
            position = paper_engine.virtual_positions[position_id]
            normalized_direction = position.side
            
            # Verify normalization
            if original_direction.upper() in ['BUY', 'BULL', 'UP', 'LONG']:
                expected = 'LONG'
            else:
                expected = 'SHORT'
            
            correct = normalized_direction == expected
            status = "✅ PASS" if correct else "❌ FAIL"
            
            print(f"  {signal['symbol']:8} {original_direction:4} → {normalized_direction:5} (expected: {expected:5}) {status}")
            
            if not correct:
                all_passed = False
        else:
            print(f"  {signal['symbol']:8} {original_direction:4} → FAILED TO EXECUTE")
            all_passed = False
    
    print(f"\nPaper trading direction normalization test: {'✅ ALL PASSED' if all_passed else '❌ SOME FAILED'}")
    return all_passed

async def main():
    """Run all directional accuracy tests."""
    print("🚀 STARTING DIRECTIONAL ACCURACY VERIFICATION TESTS")
    print("="*80)
    
    # Run all tests
    test_results = []
    
    try:
        test_results.append(await test_direction_normalization())
        test_results.append(await test_tp_sl_orientation())
        test_results.append(await test_opportunity_finalization())
        test_results.append(await test_paper_trading_direction_normalization())
        
        # Summary
        print("\n" + "="*80)
        print("📊 TEST SUMMARY")
        print("="*80)
        
        passed_tests = sum(test_results)
        total_tests = len(test_results)
        
        test_names = [
            "Direction Normalization",
            "TP/SL Orientation Fixes", 
            "Opportunity Finalization",
            "Paper Trading Direction Normalization"
        ]
        
        for i, (name, passed) in enumerate(zip(test_names, test_results)):
            status = "✅ PASSED" if passed else "❌ FAILED"
            print(f"{i+1}. {name:35} {status}")
        
        print(f"\nOverall Result: {passed_tests}/{total_tests} tests passed")
        
        if passed_tests == total_tests:
            print("🎉 ALL DIRECTIONAL ACCURACY FIXES ARE WORKING CORRECTLY!")
            return True
        else:
            print("⚠️  SOME TESTS FAILED - DIRECTIONAL ACCURACY ISSUES REMAIN")
            return False
            
    except Exception as e:
        print(f"❌ Test execution failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
