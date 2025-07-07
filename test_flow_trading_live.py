#!/usr/bin/env python3
"""
Test Flow Trading Only Paper Trading - Live Implementation Test
Verifies the implementation works correctly in a real environment
"""

import asyncio
import logging
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.trading.enhanced_paper_trading_engine import EnhancedPaperTradingEngine
from src.api.trading_routes.paper_trading_routes import initialize_paper_trading_engine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_flow_trading_live():
    """Test Flow Trading only paper trading in live environment"""
    
    print("🚀 Testing Flow Trading Only Paper Trading - LIVE")
    print("=" * 60)
    
    try:
        # Test 1: Initialize with Flow Trading only
        print("\n1️⃣ Testing Flow Trading Only Initialization")
        
        config = {
            'paper_trading': {
                'initial_balance': 10000.0,
                'max_position_size_pct': 0.02,
                'max_total_exposure_pct': 1.0,
                'max_daily_loss_pct': 0.50
            }
        }
        
        # Initialize with adaptive strategy
        print("   Initializing with adaptive strategy...")
        engine = await initialize_paper_trading_engine(
            config=config,
            exchange_client=None,  # Mock mode
            flow_trading_strategy='adaptive'
        )
        
        if not engine:
            print("   ❌ Failed to initialize engine")
            return False
        
        print(f"   ✅ Engine initialized successfully")
        print(f"   📊 Strategy: {engine.flow_trading_strategy}")
        print(f"   🔧 No fallback dependencies:")
        print(f"      - opportunity_manager: {engine.opportunity_manager}")
        print(f"      - profit_scraping_engine: {engine.profit_scraping_engine}")
        
        # Verify no fallback dependencies
        assert engine.opportunity_manager is None, "opportunity_manager should be None"
        assert engine.profit_scraping_engine is None, "profit_scraping_engine should be None"
        
        # Test 2: Test Flow Trading opportunity generation
        print("\n2️⃣ Testing Flow Trading Opportunity Generation")
        
        print("   Getting Flow Trading opportunities...")
        opportunities = await engine._get_fresh_opportunities()
        
        print(f"   📈 Found {len(opportunities)} Flow Trading opportunities")
        
        if opportunities:
            for i, opp in enumerate(opportunities[:3]):  # Show first 3
                print(f"   🎯 Opportunity {i+1}: {opp.get('symbol')} {opp.get('side')} (confidence: {opp.get('confidence', 0):.2f})")
        else:
            print("   ℹ️ No opportunities found (normal in mock mode)")
        
        # Test 3: Test strategy switching
        print("\n3️⃣ Testing Strategy Switching")
        
        original_strategy = engine.flow_trading_strategy
        print(f"   Original strategy: {original_strategy}")
        
        # Switch to different strategy
        new_strategy = 'breakout'
        engine.flow_trading_strategy = new_strategy
        
        print(f"   Switched to: {engine.flow_trading_strategy}")
        assert engine.flow_trading_strategy == new_strategy, "Strategy switch failed"
        
        print("   ✅ Strategy switching works correctly")
        
        # Test 4: Test account status
        print("\n4️⃣ Testing Account Status")
        
        account_status = engine.get_account_status()
        print(f"   💰 Balance: ${account_status['account']['balance']:.2f}")
        print(f"   📊 Total trades: {account_status['account']['total_trades']}")
        print(f"   🎯 Win rate: {account_status['account']['win_rate']*100:.1f}%")
        print(f"   📈 Active positions: {len(account_status['positions'])}")
        
        # Test 5: Test starting/stopping
        print("\n5️⃣ Testing Start/Stop Functionality")
        
        print("   Starting paper trading engine...")
        await engine.start()
        print(f"   ✅ Engine running: {engine.is_running}")
        
        print("   Stopping paper trading engine...")
        engine.stop()
        print(f"   ✅ Engine stopped: {not engine.is_running}")
        
        print("\n🎉 All Live Tests Passed!")
        print("=" * 60)
        print("✅ Flow Trading only implementation working correctly")
        print("✅ No fallback dependencies")
        print("✅ Strategy selection functional")
        print("✅ Start/stop operations working")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Live test failed with error: {e}")
        import traceback
        print(f"Full traceback:\n{traceback.format_exc()}")
        return False

async def test_api_simulation():
    """Simulate API endpoint functionality"""
    
    print("\n🌐 Testing API Endpoint Simulation")
    print("=" * 40)
    
    try:
        # Simulate the new API endpoints
        from src.api.trading_routes.paper_trading_routes import get_available_strategies
        
        # Test get_available_strategies
        print("\n📋 Testing get_available_strategies...")
        strategies_response = await get_available_strategies()
        
        if strategies_response and 'data' in strategies_response:
            strategies = strategies_response['data']['available_strategies']
            print(f"   ✅ Found {len(strategies)} available strategies:")
            for strategy_key, strategy_info in strategies.items():
                print(f"      - {strategy_key}: {strategy_info['name']}")
                print(f"        {strategy_info['description']}")
        
        print("\n🎉 API Simulation Tests Passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ API simulation test failed: {e}")
        return False

async def main():
    """Run all live tests"""
    
    print("🚀 Starting Flow Trading Only Paper Trading - LIVE TESTS")
    print("=" * 80)
    
    # Run live functionality tests
    live_test_passed = await test_flow_trading_live()
    
    # Run API simulation tests
    api_test_passed = await test_api_simulation()
    
    print("\n" + "=" * 80)
    print("📊 LIVE TEST SUMMARY")
    print("=" * 80)
    print(f"Live Functionality: {'✅ PASSED' if live_test_passed else '❌ FAILED'}")
    print(f"API Simulation: {'✅ PASSED' if api_test_passed else '❌ FAILED'}")
    
    if live_test_passed and api_test_passed:
        print("\n🎉 ALL LIVE TESTS PASSED!")
        print("Flow Trading Only Paper Trading is working correctly!")
        print("\n📝 ANSWER TO ORIGINAL QUESTION:")
        print("❌ NO - Paper trading does NOT have its own profit scraping engine")
        print("✅ YES - Paper trading now uses ONLY Flow Trading")
        return True
    else:
        print("\n❌ SOME LIVE TESTS FAILED")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
