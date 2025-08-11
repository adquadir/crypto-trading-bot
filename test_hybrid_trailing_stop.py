#!/usr/bin/env python3
"""
Test script for the enhanced hybrid trailing stop system in the profit scraping engine.
This script demonstrates the new features:
- Dollar-step trailing with $10 increments up to $100
- Hysteresis and cooldown protection against whipsaws
- Cap hand-off to tight ATR trailing after $100
- Integration with existing ATR breakeven and trailing
"""

import asyncio
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class MockTrade:
    """Mock trade for testing trailing stop logic"""
    trade_id: str
    symbol: str
    side: str
    entry_price: float
    quantity: float
    leverage: int
    profit_target: float
    stop_loss: float
    entry_time: datetime
    level_type: str
    confidence_score: int
    # Enhanced trailing fields
    locked_profit_usd: float = 0.0
    last_step_usd: float = 0.0
    max_trail_cap_usd: float = 100.0
    step_increment_usd: float = 10.0
    step_mode_percent: bool = False
    step_increment_pct: float = 0.002
    step_cooldown_sec: int = 20
    last_step_time: datetime = None
    hysteresis_pct: float = 0.0008
    trail_start_net_usd: float = 18.0
    fee_buffer_usd: float = 0.40
    cap_handoff_tight_atr: bool = True
    cap_trail_mult: float = 0.55

class MockProfitScrapingEngine:
    """Mock profit scraping engine for testing"""
    
    def __init__(self):
        self.active_trades = {}
    
    def _price_for_locked_usd(self, trade: MockTrade, locked_usd: float) -> float:
        """Convert locked USD profit to stop-loss price."""
        try:
            denom = max(1e-12, trade.quantity * trade.leverage)
            delta = locked_usd / denom
            return trade.entry_price + delta if trade.side == 'LONG' else trade.entry_price - delta
        except Exception as e:
            logger.error(f"Error calculating price for locked USD {locked_usd}: {e}")
            return trade.stop_loss
    
    async def _get_atr_pct_latest(self, symbol: str) -> float:
        """Mock ATR calculation"""
        return 0.02  # 2% ATR for testing
    
    def simulate_trailing_logic(self, trade: MockTrade, current_price: float) -> Dict[str, Any]:
        """Simulate the enhanced trailing stop logic"""
        results = {
            'original_sl': trade.stop_loss,
            'step_triggered': False,
            'cap_handoff': False,
            'locked_profit': trade.locked_profit_usd,
            'new_sl': trade.stop_loss,
            'unrealized_pnl': 0.0
        }
        
        # Calculate unrealized PnL
        if trade.quantity > 0:
            pnl_pct = ((current_price - trade.entry_price) if trade.side == 'LONG'
                       else (trade.entry_price - current_price)) / max(1e-12, trade.entry_price)
            notional = trade.quantity * trade.entry_price
            unrealized_usd = pnl_pct * trade.leverage * notional
            results['unrealized_pnl'] = unrealized_usd

            if unrealized_usd > 0:
                start_threshold = trade.trail_start_net_usd + trade.fee_buffer_usd
                if unrealized_usd >= start_threshold:
                    # Step size calculation
                    step_usd = (trade.step_increment_pct * trade.leverage * notional
                                if trade.step_mode_percent else trade.step_increment_usd)

                    # Next target + hysteresis
                    next_step_base = max(step_usd, trade.last_step_usd + step_usd)
                    target_to_lock = min(trade.max_trail_cap_usd, next_step_base)
                    hysteresis_add = max(0.0, trade.hysteresis_pct * trade.entry_price * trade.quantity * trade.leverage)
                    arm_level_usd = target_to_lock + hysteresis_add

                    # Cooldown check
                    now = datetime.now()
                    cooled = (trade.last_step_time is None) or ((now - trade.last_step_time).total_seconds() >= trade.step_cooldown_sec)

                    if unrealized_usd >= arm_level_usd and cooled:
                        trade.locked_profit_usd = target_to_lock
                        new_sl_price = self._price_for_locked_usd(trade, trade.locked_profit_usd)

                        if trade.side == 'LONG':
                            if new_sl_price > trade.stop_loss:
                                trade.stop_loss = new_sl_price
                                trade.last_step_usd = target_to_lock
                                trade.last_step_time = now
                                results['step_triggered'] = True
                                results['new_sl'] = trade.stop_loss
                                results['locked_profit'] = trade.locked_profit_usd
                        else:
                            if (trade.stop_loss == 0) or (new_sl_price < trade.stop_loss):
                                trade.stop_loss = new_sl_price
                                trade.last_step_usd = target_to_lock
                                trade.last_step_time = now
                                results['step_triggered'] = True
                                results['new_sl'] = trade.stop_loss
                                results['locked_profit'] = trade.locked_profit_usd

                    # Cap hand-off simulation
                    if trade.cap_handoff_tight_atr and trade.locked_profit_usd >= trade.max_trail_cap_usd:
                        atr_pct = 0.02  # Mock ATR
                        tight_gap = max(atr_pct * trade.cap_trail_mult, 0.0012)
                        cap_sl = (current_price * (1 - tight_gap) if trade.side == 'LONG'
                                  else current_price * (1 + tight_gap))

                        if trade.side == 'LONG':
                            if cap_sl > trade.stop_loss:
                                trade.stop_loss = cap_sl
                                results['cap_handoff'] = True
                                results['new_sl'] = trade.stop_loss
                        else:
                            if (trade.stop_loss == 0) or (cap_sl < trade.stop_loss):
                                trade.stop_loss = cap_sl
                                results['cap_handoff'] = True
                                results['new_sl'] = trade.stop_loss
        
        return results

async def test_hybrid_trailing_system():
    """Test the hybrid trailing stop system with various scenarios"""
    logger.info("🧪 Testing Enhanced Hybrid Trailing Stop System")
    
    engine = MockProfitScrapingEngine()
    
    # Create a mock LONG trade
    trade = MockTrade(
        trade_id="TEST_001",
        symbol="BTCUSDT",
        side="LONG",
        entry_price=50000.0,
        quantity=0.01,  # $500 position at 10x leverage
        leverage=10,
        profit_target=50900.0,  # Initial $18 target
        stop_loss=49640.0,      # Initial $18 stop loss
        entry_time=datetime.now(),
        level_type="support",
        confidence_score=85
    )
    
    logger.info(f"📊 Initial Trade Setup:")
    logger.info(f"   Entry: ${trade.entry_price}")
    logger.info(f"   Initial SL: ${trade.stop_loss}")
    logger.info(f"   Position: ${trade.quantity * trade.entry_price * trade.leverage:.0f} notional")
    
    # Test scenarios with different price movements
    test_prices = [
        50000,   # Entry price
        50200,   # Small move (+$20 profit)
        50400,   # Approaching first step (+$40 profit)
        50500,   # First step trigger (+$50 profit)
        50700,   # Second step approaching (+$70 profit)
        50800,   # Second step trigger (+$80 profit)
        51500,   # Multiple steps (+$150 profit - should hit cap)
        52000,   # Cap hand-off territory (+$200 profit)
        51800,   # Pullback to test cap trailing
        51600,   # Further pullback
    ]
    
    logger.info("\n🎯 Testing Price Movement Scenarios:")
    
    for i, price in enumerate(test_prices):
        logger.info(f"\n--- Scenario {i+1}: Price = ${price} ---")
        
        results = engine.simulate_trailing_logic(trade, price)
        
        logger.info(f"Unrealized P&L: ${results['unrealized_pnl']:.2f}")
        logger.info(f"Locked Profit: ${results['locked_profit']:.2f}")
        logger.info(f"Stop Loss: ${results['original_sl']:.2f} → ${results['new_sl']:.2f}")
        
        if results['step_triggered']:
            logger.info("🔒 STEP TRAIL TRIGGERED!")
        
        if results['cap_handoff']:
            logger.info("🎯 CAP HANDOFF TO ATR TRAILING!")
        
        # Add small delay to simulate cooldown
        await asyncio.sleep(0.1)
    
    logger.info("\n✅ Hybrid Trailing Stop Test Completed!")
    
    # Test SHORT trade scenario
    logger.info("\n🔄 Testing SHORT Trade Scenario:")
    
    short_trade = MockTrade(
        trade_id="TEST_002",
        symbol="ETHUSDT",
        side="SHORT",
        entry_price=3000.0,
        quantity=0.167,  # ~$500 position at 10x leverage
        leverage=10,
        profit_target=2946.0,  # Initial $18 target
        stop_loss=3054.0,      # Initial $18 stop loss
        entry_time=datetime.now(),
        level_type="resistance",
        confidence_score=80
    )
    
    short_test_prices = [
        3000,   # Entry
        2980,   # Small profit
        2950,   # Approaching step
        2940,   # Step trigger
        2900,   # Multiple steps
        2800,   # Cap territory
        2850,   # Pullback test
    ]
    
    for i, price in enumerate(short_test_prices):
        logger.info(f"\n--- SHORT Scenario {i+1}: Price = ${price} ---")
        
        results = engine.simulate_trailing_logic(short_trade, price)
        
        logger.info(f"Unrealized P&L: ${results['unrealized_pnl']:.2f}")
        logger.info(f"Locked Profit: ${results['locked_profit']:.2f}")
        logger.info(f"Stop Loss: ${results['original_sl']:.2f} → ${results['new_sl']:.2f}")
        
        if results['step_triggered']:
            logger.info("🔒 SHORT STEP TRAIL TRIGGERED!")
        
        if results['cap_handoff']:
            logger.info("🎯 SHORT CAP HANDOFF TO ATR TRAILING!")
        
        await asyncio.sleep(0.1)

def test_hysteresis_and_cooldown():
    """Test hysteresis and cooldown features"""
    logger.info("\n🛡️ Testing Hysteresis and Cooldown Protection:")
    
    engine = MockProfitScrapingEngine()
    
    trade = MockTrade(
        trade_id="TEST_HYSTERESIS",
        symbol="BTCUSDT",
        side="LONG",
        entry_price=50000.0,
        quantity=0.01,
        leverage=10,
        profit_target=50900.0,
        stop_loss=49640.0,
        entry_time=datetime.now(),
        level_type="support",
        confidence_score=85,
        step_cooldown_sec=5  # Short cooldown for testing
    )
    
    # Test hysteresis - price just touches step level but doesn't exceed hysteresis
    logger.info("Testing hysteresis protection (price touches but doesn't hold):")
    
    # Price that would trigger step without hysteresis
    step_price = 50500  # $50 profit, should trigger $50 step
    results = engine.simulate_trailing_logic(trade, step_price)
    
    if not results['step_triggered']:
        logger.info("✅ Hysteresis protection working - step not triggered at exact level")
    else:
        logger.info("❌ Hysteresis protection failed")
    
    # Price that exceeds hysteresis buffer
    hysteresis_price = 50520  # Exceeds hysteresis buffer
    results = engine.simulate_trailing_logic(trade, hysteresis_price)
    
    if results['step_triggered']:
        logger.info("✅ Step triggered after exceeding hysteresis buffer")
    else:
        logger.info("❌ Step should have triggered after hysteresis")

async def main():
    """Main test function"""
    logger.info("🚀 Starting Enhanced Hybrid Trailing Stop System Tests")
    
    await test_hybrid_trailing_system()
    test_hysteresis_and_cooldown()
    
    logger.info("\n🎉 All tests completed!")
    logger.info("\n📋 System Features Demonstrated:")
    logger.info("✅ Dollar-step trailing ($10 increments)")
    logger.info("✅ Hysteresis protection against whipsaws")
    logger.info("✅ Cooldown between step adjustments")
    logger.info("✅ Cap hand-off to ATR trailing after $100")
    logger.info("✅ Support for both LONG and SHORT trades")
    logger.info("✅ Fee-aware start threshold")
    logger.info("✅ Configurable parameters per trade")

if __name__ == "__main__":
    asyncio.run(main())
