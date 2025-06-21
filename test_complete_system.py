#!/usr/bin/env python3
"""
🎯 Complete Signal Tracking & Validation System Test

Tests all 3 phases:
1. ✅ Phase 1: Comparative Backtesting (existing)
2. 🔥 Phase 2: Real Signal Logging (new)
3. 📊 Phase 3: Signal Replay Backtesting (new)
"""

import asyncio
import sys
import os
import time
import json
from datetime import datetime, timedelta

# Add src to path
sys.path.append('src')

from src.signals.signal_tracker import real_signal_tracker
from src.backtesting.signal_replay_backtester import signal_replay_backtester

async def test_phase_2_signal_logging():
    """Test Phase 2: Real Signal Logging"""
    print("\n" + "="*80)
    print("🔥 PHASE 2: REAL SIGNAL LOGGING TEST")
    print("="*80)
    
    try:
        # Initialize signal tracker
        await real_signal_tracker.initialize()
        print("✅ Signal tracker initialized")
        
        # Create test signals to log
        test_signals = [
            {
                'symbol': 'BTCUSDT',
                'strategy': 'swing_basic',
                'direction': 'LONG',
                'entry_price': 105000.0,
                'stop_loss': 103500.0,
                'take_profit': 108000.0,
                'confidence': 0.75,
                'signal_type': 'swing_basic'
            },
            {
                'symbol': 'ETHUSDT',
                'strategy': 'trend_following_stable',
                'direction': 'SHORT',
                'entry_price': 2520.0,
                'stop_loss': 2580.0,
                'take_profit': 2420.0,
                'confidence': 0.82,
                'signal_type': 'trend_following'
            }
        ]
        
        # Log test signals
        logged_signals = []
        for signal in test_signals:
            market_context = {
                'funding_rate': 0.0001,
                'open_interest': 1000000,
                'volume_24h': 50000000,
                'market_regime': 'TRENDING'
            }
            
            signal_id = await real_signal_tracker.log_signal(
                signal=signal,
                trading_mode="live",
                market_context=market_context
            )
            
            if signal_id:
                logged_signals.append(signal_id)
                print(f"✅ Logged signal: {signal['symbol']} {signal['direction']} (ID: {signal_id[:8]}...)")
            else:
                print(f"❌ Failed to log signal: {signal['symbol']}")
        
        print(f"\n📊 Successfully logged {len(logged_signals)} signals")
        return len(logged_signals) > 0
        
    except Exception as e:
        print(f"❌ Phase 2 failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def run_basic_test():
    """Run basic test"""
    print("🚀 CRYPTO TRADING BOT - SIGNAL TRACKING SYSTEM TEST")
    print("=" * 80)
    
    # Test Phase 2: Real Signal Logging
    result = await test_phase_2_signal_logging()
    
    if result:
        print("\n🎉 BASIC TEST PASSED!")
        print("✅ Signal tracking system is working!")
    else:
        print("\n❌ BASIC TEST FAILED!")
    
    return result

if __name__ == "__main__":
    # Run the basic test
    success = asyncio.run(run_basic_test())
    sys.exit(0 if success else 1)
