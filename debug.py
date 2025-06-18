"""Debug script for testing exchange connection and data processing."""

import asyncio
import logging
import os
from typing import Dict, List, Optional
import aiohttp

from dotenv import load_dotenv

from src.market_data.exchange_client import ExchangeClient
from src.market_data.processor import MarketDataProcessor

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_connection():
    """Test exchange connection and data processing."""
    try:
        logger.info("=== Starting Connection Test ===")
        load_dotenv()
        
        # Get proxy configuration
        proxy_host = os.getenv('PROXY_HOST')
        proxy_port = os.getenv('PROXY_PORT')
        proxy_user = os.getenv('PROXY_USER')
        proxy_pass = os.getenv('PROXY_PASS')
        
        # Format proxy URL
        proxy_url = None
        if proxy_host and proxy_port:
            proxy_url = f"http://{proxy_host}:{proxy_port}"
            if proxy_user and proxy_pass:
                proxy_url = f"http://{proxy_user}:{proxy_pass}@{proxy_host}:{proxy_port}"
            logger.info(f"Using proxy: {proxy_url}")
        
        # Test HTTP connection
        async with aiohttp.ClientSession() as session:
            # Test futures API
            futures_url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
            try:
                async with session.get(futures_url, proxy=proxy_url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        symbols = [s['symbol'] for s in data['symbols'] 
                                 if s['contractType'] == 'PERPETUAL' and s['status'] == 'TRADING']
                        logger.info(f"Futures API test successful. Retrieved {len(symbols)} symbols")
                    else:
                        error_text = await response.text()
                        logger.error(f"Futures API test failed: {response.status} {error_text}")
            except Exception as e:
                logger.error(f"Futures API test failed: {e}")
            
            # Test spot API
            spot_url = "https://api.binance.com/api/v3/exchangeInfo"
            try:
                async with session.get(spot_url, proxy=proxy_url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        symbols = [s['symbol'] for s in data['symbols'] if s['status'] == 'TRADING']
                        logger.info(f"Spot API test successful. Retrieved {len(symbols)} symbols")
                    else:
                        error_text = await response.text()
                        logger.error(f"Spot API test failed: {response.status} {error_text}")
            except Exception as e:
                logger.error(f"Spot API test failed: {e}")
        
        logger.info("=== Test Complete ===")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(test_connection())