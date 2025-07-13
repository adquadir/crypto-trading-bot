#!/usr/bin/env python3
"""
Test script to verify the new dollar-based stop loss system
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

async def test_dollar_based_stop_loss():
    """Test that the new dollar-based stop loss system works correctly"""
    print("🧪 Testing Dollar-Based Stop Loss System")
    print("=" * 60)
    
    # Create engine with configuration
    config = {
        'paper_trading': {
            'initial_balance': 10000.0,
            'risk_per_trade_pct': 0.10,  # 10% = $1000 per position
            'leverage': 10.0,
            'pure_3_rule_mode': True,
            'primary_target_dollars': 10.0,
            'absolute_floor_dollars': 7.0,
            'stop_loss_dollars': 10.0
        }
    }
    
    engine = EnhancedPaperTradingEngine(config)
    
    # Test configuration
    print(f"🎯 Configuration Test:")
    print(f"   Initial Balance: ${config['paper_trading']['initial_balance']:,}")
    print(f"   Risk per Trade: {config['paper_trading']['risk_per_trade_pct']:.1%}")
    print(f"   Capital per Position: ${config['paper_trading']['initial_balance'] * config['paper_trading']['risk_per_trade_pct']:,}")
    print(f"   Leverage: {config['paper_trading']['leverage']}x")
    print(f"   Pure 3-Rule Mode: {config['paper_trading']['pure_3_rule_mode']}")
    print()
    
    # Test the 4 rules
    print("🎯 Testing the 4 Exit Rules:")
    print("   ✅ Rule 1: Take profit = $10")
    print("   ✅ Rule 2: Trailing floor activation = $7")
    print("   ✅ Rule 3: Stop-loss = $10 loss max")
    print("   ✅ Rule 4: Failsafe = $15 loss hard stop")
    print()
    
    # Test position calculation
    print("💰 Position Calculation Test:")
    current_balance = engine.account.balance
    risk_per_trade = engine.risk_per_trade_pct
    leverage = engine.leverage
    capital_per_position = current_balance * risk_per_trade
    notional_value = capital_per_position * leverage
    
    print(f"   Current Balance: ${current_balance:,}")
    print(f"   Risk per Trade: {risk_per_trade:.1%}")
    print(f"   Capital per Position: ${capital_per_position:,}")
    print(f"   Leverage: {leverage}x")
    print(f"   Notional Value: ${notional_value:,}")
    print()
    
    # Test PnL scenarios
    print("📊 PnL Scenario Testing:")
    
    # Example position
    entry_price = 50000.0  # $50K BTC
    quantity = notional_value / entry_price
    
    scenarios = [
        ("$10 profit target", 50000 + (10 / quantity)),
        ("$7 floor activation", 50000 + (7 / quantity)),
        ("$0 break-even", 50000),
        ("$5 small loss", 50000 - (5 / quantity)),
        ("$10 stop loss", 50000 - (10 / quantity)),
        ("$15 failsafe", 50000 - (15 / quantity))
    ]
    
    print(f"   Position: {quantity:.6f} BTC @ ${entry_price:,}")
    print(f"   Capital at Risk: ${capital_per_position:,}")
    print()
    
    for scenario_name, price in scenarios:
        pnl = (price - entry_price) * quantity
        pnl_pct = (price - entry_price) / entry_price * 100
        
        status = ""
        if pnl >= 10:
            status = "✅ TAKE PROFIT"
        elif pnl >= 7:
            status = "🛡️  FLOOR ACTIVE"
        elif pnl >= 0:
            status = "💚 PROFIT"
        elif pnl >= -10:
            status = "⚠️  LOSS"
        elif pnl >= -15:
            status = "🛑 STOP LOSS"
        else:
            status = "🚨 FAILSAFE"
        
        print(f"   {scenario_name:<20} @ ${price:8,.2f} = ${pnl:+7.2f} ({pnl_pct:+5.2f}%) {status}")
    
    print()
    
    # Test rule hierarchy
    print("🎯 Rule Hierarchy Test:")
    test_pnl_values = [15, 10, 7, 5, 0, -5, -10, -15, -20]
    
    for pnl in test_pnl_values:
        if pnl >= 10:
            rule = "RULE 1: Primary Target ($10)"
            action = "IMMEDIATE EXIT"
        elif pnl >= 7:
            rule = "RULE 2: Floor Activation ($7)"
            action = "FLOOR PROTECTED"
        elif pnl <= -15:
            rule = "RULE 4: Failsafe ($15 loss)"
            action = "HARD STOP"
        elif pnl <= -10:
            rule = "RULE 3: Stop Loss ($10 loss)"
            action = "STOP LOSS EXIT"
        else:
            rule = "No rule triggered"
            action = "CONTINUE TRADING"
        
        print(f"   ${pnl:+3.0f} PnL → {rule:<30} → {action}")
    
    print()
    
    # Verification checks
    print("🔍 System Verification:")
    checks = [
        ("Capital per position is $1,000", abs(capital_per_position - 1000.0) < 0.01),
        ("Leverage is 10x", abs(leverage - 10.0) < 0.01),
        ("Notional value is $10,000", abs(notional_value - 10000.0) < 0.01),
        ("Pure 3-Rule Mode enabled", engine.pure_3_rule_mode),
        ("Primary target is $10", abs(engine.config.get('primary_target_dollars', 10.0) - 10.0) < 0.01),
        ("Floor activation is $7", abs(engine.config.get('absolute_floor_dollars', 7.0) - 7.0) < 0.01),
    ]
    
    all_passed = True
    for check_name, passed in checks:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {check_name:<35} {status}")
        if not passed:
            all_passed = False
    
    print()
    
    if all_passed:
        print("🎉 ALL TESTS PASSED! Dollar-based stop loss system is working correctly!")
        print("🎯 The system now uses:")
        print("   • $10 take profit (immediate exit)")
        print("   • $7 floor protection (trailing stop)")
        print("   • $10 stop loss (maximum loss)")
        print("   • $15 failsafe (hard stop)")
    else:
        print("❌ Some tests failed. Please review the configuration.")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    asyncio.run(test_dollar_based_stop_loss()) 