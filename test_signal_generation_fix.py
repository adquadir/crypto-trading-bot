#!/usr/bin/env python3

import asyncio
import logging
import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.api.main import initialize_components

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_signal_generation():
    """Test that signal generation is working and creating real positions."""
    try:
        logger.info("🚀 Testing Signal Generation Fix...")
        
        # Initialize all components
        logger.info("Initializing components...")
        await initialize_components()
        
        # Import the global components
        from src.api.main import opportunity_manager, paper_trading_engine
        
        if not opportunity_manager:
            logger.error("❌ Opportunity manager not initialized")
            return False
            
        if not paper_trading_engine:
            logger.error("❌ Paper trading engine not initialized")
            return False
            
        logger.info("✅ Components initialized successfully")
        
        # Test signal generation
        logger.info("🔍 Testing signal generation...")
        opportunities = opportunity_manager.get_opportunities()
        
        logger.info(f"📊 Found {len(opportunities)} opportunities")
        
        if len(opportunities) == 0:
            logger.warning("⚠️ No opportunities found - triggering manual scan...")
            await opportunity_manager.scan_opportunities_incremental()
            opportunities = opportunity_manager.get_opportunities()
            logger.info(f"📊 After manual scan: {len(opportunities)} opportunities")
        
        if len(opportunities) > 0:
            # Test the first opportunity
            opp = opportunities[0]
            logger.info(f"✅ Sample opportunity: {opp['symbol']} {opp['direction']}")
            logger.info(f"   Entry: {opp.get('entry_price', 'N/A')}")
            logger.info(f"   TP: {opp.get('take_profit', 'N/A')}")
            logger.info(f"   SL: {opp.get('stop_loss', 'N/A')}")
            logger.info(f"   Confidence: {opp.get('confidence', 'N/A')}")
            logger.info(f"   Tradable: {opp.get('tradable', 'N/A')}")
            
            # Test paper trading position creation
            logger.info("🎯 Testing position creation...")
            try:
                position_size = 100.0 / opp['entry_price']  # $100 position
                
                # Create a paper trading position
                position_result = await paper_trading_engine.simulate_trade(
                    symbol=opp['symbol'],
                    direction=opp['direction'],
                    entry_price=opp['entry_price'],
                    take_profit=opp['take_profit'],
                    stop_loss=opp['stop_loss'],
                    position_size=position_size,
                    confidence=opp.get('confidence', 0.7)
                )
                
                if position_result:
                    logger.info("✅ Position created successfully!")
                    logger.info(f"   Position ID: {position_result.get('position_id', 'N/A')}")
                    return True
                else:
                    logger.error("❌ Failed to create position")
                    return False
                    
            except Exception as e:
                logger.error(f"❌ Error creating position: {e}")
                return False
        else:
            logger.error("❌ No opportunities generated - signal generation not working")
            return False
            
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main test function."""
    logger.info("🧪 Starting Signal Generation Fix Test")
    
    success = await test_signal_generation()
    
    if success:
        logger.info("🎉 SUCCESS: Signal generation is working and creating positions!")
    else:
        logger.error("💥 FAILED: Signal generation or position creation not working")
    
    return success

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
