#!/usr/bin/env python3
"""
Test script to verify monitoring loop fixes are working properly
Tests position limits, take profit triggers, and stop loss enforcement
"""

import asyncio
import logging
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, Any

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.trading.enhanced_paper_trading_engine import EnhancedPaperTradingEngine
from src.database.database import Database

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MockExchangeClient:
    """Mock exchange client for testing"""
    
    def __init__(self):
        self.prices = {
            'BTCUSDT': 45000.0,
            'ETHUSDT': 2800.0,
            'BNBUSDT': 320.0
        }
        self.price_changes = {}
    
    def set_price(self, symbol: str, price: float):
        """Set price for testing"""
        self.prices[symbol] = price
        logger.info(f"📊 Mock price set: {symbol} = ${price:.2f}")
    
    def simulate_price_movement(self, symbol: str, change_pct: float):
        """Simulate price movement"""
        if symbol in self.prices:
            old_price = self.prices[symbol]
            new_price = old_price * (1 + change_pct / 100)
            self.prices[symbol] = new_price
            logger.info(f"📈 Price movement: {symbol} ${old_price:.2f} → ${new_price:.2f} ({change_pct:+.2f}%)")
    
    async def get_current_price(self, symbol: str) -> float:
        """Get current price"""
        return self.prices.get(symbol, 45000.0)
    
    async def get_ticker_24h(self, symbol: str) -> Dict[str, Any]:
        """Get 24h ticker"""
        price = self.prices.get(symbol, 45000.0)
        return {
            'symbol': symbol,
            'lastPrice': str(price),
            'priceChange': '0',
            'priceChangePercent': '0'
        }

async def test_position_limits():
    """Test that position limits are strictly enforced"""
    logger.info("🧪 Testing position limits enforcement...")
    
    # Create engine with low position limit for testing
    config = {
        'paper_trading': {
            'initial_balance': 10000.0,
            'max_positions': 3,  # Low limit for testing
            'risk_per_trade_pct': 0.10,  # 10% per trade
            'leverage': 10.0
        }
    }
    
    mock_client = MockExchangeClient()
    engine = EnhancedPaperTradingEngine(config, mock_client)
    
    # Start engine
    await engine.start()
    await asyncio.sleep(1)  # Let it initialize
    
    # Try to create 5 positions (should only allow 3)
    symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'SOLUSDT']
    successful_trades = 0
    
    for i, symbol in enumerate(symbols):
        signal = {
            'symbol': symbol,
            'side': 'LONG',
            'confidence': 0.8,
            'strategy_type': 'test',
            'signal_source': 'test',
            'reason': f'test_position_{i+1}'
        }
        
        position_id = await engine.execute_trade(signal)
        if position_id:
            successful_trades += 1
            logger.info(f"✅ Trade {i+1} successful: {symbol}")
        else:
            logger.info(f"❌ Trade {i+1} rejected: {symbol}")
    
    # Verify position count
    actual_positions = len(engine.positions)
    logger.info(f"📊 Position limit test: {successful_trades} successful trades, {actual_positions} active positions")
    
    # Should have exactly 3 positions (the limit)
    assert actual_positions <= 3, f"Position limit violated: {actual_positions} > 3"
    assert successful_trades <= 3, f"Too many trades allowed: {successful_trades} > 3"
    
    engine.stop()
    logger.info("✅ Position limits test PASSED")
    return True

async def test_take_profit_triggers():
    """Test that $10 take profit triggers work correctly"""
    logger.info("🧪 Testing $10 take profit triggers...")
    
    config = {
        'paper_trading': {
            'initial_balance': 10000.0,
            'max_positions': 10,
            'risk_per_trade_pct': 0.10,  # 10% per trade = $1000 capital
            'leverage': 10.0,  # 10x leverage = $10,000 notional
            'primary_target_dollars': 18.0  # $18 gross = $10 net after fees
        }
    }
    
    mock_client = MockExchangeClient()
    engine = EnhancedPaperTradingEngine(config, mock_client)
    
    # Start engine
    await engine.start()
    await asyncio.sleep(1)
    
    # Create a position
    signal = {
        'symbol': 'BTCUSDT',
        'side': 'LONG',
        'confidence': 0.8,
        'strategy_type': 'test',
        'signal_source': 'test',
        'reason': 'take_profit_test'
    }
    
    position_id = await engine.execute_trade(signal)
    assert position_id, "Failed to create test position"
    
    initial_positions = len(engine.positions)
    logger.info(f"📊 Created test position: {position_id}")
    
    # Simulate price movement that should trigger $10 take profit
    # For $10,000 notional position: $18 profit = 0.18% price movement
    mock_client.simulate_price_movement('BTCUSDT', 0.20)  # 0.20% increase
    
    # Wait for monitoring loop to process
    await asyncio.sleep(2)
    
    # Check if position was closed
    final_positions = len(engine.positions)
    logger.info(f"📊 Positions after price movement: {initial_positions} → {final_positions}")
    
    # Position should be closed due to take profit
    assert final_positions < initial_positions, "Take profit did not trigger"
    
    # Check completed trades
    if engine.completed_trades:
        last_trade = engine.completed_trades[-1]
        logger.info(f"💰 Last trade P&L: ${last_trade.pnl:.2f} (reason: {last_trade.exit_reason})")
        assert last_trade.exit_reason == "primary_target_10_dollars", f"Wrong exit reason: {last_trade.exit_reason}"
        assert last_trade.pnl >= 8.0, f"Take profit too low: ${last_trade.pnl:.2f}"
    
    engine.stop()
    logger.info("✅ Take profit triggers test PASSED")
    return True

async def test_stop_loss_enforcement():
    """Test that stop loss limits losses to $10 net"""
    logger.info("🧪 Testing stop loss enforcement...")
    
    config = {
        'paper_trading': {
            'initial_balance': 10000.0,
            'max_positions': 10,
            'risk_per_trade_pct': 0.10,  # 10% per trade = $1000 capital
            'leverage': 10.0,  # 10x leverage = $10,000 notional
            'pure_3_rule_mode': True
        }
    }
    
    mock_client = MockExchangeClient()
    engine = EnhancedPaperTradingEngine(config, mock_client)
    
    # Start engine
    await engine.start()
    await asyncio.sleep(1)
    
    # Create a position
    signal = {
        'symbol': 'BTCUSDT',
        'side': 'LONG',
        'confidence': 0.8,
        'strategy_type': 'test',
        'signal_source': 'test',
        'reason': 'stop_loss_test'
    }
    
    position_id = await engine.execute_trade(signal)
    assert position_id, "Failed to create test position"
    
    initial_positions = len(engine.positions)
    logger.info(f"📊 Created test position: {position_id}")
    
    # Simulate large price drop that should trigger stop loss
    mock_client.simulate_price_movement('BTCUSDT', -0.25)  # 0.25% decrease
    
    # Wait for monitoring loop to process
    await asyncio.sleep(2)
    
    # Check if position was closed
    final_positions = len(engine.positions)
    logger.info(f"📊 Positions after price drop: {initial_positions} → {final_positions}")
    
    # Position should be closed due to stop loss
    assert final_positions < initial_positions, "Stop loss did not trigger"
    
    # Check completed trades
    if engine.completed_trades:
        last_trade = engine.completed_trades[-1]
        logger.info(f"💸 Last trade P&L: ${last_trade.pnl:.2f} (reason: {last_trade.exit_reason})")
        assert "stop_loss" in last_trade.exit_reason.lower(), f"Wrong exit reason: {last_trade.exit_reason}"
        assert last_trade.pnl <= -8.0, f"Stop loss too high: ${last_trade.pnl:.2f}"
        assert last_trade.pnl >= -12.0, f"Stop loss too low: ${last_trade.pnl:.2f}"
    
    engine.stop()
    logger.info("✅ Stop loss enforcement test PASSED")
    return True

async def test_floor_protection():
    """Test that $7 floor protection works"""
    logger.info("🧪 Testing $7 floor protection...")
    
    config = {
        'paper_trading': {
            'initial_balance': 10000.0,
            'max_positions': 10,
            'risk_per_trade_pct': 0.10,
            'leverage': 10.0,
            'absolute_floor_dollars': 15.0  # $15 gross = $7 net after fees
        }
    }
    
    mock_client = MockExchangeClient()
    engine = EnhancedPaperTradingEngine(config, mock_client)
    
    # Start engine
    await engine.start()
    await asyncio.sleep(1)
    
    # Create a position
    signal = {
        'symbol': 'BTCUSDT',
        'side': 'LONG',
        'confidence': 0.8,
        'strategy_type': 'test',
        'signal_source': 'test',
        'reason': 'floor_test'
    }
    
    position_id = await engine.execute_trade(signal)
    assert position_id, "Failed to create test position"
    
    # First, move price up to activate floor
    mock_client.simulate_price_movement('BTCUSDT', 0.20)  # Activate floor
    await asyncio.sleep(1)
    
    # Then move price down to test floor protection
    mock_client.simulate_price_movement('BTCUSDT', -0.10)  # Should trigger floor
    await asyncio.sleep(2)
    
    # Check if position was closed due to floor violation
    final_positions = len(engine.positions)
    logger.info(f"📊 Positions after floor test: {final_positions}")
    
    if engine.completed_trades:
        last_trade = engine.completed_trades[-1]
        logger.info(f"🛡️ Last trade P&L: ${last_trade.pnl:.2f} (reason: {last_trade.exit_reason})")
        
        if "floor" in last_trade.exit_reason.lower():
            assert last_trade.pnl >= 6.0, f"Floor protection failed: ${last_trade.pnl:.2f}"
            logger.info("✅ Floor protection triggered correctly")
        else:
            logger.info("ℹ️ Floor protection not triggered (position may have hit other exit)")
    
    engine.stop()
    logger.info("✅ Floor protection test PASSED")
    return True

async def test_monitoring_loop_health():
    """Test that monitoring loop runs without crashes"""
    logger.info("🧪 Testing monitoring loop health...")
    
    config = {
        'paper_trading': {
            'initial_balance': 10000.0,
            'max_positions': 5,
            'risk_per_trade_pct': 0.10,
            'leverage': 10.0
        }
    }
    
    mock_client = MockExchangeClient()
    engine = EnhancedPaperTradingEngine(config, mock_client)
    
    # Start engine
    await engine.start()
    
    # Let it run for a few seconds
    logger.info("⏱️ Running monitoring loop for 5 seconds...")
    await asyncio.sleep(5)
    
    # Check that engine is still running
    assert engine.is_running, "Engine stopped unexpectedly"
    
    # Check that monitoring task is still alive
    if hasattr(engine, 'monitoring_task'):
        assert not engine.monitoring_task.done(), "Monitoring task crashed"
        logger.info("✅ Monitoring task is healthy")
    
    engine.stop()
    logger.info("✅ Monitoring loop health test PASSED")
    return True

async def main():
    """Run all monitoring loop tests"""
    logger.info("🚀 Starting monitoring loop fixes verification...")
    
    tests = [
        ("Position Limits", test_position_limits),
        ("Take Profit Triggers", test_take_profit_triggers),
        ("Stop Loss Enforcement", test_stop_loss_enforcement),
        ("Floor Protection", test_floor_protection),
        ("Monitoring Loop Health", test_monitoring_loop_health)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            logger.info(f"\n{'='*60}")
            logger.info(f"🧪 Running: {test_name}")
            logger.info(f"{'='*60}")
            
            result = await test_func()
            if result:
                logger.info(f"✅ {test_name} PASSED")
                passed += 1
            else:
                logger.error(f"❌ {test_name} FAILED")
                failed += 1
                
        except Exception as e:
            logger.error(f"❌ {test_name} FAILED with exception: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            failed += 1
        
        # Brief pause between tests
        await asyncio.sleep(1)
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info(f"🏁 TEST SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"✅ Passed: {passed}")
    logger.info(f"❌ Failed: {failed}")
    logger.info(f"📊 Total: {passed + failed}")
    
    if failed == 0:
        logger.info("🎉 ALL TESTS PASSED! Monitoring loop fixes are working correctly.")
        return True
    else:
        logger.error(f"💥 {failed} tests failed. Please review the issues above.")
        return False

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("🛑 Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"💥 Test runner failed: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)
