#!/usr/bin/env python3
"""
Test Paper Trading API Fix
Tests the fixed paper trading endpoints
"""

import asyncio
import sys
import os
import requests
import json
from datetime import datetime

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def test_paper_trading_endpoints():
    """Test paper trading API endpoints"""
    base_url = "http://localhost:8000/api/v1/paper-trading"
    
    print("🧪 Testing Paper Trading API Endpoints...")
    print("=" * 60)
    
    # Test endpoints
    endpoints = [
        ("/strategies", "GET", "Available strategies"),
        ("/strategy", "GET", "Current strategy"),
        ("/status", "GET", "Paper trading status"),
        ("/health", "GET", "Health check")
    ]
    
    results = []
    
    for endpoint, method, description in endpoints:
        url = f"{base_url}{endpoint}"
        print(f"\n📡 Testing {method} {endpoint} - {description}")
        
        try:
            if method == "GET":
                response = requests.get(url, timeout=10)
            else:
                response = requests.post(url, timeout=10)
            
            print(f"   Status Code: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"   ✅ SUCCESS - Response: {json.dumps(data, indent=2)[:200]}...")
                    results.append((endpoint, "SUCCESS", response.status_code))
                except json.JSONDecodeError as e:
                    print(f"   ❌ JSON DECODE ERROR: {e}")
                    print(f"   Raw response: {response.text[:200]}...")
                    results.append((endpoint, "JSON_ERROR", response.status_code))
            else:
                print(f"   ❌ ERROR - Status: {response.status_code}")
                print(f"   Response: {response.text[:200]}...")
                results.append((endpoint, "ERROR", response.status_code))
                
        except requests.exceptions.RequestException as e:
            print(f"   ❌ REQUEST ERROR: {e}")
            results.append((endpoint, "REQUEST_ERROR", 0))
        except Exception as e:
            print(f"   ❌ UNEXPECTED ERROR: {e}")
            results.append((endpoint, "UNEXPECTED_ERROR", 0))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 60)
    
    success_count = 0
    for endpoint, status, code in results:
        status_emoji = "✅" if status == "SUCCESS" else "❌"
        print(f"{status_emoji} {endpoint}: {status} ({code})")
        if status == "SUCCESS":
            success_count += 1
    
    print(f"\n🎯 Success Rate: {success_count}/{len(results)} ({success_count/len(results)*100:.1f}%)")
    
    if success_count == len(results):
        print("🎉 ALL TESTS PASSED! Paper Trading API is working correctly.")
        return True
    else:
        print("⚠️  Some tests failed. Check the errors above.")
        return False

def test_server_running():
    """Check if the server is running"""
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            print("✅ Server is running")
            return True
        else:
            print(f"❌ Server responded with status {response.status_code}")
            return False
    except requests.exceptions.RequestException:
        print("❌ Server is not running or not accessible")
        return False

if __name__ == "__main__":
    print("🚀 Paper Trading API Fix Test")
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Check if server is running
    if not test_server_running():
        print("\n💡 To start the server, run:")
        print("   python src/api/main.py")
        sys.exit(1)
    
    # Test the endpoints
    success = test_paper_trading_endpoints()
    
    print(f"\n⏰ Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if success:
        print("🎉 Paper Trading API is working correctly!")
        sys.exit(0)
    else:
        print("❌ Paper Trading API has issues that need to be fixed.")
        sys.exit(1)
