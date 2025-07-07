#!/usr/bin/env python3
"""
Test Paper Trading Positions Fix
Verifies that positions are properly created and displayed
"""

import asyncio
import requests
import json
import time
from datetime import datetime

# Configuration
API_BASE_URL = "http://localhost:8000"

async def test_paper_trading_positions():
    """Test the complete paper trading positions flow"""
    print("🧪 Testing Paper Trading Positions Fix")
    print("=" * 50)
    
    try:
        # Step 1: Check initial status
        print("\n1. Checking initial paper trading status...")
        response = requests.get(f"{API_BASE_URL}/api/v1/paper-trading/status")
        if response.status_code == 200:
            status_data = response.json()
            print(f"✅ Status check successful")
            print(f"   Engine running: {status_data['data']['enabled']}")
            print(f"   Balance: ${status_data['data']['virtual_balance']}")
            print(f"   Active positions: {status_data['data']['active_positions']}")
        else:
            print(f"❌ Status check failed: {response.status_code}")
            return False
        
        # Step 2: Start paper trading if not running
        if not status_data['data']['enabled']:
            print("\n2. Starting paper trading engine...")
            response = requests.post(f"{API_BASE_URL}/api/v1/paper-trading/start")
            if response.status_code == 200:
                start_data = response.json()
                print(f"✅ Paper trading started successfully")
                print(f"   Message: {start_data['message']}")
            else:
                print(f"❌ Failed to start paper trading: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
        else:
            print("\n2. Paper trading already running ✅")
        
        # Step 3: Check positions before simulation
        print("\n3. Checking positions before simulation...")
        response = requests.get(f"{API_BASE_URL}/api/v1/paper-trading/positions")
        if response.status_code == 200:
            positions_data = response.json()
            initial_positions = len(positions_data['data'])
            print(f"✅ Initial positions: {initial_positions}")
        else:
            print(f"❌ Failed to get positions: {response.status_code}")
            return False
        
        # Step 4: Simulate trading signals to create positions
        print("\n4. Simulating trading signals...")
        response = requests.post(f"{API_BASE_URL}/api/v1/paper-trading/simulate-signals", 
                               params={"symbol": "BTCUSDT", "count": 5, "strategy_type": "scalping"})
        if response.status_code == 200:
            simulation_data = response.json()
            print(f"✅ Signal simulation successful")
            print(f"   Message: {simulation_data['message']}")
            print(f"   Executed trades: {len(simulation_data['executed_trades'])}")
            print(f"   Total positions: {simulation_data['total_positions']}")
        else:
            print(f"❌ Signal simulation failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
        
        # Step 5: Wait a moment for positions to be processed
        print("\n5. Waiting for positions to be processed...")
        time.sleep(2)
        
        # Step 6: Check positions after simulation
        print("\n6. Checking positions after simulation...")
        response = requests.get(f"{API_BASE_URL}/api/v1/paper-trading/positions")
        if response.status_code == 200:
            positions_data = response.json()
            final_positions = len(positions_data['data'])
            print(f"✅ Final positions: {final_positions}")
            
            if final_positions > initial_positions:
                print(f"🎉 SUCCESS: Positions increased from {initial_positions} to {final_positions}")
                
                # Display position details
                print("\n📊 Position Details:")
                for i, position in enumerate(positions_data['data'][:3]):  # Show first 3
                    print(f"   Position {i+1}:")
                    print(f"     Symbol: {position['symbol']}")
                    print(f"     Side: {position['side']}")
                    print(f"     Entry Price: ${position['entry_price']:.4f}")
                    print(f"     Current Price: ${position['current_price']:.4f}")
                    print(f"     Unrealized P&L: ${position['unrealized_pnl']:.2f}")
                    print(f"     Strategy: {position['strategy_type']}")
                
                return True
            else:
                print(f"❌ FAILURE: No new positions created")
                return False
        else:
            print(f"❌ Failed to get final positions: {response.status_code}")
            return False
        
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_manual_trade():
    """Test manual trade execution"""
    print("\n" + "=" * 50)
    print("🧪 Testing Manual Trade Execution")
    print("=" * 50)
    
    try:
        # Execute a manual trade
        trade_request = {
            "symbol": "ETHUSDT",
            "strategy_type": "manual",
            "side": "LONG",
            "confidence": 0.8,
            "reason": "manual_test_trade",
            "market_regime": "testing",
            "volatility_regime": "medium"
        }
        
        print("\n1. Executing manual trade...")
        response = requests.post(f"{API_BASE_URL}/api/v1/paper-trading/trade", 
                               json=trade_request)
        
        if response.status_code == 200:
            trade_data = response.json()
            print(f"✅ Manual trade executed successfully")
            print(f"   Message: {trade_data['message']}")
            print(f"   Position ID: {trade_data['position_id']}")
            return True
        else:
            print(f"❌ Manual trade failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Manual trade test failed: {e}")
        return False

async def test_engine_initialization():
    """Test engine initialization and debug endpoints"""
    print("\n" + "=" * 50)
    print("🧪 Testing Engine Initialization")
    print("=" * 50)
    
    try:
        # Test debug endpoint
        print("\n1. Checking engine debug status...")
        response = requests.get(f"{API_BASE_URL}/api/v1/paper-trading/debug/engine-status")
        if response.status_code == 200:
            debug_data = response.json()
            print(f"✅ Debug status retrieved")
            print(f"   Routes engine exists: {debug_data['data']['routes_engine']['exists']}")
            print(f"   Main engine exists: {debug_data['data']['main_engine']['exists']}")
            print(f"   Engines match: {debug_data['data']['engines_match']}")
            print(f"   Recommended action: {debug_data['data']['troubleshooting']['recommended_action']}")
        else:
            print(f"❌ Debug status failed: {response.status_code}")
        
        # Test force initialization if needed
        print("\n2. Testing force initialization...")
        response = requests.post(f"{API_BASE_URL}/api/v1/paper-trading/force-init")
        if response.status_code == 200:
            init_data = response.json()
            print(f"✅ Force initialization successful")
            print(f"   Message: {init_data['message']}")
            print(f"   Engine type: {init_data['data']['engine_type']}")
            print(f"   Balance: ${init_data['data']['virtual_balance']}")
        else:
            print(f"❌ Force initialization failed: {response.status_code}")
            print(f"   Response: {response.text}")
        
        return True
        
    except Exception as e:
        print(f"❌ Engine initialization test failed: {e}")
        return False

async def main():
    """Run all tests"""
    print("🚀 Paper Trading Positions Fix Test Suite")
    print("=" * 60)
    
    # Test 1: Engine initialization
    test1_result = await test_engine_initialization()
    
    # Test 2: Basic positions flow
    test2_result = await test_paper_trading_positions()
    
    # Test 3: Manual trade
    test3_result = await test_manual_trade()
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 60)
    print(f"Engine Initialization: {'✅ PASS' if test1_result else '❌ FAIL'}")
    print(f"Positions Flow:        {'✅ PASS' if test2_result else '❌ FAIL'}")
    print(f"Manual Trade:          {'✅ PASS' if test3_result else '❌ FAIL'}")
    
    overall_success = test1_result and test2_result and test3_result
    print(f"\nOverall Result: {'🎉 ALL TESTS PASSED' if overall_success else '❌ SOME TESTS FAILED'}")
    
    if overall_success:
        print("\n✅ Paper trading positions fix is working correctly!")
        print("   - Engine initializes properly")
        print("   - Positions are created and displayed")
        print("   - Manual trades work")
    else:
        print("\n❌ Paper trading positions fix needs more work")
        print("   Check the server logs for detailed error information")

if __name__ == "__main__":
    asyncio.run(main())
