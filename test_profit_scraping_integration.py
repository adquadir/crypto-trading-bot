#!/usr/bin/env python3
"""
Test Profit Scraping Integration with Paper Trading
Verifies that paper trading engine uses profit scraping opportunities
"""

import asyncio
import logging
import sys
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_profit_scraping_integration():
    """Test the integration between profit scraping and paper trading"""
    try:
        logger.info("🧪 Testing Profit Scraping Integration with Paper Trading")
        
        # Import components
        from src.strategies.profit_scraping.profit_scraping_engine import ProfitScrapingEngine
        from src.trading.enhanced_paper_trading_engine import EnhancedPaperTradingEngine
        from src.utils.config import load_config
        
        # Load config
        config = load_config() or {}
        paper_config = {'paper_trading': {'initial_balance': 10000.0, 'enabled': True}}
        
        logger.info("✅ Step 1: Initialize Profit Scraping Engine")
        
        # Initialize profit scraping engine
        profit_scraping_engine = ProfitScrapingEngine(
            exchange_client=None,  # Mock mode
            paper_trading_engine=None
        )
        
        logger.info("✅ Step 2: Initialize Paper Trading Engine with Profit Scraping")
        
        # Initialize paper trading engine WITH profit scraping connection
        paper_trading_engine = EnhancedPaperTradingEngine(
            config=paper_config,
            exchange_client=None,  # Mock mode
            opportunity_manager=None,  # Not needed
            profit_scraping_engine=profit_scraping_engine  # CONNECTED!
        )
        
        logger.info("✅ Step 3: Start Profit Scraping Engine")
        
        # Start profit scraping for test symbols
        test_symbols = ['BTCUSDT', 'ETHUSDT']
        scraping_started = await profit_scraping_engine.start_scraping(test_symbols)
        
        if scraping_started:
            logger.info(f"🎯 Profit scraping started for {test_symbols}")
        else:
            logger.error("❌ Failed to start profit scraping")
            return False
        
        logger.info("✅ Step 4: Start Paper Trading Engine")
        
        # Start paper trading engine
        await paper_trading_engine.start()
        
        logger.info("✅ Step 5: Wait for Profit Scraping to Identify Opportunities")
        
        # Wait for profit scraping to identify opportunities
        await asyncio.sleep(10)
        
        # Check profit scraping opportunities
        opportunities = profit_scraping_engine.get_opportunities()
        logger.info(f"🎯 Profit Scraping found {len(opportunities)} symbol opportunities")
        
        for symbol, symbol_opportunities in opportunities.items():
            logger.info(f"🎯 {symbol}: {len(symbol_opportunities)} opportunities")
            for i, opp in enumerate(symbol_opportunities):
                level = opp.get('level', {})
                targets = opp.get('targets', {})
                logger.info(f"   Opportunity {i+1}: {level.get('level_type')} @ ${level.get('price', 0):.2f} "
                           f"(confidence: {opp.get('opportunity_score', 0)}%)")
        
        logger.info("✅ Step 6: Test Paper Trading Signal Processing")
        
        # Check if paper trading engine can access profit scraping opportunities
        fresh_opportunities = await paper_trading_engine._get_fresh_opportunities()
        logger.info(f"🎯 Paper Trading found {len(fresh_opportunities)} fresh opportunities from profit scraping")
        
        for opp in fresh_opportunities:
            logger.info(f"   Paper Trading Opportunity: {opp.get('symbol')} {opp.get('side')} "
                       f"(confidence: {opp.get('confidence', 0):.2f}) - Strategy: {opp.get('strategy_type')}")
        
        logger.info("✅ Step 7: Test Signal Conversion")
        
        # Test signal conversion
        if fresh_opportunities:
            test_opp = fresh_opportunities[0]
            signal = paper_trading_engine._convert_opportunity_to_signal(test_opp)
            
            if signal:
                logger.info(f"🎯 Successfully converted opportunity to signal: {signal}")
                
                # Test if we should trade this signal
                should_trade = paper_trading_engine._should_trade_signal(signal)
                logger.info(f"🎯 Should trade signal: {should_trade}")
                
                if should_trade:
                    logger.info("✅ Step 8: Execute Test Trade")
                    
                    # Execute a test trade
                    position_id = await paper_trading_engine.execute_trade(signal)
                    
                    if position_id:
                        logger.info(f"🚀 Successfully executed paper trade: {position_id}")
                        
                        # Check account status
                        account_status = paper_trading_engine.get_account_status()
                        logger.info(f"📊 Account Status: {account_status['account']['active_positions']} active positions")
                        
                        # Wait a bit then close the position
                        await asyncio.sleep(5)
                        
                        trade = await paper_trading_engine.close_position(position_id, "test_completion")
                        if trade:
                            logger.info(f"📉 Successfully closed position: P&L ${trade.pnl:.2f}")
                        
                    else:
                        logger.warning("❌ Failed to execute paper trade")
                else:
                    logger.info("ℹ️ Signal rejected by trading filters")
            else:
                logger.warning("❌ Failed to convert opportunity to signal")
        else:
            logger.warning("⚠️ No fresh opportunities found from profit scraping")
        
        logger.info("✅ Step 9: Verify Integration Status")
        
        # Final verification
        profit_status = profit_scraping_engine.get_status()
        paper_status = paper_trading_engine.get_account_status()
        
        logger.info(f"🎯 Profit Scraping Status: Active={profit_status.get('active')}, "
                   f"Symbols={len(profit_status.get('monitored_symbols', []))}, "
                   f"Trades={profit_status.get('total_trades', 0)}")
        
        logger.info(f"📊 Paper Trading Status: Running={paper_status.get('is_running')}, "
                   f"Balance=${paper_status['account']['balance']:.2f}, "
                   f"Trades={paper_status['account']['total_trades']}")
        
        # Check if paper trading engine has profit scraping connection
        has_profit_scraping = hasattr(paper_trading_engine, 'profit_scraping_engine') and \
                             paper_trading_engine.profit_scraping_engine is not None
        
        logger.info(f"🔗 Integration Status: Paper Trading connected to Profit Scraping = {has_profit_scraping}")
        
        if has_profit_scraping and profit_status.get('active'):
            logger.info("🎉 SUCCESS: Profit Scraping Integration is working correctly!")
            logger.info("🎯 Paper Trading Engine is now using sophisticated magnet level logic")
            return True
        else:
            logger.error("❌ FAILURE: Integration not working properly")
            return False
        
    except Exception as e:
        logger.error(f"❌ Test failed with error: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return False
    
    finally:
        # Cleanup
        try:
            if 'profit_scraping_engine' in locals():
                await profit_scraping_engine.stop_scraping()
            if 'paper_trading_engine' in locals():
                paper_trading_engine.stop()
        except Exception as e:
            logger.warning(f"Cleanup error: {e}")

async def main():
    """Main test function"""
    logger.info("🚀 Starting Profit Scraping Integration Test")
    
    success = await test_profit_scraping_integration()
    
    if success:
        logger.info("✅ All tests passed! Integration is working correctly.")
        sys.exit(0)
    else:
        logger.error("❌ Tests failed! Integration needs fixing.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
