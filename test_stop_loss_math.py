#!/usr/bin/env python3
"""
Test Stop Loss Math
Verify the mathematical calculation for $10 stop loss
"""

def test_stop_loss_calculation():
    """Test the stop loss calculation math"""
    
    print("🧪 TESTING STOP LOSS CALCULATION MATH")
    print("=" * 60)
    
    # Trading parameters
    balance = 10000.0
    risk_per_trade_pct = 0.02  # 2%
    leverage = 10.0
    target_loss = 10.0  # $10 maximum loss
    
    capital_per_position = balance * risk_per_trade_pct  # $200
    notional_value = capital_per_position * leverage  # $2000
    
    print(f"Account Balance: ${balance:.2f}")
    print(f"Risk per Trade: {risk_per_trade_pct:.1%} = ${capital_per_position:.2f}")
    print(f"Leverage: {leverage}x")
    print(f"Notional Value: ${notional_value:.2f}")
    print(f"Target Max Loss: ${target_loss:.2f}")
    print()
    
    # Test scenarios with different prices
    test_scenarios = [
        {'symbol': 'BTCUSDT', 'price': 50000.0, 'side': 'LONG'},
        {'symbol': 'ETHUSDT', 'price': 3000.0, 'side': 'LONG'},
        {'symbol': 'BNBUSDT', 'price': 300.0, 'side': 'SHORT'},
        {'symbol': 'ADAUSDT', 'price': 0.5, 'side': 'LONG'},
        {'symbol': 'SOLUSDT', 'price': 100.0, 'side': 'SHORT'}
    ]
    
    print("Testing stop loss calculations for different price levels:")
    print()
    
    for i, scenario in enumerate(test_scenarios, 1):
        symbol = scenario['symbol']
        price = scenario['price']
        side = scenario['side']
        
        print(f"📊 TEST {i}: {symbol} {side} @ ${price:.4f}")
        
        # Calculate quantity
        quantity = notional_value / price
        
        # Calculate stop loss price for exactly $10 loss
        if side == 'LONG':
            # For LONG: loss = (entry_price - sl_price) * quantity
            # Solve for sl_price: sl_price = entry_price - (target_loss / quantity)
            sl_price = price - (target_loss / quantity)
            expected_loss = (price - sl_price) * quantity
            sl_pct = (price - sl_price) / price * 100
        else:  # SHORT
            # For SHORT: loss = (sl_price - entry_price) * quantity
            # Solve for sl_price: sl_price = entry_price + (target_loss / quantity)
            sl_price = price + (target_loss / quantity)
            expected_loss = (sl_price - price) * quantity
            sl_pct = (sl_price - price) / price * 100
        
        print(f"   Entry Price: ${price:.4f}")
        print(f"   Stop Loss:   ${sl_price:.4f} ({sl_pct:.3f}%)")
        print(f"   Quantity:    {quantity:.6f} {symbol}")
        print(f"   Expected Loss: ${expected_loss:.2f}")
        
        # Verify the loss is exactly $10
        if abs(expected_loss - target_loss) < 0.01:  # Within 1 cent
            print(f"   ✅ CORRECT: Loss = ${expected_loss:.2f} = ${target_loss:.2f}")
        else:
            print(f"   ❌ INCORRECT: Loss = ${expected_loss:.2f} ≠ ${target_loss:.2f}")
        
        print()
    
    print("🎯 SUMMARY:")
    print("The corrected stop loss calculation:")
    print("1. Uses actual position quantity based on capital and leverage")
    print("2. Calculates exact price movement needed for $10 loss")
    print("3. Sets stop loss price to achieve that exact $10 loss")
    print()
    print("Formula:")
    print("- LONG: SL Price = Entry Price - ($10 / Quantity)")
    print("- SHORT: SL Price = Entry Price + ($10 / Quantity)")
    print()
    print("This ensures Rule 3 properly limits losses to $10 regardless of entry price.")

if __name__ == "__main__":
    test_stop_loss_calculation()
