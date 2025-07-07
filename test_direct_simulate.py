#!/usr/bin/env python3

import requests
import json

def test_direct_simulate():
    """Test the simulate endpoint directly with explicit parameters"""
    
    print("🔧 Direct Simulate Test")
    print("=" * 60)
    
    # Test the simulate endpoint directly
    url = "http://localhost:8000/api/v1/paper-trading/simulate-signals"
    
    # Test with explicit parameters
    params = {
        'symbol': 'BTCUSDT',
        'count': 5,  # Explicitly set count
        'strategy_type': 'scalping'
    }
    
    print(f"1. Testing simulate endpoint with params: {params}")
    
    try:
        response = requests.post(url, params=params)
        print(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Response: {json.dumps(result, indent=2)}")
            
            # Check if positions were created
            executed_trades = result.get('executed_trades', [])
            total_positions = result.get('total_positions', 0)
            
            print(f"\n📊 Results:")
            print(f"   Executed trades: {len(executed_trades)}")
            print(f"   Total positions: {total_positions}")
            
            if len(executed_trades) > 0:
                print("✅ SUCCESS: Positions created!")
                for i, trade in enumerate(executed_trades):
                    signal = trade.get('signal', {})
                    print(f"   Trade {i+1}: {signal.get('symbol')} {signal.get('side')} @ {signal.get('entry_price', 0):.2f}")
            else:
                print("❌ FAILED: No positions created")
                
        else:
            print(f"❌ Request failed with status {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("\n" + "=" * 60)
    print("Direct Simulate Test Complete")

if __name__ == "__main__":
    test_direct_simulate()
