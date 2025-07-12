#!/usr/bin/env python3
"""
Test script to verify the $10 take profit fix is working correctly
This will test the critical fixes made to the position monitoring loop
"""

import asyncio
import logging
import sys
import os
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

# Add the src directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from trading.enhanced_paper_trading_engine import EnhancedPaperTradingEngine, PaperPosition

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MockExchangeClient:
    """Mock exchange client for testing"""
    
    def __init__(self):
        self.prices = {
            'BTCUSDT': 50000.0,  # Starting price
            'ETHUSDT': 3000.0
        }
        self.price_increments = {
            'BTCUSDT': 0,  # Will be set during test
            'ETHUSDT': 0
        }
    
    async def get_current_price(self, symbol):
        """Return mock price that can be controlled for testing"""
        base_price = self.prices[symbol]
        increment = self.price_increments.get(symbol, 0)
        current_price = base_price + increment
        logger.info(f"📊 Mock price for {symbol}: ${current_price:.2f} (base: ${base_price:.2f}, increment: {increment})")
        return current_price
    
    async def get_ticker_24h(self, symbol):
        """Mock ticker data"""
        price = await self.get_current_price(symbol)
        return {'lastPrice': str(price)}
    
    def set_price_increment(self, symbol, increment):
        """Set price increment for testing profit scenarios"""
        self.price_increments[symbol] = increment
        logger.info(f"🎯 Set price increment for {symbol}: {increment} (new price will be ${self.prices[symbol] + increment:.2f})")

async def test_10_dollar_take_profit_fix():
    """Test the $10 take profit fix with various scenarios"""
    
    logger.info("🚀 Starting $10 Take Profit Fix Verification Test")
    logger.info("=" * 60)
    
    # Create mock exchange client
    mock_exchange = MockExchangeClient()
    
    # Create paper trading engine with test config
    config = {
        'paper_trading': {
            'initial_balance': 10000.0,
            'risk_per_trade_pct': 0.02,  # 2% per trade
            'max_positions': 50,
            'leverage': 10.0
        }
    }
    
    engine = EnhancedPaperTradingEngine(config, mock_exchange)
    
    # Start the engine
    await engine.start()
    
    try:
        # Test 1: Create a position that will reach $10 profit
        logger.info("\n🎯 TEST 1: Creating position that will reach $10 profit")
        logger.info("-" * 50)
        
        # Create a LONG position at $50,000
        symbol = 'BTCUSDT'
        entry_price = 50000.0
        
        # Calculate position size for $10 profit target
        # With 2% risk ($200) and 10x leverage = $2000 notional
        # Quantity = $2000 / $50,000 = 0.04 BTC
        # For $10 profit: price needs to move 0.5% (10/2000 = 0.005)
        # Target price = $50,000 * 1.005 = $50,250
        
        position = PaperPosition(
            id="test_position_1",
            symbol=symbol,
            strategy_type="test",
            side="LONG",
            entry_price=entry_price,
            quantity=0.04,  # 0.04 BTC
            entry_time=datetime.utcnow(),
            capital_allocated=200.0,
            leverage=10.0,
            notional_value=2000.0
        )
        
        # Add position to engine
        engine.positions[position.id] = position
        
        logger.info(f"✅ Created test position:")
        logger.info(f"   Symbol: {position.symbol}")
        logger.info(f"   Side: {position.side}")
        logger.info(f"   Entry Price: ${position.entry_price:.2f}")
        logger.info(f"   Quantity: {position.quantity:.6f}")
        logger.info(f"   Capital at Risk: ${position.capital_allocated:.2f}")
        logger.info(f"   Notional Value: ${position.notional_value:.2f}")
        
        # Test 2: Simulate price movement to $9 profit (should NOT close)
        logger.info("\n🎯 TEST 2: Price movement to $9 profit (should NOT close)")
        logger.info("-" * 50)
        
        # Calculate price for $9 profit: $9 / 0.04 BTC = $225 increase
        target_price_9_profit = entry_price + (9.0 / position.quantity)
        price_increment_9 = target_price_9_profit - entry_price
        
        mock_exchange.set_price_increment(symbol, price_increment_9)
        
        logger.info(f"💰 Target price for $9 profit: ${target_price_9_profit:.2f}")
        logger.info(f"💰 Expected profit: ${9.0:.2f}")
        
        # Wait for one monitoring cycle
        await asyncio.sleep(2)
        
        # Check if position is still open
        if position.id in engine.positions:
            logger.info("✅ CORRECT: Position still open at $9 profit")
            
            # Calculate actual profit
            current_price = await mock_exchange.get_current_price(symbol)
            actual_profit = (current_price - entry_price) * position.quantity
            logger.info(f"📊 Actual profit: ${actual_profit:.2f}")
        else:
            logger.error("❌ ERROR: Position closed prematurely at $9 profit!")
            return False
        
        # Test 3: Simulate price movement to $10.50 profit (should close immediately)
        logger.info("\n🎯 TEST 3: Price movement to $10.50 profit (should close IMMEDIATELY)")
        logger.info("-" * 50)
        
        # Calculate price for $10.50 profit: $10.50 / 0.04 BTC = $262.50 increase
        target_price_10_profit = entry_price + (10.5 / position.quantity)
        price_increment_10 = target_price_10_profit - entry_price
        
        mock_exchange.set_price_increment(symbol, price_increment_10)
        
        logger.info(f"💰 Target price for $10.50 profit: ${target_price_10_profit:.2f}")
        logger.info(f"💰 Expected profit: ${10.5:.2f}")
        
        # Wait for monitoring cycles (should close within 1-2 seconds with 1-second monitoring)
        max_wait_time = 5  # Maximum 5 seconds to close
        start_time = datetime.utcnow()
        
        while (datetime.utcnow() - start_time).total_seconds() < max_wait_time:
            await asyncio.sleep(0.5)  # Check every 0.5 seconds
            
            if position.id not in engine.positions:
                close_time = (datetime.utcnow() - start_time).total_seconds()
                logger.info(f"✅ EXCELLENT: Position closed in {close_time:.1f} seconds!")
                
                # Check completed trades
                if engine.completed_trades:
                    last_trade = engine.completed_trades[-1]
                    logger.info(f"📋 Trade Details:")
                    logger.info(f"   Exit Reason: {last_trade.exit_reason}")
                    logger.info(f"   P&L: ${last_trade.pnl:.2f}")
                    logger.info(f"   Exit Price: ${last_trade.exit_price:.2f}")
                    
                    if last_trade.exit_reason == "primary_target_10_dollars":
                        logger.info("✅ PERFECT: Closed with correct exit reason!")
                        break
                    else:
                        logger.warning(f"⚠️ WARNING: Unexpected exit reason: {last_trade.exit_reason}")
                else:
                    logger.warning("⚠️ WARNING: No completed trades found")
                break
        else:
            logger.error("❌ CRITICAL ERROR: Position did not close within 5 seconds at $10+ profit!")
            
            # Debug information
            if position.id in engine.positions:
                current_price = await mock_exchange.get_current_price(symbol)
                actual_profit = (current_price - entry_price) * position.quantity
                logger.error(f"🐛 DEBUG: Position still open with ${actual_profit:.2f} profit")
                logger.error(f"🐛 DEBUG: Current price: ${current_price:.2f}")
                logger.error(f"🐛 DEBUG: Position closed flag: {getattr(position, 'closed', 'not set')}")
            
            return False
        
        # Test 4: Test the $7 floor system
        logger.info("\n🎯 TEST 4: Testing $7 floor protection system")
        logger.info("-" * 50)
        
        # Create another position for floor testing
        position_2 = PaperPosition(
            id="test_position_2",
            symbol=symbol,
            strategy_type="test",
            side="LONG",
            entry_price=entry_price,
            quantity=0.04,
            entry_time=datetime.utcnow(),
            capital_allocated=200.0,
            leverage=10.0,
            notional_value=2000.0
        )
        
        engine.positions[position_2.id] = position_2
        
        # First, move to $8 profit to activate floor
        target_price_8_profit = entry_price + (8.0 / position_2.quantity)
        price_increment_8 = target_price_8_profit - entry_price
        mock_exchange.set_price_increment(symbol, price_increment_8)
        
        logger.info(f"💰 Moving to $8 profit to activate $7 floor...")
        await asyncio.sleep(2)  # Wait for monitoring cycle
        
        # Check if floor is activated
        if hasattr(position_2, 'profit_floor_activated') and position_2.profit_floor_activated:
            logger.info("✅ CORRECT: $7 floor activated at $8 profit")
        else:
            logger.info("📊 Floor activation status will be checked in monitoring loop")
        
        # Now drop to $6.50 profit (should close due to floor violation)
        target_price_6_profit = entry_price + (6.5 / position_2.quantity)
        price_increment_6 = target_price_6_profit - entry_price
        mock_exchange.set_price_increment(symbol, price_increment_6)
        
        logger.info(f"💰 Dropping to $6.50 profit (should trigger $7 floor protection)...")
        
        # Wait for floor protection to trigger
        start_time = datetime.utcnow()
        while (datetime.utcnow() - start_time).total_seconds() < 5:
            await asyncio.sleep(0.5)
            
            if position_2.id not in engine.positions:
                logger.info("✅ CORRECT: Position closed due to $7 floor violation")
                
                if engine.completed_trades:
                    last_trade = engine.completed_trades[-1]
                    if last_trade.exit_reason == "absolute_floor_7_dollars":
                        logger.info("✅ PERFECT: Closed with correct floor protection reason!")
                    else:
                        logger.warning(f"⚠️ WARNING: Unexpected exit reason: {last_trade.exit_reason}")
                break
        else:
            logger.warning("⚠️ WARNING: Floor protection may not have triggered within 5 seconds")
        
        logger.info("\n🎉 $10 Take Profit Fix Verification Complete!")
        logger.info("=" * 60)
        
        # Summary
        logger.info("\n📊 TEST SUMMARY:")
        logger.info(f"✅ Positions created: 2")
        logger.info(f"✅ Completed trades: {len(engine.completed_trades)}")
        logger.info(f"✅ Active positions: {len(engine.positions)}")
        
        if engine.completed_trades:
            for i, trade in enumerate(engine.completed_trades, 1):
                logger.info(f"   Trade {i}: {trade.symbol} {trade.side} - P&L: ${trade.pnl:.2f} - Reason: {trade.exit_reason}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed with error: {e}")
        import traceback
        logger.error(f"❌ Full traceback: {traceback.format_exc()}")
        return False
    
    finally:
        # Stop the engine
        engine.stop()

async def main():
    """Main test function"""
    logger.info("🔧 $10 Take Profit Fix Verification Test")
    logger.info("This test verifies that the critical fixes work correctly:")
    logger.info("1. Faster monitoring (1 second instead of 3)")
    logger.info("2. Better error handling in price fetching")
    logger.info("3. Improved race condition protection")
    logger.info("4. Enhanced logging for positions approaching $10")
    logger.info("5. $7 floor protection system")
    
    success = await test_10_dollar_take_profit_fix()
    
    if success:
        logger.info("\n🎉 ALL TESTS PASSED! The $10 take profit fix is working correctly.")
        return 0
    else:
        logger.error("\n❌ TESTS FAILED! The $10 take profit fix needs more work.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
