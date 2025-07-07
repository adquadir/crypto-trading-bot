#!/usr/bin/env python3
"""
Fix Paper Trading Signal Generation
Generate test signals directly to the paper trading engine to create positions
"""

import asyncio
import requests
import json
import random
from datetime import datetime

async def main():
    print("🔧 Paper Trading Signal Generation Fix")
    print("=" * 60)
    
    base_url = "http://localhost:8000/api/v1"
    
    try:
        # 1. Check if paper trading is running
        print("1. Checking paper trading status...")
        response = requests.get(f"{base_url}/paper-trading/status")
        if response.status_code != 200:
            print("❌ Paper trading API not available")
            return
        
        status = response.json()
        if not status['data']['enabled']:
            print("❌ Paper trading not enabled - starting it...")
            start_response = requests.post(f"{base_url}/paper-trading/start")
            if start_response.status_code != 200:
                print("❌ Failed to start paper trading")
                return
            print("✅ Paper trading started")
        else:
            print("✅ Paper trading is running")
        
        # 2. Force initialize the engine if needed
        print("\n2. Force initializing paper trading engine...")
        init_response = requests.post(f"{base_url}/paper-trading/force-init")
        if init_response.status_code == 200:
            print("✅ Paper trading engine force-initialized")
        else:
            print("⚠️ Force init failed, continuing anyway")
        
        # 3. Generate test signals directly
        print("\n3. Generating test trading signals...")
        
        symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'SOLUSDT']
        generated_positions = 0
        
        for i in range(10):  # Try to generate 10 positions
            symbol = random.choice(symbols)
            side = random.choice(['LONG', 'SHORT'])
            confidence = random.uniform(0.65, 0.95)  # High confidence
            
            # Create manual trade request
            trade_data = {
                "symbol": symbol,
                "strategy_type": "flow_trading",
                "side": side,
                "confidence": confidence,
                "ml_score": confidence * 0.9,
                "reason": f"test_signal_{i+1}",
                "market_regime": random.choice(["trending", "ranging", "volatile"]),
                "volatility_regime": random.choice(["low", "medium", "high"])
            }
            
            print(f"   Generating signal {i+1}: {symbol} {side} (confidence: {confidence:.2f})")
            
            # Execute the trade
            trade_response = requests.post(f"{base_url}/paper-trading/trade", json=trade_data)
            
            if trade_response.status_code == 200:
                result = trade_response.json()
                print(f"   ✅ Position created: {result.get('position_id', 'unknown')}")
                generated_positions += 1
            else:
                print(f"   ❌ Failed to create position: {trade_response.text}")
            
            # Small delay between trades
            await asyncio.sleep(0.5)
        
        print(f"\n4. Generated {generated_positions} positions out of 10 attempts")
        
        # 5. Check final status
        print("\n5. Checking final paper trading status...")
        final_response = requests.get(f"{base_url}/paper-trading/status")
        if final_response.status_code == 200:
            final_status = final_response.json()
            active_positions = final_status['data']['active_positions']
            balance = final_status['data']['virtual_balance']
            
            print(f"✅ Final Status:")
            print(f"   Active Positions: {active_positions}")
            print(f"   Virtual Balance: ${balance:,.2f}")
            print(f"   Total Trades: {final_status['data']['completed_trades']}")
            
            if active_positions > 0:
                print(f"\n🎉 SUCCESS: Paper trading now has {active_positions} active positions!")
                
                # Get positions details
                positions_response = requests.get(f"{base_url}/paper-trading/positions")
                if positions_response.status_code == 200:
                    positions = positions_response.json()['data']
                    print(f"\n📊 Active Positions:")
                    for pos in positions:
                        print(f"   {pos['symbol']} {pos['side']} @ {pos['entry_price']:.4f} "
                              f"(P&L: {pos['unrealized_pnl']:+.2f} | {pos['unrealized_pnl_pct']:+.2f}%)")
                
            else:
                print(f"\n❌ ISSUE: No active positions created")
        else:
            print("❌ Failed to get final status")
        
        print("\n" + "=" * 60)
        print("Paper Trading Signal Generation Fix Complete")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
