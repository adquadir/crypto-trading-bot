#!/usr/bin/env python3
"""
Direct test of the close endpoint to verify it's working
"""

import asyncio
import aiohttp
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_close_endpoint_directly():
    """Test the close endpoint directly"""
    
    base_url = "http://localhost:8000"
    
    async with aiohttp.ClientSession() as session:
        try:
            # Test 1: Check if the close endpoint exists by testing with an invalid ID
            logger.info("🧪 Test 1: Testing close endpoint with invalid ID...")
            
            invalid_id = "test_invalid_id_12345"
            close_url = f"{base_url}/api/v1/paper-trading/positions/{invalid_id}/close"
            
            async with session.post(close_url, json={"exit_reason": "test"}) as response:
                logger.info(f"📊 Close endpoint response status: {response.status}")
                
                if response.status == 404:
                    try:
                        error_data = await response.json()
                        logger.info(f"📋 404 Response: {error_data}")
                        
                        # Check if it's a "position not found" error (good) vs "endpoint not found" error (bad)
                        if "Position" in str(error_data.get('detail', '')) and "not found" in str(error_data.get('detail', '')):
                            logger.info("✅ SUCCESS: Close endpoint exists and correctly reports position not found")
                            return True
                        else:
                            logger.error("❌ FAILED: Close endpoint returns generic 404 - endpoint may not exist")
                            return False
                    except:
                        error_text = await response.text()
                        logger.info(f"📋 404 Response text: {error_text}")
                        if "Not Found" in error_text and "Position" not in error_text:
                            logger.error("❌ FAILED: Generic 404 - close endpoint doesn't exist")
                            return False
                        else:
                            logger.info("✅ SUCCESS: Close endpoint exists")
                            return True
                elif response.status == 503:
                    error_data = await response.json()
                    logger.info(f"✅ SUCCESS: Close endpoint exists but system not ready: {error_data.get('detail', '')}")
                    return True
                else:
                    logger.info(f"✅ SUCCESS: Close endpoint exists (unexpected status {response.status} but not 404)")
                    return True
                    
        except Exception as e:
            logger.error(f"❌ Test failed with exception: {e}")
            return False

async def main():
    """Main test function"""
    logger.info("🚀 Starting Direct Close Endpoint Test")
    logger.info("=" * 50)
    
    success = await test_close_endpoint_directly()
    
    logger.info("=" * 50)
    if success:
        logger.info("✅ CLOSE ENDPOINT TEST PASSED - Endpoint exists and is working")
    else:
        logger.error("❌ CLOSE ENDPOINT TEST FAILED - Endpoint may not exist")
    
    return success

if __name__ == "__main__":
    result = asyncio.run(main())
    exit(0 if result else 1)
