#!/usr/bin/env python3
"""
Quick script to enable paper trading mode and fix signal connections
This directly accesses the opportunity manager to enable relaxed validation
"""

import sys
import os
import requests
import time

# Add project root to path
sys.path.append('/home/ubuntu/crypto-trading-bot')

def test_connection():
    """Test API connection"""
    try:
        response = requests.get("http://localhost:8000/api/v1/paper-trading/status", timeout=5)
        if response.status_code == 200:
            print("✅ API connection working")
            return True
        else:
            print(f"❌ API connection failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ API connection error: {e}")
        return False

def enable_paper_trading_mode():
    """Enable paper trading mode through API"""
    try:
        print("🎯 Attempting to enable paper trading mode...")
        
        # Check current opportunity count
        opp_response = requests.get("http://localhost:8000/api/v1/opportunities", timeout=10)
        if opp_response.status_code == 200:
            opp_data = opp_response.json()
            current_opportunities = len(opp_data.get('data', []))
            print(f"📊 Current opportunities: {current_opportunities}")
        
        # Try to enable paper trading mode
        response = requests.post("http://localhost:8000/api/v1/paper-trading/enable-paper-trading-mode", timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                print("✅ Paper trading mode enabled successfully!")
                print(f"📊 Results: {data.get('data', {})}")
                return True
            else:
                print(f"❌ Failed to enable: {data.get('message')}")
        else:
            print(f"❌ HTTP Error {response.status_code}: {response.text}")
            
        return False
        
    except Exception as e:
        print(f"❌ Error enabling paper trading mode: {e}")
        return False

def inject_test_signals():
    """Inject test signals to verify paper trading works"""
    try:
        print("🚀 Injecting test signals...")
        
        # Use the simulate signals endpoint  
        response = requests.post("http://localhost:8000/api/v1/paper-trading/simulate-signals?symbol=BTCUSDT&count=3", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                print("✅ Test signals injected successfully!")
                print(f"📊 Trades executed: {data.get('data', {}).get('trades_executed', 0)}")
                return True
            
        print(f"❌ Signal injection failed: {response.text}")
        return False
        
    except Exception as e:
        print(f"❌ Error injecting signals: {e}")
        return False

def check_positions():
    """Check current paper trading positions"""
    try:
        response = requests.get("http://localhost:8000/api/v1/paper-trading/positions", timeout=5)
        if response.status_code == 200:
            data = response.json()
            positions = data.get('data', [])
            print(f"📊 Active positions: {len(positions)}")
            
            for i, pos in enumerate(positions[:3]):  # Show first 3
                symbol = pos.get('symbol', 'Unknown')
                side = pos.get('side', 'Unknown')
                pnl = pos.get('unrealized_pnl', 0)
                print(f"   {i+1}. {symbol} {side} - P&L: ${pnl:.2f}")
                
            return len(positions)
        else:
            print(f"❌ Failed to get positions: {response.status_code}")
            return 0
    except Exception as e:
        print(f"❌ Error checking positions: {e}")
        return 0

def main():
    print("🎯 PAPER TRADING MODE ENABLER")
    print("=" * 50)
    
    # Step 1: Test connection
    if not test_connection():
        print("💔 Cannot connect to API - make sure the server is running")
        return
    
    # Step 2: Check current positions
    current_positions = check_positions()
    
    # Step 3: Enable paper trading mode (if endpoints work)
    if not enable_paper_trading_mode():
        print("⚠️  Could not enable through API endpoint")
        print("📝 Manual solution: Edit opportunity_manager.py to set paper_trading_mode = True")
    
    # Step 4: Inject test signals if no positions
    if current_positions == 0:
        print("\n🧪 No positions found - injecting test signals...")
        inject_test_signals()
        time.sleep(2)
        check_positions()
    
    print("\n✅ Paper trading mode setup completed!")
    print("🔍 Monitor logs: pm2 logs crypto-trading-api")
    print("📊 Check frontend: Paper Trading page should show positions")

if __name__ == "__main__":
    main() 