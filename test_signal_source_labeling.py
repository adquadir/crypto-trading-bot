#!/usr/bin/env python3
"""
Test Signal Source Labeling
Verify that signals are properly labeled with their source
"""

import asyncio
import requests
import json
import time

async def test_signal_sources():
    """Test signal source labeling"""
    try:
        print("🔧 Testing Signal Source Labeling...")
        
        # Start paper trading
        print("\n1. Starting paper trading...")
        response = requests.post("http://localhost:8000/api/v1/paper-trading/start")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Paper trading started: {data.get('data', {}).get('enabled', False)}")
        else:
            print(f"❌ Failed to start paper trading: {response.status_code}")
            return
        
        # Wait for initial signal processing
        print("\n2. Waiting for signal processing...")
        await asyncio.sleep(60)  # Wait for signals to be processed
        
        # Check positions and their signal sources
        print("\n3. Checking position signal sources...")
        response = requests.get("http://localhost:8000/api/v1/paper-trading/positions")
        if response.status_code == 200:
            data = response.json()
            positions = data.get('data', [])
            
            print(f"📊 Found {len(positions)} positions:")
            
            # Count by signal source
            source_counts = {}
            for pos in positions:
                source = pos.get('signal_source', 'unknown')
                source_counts[source] = source_counts.get(source, 0) + 1
                print(f"  - {pos.get('symbol')} {pos.get('side')} [SOURCE: {source}]")
            
            print(f"\n📈 Signal Source Summary:")
            for source, count in source_counts.items():
                print(f"  - {source}: {count} positions")
            
            # Check engine status
            print("\n4. Checking engine status...")
            response = requests.get("http://localhost:8000/api/v1/paper-trading/debug/engine-status")
            if response.status_code == 200:
                data = response.json()
                connections = data.get('data', {}).get('connections', {})
                print(f"✅ Profit Scraping: Connected={connections.get('profit_scraping_connected')}, Active={connections.get('profit_scraping_active')}, Opportunities={connections.get('profit_scraping_opportunities', 0)}")
                print(f"✅ Opportunity Manager: Connected={connections.get('opportunity_manager_connected')}, Opportunities={connections.get('opportunity_manager_opportunities', 0)}")
        
        print(f"\n🎉 Test completed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_signal_sources()) 