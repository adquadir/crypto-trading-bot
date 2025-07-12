#!/usr/bin/env python3
"""
Test Pure 3-Rule Mode Frontend/Backend Integration
Tests the new API endpoints and frontend integration for Pure 3-Rule Mode control
"""

import asyncio
import requests
import json
import time
from datetime import datetime

# Configuration
API_BASE_URL = "http://localhost:8000"
PAPER_TRADING_BASE = f"{API_BASE_URL}/api/v1/paper-trading"

def test_rule_mode_endpoints():
    """Test the Pure 3-Rule Mode API endpoints"""
    print("🎯 Testing Pure 3-Rule Mode API Endpoints")
    print("=" * 60)
    
    # Test 1: Get current rule mode status
    print("\n1. Testing GET /rule-mode endpoint...")
    try:
        response = requests.get(f"{PAPER_TRADING_BASE}/rule-mode")
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Success: {data['status']}")
            print(f"   📊 Current Mode: {data['data']['mode_name']}")
            print(f"   🎯 Pure 3-Rule Mode: {data['data']['pure_3_rule_mode']}")
            print(f"   📝 Description: {data['data']['description']}")
            
            if 'rules_active' in data['data']:
                print(f"   🔧 Active Rules: {data['data']['rules_active']}")
            
            current_mode = data['data']['pure_3_rule_mode']
        else:
            print(f"   ❌ Failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    # Test 2: Toggle rule mode
    print("\n2. Testing POST /rule-mode endpoint (toggle mode)...")
    try:
        new_mode = not current_mode  # Toggle the mode
        response = requests.post(
            f"{PAPER_TRADING_BASE}/rule-mode",
            params={"pure_3_rule_mode": new_mode}
        )
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Success: {data['status']}")
            print(f"   🔄 Mode Changed: {data['data']['old_mode']} → {data['data']['new_mode']}")
            print(f"   📝 Message: {data['message']}")
            print(f"   ⚡ Applied: {data['data']['change_applied']}")
        else:
            print(f"   ❌ Failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    # Test 3: Get rule configuration
    print("\n3. Testing GET /rule-config endpoint...")
    try:
        response = requests.get(f"{PAPER_TRADING_BASE}/rule-config")
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Success: {data['status']}")
            print(f"   💰 Primary Target: ${data['data']['primary_target_dollars']}")
            print(f"   🛡️ Absolute Floor: ${data['data']['absolute_floor_dollars']}")
            print(f"   🛑 Stop Loss: {data['data']['stop_loss_percent']}%")
            print(f"   🔧 Engine Available: {data['data']['engine_available']}")
            
            if 'leverage_info' in data['data']:
                leverage_info = data['data']['leverage_info']
                print(f"   📊 Leverage: {leverage_info['current_leverage']}x")
                print(f"   💵 Capital per Position: ${leverage_info['capital_per_position']}")
        else:
            print(f"   ❌ Failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    # Test 4: Update rule configuration
    print("\n4. Testing POST /rule-config endpoint...")
    try:
        new_config = {
            "primary_target_dollars": 12.0,
            "absolute_floor_dollars": 8.0,
            "stop_loss_percent": 0.6
        }
        
        response = requests.post(
            f"{PAPER_TRADING_BASE}/rule-config",
            json=new_config
        )
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Success: {data['status']}")
            print(f"   💰 New Target: ${data['data']['primary_target_dollars']}")
            print(f"   🛡️ New Floor: ${data['data']['absolute_floor_dollars']}")
            print(f"   🛑 New Stop Loss: {data['data']['stop_loss_percent']}%")
            print(f"   📝 Applies To: {data['data']['applies_to']}")
            print(f"   ✅ Valid Config: {data['data']['validation']['configuration_valid']}")
        else:
            print(f"   ❌ Failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    # Test 5: Test invalid configuration (should fail)
    print("\n5. Testing invalid configuration (should fail)...")
    try:
        invalid_config = {
            "primary_target_dollars": 5.0,  # Lower than floor
            "absolute_floor_dollars": 8.0,
            "stop_loss_percent": 0.6
        }
        
        response = requests.post(
            f"{PAPER_TRADING_BASE}/rule-config",
            json=invalid_config
        )
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 400:
            print(f"   ✅ Correctly rejected invalid config")
            print(f"   📝 Error: {response.json()['detail']}")
        else:
            print(f"   ❌ Should have rejected invalid config: {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    return True

def test_status_endpoint_integration():
    """Test that the status endpoint includes rule mode information"""
    print("\n🔍 Testing Status Endpoint Integration")
    print("=" * 60)
    
    try:
        response = requests.get(f"{PAPER_TRADING_BASE}/status")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Success: {data['status']}")
            
            # Check if rule_mode is included in status
            if 'rule_mode' in data['data']:
                rule_mode = data['data']['rule_mode']
                print(f"🎯 Rule Mode in Status: ✅")
                print(f"   Mode: {rule_mode['mode_name']}")
                print(f"   Pure 3-Rule: {rule_mode['pure_3_rule_mode']}")
                print(f"   Target: ${rule_mode['primary_target_dollars']}")
                print(f"   Floor: ${rule_mode['absolute_floor_dollars']}")
                print(f"   Stop Loss: {rule_mode['stop_loss_percent']}%")
                return True
            else:
                print(f"❌ Rule mode not found in status response")
                return False
        else:
            print(f"❌ Failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_frontend_data_flow():
    """Test the complete data flow that the frontend would use"""
    print("\n🌐 Testing Frontend Data Flow")
    print("=" * 60)
    
    # Simulate frontend startup - fetch all required data
    endpoints_to_test = [
        ("/status", "Status"),
        ("/rule-mode", "Rule Mode"),
        ("/rule-config", "Rule Config"),
        ("/strategies", "Strategies"),
        ("/strategy", "Current Strategy")
    ]
    
    all_success = True
    
    for endpoint, name in endpoints_to_test:
        print(f"\n📡 Fetching {name} ({endpoint})...")
        try:
            response = requests.get(f"{PAPER_TRADING_BASE}{endpoint}")
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ {name}: Success")
                
                # Log key data points
                if endpoint == "/status" and 'rule_mode' in data.get('data', {}):
                    print(f"   🎯 Rule mode included in status")
                elif endpoint == "/rule-mode":
                    print(f"   🎯 Mode: {data['data']['mode_name']}")
                elif endpoint == "/rule-config":
                    print(f"   ⚙️ Config: ${data['data']['primary_target_dollars']}/${data['data']['absolute_floor_dollars']}")
                    
            else:
                print(f"   ❌ {name}: Failed ({response.status_code})")
                all_success = False
                
        except Exception as e:
            print(f"   ❌ {name}: Error - {e}")
            all_success = False
    
    return all_success

def test_rule_mode_persistence():
    """Test that rule mode changes persist"""
    print("\n💾 Testing Rule Mode Persistence")
    print("=" * 60)
    
    try:
        # Get initial mode
        response = requests.get(f"{PAPER_TRADING_BASE}/rule-mode")
        if response.status_code != 200:
            print("❌ Failed to get initial mode")
            return False
        
        initial_mode = response.json()['data']['pure_3_rule_mode']
        print(f"📊 Initial Mode: {'Pure 3-Rule' if initial_mode else 'Complex'}")
        
        # Toggle mode
        new_mode = not initial_mode
        response = requests.post(
            f"{PAPER_TRADING_BASE}/rule-mode",
            params={"pure_3_rule_mode": new_mode}
        )
        
        if response.status_code != 200:
            print("❌ Failed to toggle mode")
            return False
        
        print(f"🔄 Toggled to: {'Pure 3-Rule' if new_mode else 'Complex'}")
        
        # Wait a moment
        time.sleep(1)
        
        # Check if change persisted
        response = requests.get(f"{PAPER_TRADING_BASE}/rule-mode")
        if response.status_code != 200:
            print("❌ Failed to verify persistence")
            return False
        
        current_mode = response.json()['data']['pure_3_rule_mode']
        
        if current_mode == new_mode:
            print(f"✅ Mode change persisted: {'Pure 3-Rule' if current_mode else 'Complex'}")
            
            # Restore original mode
            response = requests.post(
                f"{PAPER_TRADING_BASE}/rule-mode",
                params={"pure_3_rule_mode": initial_mode}
            )
            
            if response.status_code == 200:
                print(f"🔄 Restored original mode: {'Pure 3-Rule' if initial_mode else 'Complex'}")
                return True
            else:
                print("⚠️ Could not restore original mode")
                return False
        else:
            print(f"❌ Mode change did not persist")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    """Run all Pure 3-Rule Mode integration tests"""
    print("🎯 PURE 3-RULE MODE FRONTEND/BACKEND INTEGRATION TEST")
    print("=" * 80)
    print(f"🕒 Test Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🌐 API Base URL: {API_BASE_URL}")
    print()
    
    tests = [
        ("Rule Mode API Endpoints", test_rule_mode_endpoints),
        ("Status Endpoint Integration", test_status_endpoint_integration),
        ("Frontend Data Flow", test_frontend_data_flow),
        ("Rule Mode Persistence", test_rule_mode_persistence)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n🧪 Running: {test_name}")
        print("-" * 60)
        
        try:
            success = test_func()
            results[test_name] = success
            
            if success:
                print(f"\n✅ {test_name}: PASSED")
            else:
                print(f"\n❌ {test_name}: FAILED")
                
        except Exception as e:
            print(f"\n💥 {test_name}: ERROR - {e}")
            results[test_name] = False
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status:<12} {test_name}")
    
    print(f"\n🎯 Overall Result: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED! Pure 3-Rule Mode integration is working correctly.")
        print("\n📋 Frontend Integration Ready:")
        print("   • Rule mode toggle switch")
        print("   • Rule configuration panel")
        print("   • Mode status display")
        print("   • Real-time updates")
        print("   • Parameter validation")
    else:
        print("⚠️ Some tests failed. Check the output above for details.")
    
    print(f"\n🕒 Test Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
