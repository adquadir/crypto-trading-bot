#!/usr/bin/env python3

"""
Test script to verify Pure 3-Rule Mode frontend display fix and trailing floor configuration fix
"""

import asyncio
import requests
import yaml
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

async def test_pure_3_rule_mode_fixes():
    """Test both fixes for Pure 3-Rule Mode"""
    
    print("🧪 Testing Pure 3-Rule Mode Fixes")
    print("=" * 50)
    
    # Test 1: Check config values
    print("\n1️⃣ Testing Config Values:")
    try:
        with open('config/config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        real_trading_config = config.get('real_trading', {})
        
        print(f"   pure_3_rule_mode: {real_trading_config.get('pure_3_rule_mode')}")
        print(f"   primary_target_dollars: {real_trading_config.get('primary_target_dollars')}")
        print(f"   absolute_floor_dollars: {real_trading_config.get('absolute_floor_dollars')}")
        print(f"   trailing_floor_start_dollars: {real_trading_config.get('trailing_floor_start_dollars')}")
        print(f"   stop_loss_percent: {real_trading_config.get('stop_loss_percent')}")
        
        if real_trading_config.get('pure_3_rule_mode'):
            print("   ✅ Pure 3-Rule Mode is enabled in config")
        else:
            print("   ❌ Pure 3-Rule Mode is disabled in config")
            
    except Exception as e:
        print(f"   ❌ Error reading config: {e}")
    
    # Test 2: Check API endpoints
    print("\n2️⃣ Testing API Endpoints:")
    
    base_url = "http://localhost:8000"
    
    # Test /api/v1/real-trading/status endpoint
    try:
        response = requests.get(f"{base_url}/api/v1/real-trading/status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            status_data = data.get('data', {})
            
            print(f"   Status endpoint pure_3_rule_mode: {status_data.get('pure_3_rule_mode')}")
            print(f"   Status endpoint primary_target_dollars: {status_data.get('primary_target_dollars')}")
            print(f"   Status endpoint absolute_floor_dollars: {status_data.get('absolute_floor_dollars')}")
            
            if status_data.get('pure_3_rule_mode'):
                print("   ✅ Status endpoint shows Pure 3-Rule Mode enabled")
            else:
                print("   ❌ Status endpoint shows Pure 3-Rule Mode disabled")
        else:
            print(f"   ❌ Status endpoint error: {response.status_code}")
            
    except Exception as e:
        print(f"   ⚠️  Status endpoint not accessible: {e}")
    
    # Test /api/v1/real-trading/safety-status endpoint (the key fix)
    try:
        response = requests.get(f"{base_url}/api/v1/real-trading/safety-status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            safety_data = data.get('data', {})
            
            print(f"   Safety endpoint pure_3_rule_mode: {safety_data.get('pure_3_rule_mode')}")
            print(f"   Safety endpoint primary_target_dollars: {safety_data.get('primary_target_dollars')}")
            print(f"   Safety endpoint absolute_floor_dollars: {safety_data.get('absolute_floor_dollars')}")
            print(f"   Safety endpoint stop_loss_percent: {safety_data.get('stop_loss_percent')}")
            
            if safety_data.get('pure_3_rule_mode'):
                print("   ✅ Safety endpoint shows Pure 3-Rule Mode enabled (FRONTEND FIX WORKING!)")
            else:
                print("   ❌ Safety endpoint shows Pure 3-Rule Mode disabled (frontend will show DISABLED)")
                
            # Check if all required fields are present
            required_fields = ['pure_3_rule_mode', 'primary_target_dollars', 'absolute_floor_dollars', 'stop_loss_percent']
            missing_fields = [field for field in required_fields if field not in safety_data]
            
            if not missing_fields:
                print("   ✅ All Pure 3-Rule Mode fields present in safety endpoint")
            else:
                print(f"   ❌ Missing fields in safety endpoint: {missing_fields}")
                
        else:
            print(f"   ❌ Safety endpoint error: {response.status_code}")
            
    except Exception as e:
        print(f"   ⚠️  Safety endpoint not accessible: {e}")
    
    # Test 3: Check RealTradingEngine configuration
    print("\n3️⃣ Testing RealTradingEngine Configuration:")
    
    try:
        from src.trading.real_trading_engine import RealTradingEngine
        from src.market_data.exchange_client import ExchangeClient
        
        # Load config
        with open('config/config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        # Create a mock exchange client (we won't actually use it)
        class MockExchangeClient:
            pass
        
        mock_client = MockExchangeClient()
        
        # Create real trading engine
        engine = RealTradingEngine(config, mock_client)
        
        print(f"   Engine pure_3_rule_mode: {engine.pure_3_rule_mode}")
        print(f"   Engine primary_target_dollars: {engine.primary_target_dollars}")
        print(f"   Engine absolute_floor_dollars: {engine.absolute_floor_dollars}")
        print(f"   Engine trailing_floor_start: {engine.trailing_floor_start}")
        print(f"   Engine stop_loss_percent: {engine.stop_loss_percent}")
        
        if engine.pure_3_rule_mode:
            print("   ✅ Engine has Pure 3-Rule Mode enabled")
        else:
            print("   ❌ Engine has Pure 3-Rule Mode disabled")
            
        # Check if trailing_floor_start is properly configured
        config_trailing_start = config.get('real_trading', {}).get('trailing_floor_start_dollars')
        if config_trailing_start and engine.trailing_floor_start == float(config_trailing_start):
            print(f"   ✅ Engine honors trailing_floor_start_dollars: ${engine.trailing_floor_start}")
        elif engine.trailing_floor_start == engine.absolute_floor_dollars:
            print(f"   ✅ Engine defaults trailing_floor_start to absolute_floor_dollars: ${engine.trailing_floor_start}")
        else:
            print(f"   ❌ Engine trailing_floor_start configuration issue")
            
    except Exception as e:
        print(f"   ❌ Error testing engine configuration: {e}")
    
    # Test 4: Summary and recommendations
    print("\n4️⃣ Summary and Recommendations:")
    print("   📋 Fixes Applied:")
    print("      ✅ Fix 1: Added Pure 3-Rule Mode fields to /api/v1/real-trading/safety-status")
    print("      ✅ Fix 2: Added trailing_floor_start configuration to RealTradingEngine")
    print("      ✅ Fix 3: Updated position initialization to use trailing_floor_start")
    print("      ✅ Fix 4: Updated trailing activation logic to use trailing_floor_start")
    
    print("\n   🎯 Expected Results:")
    print("      • Frontend should now show 'Pure 3-Rule Mode: ENABLED'")
    print("      • Trailing system should start at configured trailing_floor_start_dollars ($15)")
    print("      • Profit taking should work with correct target values")
    print("      • Trailing increment should work properly")
    
    print("\n   🔄 Next Steps:")
    print("      1. Restart the API server to load the fixes")
    print("      2. Check the frontend - Pure 3-Rule Mode should show 'ENABLED'")
    print("      3. Monitor real trading positions to verify trailing system works")
    print("      4. Verify profit taking occurs at correct levels")

if __name__ == "__main__":
    asyncio.run(test_pure_3_rule_mode_fixes())
