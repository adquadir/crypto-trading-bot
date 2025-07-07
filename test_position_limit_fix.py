#!/usr/bin/env python3
"""
Test the position limit fix - ensure no unlimited positions are created
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.trading.enhanced_paper_trading_engine import EnhancedPaperTradingEngine

async def test_position_limit_enforcement():
    """Test that position limits are properly enforced"""
    print("🧪 Testing Position Limit Enforcement")
    print("=" * 50)
    
    # Create paper trading engine with small position limit for testing
    config = {
        'paper_trading': {
            'initial_balance': 10000.0,
            'risk_per_trade_pct': 0.02,  # 2% of balance per trade
            'max_positions': 3,  # Small limit for testing
            'leverage': 10.0,
            'enabled': True
        }
    }
    
    engine = EnhancedPaperTradingEngine(config)
    
    print(f"Initial setup:")
    print(f"- Balance: ${engine.account.balance:,.2f}")
    print(f"- Max positions: {engine.max_positions}")
    print(f"- Risk per trade: {engine.risk_per_trade_pct:.1%}")
    print(f"- Leverage: {engine.leverage}x")
    
    # Test signals to simulate trading
    test_signals = [
        {'symbol': 'BTCUSDT', 'side': 'LONG', 'confidence': 0.8, 'strategy_type': 'test', 'reason': 'test_signal_1'},
        {'symbol': 'ETHUSDT', 'side': 'LONG', 'confidence': 0.8, 'strategy_type': 'test', 'reason': 'test_signal_2'},
        {'symbol': 'BNBUSDT', 'side': 'LONG', 'confidence': 0.8, 'strategy_type': 'test', 'reason': 'test_signal_3'},
        {'symbol': 'ADAUSDT', 'side': 'LONG', 'confidence': 0.8, 'strategy_type': 'test', 'reason': 'test_signal_4'},  # Should be rejected
        {'symbol': 'SOLUSDT', 'side': 'LONG', 'confidence': 0.8, 'strategy_type': 'test', 'reason': 'test_signal_5'},  # Should be rejected
    ]
    
    print(f"\n🎯 Testing Position Creation:")
    successful_positions = 0
    rejected_positions = 0
    
    for i, signal in enumerate(test_signals, 1):
        print(f"\nAttempt {i}: {signal['symbol']} {signal['side']}")
        
        # Try to execute trade
        position_id = await engine.execute_trade(signal)
        
        if position_id:
            successful_positions += 1
            print(f"✅ Position created: {position_id}")
            print(f"   Current positions: {len(engine.positions)}")
        else:
            rejected_positions += 1
            print(f"❌ Position rejected (limits reached)")
            print(f"   Current positions: {len(engine.positions)}")
    
    print(f"\n📊 Test Results:")
    print(f"✅ Successful positions: {successful_positions}")
    print(f"❌ Rejected positions: {rejected_positions}")
    print(f"📈 Total positions: {len(engine.positions)}")
    print(f"🎯 Max allowed: {engine.max_positions}")
    
    # Verify the fix worked
    if len(engine.positions) <= engine.max_positions:
        print(f"\n🎉 SUCCESS: Position limit properly enforced!")
        print(f"   Expected: ≤ {engine.max_positions} positions")
        print(f"   Actual: {len(engine.positions)} positions")
        
        if successful_positions == engine.max_positions and rejected_positions > 0:
            print(f"✅ Perfect: Exactly {engine.max_positions} positions created, excess rejected")
        else:
            print(f"⚠️ Note: {successful_positions} created, {rejected_positions} rejected")
    else:
        print(f"\n❌ FAILURE: Position limit NOT enforced!")
        print(f"   Expected: ≤ {engine.max_positions} positions")
        print(f"   Actual: {len(engine.positions)} positions")
    
    # Show position details
    print(f"\n📋 Active Positions:")
    for pos_id, position in engine.positions.items():
        print(f"   {position.symbol} {position.side} @ ${position.entry_price:.2f} (Capital: ${position.capital_allocated:.2f})")
    
    print(f"\n💰 Account Status:")
    print(f"   Balance: ${engine.account.balance:.2f}")
    print(f"   Total allocated: ${sum(pos.capital_allocated for pos in engine.positions.values()):.2f}")
    print(f"   Available: ${engine.account.balance - sum(pos.capital_allocated for pos in engine.positions.values()):.2f}")

if __name__ == "__main__":
    asyncio.run(test_position_limit_enforcement())
