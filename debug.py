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
    
    # Initialize components with explicit parameters
    client = ExchangeClient(
        api_key=os.getenv('BINANCE_API_KEY'),
        api_secret=os.getenv('BINANCE_API_SECRET'),
        testnet=True  # Use testnet for debugging
    )
    
    # Initialize processor with window sizes that match your strategies
    processor = MarketDataProcessor(window_sizes=[20, 50, 200])
    
    try:
        logger.info("=== Starting Comprehensive Connection Test ===")
        
        # 1. Test API connection and keys
        logger.info("1. Testing API connection...")
        await client.initialize()
        
        # 2. Test proxy connection
        logger.info("2. Testing proxy connection...")
        await client.test_proxy_connection()
        
        # 3. Test data fetching with different timeframes
        symbol = "BTCUSDT"
        test_cases = [
            ("1m", 200),  # Enough for largest window size
            ("5m", 100),
            ("15m", 50)
        ]
        
        for interval, limit in test_cases:
            logger.info(f"3. Testing {interval} data (limit={limit})...")
            data = await client.get_historical_data(symbol, interval, limit)
            logger.info(f"Received {len(data) if data else 0} data points")
            
            if not data:
                logger.error(f"No data received for {interval} {symbol}")
                continue
                
            # 4. Test data processing
            logger.info("4. Testing data processing...")
            success = processor.update_ohlcv(symbol, data)
            logger.info(f"Data processing: {'SUCCESS' if success else 'FAILED'}")
            
            if not success:
                continue
                
            # 5. Test indicator calculation
            logger.info("5. Testing indicator calculation...")
            market_state = processor.get_market_state(symbol)
            
            if not market_state or not market_state.get('indicators'):
                logger.error("No indicators calculated - check window sizes")
            else:
                logger.info(f"Calculated {len(market_state['indicators'])} indicators")
                logger.debug(f"Sample indicators: { {k: v for k, v in list(market_state['indicators'].items())[:5]} }")
                
            # 6. Test raw data access
            raw_data = processor.get_raw_data(symbol)
            logger.info(f"6. Data stored: {len(raw_data) if raw_data is not None else 0} records")
            
    except Exception as e:
        logger.error(f"Test failed: {str(e)}", exc_info=True)
    finally:
        await client.close()
        logger.info("=== Test Complete ===")

if __name__ == "__main__":
    asyncio.run(test_connection())