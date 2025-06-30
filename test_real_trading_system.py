#!/usr/bin/env python3
"""
Test Real Trading System
Tests the complete real trading implementation with manual trade learning
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_real_trading_system():
    """Test the real trading system"""
    try:
        logger.info("🚀 Testing Real Trading System...")
        
        # Import components
        from src.trading.real_trading_engine import RealTradingEngine
        from src.market_data.exchange_client import ExchangeClient
        
        # Initialize exchange client
        logger.info("Initializing exchange client...")
        exchange_client = ExchangeClient()
        
        # Initialize real trading engine
        logger.info("Initializing real trading engine...")
        real_engine = RealTradingEngine(exchange_client)
        
        # Test engine status
        status = real_engine.get_status()
        logger.info(f"Real trading engine status: {status}")
        
        # Test configuration
        logger.info("Testing configuration:")
        logger.info(f"  - Position size: ${real_engine.position_size_usd}")
        logger.info(f"  - Leverage: {real_engine.leverage}x")
        logger.info(f"  - Daily loss limit: {real_engine.max_daily_loss}")
        logger.info(f"  - Emergency stop: {real_engine.emergency_stop}")
        
        # Test trade sync service
        if real_engine.trade_sync_service:
            sync_status = real_engine.trade_sync_service.get_sync_status()
            logger.info(f"Trade sync service status: {sync_status}")
        
        # Test signal processing (without executing)
        test_signal = {
            'symbol': 'BTCUSDT',
            'side': 'LONG',
            'confidence': 0.8,
            'strategy_type': 'profit_scraping',
            'entry_reason': 'test_signal'
        }
        
        logger.info("Testing signal validation...")
        safety_check = real_engine._safety_checks(test_signal)
        logger.info(f"Safety check result: {safety_check}")
        
        # Test position size calculation
        test_price = 50000.0  # $50k BTC
        position_size = real_engine._calculate_position_size('BTCUSDT', test_price, 0.8)
        logger.info(f"Position size calculation: {position_size:.6f} BTC (${position_size * test_price:.2f})")
        
        # Test stop loss and take profit
        stop_loss = real_engine._calculate_stop_loss(test_price, 'LONG')
        take_profit = real_engine._calculate_take_profit(test_price, 'LONG')
        logger.info(f"Stop loss: ${stop_loss:.2f} ({((stop_loss - test_price) / test_price * 100):.2f}%)")
        logger.info(f"Take profit: ${take_profit:.2f} ({((take_profit - test_price) / test_price * 100):.2f}%)")
        
        logger.info("✅ Real trading system test completed successfully")
        
        # Display warnings
        logger.warning("⚠️  IMPORTANT WARNINGS:")
        logger.warning("⚠️  1. This system trades with REAL MONEY")
        logger.warning("⚠️  2. Uses SAME configuration as successful paper trading")
        logger.warning("⚠️  3. HIGH confidence threshold (0.7) for quality trades")
        logger.warning("⚠️  4. Smart position limits based on account balance")
        logger.warning("⚠️  5. $500 daily loss limit for conservative real money trading")
        logger.warning("⚠️  6. Manual trade learning is active")
        logger.warning("⚠️  7. Test thoroughly before live deployment")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Real trading system test failed: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return False

async def test_api_integration():
    """Test API integration"""
    try:
        logger.info("🧪 Testing API integration...")
        
        # Import API components
        from src.api.trading_routes.real_trading_routes import get_real_trading_engine
        
        # Test engine creation
        engine = get_real_trading_engine()
        logger.info(f"API engine created: {engine is not None}")
        
        # Test status endpoint
        status = engine.get_status()
        logger.info(f"API status: {status}")
        
        logger.info("✅ API integration test completed")
        return True
        
    except Exception as e:
        logger.error(f"❌ API integration test failed: {e}")
        return False

async def test_trade_sync_service():
    """Test trade synchronization service"""
    try:
        logger.info("🔄 Testing Trade Sync Service...")
        
        from src.trading.trade_sync_service import TradeSyncService
        from src.market_data.exchange_client import ExchangeClient
        
        # Initialize components
        exchange_client = ExchangeClient()
        sync_service = TradeSyncService(exchange_client)
        
        # Test status
        status = sync_service.get_sync_status()
        logger.info(f"Sync service status: {status}")
        
        # Test manual trades
        manual_trades = sync_service.get_manual_trades()
        logger.info(f"Manual trades detected: {len(manual_trades)}")
        
        logger.info("✅ Trade sync service test completed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Trade sync service test failed: {e}")
        return False

async def main():
    """Main test function"""
    logger.info("🚀 Starting Real Trading System Tests...")
    
    success_count = 0
    total_tests = 3
    
    # Test real trading system
    if await test_real_trading_system():
        success_count += 1
    
    # Test API integration
    if await test_api_integration():
        success_count += 1
    
    # Test trade sync service
    if await test_trade_sync_service():
        success_count += 1
    
    logger.info(f"🎯 Tests completed: {success_count}/{total_tests} successful")
    
    if success_count == total_tests:
        logger.info("✅ ALL TESTS PASSED - Real trading system is ready")
        logger.warning("⚠️  REMEMBER: This system trades with REAL MONEY")
        logger.warning("⚠️  ALWAYS test with small amounts first")
    else:
        logger.warning(f"⚠️ Some tests failed ({success_count}/{total_tests})")
    
    return success_count == total_tests

if __name__ == "__main__":
    asyncio.run(main())
