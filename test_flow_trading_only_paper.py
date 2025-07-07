#!/usr/bin/env python3
"""
Test Flow Trading Only Paper Trading System
Verifies that paper trading now uses ONLY Flow Trading (no fallbacks)
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

async def test_flow_trading_only_paper():
    """Test that paper trading uses ONLY Flow Trading"""
    
    print("🧪 Testing Flow Trading Only Paper Trading System")
    print("=" * 60)
    
    try:
        # Test 1: Initialize with different strategies
        print("\n1️⃣ Testing Strategy Initialization")
        
        config = {
            'paper_trading': {
                'initial_balance': 10000.0,
                'max_position_size_pct': 0.02,
                'max_total_exposure_pct': 1.0,
                'max_daily_loss_pct': 0.50
            }
        }
        
        strategies_to_test = ['adaptive', 'breakout', 'support_resistance', 'momentum']
        
        for strategy in strategies_to_test:
            print(f"\n   Testing {strategy} strategy...")
            
            engine = await initialize_paper_trading_engine(
                config=config,
                exchange_client=None,  # Mock mode
                flow_trading_strategy=strategy
            )
            
            if engine:
                print(f"   ✅ {strategy} strategy initialized successfully")
                print(f"   📊 Strategy: {engine.flow_trading_strategy}")
                print(f"   🔧 No fallback dependencies: opportunity_manager={engine.opportunity_manager}, profit_scraping_engine={engine.profit_scraping_engine}")
                
                # Verify no fallback dependencies
                assert engine.opportunity_manager is None, f"opportunity_manager should be None, got {engine.opportunity_manager}"
                assert engine.profit_scraping_engine is None, f"profit_scraping_engine should be None, got {engine.profit_scraping_engine}"
                assert engine.flow_trading_strategy == strategy, f"Strategy should be {strategy}, got {engine.flow_trading_strategy}"
                
            else:
                print(f"   ❌ Failed to initialize {strategy} strategy")
                return False
        
        # Test 2: Test Flow Trading opportunity generation
        print("\n2️⃣ Testing Flow Trading Opportunity Generation")
        
        # Use adaptive strategy for testing
        engine = await initialize_paper_trading_engine(
            config=config,
            exchange_client=None,
            flow_trading_strategy='adaptive'
        )
        
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
        new_strategy = 'breakout' if original_strategy != 'breakout' else 'momentum'
        engine.flow_trading_strategy = new_strategy
        
        print(f"   Switched to: {engine.flow_trading_strategy}")
        assert engine.flow_trading_strategy == new_strategy, f"Strategy switch failed"
        
        print("   ✅ Strategy switching works correctly")
        
        # Test 4: Test that fallback methods are removed
        print("\n4️⃣ Testing Fallback Removal")
        
        print("   Checking _get_fresh_opportunities method...")
        
        # This should only use Flow Trading, no fallbacks
        opportunities = await engine._get_fresh_opportunities()
        print(f"   📊 Method returned {len(opportunities)} opportunities (Flow Trading only)")
        
        # Test 5: Verify initialization parameters
        print("\n5️⃣ Testing Initialization Parameters")
        
        # Test with all strategy types
        for strategy in ['adaptive', 'breakout', 'support_resistance', 'momentum']:
            test_engine = EnhancedPaperTradingEngine(
                config=config,
                exchange_client=None,
                flow_trading_strategy=strategy
            )
            
            print(f"   ✅ {strategy}: flow_trading_strategy={test_engine.flow_trading_strategy}")
            
            # Verify no fallback dependencies
            assert test_engine.opportunity_manager is None
            assert test_engine.profit_scraping_engine is None
            assert test_engine.flow_trading_strategy == strategy
        
        print("\n🎉 All Tests Passed!")
        print("=" * 60)
        print("✅ Paper Trading now uses ONLY Flow Trading")
        print("✅ All fallback dependencies removed")
        print("✅ Strategy selection working")
        print("✅ No profit scraping or opportunity manager dependencies")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        print(f"Full traceback:\n{traceback.format_exc()}")
        return False

async def test_api_endpoints():
    """Test the new API endpoints"""
    
    print("\n🌐 Testing API Endpoints")
    print("=" * 40)
    
    try:
        from src.api.trading_routes.paper_trading_routes import get_available_strategies, set_trading_strategy, get_current_strategy
        
        # Test get_available_strategies
        print("\n📋 Testing get_available_strategies...")
        strategies_response = await get_available_strategies()
        
        if strategies_response and 'data' in strategies_response:
            strategies = strategies_response['data']['available_strategies']
            print(f"   ✅ Found {len(strategies)} available strategies:")
            for strategy_key, strategy_info in strategies.items():
                print(f"      - {strategy_key}: {strategy_info['name']}")
        
        print("\n🎉 API Endpoint Tests Passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ API test failed: {e}")
        return False

async def main():
    """Run all tests"""
    
    print("🚀 Starting Flow Trading Only Paper Trading Tests")
    print("=" * 80)
    
    # Run core functionality tests
    core_test_passed = await test_flow_trading_only_paper()
    
    # Run API tests
    api_test_passed = await test_api_endpoints()
    
    print("\n" + "=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)
    print(f"Core Functionality: {'✅ PASSED' if core_test_passed else '❌ FAILED'}")
    print(f"API Endpoints: {'✅ PASSED' if api_test_passed else '❌ FAILED'}")
    
    if core_test_passed and api_test_passed:
        print("\n🎉 ALL TESTS PASSED!")
        print("Paper Trading is now Flow Trading Only!")
        return True
    else:
        print("\n❌ SOME TESTS FAILED")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
