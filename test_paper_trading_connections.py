#!/usr/bin/env python3
"""
Test Paper Trading Connections
Verify that paper trading engine has proper connections to signal sources
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_connections():
    """Test paper trading engine connections"""
    try:
        logger.info("🔧 Testing Paper Trading Connections...")
        
        # Test 1: Check if paper trading engine exists
        try:
            from src.api.trading_routes.paper_trading_routes import get_paper_engine
            engine = get_paper_engine()
            
            if engine:
                logger.info("✅ Paper trading engine found")
                logger.info(f"   Type: {type(engine).__name__}")
                logger.info(f"   Running: {engine.is_running}")
                logger.info(f"   Balance: ${engine.account.balance:.2f}")
            else:
                logger.error("❌ Paper trading engine not found")
                return
                
        except Exception as e:
            logger.error(f"❌ Error getting paper trading engine: {e}")
            return
        
        # Test 2: Check profit scraping engine connection
        profit_scraping_connected = hasattr(engine, 'profit_scraping_engine') and engine.profit_scraping_engine is not None
        logger.info(f"🎯 Profit Scraping Engine Connected: {profit_scraping_connected}")
        
        if profit_scraping_connected:
            profit_scraping_active = getattr(engine.profit_scraping_engine, 'active', False)
            logger.info(f"   Active: {profit_scraping_active}")
            
            try:
                opportunities = engine.profit_scraping_engine.get_opportunities()
                opp_count = len(opportunities) if opportunities else 0
                logger.info(f"   Opportunities: {opp_count}")
                
                if opp_count > 0:
                    logger.info("   Sample opportunities:")
                    for symbol, symbol_opps in list(opportunities.items())[:3]:
                        logger.info(f"     {symbol}: {len(symbol_opps)} opportunities")
                        
            except Exception as e:
                logger.error(f"   Error getting profit scraping opportunities: {e}")
        
        # Test 3: Check opportunity manager connection  
        opportunity_manager_connected = hasattr(engine, 'opportunity_manager') and engine.opportunity_manager is not None
        logger.info(f"🎯 Opportunity Manager Connected: {opportunity_manager_connected}")
        
        if opportunity_manager_connected:
            try:
                opportunities = engine.opportunity_manager.get_opportunities()
                opp_count = len(opportunities) if opportunities else 0
                logger.info(f"   Opportunities: {opp_count}")
                
                if opp_count > 0:
                    logger.info("   Sample opportunities:")
                    for i, opp in enumerate(opportunities[:3]):
                        symbol = opp.get('symbol', 'unknown')
                        direction = opp.get('direction', opp.get('side', 'unknown'))
                        confidence = opp.get('confidence', 0)
                        logger.info(f"     {i+1}. {symbol} {direction} (confidence: {confidence:.3f})")
                        
            except Exception as e:
                logger.error(f"   Error getting opportunity manager opportunities: {e}")
        
        # Test 4: Test signal processing
        logger.info("🔍 Testing signal processing...")
        
        try:
            # Get fresh opportunities using the engine's method
            opportunities = await engine._get_fresh_opportunities()
            logger.info(f"   Fresh opportunities found: {len(opportunities)}")
            
            if opportunities:
                logger.info("   Sample fresh opportunities:")
                for i, opp in enumerate(opportunities[:3]):
                    symbol = opp.get('symbol', 'unknown')
                    side = opp.get('side', 'unknown')
                    confidence = opp.get('confidence', 0)
                    source = opp.get('signal_source', 'unknown')
                    logger.info(f"     {i+1}. {symbol} {side} (confidence: {confidence:.3f}, source: {source})")
            else:
                logger.warning("   No fresh opportunities found - this is why positions aren't being created")
                
        except Exception as e:
            logger.error(f"   Error testing signal processing: {e}")
        
        # Test 5: Check signal configuration
        logger.info("⚙️ Signal Configuration:")
        logger.info(f"   Pure Profit Scraping Mode: {engine.signal_config.get('pure_profit_scraping_mode', 'unknown')}")
        logger.info(f"   Allow Opportunity Fallback: {engine.signal_config.get('allow_opportunity_fallback', 'unknown')}")
        logger.info(f"   Allow Flow Trading Fallback: {engine.signal_config.get('allow_flow_trading_fallback', 'unknown')}")
        
        # Test 6: Summary and recommendations
        logger.info("📋 SUMMARY:")
        
        if profit_scraping_connected and getattr(engine.profit_scraping_engine, 'active', False):
            logger.info("✅ Profit scraping engine is connected and active")
            
            try:
                profit_opps = engine.profit_scraping_engine.get_opportunities()
                if profit_opps and len(profit_opps) > 0:
                    logger.info("✅ Profit scraping engine is generating opportunities")
                else:
                    logger.warning("⚠️ Profit scraping engine is not generating opportunities")
                    logger.info("   RECOMMENDATION: Check if profit scraping symbols are being monitored")
            except:
                logger.warning("⚠️ Cannot get profit scraping opportunities")
                
        elif opportunity_manager_connected:
            logger.info("✅ Opportunity manager is connected (fallback available)")
            
            try:
                opp_opps = engine.opportunity_manager.get_opportunities()
                if opp_opps and len(opp_opps) > 0:
                    logger.info("✅ Opportunity manager is generating opportunities")
                else:
                    logger.warning("⚠️ Opportunity manager is not generating opportunities")
            except:
                logger.warning("⚠️ Cannot get opportunity manager opportunities")
        else:
            logger.error("❌ NO SIGNAL SOURCES CONNECTED")
            logger.info("   RECOMMENDATION: Check server startup logs for connection errors")
        
        # Check if engine is running
        if not engine.is_running:
            logger.warning("⚠️ Paper trading engine is not running")
            logger.info("   RECOMMENDATION: Click 'Start Trading' in the frontend")
        else:
            logger.info("✅ Paper trading engine is running")
            
        logger.info("🔧 Connection test completed")
        
    except Exception as e:
        logger.error(f"❌ Error in connection test: {e}")
        import traceback
        logger.error(f"❌ Full traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(test_connections()) 