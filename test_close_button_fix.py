#!/usr/bin/env python3
"""
Test script to verify the close button fix for paper trading positions
"""

import asyncio
import requests
import json
import time
from datetime import datetime

# Configuration
API_BASE_URL = "http://localhost:8000"
PAPER_TRADING_API = f"{API_BASE_URL}/api/v1/paper-trading"

def log_message(message):
    """Log message with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")

def test_api_endpoint(endpoint, method="GET", data=None):
    """Test an API endpoint and return response"""
    try:
        url = f"{PAPER_TRADING_API}{endpoint}"
        log_message(f"Testing {method} {url}")
        
        if method == "GET":
            response = requests.get(url)
        elif method == "POST":
            response = requests.post(url, json=data)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        log_message(f"Response: {response.status_code}")
        
        if response.status_code == 200:
            return response.json()
        else:
            log_message(f"Error: {response.text}")
            return None
            
    except Exception as e:
        log_message(f"Exception: {e}")
        return None

async def main():
    """Main test function"""
    log_message("🧪 Starting Close Button Fix Test")
    
    # Step 1: Check paper trading status
    log_message("📊 Step 1: Checking paper trading status")
    status = test_api_endpoint("/status")
    if not status:
        log_message("❌ Failed to get status")
        return
    
    log_message(f"✅ Status: Engine running = {status['data']['enabled']}")
    
    # Step 2: Start paper trading if not running
    if not status['data']['enabled']:
        log_message("🚀 Step 2: Starting paper trading")
        start_result = test_api_endpoint("/start", "POST")
        if not start_result:
            log_message("❌ Failed to start paper trading")
            return
        log_message("✅ Paper trading started")
        
        # Wait a moment for initialization
        time.sleep(2)
    else:
        log_message("✅ Paper trading already running")
    
    # Step 3: Get current positions
    log_message("📋 Step 3: Getting current positions")
    positions = test_api_endpoint("/positions")
    if not positions:
        log_message("❌ Failed to get positions")
        return
    
    current_positions = positions['data']
    log_message(f"✅ Found {len(current_positions)} active positions")
    
    # Step 4: Create a test position if none exist
    if len(current_positions) == 0:
        log_message("🎯 Step 4: Creating test position")
        trade_data = {
            "symbol": "BTCUSDT",
            "strategy_type": "scalping",
            "side": "LONG",
            "confidence": 0.75,
            "reason": "close_button_test",
            "market_regime": "test",
            "volatility_regime": "medium"
        }
        
        trade_result = test_api_endpoint("/trade", "POST", trade_data)
        if not trade_result:
            log_message("❌ Failed to create test position")
            return
        
        log_message(f"✅ Created test position: {trade_result['position_id']}")
        
        # Wait a moment for position to be established
        time.sleep(1)
        
        # Get updated positions
        positions = test_api_endpoint("/positions")
        if not positions:
            log_message("❌ Failed to get updated positions")
            return
        current_positions = positions['data']
    
    # Step 5: Test closing a position
    if len(current_positions) > 0:
        test_position = current_positions[0]
        position_id = test_position['id']
        
        log_message(f"🔄 Step 5: Testing close button for position {position_id}")
        log_message(f"   Position: {test_position['symbol']} {test_position['side']} @ {test_position['entry_price']}")
        log_message(f"   Current P&L: ${test_position['unrealized_pnl']:.2f}")
        
        # Test the close endpoint
        close_result = test_api_endpoint(f"/positions/{position_id}/close", "POST")
        
        if close_result:
            log_message("✅ CLOSE BUTTON TEST PASSED!")
            log_message(f"   Trade closed successfully")
            log_message(f"   Final P&L: ${close_result['trade']['pnl']:.2f}")
            log_message(f"   Duration: {close_result['trade']['duration_minutes']} minutes")
            log_message(f"   Exit reason: {close_result['trade']['exit_reason']}")
            
            # Verify position was removed
            time.sleep(1)
            updated_positions = test_api_endpoint("/positions")
            if updated_positions:
                remaining_positions = updated_positions['data']
                position_removed = not any(p['id'] == position_id for p in remaining_positions)
                
                if position_removed:
                    log_message("✅ Position successfully removed from active positions")
                else:
                    log_message("⚠️ Position still appears in active positions")
            
        else:
            log_message("❌ CLOSE BUTTON TEST FAILED!")
            log_message("   Close endpoint returned error")
    else:
        log_message("⚠️ No positions available to test close functionality")
    
    # Step 6: Test error handling
    log_message("🧪 Step 6: Testing error handling")
    
    # Test closing non-existent position
    fake_position_id = "fake-position-id-12345"
    error_result = test_api_endpoint(f"/positions/{fake_position_id}/close", "POST")
    
    if error_result is None:
        log_message("✅ Error handling test passed - non-existent position properly rejected")
    else:
        log_message("⚠️ Error handling test - unexpected success for fake position")
    
    # Step 7: Final status check
    log_message("📊 Step 7: Final status check")
    final_status = test_api_endpoint("/status")
    if final_status:
        log_message(f"✅ Final balance: ${final_status['data']['virtual_balance']:.2f}")
        log_message(f"✅ Total trades: {final_status['data']['completed_trades']}")
        log_message(f"✅ Active positions: {final_status['data']['active_positions']}")
    
    log_message("🎉 Close Button Fix Test Completed!")

if __name__ == "__main__":
    asyncio.run(main())
