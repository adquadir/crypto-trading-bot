#!/usr/bin/env python3
"""
Test script to verify paper trading start button functionality
Run this to check if the paper trading engine can be started properly
"""

import asyncio
import requests
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_BASE_URL = "http://localhost:8000"

async def test_paper_trading_start():
    """Test the paper trading start functionality"""
    
    print("🧪 Testing Paper Trading Start Button Functionality")
    print("=" * 60)
    
    # Test 1: Check status endpoint
    print("\n1️⃣ Testing status endpoint...")
    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/paper-trading/status")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Status endpoint working")
            print(f"   Enabled: {data.get('data', {}).get('enabled', False)}")
            print(f"   Virtual Balance: ${data.get('data', {}).get('virtual_balance', 0)}")
            print(f"   Message: {data.get('data', {}).get('message', 'N/A')}")
        else:
            print(f"❌ Status endpoint failed: {response.text}")
            
    except Exception as e:
        print(f"❌ Status endpoint error: {e}")
    
    # Test 2: Try force initialization
    print("\n2️⃣ Testing force initialization...")
    try:
        response = requests.post(f"{API_BASE_URL}/api/v1/paper-trading/force-init")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Force initialization: {data.get('status')}")
            print(f"   Message: {data.get('message')}")
        else:
            print(f"❌ Force init failed: {response.text}")
            
    except Exception as e:
        print(f"❌ Force init error: {e}")
    
    # Test 3: Try to start paper trading
    print("\n3️⃣ Testing start endpoint...")
    try:
        response = requests.post(f"{API_BASE_URL}/api/v1/paper-trading/start")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Start endpoint: {data.get('status')}")
            print(f"   Message: {data.get('message')}")
            print(f"   Virtual Balance: ${data.get('data', {}).get('virtual_balance', 0)}")
        else:
            print(f"❌ Start failed: {response.text}")
            
    except Exception as e:
        print(f"❌ Start error: {e}")
    
    # Test 4: Check final status
    print("\n4️⃣ Checking final status...")
    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/paper-trading/status")
        
        if response.status_code == 200:
            data = response.json()
            is_enabled = data.get('data', {}).get('enabled', False)
            balance = data.get('data', {}).get('virtual_balance', 0)
            
            if is_enabled:
                print(f"✅ Paper trading is now RUNNING")
                print(f"   Virtual Balance: ${balance}")
                print(f"   🎉 START BUTTON SHOULD WORK!")
            else:
                print(f"❌ Paper trading still not running")
                print(f"   This indicates there's still an issue")
        else:
            print(f"❌ Final status check failed")
            
    except Exception as e:
        print(f"❌ Final status error: {e}")
    
    print("\n" + "=" * 60)
    print("🏁 Test Complete")
    print("\nIf you see '🎉 START BUTTON SHOULD WORK!' above, the issue is fixed!")
    print("If not, check the error messages for what needs to be addressed.")

if __name__ == "__main__":
    asyncio.run(test_paper_trading_start())
