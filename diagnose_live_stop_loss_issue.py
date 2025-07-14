#!/usr/bin/env python3
"""
Diagnose Live Stop Loss Issue
Check if the running system is using the correct stop loss calculation
"""

import requests
import json
import sys

def test_live_stop_loss_calculation():
    """Test the live system's stop loss calculation"""
    
    print("🔍 LIVE STOP LOSS DIAGNOSTIC")
    print("=" * 60)
    
    try:
        # Check if API is running
        response = requests.get('http://localhost:8000/api/v1/paper-trading/status', timeout=10)
        if response.status_code != 200:
            print(f"❌ API not responding: {response.status_code}")
            return False
        
        status = response.json()
        print(f"✅ API Status: {status.get('status', 'unknown')}")
        print(f"📊 Paper Trading Running: {status.get('is_running', False)}")
        print(f"💰 Account Balance: ${status.get('account', {}).get('balance', 0):.2f}")
        print(f"🎯 Active Positions: {status.get('account', {}).get('active_positions', 0)}")
        print()
        
        # Check recent trades to see if new ones use correct stop loss
        print("🔍 CHECKING RECENT TRADES...")
        trades_response = requests.get('http://localhost:8000/api/v1/paper-trading/trades', timeout=10)
        trades_data = trades_response.json()
        trades = trades_data.get('trades', [])
        
        # Look for trades after the restart (most recent ones)
        recent_stop_loss_trades = []
        for trade in trades[-10:]:  # Last 10 trades
            if 'stop_loss' in trade.get('exit_reason', ''):
                recent_stop_loss_trades.append(trade)
        
        if recent_stop_loss_trades:
            print(f"Found {len(recent_stop_loss_trades)} recent stop loss trades:")
            print()
            print(f"{'Symbol':>8} {'PnL':>8} {'Exit Reason':>25} {'Fixed?'}")
            print("-" * 50)
            
            fixed_count = 0
            for trade in recent_stop_loss_trades:
                symbol = trade.get('symbol', 'UNKNOWN')
                pnl = trade.get('pnl', 0)
                exit_reason = trade.get('exit_reason', 'unknown')
                
                # Check if loss is within $10 limit (indicating fix is working)
                if pnl >= -12:  # Allow small margin for fees/slippage
                    status = "✅ FIXED"
                    fixed_count += 1
                else:
                    status = "❌ BROKEN"
                
                print(f"{symbol:>8} ${pnl:>6.2f} {exit_reason:>25} {status}")
            
            print("-" * 50)
            print(f"Fixed: {fixed_count}/{len(recent_stop_loss_trades)} trades")
            
            if fixed_count == len(recent_stop_loss_trades):
                print("✅ STOP LOSS FIX IS WORKING!")
                return True
            elif fixed_count > 0:
                print("⚠️ PARTIAL FIX - Some trades fixed, some still broken")
                return False
            else:
                print("❌ STOP LOSS FIX NOT WORKING - All trades still broken")
                return False
        else:
            print("ℹ️ No recent stop loss trades found - need to wait for new trades")
            return None
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def check_position_monitoring():
    """Check if position monitoring is working correctly"""
    
    print("\n🔍 POSITION MONITORING CHECK")
    print("=" * 40)
    
    try:
        # Get current positions
        response = requests.get('http://localhost:8000/api/v1/paper-trading/positions', timeout=10)
        if response.status_code != 200:
            print(f"❌ Cannot get positions: {response.status_code}")
            return
        
        positions_data = response.json()
        positions = positions_data.get('positions', {})
        
        if not positions:
            print("ℹ️ No active positions to monitor")
            return
        
        print(f"📊 Active Positions: {len(positions)}")
        
        for pos_id, position in positions.items():
            symbol = position.get('symbol', 'UNKNOWN')
            side = position.get('side', 'UNKNOWN')
            entry_price = position.get('entry_price', 0)
            current_price = position.get('current_price', 0)
            unrealized_pnl = position.get('unrealized_pnl', 0)
            stop_loss = position.get('stop_loss', 0)
            
            print(f"\n📍 {symbol} {side}")
            print(f"   Entry: ${entry_price:.4f}")
            print(f"   Current: ${current_price:.4f}")
            print(f"   Stop Loss: ${stop_loss:.4f}")
            print(f"   Unrealized P&L: ${unrealized_pnl:.2f}")
            
            # Check if stop loss is set correctly (should be ~0.18% away)
            if side == 'LONG':
                sl_distance_pct = (entry_price - stop_loss) / entry_price * 100
            else:
                sl_distance_pct = (stop_loss - entry_price) / entry_price * 100
            
            print(f"   Stop Loss Distance: {sl_distance_pct:.3f}%")
            
            # Check if it's close to the expected 0.18%
            if 0.15 <= sl_distance_pct <= 0.25:
                print(f"   ✅ Stop Loss looks correct (~0.18%)")
            else:
                print(f"   ❌ Stop Loss distance seems wrong (expected ~0.18%)")
    
    except Exception as e:
        print(f"❌ Position monitoring check failed: {e}")

def main():
    """Main diagnostic function"""
    
    print("🚀 STARTING LIVE STOP LOSS DIAGNOSTIC")
    print("This will check if the restart fixed the stop loss issue")
    print()
    
    # Test 1: Check recent trades
    trade_result = test_live_stop_loss_calculation()
    
    # Test 2: Check current positions
    check_position_monitoring()
    
    print("\n" + "=" * 60)
    print("📋 DIAGNOSTIC SUMMARY:")
    
    if trade_result is True:
        print("✅ STOP LOSS FIX IS WORKING - Recent trades show correct $10 limits")
    elif trade_result is False:
        print("❌ STOP LOSS FIX NOT WORKING - Trades still exceed $10 limit")
        print("🔧 RECOMMENDATION: The system may need additional fixes")
    elif trade_result is None:
        print("⏳ INCONCLUSIVE - No recent stop loss trades to analyze")
        print("🔧 RECOMMENDATION: Wait for new trades or create test positions")
    
    print("\n💡 To monitor in real-time, run:")
    print("   python3 check_stop_loss_amounts.py")
    print("   (Run this again in a few minutes to see new trades)")

if __name__ == "__main__":
    main()
