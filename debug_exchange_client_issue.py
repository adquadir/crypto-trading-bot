#!/usr/bin/env python3

"""
Debug Exchange Client Issue
Test the exchange client initialization to see what's failing
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_exchange_client():
    """Test exchange client initialization"""
    try:
        logger.info("🔍 Testing exchange client initialization...")
        
        # Test config loading
        logger.info("📋 Step 1: Loading configuration...")
        from src.utils.config import load_config
        config = load_config()
        logger.info("✅ Configuration loaded successfully")
        
        # Test exchange client import
        logger.info("📦 Step 2: Importing exchange client...")
        from src.market_data.exchange_client import ExchangeClient
        logger.info("✅ Exchange client imported successfully")
        
        # Test exchange client creation
        logger.info("🏗️ Step 3: Creating exchange client instance...")
        exchange_client = ExchangeClient()
        logger.info("✅ Exchange client instance created successfully")
        
        # Test connection
        logger.info("🔗 Step 4: Testing exchange client connection...")
        
        # Check what methods are available
        logger.info(f"Available methods: {[method for method in dir(exchange_client) if not method.startswith('_')]}")
        
        if hasattr(exchange_client, 'get_ticker_24h'):
            logger.info("Using get_ticker_24h method...")
            ticker = await exchange_client.get_ticker_24h('BTCUSDT')
            logger.info(f"✅ Connection test successful: {ticker}")
        elif hasattr(exchange_client, 'get_ticker'):
            logger.info("Using get_ticker method...")
            ticker = await exchange_client.get_ticker('BTCUSDT')
            logger.info(f"✅ Connection test successful: {ticker}")
        elif hasattr(exchange_client, 'fetch_ticker'):
            logger.info("Using fetch_ticker method...")
            ticker = await exchange_client.fetch_ticker('BTC/USDT')
            logger.info(f"✅ Connection test successful: {ticker}")
        else:
            logger.error("❌ No suitable ticker method found")
            return False
        
        logger.info("🎉 Exchange client is working correctly!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Exchange client test failed: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return False

async def test_basic_imports():
    """Test basic imports that might be failing"""
    try:
        logger.info("🔍 Testing basic imports...")
        
        # Test strategy manager
        logger.info("📦 Testing strategy manager import...")
        from src.strategy.strategy_manager import StrategyManager
        logger.info("✅ Strategy manager imported successfully")
        
        # Test risk manager
        logger.info("📦 Testing risk manager import...")
        from src.risk.risk_manager import RiskManager
        logger.info("✅ Risk manager imported successfully")
        
        # Test signal tracker
        logger.info("📦 Testing signal tracker import...")
        from src.signals.enhanced_signal_tracker import EnhancedSignalTracker
        logger.info("✅ Signal tracker imported successfully")
        
        # Test opportunity manager
        logger.info("📦 Testing opportunity manager import...")
        from src.opportunity.opportunity_manager import OpportunityManager
        logger.info("✅ Opportunity manager imported successfully")
        
        # Test profit scraping engine
        logger.info("📦 Testing profit scraping engine import...")
        from src.strategies.profit_scraping.profit_scraping_engine import ProfitScrapingEngine
        logger.info("✅ Profit scraping engine imported successfully")
        
        # Test paper trading engine
        logger.info("📦 Testing paper trading engine import...")
        from src.trading.enhanced_paper_trading_engine import EnhancedPaperTradingEngine
        logger.info("✅ Paper trading engine imported successfully")
        
        logger.info("🎉 All imports are working correctly!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Import test failed: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return False

async def main():
    """Main test function"""
    logger.info("🔧 Starting Exchange Client Debug Test...")
    logger.info("="*60)
    
    # Test basic imports first
    if not await test_basic_imports():
        logger.error("❌ Basic imports failed - cannot proceed")
        return 1
    
    logger.info("\n" + "="*60)
    
    # Test exchange client
    if not await test_exchange_client():
        logger.error("❌ Exchange client test failed")
        return 1
    
    logger.info("\n" + "="*60)
    logger.info("🎉 All tests passed! The issue might be elsewhere.")
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
