#!/usr/bin/env python3
"""
Test script to verify the close button backend API issue
This will help identify exactly why the close button returns "not found"
"""

import asyncio
import aiohttp
import json
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_close_button_backend():
    """Test the close button backend API to identify the exact issue"""
    
    base_url = "http://localhost:8000"
    
    async with aiohttp.ClientSession() as session:
        try:
            # Step 1: Check if paper trading is running
            logger.info("🔍 Step 1: Checking paper trading status...")
            async with session.get(f"{base_url}/api/v1/paper-trading/status") as response:
                if response.status == 200:
                    status_data = await response.json()
                    logger.info(f"✅ Paper trading status: {status_data.get('data', {}).get('enabled', False)}")
                    logger.info(f"📊 Active positions: {status_data.get('data', {}).get('active_positions', 0)}")
                else:
                    logger.error(f"❌ Failed to get status: {response.status}")
                    return
            
            # Step 2: Get current positions to see their actual IDs
            logger.info("🔍 Step 2: Getting current positions...")
            async with session.get(f"{base_url}/api/v1/paper-trading/positions") as response:
                if response.status == 200:
                    positions_data = await response.json()
                    positions = positions_data if isinstance(positions_data, list) else positions_data.get('data', [])
                    
                    logger.info(f"📊 Found {len(positions)} positions")
                    
                    if not positions:
                        logger.warning("⚠️ No positions found - need to create a test position first")
                        
                        # Create a test position
                        logger.info("🔄 Creating test position...")
                        test_trade = {
                            "symbol": "BTCUSDT",
                            "strategy_type": "scalping",
                            "side": "LONG",
                            "confidence": 0.8,
                            "reason": "test_close_button",
                            "market_regime": "trending",
                            "volatility_regime": "medium"
                        }
                        
                        async with session.post(f"{base_url}/api/v1/paper-trading/trade", json=test_trade) as trade_response:
                            if trade_response.status == 200:
                                trade_result = await trade_response.json()
                                logger.info(f"✅ Test position created: {trade_result.get('position_id')}")
                                
                                # Get positions again
                                async with session.get(f"{base_url}/api/v1/paper-trading/positions") as pos_response:
                                    if pos_response.status == 200:
                                        positions_data = await pos_response.json()
                                        positions = positions_data if isinstance(positions_data, list) else positions_data.get('data', [])
                            else:
                                logger.error(f"❌ Failed to create test position: {trade_response.status}")
                                return
                    
                    # Analyze position ID formats
                    for i, position in enumerate(positions):
                        logger.info(f"📋 Position {i+1}:")
                        logger.info(f"   Raw position data: {json.dumps(position, indent=2)}")
                        
                        # Check all possible ID fields
                        possible_ids = []
                        for id_field in ['id', 'position_id', 'trade_id', '_id', 'uid']:
                            if id_field in position:
                                possible_ids.append(f"{id_field}: '{position[id_field]}'")
                        
                        logger.info(f"   Possible ID fields: {possible_ids}")
                        
                        # Test the close endpoint with each possible ID
                        for id_field in ['id', 'position_id', 'trade_id', '_id', 'uid']:
                            if id_field in position:
                                position_id = position[id_field]
                                logger.info(f"🧪 Testing close with {id_field}='{position_id}'...")
                                
                                close_url = f"{base_url}/api/v1/paper-trading/positions/{position_id}/close"
                                close_data = {"exit_reason": "test_close"}
                                
                                async with session.post(close_url, json=close_data) as close_response:
                                    logger.info(f"   Close response status: {close_response.status}")
                                    
                                    if close_response.status == 200:
                                        close_result = await close_response.json()
                                        logger.info(f"   ✅ SUCCESS with {id_field}: {close_result.get('message', 'No message')}")
                                        return  # Success, we found the right field
                                    else:
                                        try:
                                            error_data = await close_response.json()
                                            logger.info(f"   ❌ FAILED with {id_field}: {error_data.get('detail', 'No error detail')}")
                                        except:
                                            error_text = await close_response.text()
                                            logger.info(f"   ❌ FAILED with {id_field}: {error_text}")
                        
                        # If we get here, none of the standard ID fields worked
                        logger.error(f"❌ CRITICAL: No working ID field found for position!")
                        
                        # Try composite ID as fallback
                        if 'symbol' in position and 'entry_time' in position:
                            composite_id = f"{position['symbol']}::{position['entry_time']}"
                            logger.info(f"🧪 Testing close with composite ID: '{composite_id}'...")
                            
                            close_url = f"{base_url}/api/v1/paper-trading/positions/{composite_id}/close"
                            close_data = {"exit_reason": "test_close"}
                            
                            async with session.post(close_url, json=close_data) as close_response:
                                logger.info(f"   Composite ID response status: {close_response.status}")
                                
                                if close_response.status == 200:
                                    close_result = await close_response.json()
                                    logger.info(f"   ✅ SUCCESS with composite ID: {close_result.get('message', 'No message')}")
                                else:
                                    try:
                                        error_data = await close_response.json()
                                        logger.info(f"   ❌ FAILED with composite ID: {error_data.get('detail', 'No error detail')}")
                                    except:
                                        error_text = await close_response.text()
                                        logger.info(f"   ❌ FAILED with composite ID: {error_text}")
                        
                        break  # Only test the first position
                        
                else:
                    logger.error(f"❌ Failed to get positions: {response.status}")
                    return
            
            # Step 3: Test the API route registration
            logger.info("🔍 Step 3: Testing API route registration...")
            
            # Test with a clearly invalid position ID to see the error format
            invalid_id = "invalid_test_id_12345"
            close_url = f"{base_url}/api/v1/paper-trading/positions/{invalid_id}/close"
            close_data = {"exit_reason": "test_invalid"}
            
            async with session.post(close_url, json=close_data) as response:
                logger.info(f"Invalid ID test response status: {response.status}")
                
                if response.status == 404:
                    try:
                        error_data = await response.json()
                        logger.info(f"404 error format: {error_data}")
                    except:
                        error_text = await response.text()
                        logger.info(f"404 error text: {error_text}")
                elif response.status == 422:
                    logger.info("422 = Route exists but validation failed")
                else:
                    logger.info(f"Unexpected status for invalid ID: {response.status}")
            
        except Exception as e:
            logger.error(f"❌ Test failed with exception: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")

async def main():
    """Main test function"""
    logger.info("🚀 Starting Close Button Backend Verification Test")
    logger.info("=" * 60)
    
    await test_close_button_backend()
    
    logger.info("=" * 60)
    logger.info("✅ Close Button Backend Verification Test Complete")

if __name__ == "__main__":
    asyncio.run(main())
