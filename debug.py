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
    
    # Initialize exchange client with config
    exchange_config = {
        'api_key': os.getenv('BINANCE_API_KEY'),
        'api_secret': os.getenv('BINANCE_API_SECRET'),
        'base_url': 'https://api.binance.com',
        'ws_url': 'wss://stream.binance.com:9443/ws/stream',
        'testnet': os.getenv('USE_TESTNET', 'False').lower() == 'true',
        'proxy': {
            'host': os.getenv('PROXY_HOST'),
            'port': os.getenv('PROXY_PORT'),
            'username': os.getenv('PROXY_USER'),
            'password': os.getenv('PROXY_PASS')
        },
        'proxy_ports': os.getenv('PROXY_LIST', '10001,10002,10003').split(','),
        'failover_ports': os.getenv('FAILOVER_PORTS', '10001,10002,10003').split(','),
        'symbols': os.getenv('TRADING_SYMBOLS', 'BTCUSDT').split(',')
    }
    exchange_client = ExchangeClient(config=exchange_config)
    
    processor = MarketDataProcessor()
    
    try:
        logger.info("=== Starting Connection Test ===")
        
        # Test initialization
        await exchange_client.initialize()
        await exchange_client.test_proxy_connection()
        
        # Test data fetching
        symbol = "BTCUSDT"
        data = await exchange_client.get_historical_data(symbol, "1m", 200)
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
        await exchange_client.close()
        logger.info("=== Test Complete ===")

if __name__ == "__main__":
    asyncio.run(test_connection())