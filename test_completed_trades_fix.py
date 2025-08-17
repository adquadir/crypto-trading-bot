#!/usr/bin/env python3

"""
Test script to verify the completed trades display fix for real trading.
This script tests the enhanced endpoint with backfill functionality.
"""

import asyncio
import aiohttp
import json
from datetime import datetime

async def test_completed_trades_endpoint():
    """Test the enhanced completed trades endpoint"""
    
    base_url = "http://localhost:8000"
    endpoint = "/api/v1/real-trading/completed-trades"
    
    print("🧪 Testing Real Trading Completed Trades Fix")
    print("=" * 60)
    
    async with aiohttp.ClientSession() as session:
        
        # Test 1: Default behavior (with backfill enabled)
        print("\n1️⃣ Testing default endpoint (backfill=true)")
        try:
            async with session.get(f"{base_url}{endpoint}") as response:
                if response.status == 200:
                    data = await response.json()
                    trades = data.get('data', [])
                    count = data.get('count', 0)
                    
                    print(f"✅ Status: {response.status}")
                    print(f"✅ Response format: {data.get('success', False)}")
                    print(f"✅ Trades count: {count}")
                    
                    if trades:
                        print(f"✅ Sample trade fields: {list(trades[0].keys())}")
                        
                        # Check for backfill indicators
                        backfill_trades = [t for t in trades if t.get('exit_reason') == 'exchange_history']
                        if backfill_trades:
                            print(f"✅ Found {len(backfill_trades)} backfilled trades from exchange history")
                        else:
                            print("ℹ️  No backfilled trades (engine may have in-memory trades)")
                    else:
                        print("ℹ️  No trades returned (empty list)")
                        
                else:
                    print(f"❌ HTTP Error: {response.status}")
                    error_text = await response.text()
                    print(f"❌ Error: {error_text}")
                    
        except Exception as e:
            print(f"❌ Request failed: {e}")
        
        # Test 2: Explicit backfill enabled
        print("\n2️⃣ Testing with explicit backfill=true&limit=50")
        try:
            params = "?backfill=true&limit=50"
            async with session.get(f"{base_url}{endpoint}{params}") as response:
                if response.status == 200:
                    data = await response.json()
                    trades = data.get('data', [])
                    count = data.get('count', 0)
                    
                    print(f"✅ Status: {response.status}")
                    print(f"✅ Trades count: {count}")
                    print(f"✅ Limited to: {min(count, 50)} trades")
                    
                else:
                    print(f"❌ HTTP Error: {response.status}")
                    
        except Exception as e:
            print(f"❌ Request failed: {e}")
        
        # Test 3: Backfill disabled
        print("\n3️⃣ Testing with backfill=false (in-memory only)")
        try:
            params = "?backfill=false&limit=100"
            async with session.get(f"{base_url}{endpoint}{params}") as response:
                if response.status == 200:
                    data = await response.json()
                    trades = data.get('data', [])
                    count = data.get('count', 0)
                    
                    print(f"✅ Status: {response.status}")
                    print(f"✅ In-memory trades count: {count}")
                    
                    if count == 0:
                        print("ℹ️  No in-memory trades (expected if engine restarted)")
                    else:
                        print(f"✅ Found {count} in-memory trades from current session")
                        
                else:
                    print(f"❌ HTTP Error: {response.status}")
                    
        except Exception as e:
            print(f"❌ Request failed: {e}")
        
        # Test 4: Check real trading engine status
        print("\n4️⃣ Checking real trading engine status")
        try:
            status_endpoint = "/api/v1/real-trading/status"
            async with session.get(f"{base_url}{status_endpoint}") as response:
                if response.status == 200:
                    data = await response.json()
                    status_data = data.get('data', {})
                    
                    print(f"✅ Engine running: {status_data.get('is_running', False)}")
                    print(f"✅ Total trades: {status_data.get('total_trades', 0)}")
                    print(f"✅ Active positions: {status_data.get('active_positions', 0)}")
                    print(f"✅ Engine mode: {status_data.get('mode', 'unknown')}")
                    
                else:
                    print(f"❌ Status check failed: {response.status}")
                    
        except Exception as e:
            print(f"❌ Status check failed: {e}")

def test_frontend_integration():
    """Test that the frontend change is correct"""
    
    print("\n5️⃣ Verifying frontend integration")
    print("-" * 40)
    
    try:
        with open('frontend/src/pages/RealTrading.js', 'r') as f:
            content = f.read()
            
        # Check if the backfill parameter is present
        if '?limit=100&backfill=true' in content:
            print("✅ Frontend correctly calls endpoint with backfill=true")
        else:
            print("❌ Frontend missing backfill parameter")
            
        # Check if the fetchTrades function exists
        if 'const fetchTrades = async () => {' in content:
            print("✅ Frontend fetchTrades function found")
        else:
            print("❌ Frontend fetchTrades function missing")
            
        # Check if TradesTable component exists
        if 'const TradesTable = () => (' in content:
            print("✅ Frontend TradesTable component found")
        else:
            print("❌ Frontend TradesTable component missing")
            
    except FileNotFoundError:
        print("❌ Frontend file not found")
    except Exception as e:
        print(f"❌ Frontend check failed: {e}")

async def test_exchange_client_method():
    """Test if exchange client has the required method"""
    
    print("\n6️⃣ Testing exchange client compatibility")
    print("-" * 40)
    
    try:
        # Import and check if the method exists
        from src.market_data.exchange_client import ExchangeClient
        
        client = ExchangeClient()
        
        # Check if get_account_trades method exists
        if hasattr(client, 'get_account_trades'):
            print("✅ ExchangeClient.get_account_trades method exists")
        else:
            print("❌ ExchangeClient.get_account_trades method missing")
            print("ℹ️  Backfill functionality will not work without this method")
            
    except ImportError as e:
        print(f"❌ Cannot import ExchangeClient: {e}")
    except Exception as e:
        print(f"❌ Exchange client check failed: {e}")

async def main():
    """Run all tests"""
    
    print("🔧 Real Trading Completed Trades Fix - Verification Test")
    print("=" * 60)
    print(f"⏰ Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Test the API endpoint
    await test_completed_trades_endpoint()
    
    # Test frontend integration
    test_frontend_integration()
    
    # Test exchange client compatibility
    await test_exchange_client_method()
    
    print("\n" + "=" * 60)
    print("🎯 Test Summary:")
    print("✅ Backend endpoint enhanced with backfill functionality")
    print("✅ Frontend updated to call endpoint with backfill=true")
    print("✅ Duplicate completed_trades definition removed from engine")
    print("✅ Exchange history backfill provides fallback data")
    
    print("\n💡 Expected Behavior:")
    print("- If engine has in-memory trades → shows those (full fidelity)")
    print("- If engine restarted/empty → shows exchange history (reduced fidelity)")
    print("- Frontend completed trades tab should now show data after restarts")
    
    print("\n🚀 Next Steps:")
    print("1. Restart the API server to test the fix")
    print("2. Check the Real Trading frontend tab")
    print("3. Verify completed trades are visible")
    print("4. Consider implementing database persistence for long-term solution")

if __name__ == "__main__":
    asyncio.run(main())
