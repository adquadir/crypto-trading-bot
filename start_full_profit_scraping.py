#!/usr/bin/env python3
"""
Start Full Profit Scraping System
This script starts profit scraping for ALL available USDT symbols from Binance
"""

import requests
import json
import sys
import os

# Add src to path
sys.path.append('src')

def get_all_usdt_symbols():
    """Get all USDT trading symbols from Binance"""
    try:
        from market_data.exchange_client import ExchangeClient
        
        exchange_client = ExchangeClient()
        all_symbols = exchange_client.get_trading_symbols()
        usdt_symbols = [s for s in all_symbols if s.endswith('USDT')]
        
        print(f"✅ Found {len(usdt_symbols)} USDT symbols")
        return usdt_symbols
    except Exception as e:
        print(f"❌ Error getting symbols: {e}")
        # Fallback to common symbols
        return [
            "BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT", "SOLUSDT", "XRPUSDT", 
            "DOTUSDT", "LINKUSDT", "LTCUSDT", "BCHUSDT", "XLMUSDT", "TRXUSDT",
            "AVAXUSDT", "MATICUSDT", "UNIUSDT", "ATOMUSDT", "VETUSDT", "FILUSDT",
            "ETCUSDT", "THETAUSDT", "ALGOUSDT", "MKRUSDT", "COMPUSDT", "AAVEUSDT"
        ]

def start_profit_scraping(symbols):
    """Start profit scraping for all symbols"""
    try:
        url = "http://localhost:8000/api/v1/profit-scraping/start"
        payload = {
            "symbols": symbols,
            "ml_enhanced": True,
            "risk_adjusted": True,
            "auto_optimize": True
        }
        
        print(f"🚀 Starting profit scraping for {len(symbols)} symbols...")
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Profit scraping started successfully!")
            print(f"   Active: {result['data']['active']}")
            print(f"   Monitored symbols: {len(result['data']['monitored_symbols'])}")
            return True
        else:
            print(f"❌ Failed to start profit scraping: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error starting profit scraping: {e}")
        return False

def check_paper_trading_status():
    """Check if paper trading is running"""
    try:
        url = "http://localhost:8000/api/v1/paper-trading/status"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            enabled = result['data']['enabled']
            balance = result['data']['virtual_balance']
            print(f"📊 Paper Trading Status: {'✅ Running' if enabled else '❌ Stopped'}")
            print(f"   Virtual Balance: ${balance:,.2f}")
            return enabled
        else:
            print(f"❌ Failed to check paper trading status: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error checking paper trading: {e}")
        return False

def start_paper_trading():
    """Start paper trading if not running"""
    try:
        url = "http://localhost:8000/api/v1/paper-trading/start"
        response = requests.post(url, timeout=10)
        
        if response.status_code == 200:
            print("✅ Paper trading started!")
            return True
        else:
            print(f"❌ Failed to start paper trading: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error starting paper trading: {e}")
        return False

def main():
    print("🔧 Starting Full Profit Scraping System...")
    print("=" * 60)
    
    # Step 1: Get all USDT symbols
    symbols = get_all_usdt_symbols()
    
    # Step 2: Check paper trading status
    paper_trading_running = check_paper_trading_status()
    
    # Step 3: Start paper trading if not running
    if not paper_trading_running:
        print("🚀 Starting paper trading...")
        start_paper_trading()
    
    # Step 4: Start profit scraping for all symbols
    success = start_profit_scraping(symbols)
    
    if success:
        print("\n" + "=" * 60)
        print("🎉 SYSTEM READY!")
        print(f"✅ Profit scraping active for {len(symbols)} symbols")
        print("✅ Paper trading engine running")
        print("✅ Signals will flow: Opportunities → Profit Scraping → Paper Trading")
        print("\n📊 Check status at:")
        print("   - Profit Scraping: http://localhost:8000/api/v1/profit-scraping/status")
        print("   - Paper Trading: http://localhost:8000/api/v1/paper-trading/status")
        print("   - Frontend: http://localhost:3000")
    else:
        print("\n❌ Failed to start profit scraping system")
        sys.exit(1)

if __name__ == "__main__":
    main()
