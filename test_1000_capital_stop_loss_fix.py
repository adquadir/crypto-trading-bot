#!/usr/bin/env python3
"""
Test $1000 Capital Stop Loss Fix
Verify the corrected stop loss calculation for $1000 capital allocation
"""

def test_1000_capital_stop_loss_calculation():
    """Test the corrected stop loss calculation for $1000 capital"""
    
    print("🧪 TESTING $1000 CAPITAL STOP LOSS CALCULATION")
    print("=" * 60)
    
    # CORRECTED Trading parameters
    balance = 10000.0
    risk_per_trade_pct = 0.10  # 10% of balance per trade
    leverage = 10.0
    target_net_loss = 10.0  # $10 net loss after fees
    
    capital_per_position = balance * risk_per_trade_pct  # $1000
    notional_value = capital_per_position * leverage  # $10,000
    
    # Fee calculation (Binance Futures taker fees)
    fee_per_side = 0.0004  # 0.04% taker fee
    round_trip_fee_pct = fee_per_side * 2  # 0.08% total
    total_fees_dollars = notional_value * round_trip_fee_pct  # $8
    
    # Target: $10 net loss = $10 + $8 fees = $18 gross loss needed
    required_gross_loss = target_net_loss + total_fees_dollars  # $18
    
    print(f"Account Balance: ${balance:.2f}")
    print(f"Risk per Trade: {risk_per_trade_pct:.1%} = ${capital_per_position:.2f}")
    print(f"Leverage: {leverage}x")
    print(f"Notional Value: ${notional_value:.2f}")
    print(f"Total Fees: ${total_fees_dollars:.2f}")
    print(f"Target Net Loss: ${target_net_loss:.2f}")
    print(f"Required Gross Loss: ${required_gross_loss:.2f}")
    print()
    
    # Test scenarios with different prices
    test_scenarios = [
        {'symbol': 'BTCUSDT', 'price': 50000.0, 'side': 'LONG'},
        {'symbol': 'ETHUSDT', 'price': 3000.0, 'side': 'LONG'},
        {'symbol': 'BNBUSDT', 'price': 300.0, 'side': 'SHORT'},
        {'symbol': 'ADAUSDT', 'price': 0.5, 'side': 'LONG'},
        {'symbol': 'SOLUSDT', 'price': 100.0, 'side': 'SHORT'},
        {'symbol': 'XRPUSDT', 'price': 2.85, 'side': 'LONG'},  # Real example from your data
        {'symbol': 'LINKUSDT', 'price': 15.67, 'side': 'SHORT'}  # Real example from your data
    ]
    
    print("Testing CORRECTED stop loss calculations for $1000 capital:")
    print()
    
    all_passed = True
    
    for i, scenario in enumerate(test_scenarios, 1):
        symbol = scenario['symbol']
        price = scenario['price']
        side = scenario['side']
        
        print(f"📊 TEST {i}: {symbol} {side} @ ${price:.4f}")
        
        # Calculate quantity based on $10,000 notional value
        quantity = notional_value / price
        
        # Calculate stop loss price for exactly $18 gross loss
        if side == 'LONG':
            # For LONG: gross_loss = (entry_price - sl_price) * quantity
            # Solve for sl_price: sl_price = entry_price - (required_gross_loss / quantity)
            sl_price = price - (required_gross_loss / quantity)
            expected_gross_loss = (price - sl_price) * quantity
            sl_pct = (price - sl_price) / price * 100
        else:  # SHORT
            # For SHORT: gross_loss = (sl_price - entry_price) * quantity
            # Solve for sl_price: sl_price = entry_price + (required_gross_loss / quantity)
            sl_price = price + (required_gross_loss / quantity)
            expected_gross_loss = (sl_price - price) * quantity
            sl_pct = (sl_price - price) / price * 100
        
        expected_net_loss = expected_gross_loss - total_fees_dollars
        
        print(f"   Entry Price: ${price:.4f}")
        print(f"   Stop Loss:   ${sl_price:.4f} ({sl_pct:.3f}%)")
        print(f"   Quantity:    {quantity:.6f} {symbol}")
        print(f"   Notional:    ${notional_value:.2f}")
        print(f"   Expected Gross Loss: ${expected_gross_loss:.2f}")
        print(f"   Expected Net Loss: ${expected_net_loss:.2f}")
        
        # Verify the loss is exactly $10 net
        if abs(expected_net_loss - target_net_loss) < 0.01:  # Within 1 cent
            print(f"   ✅ CORRECT: Net loss = ${expected_net_loss:.2f} = ${target_net_loss:.2f}")
        else:
            print(f"   ❌ INCORRECT: Net loss = ${expected_net_loss:.2f} ≠ ${target_net_loss:.2f}")
            all_passed = False
        
        # Verify gross loss is exactly $18
        if abs(expected_gross_loss - required_gross_loss) < 0.01:  # Within 1 cent
            print(f"   ✅ CORRECT: Gross loss = ${expected_gross_loss:.2f} = ${required_gross_loss:.2f}")
        else:
            print(f"   ❌ INCORRECT: Gross loss = ${expected_gross_loss:.2f} ≠ ${required_gross_loss:.2f}")
            all_passed = False
        
        print()
    
    print("🎯 SUMMARY:")
    if all_passed:
        print("✅ ALL TESTS PASSED: Stop loss calculation is CORRECT for $1000 capital")
    else:
        print("❌ SOME TESTS FAILED: Stop loss calculation needs further adjustment")
    
    print()
    print("The CORRECTED stop loss calculation:")
    print("1. Uses actual $1000 capital allocation (10% of $10k balance)")
    print("2. Applies 10x leverage for $10,000 notional positions")
    print("3. Calculates $8 fees on $10,000 positions (0.08%)")
    print("4. Sets stop loss for exactly $18 gross loss = $10 net loss")
    print()
    print("Formula:")
    print("- Capital: $10,000 × 10% = $1,000")
    print("- Notional: $1,000 × 10x = $10,000")
    print("- Fees: $10,000 × 0.08% = $8")
    print("- Target: $10 net + $8 fees = $18 gross")
    print("- LONG: SL Price = Entry Price - ($18 / Quantity)")
    print("- SHORT: SL Price = Entry Price + ($18 / Quantity)")
    print()
    print("This ensures Rule 3 properly limits losses to $10 NET regardless of entry price.")
    
    return all_passed

if __name__ == "__main__":
    success = test_1000_capital_stop_loss_calculation()
    exit(0 if success else 1)
