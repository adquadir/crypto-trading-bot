#!/usr/bin/env python3

import asyncio
import logging
import sys
import os

# Add the project root to Python path
sys.path.insert(0, '/home/ubuntu/crypto-trading-bot')

from src.api.trading_routes.paper_trading_routes import initialize_paper_trading_engine
from src.market_data.exchange_client import ExchangeClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_paper_trading_profit_scraping():
    """Test paper trading with profit scraping integration"""
    try:
        logger.info("🧪 Testing Paper Trading + Profit Scraping Integration")
        
        # Initialize exchange client
        exchange_client = ExchangeClient()
        
        # Initialize paper trading engine with profit scraping
        config = {
            'paper_trading': {
                'initial_balance': 10000.0,
                'enabled': True
            }
        }
        
        paper_engine = await initialize_paper_trading_engine(
            config=config,
            exchange_client=exchange_client,
            flow_trading_strategy='adaptive'
        )
        
        if not paper_engine:
            logger.error("❌ Failed to initialize paper trading engine")
            return False
        
        # Check if opportunity manager is connected
        if paper_engine.opportunity_manager:
            logger.info("✅ Opportunity Manager connected successfully")
        else:
            logger.warning("⚠️ Opportunity Manager not connected")
        
        # Check if profit scraping engine is connected
        if paper_engine.profit_scraping_engine:
            logger.info("✅ Profit Scraping Engine connected successfully")
        else:
            logger.warning("⚠️ Profit Scraping Engine not connected")
        
        # Start the paper trading engine
        await paper_engine.start()
        logger.info("✅ Paper Trading Engine started")
        
        # Wait a bit to see if signal processing works
        logger.info("⏳ Waiting 10 seconds to test signal processing...")
        await asyncio.sleep(10)
        
        # Check account status
        account_status = paper_engine.get_account_status()
        logger.info(f"📊 Account Status:")
        logger.info(f"   Balance: ${account_status['account']['balance']:.2f}")
        logger.info(f"   Active Positions: {account_status['account']['active_positions']}")
        logger.info(f"   Running: {account_status['is_running']}")
        
        # Stop the engine
        paper_engine.stop()
        logger.info("🛑 Paper Trading Engine stopped")
        
        logger.info("✅ Test completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_paper_trading_profit_scraping())
    if success:
        print("✅ Paper Trading + Profit Scraping integration test PASSED")
    else:
        print("❌ Paper Trading + Profit Scraping integration test FAILED")
        sys.exit(1)
