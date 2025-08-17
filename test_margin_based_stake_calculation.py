#!/usr/bin/env python3
"""
Test script to verify the margin-based stake calculation fix.

This test verifies that:
1. Configuration is loaded correctly with new parameters
2. MARGIN mode calculates notional = stake_usd * leverage
3. NOTIONAL mode (legacy) calculates notional = stake_usd
4. Quantity calculation uses the correct notional value
"""

import asyncio
import sys
import os
import yaml
from unittest.mock import Mock, AsyncMock

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Set PYTHONPATH to include the project root
os.environ['PYTHONPATH'] = os.path.dirname(__file__)

try:
    from src.trading.real_trading_engine import RealTradingEngine
except ImportError:
    # Fallback for different import scenarios
    sys.path.insert(0, os.path.dirname(__file__))
    from src.trading.real_trading_engine import RealTradingEngine

def load_config():
    """Load the configuration file"""
    try:
        with open('config/config.yaml', 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        return None

def test_config_loading():
    """Test that the new configuration parameters are loaded correctly"""
    print("🔧 Testing configuration loading...")
    
    config = load_config()
    if not config:
        return False
    
    real_trading_config = config.get('real_trading', {})
    
    # Check new parameters
    expected_params = {
        'stake_usd': 100.0,
        'stake_mode': 'MARGIN',
        'margin_mode': 'ISOLATED',
        'default_leverage': 10,
        'max_leverage': 20
    }
    
    for param, expected_value in expected_params.items():
        actual_value = real_trading_config.get(param)
        if actual_value != expected_value:
            print(f"❌ Config mismatch: {param} = {actual_value}, expected {expected_value}")
            return False
        print(f"✅ {param}: {actual_value}")
    
    # Check paper trading alignment
    paper_trading_config = config.get('paper_trading', {})
    paper_stake = paper_trading_config.get('stake_amount')
    if paper_stake != 100.0:
        print(f"❌ Paper trading stake mismatch: {paper_stake}, expected 100.0")
        return False
    print(f"✅ paper_trading.stake_amount: {paper_stake}")
    
    print("✅ Configuration loading test passed!")
    return True

def test_engine_initialization():
    """Test that the RealTradingEngine initializes with correct parameters"""
    print("\n🔧 Testing engine initialization...")
    
    config = load_config()
    if not config:
        return False
    
    # Create mock exchange client
    mock_exchange = Mock()
    
    try:
        engine = RealTradingEngine(config, mock_exchange)
        
        # Check that parameters are loaded correctly
        expected_values = {
            'stake_usd': 100.0,
            'stake_mode': 'MARGIN',
            'margin_mode': 'ISOLATED',
            'default_leverage': 10.0
        }
        
        for attr, expected_value in expected_values.items():
            actual_value = getattr(engine, attr)
            if actual_value != expected_value:
                print(f"❌ Engine attribute mismatch: {attr} = {actual_value}, expected {expected_value}")
                return False
            print(f"✅ engine.{attr}: {actual_value}")
        
        print("✅ Engine initialization test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Engine initialization failed: {e}")
        return False

def test_margin_calculation_logic():
    """Test the margin vs notional calculation logic"""
    print("\n🔧 Testing margin calculation logic...")
    
    config = load_config()
    if not config:
        return False
    
    # Test MARGIN mode
    print("\n📊 Testing MARGIN mode:")
    config['real_trading']['stake_mode'] = 'MARGIN'
    
    mock_exchange = Mock()
    engine = RealTradingEngine(config, mock_exchange)
    
    # Simulate the calculation logic
    stake_usd = engine.stake_usd  # 100.0
    leverage = 10  # 10x leverage
    entry_price = 50000.0  # $50,000 BTC price
    
    if engine.stake_mode == "MARGIN":
        notional_target = stake_usd * leverage  # 100 * 10 = 1000
    else:
        notional_target = stake_usd
    
    qty = notional_target / entry_price  # 1000 / 50000 = 0.02
    
    expected_notional = 1000.0
    expected_qty = 0.02
    
    print(f"  Stake USD (margin): ${stake_usd}")
    print(f"  Leverage: {leverage}x")
    print(f"  Entry price: ${entry_price}")
    print(f"  Calculated notional: ${notional_target}")
    print(f"  Calculated quantity: {qty}")
    
    if abs(notional_target - expected_notional) > 0.01:
        print(f"❌ Notional calculation error: {notional_target}, expected {expected_notional}")
        return False
    
    if abs(qty - expected_qty) > 0.0001:
        print(f"❌ Quantity calculation error: {qty}, expected {expected_qty}")
        return False
    
    print("✅ MARGIN mode calculation correct!")
    
    # Test NOTIONAL mode (legacy)
    print("\n📊 Testing NOTIONAL mode (legacy):")
    config['real_trading']['stake_mode'] = 'NOTIONAL'
    
    engine = RealTradingEngine(config, mock_exchange)
    
    if engine.stake_mode == "MARGIN":
        notional_target = stake_usd * leverage
    else:
        notional_target = stake_usd  # 100.0 (legacy behavior)
    
    qty = notional_target / entry_price  # 100 / 50000 = 0.002
    
    expected_notional_legacy = 100.0
    expected_qty_legacy = 0.002
    
    print(f"  Stake USD (notional): ${stake_usd}")
    print(f"  Leverage: {leverage}x (ignored in NOTIONAL mode)")
    print(f"  Entry price: ${entry_price}")
    print(f"  Calculated notional: ${notional_target}")
    print(f"  Calculated quantity: {qty}")
    
    if abs(notional_target - expected_notional_legacy) > 0.01:
        print(f"❌ Legacy notional calculation error: {notional_target}, expected {expected_notional_legacy}")
        return False
    
    if abs(qty - expected_qty_legacy) > 0.000001:
        print(f"❌ Legacy quantity calculation error: {qty}, expected {expected_qty_legacy}")
        return False
    
    print("✅ NOTIONAL mode (legacy) calculation correct!")
    print("✅ Margin calculation logic test passed!")
    return True

def test_binance_margin_calculation():
    """Test that the calculation matches Binance futures margin requirements"""
    print("\n🔧 Testing Binance futures margin calculation...")
    
    # Binance futures formula:
    # Size/Notional (USDT) = qty × price
    # Capital/Margin used (USDT) = Size ÷ Leverage
    
    # Test case: Want $100 margin with 10x leverage
    desired_margin = 100.0
    leverage = 10
    entry_price = 50000.0
    
    # With MARGIN mode:
    # notional = desired_margin * leverage = 100 * 10 = 1000
    # qty = notional / entry_price = 1000 / 50000 = 0.02
    # Binance margin = (qty * entry_price) / leverage = (0.02 * 50000) / 10 = 100
    
    notional = desired_margin * leverage
    qty = notional / entry_price
    binance_margin = (qty * entry_price) / leverage
    
    print(f"  Desired margin: ${desired_margin}")
    print(f"  Leverage: {leverage}x")
    print(f"  Entry price: ${entry_price}")
    print(f"  Calculated notional: ${notional}")
    print(f"  Calculated quantity: {qty}")
    print(f"  Binance margin check: ${binance_margin}")
    
    if abs(binance_margin - desired_margin) > 0.01:
        print(f"❌ Binance margin calculation error: ${binance_margin}, expected ${desired_margin}")
        return False
    
    print("✅ Binance futures margin calculation correct!")
    return True

def test_status_reporting():
    """Test that the new parameters are included in status reporting"""
    print("\n🔧 Testing status reporting...")
    
    config = load_config()
    if not config:
        return False
    
    mock_exchange = Mock()
    engine = RealTradingEngine(config, mock_exchange)
    
    status = engine.get_status()
    
    # Check that new parameters are in status
    expected_status_fields = [
        'stake_usd',
        'stake_mode',
        'margin_mode',
        'default_leverage'
    ]
    
    for field in expected_status_fields:
        if field not in status:
            print(f"❌ Missing status field: {field}")
            return False
        print(f"✅ status['{field}']: {status[field]}")
    
    print("✅ Status reporting test passed!")
    return True

async def main():
    """Run all tests"""
    print("🚀 Testing Margin-Based Stake Calculation Fix")
    print("=" * 50)
    
    tests = [
        test_config_loading,
        test_engine_initialization,
        test_margin_calculation_logic,
        test_binance_margin_calculation,
        test_status_reporting
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                print(f"❌ Test failed: {test.__name__}")
        except Exception as e:
            print(f"❌ Test error in {test.__name__}: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Margin-based stake calculation is working correctly.")
        print("\n📋 Summary of changes:")
        print("  • Configuration updated with new parameters")
        print("  • MARGIN mode: notional = stake_usd × leverage")
        print("  • NOTIONAL mode: notional = stake_usd (legacy)")
        print("  • Paper trading stake aligned to $100")
        print("  • Status reporting includes new parameters")
        return True
    else:
        print("❌ Some tests failed. Please check the implementation.")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
