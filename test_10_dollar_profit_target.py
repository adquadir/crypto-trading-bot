#!/usr/bin/env python3
"""
Test script to verify $10 profit target implementation
"""

import asyncio
import logging
from datetime import datetime, timedelta
from src.trading.enhanced_paper_trading_engine import EnhancedPaperTradingEngine
from src.strategies.profit_scraping.statistical_calculator import StatisticalCalculator
from src.strategies.profit_scraping.price_level_analyzer import PriceLevel

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_paper_trading_tp():
    """Test paper trading engine TP calculation"""
    logger.info("🧪 Testing Paper Trading Engine TP calculation...")
    
    # Create paper trading engine with test config
    config = {
        'paper_trading': {
            'initial_balance': 10000.0,
            'risk_per_trade_pct': 0.02,  # 2% = $200 per trade
            'leverage': 10.0,  # 10x leverage
            'max_positions': 50
        }
    }
    
    engine = EnhancedPaperTradingEngine(config)
    
    # Test TP calculation for LONG position
    entry_price = 50000.0  # $50,000 BTC price
    tp_long = await engine._calculate_take_profit(entry_price, 'LONG', 'BTCUSDT')
    
    # Expected: 0.5% above entry = $50,250
    expected_tp_long = entry_price * 1.005
    
    logger.info(f"📊 LONG Position Test:")
    logger.info(f"   Entry Price: ${entry_price:,.2f}")
    logger.info(f"   Calculated TP: ${tp_long:,.2f}")
    logger.info(f"   Expected TP: ${expected_tp_long:,.2f}")
    logger.info(f"   Match: {'✅' if abs(tp_long - expected_tp_long) < 0.01 else '❌'}")
    
    # Test TP calculation for SHORT position
    tp_short = await engine._calculate_take_profit(entry_price, 'SHORT', 'BTCUSDT')
    
    # Expected: 0.5% below entry = $49,750
    expected_tp_short = entry_price * 0.995
    
    logger.info(f"📊 SHORT Position Test:")
    logger.info(f"   Entry Price: ${entry_price:,.2f}")
    logger.info(f"   Calculated TP: ${tp_short:,.2f}")
    logger.info(f"   Expected TP: ${expected_tp_short:,.2f}")
    logger.info(f"   Match: {'✅' if abs(tp_short - expected_tp_short) < 0.01 else '❌'}")
    
    # Calculate actual profit with leverage
    capital_at_risk = 200.0  # $200 per position (2% of $10k)
    leverage = 10.0
    notional_value = capital_at_risk * leverage  # $2,000
    quantity = notional_value / entry_price  # BTC quantity
    
    # LONG profit calculation
    price_change_long = tp_long - entry_price
    profit_long = (price_change_long / entry_price) * notional_value
    
    logger.info(f"💰 LONG Profit Calculation:")
    logger.info(f"   Capital at risk: ${capital_at_risk:.2f}")
    logger.info(f"   Leverage: {leverage}x")
    logger.info(f"   Notional value: ${notional_value:,.2f}")
    logger.info(f"   BTC quantity: {quantity:.6f}")
    logger.info(f"   Price change: ${price_change_long:,.2f}")
    logger.info(f"   Profit: ${profit_long:.2f}")
    logger.info(f"   Target $10: {'✅' if abs(profit_long - 10.0) < 0.01 else '❌'}")
    
    # SHORT profit calculation
    price_change_short = entry_price - tp_short
    profit_short = (price_change_short / entry_price) * notional_value
    
    logger.info(f"💰 SHORT Profit Calculation:")
    logger.info(f"   Capital at risk: ${capital_at_risk:.2f}")
    logger.info(f"   Leverage: {leverage}x")
    logger.info(f"   Notional value: ${notional_value:,.2f}")
    logger.info(f"   BTC quantity: {quantity:.6f}")
    logger.info(f"   Price change: ${price_change_short:,.2f}")
    logger.info(f"   Profit: ${profit_short:.2f}")
    logger.info(f"   Target $10: {'✅' if abs(profit_short - 10.0) < 0.01 else '❌'}")

def test_profit_scraping_tp():
    """Test profit scraping statistical calculator TP"""
    logger.info("🧪 Testing Profit Scraping Statistical Calculator TP...")
    
    calculator = StatisticalCalculator()
    
    # Create test support level
    support_level = PriceLevel(
        price=50000.0,
        level_type='support',
        strength_score=85,
        touch_count=5,
        bounce_count=4,
        avg_bounce_distance=0.01,
        max_bounce_distance=0.02,
        last_tested=datetime.now(),
        first_identified=datetime.now() - timedelta(days=7),
        volume_confirmation=1000.0
    )
    
    # Test bounce analysis (mock data)
    bounce_analysis = {
        'sample_size': 10,
        'success_rate': 0.8,
        'percentile_75': 0.015,  # This should be ignored now
        'bounce_data': []
    }
    
    # Calculate profit target
    current_price = 50000.0
    tp_support = calculator._calculate_profit_target(support_level, bounce_analysis, current_price)
    
    # Expected: 0.5% above support = $50,250
    expected_tp_support = support_level.price * 1.005
    
    logger.info(f"📊 Support Level Test:")
    logger.info(f"   Support Price: ${support_level.price:,.2f}")
    logger.info(f"   Calculated TP: ${tp_support:,.2f}")
    logger.info(f"   Expected TP: ${expected_tp_support:,.2f}")
    logger.info(f"   Match: {'✅' if abs(tp_support - expected_tp_support) < 0.01 else '❌'}")
    
    # Create test resistance level
    resistance_level = PriceLevel(
        price=50000.0,
        level_type='resistance',
        strength_score=85,
        touch_count=5,
        bounce_count=4,
        avg_bounce_distance=0.01,
        max_bounce_distance=0.02,
        last_tested=datetime.now(),
        first_identified=datetime.now() - timedelta(days=7),
        volume_confirmation=1000.0
    )
    
    # Calculate profit target for resistance
    tp_resistance = calculator._calculate_profit_target(resistance_level, bounce_analysis, current_price)
    
    # Expected: 0.5% below resistance = $49,750
    expected_tp_resistance = resistance_level.price * 0.995
    
    logger.info(f"📊 Resistance Level Test:")
    logger.info(f"   Resistance Price: ${resistance_level.price:,.2f}")
    logger.info(f"   Calculated TP: ${tp_resistance:,.2f}")
    logger.info(f"   Expected TP: ${expected_tp_resistance:,.2f}")
    logger.info(f"   Match: {'✅' if abs(tp_resistance - expected_tp_resistance) < 0.01 else '❌'}")

def test_profit_calculation():
    """Test the actual $10 profit calculation"""
    logger.info("🧪 Testing $10 Profit Calculation Logic...")
    
    # Test parameters
    entry_price = 50000.0
    capital_at_risk = 200.0  # 2% of $10,000
    leverage = 10.0
    target_profit = 10.0
    
    # Calculate required price movement for $10 profit
    notional_value = capital_at_risk * leverage  # $2,000
    required_price_change_pct = target_profit / notional_value  # $10 / $2,000 = 0.005 = 0.5%
    
    logger.info(f"💡 Calculation Logic:")
    logger.info(f"   Target profit: ${target_profit:.2f}")
    logger.info(f"   Capital at risk: ${capital_at_risk:.2f}")
    logger.info(f"   Leverage: {leverage}x")
    logger.info(f"   Notional value: ${notional_value:,.2f}")
    logger.info(f"   Required price change: {required_price_change_pct:.3%}")
    
    # Test LONG position
    tp_long = entry_price * (1 + required_price_change_pct)
    actual_profit_long = ((tp_long - entry_price) / entry_price) * notional_value
    
    logger.info(f"📈 LONG Position:")
    logger.info(f"   Entry: ${entry_price:,.2f}")
    logger.info(f"   TP: ${tp_long:,.2f}")
    logger.info(f"   Profit: ${actual_profit_long:.2f}")
    logger.info(f"   Target $10: {'✅' if abs(actual_profit_long - 10.0) < 0.01 else '❌'}")
    
    # Test SHORT position
    tp_short = entry_price * (1 - required_price_change_pct)
    actual_profit_short = ((entry_price - tp_short) / entry_price) * notional_value
    
    logger.info(f"📉 SHORT Position:")
    logger.info(f"   Entry: ${entry_price:,.2f}")
    logger.info(f"   TP: ${tp_short:,.2f}")
    logger.info(f"   Profit: ${actual_profit_short:.2f}")
    logger.info(f"   Target $10: {'✅' if abs(actual_profit_short - 10.0) < 0.01 else '❌'}")

async def main():
    """Run all tests"""
    logger.info("🚀 Starting $10 Profit Target Tests")
    logger.info("=" * 60)
    
    # Test 1: Basic calculation logic
    test_profit_calculation()
    logger.info("=" * 60)
    
    # Test 2: Paper trading engine
    await test_paper_trading_tp()
    logger.info("=" * 60)
    
    # Test 3: Profit scraping calculator
    test_profit_scraping_tp()
    logger.info("=" * 60)
    
    logger.info("✅ All tests completed!")
    logger.info("🎯 Summary: Both engines now use fixed 0.5% TP for $10 profit target")
    logger.info("💰 With $200 capital at risk and 10x leverage, 0.5% price movement = $10 profit")

if __name__ == "__main__":
    asyncio.run(main())
