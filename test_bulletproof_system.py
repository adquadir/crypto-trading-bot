#!/usr/bin/env python3
"""
Test the direct initialization system (no fallbacks, no mocks)
"""

import asyncio
import sys
import os
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_exchange_client():
    """Test exchange client initialization"""
    try:
        from src.api.main import initialize_exchange_client
        
        logger.info("🔗 Testing exchange client...")
        exchange_client = await initialize_exchange_client()
        
        if exchange_client:
            logger.info("✅ Exchange client initialized successfully")
            logger.info(f"✅ Exchange client type: {type(exchange_client).__name__}")
            return True
        else:
            logger.error("❌ Exchange client is None")
            return False
            
    except Exception as e:
        logger.error(f"❌ Exchange client test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_strategy_manager():
    """Test strategy manager initialization"""
    try:
        from src.api.main import initialize_strategy_manager, initialize_exchange_client
        
        logger.info("🎯 Testing strategy manager...")
        
        # Need exchange client first
        exchange_client = await initialize_exchange_client()
        strategy_manager = await initialize_strategy_manager(exchange_client)
        
        if strategy_manager:
            logger.info("✅ Strategy manager initialized successfully")
            logger.info(f"✅ Strategy manager type: {type(strategy_manager).__name__}")
            return True
        else:
            logger.error("❌ Strategy manager is None")
            return False
            
    except Exception as e:
        logger.error(f"❌ Strategy manager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_paper_trading():
    """Test paper trading engine initialization"""
    try:
        from src.api.main import (
            initialize_exchange_client,
            initialize_opportunity_manager,
            initialize_profit_scraping_engine,
            initialize_paper_trading_engine,
            initialize_strategy_manager,
            initialize_risk_manager,
            initialize_signal_tracker
        )
        from src.utils.config import load_config
        
        logger.info("🚀 Testing paper trading engine...")
        
        # Initialize all dependencies
        config = load_config()
        exchange_client = await initialize_exchange_client()
        strategy_manager = await initialize_strategy_manager(exchange_client)
        risk_manager = await initialize_risk_manager(config)
        signal_tracker = await initialize_signal_tracker()
        opportunity_manager = await initialize_opportunity_manager(
            exchange_client, strategy_manager, risk_manager, signal_tracker
        )
        profit_scraping_engine = await initialize_profit_scraping_engine(exchange_client)
        
        # Initialize paper trading engine
        paper_trading_engine = await initialize_paper_trading_engine(
            config, exchange_client, opportunity_manager, profit_scraping_engine
        )
        
        if paper_trading_engine:
            logger.info("✅ Paper trading engine initialized successfully")
            logger.info(f"✅ Paper trading engine type: {type(paper_trading_engine).__name__}")
            
            # Test connections
            if hasattr(paper_trading_engine, 'opportunity_manager') and paper_trading_engine.opportunity_manager:
                logger.info("✅ Opportunity manager connected")
            if hasattr(paper_trading_engine, 'profit_scraping_engine') and paper_trading_engine.profit_scraping_engine:
                logger.info("✅ Profit scraping engine connected")
                
            return True
        else:
            logger.error("❌ Paper trading engine is None")
            return False
            
    except Exception as e:
        logger.error(f"❌ Paper trading engine test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_full_system():
    """Test the complete initialization system"""
    try:
        from src.api.main import initialize_components
        
        logger.info("🎉 Testing FULL system...")
        
        # This should initialize all components
        await initialize_components()
        
        logger.info("🎉 FULL SYSTEM TEST PASSED!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Full system test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all tests"""
    logger.info("🚀 Starting System Tests...")
    
    tests = [
        ("Exchange Client", test_exchange_client),
        ("Strategy Manager", test_strategy_manager),
        ("Paper Trading Engine", test_paper_trading),
        ("Full System", test_full_system)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        logger.info(f"\n{'='*50}")
        logger.info(f"🧪 Running {test_name} Test")
        logger.info(f"{'='*50}")
        
        try:
            result = await test_func()
            results.append((test_name, result))
            
            if result:
                logger.info(f"✅ {test_name} Test: PASSED")
            else:
                logger.error(f"❌ {test_name} Test: FAILED")
                
        except Exception as e:
            logger.error(f"❌ {test_name} Test: CRASHED - {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info(f"\n{'='*50}")
    logger.info("📊 SYSTEM TEST SUMMARY")
    logger.info(f"{'='*50}")
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"{test_name}: {status}")
        if result:
            passed += 1
    
    logger.info(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 ALL TESTS PASSED!")
        logger.info("🚀 System is ready for deployment!")
    else:
        logger.error("⚠️ Some tests failed - system needs fixes")
    
    return passed == total

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
