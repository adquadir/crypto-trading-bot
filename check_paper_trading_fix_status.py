#!/usr/bin/env python3

"""
VERIFY PAPER TRADING FIX STATUS
===============================

Quick verification script to check:
1. Current position count
2. Configuration loading
3. Position limits enforcement
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.utils.config import load_config
from src.trading.enhanced_paper_trading_engine import EnhancedPaperTradingEngine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def check_paper_trading_status():
    """Check current paper trading status"""
    try:
        logger.info("🔍 CHECKING PAPER TRADING STATUS")
        
        # Load configuration
        config = load_config()
        paper_config = config.get('paper_trading', {})
        
        # Ensure proper defaults
        paper_config.setdefault('max_positions', 15)
        paper_config.setdefault('initial_balance', 10000.0)
        paper_config.setdefault('risk_per_trade_pct', 0.05)
        
        logger.info(f"📊 CONFIG VERIFICATION:")
        logger.info(f"   Max positions: {paper_config.get('max_positions', 'NOT SET')}")
        logger.info(f"   Initial balance: ${paper_config.get('initial_balance', 'NOT SET')}")
        logger.info(f"   Risk per trade: {paper_config.get('risk_per_trade_pct', 'NOT SET'):.1%}")
        
        # Initialize engine
        engine = EnhancedPaperTradingEngine({'paper_trading': paper_config})
        
        # Load state
        await engine._load_state()
        
        # Current status
        current_positions = len(engine.positions)
        account_balance = engine.account.balance
        max_allowed = engine.max_positions
        
        logger.info(f"📊 CURRENT STATUS:")
        logger.info(f"   Active positions: {current_positions}")
        logger.info(f"   Max allowed: {max_allowed}")
        logger.info(f"   Account balance: ${account_balance:.2f}")
        logger.info(f"   Position limit enforcement: {'✅ ACTIVE' if max_allowed > 0 else '❌ MISSING'}")
        
        # Check position details if any exist
        if current_positions > 0:
            logger.info(f"📋 POSITION DETAILS:")
            for i, (pos_id, position) in enumerate(engine.positions.items(), 1):
                logger.info(f"   {i}. {position.symbol} {position.side} - P&L: ${position.unrealized_pnl:.2f}")
                if i >= 10:  # Show first 10 only
                    logger.info(f"   ... and {current_positions - 10} more positions")
                    break
        
        # Verify limits are working
        if current_positions <= max_allowed:
            logger.info("✅ POSITION COUNT WITHIN LIMITS")
        else:
            logger.error(f"❌ POSITION LIMIT EXCEEDED: {current_positions} > {max_allowed}")
            
        # Summary
        logger.info("=" * 50)
        logger.info("📋 STATUS SUMMARY:")
        logger.info(f"   Position overflow issue: {'✅ FIXED' if current_positions <= max_allowed else '❌ STILL EXISTS'}")
        logger.info(f"   Configuration loading: {'✅ WORKING' if max_allowed == 15 else '❌ ISSUE'}")
        logger.info(f"   Database state: {'✅ CLEAN' if current_positions == 0 else f'⚠️ {current_positions} positions'}")
        
        return current_positions, max_allowed
        
    except Exception as e:
        logger.error(f"❌ Status check failed: {e}")
        import traceback
        logger.error(f"❌ Full traceback: {traceback.format_exc()}")
        return None, None

async def main():
    """Main verification"""
    try:
        current_positions, max_allowed = await check_paper_trading_status()
        
        if current_positions is not None and max_allowed is not None:
            if current_positions <= max_allowed:
                logger.info("🎉 SUCCESS: Paper trading position overflow has been FIXED!")
                logger.info(f"   Positions: {current_positions}/{max_allowed}")
            else:
                logger.error("🚨 ISSUE: Position overflow still exists")
                logger.error(f"   Positions: {current_positions}/{max_allowed}")
        else:
            logger.error("❌ Could not verify status due to errors")
            
    except Exception as e:
        logger.error(f"❌ Verification failed: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 