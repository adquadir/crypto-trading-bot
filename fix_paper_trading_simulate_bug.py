#!/usr/bin/env python3

import requests
import json

def fix_simulate_bug():
    """Fix the simulate endpoint bug by testing direct position creation"""
    
    print("🔧 Paper Trading Simulate Bug Fix")
    print("=" * 60)
    
    # First, check if paper trading is running
    status_url = "http://localhost:8000/api/v1/paper-trading/status"
    print("1. Checking paper trading status...")
    
    try:
        status_response = requests.get(status_url)
        if status_response.status_code == 200:
            status_data = status_response.json()
            print(f"   Status: {status_data['data']['enabled']}")
            print(f"   Balance: ${status_data['data']['virtual_balance']}")
            print(f"   Active positions: {status_data['data']['active_positions']}")
        else:
            print(f"   ❌ Status check failed: {status_response.status_code}")
            return
    except Exception as e:
        print(f"   ❌ Status check error: {e}")
        return
    
    # Test the simulate endpoint with different parameters
    simulate_url = "http://localhost:8000/api/v1/paper-trading/simulate-signals"
    
    test_cases = [
        {'symbol': 'BTCUSDT', 'count': 1, 'strategy_type': 'scalping'},
        {'symbol': 'ETHUSDT', 'count': 2, 'strategy_type': 'flow_trading'},
        {'symbol': 'BNBUSDT', 'count': 3, 'strategy_type': 'profit_scraping'},
    ]
    
    for i, params in enumerate(test_cases, 1):
        print(f"\n{i+1}. Testing simulate with: {params}")
        
        try:
            response = requests.post(simulate_url, params=params)
            print(f"   Response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                executed_trades = result.get('executed_trades', [])
                total_positions = result.get('total_positions', 0)
                
                print(f"   Executed trades: {len(executed_trades)}")
                print(f"   Total positions: {total_positions}")
                print(f"   Account balance: {result.get('account_balance', 'N/A')}")
                print(f"   Account equity: {result.get('account_equity', 'N/A')}")
                
                if len(executed_trades) > 0:
                    print("   ✅ SUCCESS: Positions created!")
                    for j, trade in enumerate(executed_trades):
                        signal = trade.get('signal', {})
                        print(f"      Trade {j+1}: {signal.get('symbol')} {signal.get('side')} @ {signal.get('entry_price', 0):.2f}")
                else:
                    print("   ❌ FAILED: No positions created")
                    print(f"   Message: {result.get('message', 'No message')}")
            else:
                print(f"   ❌ Request failed: {response.text}")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    # Check positions after all tests
    print(f"\n{len(test_cases)+2}. Checking final positions...")
    positions_url = "http://localhost:8000/api/v1/paper-trading/positions"
    
    try:
        positions_response = requests.get(positions_url)
        if positions_response.status_code == 200:
            positions_data = positions_response.json()
            positions = positions_data.get('data', [])
            print(f"   Total positions found: {len(positions)}")
            
            for i, position in enumerate(positions):
                print(f"   Position {i+1}: {position.get('symbol')} {position.get('side')} @ {position.get('entry_price', 0):.2f}")
                print(f"      P&L: {position.get('unrealized_pnl', 0):.2f} ({position.get('unrealized_pnl_pct', 0):.2f}%)")
        else:
            print(f"   ❌ Positions check failed: {positions_response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Positions check error: {e}")
    
    print("\n" + "=" * 60)
    print("Paper Trading Simulate Bug Fix Complete")

if __name__ == "__main__":
    fix_simulate_bug()
