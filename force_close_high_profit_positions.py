#!/usr/bin/env python3
"""
Force close all positions with $10+ profit immediately
"""

import requests
import json

def force_close_high_profit_positions():
    try:
        print("🔨 FORCE CLOSING ALL POSITIONS WITH $10+ PROFIT")
        print("=" * 60)
        
        # Get current positions
        response = requests.get("http://localhost:8000/api/v1/paper-trading/positions", timeout=10)
        if response.status_code != 200:
            print(f"❌ Could not get positions: {response.status_code}")
            return False
        
        positions_data = response.json()
        positions = positions_data.get('data', [])
        
        high_profit_positions = [
            pos for pos in positions 
            if pos.get('unrealized_pnl', 0) >= 10.0
        ]
        
        print(f"🎯 Found {len(high_profit_positions)} positions to force close")
        
        closed_count = 0
        for pos in high_profit_positions:
            position_id = pos.get('id')
            symbol = pos.get('symbol')
            pnl = pos.get('unrealized_pnl', 0)
            
            print(f"🔨 Force closing {symbol} (${pnl:.2f} profit)")
            
            try:
                close_response = requests.post(
                    f"http://localhost:8000/api/v1/paper-trading/positions/{position_id}/close",
                    json={"exit_reason": "manual_10_dollar_fix"},
                    timeout=10
                )
                
                if close_response.status_code == 200:
                    print(f"✅ Closed {symbol}")
                    closed_count += 1
                else:
                    print(f"❌ Failed to close {symbol}: {close_response.status_code}")
                    print(f"   Response: {close_response.text}")
                    
            except Exception as e:
                print(f"❌ Error closing {symbol}: {e}")
        
        print(f"\n🎉 Successfully closed {closed_count} positions")
        
        # Verify closure
        print("\n🔍 Verifying positions were closed...")
        response2 = requests.get("http://localhost:8000/api/v1/paper-trading/positions", timeout=10)
        if response2.status_code == 200:
            positions_data2 = response2.json()
            positions2 = positions_data2.get('data', [])
            
            remaining_high_profit = [
                pos for pos in positions2 
                if pos.get('unrealized_pnl', 0) >= 10.0
            ]
            
            if len(remaining_high_profit) == 0:
                print("✅ SUCCESS: All high-profit positions closed!")
                return True
            else:
                print(f"❌ STILL HAVE {len(remaining_high_profit)} high-profit positions:")
                for pos in remaining_high_profit:
                    print(f"   {pos.get('symbol')}: ${pos.get('unrealized_pnl', 0):.2f}")
                return False
        
        return closed_count > 0
        
    except Exception as e:
        print(f"❌ Force close failed: {e}")
        return False

if __name__ == "__main__":
    success = force_close_high_profit_positions()
    if success:
        print("\n🎉 FORCE CLOSE COMPLETED SUCCESSFULLY!")
    else:
        print("\n❌ FORCE CLOSE FAILED!")
