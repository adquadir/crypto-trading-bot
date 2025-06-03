# File: debug.py (updated version)
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
    
    # Initialize processor with explicit window size
    processor = MarketDataProcessor(window_sizes=[20, 50, 200])  # Match your strategy needs
    
    try:
        logger.info("=== Starting Connection Test ===")
        
        await client.initialize()
        await client.test_proxy_connection()
        
        symbol = "BTCUSDT"
        # Fetch enough data for the largest window (200)
        data = await client.get_historical_data(symbol, "1m", 200)  # Changed from 5 to 200
        logger.info(f"Received {len(data) if data else 0} data points")
        
        if data:
            success = processor.update_ohlcv(symbol, data)
            logger.info(f"Data processing: {'SUCCESS' if success else 'FAILED'}")
            
            if success:
                market_state = processor.get_market_state(symbol)
                if market_state.get('indicators'):
                    logger.info(f"Calculated {len(market_state['indicators'])} indicators")
                    # Log first 3 indicators for verification
                    logger.debug(f"Sample indicators: {dict(list(market_state['indicators'].items())[:3]}")
                else:
                    logger.warning("No indicators calculated - check data sufficiency")
        
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
    finally:
        await client.close()
        logger.info("=== Test Complete ===")

if __name__ == "__main__":
    asyncio.run(test_connection())