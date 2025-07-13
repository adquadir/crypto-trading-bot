#!/usr/bin/env python3
"""
Test Corrected Stop Loss Calculation
Verify that the new stop loss calculation properly limits losses to $10
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.trading.enhanced_paper_trading_engine import EnhancedPaperTradingEngine

async def test_stop_loss_calculation():
    """Test the corrected stop loss calculation"""
    
    print("🧪 TESTING CORRECTED STOP LOSS CALCULATION")
    print("=" * 60)
    
    # Create a test engine instance
    config = {
        'paper_trading': {
            'initial_balance': 10000.0,
            'risk_per_trade_pct': 0.02,  # 2% = $200 per trade
            'leverage': 10.0,  # 10x leverage
            'max_positions': 50
        }
    }
    
    engine = EnhancedPaperTradingEngine(config)
    
    # Test scenarios with different prices
    test_scenarios = [
        {'symbol': 'BTCUSDT', 'price': 50000.0, 'side': 'LONG'},
        {'symbol': 'ETHUSDT', 'price': 3000.0, 'side': 'LONG'},
        {'symbol': 'BNBUSDT', 'price': 300.0, 'side': 'SHORT'},
        {'symbol': 'ADAUSDT', 'price': 0.5, 'side': 'LONG'},
        {'symbol': 'SOLUSDT', 'price': 100.0, 'side': 'SHORT'}
    ]
    
    print("Testing stop loss calculations for different price levels:")
    print()
    
    for i, scenario in enumerate(test_scenarios, 1):
        symbol = scenario['symbol']
        price = scenario['price']
        side = scenario['side']
        
        print(f"📊 TEST {i}: {symbol} {side} @ ${price:.4f}")
        
        # Calculate stop loss using the corrected method
        try:
            sl_price = await engine._calculate_stop_loss(price, side, symbol)
            
            # Calculate position parameters
            capital_per_position = engine.account.balance * engine.risk_per_trade_pct  # $200
            leverage = engine.leverage  # 10x
            notional_value = capital_per_position * leverage  # $2000
            quantity = notional_value / price
            
            # Calculate expected loss
            if side == 'LONG':
                expected_loss = (price - sl_price) * quantity
                sl_pct = (price - sl_price) / price * 100
            else:  # SHORT
                expected_loss = (sl_price - price) * quantity
                sl_pct = (sl_price - price) / price * 100
            
            print(f"   Entry Price: ${price:.4f}")
            print(f"   Stop Loss:   ${sl_price:.4f} ({sl_pct:.3f}%)")
            print(f"   Quantity:    {quantity:.6f} {symbol}")
            print(f"   Capital:     ${capital_per_position:.2f}")
            print(f"   Leverage:    {leverage}x")
            print(f"   Expected Loss: ${expected_loss:.2f}")
            
            # Verify the loss is approximately $10
            if abs(expected_loss - 10.0) < 0.01:  # Within 1 cent
                print(f"   ✅ CORRECT: Loss = ${expected_loss:.2f} ≈ $10.00")
            else:
                print(f"   ❌ INCORRECT: Loss = ${expected_loss:.2f} ≠ $10.00")
            
            print()
            
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            print()
    
    print("🎯 SUMMARY:")
    print("The corrected stop loss calculation should:")
    print("1. Calculate the exact quantity based on capital and leverage")
    print("2. Determine the price movement needed for exactly $10 loss")
    print("3. Set the stop loss price to achieve that $10 loss limit")
    print()
    print("This ensures Rule 3 (0.5% stop loss) properly limits losses to $10")
    print("regardless of the entry price or symbol being traded.")

if __name__ == "__main__":
    asyncio.run(test_stop_loss_calculation())
