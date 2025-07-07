#!/usr/bin/env python3

import asyncio
import logging
import sys
import time

# Add the project root to Python path
sys.path.insert(0, '/home/ubuntu/crypto-trading-bot')

from src.trading.enhanced_paper_trading_engine import EnhancedPaperTradingEngine
from src.utils.config import load_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_paper_trading_with_signals():
    """Test paper trading with manual signal injection"""
    try:
        logger.info("🧪 Testing Paper Trading with Signal Generation...")
        
        # Load config
        config = load_config()
        paper_config = config.get('paper_trading', {}) if config else {}
        paper_config.setdefault('initial_balance', 10000.0)
        paper_config.setdefault('enabled', True)
        
        # Create paper trading engine
        engine = EnhancedPaperTradingEngine(
            config={'paper_trading': paper_config},
            exchange_client=None,  # Mock mode
            flow_trading_strategy='adaptive'
        )
        
        logger.info("✅ Paper trading engine created")
        
        # Start the engine
        await engine.start()
        logger.info("✅ Paper trading engine started")
        
        # Wait a moment for initialization
        await asyncio.sleep(2)
        
        # Generate test signals
        test_signals = [
            {
                'symbol': 'BTCUSDT',
                'strategy_type': 'flow_trading',
                'side': 'LONG',
                'confidence': 0.85,
                'ml_score': 0.80,
                'reason': 'strong_uptrend',
                'market_regime': 'trending',
                'volatility_regime': 'medium'
            },
            {
                'symbol': 'ETHUSDT',
                'strategy_type': 'flow_trading',
                'side': 'SHORT',
                'confidence': 0.75,
                'ml_score': 0.70,
                'reason': 'resistance_rejection',
                'market_regime': 'ranging',
                'volatility_regime': 'low'
            },
            {
                'symbol': 'ADAUSDT',
                'strategy_type': 'flow_trading',
                'side': 'LONG',
                'confidence': 0.90,
                'ml_score': 0.85,
                'reason': 'breakout_confirmed',
                'market_regime': 'trending',
                'volatility_regime': 'high'
            }
        ]
        
        # Execute test trades
        for i, signal in enumerate(test_signals):
            logger.info(f"🎯 Executing test trade {i+1}: {signal['symbol']} {signal['side']}")
            
            position_id = await engine.execute_trade(signal)
            if position_id:
                logger.info(f"✅ Trade {i+1} executed successfully: {position_id}")
            else:
                logger.warning(f"❌ Trade {i+1} failed")
            
            # Wait between trades
            await asyncio.sleep(1)
        
        # Check account status
        status = engine.get_account_status()
        logger.info(f"📊 Final Account Status:")
        logger.info(f"   Balance: ${status['account']['balance']:.2f}")
        logger.info(f"   Active Positions: {len(status['positions'])}")
        logger.info(f"   Total Trades: {status['account']['completed_trades']}")
        
        # List positions
        if status['positions']:
            logger.info("📈 Active Positions:")
            for pos in status['positions']:
                logger.info(f"   {pos['symbol']} {pos['side']} - Size: {pos['size']:.4f} - P&L: ${pos['unrealized_pnl']:.2f}")
        
        # Stop the engine
        engine.stop()
        logger.info("✅ Paper trading engine stopped")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_paper_trading_with_signals())
    if success:
        print("🎉 Paper trading with signals test PASSED")
    else:
        print("💥 Paper trading with signals test FAILED")
        sys.exit(1)
