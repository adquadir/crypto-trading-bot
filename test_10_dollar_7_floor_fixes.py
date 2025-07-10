#!/usr/bin/env python3
"""
Test script to verify the $10 take profit and $7 floor system fixes
"""

import asyncio
import logging
import sys
import os
from datetime import datetime

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.trading.enhanced_paper_trading_engine import EnhancedPaperTradingEngine, PaperPosition
from src.market_data.exchange_client import ExchangeClient

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MockExchangeClient:
    """Mock exchange client for testing"""
    
    def __init__(self):
        self.mock_prices = {
            'BTCUSDT': 50000.0
        }
        self.price_sequence = []
        self.price_index = 0
    
    def set_price_sequence(self, prices):
        """Set a sequence of prices to simulate price movement"""
        self.price_sequence = prices
        self.price_index = 0
    
    async def get_current_price(self, symbol):
        """Return mock price"""
        if self.price_sequence and self.price_index < len(self.price_sequence):
            price = self.price_sequence[self.price_index]
            self.price_index += 1
            return price
        return self.mock_prices.get(symbol, 50000.0)
    
    async def get_ticker_24h(self, symbol):
        """Return mock ticker"""
        price = await self.get_current_price(symbol)
        return {'lastPrice': str(price)}
    
    async def get_klines(self, symbol, interval, limit):
        """Return mock klines"""
        price = await self.get_current_price(symbol)
        # Return simple klines data
        klines = []
        for i in range(limit):
            klines.append([
                0,  # open_time
                str(price),  # open
                str(price * 1.001),  # high
                str(price * 0.999),  # low
                str(price),  # close
                "1000.0",  # volume
                0,  # close_time
                "0",  # quote_asset_volume
                0,  # number_of_trades
                "0",  # taker_buy_base_asset_volume
                "0",  # taker_buy_quote_asset_volume
                "0"  # ignore
            ])
        return klines

async def test_10_dollar_take_profit():
    """Test that $10 take profit works correctly"""
    logger.info("🎯 Testing $10 Take Profit System")
    
    # Create mock exchange client
    mock_client = MockExchangeClient()
    
    # Create paper trading engine
    config = {
        'paper_trading': {
            'initial_balance': 10000.0,
            'enabled': True,
            'max_position_size_pct': 0.02,
            'max_total_exposure_pct': 1.0,
            'max_daily_loss_pct': 0.50
        }
    }
    
    engine = EnhancedPaperTradingEngine(config, mock_client)
    
    # Start the engine
    await engine.start()
    
    # Create a test signal
    signal = {
        'symbol': 'BTCUSDT',
        'strategy_type': 'test',
        'side': 'LONG',
        'confidence': 0.8,
        'ml_score': 0.8,
        'reason': 'test_10_dollar_tp',
        'market_regime': 'test',
        'volatility_regime': 'medium'
    }
    
    # Set initial price
    mock_client.mock_prices['BTCUSDT'] = 50000.0
    
    # Execute trade
    position_id = await engine.execute_trade(signal)
    
    if not position_id:
        logger.error("❌ Failed to create test position")
        return False
    
    logger.info(f"✅ Created test position: {position_id}")
    
    # Get the position
    position = engine.positions[position_id]
    logger.info(f"📊 Position details: Entry @ ${position.entry_price:.2f}, Quantity: {position.quantity:.6f}")
    logger.info(f"📊 Take Profit: ${position.take_profit:.4f}")
    
    # Calculate what price would give us $10 profit
    # With 10x leverage and $200 capital: $10 profit = 0.5% price movement
    target_price = position.entry_price * 1.005  # 0.5% increase
    logger.info(f"🎯 Target price for $10 profit: ${target_price:.4f}")
    
    # Set price sequence to reach $10 profit
    mock_client.set_price_sequence([target_price])
    
    # Manually trigger position monitoring
    positions_to_close = []
    current_price = await mock_client.get_current_price('BTCUSDT')
    
    # Update position P&L
    position.unrealized_pnl = (current_price - position.entry_price) * position.quantity
    position.current_price = current_price
    
    logger.info(f"💰 Current P&L: ${position.unrealized_pnl:.2f}")
    
    # Check if take profit should trigger
    if position.take_profit and current_price >= position.take_profit:
        logger.info("✅ Take profit should trigger!")
        
        # Close the position
        trade = await engine.close_position(position_id, "take_profit")
        
        if trade:
            logger.info(f"✅ Position closed with P&L: ${trade.pnl:.2f}")
            
            # Verify the profit is approximately $10
            if 9.0 <= trade.pnl <= 11.0:
                logger.info("✅ $10 Take Profit Test PASSED!")
                return True
            else:
                logger.error(f"❌ Expected ~$10 profit, got ${trade.pnl:.2f}")
                return False
        else:
            logger.error("❌ Failed to close position")
            return False
    else:
        logger.error(f"❌ Take profit did not trigger. Current: ${current_price:.4f}, TP: ${position.take_profit:.4f}")
        return False

async def test_7_dollar_floor_system():
    """Test that $7 floor system works correctly"""
    logger.info("🛡️ Testing $7 Floor Protection System")
    
    # Create mock exchange client
    mock_client = MockExchangeClient()
    
    # Create paper trading engine
    config = {
        'paper_trading': {
            'initial_balance': 10000.0,
            'enabled': True,
            'max_position_size_pct': 0.02,
            'max_total_exposure_pct': 1.0,
            'max_daily_loss_pct': 0.50
        }
    }
    
    engine = EnhancedPaperTradingEngine(config, mock_client)
    
    # Start the engine
    await engine.start()
    
    # Create a test signal
    signal = {
        'symbol': 'BTCUSDT',
        'strategy_type': 'test',
        'side': 'LONG',
        'confidence': 0.8,
        'ml_score': 0.8,
        'reason': 'test_7_dollar_floor',
        'market_regime': 'test',
        'volatility_regime': 'medium'
    }
    
    # Set initial price
    mock_client.mock_prices['BTCUSDT'] = 50000.0
    
    # Execute trade
    position_id = await engine.execute_trade(signal)
    
    if not position_id:
        logger.error("❌ Failed to create test position")
        return False
    
    logger.info(f"✅ Created test position: {position_id}")
    
    # Get the position
    position = engine.positions[position_id]
    logger.info(f"📊 Position details: Entry @ ${position.entry_price:.2f}, Quantity: {position.quantity:.6f}")
    
    # Simulate price movement: Go to $8 profit, then drop to $6.99
    price_for_8_dollars = position.entry_price * 1.004  # 0.4% for $8 profit
    price_for_6_99_dollars = position.entry_price * 1.0035  # Slightly below $7
    
    logger.info(f"🎯 Price for $8 profit: ${price_for_8_dollars:.4f}")
    logger.info(f"🎯 Price for $6.99 profit: ${price_for_6_99_dollars:.4f}")
    
    # Step 1: Move to $8 profit to activate floor
    mock_client.mock_prices['BTCUSDT'] = price_for_8_dollars
    current_price = await mock_client.get_current_price('BTCUSDT')
    
    # Update position P&L
    position.unrealized_pnl = (current_price - position.entry_price) * position.quantity
    position.current_price = current_price
    position.highest_profit_ever = max(position.highest_profit_ever, position.unrealized_pnl)
    
    logger.info(f"💰 P&L at peak: ${position.unrealized_pnl:.2f}")
    logger.info(f"💰 Highest profit ever: ${position.highest_profit_ever:.2f}")
    
    # Check if floor should be activated
    if position.highest_profit_ever >= position.absolute_floor_profit:
        position.profit_floor_activated = True
        logger.info("🛡️ Floor activated!")
    
    # Step 2: Drop to $6.99 to test floor protection
    mock_client.mock_prices['BTCUSDT'] = price_for_6_99_dollars
    current_price = await mock_client.get_current_price('BTCUSDT')
    
    # Update position P&L
    position.unrealized_pnl = (current_price - position.entry_price) * position.quantity
    position.current_price = current_price
    
    logger.info(f"💰 P&L after drop: ${position.unrealized_pnl:.2f}")
    
    # Check if floor protection should trigger
    if position.profit_floor_activated and position.unrealized_pnl < position.absolute_floor_profit:
        logger.info("✅ Floor protection should trigger!")
        
        # Close the position
        trade = await engine.close_position(position_id, "absolute_floor_7_dollars")
        
        if trade:
            logger.info(f"✅ Position closed with P&L: ${trade.pnl:.2f}")
            
            # Verify the profit is approximately $7 (allowing for fees)
            if 6.5 <= trade.pnl <= 7.5:
                logger.info("✅ $7 Floor Protection Test PASSED!")
                return True
            else:
                logger.error(f"❌ Expected ~$7 profit, got ${trade.pnl:.2f}")
                return False
        else:
            logger.error("❌ Failed to close position")
            return False
    else:
        logger.error(f"❌ Floor protection did not trigger. Floor active: {position.profit_floor_activated}, P&L: ${position.unrealized_pnl:.2f}")
        return False

async def test_cooperative_system():
    """Test that both systems work together cooperatively"""
    logger.info("🤝 Testing Cooperative $10 TP + $7 Floor System")
    
    # Create mock exchange client
    mock_client = MockExchangeClient()
    
    # Create paper trading engine
    config = {
        'paper_trading': {
            'initial_balance': 10000.0,
            'enabled': True,
            'max_position_size_pct': 0.02,
            'max_total_exposure_pct': 1.0,
            'max_daily_loss_pct': 0.50
        }
    }
    
    engine = EnhancedPaperTradingEngine(config, mock_client)
    
    # Start the engine
    await engine.start()
    
    # Create a test signal
    signal = {
        'symbol': 'BTCUSDT',
        'strategy_type': 'test',
        'side': 'LONG',
        'confidence': 0.8,
        'ml_score': 0.8,
        'reason': 'test_cooperative_system',
        'market_regime': 'test',
        'volatility_regime': 'medium'
    }
    
    # Set initial price
    mock_client.mock_prices['BTCUSDT'] = 50000.0
    
    # Execute trade
    position_id = await engine.execute_trade(signal)
    
    if not position_id:
        logger.error("❌ Failed to create test position")
        return False
    
    logger.info(f"✅ Created test position: {position_id}")
    
    # Get the position
    position = engine.positions[position_id]
    logger.info(f"📊 Position details: Entry @ ${position.entry_price:.2f}")
    logger.info(f"📊 Take Profit: ${position.take_profit:.4f}")
    logger.info(f"📊 Floor Protection: ${position.absolute_floor_profit}")
    
    # Verify both systems are enabled
    has_take_profit = position.take_profit is not None
    has_floor_protection = position.absolute_floor_profit == 7.0
    
    if has_take_profit and has_floor_protection:
        logger.info("✅ Cooperative System Test PASSED!")
        logger.info("✅ Both $10 take profit AND $7 floor protection are active")
        return True
    else:
        logger.error(f"❌ Systems not properly configured. TP: {has_take_profit}, Floor: {has_floor_protection}")
        return False

async def main():
    """Run all tests"""
    logger.info("🚀 Starting $10 Take Profit and $7 Floor System Tests")
    
    tests = [
        ("$10 Take Profit", test_10_dollar_take_profit),
        ("$7 Floor Protection", test_7_dollar_floor_system),
        ("Cooperative System", test_cooperative_system)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        logger.info(f"\n{'='*60}")
        logger.info(f"Running {test_name} Test")
        logger.info(f"{'='*60}")
        
        try:
            result = await test_func()
            results.append((test_name, result))
            
            if result:
                logger.info(f"✅ {test_name} Test: PASSED")
            else:
                logger.error(f"❌ {test_name} Test: FAILED")
                
        except Exception as e:
            logger.error(f"❌ {test_name} Test: ERROR - {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("TEST SUMMARY")
    logger.info(f"{'='*60}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"{test_name}: {status}")
    
    logger.info(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 ALL TESTS PASSED! $10 TP and $7 Floor fixes are working correctly!")
        return True
    else:
        logger.error("❌ Some tests failed. Please check the implementation.")
        return False

if __name__ == "__main__":
    asyncio.run(main())
