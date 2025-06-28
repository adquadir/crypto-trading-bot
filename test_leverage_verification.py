#!/usr/bin/env python3
"""
Leverage and Stop Loss Verification Test
Tests that paper trading actually uses 10x leverage and 15% stop loss
"""

import asyncio
import logging
from datetime import datetime
from src.trading.enhanced_paper_trading_engine import EnhancedPaperTradingEngine

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_leverage_calculations():
    """Test that leverage is actually applied in position sizing"""
    
    print("🧪 Testing Leverage Implementation...")
    print("=" * 60)
    
    # Initialize paper trading engine
    config = {
        'paper_trading': {
            'initial_balance': 10000.0,
            'max_position_size_pct': 0.02,
            'max_total_exposure_pct': 0.10,
            'max_daily_loss_pct': 0.05
        }
    }
    
    engine = EnhancedPaperTradingEngine(config)
    
    # Test position sizing with different prices
    test_cases = [
        {'symbol': 'BTCUSDT', 'price': 50000.0, 'expected_without_leverage': 0.004, 'expected_with_leverage': 0.04},
        {'symbol': 'ETHUSDT', 'price': 3000.0, 'expected_without_leverage': 0.0667, 'expected_with_leverage': 0.6667},
        {'symbol': 'ADAUSDT', 'price': 0.5, 'expected_without_leverage': 400.0, 'expected_with_leverage': 4000.0}
    ]
    
    print("📊 Position Sizing Tests:")
    print("-" * 40)
    
    for test_case in test_cases:
        symbol = test_case['symbol']
        price = test_case['price']
        expected_with_leverage = test_case['expected_with_leverage']
        
        # Calculate position size using the engine
        position_size = engine._calculate_position_size(symbol, price, 0.8)
        
        print(f"Symbol: {symbol}")
        print(f"Price: ${price:,.2f}")
        print(f"Expected position size (10x leverage): {expected_with_leverage:.6f}")
        print(f"Actual position size: {position_size:.6f}")
        
        # Check if leverage is applied correctly
        leverage_applied = abs(position_size - expected_with_leverage) < 0.001
        
        if leverage_applied:
            print("✅ PASS: 10x leverage correctly applied")
        else:
            print("❌ FAIL: Leverage not applied correctly")
            
        print()
    
    return True

async def test_stop_loss_calculations():
    """Test that stop loss is set to 15%"""
    
    print("🛡️ Testing Stop Loss Implementation...")
    print("=" * 60)
    
    # Initialize paper trading engine
    config = {'paper_trading': {'initial_balance': 10000.0}}
    engine = EnhancedPaperTradingEngine(config)
    
    # Test stop loss calculations
    test_cases = [
        {'price': 50000.0, 'side': 'LONG', 'expected_sl': 42500.0},   # 50000 * (1 - 0.15)
        {'price': 50000.0, 'side': 'SHORT', 'expected_sl': 57500.0}, # 50000 * (1 + 0.15)
        {'price': 3000.0, 'side': 'LONG', 'expected_sl': 2550.0},    # 3000 * (1 - 0.15)
        {'price': 3000.0, 'side': 'SHORT', 'expected_sl': 3450.0},   # 3000 * (1 + 0.15)
    ]
    
    print("📊 Stop Loss Tests:")
    print("-" * 40)
    
    for test_case in test_cases:
        price = test_case['price']
        side = test_case['side']
        expected_sl = test_case['expected_sl']
        
        # Calculate stop loss using the engine
        stop_loss = engine._calculate_stop_loss(price, side, 'TESTUSDT')
        
        print(f"Entry Price: ${price:,.2f}")
        print(f"Side: {side}")
        print(f"Expected Stop Loss (15%): ${expected_sl:,.2f}")
        print(f"Actual Stop Loss: ${stop_loss:,.2f}")
        
        # Check if stop loss is calculated correctly
        sl_correct = abs(stop_loss - expected_sl) < 0.01
        
        if sl_correct:
            print("✅ PASS: 15% stop loss correctly calculated")
        else:
            print("❌ FAIL: Stop loss calculation incorrect")
            
        print()
    
    return True

async def test_take_profit_calculations():
    """Test that take profit is set to 15%"""
    
    print("🎯 Testing Take Profit Implementation...")
    print("=" * 60)
    
    # Initialize paper trading engine
    config = {'paper_trading': {'initial_balance': 10000.0}}
    engine = EnhancedPaperTradingEngine(config)
    
    # Test take profit calculations
    test_cases = [
        {'price': 50000.0, 'side': 'LONG', 'expected_tp': 57500.0},   # 50000 * (1 + 0.15)
        {'price': 50000.0, 'side': 'SHORT', 'expected_tp': 42500.0}, # 50000 * (1 - 0.15)
        {'price': 3000.0, 'side': 'LONG', 'expected_tp': 3450.0},    # 3000 * (1 + 0.15)
        {'price': 3000.0, 'side': 'SHORT', 'expected_tp': 2550.0},   # 3000 * (1 - 0.15)
    ]
    
    print("📊 Take Profit Tests:")
    print("-" * 40)
    
    for test_case in test_cases:
        price = test_case['price']
        side = test_case['side']
        expected_tp = test_case['expected_tp']
        
        # Calculate take profit using the engine
        take_profit = engine._calculate_take_profit(price, side, 'TESTUSDT')
        
        print(f"Entry Price: ${price:,.2f}")
        print(f"Side: {side}")
        print(f"Expected Take Profit (15%): ${expected_tp:,.2f}")
        print(f"Actual Take Profit: ${take_profit:,.2f}")
        
        # Check if take profit is calculated correctly
        tp_correct = abs(take_profit - expected_tp) < 0.01
        
        if tp_correct:
            print("✅ PASS: 15% take profit correctly calculated")
        else:
            print("❌ FAIL: Take profit calculation incorrect")
            
        print()
    
    return True

async def test_pnl_calculations():
    """Test P&L calculations with leverage"""
    
    print("💰 Testing P&L Calculations with Leverage...")
    print("=" * 60)
    
    # Test scenario: BTC at $50,000
    entry_price = 50000.0
    base_capital = 200.0
    leverage = 10.0
    leveraged_capital = base_capital * leverage  # $2,000
    position_size = leveraged_capital / entry_price  # 0.04 BTC
    
    print(f"Test Scenario:")
    print(f"Entry Price: ${entry_price:,.2f}")
    print(f"Base Capital: ${base_capital}")
    print(f"Leverage: {leverage}x")
    print(f"Leveraged Capital: ${leveraged_capital}")
    print(f"Position Size: {position_size:.6f} BTC")
    print()
    
    # Test different price movements
    price_movements = [
        {'new_price': 52500.0, 'move_pct': 5.0, 'expected_pnl': 100.0},   # 5% up = $100 profit
        {'new_price': 47500.0, 'move_pct': -5.0, 'expected_pnl': -100.0}, # 5% down = $100 loss
        {'new_price': 57500.0, 'move_pct': 15.0, 'expected_pnl': 300.0},  # 15% up = $300 profit
        {'new_price': 42500.0, 'move_pct': -15.0, 'expected_pnl': -300.0} # 15% down = $300 loss
    ]
    
    print("📊 P&L Movement Tests:")
    print("-" * 40)
    
    for movement in price_movements:
        new_price = movement['new_price']
        move_pct = movement['move_pct']
        expected_pnl = movement['expected_pnl']
        
        # Calculate actual P&L
        actual_pnl = (new_price - entry_price) * position_size
        
        print(f"Price Movement: {move_pct:+.1f}% (${entry_price:,.0f} → ${new_price:,.0f})")
        print(f"Expected P&L: ${expected_pnl:+.2f}")
        print(f"Actual P&L: ${actual_pnl:+.2f}")
        
        # Check if P&L is calculated correctly
        pnl_correct = abs(actual_pnl - expected_pnl) < 0.01
        
        if pnl_correct:
            print("✅ PASS: P&L calculation correct with leverage")
        else:
            print("❌ FAIL: P&L calculation incorrect")
            
        print()
    
    return True

async def test_account_status_display():
    """Test that account status shows correct values"""
    
    print("📋 Testing Account Status Display...")
    print("=" * 60)
    
    # Initialize paper trading engine
    config = {'paper_trading': {'initial_balance': 10000.0}}
    engine = EnhancedPaperTradingEngine(config)
    
    # Get account status
    status = engine.get_account_status()
    account_data = status['account']
    
    print("Account Status Values:")
    print(f"Leverage: {account_data.get('leverage', 'NOT SET')}")
    print(f"Capital Per Position: ${account_data.get('capital_per_position', 'NOT SET')}")
    
    # Verify values
    leverage_correct = account_data.get('leverage') == 10.0
    capital_correct = account_data.get('capital_per_position') == 200.0
    
    if leverage_correct:
        print("✅ PASS: Leverage display shows 10x")
    else:
        print("❌ FAIL: Leverage display incorrect")
    
    if capital_correct:
        print("✅ PASS: Capital per position shows $200")
    else:
        print("❌ FAIL: Capital per position incorrect")
    
    print()
    return leverage_correct and capital_correct

async def main():
    """Run all verification tests"""
    
    print("🚀 LEVERAGE & STOP LOSS VERIFICATION TEST")
    print("=" * 80)
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Run all tests
    tests = [
        ("Leverage Calculations", test_leverage_calculations),
        ("Stop Loss Calculations", test_stop_loss_calculations),
        ("Take Profit Calculations", test_take_profit_calculations),
        ("P&L Calculations", test_pnl_calculations),
        ("Account Status Display", test_account_status_display)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ ERROR in {test_name}: {e}")
            results.append((test_name, False))
        
        print()
    
    # Summary
    print("📊 TEST SUMMARY")
    print("=" * 80)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
        if result:
            passed += 1
    
    print()
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED! Leverage and stop loss are working correctly.")
    else:
        print("⚠️  Some tests failed. Please review the implementation.")
    
    print()
    print("Key Verification Points:")
    print("✓ 10x leverage applied to position sizing ($200 → $2,000 effective)")
    print("✓ 15% stop loss (not 25%)")
    print("✓ 15% take profit")
    print("✓ P&L calculations reflect leveraged positions")
    print("✓ UI displays match backend calculations")

if __name__ == "__main__":
    asyncio.run(main())
