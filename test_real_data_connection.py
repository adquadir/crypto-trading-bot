#!/usr/bin/env python3
"""
Test script to verify the system uses REAL Binance data instead of mock data
"""

import asyncio
import logging
import sys
import os

# Add the src directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.strategies.profit_scraping.price_level_analyzer import PriceLevelAnalyzer
from src.market_data.exchange_client import ExchangeClient

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_real_data_connection():
    """Test that the system uses real Binance data when exchange client is available"""
    
    logger.info("🧪 Testing REAL Binance data connection...")
    
    try:
        # Initialize exchange client (this connects to real Binance)
        logger.info("🔗 Initializing exchange client...")
        exchange_client = ExchangeClient()
        await exchange_client.initialize()
        logger.info("✅ Exchange client initialized")
        
        # Test connection
        connection_ok = await exchange_client.check_connection()
        if not connection_ok:
            logger.error("❌ Exchange connection failed")
            return False
        
        logger.info("✅ Exchange connection verified")
        
        # Initialize price level analyzer
        analyzer = PriceLevelAnalyzer(min_touches=2, min_strength=50)
        
        # Test with real data
        test_symbol = 'BTCUSDT'
        logger.info(f"📊 Testing real data analysis for {test_symbol}...")
        
        # This should now use REAL Binance data
        levels = await analyzer.analyze_symbol(test_symbol, exchange_client)
        
        logger.info(f"📈 Analysis complete:")
        logger.info(f"  Total levels found: {len(levels)}")
        
        support_count = sum(1 for level in levels if level.level_type == 'support')
        resistance_count = sum(1 for level in levels if level.level_type == 'resistance')
        
        logger.info(f"  Support levels (LONG): {support_count}")
        logger.info(f"  Resistance levels (SHORT): {resistance_count}")
        
        # Show some example levels
        for i, level in enumerate(levels[:5]):  # Show first 5 levels
            direction = "LONG" if level.level_type == 'support' else "SHORT"
            logger.info(f"    {direction} @ ${level.price:.2f} (strength: {level.strength_score})")
        
        # Check if we got realistic price levels for BTC
        if levels:
            prices = [level.price for level in levels]
            min_price = min(prices)
            max_price = max(prices)
            
            # BTC should be in a reasonable range (e.g., $20k - $200k)
            if 20000 <= min_price <= 200000 and 20000 <= max_price <= 200000:
                logger.info(f"✅ SUCCESS: Price levels look realistic for BTC (${min_price:.0f} - ${max_price:.0f})")
                logger.info("🎉 System is using REAL Binance data for profit scraping!")
                return True
            else:
                logger.warning(f"⚠️ Price levels seem unrealistic: ${min_price:.0f} - ${max_price:.0f}")
                return False
        else:
            logger.warning("⚠️ No price levels found")
            return False
            
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return False
    
    finally:
        # Clean up
        try:
            if 'exchange_client' in locals():
                await exchange_client.close()
        except:
            pass

async def main():
    """Main test function"""
    
    logger.info("🚀 Starting real data connection test...")
    
    success = await test_real_data_connection()
    
    if success:
        logger.info("\n🎉 TEST PASSED!")
        logger.info("✅ Your profit scraping system will use REAL Binance data")
        logger.info("✅ Price levels will be based on actual market movements")
        logger.info("✅ Trading signals will reflect real market conditions")
        logger.info("\n💡 Restart your paper trading system to use real data:")
        logger.info("   pkill -f simple_api.py && nohup python simple_api.py > api.log 2>&1 &")
    else:
        logger.warning("\n⚠️ TEST FAILED!")
        logger.warning("❌ System may still be using mock data")
        logger.warning("❌ Check your Binance API connection")

if __name__ == "__main__":
    asyncio.run(main())
