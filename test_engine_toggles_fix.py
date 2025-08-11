#!/usr/bin/env python3
"""
Test the new engine toggle endpoints that match the frontend expectations
"""

import asyncio
import aiohttp
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_BASE_URL = "http://localhost:8000"

async def test_engine_toggles():
    """Test the new engine toggle endpoints"""
    
    async with aiohttp.ClientSession() as session:
        
        print("🧪 Testing Engine Toggle Endpoints")
        print("=" * 50)
        
        # Test 1: Get initial engine status
        print("\n1️⃣ Testing GET /api/v1/paper-trading/engines")
        try:
            async with session.get(f"{API_BASE_URL}/api/v1/paper-trading/engines") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ GET engines status: {response.status}")
                    print(f"📊 Response: {json.dumps(data, indent=2)}")
                    
                    # Extract current states
                    engines_data = data.get('data', {})
                    opportunity_manager_enabled = engines_data.get('opportunity_manager', True)
                    profit_scraper_enabled = engines_data.get('profit_scraper', True)
                    
                    print(f"🎯 Opportunity Manager: {'ENABLED' if opportunity_manager_enabled else 'DISABLED'}")
                    print(f"🎯 Profit Scraper: {'ENABLED' if profit_scraper_enabled else 'DISABLED'}")
                else:
                    print(f"❌ GET engines failed: {response.status}")
                    text = await response.text()
                    print(f"Error: {text}")
                    return False
        except Exception as e:
            print(f"❌ GET engines error: {e}")
            return False
        
        # Test 2: Toggle Opportunity Manager OFF
        print("\n2️⃣ Testing POST /api/v1/paper-trading/engine-toggle (Opportunity Manager OFF)")
        try:
            toggle_data = {
                "engine": "opportunity_manager",
                "enabled": False
            }
            
            async with session.post(
                f"{API_BASE_URL}/api/v1/paper-trading/engine-toggle",
                json=toggle_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Toggle opportunity_manager OFF: {response.status}")
                    print(f"📊 Response: {json.dumps(data, indent=2)}")
                else:
                    print(f"❌ Toggle failed: {response.status}")
                    text = await response.text()
                    print(f"Error: {text}")
                    return False
        except Exception as e:
            print(f"❌ Toggle error: {e}")
            return False
        
        # Test 3: Toggle Profit Scraper OFF
        print("\n3️⃣ Testing POST /api/v1/paper-trading/engine-toggle (Profit Scraper OFF)")
        try:
            toggle_data = {
                "engine": "profit_scraper",
                "enabled": False
            }
            
            async with session.post(
                f"{API_BASE_URL}/api/v1/paper-trading/engine-toggle",
                json=toggle_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Toggle profit_scraper OFF: {response.status}")
                    print(f"📊 Response: {json.dumps(data, indent=2)}")
                else:
                    print(f"❌ Toggle failed: {response.status}")
                    text = await response.text()
                    print(f"Error: {text}")
                    return False
        except Exception as e:
            print(f"❌ Toggle error: {e}")
            return False
        
        # Test 4: Verify both are OFF
        print("\n4️⃣ Testing GET /api/v1/paper-trading/engines (Verify both OFF)")
        try:
            async with session.get(f"{API_BASE_URL}/api/v1/paper-trading/engines") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ GET engines status: {response.status}")
                    print(f"📊 Response: {json.dumps(data, indent=2)}")
                    
                    # Verify both are disabled
                    engines_data = data.get('data', {})
                    opportunity_manager_enabled = engines_data.get('opportunity_manager', True)
                    profit_scraper_enabled = engines_data.get('profit_scraper', True)
                    
                    if not opportunity_manager_enabled and not profit_scraper_enabled:
                        print("✅ Both engines successfully disabled!")
                    else:
                        print(f"❌ Expected both OFF, got OM: {opportunity_manager_enabled}, PS: {profit_scraper_enabled}")
                        return False
                else:
                    print(f"❌ GET engines failed: {response.status}")
                    return False
        except Exception as e:
            print(f"❌ GET engines error: {e}")
            return False
        
        # Test 5: Toggle Opportunity Manager back ON
        print("\n5️⃣ Testing POST /api/v1/paper-trading/engine-toggle (Opportunity Manager ON)")
        try:
            toggle_data = {
                "engine": "opportunity_manager",
                "enabled": True
            }
            
            async with session.post(
                f"{API_BASE_URL}/api/v1/paper-trading/engine-toggle",
                json=toggle_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Toggle opportunity_manager ON: {response.status}")
                    print(f"📊 Response: {json.dumps(data, indent=2)}")
                else:
                    print(f"❌ Toggle failed: {response.status}")
                    text = await response.text()
                    print(f"Error: {text}")
                    return False
        except Exception as e:
            print(f"❌ Toggle error: {e}")
            return False
        
        # Test 6: Toggle Profit Scraper back ON
        print("\n6️⃣ Testing POST /api/v1/paper-trading/engine-toggle (Profit Scraper ON)")
        try:
            toggle_data = {
                "engine": "profit_scraper",
                "enabled": True
            }
            
            async with session.post(
                f"{API_BASE_URL}/api/v1/paper-trading/engine-toggle",
                json=toggle_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Toggle profit_scraper ON: {response.status}")
                    print(f"📊 Response: {json.dumps(data, indent=2)}")
                else:
                    print(f"❌ Toggle failed: {response.status}")
                    text = await response.text()
                    print(f"Error: {text}")
                    return False
        except Exception as e:
            print(f"❌ Toggle error: {e}")
            return False
        
        # Test 7: Final verification - both should be ON
        print("\n7️⃣ Testing GET /api/v1/paper-trading/engines (Final verification)")
        try:
            async with session.get(f"{API_BASE_URL}/api/v1/paper-trading/engines") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ GET engines status: {response.status}")
                    print(f"📊 Response: {json.dumps(data, indent=2)}")
                    
                    # Verify both are enabled
                    engines_data = data.get('data', {})
                    opportunity_manager_enabled = engines_data.get('opportunity_manager', True)
                    profit_scraper_enabled = engines_data.get('profit_scraper', True)
                    
                    if opportunity_manager_enabled and profit_scraper_enabled:
                        print("✅ Both engines successfully re-enabled!")
                        return True
                    else:
                        print(f"❌ Expected both ON, got OM: {opportunity_manager_enabled}, PS: {profit_scraper_enabled}")
                        return False
                else:
                    print(f"❌ GET engines failed: {response.status}")
                    return False
        except Exception as e:
            print(f"❌ GET engines error: {e}")
            return False
        
        return True

async def test_invalid_engine_name():
    """Test invalid engine name handling"""
    print("\n🧪 Testing Invalid Engine Name Handling")
    print("=" * 50)
    
    async with aiohttp.ClientSession() as session:
        try:
            toggle_data = {
                "engine": "invalid_engine",
                "enabled": True
            }
            
            async with session.post(
                f"{API_BASE_URL}/api/v1/paper-trading/engine-toggle",
                json=toggle_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 400:
                    data = await response.json()
                    print(f"✅ Invalid engine name properly rejected: {response.status}")
                    print(f"📊 Error response: {json.dumps(data, indent=2)}")
                    return True
                else:
                    print(f"❌ Expected 400 error, got: {response.status}")
                    return False
        except Exception as e:
            print(f"❌ Invalid engine test error: {e}")
            return False

async def main():
    """Run all tests"""
    print("🚀 Starting Engine Toggle API Tests")
    print("=" * 60)
    
    # Test basic functionality
    basic_test_passed = await test_engine_toggles()
    
    # Test error handling
    error_test_passed = await test_invalid_engine_name()
    
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 60)
    print(f"✅ Basic Toggle Tests: {'PASSED' if basic_test_passed else 'FAILED'}")
    print(f"✅ Error Handling Tests: {'PASSED' if error_test_passed else 'FAILED'}")
    
    if basic_test_passed and error_test_passed:
        print("\n🎉 ALL TESTS PASSED! Engine toggle endpoints are working correctly.")
        print("\n🎯 Frontend toggles should now work without 'not found' errors!")
        print("\nEndpoints implemented:")
        print("  • GET  /api/v1/paper-trading/engines")
        print("  • POST /api/v1/paper-trading/engine-toggle")
        return True
    else:
        print("\n❌ SOME TESTS FAILED! Check the API server and endpoints.")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
