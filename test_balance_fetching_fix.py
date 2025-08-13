#!/usr/bin/env python3

import asyncio
import requests
import json

async def test_balance_fetching_fix():
    """Test the balance fetching fix for real trading safety-status endpoint"""
    
    print("🚀 Balance Fetching Fix Test")
    print("=" * 60)
    
    base_url = "http://localhost:8000"
    
    # Test 1: Check account-balance endpoint
    print("\n📋 Test 1: Account Balance Endpoint")
    print("-" * 40)
    
    try:
        response = requests.get(f"{base_url}/api/v1/real-trading/account-balance")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Account balance endpoint working")
            print(f"Response: {json.dumps(data, indent=2)}")
        else:
            print(f"❌ Account balance endpoint failed: {response.text}")
            
    except Exception as e:
        print(f"❌ Error testing account balance: {e}")
    
    # Test 2: Check safety-status endpoint balance fields
    print("\n📋 Test 2: Safety Status Balance Fields")
    print("-" * 40)
    
    try:
        response = requests.get(f"{base_url}/api/v1/real-trading/safety-status")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            balance_fields = {
                'balance_total_usd': data['data'].get('balance_total_usd'),
                'available_usd': data['data'].get('available_usd'),
                'initial_margin_usd': data['data'].get('initial_margin_usd'),
                'maint_margin_usd': data['data'].get('maint_margin_usd')
            }
            
            print("Balance fields in safety-status:")
            for field, value in balance_fields.items():
                status = "✅" if value is not None else "❌"
                print(f"  {status} {field}: {value}")
                
            if all(v is not None for v in balance_fields.values()):
                print("✅ All balance fields populated successfully!")
            else:
                print("❌ Some balance fields are still null")
                
        else:
            print(f"❌ Safety status endpoint failed: {response.text}")
            
    except Exception as e:
        print(f"❌ Error testing safety status: {e}")
    
    # Test 3: Check if system is in testnet mode
    print("\n📋 Test 3: System Configuration Check")
    print("-" * 40)
    
    try:
        # Check if we can determine testnet mode from config
        print("🔍 Checking system configuration...")
        
        # Read config file to check testnet setting
        try:
            with open('config/config.yaml', 'r') as f:
                import yaml
                config = yaml.safe_load(f)
                testnet = config.get('exchange', {}).get('testnet', False)
                print(f"📊 Testnet mode: {testnet}")
                
                if testnet:
                    print("⚠️  System is in TESTNET mode - balance fetching may be limited")
                else:
                    print("💰 System is in MAINNET mode - balance fetching should work")
                    
        except Exception as e:
            print(f"⚠️  Could not read config: {e}")
            
    except Exception as e:
        print(f"❌ Error checking configuration: {e}")
    
    # Test 4: Provide solution recommendations
    print("\n📋 Test 4: Solution Recommendations")
    print("-" * 40)
    
    print("🔧 Potential Solutions:")
    print("1. ✅ Balance fetching logic added to safety-status endpoint")
    print("2. ⚠️  If testnet mode: Balance data may be limited/mock")
    print("3. 🔑 If mainnet mode: Check API credentials have balance permissions")
    print("4. 🌐 Network issues: Check exchange connectivity")
    print("5. 📊 Rate limiting: Exchange may be throttling balance requests")
    
    print("\n💡 Next Steps:")
    print("- If testnet: Balance will show null (expected behavior)")
    print("- If mainnet: Verify API key has 'Read' permissions for account data")
    print("- Check exchange client implementation for balance endpoint")
    
    print("\n" + "=" * 60)
    print("🎯 Balance Fetching Fix Test Complete")

if __name__ == "__main__":
    asyncio.run(test_balance_fetching_fix())
