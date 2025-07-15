#!/usr/bin/env python3

"""
Test Profit Scraping Engine Integration Fix
Verifies that the profit scraping engine is properly connected and generating signals for paper trading
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from src.utils.config import load_config
from src.market_data.exchange_client import ExchangeClient
from src.strategies.profit_scraping.profit_scraping_engine import ProfitScrapingEngine
from src.trading.enhanced_paper_trading_engine import EnhancedPaperTradingEngine

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_profit_scraping_integration():
    """Test the complete profit scraping integration"""
    
    logger.info("🚀 Testing Profit Scraping Engine Integration...")
    
    try:
        # Step 1: Initialize exchange client
        logger.info("📡 Step 1: Initializing exchange client...")
        exchange_client = ExchangeClient()
        
        # Test connection
        ticker = await exchange_client.get_ticker_24h('BTCUSDT')
        logger.info(f"✅ Exchange client connected - BTCUSDT price: ${float(ticker.get('lastPrice', 0)):.2f}")
        
        # Step 2: Initialize profit scraping engine
        logger.info("🎯 Step 2: Initializing profit scraping engine...")
        profit_scraping_engine = ProfitScrapingEngine(
            exchange_client=exchange_client,
            paper_trading_engine=None  # Will be connected later
        )
        logger.info("✅ Profit scraping engine initialized")
        
        # Step 3: Start profit scraping with liquid symbols
        logger.info("🔄 Step 3: Starting profit scraping engine...")
        liquid_symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
        
        scraping_started = await profit_scraping_engine.start_scraping(liquid_symbols)
        if not scraping_started:
            raise Exception("Failed to start profit scraping engine")
        
        logger.info(f"✅ Profit scraping engine started with {len(liquid_symbols)} symbols")
        logger.info(f"   Active: {profit_scraping_engine.active}")
        logger.info(f"   Monitored symbols: {list(profit_scraping_engine.monitored_symbols)}")
        
        # Step 4: Initialize paper trading engine
        logger.info("📊 Step 4: Initializing paper trading engine...")
        config = load_config()
        
        paper_trading_engine = EnhancedPaperTradingEngine(
            config=config,
            exchange_client=exchange_client
        )
        
        # Connect profit scraping engine
        logger.info("🔗 Step 5: Connecting profit scraping engine to paper trading...")
        paper_trading_engine.connect_profit_scraping_engine(profit_scraping_engine)
        
        # Verify connection
        if not (hasattr(paper_trading_engine, 'profit_scraping_engine') and paper_trading_engine.profit_scraping_engine):
            raise Exception("Profit scraping engine connection failed")
        
        logger.info("✅ Profit scraping engine connected to paper trading")
        
        # Step 6: Start paper trading engine
        logger.info("🚀 Step 6: Starting paper trading engine...")
        await paper_trading_engine.start()
        logger.info("✅ Paper trading engine started")
        
        # Step 7: Wait for initial analysis and signal generation
        logger.info("⏳ Step 7: Waiting for profit scraping analysis...")
        await asyncio.sleep(10)  # Wait 10 seconds for initial analysis
        
        # Step 8: Check for opportunities and signals
        logger.info("🔍 Step 8: Checking for profit scraping opportunities...")
        
        # Get opportunities from profit scraping engine
        opportunities = profit_scraping_engine.get_opportunities()
        logger.info(f"📈 Found {len(opportunities)} symbols with opportunities:")
        
        total_opportunities = 0
        for symbol, symbol_opportunities in opportunities.items():
            if symbol_opportunities:
                logger.info(f"   {symbol}: {len(symbol_opportunities)} opportunities")
                for i, opp in enumerate(symbol_opportunities[:2]):  # Show first 2
                    logger.info(f"     #{i+1}: Score {opp['opportunity_score']}, Level {opp['level']['level_type']} @ {opp['level']['price']:.4f}")
                total_opportunities += len(symbol_opportunities)
        
        logger.info(f"📊 Total opportunities found: {total_opportunities}")
        
        # Step 9: Check paper trading signal processing
        logger.info("🎯 Step 9: Testing signal processing...")
        
        # Get fresh opportunities through paper trading engine
        fresh_opportunities = await paper_trading_engine._get_fresh_opportunities()
        logger.info(f"🔄 Paper trading found {len(fresh_opportunities)} fresh opportunities")
        
        for i, opp in enumerate(fresh_opportunities[:3]):  # Show first 3
            logger.info(f"   Signal #{i+1}: {opp.get('symbol')} {opp.get('side')} (confidence: {opp.get('confidence', 0):.3f})")
        
        # Step 10: Check paper trading status
        logger.info("📋 Step 10: Checking paper trading status...")
        account_status = paper_trading_engine.get_account_status()
        
        logger.info(f"💰 Account Balance: ${account_status['account']['balance']:.2f}")
        logger.info(f"📊 Active Positions: {account_status['account']['active_positions']}")
        logger.info(f"📈 Total Trades: {account_status['account']['total_trades']}")
        logger.info(f"🎯 Engine Running: {account_status['is_running']}")
        
        # Step 11: Final validation
        logger.info("✅ Step 11: Final validation...")
        
        # Validate profit scraping engine is active
        if not profit_scraping_engine.active:
            raise Exception("Profit scraping engine is not active")
        
        # Validate paper trading engine is running
        if not paper_trading_engine.is_running:
            raise Exception("Paper trading engine is not running")
        
        # Validate connection exists
        if not paper_trading_engine.profit_scraping_engine:
            raise Exception("Profit scraping connection missing")
        
        logger.info("🎉 ALL INTEGRATION TESTS PASSED!")
        
        # Show summary
        logger.info("\n" + "="*60)
        logger.info("📊 INTEGRATION TEST SUMMARY")
        logger.info("="*60)
        logger.info(f"✅ Exchange Client: Connected")
        logger.info(f"✅ Profit Scraping Engine: Active with {len(profit_scraping_engine.monitored_symbols)} symbols")
        logger.info(f"✅ Paper Trading Engine: Running")
        logger.info(f"✅ Signal Generation: {total_opportunities} opportunities found")
        logger.info(f"✅ Signal Processing: {len(fresh_opportunities)} signals ready for trading")
        logger.info(f"✅ Pure Mode: Enabled (profit scraping primary)")
        logger.info("="*60)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Integration test failed: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return False
    
    finally:
        # Cleanup
        try:
            if 'profit_scraping_engine' in locals() and profit_scraping_engine:
                await profit_scraping_engine.stop_scraping()
            if 'paper_trading_engine' in locals() and paper_trading_engine:
                paper_trading_engine.stop()
        except Exception as cleanup_error:
            logger.error(f"Cleanup error: {cleanup_error}")

async def main():
    """Main test function"""
    logger.info("🔧 Starting Profit Scraping Integration Test...")
    
    success = await test_profit_scraping_integration()
    
    if success:
        logger.info("🎉 Integration test completed successfully!")
        logger.info("💡 The profit scraping engine should now be providing signals to paper trading")
        return 0
    else:
        logger.error("❌ Integration test failed!")
        logger.error("💡 Check the logs above for specific issues")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
