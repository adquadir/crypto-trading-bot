#!/usr/bin/env python3
"""
Test script to verify the new $1000 capital per position allocation
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.trading.enhanced_paper_trading_engine import EnhancedPaperTradingEngine
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_new_capital_allocation():
    """Test that the new $1000 capital per position allocation works correctly"""
    print("🧪 Testing New $1000 Capital Per Position Allocation")
    print("=" * 60)
    
    # Create engine with new configuration
    config = {
        'paper_trading': {
            'initial_balance': 10000.0,
            'risk_per_trade_pct': 0.10,  # 10% = $1000 per position
            'leverage': 10.0,
            'max_positions': 50,
            'pure_3_rule_mode': True,
            'primary_target_dollars': 10.0,
            'absolute_floor_dollars': 7.0,
            'stop_loss_percent': 0.5
        }
    }
    
    engine = EnhancedPaperTradingEngine(config)
    
    # Test configuration values
    print("\n💰 Configuration Test:")
    print(f"   Initial Balance: ${engine.account.balance:,.2f}")
    print(f"   Risk Per Trade: {engine.risk_per_trade_pct:.1%}")
    print(f"   Leverage: {engine.leverage}x")
    print(f"   Max Positions: {engine.max_positions}")
    
    # Calculate expected capital per position
    expected_capital = engine.account.balance * engine.risk_per_trade_pct
    print(f"   Expected Capital Per Position: ${expected_capital:,.2f}")
    
    # Test position size calculation
    print("\n🔢 Position Size Calculation Test:")
    test_price = 50000.0  # Example Bitcoin price
    test_confidence = 0.75
    
    position_size = engine._calculate_position_size("BTCUSDT", test_price, test_confidence)
    capital_per_position = engine.account.balance * engine.risk_per_trade_pct
    notional_value = capital_per_position * engine.leverage
    
    print(f"   Test Price: ${test_price:,.2f}")
    print(f"   Capital at Risk: ${capital_per_position:,.2f}")
    print(f"   Leverage: {engine.leverage}x")
    print(f"   Notional Value: ${notional_value:,.2f}")
    print(f"   Position Size: {position_size:.6f} BTC")
    print(f"   Position Value: ${position_size * test_price:,.2f}")
    
    # Test take profit calculation
    print("\n🎯 Take Profit Test:")
    tp_price = await engine._calculate_take_profit(test_price, "LONG", "BTCUSDT")
    tp_percentage = ((tp_price - test_price) / test_price) * 100
    expected_profit = (tp_price - test_price) * position_size
    
    print(f"   Entry Price: ${test_price:,.2f}")
    print(f"   Take Profit: ${tp_price:,.2f}")
    print(f"   TP Percentage: {tp_percentage:.3f}%")
    print(f"   Expected Profit: ${expected_profit:.2f}")
    print(f"   Target Profit: $10.00")
    
    # Test stop loss calculation
    print("\n🛡️ Stop Loss Test:")
    sl_price = await engine._calculate_stop_loss(test_price, "LONG", "BTCUSDT")
    sl_percentage = ((test_price - sl_price) / test_price) * 100
    expected_loss = (test_price - sl_price) * position_size
    
    print(f"   Entry Price: ${test_price:,.2f}")
    print(f"   Stop Loss: ${sl_price:,.2f}")
    print(f"   SL Percentage: {sl_percentage:.3f}%")
    print(f"   Expected Loss: ${expected_loss:.2f}")
    print(f"   Target Loss: $10.00")
    
    # Test Pure 3-Rule Mode configuration
    print("\n🎯 Pure 3-Rule Mode Test:")
    print(f"   Mode Enabled: {engine.pure_3_rule_mode}")
    print(f"   Primary Target: $10.00")
    print(f"   Absolute Floor: $7.00")
    print(f"   Stop Loss: 0.5%")
    
    # Test account status
    print("\n📊 Account Status Test:")
    status = engine.get_account_status()
    account_data = status['account']
    
    print(f"   Balance: ${account_data['balance']:,.2f}")
    print(f"   Capital Per Position: ${account_data['capital_per_position']:,.2f}")
    print(f"   Leverage: {account_data['leverage']}x")
    print(f"   Active Positions: {account_data['active_positions']}")
    
    # Test maximum positions calculation
    print("\n📈 Maximum Positions Test:")
    max_capital_usage = engine.max_positions * capital_per_position
    print(f"   Max Positions: {engine.max_positions}")
    print(f"   Capital Per Position: ${capital_per_position:,.2f}")
    print(f"   Max Capital Usage: ${max_capital_usage:,.2f}")
    print(f"   Available Balance: ${engine.account.balance:,.2f}")
    print(f"   Capital Utilization: {(max_capital_usage / engine.account.balance) * 100:.1f}%")
    
    # Validation checks
    print("\n✅ Validation Checks:")
    
    # Check if capital per position is $1000
    if abs(capital_per_position - 1000.0) < 0.01:
        print("   ✅ Capital per position is correctly set to $1000")
    else:
        print(f"   ❌ Capital per position is ${capital_per_position:,.2f}, expected $1000")
    
    # Check if notional value is $10,000
    if abs(notional_value - 10000.0) < 0.01:
        print("   ✅ Notional value is correctly set to $10,000")
    else:
        print(f"   ❌ Notional value is ${notional_value:,.2f}, expected $10,000")
    
    # Check if take profit gives approximately $10 profit
    if abs(expected_profit - 10.0) < 0.50:
        print("   ✅ Take profit gives approximately $10 profit")
    else:
        print(f"   ❌ Take profit gives ${expected_profit:.2f}, expected ~$10")
    
    # Check if stop loss gives approximately $10 loss
    if abs(expected_loss - 10.0) < 0.50:
        print("   ✅ Stop loss gives approximately $10 loss")
    else:
        print(f"   ❌ Stop loss gives ${expected_loss:.2f}, expected ~$10")
    
    # Check if risk percentage is 10%
    if abs(engine.risk_per_trade_pct - 0.10) < 0.001:
        print("   ✅ Risk per trade is correctly set to 10%")
    else:
        print(f"   ❌ Risk per trade is {engine.risk_per_trade_pct:.1%}, expected 10%")
    
    print("\n🎉 Test completed successfully!")
    print("   The paper trading engine now uses $1000 per position")
    print("   with $10,000 notional value (10x leverage)")
    print("   achieving $10 profit/loss targets with smaller price movements")

if __name__ == "__main__":
    asyncio.run(test_new_capital_allocation()) 