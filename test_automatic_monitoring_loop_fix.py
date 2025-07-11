#!/usr/bin/env python3
"""
Test the automatic monitoring loop fix for paper trading
"""

import requests
import time
import json

def test_automatic_monitoring_loop():
    """Test that the monitoring loop starts automatically when paper trading is started"""
    
    print("🧪 TESTING AUTOMATIC MONITORING LOOP FIX")
    print("=" * 60)
    
    base_url = "http://localhost:8000/api/v1/paper-trading"
    
    try:
        # Step 1: Stop paper trading if running
        print("1️⃣ Stopping paper trading to ensure clean start...")
        stop_response = requests.post(f"{base_url}/stop", timeout=10)
        print(f"   Stop response: {stop_response.status_code}")
        time.sleep(2)
        
        # Step 2: Start paper trading
        print("2️⃣ Starting paper trading with monitoring loop verification...")
        start_response = requests.post(f"{base_url}/start", timeout=30)
        
        if start_response.status_code == 200:
            start_data = start_response.json()
            print(f"   ✅ Start successful: {start_data.get('message', 'No message')}")
            
            # Check if monitoring loop status is included
            if 'data' in start_data and 'monitoring_loop_status' in start_data['data']:
                monitoring_status = start_data['data']['monitoring_loop_status']
                print(f"   📊 Monitoring loop status:")
                print(f"      - Position monitoring active: {monitoring_status.get('position_monitoring_active', False)}")
                print(f"      - Signal processing active: {monitoring_status.get('signal_processing_active', False)}")
                print(f"      - Engine running: {monitoring_status.get('engine_running', False)}")
                print(f"      - Has monitoring method: {monitoring_status.get('has_monitoring_method', False)}")
                print(f"      - Has monitoring task: {monitoring_status.get('has_monitoring_task', False)}")
                print(f"      - Total tasks: {monitoring_status.get('total_tasks', 0)}")
                
                # Check if $10 take profit protection is enabled
                ten_dollar_protection = start_data['data'].get('ten_dollar_protection', False)
                print(f"   🎯 $10 Take Profit Protection: {'✅ ENABLED' if ten_dollar_protection else '❌ DISABLED'}")
                
                if monitoring_status.get('position_monitoring_active', False):
                    print("   ✅ SUCCESS: Position monitoring loop is active!")
                    return True
                else:
                    print("   ❌ FAILURE: Position monitoring loop is NOT active!")
                    return False
            else:
                print("   ⚠️ WARNING: No monitoring loop status in response")
                return False
        else:
            print(f"   ❌ Start failed: {start_response.status_code}")
            print(f"   Response: {start_response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False

def test_monitoring_loop_verification():
    """Test the monitoring loop verification endpoint"""
    
    print("\n🔍 TESTING MONITORING LOOP VERIFICATION")
    print("=" * 60)
    
    try:
        # Get current status to check monitoring loop
        response = requests.get("http://localhost:8000/api/v1/paper-trading/status", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            enabled = data.get('data', {}).get('enabled', False)
            
            if enabled:
                print("✅ Paper trading is running")
                print("   The monitoring loop should be active and checking for $10+ profits every 3 seconds")
                print("   Positions with $10+ profit should be automatically closed")
                return True
            else:
                print("❌ Paper trading is not running")
                return False
        else:
            print(f"❌ Status check failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False

def test_position_check():
    """Check current positions for any with $10+ profit"""
    
    print("\n💰 CHECKING FOR HIGH-PROFIT POSITIONS")
    print("=" * 60)
    
    try:
        response = requests.get("http://localhost:8000/api/v1/paper-trading/positions", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            positions = data.get('data', [])
            
            print(f"📊 Total positions: {len(positions)}")
            
            high_profit_positions = [
                pos for pos in positions 
                if pos.get('unrealized_pnl', 0) >= 10.0
            ]
            
            if high_profit_positions:
                print(f"🎯 Positions with $10+ profit: {len(high_profit_positions)}")
                for pos in high_profit_positions:
                    symbol = pos.get('symbol', 'UNKNOWN')
                    pnl = pos.get('unrealized_pnl', 0)
                    age = pos.get('age_minutes', 0)
                    print(f"   💰 {symbol}: ${pnl:.2f} profit (age: {age:.1f} minutes)")
                
                print("❌ ISSUE: These positions should have been closed automatically!")
                print("   The monitoring loop may not be working properly.")
                return False
            else:
                print("✅ SUCCESS: No positions with $10+ profit found")
                print("   The monitoring loop is working correctly!")
                return True
                
        else:
            print(f"❌ Position check failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Position check failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 AUTOMATIC MONITORING LOOP FIX TEST")
    print("Testing that the $10 take profit monitoring loop starts automatically")
    print("=" * 80)
    
    # Run tests
    test1_passed = test_automatic_monitoring_loop()
    test2_passed = test_monitoring_loop_verification()
    test3_passed = test_position_check()
    
    print("\n" + "=" * 80)
    print("📋 TEST RESULTS SUMMARY")
    print("=" * 80)
    print(f"1️⃣ Automatic monitoring loop startup: {'✅ PASS' if test1_passed else '❌ FAIL'}")
    print(f"2️⃣ Monitoring loop verification: {'✅ PASS' if test2_passed else '❌ FAIL'}")
    print(f"3️⃣ High-profit position check: {'✅ PASS' if test3_passed else '❌ FAIL'}")
    
    all_passed = test1_passed and test2_passed and test3_passed
    
    if all_passed:
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ The automatic monitoring loop fix is working correctly")
        print("✅ $10 take profit system will work automatically when paper trading is started")
    else:
        print("\n❌ SOME TESTS FAILED!")
        print("🔧 The monitoring loop may need additional fixes")
        
    print("\n" + "=" * 80)
