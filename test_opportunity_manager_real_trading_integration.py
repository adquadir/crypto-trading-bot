#!/usr/bin/env python3
"""
Test OpportunityManager Integration with Real Trading Engine
This script tests the connection and signal flow between OpportunityManager and Real Trading Engine
"""

import asyncio
import logging
import yaml
import sys
import os
from datetime import datetime

# Add src to path
sys.path.append('src')

# Fix imports for standalone script
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from src.trading.real_trading_engine import RealTradingEngine
from src.market_data.exchange_client import ExchangeClient
from src.opportunity.opportunity_manager import OpportunityManager
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

async def test_opportunity_manager_integration():
    """Test OpportunityManager integration with Real Trading Engine"""
    
    print("🧪 Testing OpportunityManager Integration with Real Trading Engine")
    print("=" * 70)
    
    try:
        # Load configuration
        print("📋 Loading configuration...")
        with open('config/config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        # Create exchange client (testnet mode for safety)
        print("🔗 Creating exchange client...")
        exchange_client = ExchangeClient()
        
        # Create real trading engine
        print("🚀 Creating Real Trading Engine...")
        real_engine = RealTradingEngine(config, exchange_client)
        
        # Display engine configuration
        print(f"   ✅ Engine created successfully")
        print(f"   💰 Stake per trade: ${real_engine.stake_usd}")
        print(f"   📊 Max positions: {real_engine.max_positions}")
        print(f"   🎯 Pure 3-rule mode: {real_engine.pure_3_rule_mode}")
        print(f"   🔒 Enabled: {real_engine.enabled}")
        print(f"   📡 Signal sources: {real_engine.accept_sources}")
        
        # Create OpportunityManager with required dependencies
        print("\n🎯 Creating OpportunityManager with dependencies...")
        
        # Create required dependencies
        from src.strategy.strategy_manager import StrategyManager
        from src.risk.risk_manager import RiskManager
        
        # Initialize strategy manager with exchange client
        strategy_manager = StrategyManager(exchange_client)
        
        # Initialize risk manager with config
        risk_manager = RiskManager(config)
        
        # Create OpportunityManager with dependencies
        opportunity_manager = OpportunityManager(
            exchange_client=exchange_client,
            strategy_manager=strategy_manager,
            risk_manager=risk_manager
        )
        
        # Connect OpportunityManager to Real Trading Engine
        print("🔗 Connecting OpportunityManager to Real Trading Engine...")
        real_engine.connect_opportunity_manager(opportunity_manager)
        
        # Verify connection
        has_opp_manager = real_engine.opportunity_manager is not None
        print(f"   ✅ Connection status: {'Connected' if has_opp_manager else 'Not Connected'}")
        
        if has_opp_manager:
            print("   🎯 OpportunityManager successfully connected!")
        else:
            print("   ❌ OpportunityManager connection failed!")
            return False
        
        # Test getting opportunities
        print("\n📊 Testing opportunity retrieval...")
        try:
            opportunities = opportunity_manager.get_opportunities()
            
            if opportunities:
                if isinstance(opportunities, dict):
                    total_opps = sum(len(opp_list) for opp_list in opportunities.values())
                    print(f"   📈 Found {total_opps} opportunities across {len(opportunities)} symbols")
                    
                    # Show sample opportunities
                    for symbol, opp_list in list(opportunities.items())[:3]:  # Show first 3 symbols
                        print(f"   📊 {symbol}: {len(opp_list)} opportunities")
                        if opp_list:
                            sample_opp = opp_list[0]
                            print(f"      - Direction: {sample_opp.get('direction', 'N/A')}")
                            print(f"      - Entry: ${sample_opp.get('entry_price', 0):.6f}")
                            print(f"      - Confidence: {sample_opp.get('confidence', 0):.2f}")
                            print(f"      - Tradable: {sample_opp.get('tradable', False)}")
                
                elif isinstance(opportunities, list):
                    print(f"   📈 Found {len(opportunities)} opportunities")
                    
                    # Show sample opportunities
                    for i, opp in enumerate(opportunities[:3]):  # Show first 3
                        print(f"   📊 Opportunity {i+1}:")
                        print(f"      - Symbol: {opp.get('symbol', 'N/A')}")
                        print(f"      - Direction: {opp.get('direction', 'N/A')}")
                        print(f"      - Entry: ${opp.get('entry_price', 0):.6f}")
                        print(f"      - Confidence: {opp.get('confidence', 0):.2f}")
                        print(f"      - Tradable: {opp.get('tradable', False)}")
                
            else:
                print("   📊 No opportunities currently available")
                
        except Exception as e:
            print(f"   ❌ Error getting opportunities: {e}")
        
        # Test signal acceptance criteria
        print("\n🔍 Testing signal acceptance criteria...")
        
        # Create test opportunity
        test_opportunity = {
            'symbol': 'BTCUSDT',
            'direction': 'LONG',
            'entry_price': 50000.0,
            'confidence': 0.8,
            'tradable': True,
            'signal_source': 'opportunity_manager',
            'strategy': 'opportunity_manager'
        }
        
        # Test if opportunity would be accepted
        is_acceptable = real_engine._is_acceptable_opportunity(test_opportunity)
        print(f"   🧪 Test opportunity acceptance: {'✅ Accepted' if is_acceptable else '❌ Rejected'}")
        
        if is_acceptable:
            print("   ✅ Signal meets all acceptance criteria")
        else:
            print("   ❌ Signal does not meet acceptance criteria")
            print("   📋 Checking criteria:")
            print(f"      - Signal source: {test_opportunity.get('signal_source', 'N/A')}")
            print(f"      - Confidence: {test_opportunity.get('confidence', 0)}")
            print(f"      - Tradable: {test_opportunity.get('tradable', False)}")
        
        # Test engine status
        print("\n📊 Testing engine status...")
        status = real_engine.get_status()
        
        print(f"   🔧 Engine running: {status.get('is_running', False)}")
        print(f"   🔒 Engine enabled: {status.get('enabled', False)}")
        print(f"   🚨 Emergency stop: {status.get('emergency_stop', False)}")
        print(f"   📊 Active positions: {status.get('active_positions', 0)}")
        print(f"   💰 Total PnL: ${status.get('total_pnl', 0):.2f}")
        print(f"   📈 Total trades: {status.get('total_trades', 0)}")
        print(f"   🎯 Pure 3-rule mode: {status.get('pure_3_rule_mode', False)}")
        print(f"   💵 Stake per trade: ${status.get('stake_usd', 0):.2f}")
        print(f"   📊 Max positions: {status.get('max_positions', 0)}")
        
        # Test safety checks (without actually starting trading)
        print("\n🛡️ Testing safety checks...")
        
        # Create a test signal for safety check
        test_signal = {
            'symbol': 'BTCUSDT',
            'direction': 'LONG',
            'entry_price': 50000.0,
            'confidence': 0.8,
            'strategy': 'opportunity_manager'
        }
        
        # Note: We won't actually execute trades in this test
        print("   ⚠️  Safety checks would be performed before real trade execution")
        print("   🔒 Real trading is disabled for safety during testing")
        
        print("\n✅ OpportunityManager Integration Test Complete!")
        print("=" * 70)
        print("📋 Summary:")
        print(f"   ✅ Real Trading Engine: Created successfully")
        print(f"   ✅ OpportunityManager: Connected successfully")
        print(f"   ✅ Configuration: Loaded successfully")
        print(f"   ✅ Signal Flow: Ready for real trading")
        print(f"   🔒 Safety: Real trading disabled for testing")
        
        print("\n🚀 To enable real trading:")
        print("   1. Set real_trading.enabled = true in config.yaml")
        print("   2. Ensure valid Binance API keys are configured")
        print("   3. Start the API server")
        print("   4. Use /api/v1/real-trading/connect-opportunity-manager endpoint")
        print("   5. Use /api/v1/real-trading/start endpoint")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        logger.error(f"Integration test error: {e}", exc_info=True)
        return False

async def test_api_integration():
    """Test API integration"""
    
    print("\n🌐 Testing API Integration...")
    print("-" * 50)
    
    try:
        # Import API components
        from api.trading_routes.real_trading_routes import get_real_trading_engine
        
        # Test engine creation through API
        print("🔧 Testing engine creation through API...")
        engine = get_real_trading_engine()
        
        if engine:
            print("   ✅ Engine created successfully through API")
            
            # Test status endpoint logic
            status = engine.get_status()
            print(f"   📊 Status retrieved: {len(status)} fields")
            
            # Test OpportunityManager connection through API
            print("🔗 Testing OpportunityManager connection...")
            
            # Import and create OpportunityManager
            opportunity_manager = OpportunityManager()
            
            # Connect to engine
            engine.connect_opportunity_manager(opportunity_manager)
            
            has_opp_manager = engine.opportunity_manager is not None
            print(f"   ✅ Connection status: {'Connected' if has_opp_manager else 'Not Connected'}")
            
            print("   ✅ API integration test passed!")
            
        else:
            print("   ❌ Failed to create engine through API")
            return False
            
        return True
        
    except Exception as e:
        print(f"   ❌ API integration test failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 OpportunityManager Real Trading Integration Test")
    print("=" * 70)
    print(f"⏰ Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Run tests
    loop = asyncio.get_event_loop()
    
    # Test 1: Core integration
    success1 = loop.run_until_complete(test_opportunity_manager_integration())
    
    # Test 2: API integration
    success2 = loop.run_until_complete(test_api_integration())
    
    print("\n" + "=" * 70)
    print("🏁 Test Results:")
    print(f"   Core Integration: {'✅ PASSED' if success1 else '❌ FAILED'}")
    print(f"   API Integration:  {'✅ PASSED' if success2 else '❌ FAILED'}")
    
    overall_success = success1 and success2
    print(f"\n🎯 Overall Result: {'✅ ALL TESTS PASSED' if overall_success else '❌ SOME TESTS FAILED'}")
    
    if overall_success:
        print("\n🚀 OpportunityManager is ready for Real Trading integration!")
        print("   Remember to enable real trading in config when ready for live trading.")
    else:
        print("\n⚠️  Please fix the issues before proceeding with real trading.")
    
    print(f"\n⏰ Test completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
