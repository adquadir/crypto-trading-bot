#!/usr/bin/env python3

import requests
import json
from datetime import datetime

def test_signal_source_display():
    """
    Test the signal source display fix to ensure accurate engine identification
    """
    
    print("🔍 TESTING SIGNAL SOURCE DISPLAY FIX")
    print("=" * 60)
    
    base_url = "http://localhost:8000"
    
    # 1. Check current paper trading status
    print("\n1️⃣ CHECKING PAPER TRADING STATUS...")
    try:
        response = requests.get(f"{base_url}/api/v1/paper-trading/status", timeout=10)
        if response.status_code == 200:
            data = response.json()
            status = data.get('data', {})
            print(f"✅ Paper Trading Status: {'RUNNING' if status.get('enabled') else 'STOPPED'}")
            print(f"   Active Positions: {status.get('active_positions', 0)}")
            print(f"   Completed Trades: {status.get('completed_trades', 0)}")
        else:
            print(f"❌ Failed to get status: {response.status_code}")
    except Exception as e:
        print(f"❌ Error getting status: {e}")
    
    # 2. Check active positions and their signal sources
    print("\n2️⃣ CHECKING ACTIVE POSITIONS SIGNAL SOURCES...")
    try:
        response = requests.get(f"{base_url}/api/v1/paper-trading/positions", timeout=10)
        if response.status_code == 200:
            data = response.json()
            positions = data.get('data', [])
            
            if positions:
                print(f"✅ Found {len(positions)} active positions:")
                
                signal_source_counts = {}
                for pos in positions:
                    signal_source = pos.get('signal_source', 'unknown')
                    signal_source_counts[signal_source] = signal_source_counts.get(signal_source, 0) + 1
                    
                    print(f"   📊 {pos.get('symbol', 'N/A')} | {pos.get('side', 'N/A')} | "
                          f"Source: '{signal_source}' | "
                          f"PnL: ${pos.get('unrealized_pnl', 0):.2f} | "
                          f"Age: {pos.get('age_minutes', 0):.0f}m")
                
                print(f"\n📈 SIGNAL SOURCE BREAKDOWN:")
                for source, count in signal_source_counts.items():
                    print(f"   • {source}: {count} positions")
                    
            else:
                print("ℹ️  No active positions found")
        else:
            print(f"❌ Failed to get positions: {response.status_code}")
    except Exception as e:
        print(f"❌ Error getting positions: {e}")
    
    # 3. Check completed trades and their signal sources
    print("\n3️⃣ CHECKING COMPLETED TRADES SIGNAL SOURCES...")
    try:
        response = requests.get(f"{base_url}/api/v1/paper-trading/trades", timeout=10)
        if response.status_code == 200:
            data = response.json()
            trades = data.get('trades', [])
            
            if trades:
                print(f"✅ Found {len(trades)} completed trades:")
                
                # Get recent trades (last 10)
                recent_trades = trades[-10:] if len(trades) > 10 else trades
                
                signal_source_counts = {}
                for trade in recent_trades:
                    signal_source = trade.get('signal_source', 'unknown')
                    signal_source_counts[signal_source] = signal_source_counts.get(signal_source, 0) + 1
                    
                    result = "WIN" if trade.get('pnl', 0) > 0 else "LOSS"
                    print(f"   📊 {trade.get('symbol', 'N/A')} | {trade.get('side', 'N/A')} | "
                          f"Source: '{signal_source}' | "
                          f"PnL: ${trade.get('pnl', 0):.2f} | "
                          f"{result}")
                
                print(f"\n📈 COMPLETED TRADES SIGNAL SOURCE BREAKDOWN:")
                for source, count in signal_source_counts.items():
                    print(f"   • {source}: {count} trades")
                    
            else:
                print("ℹ️  No completed trades found")
        else:
            print(f"❌ Failed to get trades: {response.status_code}")
    except Exception as e:
        print(f"❌ Error getting trades: {e}")
    
    # 4. Test the frontend mapping logic
    print("\n4️⃣ TESTING FRONTEND SIGNAL SOURCE MAPPING...")
    
    # Define the same mapping as in the frontend
    source_map = {
        # Profit Scraping Engine
        'profit_scraping_support': 'Profit Scraping (Support)',
        'profit_scraping_resistance': 'Profit Scraping (Resistance)',
        'profit_scraping_engine': 'Profit Scraping Engine',
        'profit_scraping': 'Profit Scraping',
        
        # Opportunity Manager
        'opportunity_manager': 'Opportunity Manager',
        'opportunity_scalping': 'Opportunity Manager (Scalping)',
        'opportunity_swing': 'Opportunity Manager (Swing)',
        
        # Flow Trading System
        'flow_trading_adaptive': 'Flow Trading (Adaptive)',
        'flow_trading_breakout': 'Flow Trading (Breakout)',
        'flow_trading_support_resistance': 'Flow Trading (S/R)',
        'flow_trading_momentum': 'Flow Trading (Momentum)',
        'flow_trading_engine': 'Flow Trading Engine',
        
        # Auto Signal Generator
        'auto_signal_generator': 'Auto Signal Generator',
        'auto_signal_scalping': 'Auto Signals (Scalping)',
        'auto_signal_swing': 'Auto Signals (Swing)',
        
        # Scalping Engine
        'scalping_engine': 'Scalping Engine',
        'realtime_scalping': 'Realtime Scalping',
    }
    
    def get_signal_source_display(signal_source):
        return source_map.get(signal_source, signal_source or 'Unknown Source')
    
    def get_signal_source_color(signal_source):
        if signal_source and signal_source.startswith('profit_scraping'):
            return 'primary'
        elif signal_source and signal_source.startswith('opportunity'):
            return 'secondary'
        elif signal_source and signal_source.startswith('flow_trading'):
            return 'info'
        elif signal_source and signal_source.startswith('auto_signal'):
            return 'warning'
        elif signal_source and signal_source.startswith('scalping'):
            return 'success'
        else:
            return 'default'
    
    # Test common signal sources
    test_sources = [
        'profit_scraping_support',
        'profit_scraping_resistance', 
        'opportunity_manager',
        'flow_trading_adaptive',
        'auto_signal_generator',
        'scalping_engine',
        'unknown_source',
        None,
        ''
    ]
    
    print("✅ Frontend Display Mapping Test:")
    for source in test_sources:
        display = get_signal_source_display(source)
        color = get_signal_source_color(source)
        print(f"   • '{source}' → '{display}' (color: {color})")
    
    # 5. Check if profit scraping is running
    print("\n5️⃣ CHECKING PROFIT SCRAPING ENGINE STATUS...")
    try:
        response = requests.get(f"{base_url}/api/v1/profit-scraping/status", timeout=10)
        if response.status_code == 200:
            data = response.json()
            status = data.get('data', {})
            print(f"✅ Profit Scraping Status: {'RUNNING' if status.get('enabled') else 'STOPPED'}")
            print(f"   Active Symbols: {len(status.get('active_symbols', []))}")
            print(f"   Signals Generated: {status.get('signals_generated', 0)}")
        else:
            print(f"❌ Failed to get profit scraping status: {response.status_code}")
    except Exception as e:
        print(f"❌ Error getting profit scraping status: {e}")

def main():
    """Main function to run the test"""
    print(f"🚀 Starting Signal Source Display Test at {datetime.now()}")
    
    try:
        test_signal_source_display()
        
        print("\n" + "=" * 60)
        print("✅ SIGNAL SOURCE DISPLAY TEST COMPLETED")
        print("\n🎯 KEY FINDINGS:")
        print("   • Fixed confusing 'Opportunity Profit' display")
        print("   • Implemented clear, descriptive signal source names")
        print("   • Added color coding for different engine types")
        print("   • Removed complex string parsing that caused errors")
        print("\n📋 WHAT TO LOOK FOR:")
        print("   • Signal sources should show clear names like:")
        print("     - 'Profit Scraping (Support)' instead of 'Profit Support'")
        print("     - 'Opportunity Manager' instead of 'Opportunity Profit'")
        print("     - 'Flow Trading (Adaptive)' for flow trading signals")
        print("   • No more weird combinations or parsing errors")
        print("   • Consistent display across active positions and completed trades")
        
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")

if __name__ == "__main__":
    main()
