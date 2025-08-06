#!/usr/bin/env python3
"""
Diagnose PM2 Paper Trading Issue
Comprehensive diagnosis of paper trading frontend "Failed to fetch data" error
"""

import asyncio
import logging
import requests
import json
import sys
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def diagnose_paper_trading_issue():
    """Comprehensive diagnosis of paper trading frontend issue"""
    
    print("🔍 PAPER TRADING FRONTEND DIAGNOSIS")
    print("=" * 60)
    
    # Test 1: Check if API server is running
    print("\n1. 🌐 API SERVER STATUS CHECK")
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            print("✅ API server is running and responding")
            print(f"   Response: {response.json()}")
        else:
            print(f"❌ API server returned status {response.status_code}")
            print(f"   Response: {response.text}")
    except requests.exceptions.ConnectionError:
        print("❌ CRITICAL: API server is not running on port 8000")
        print("   Solution: Start the API server with 'python src/api/main.py'")
        return
    except Exception as e:
        print(f"❌ Error connecting to API server: {e}")
        return
    
    # Test 2: Check paper trading status endpoint
    print("\n2. 📊 PAPER TRADING STATUS ENDPOINT")
    try:
        response = requests.get("http://localhost:8000/api/paper-trading/status", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print("✅ Paper trading status endpoint working")
            print(f"   Running: {data.get('is_running', 'Unknown')}")
            print(f"   Active positions: {data.get('account', {}).get('active_positions', 'Unknown')}")
            print(f"   Balance: ${data.get('account', {}).get('balance', 'Unknown')}")
            print(f"   Total trades: {data.get('account', {}).get('total_trades', 'Unknown')}")
        else:
            print(f"❌ Paper trading status endpoint failed: {response.status_code}")
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"❌ Error fetching paper trading status: {e}")
    
    # Test 3: Check if paper trading engine is initialized
    print("\n3. 🎯 PAPER TRADING ENGINE INITIALIZATION")
    try:
        response = requests.get("http://localhost:8000/api/paper-trading/account", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print("✅ Paper trading account endpoint working")
            account = data.get('account', {})
            print(f"   Balance: ${account.get('balance', 0):.2f}")
            print(f"   Equity: ${account.get('equity', 0):.2f}")
            print(f"   Realized P&L: ${account.get('realized_pnl', 0):.2f}")
            print(f"   Win Rate: {account.get('win_rate', 0):.1%}")
        else:
            print(f"❌ Paper trading account endpoint failed: {response.status_code}")
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"❌ Error fetching paper trading account: {e}")
    
    # Test 4: Check positions endpoint
    print("\n4. 📈 POSITIONS ENDPOINT")
    try:
        response = requests.get("http://localhost:8000/api/paper-trading/positions", timeout=10)
        if response.status_code == 200:
            data = response.json()
            positions = data.get('positions', {})
            print(f"✅ Positions endpoint working - {len(positions)} active positions")
            if positions:
                for pos_id, pos in list(positions.items())[:3]:  # Show first 3
                    print(f"   {pos.get('symbol')} {pos.get('side')} @ ${pos.get('entry_price', 0):.4f}")
        else:
            print(f"❌ Positions endpoint failed: {response.status_code}")
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"❌ Error fetching positions: {e}")
    
    # Test 5: Check trades endpoint
    print("\n5. 📋 TRADES ENDPOINT")
    try:
        response = requests.get("http://localhost:8000/api/paper-trading/trades", timeout=10)
        if response.status_code == 200:
            data = response.json()
            trades = data.get('trades', [])
            print(f"✅ Trades endpoint working - {len(trades)} recent trades")
            if trades:
                for trade in trades[:3]:  # Show first 3
                    pnl = trade.get('pnl', 0)
                    print(f"   {trade.get('symbol')} {trade.get('side')} P&L: ${pnl:.2f}")
        else:
            print(f"❌ Trades endpoint failed: {response.status_code}")
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"❌ Error fetching trades: {e}")
    
    # Test 6: Check start/stop endpoints
    print("\n6. 🚀 START/STOP ENDPOINTS")
    try:
        # Test start endpoint
        response = requests.post("http://localhost:8000/api/paper-trading/start", timeout=10)
        if response.status_code == 200:
            print("✅ Start endpoint working")
            print(f"   Response: {response.json()}")
        else:
            print(f"⚠️ Start endpoint returned: {response.status_code}")
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"❌ Error testing start endpoint: {e}")
    
    # Test 7: Check CORS headers
    print("\n7. 🌐 CORS HEADERS CHECK")
    try:
        response = requests.options("http://localhost:8000/api/paper-trading/status", timeout=5)
        headers = response.headers
        print(f"✅ CORS preflight response: {response.status_code}")
        print(f"   Access-Control-Allow-Origin: {headers.get('Access-Control-Allow-Origin', 'Not set')}")
        print(f"   Access-Control-Allow-Methods: {headers.get('Access-Control-Allow-Methods', 'Not set')}")
        print(f"   Access-Control-Allow-Headers: {headers.get('Access-Control-Allow-Headers', 'Not set')}")
    except Exception as e:
        print(f"❌ Error checking CORS headers: {e}")
    
    # Test 8: Check frontend config
    print("\n8. ⚙️ FRONTEND CONFIGURATION")
    try:
        with open('frontend/src/config.js', 'r') as f:
            config_content = f.read()
            if 'localhost:8000' in config_content:
                print("✅ Frontend config points to localhost:8000")
            else:
                print("⚠️ Frontend config may not be pointing to correct API URL")
                print("   Check frontend/src/config.js")
    except Exception as e:
        print(f"❌ Error reading frontend config: {e}")
    
    # Test 9: Check if exchange client is working
    print("\n9. 💱 EXCHANGE CLIENT STATUS")
    try:
        response = requests.get("http://localhost:8000/api/market-data/status", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print("✅ Exchange client status available")
            print(f"   Status: {data.get('status', 'Unknown')}")
            print(f"   Connected: {data.get('connected', 'Unknown')}")
        else:
            print(f"⚠️ Exchange client status: {response.status_code}")
    except Exception as e:
        print(f"⚠️ Exchange client status check failed: {e}")
    
    # Test 10: Check database connection
    print("\n10. 🗄️ DATABASE CONNECTION")
    try:
        response = requests.get("http://localhost:8000/api/database/status", timeout=10)
        if response.status_code == 200:
            print("✅ Database connection working")
        else:
            print(f"⚠️ Database status: {response.status_code}")
    except Exception as e:
        print(f"⚠️ Database status check failed: {e}")
    
    print("\n" + "=" * 60)
    print("🎯 DIAGNOSIS SUMMARY")
    print("=" * 60)
    
    # Provide recommendations
    print("\n📋 RECOMMENDATIONS:")
    print("1. If API server is not running: python src/api/main.py")
    print("2. If endpoints are failing: Check server logs for errors")
    print("3. If CORS issues: Ensure frontend is running on correct port")
    print("4. If data type errors: Check recent fixes in enhanced_paper_trading_engine.py")
    print("5. If exchange client issues: Verify Binance API connection")
    
    print(f"\n✅ Diagnosis completed at {datetime.now()}")

if __name__ == "__main__":
    asyncio.run(diagnose_paper_trading_issue())
