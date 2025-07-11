#!/usr/bin/env python3
"""
Quick status check to see current positions with $10+ profit
"""

import requests
import json

def check_status():
    try:
        print("🔍 Checking current positions...")
        
        # Get current positions
        response = requests.get("http://localhost:8000/api/v1/paper-trading/positions", timeout=5)
        if response.status_code == 200:
            positions_data = response.json()
            positions = positions_data.get('data', [])
            
            print(f"📊 Total positions: {len(positions)}")
            
            high_profit_positions = []
            for pos in positions:
                pnl = pos.get('unrealized_pnl', 0)
                if pnl >= 10.0:
                    high_profit_positions.append(pos)
                    symbol = pos.get('symbol', 'UNKNOWN')
                    print(f"💰 {symbol}: ${pnl:.2f} profit")
            
            print(f"🎯 Positions with $10+ profit: {len(high_profit_positions)}")
            
            if len(high_profit_positions) == 0:
                print("✅ SUCCESS: No positions with $10+ profit!")
            else:
                print("❌ ISSUE: Still have high-profit positions")
                
        else:
            print(f"❌ API error: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    check_status()
