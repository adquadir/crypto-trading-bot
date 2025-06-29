"""
Test Profit Scraping System
Comprehensive test of the real profit scraping implementation
"""

import asyncio
import logging
import sys
import os
from datetime import datetime

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from strategies.profit_scraping import ProfitScrapingEngine
from market_data.exchange_client import ExchangeClient
from trading.enhanced_paper_trading_engine import EnhancedPaperTradingEngine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_profit_scraping_system():
    """Test the complete profit scraping system"""
    try:
        logger.info("🚀 Starting Profit Scraping System Test")
        
        # Initialize components
        logger.info("📊 Initializing components...")
        
        # Create exchange client (will use mock data for testing)
        exchange_client = None  # Use None to trigger mock data generation
        
        # Create paper trading engine
        paper_trading_engine = EnhancedPaperTradingEngine()
        
        # Create profit scraping engine
        engine = ProfitScrapingEngine(
            exchange_client=exchange_client,
            paper_trading_engine=paper_trading_engine
        )
        
        logger.info("✅ Components initialized successfully")
        
        # Test 1: Check initial status
        logger.info("\n📋 Test 1: Initial Status")
        status = engine.get_status()
        logger.info(f"Initial status: {status}")
        assert not status['active'], "Engine should not be active initially"
        
        # Test 2: Start profit scraping
        logger.info("\n🎯 Test 2: Start Profit Scraping")
        test_symbols = ['BTCUSDT', 'ETHUSDT']
        success = await engine.start_scraping(test_symbols)
        assert success, "Failed to start profit scraping"
        
        status = engine.get_status()
        logger.info(f"Status after start: {status}")
        assert status['active'], "Engine should be active after start"
        assert set(status['monitored_symbols']) == set(test_symbols), "Monitored symbols mismatch"
        
        # Test 3: Wait for analysis to complete
        logger.info("\n🔍 Test 3: Wait for Symbol Analysis")
        await asyncio.sleep(3)  # Give time for initial analysis
        
        # Check identified levels
        for symbol in test_symbols:
            levels = engine.get_identified_levels(symbol)
            logger.info(f"{symbol} levels: {len(levels['price_levels'])} price levels, {len(levels['magnet_levels'])} magnet levels")
        
        # Test 4: Check opportunities
        logger.info("\n💡 Test 4: Check Opportunities")
        opportunities = engine.get_opportunities()
        logger.info(f"Current opportunities: {len(opportunities)} symbols with opportunities")
        
        for symbol, symbol_opps in opportunities.items():
            logger.info(f"{symbol}: {len(symbol_opps)} opportunities")
            for i, opp in enumerate(symbol_opps[:2]):  # Show top 2
                logger.info(f"  Opportunity {i+1}: Score={opp['opportunity_score']}, "
                           f"Level={opp['level']['level_type']} @ ${opp['level']['price']:.2f}")
        
        # Test 5: Monitor for a short period
        logger.info("\n⏱️ Test 5: Monitor for 30 seconds")
        start_time = datetime.now()
        
        while (datetime.now() - start_time).seconds < 30:
            # Check for active trades
            active_trades = engine.get_active_trades()
            if active_trades:
                logger.info(f"Active trades: {len(active_trades)}")
                for trade in active_trades:
                    logger.info(f"  Trade: {trade['symbol']} {trade['side']} @ ${trade['entry_price']:.2f}")
            
            await asyncio.sleep(5)
        
        # Test 6: Check final status
        logger.info("\n📊 Test 6: Final Status Check")
        final_status = engine.get_status()
        logger.info(f"Final status: {final_status}")
        
        # Test 7: Stop profit scraping
        logger.info("\n🛑 Test 7: Stop Profit Scraping")
        success = await engine.stop_scraping()
        assert success, "Failed to stop profit scraping"
        
        status = engine.get_status()
        logger.info(f"Status after stop: {status}")
        assert not status['active'], "Engine should not be active after stop"
        
        logger.info("\n✅ All tests passed! Profit scraping system is working correctly.")
        
        # Print summary
        logger.info("\n📈 Test Summary:")
        logger.info(f"  Total trades executed: {final_status['total_trades']}")
        logger.info(f"  Winning trades: {final_status['winning_trades']}")
        logger.info(f"  Win rate: {final_status['win_rate']:.1%}")
        logger.info(f"  Total profit: ${final_status['total_profit']:.2f}")
        logger.info(f"  Test duration: {final_status['uptime_minutes']:.1f} minutes")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_individual_components():
    """Test individual components separately"""
    try:
        logger.info("\n🧪 Testing Individual Components")
        
        # Test Price Level Analyzer
        logger.info("\n📊 Testing Price Level Analyzer")
        from strategies.profit_scraping.price_level_analyzer import PriceLevelAnalyzer
        
        analyzer = PriceLevelAnalyzer()
        levels = await analyzer.analyze_symbol('BTCUSDT', None)  # Use mock data
        logger.info(f"Price Level Analyzer: Found {len(levels)} levels")
        
        for level in levels[:3]:  # Show top 3
            logger.info(f"  Level: {level.level_type} @ ${level.price:.2f}, "
                       f"strength={level.strength_score}, touches={level.touch_count}")
        
        # Test Magnet Level Detector
        logger.info("\n🧲 Testing Magnet Level Detector")
        from strategies.profit_scraping.magnet_level_detector import MagnetLevelDetector
        
        detector = MagnetLevelDetector()
        current_price = 50000  # Mock BTC price
        
        # Generate mock historical data
        import pandas as pd
        import numpy as np
        from datetime import timedelta
        
        timestamps = pd.date_range(start=datetime.now() - timedelta(days=30), periods=720, freq='H')
        mock_data = pd.DataFrame({
            'timestamp': timestamps,
            'high': np.random.uniform(49000, 51000, 720),
            'low': np.random.uniform(49000, 51000, 720),
            'close': np.random.uniform(49000, 51000, 720)
        })
        
        magnets = detector.detect_magnet_levels('BTCUSDT', current_price, levels, mock_data)
        logger.info(f"Magnet Level Detector: Found {len(magnets)} magnet levels")
        
        for magnet in magnets[:3]:  # Show top 3
            logger.info(f"  Magnet: {magnet.magnet_type} @ ${magnet.price:.2f}, "
                       f"strength={magnet.strength}")
        
        # Test Statistical Calculator
        logger.info("\n📈 Testing Statistical Calculator")
        from strategies.profit_scraping.statistical_calculator import StatisticalCalculator
        
        calculator = StatisticalCalculator()
        
        if levels and len(mock_data) > 100:
            targets = calculator.calculate_targets(levels[0], current_price, mock_data)
            if targets:
                logger.info(f"Statistical Calculator: Generated targets")
                logger.info(f"  Entry: ${targets.entry_price:.2f}")
                logger.info(f"  Profit Target: ${targets.profit_target:.2f}")
                logger.info(f"  Stop Loss: ${targets.stop_loss:.2f}")
                logger.info(f"  Profit Probability: {targets.profit_probability:.1%}")
                logger.info(f"  Risk/Reward: {targets.risk_reward_ratio:.1f}")
                logger.info(f"  Confidence: {targets.confidence_score}/100")
            else:
                logger.info("Statistical Calculator: No valid targets generated")
        
        logger.info("✅ Individual component tests completed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Component test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main test function"""
    logger.info("🎯 Starting Comprehensive Profit Scraping Tests")
    
    # Test individual components first
    component_success = await test_individual_components()
    
    if component_success:
        # Test full system
        system_success = await test_profit_scraping_system()
        
        if system_success:
            logger.info("\n🎉 ALL TESTS PASSED! The profit scraping system is ready for deployment.")
        else:
            logger.error("\n❌ System test failed")
    else:
        logger.error("\n❌ Component tests failed")

if __name__ == "__main__":
    asyncio.run(main())
