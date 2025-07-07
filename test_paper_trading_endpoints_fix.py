#!/usr/bin/env python3
"""
Test and fix all paper trading endpoints
"""

import requests
import json
import sys
import time

def test_endpoint(method, url, data=None, expected_status=200):
    """Test an endpoint and return result"""
    try:
        if method.upper() == 'GET':
            response = requests.get(url, timeout=10)
        elif method.upper() == 'POST':
            response = requests.post(url, json=data, timeout=10)
        else:
            return False, f"Unsupported method: {method}"
        
        success = response.status_code == expected_status
        
        if success:
            try:
                result = response.json()
                return True, result
            except:
                return True, response.text
        else:
            return False, f"Status {response.status_code}: {response.text}"
            
    except Exception as e:
        return False, f"Request failed: {e}"

def main():
    base_url = "http://localhost:8000/api/v1/paper-trading"
    
    print("🧪 Testing Paper Trading Endpoints...")
    print("=" * 50)
    
    # Test endpoints
    endpoints = [
        ("GET", "/status", None),
        ("GET", "/strategies", None),
        ("GET", "/strategy", None),
        ("GET", "/health", None),
        ("GET", "/positions", None),
        ("GET", "/performance", None),
        ("GET", "/config", None),
        ("POST", "/start", None),
        ("POST", "/stop", None),
    ]
    
    results = {}
    
    for method, endpoint, data in endpoints:
        url = f"{base_url}{endpoint}"
        print(f"\n🔍 Testing {method} {endpoint}")
        
        success, result = test_endpoint(method, url, data)
        results[endpoint] = {"success": success, "result": result}
        
        if success:
            print(f"✅ SUCCESS")
            if isinstance(result, dict):
                if 'status' in result:
                    print(f"   Status: {result['status']}")
                if 'message' in result:
                    print(f"   Message: {result['message']}")
        else:
            print(f"❌ FAILED: {result}")
    
    print("\n" + "=" * 50)
    print("📊 SUMMARY")
    print("=" * 50)
    
    passed = sum(1 for r in results.values() if r['success'])
    total = len(results)
    
    print(f"Passed: {passed}/{total}")
    
    if passed < total:
        print("\n❌ FAILED ENDPOINTS:")
        for endpoint, result in results.items():
            if not result['success']:
                print(f"  {endpoint}: {result['result']}")
    else:
        print("\n🎉 ALL ENDPOINTS WORKING!")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
