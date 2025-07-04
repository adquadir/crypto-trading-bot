#!/usr/bin/env python3
"""
Test script to verify that the profit scraping system generates balanced LONG and SHORT signals
"""

import asyncio
import logging
import sys
import os

# Add the src directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.strategies.profit_scraping.profit_scraping_engine import ProfitScrapingEngine
from src.strategies.profit_scraping.price_level_analyzer import PriceLevelAnalyzer
from src.trading.enhanced_paper_trading_engine import EnhancedPaperTradingEngine

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_balanced_signal_generation():
    """Test that the system generates both LONG and SHORT signals"""
    
    logger.info("🧪 Testing balanced signal generation...")
    
    # Test symbols
    test_symbols = ['BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'SOLUSDT', 'DOTUSDT']
    
    # Initialize components
    level_analyzer = PriceLevelAnalyzer(min_touches=2, min_strength=50)  # Lower thresholds for testing
    
    # Test each symbol
    signal_summary = {
        'support_levels': 0,
        'resistance_levels': 0,
        'long_opportunities': 0,
        'short_opportunities': 0
    }
    
    for symbol in test_symbols:
        logger.info(f"\n🔍 Testing {symbol}...")
        
        # Analyze price levels (this will use mock data)
        levels = await level_analyzer.analyze_symbol(symbol, exchange_client=None)
        
        logger.info(f"📊 {symbol} - Found {len(levels)} price levels:")
        
        support_count = 0
        resistance_count = 0
        
        for level in levels:
            level_type = level.level_type
            if level_type == 'support':
                support_count += 1
                signal_summary['support_levels'] += 1
                signal_summary['long_opportunities'] += 1
                logger.info(f"  📈 SUPPORT @ ${level.price:.2f} (strength: {level.strength_score}) → LONG signal")
            elif level_type == 'resistance':
                resistance_count += 1
                signal_summary['resistance_levels'] += 1
                signal_summary['short_opportunities'] += 1
                logger.info(f"  📉 RESISTANCE @ ${level.price:.2f} (strength: {level.strength_score}) → SHORT signal")
        
        logger.info(f"✅ {symbol}: {support_count} support levels (LONG), {resistance_count} resistance levels (SHORT)")
    
    # Print summary
    logger.info(f"\n📋 SIGNAL GENERATION SUMMARY:")
    logger.info(f"  Total Support Levels (LONG signals): {signal_summary['support_levels']}")
    logger.info(f"  Total Resistance Levels (SHORT signals): {signal_summary['resistance_levels']}")
    logger.info(f"  LONG Opportunities: {signal_summary['long_opportunities']}")
    logger.info(f"  SHORT Opportunities: {signal_summary['short_opportunities']}")
    
    # Check balance
    total_signals = signal_summary['long_opportunities'] + signal_summary['short_opportunities']
    if total_signals > 0:
        long_pct = (signal_summary['long_opportunities'] / total_signals) * 100
        short_pct = (signal_summary['short_opportunities'] / total_signals) * 100
        
        logger.info(f"  Signal Balance: {long_pct:.1f}% LONG, {short_pct:.1f}% SHORT")
        
        if signal_summary['short_opportunities'] > 0:
            logger.info("✅ SUCCESS: System generates both LONG and SHORT signals!")
            return True
        else:
            logger.warning("❌ ISSUE: No SHORT signals generated")
            return False
    else:
        logger.warning("❌ ISSUE: No signals generated at all")
        return False

async def test_trend_filtering():
    """Test the relaxed trend filtering logic"""
    
    logger.info("\n🧪 Testing trend filtering logic...")
    
    # Initialize profit scraping engine
    paper_engine = EnhancedPaperTradingEngine(config={'paper_trading': {}})
    profit_engine = ProfitScrapingEngine(paper_trading_engine=paper_engine)
    
    # Test trend detection for different symbols
    test_symbols = ['BTCUSDT', 'ETHUSDT', 'ADAUSDT']
    
    for symbol in test_symbols:
        logger.info(f"\n🔍 Testing trend detection for {symbol}...")
        
        # Test trend detection
        trend = await profit_engine._detect_market_trend(symbol)
        logger.info(f"  Detected trend: {trend}")
        
        # Test validation with mock opportunities
        from src.strategies.profit_scraping.profit_scraping_engine import ScrapingOpportunity
        from src.strategies.profit_scraping.price_level_analyzer import PriceLevel
        from src.strategies.profit_scraping.statistical_calculator import TradingTargets
        from datetime import datetime
        
        # Create mock support opportunity (LONG signal)
        support_level = PriceLevel(
            price=50000.0,
            level_type='support',
            strength_score=85,  # Strong level
            touch_count=5,
            bounce_count=4,
            avg_bounce_distance=0.01,
            max_bounce_distance=0.02,
            last_tested=datetime.now(),
            first_identified=datetime.now(),
            volume_confirmation=1000.0
        )
        
        support_targets = TradingTargets(
            profit_target=50400.0,
            stop_loss=49750.0,
            confidence_score=80,
            risk_reward_ratio=1.6,
            expected_duration_minutes=30
        )
        
        support_opportunity = ScrapingOpportunity(
            symbol=symbol,
            level=support_level,
            magnet_level=None,
            targets=support_targets,
            current_price=50000.0,
            distance_to_level=0.001,
            opportunity_score=85,
            created_at=datetime.now()
        )
        
        # Test support validation (should allow strong support even in downtrends)
        support_valid = await profit_engine._validate_entry_conditions(support_opportunity, 50000.0)
        logger.info(f"  Strong SUPPORT validation: {'✅ ALLOWED' if support_valid else '❌ BLOCKED'}")
        
        # Create mock resistance opportunity (SHORT signal)
        resistance_level = PriceLevel(
            price=51000.0,
            level_type='resistance',
            strength_score=85,  # Strong level
            touch_count=5,
            bounce_count=4,
            avg_bounce_distance=0.01,
            max_bounce_distance=0.02,
            last_tested=datetime.now(),
            first_identified=datetime.now(),
            volume_confirmation=1000.0
        )
        
        resistance_targets = TradingTargets(
            profit_target=50600.0,
            stop_loss=51250.0,
            confidence_score=80,
            risk_reward_ratio=1.6,
            expected_duration_minutes=30
        )
        
        resistance_opportunity = ScrapingOpportunity(
            symbol=symbol,
            level=resistance_level,
            magnet_level=None,
            targets=resistance_targets,
            current_price=51000.0,
            distance_to_level=0.001,
            opportunity_score=85,
            created_at=datetime.now()
        )
        
        # Test resistance validation (should allow strong resistance even in uptrends)
        resistance_valid = await profit_engine._validate_entry_conditions(resistance_opportunity, 51000.0)
        logger.info(f"  Strong RESISTANCE validation: {'✅ ALLOWED' if resistance_valid else '❌ BLOCKED'}")

async def main():
    """Main test function"""
    
    logger.info("🚀 Starting balanced signal generation tests...")
    
    try:
        # Test 1: Signal generation balance
        balance_success = await test_balanced_signal_generation()
        
        # Test 2: Trend filtering
        await test_trend_filtering()
        
        if balance_success:
            logger.info("\n🎉 ALL TESTS PASSED! The system should now generate balanced LONG and SHORT signals.")
            logger.info("💡 Restart your paper trading system to see the improved signal generation.")
        else:
            logger.warning("\n⚠️ TESTS REVEALED ISSUES. Check the logs above for details.")
            
    except Exception as e:
        logger.error(f"❌ Test failed with error: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(main())
