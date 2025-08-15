#!/usr/bin/env python3
"""
Test script to verify directional accuracy fixes
"""

import asyncio
import logging
import time
from src.opportunity.opportunity_manager import OpportunityManager
from src.market_data.exchange_client import ExchangeClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_direction_normalization():
    """Test that all directions are properly normalized to LONG/SHORT"""
    logger.info("Testing direction normalization...")
    
    # Create mock opportunity manager
    exchange_client = ExchangeClient()
    om = OpportunityManager(exchange_client, None, None)
    
    # Test various direction labels
    test_opportunities = [
        {"symbol": "BTCUSDT", "direction": "BUY", "entry_price": 50000, "take_profit": 51000, "stop_loss": 49000},
        {"symbol": "ETHUSDT", "direction": "SELL", "entry_price": 3000, "take_profit": 2900, "stop_loss": 3100},
        {"symbol": "ADAUSDT", "direction": "BULL", "entry_price": 1.0, "take_profit": 1.05, "stop_loss": 0.95},
        {"symbol": "SOLUSDT", "direction": "BEAR", "entry_price": 100, "take_profit": 95, "stop_loss": 105},
    ]
    
    for opp in test_opportunities:
        original_direction = opp["direction"]
        finalized = om._finalize_and_stamp(opp.copy())
        
        if finalized:
            final_direction = finalized["direction"]
            logger.info(f"Direction normalization: {original_direction} -> {final_direction}")
            
            # Verify it's either LONG or SHORT
            assert final_direction in ["LONG", "SHORT"], f"Invalid direction: {final_direction}"
            
            # Verify TP/SL are on correct sides
            entry = finalized["entry_price"]
            tp = finalized["take_profit"]
            sl = finalized["stop_loss"]
            
            if final_direction == "LONG":
                assert tp > entry, f"LONG TP should be above entry: {tp} vs {entry}"
                assert sl < entry, f"LONG SL should be below entry: {sl} vs {entry}"
            else:  # SHORT
                assert tp < entry, f"SHORT TP should be below entry: {tp} vs {entry}"
                assert sl > entry, f"SHORT SL should be above entry: {sl} vs {entry}"
    
    logger.info("✅ Direction normalization tests passed!")

async def test_debounce_logic():
    """Test that direction changes are properly debounced"""
    logger.info("Testing debounce logic...")
    
    exchange_client = ExchangeClient()
    om = OpportunityManager(exchange_client, None, None)
    
    # Set up initial opportunity
    om.opportunities["BTCUSDT"] = {
        "direction": "LONG",
        "signal_timestamp": time.time(),
        "entry_price": 50000
    }
    
    # Test rapid direction change (should be rejected)
    should_accept = om._should_accept_flip("BTCUSDT", "SHORT", momentum=0.0005)
    assert not should_accept, "Should reject rapid direction flip"
    
    # Test direction change after sufficient time
    om.opportunities["BTCUSDT"]["signal_timestamp"] = time.time() - 70  # 70 seconds ago
    should_accept = om._should_accept_flip("BTCUSDT", "SHORT", momentum=0.002)
    assert should_accept, "Should accept direction flip after sufficient time"
    
    logger.info("✅ Debounce logic tests passed!")

async def main():
    """Run all tests"""
    try:
        await test_direction_normalization()
        await test_debounce_logic()
        logger.info("🎉 All directional accuracy tests passed!")
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return False
    return True

if __name__ == "__main__":
    asyncio.run(main())
