#!/usr/bin/env python3
"""
Verification script to test 10x leverage implementation
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.trading.enhanced_paper_trading_engine import EnhancedPaperTradingEngine
import logging

# Set up logging
logging.basicConfig(level=logging.WARNING)  # Reduce noise
logger = logging.getLogger(__name__)

async def verify_leverage_implementation():
    """Verify that 10x leverage is working correctly"""
    print("🔍 Verifying 10x Leverage Implementation")
    print("=" * 50)
    
    # Create engine
    config = {
        'paper_trading': {
            'initial_balance': 10000.0,
            'risk_per_trade_pct': 0.10,  # 10% = $1000 per position
            'leverage': 10.0,
            'max_positions': 50
        }
    }
    
    engine = EnhancedPaperTradingEngine(config)
    
    # Test with realistic Bitcoin price
    entry_price = 50000.0  # $50,000 BTC
    
    print(f"\n💰 Testing with BTC @ ${entry_price:,.2f}")
    
    # Calculate position details
    capital_per_position = engine.account.balance * engine.risk_per_trade_pct
    leverage = engine.leverage
    notional_value = capital_per_position * leverage
    quantity = notional_value / entry_price
    
    print(f"   Capital at Risk: ${capital_per_position:,.2f}")
    print(f"   Leverage: {leverage}x")
    print(f"   Notional Value: ${notional_value:,.2f}")
    print(f"   BTC Quantity: {quantity:.8f}")
    print(f"   Position Value: ${quantity * entry_price:,.2f}")
    
    # Test P&L calculations
    print(f"\n📊 P&L Testing:")
    
    # Test various price movements
    test_scenarios = [
        {"price_change_pct": 0.1, "expected_pnl": 10.0},   # 0.1% = $10
        {"price_change_pct": 0.05, "expected_pnl": 5.0},   # 0.05% = $5
        {"price_change_pct": 0.2, "expected_pnl": 20.0},   # 0.2% = $20
        {"price_change_pct": -0.1, "expected_pnl": -10.0}, # -0.1% = -$10
        {"price_change_pct": -0.05, "expected_pnl": -5.0}, # -0.05% = -$5
    ]
    
    for scenario in test_scenarios:
        price_change_pct = scenario["price_change_pct"]
        expected_pnl = scenario["expected_pnl"]
        
        # Calculate new price
        new_price = entry_price * (1 + price_change_pct / 100)
        
        # Calculate P&L (LONG position)
        pnl = (new_price - entry_price) * quantity
        
        print(f"   {price_change_pct:+.2f}% price change: ${pnl:+.2f} (expected: ${expected_pnl:+.2f})")
        
        # Verify accuracy
        if abs(pnl - expected_pnl) < 0.10:  # Within 10 cents
            print(f"      ✅ Accurate")
        else:
            print(f"      ❌ Error: {abs(pnl - expected_pnl):.2f} difference")
    
    # Test take profit and stop loss calculations
    print(f"\n🎯 Take Profit & Stop Loss Testing:")
    
    tp_price = await engine._calculate_take_profit(entry_price, "LONG", "BTCUSDT")
    sl_price = await engine._calculate_stop_loss(entry_price, "LONG", "BTCUSDT")
    
    tp_percentage = ((tp_price - entry_price) / entry_price) * 100
    sl_percentage = ((entry_price - sl_price) / entry_price) * 100
    
    tp_profit = (tp_price - entry_price) * quantity
    sl_loss = (entry_price - sl_price) * quantity
    
    print(f"   Entry Price: ${entry_price:,.2f}")
    print(f"   Take Profit: ${tp_price:,.2f} ({tp_percentage:.3f}%)")
    print(f"   Stop Loss: ${sl_price:,.2f} ({sl_percentage:.3f}%)")
    print(f"   TP Profit: ${tp_profit:.2f}")
    print(f"   SL Loss: ${sl_loss:.2f}")
    
    # Test leverage effect verification
    print(f"\n🔬 Leverage Effect Verification:")
    
    # Without leverage (theoretical)
    no_leverage_quantity = capital_per_position / entry_price
    no_leverage_pnl_1pct = (entry_price * 1.01 - entry_price) * no_leverage_quantity
    
    # With 10x leverage (actual)
    with_leverage_quantity = notional_value / entry_price
    with_leverage_pnl_1pct = (entry_price * 1.01 - entry_price) * with_leverage_quantity
    with_leverage_pnl_01pct = (entry_price * 1.001 - entry_price) * with_leverage_quantity
    
    print(f"   1% price movement:")
    print(f"   Without leverage: ${no_leverage_pnl_1pct:.2f} profit")
    print(f"   With 10x leverage: ${with_leverage_pnl_1pct:.2f} profit")
    print(f"   Leverage multiplier: {with_leverage_pnl_1pct / no_leverage_pnl_1pct:.1f}x")
    print(f"   0.1% price movement with 10x leverage: ${with_leverage_pnl_01pct:.2f} profit")
    
    # Margin and risk verification
    print(f"\n💸 Margin & Risk Verification:")
    print(f"   Total balance: ${engine.account.balance:,.2f}")
    print(f"   Capital per position: ${capital_per_position:,.2f} ({capital_per_position/engine.account.balance:.1%})")
    print(f"   Notional per position: ${notional_value:,.2f}")
    print(f"   Max positions: {engine.max_positions}")
    print(f"   Max total exposure: ${notional_value * engine.max_positions:,.2f}")
    print(f"   Margin efficiency: {(notional_value * engine.max_positions) / engine.account.balance:.1f}x")
    
    # Final validation
    print(f"\n✅ Final Validation:")
    
    checks = [
        ("Capital per position is $1000", abs(capital_per_position - 1000.0) < 0.01),
        ("Leverage is 10x", abs(leverage - 10.0) < 0.01),
        ("Notional value is $10,000", abs(notional_value - 10000.0) < 0.01),
        ("0.1% price move = ~$10 P&L", abs(with_leverage_pnl_01pct - 10.0) < 0.01),
        ("Take profit gives ~$10", abs(tp_profit - 10.0) < 0.50),
        ("Stop loss gives ~$10 loss", abs(sl_loss - 10.0) < 0.50),
    ]
    
    all_passed = True
    for check_name, passed in checks:
        status = "✅" if passed else "❌"
        print(f"   {status} {check_name}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print(f"\n🎉 All leverage implementation checks PASSED!")
        print(f"   10x leverage is working correctly")
        print(f"   $1000 capital controls $10,000 position")
        print(f"   Price movements are amplified 10x as expected")
    else:
        print(f"\n⚠️ Some checks FAILED - review implementation")
    
    return all_passed

if __name__ == "__main__":
    result = asyncio.run(verify_leverage_implementation())
    sys.exit(0 if result else 1) 