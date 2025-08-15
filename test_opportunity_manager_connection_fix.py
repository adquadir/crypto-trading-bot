#!/usr/bin/env python3

"""
Test script to verify OpportunityManager connection fix in real trading routes
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import requests
import json
from datetime import datetime

def test_opportunity_manager_status():
    """Test the OpportunityManager status endpoint"""
    print("🔧 Testing OpportunityManager Connection Fix")
    print("=" * 60)
    
    try:
        # Test the opportunity manager status endpoint
        print("📡 Testing /api/v1/real-trading/opportunity-manager/status...")
        response = requests.get("http://localhost:8000/api/v1/real-trading/opportunity-manager/status")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Status endpoint working!")
            print(f"   Response: {json.dumps(data, indent=2)}")
            
            if data.get('success') and data.get('data', {}).get('connected'):
                print("🔗 OpportunityManager is CONNECTED!")
                return True
            else:
                print("❌ OpportunityManager is NOT connected")
                return False
        else:
            print(f"❌ Status endpoint failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to API server")
        print("   Make sure the API server is running on localhost:8000")
        return False
    except Exception as e:
        print(f"❌ Error testing status: {e}")
        return False

def test_real_trading_status():
    """Test the real trading status endpoint"""
    print("\n📡 Testing /api/v1/real-trading/status...")
    
    try:
        response = requests.get("http://localhost:8000/api/v1/real-trading/status")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Real trading status endpoint working!")
            print(f"   Response: {json.dumps(data, indent=2)}")
            return True
        else:
            print(f"❌ Real trading status failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing real trading status: {e}")
        return False

def main():
    """Main test function"""
    print(f"🚀 OpportunityManager Connection Fix Test")
    print(f"⏰ Started at: {datetime.now()}")
    print()
    
    # Test the endpoints
    status_ok = test_opportunity_manager_status()
    trading_status_ok = test_real_trading_status()
    
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS:")
    print(f"   OpportunityManager Status: {'✅ PASS' if status_ok else '❌ FAIL'}")
    print(f"   Real Trading Status: {'✅ PASS' if trading_status_ok else '❌ FAIL'}")
    
    if status_ok and trading_status_ok:
        print("\n🎉 ALL TESTS PASSED!")
        print("   The OpportunityManager connection fix is working correctly.")
        print("   The 'not connected' issue should now be resolved.")
    else:
        print("\n⚠️  SOME TESTS FAILED")
        print("   Check the API server logs for more details.")
    
    print(f"\n⏰ Completed at: {datetime.now()}")

if __name__ == "__main__":
    main()
