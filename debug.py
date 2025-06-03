# File: debug.py
import asyncio
import logging
import os
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
    load_dotenv()
    
    client = ExchangeClient(
        api_key=os.getenv('BINANCE_API_KEY'),
        api_secret=os.getenv('BINANCE_API_SECRET')
    )
    
    processor = MarketDataProcessor()
    
    try:
        logger.info("=== Starting Connection Test ===")
        
        # Test initialization
        await client.initialize()
        await client.test_proxy_connection()
        
        # Test data fetching
        symbol = "BTCUSDT"
        data = await client.get_historical_data(symbol, "1m", 200)
        logger.info(f"Received {len(data) if data else 0} data points")
        
        if data:
            # Test processing
            success = processor.update_ohlcv(symbol, data)
            logger.info(f"Data processing: {'SUCCESS' if success else 'FAILED'}")
            
            if success:
                market_state = processor.get_market_state(symbol)
                logger.info(f"Market state: {market_state}")
        
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
    finally:
        await client.close()
        logger.info("=== Test Complete ===")

if __name__ == "__main__":
    asyncio.run(test_connection())