#!/usr/bin/env python3
"""
Standalone test for paper trading engine
"""

import asyncio
import logging
from src.trading.enhanced_paper_trading_engine import EnhancedPaperTradingEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_paper_trading():
    """Test paper trading engine standalone"""
    try:
        logger.info("Testing paper trading engine initialization...")
        
        # Simple config
        config = {
            'paper_trading': {
                'initial_balance': 10000.0,
                'max_position_size_pct': 0.02,
                'max_total_exposure_pct': 0.10,
                'max_daily_loss_pct': 0.05,
                'enabled': True
            }
        }
        
        # Initialize engine without dependencies
        engine = EnhancedPaperTradingEngine(
            config=config,
            exchange_client=None,  # No exchange client
            opportunity_manager=None  # No opportunity manager
        )
        
        logger.info("✅ Paper trading engine created successfully")
        
        # Test starting the engine
        await engine.start()
        logger.info("✅ Paper trading engine started successfully")
        
        # Test account status
        status = engine.get_account_status()
        logger.info(f"Account status: {status['account']}")
        
        # Test executing a mock trade
        signal = {
            'symbol': 'BTCUSDT',
            'strategy_type': 'scalping',
            'side': 'LONG',
            'confidence': 0.8,
            'ml_score': 0.75,
            'reason': 'test_trade',
            'market_regime': 'trending',
            'volatility_regime': 'medium'
        }
        
        position_id = await engine.execute_trade(signal)
        if position_id:
            logger.info(f"✅ Test trade executed successfully: {position_id}")
        else:
            logger.error("❌ Test trade failed")
        
        # Test getting status again
        status = engine.get_account_status()
        logger.info(f"Updated account status: {status['account']}")
        logger.info(f"Positions: {len(status['positions'])}")
        
        # Stop engine
        engine.stop()
        logger.info("✅ Paper trading engine stopped successfully")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Paper trading test failed: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_paper_trading())
    if success:
        print("🎉 Paper trading engine test PASSED")
    else:
        print("💥 Paper trading engine test FAILED")
