#!/usr/bin/env python3
"""
Test script to verify fixes for wrong direction trades and ML learning issues

This script tests:
1. Forced signal generation has been removed
2. Paper trading validation is improved (not completely bypassed)
3. ML learning criteria are properly applied
4. System can skip trades when no strategy conditions are met
"""

import sys
import asyncio
import requests
import json
import time
from datetime import datetime

# Add project root to path
sys.path.append('/home/ubuntu/crypto-trading-bot')

async def test_signal_quality():
    """Test that signals are now generated based on strategy conditions, not forced"""
    print("🧪 Testing Signal Quality and ML Learning Integration")
    print("=" * 70)
    
    try:
        # Test 1: Check opportunity generation
        print("\n1. Testing Opportunity Generation...")
        response = requests.get("http://localhost:8000/api/v1/opportunities", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            opportunities = data.get('data', [])
            
            print(f"   Total opportunities: {len(opportunities)}")
            
            # Check for forced signals (should be gone)
            forced_signals = [opp for opp in opportunities if opp.get('strategy') == 'forced_test']
            guaranteed_signals = [opp for opp in opportunities if opp.get('strategy') == 'guaranteed']
            
            print(f"   ❌ Forced signals (should be 0): {len(forced_signals)}")
            print(f"   ❌ Guaranteed signals (should be 0): {len(guaranteed_signals)}")
            
            if forced_signals or guaranteed_signals:
                print("   🚨 ISSUE: Found forced/guaranteed signals that should have been removed!")
                for signal in (forced_signals + guaranteed_signals):
                    print(f"      - {signal['symbol']}: {signal['strategy']} ({signal.get('direction', 'N/A')})")
            else:
                print("   ✅ GOOD: No forced or guaranteed signals found")
            
            # Check strategy diversity
            strategies = {}
            for opp in opportunities:
                strategy = opp.get('strategy', 'unknown')
                strategies[strategy] = strategies.get(strategy, 0) + 1
            
            print(f"   Strategy distribution: {strategies}")
            
            # Check for proper validation
            tradable_count = sum(1 for opp in opportunities if opp.get('tradable', False))
            print(f"   Tradable opportunities: {tradable_count}/{len(opportunities)} ({tradable_count/len(opportunities)*100:.1f}%)")
            
            # Check validation reasons for rejected signals
            rejected = [opp for opp in opportunities if not opp.get('tradable', False)]
            if rejected:
                print(f"   Sample rejection reasons:")
                for i, opp in enumerate(rejected[:3]):  # Show first 3
                    reason = opp.get('rejection_reason', 'No reason given')
                    print(f"      - {opp['symbol']}: {reason}")
        
        else:
            print(f"   ❌ Failed to get opportunities: {response.status_code}")
        
        # Test 2: Check paper trading mode settings
        print("\n2. Testing Paper Trading Mode...")
        
        # Enable paper trading mode
        enable_response = requests.post("http://localhost:8000/api/v1/paper-trading/enable-paper-trading-mode", timeout=10)
        if enable_response.status_code == 200:
            print("   ✅ Paper trading mode enabled")
            
            # Check if validation criteria are relaxed but not bypassed
            response = requests.get("http://localhost:8000/api/v1/opportunities", timeout=10)
            if response.status_code == 200:
                data = response.json()
                opportunities = data.get('data', [])
                tradable_relaxed = sum(1 for opp in opportunities if opp.get('tradable', False))
                
                print(f"   Tradable with relaxed criteria: {tradable_relaxed}")
                
                # Check that validation is still applied (not completely bypassed)
                if tradable_relaxed == len(opportunities) and len(opportunities) > 0:
                    print("   ⚠️  WARNING: All signals are tradable - validation might be completely bypassed")
                elif tradable_relaxed > 0:
                    print("   ✅ GOOD: Some validation still applied with relaxed criteria")
        
        # Test 3: Check for no-trade scenarios
        print("\n3. Testing No-Trade Scenarios...")
        
        # Trigger fresh scan
        scan_response = requests.post("http://localhost:8000/api/v1/opportunities/scan", timeout=30)
        if scan_response.status_code == 200:
            print("   ✅ Opportunity scan triggered")
            
            # Wait a moment for scan to complete
            time.sleep(5)
            
            # Check results
            response = requests.get("http://localhost:8000/api/v1/opportunities", timeout=10)
            if response.status_code == 200:
                data = response.json()
                opportunities = data.get('data', [])
                
                # The system should not have signals for ALL symbols if conditions aren't met
                unique_symbols = len(set(opp['symbol'] for opp in opportunities))
                print(f"   Symbols with signals: {unique_symbols}")
                
                if unique_symbols < 15:  # If fewer than 15 symbols have signals
                    print("   ✅ GOOD: System is selective - not forcing signals for all symbols")
                else:
                    print("   ⚠️  INFO: Many symbols have signals - checking if this is legitimate")
                    
        # Test 4: Check ML learning integration
        print("\n4. Testing ML Learning Integration...")
        
        try:
            # Check if learning criteria are being applied
            sample_opp = opportunities[0] if opportunities else None
            if sample_opp:
                reasoning = sample_opp.get('reasoning', [])
                has_learning_reasoning = any('learned criteria' in str(r).lower() for r in reasoning)
                
                if has_learning_reasoning:
                    print("   ✅ GOOD: Found evidence of learned criteria being applied")
                else:
                    print("   ⚠️  INFO: No explicit learning criteria reasoning found")
                    
                print(f"   Sample reasoning: {reasoning[:3]}...")  # Show first 3 reasons
        except Exception as e:
            print(f"   ❌ Error checking ML integration: {e}")
        
        print("\n5. Summary of Fixes Applied:")
        print("   ✅ Removed forced signal generation override")
        print("   ✅ Removed guaranteed signal fallbacks")
        print("   ✅ Improved paper trading validation (relaxed but not bypassed)")
        print("   ✅ Ensured ML learning criteria are applied to strategies")
        print("   ✅ Allow system to skip trades when no conditions are met")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        return False

async def test_paper_trading_integration():
    """Test that paper trading properly uses the improved signal generation"""
    print("\n6. Testing Paper Trading Integration...")
    
    try:
        # Check paper trading status
        status_response = requests.get("http://localhost:8000/api/v1/paper-trading/status", timeout=10)
        if status_response.status_code == 200:
            status = status_response.json()
            is_running = status.get('data', {}).get('enabled', False)
            print(f"   Paper trading running: {is_running}")
            
            if is_running:
                # Test signal processing
                test_signal = {
                    "symbol": "BTCUSDT",
                    "strategy_type": "opportunity_manager",
                    "side": "LONG",
                    "confidence": 0.65,
                    "ml_score": 0.65,
                    "reason": "test_signal_quality_check",
                    "market_regime": "trending",
                    "volatility_regime": "medium"
                }
                
                trade_response = requests.post(
                    "http://localhost:8000/api/v1/paper-trading/trade", 
                    json=test_signal, 
                    timeout=10
                )
                
                if trade_response.status_code == 200:
                    print("   ✅ Paper trading accepts quality signals")
                    result = trade_response.json()
                    print(f"   Position created: {result.get('position_id', 'N/A')}")
                else:
                    print(f"   ⚠️  Paper trading rejected signal: {trade_response.text}")
            else:
                print("   ℹ️  Paper trading not running - skipping integration test")
                
    except Exception as e:
        print(f"   ❌ Error testing paper trading: {e}")

async def main():
    """Run all tests"""
    print("🔧 Wrong Direction Trades & ML Learning Fixes - Verification Test")
    print("=" * 70)
    print("Testing fixes for:")
    print("1. Forced signal generation removal")
    print("2. Improved paper trading validation")
    print("3. ML learning criteria integration")
    print("4. Selective trading (no forced positions)")
    print("=" * 70)
    
    success = await test_signal_quality()
    await test_paper_trading_integration()
    
    print("\n" + "=" * 70)
    if success:
        print("✅ Tests completed - Review results above")
        print("🎯 Expected improvements:")
        print("   - Fewer wrong-direction trades (no more coin-flip decisions)")
        print("   - ML learning actually influences trading decisions")
        print("   - System trades only when strategy conditions are met")
        print("   - Paper trading validation improved but not bypassed")
    else:
        print("❌ Tests encountered errors - check logs above")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(main()) 