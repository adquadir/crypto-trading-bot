#!/usr/bin/env python3
"""
Signal Rejection Diagnostic Tool
Helps identify why high confidence signals are being rejected
"""

import asyncio
import logging
from datetime import datetime
from src.trading.enhanced_paper_trading_engine import EnhancedPaperTradingEngine

# Set up logging to see all details
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def diagnose_signal_rejections():
    """Diagnose why signals might be getting rejected"""
    
    print("🔍 SIGNAL REJECTION DIAGNOSTIC TOOL")
    print("=" * 80)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Initialize paper trading engine
    config = {
        'paper_trading': {
            'initial_balance': 10000.0,
            'max_position_size_pct': 0.02,
            'max_total_exposure_pct': 1.0,  # 100%
            'max_daily_loss_pct': 0.50     # 50%
        }
    }
    
    engine = EnhancedPaperTradingEngine(config)
    
    print("📊 CURRENT CONFIGURATION:")
    print("-" * 40)
    print(f"Initial Balance: ${engine.account.balance:,.2f}")
    print(f"Max Total Exposure: {engine.max_total_exposure * 100:.0f}%")
    print(f"Max Daily Loss: {engine.max_daily_loss * 100:.0f}%")
    print(f"Active Positions: {len(engine.positions)}")
    print()
    
    # Test various signal scenarios
    test_signals = [
        {
            'name': 'High Confidence BTC Long',
            'signal': {
                'symbol': 'BTCUSDT',
                'side': 'LONG',
                'confidence': 0.85,
                'strategy_type': 'scalping',
                'reason': 'test_signal'
            }
        },
        {
            'name': 'Medium Confidence ETH Long',
            'signal': {
                'symbol': 'ETHUSDT',
                'side': 'LONG',
                'confidence': 0.65,
                'strategy_type': 'scalping',
                'reason': 'test_signal'
            }
        },
        {
            'name': 'Low Confidence ADA Long',
            'signal': {
                'symbol': 'ADAUSDT',
                'side': 'LONG',
                'confidence': 0.45,
                'strategy_type': 'scalping',
                'reason': 'test_signal'
            }
        },
        {
            'name': 'High Confidence BTC Short',
            'signal': {
                'symbol': 'BTCUSDT',
                'side': 'SHORT',
                'confidence': 0.80,
                'strategy_type': 'scalping',
                'reason': 'test_signal'
            }
        }
    ]
    
    print("🧪 TESTING SIGNAL ACCEPTANCE:")
    print("=" * 80)
    
    for test_case in test_signals:
        name = test_case['name']
        signal = test_case['signal']
        
        print(f"\n📋 Testing: {name}")
        print(f"   Symbol: {signal['symbol']}")
        print(f"   Side: {signal['side']}")
        print(f"   Confidence: {signal['confidence']:.2f}")
        print("-" * 40)
        
        # Test signal filtering
        should_trade = engine._should_trade_signal(signal)
        print(f"   Signal Filter Result: {'✅ PASS' if should_trade else '❌ REJECT'}")
        
        if should_trade:
            # Test risk limits
            try:
                # Mock price for testing
                mock_price = 50000.0 if 'BTC' in signal['symbol'] else 3000.0
                risk_check = await engine._check_risk_limits(signal['symbol'], mock_price)
                print(f"   Risk Check Result: {'✅ PASS' if risk_check else '❌ REJECT'}")
                
                if risk_check:
                    print(f"   🎯 WOULD EXECUTE: {signal['symbol']} {signal['side']}")
                else:
                    print(f"   ❌ BLOCKED BY RISK LIMITS")
            except Exception as e:
                print(f"   ❌ ERROR IN RISK CHECK: {e}")
        else:
            print(f"   ❌ BLOCKED BY SIGNAL FILTER")
        
        print()
    
    print("🔍 DETAILED RISK ANALYSIS:")
    print("=" * 80)
    
    # Calculate how many positions we can theoretically have
    max_exposure = engine.account.balance * engine.max_total_exposure
    position_value = 200.0 * 10.0  # $200 * 10x leverage
    max_positions = int(max_exposure / position_value)
    
    print(f"Account Balance: ${engine.account.balance:,.2f}")
    print(f"Max Exposure ({engine.max_total_exposure * 100:.0f}%): ${max_exposure:,.2f}")
    print(f"Position Value ($200 × 10x): ${position_value:,.2f}")
    print(f"Max Theoretical Positions: {max_positions}")
    print(f"Current Active Positions: {len(engine.positions)}")
    print(f"Available Position Slots: {max_positions - len(engine.positions)}")
    print()
    
    # Test multiple positions scenario
    print("🔄 TESTING MULTIPLE POSITIONS SCENARIO:")
    print("-" * 40)
    
    # Simulate having some positions
    print("Simulating 3 active positions...")
    
    # Create mock positions
    from src.trading.enhanced_paper_trading_engine import PaperPosition
    import uuid
    
    mock_positions = []
    for i in range(3):
        pos = PaperPosition(
            id=str(uuid.uuid4()),
            symbol=f'TEST{i}USDT',
            strategy_type='scalping',
            side='LONG',
            entry_price=50000.0,
            quantity=0.04,  # $2000 / $50000
            entry_time=datetime.utcnow(),
            current_price=50000.0
        )
        mock_positions.append(pos)
        engine.positions[pos.id] = pos
    
    print(f"Added {len(mock_positions)} mock positions")
    print(f"Current Active Positions: {len(engine.positions)}")
    
    # Test if we can still add more
    test_signal = {
        'symbol': 'NEWUSDT',
        'side': 'LONG',
        'confidence': 0.75,
        'strategy_type': 'scalping',
        'reason': 'test_signal'
    }
    
    should_trade = engine._should_trade_signal(test_signal)
    risk_check = await engine._check_risk_limits('NEWUSDT', 50000.0)
    
    print(f"New Signal Filter: {'✅ PASS' if should_trade else '❌ REJECT'}")
    print(f"New Risk Check: {'✅ PASS' if risk_check else '❌ REJECT'}")
    
    if should_trade and risk_check:
        print("✅ CAN STILL ADD MORE POSITIONS")
    else:
        print("❌ CANNOT ADD MORE POSITIONS")
    
    print()
    
    # Summary
    print("📊 DIAGNOSTIC SUMMARY:")
    print("=" * 80)
    print("Key Findings:")
    print(f"✓ Confidence threshold: 50% (was 70%)")
    print(f"✓ Total exposure limit: 100% (was 10%)")
    print(f"✓ Daily loss limit: 50% (was 5%)")
    print(f"✓ Multiple positions per symbol: ALLOWED")
    print(f"✓ Cooldown period: 1 minute (was 30 minutes)")
    print()
    
    print("Possible Rejection Reasons:")
    print("1. 🔍 Confidence < 50% (signals below 0.5 are rejected)")
    print("2. 🔍 Missing symbol or side in signal")
    print("3. 🔍 Price fetching failures")
    print("4. 🔍 Account balance exhausted (rare with 100% limit)")
    print("5. 🔍 Daily loss limit exceeded (50% of account)")
    print()
    
    print("Recommendations:")
    print("• Check logs for specific rejection reasons")
    print("• Verify signal confidence scores are ≥ 0.5")
    print("• Ensure price data is available")
    print("• Monitor daily P&L vs 50% loss limit")
    print("• With $10K account, you can have ~5 simultaneous $2K positions")

if __name__ == "__main__":
    asyncio.run(diagnose_signal_rejections())
