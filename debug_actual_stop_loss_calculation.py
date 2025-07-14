#!/usr/bin/env python3
"""
Debug Actual Stop Loss Calculation
Investigate why the live system is still producing $26-38 losses instead of $10
"""

import requests
import json

def debug_stop_loss_calculation():
    """Debug the actual stop loss calculation in the live system"""
    
    print("🔍 DEBUGGING ACTUAL STOP LOSS CALCULATION")
    print("=" * 60)
    
    try:
        # Get recent trades to analyze
        response = requests.get('http://localhost:8000/api/v1/paper-trading/trades', timeout=10)
        trades_data = response.json()
        trades = trades_data.get('trades', [])
        
        # Get the most recent stop loss trades
        recent_stop_loss_trades = []
        for trade in trades[-10:]:
            if 'stop_loss' in trade.get('exit_reason', ''):
                recent_stop_loss_trades.append(trade)
        
        if not recent_stop_loss_trades:
            print("❌ No recent stop loss trades found")
            return
        
        print(f"Found {len(recent_stop_loss_trades)} recent stop loss trades")
        print()
        
        for i, trade in enumerate(recent_stop_loss_trades):
            symbol = trade.get('symbol', 'UNKNOWN')
            side = trade.get('side', 'UNKNOWN')
            entry_price = trade.get('entry_price', 0)
            exit_price = trade.get('exit_price', 0)
            quantity = trade.get('quantity', 0)
            pnl = trade.get('pnl', 0)
            fees = trade.get('fees', 0)
            
            print(f"🔍 TRADE {i+1}: {symbol} {side}")
            print(f"   Entry Price: ${entry_price:.4f}")
            print(f"   Exit Price:  ${exit_price:.4f}")
            print(f"   Quantity:    {quantity:.6f}")
            print(f"   Gross P&L:   ${pnl + fees:.2f}")
            print(f"   Fees:        ${fees:.2f}")
            print(f"   Net P&L:     ${pnl:.2f}")
            
            # Calculate what the position size should be for $10 loss
            if side == 'LONG':
                price_move = entry_price - exit_price
                price_move_pct = price_move / entry_price * 100
            else:  # SHORT
                price_move = exit_price - entry_price
                price_move_pct = price_move / entry_price * 100
            
            print(f"   Price Move:  ${price_move:.4f} ({price_move_pct:.3f}%)")
            
            # Calculate what the notional value actually was
            actual_notional = quantity * entry_price
            print(f"   Actual Notional: ${actual_notional:.2f}")
            
            # Calculate what the notional should be for $18 gross loss
            if price_move != 0:
                expected_notional_for_18_loss = 18.0 / abs(price_move_pct / 100)
                expected_quantity_for_18_loss = expected_notional_for_18_loss / entry_price
                print(f"   Expected Notional for $18 loss: ${expected_notional_for_18_loss:.2f}")
                print(f"   Expected Quantity for $18 loss: {expected_quantity_for_18_loss:.6f}")
                
                # Calculate the ratio
                ratio = actual_notional / expected_notional_for_18_loss
                print(f"   Actual/Expected Ratio: {ratio:.2f}x")
                
                if ratio > 1.5:
                    print(f"   ❌ PROBLEM: Position size is {ratio:.1f}x too large!")
                elif ratio < 0.5:
                    print(f"   ❌ PROBLEM: Position size is {1/ratio:.1f}x too small!")
                else:
                    print(f"   ✅ Position size looks reasonable")
            
            print()
        
        # Check current account status
        print("🔍 CHECKING CURRENT ACCOUNT STATUS...")
        status_response = requests.get('http://localhost:8000/api/v1/paper-trading/status', timeout=10)
        status = status_response.json()
        
        account = status.get('account', {})
        balance = account.get('balance', 0)
        
        print(f"Current Balance: ${balance:.2f}")
        
        # Calculate expected position parameters
        risk_per_trade_pct = 0.10  # 10%
        leverage = 10.0
        capital_per_position = balance * risk_per_trade_pct
        notional_per_position = capital_per_position * leverage
        
        print(f"Expected Capital per Position: ${capital_per_position:.2f}")
        print(f"Expected Notional per Position: ${notional_per_position:.2f}")
        print()
        
        # Compare with actual trades
        if recent_stop_loss_trades:
            avg_actual_notional = sum(trade.get('quantity', 0) * trade.get('entry_price', 0) 
                                    for trade in recent_stop_loss_trades) / len(recent_stop_loss_trades)
            print(f"Average Actual Notional: ${avg_actual_notional:.2f}")
            print(f"Expected Notional: ${notional_per_position:.2f}")
            
            ratio = avg_actual_notional / notional_per_position
            print(f"Actual/Expected Notional Ratio: {ratio:.2f}x")
            
            if ratio > 1.2:
                print(f"❌ CRITICAL: Positions are {ratio:.1f}x larger than expected!")
                print(f"   This explains why losses are {ratio:.1f}x larger than $10")
            elif ratio < 0.8:
                print(f"❌ CRITICAL: Positions are {1/ratio:.1f}x smaller than expected!")
            else:
                print(f"✅ Position sizes look correct")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")

def check_position_sizing_logic():
    """Check if there's an issue with position sizing logic"""
    
    print("\n🔍 CHECKING POSITION SIZING LOGIC")
    print("=" * 40)
    
    # Simulate the position sizing calculation
    balance = 10000.0  # Current balance
    risk_per_trade_pct = 0.10  # 10%
    leverage = 10.0
    
    capital_per_position = balance * risk_per_trade_pct  # $1000
    notional_value = capital_per_position * leverage  # $10,000
    
    print(f"Balance: ${balance:.2f}")
    print(f"Risk per Trade: {risk_per_trade_pct:.1%}")
    print(f"Capital per Position: ${capital_per_position:.2f}")
    print(f"Leverage: {leverage:.1f}x")
    print(f"Notional Value: ${notional_value:.2f}")
    
    # Test with recent trade prices
    test_prices = [2.85, 2972.44, 162.62, 94.92, 18.58]  # Recent entry prices
    
    print("\nExpected Position Sizes:")
    for price in test_prices:
        quantity = notional_value / price
        print(f"  @ ${price:.2f}: {quantity:.6f} units (${notional_value:.2f} notional)")

def main():
    """Main debug function"""
    
    print("🚀 DEBUGGING STOP LOSS CALCULATION ISSUE")
    print("Investigating why losses are $26-38 instead of $10")
    print()
    
    debug_stop_loss_calculation()
    check_position_sizing_logic()
    
    print("\n" + "=" * 60)
    print("📋 DEBUGGING SUMMARY:")
    print("If positions are larger than expected, the issue is in position sizing.")
    print("If positions are correct size, the issue is in stop loss calculation.")
    print("If stop loss prices are wrong, the issue is in price calculation.")

if __name__ == "__main__":
    main()
