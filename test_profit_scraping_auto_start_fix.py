#!/usr/bin/env python3
"""
Test Profit Scraping Auto-Start Fix
This script tests that profit scraping automatically starts with paper trading when PM2 restarts
"""

import asyncio
import requests
import time
import sys
import subprocess
import json

def test_pm2_status():
    """Check PM2 status"""
    try:
        result = subprocess.run(['pm2', 'status'], capture_output=True, text=True)
        print("📊 PM2 Status:")
        print(result.stdout)
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Error checking PM2 status: {e}")
        return False

def restart_pm2():
    """Restart PM2 processes"""
    try:
        print("🔄 Restarting PM2 processes...")
        result = subprocess.run(['pm2', 'restart', 'all'], capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print(f"⚠️ PM2 restart warnings: {result.stderr}")
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Error restarting PM2: {e}")
        return False

def wait_for_api_ready(max_wait=60):
    """Wait for API to be ready"""
    print(f"⏳ Waiting for API to be ready (max {max_wait}s)...")
    
    for i in range(max_wait):
        try:
            response = requests.get("http://localhost:8000/health", timeout=5)
            if response.status_code == 200:
                print(f"✅ API is ready after {i+1} seconds")
                return True
        except requests.exceptions.RequestException:
            pass
        
        time.sleep(1)
        if (i + 1) % 10 == 0:
            print(f"   Still waiting... ({i+1}s)")
    
    print(f"❌ API not ready after {max_wait} seconds")
    return False

def check_paper_trading_status():
    """Check paper trading status"""
    try:
        response = requests.get("http://localhost:8000/api/v1/paper-trading/status", timeout=10)
        if response.status_code == 200:
            data = response.json()
            enabled = data['data']['enabled']
            balance = data['data']['virtual_balance']
            print(f"📊 Paper Trading: {'✅ Running' if enabled else '❌ Stopped'}")
            print(f"   Virtual Balance: ${balance:,.2f}")
            return enabled
        else:
            print(f"❌ Failed to check paper trading status: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error checking paper trading: {e}")
        return False

def check_profit_scraping_status():
    """Check profit scraping status"""
    try:
        response = requests.get("http://localhost:8000/api/v1/profit-scraping/status", timeout=10)
        if response.status_code == 200:
            data = response.json()
            active = data['data']['active']
            symbols = data['data']['monitored_symbols']
            trades = data['data']['active_trades']
            
            print(f"🎯 Profit Scraping: {'✅ Active' if active else '❌ Inactive'}")
            print(f"   Monitored Symbols: {len(symbols)} ({symbols})")
            print(f"   Active Trades: {trades}")
            print(f"   Trading Engine: {data['data'].get('trading_engine_type', 'unknown')}")
            
            return active
        else:
            print(f"❌ Failed to check profit scraping status: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error checking profit scraping: {e}")
        return False

def check_health_status():
    """Check overall health status"""
    try:
        response = requests.get("http://localhost:8000/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            components = data['components']
            
            print("🏥 Health Check:")
            for component, status in components.items():
                status_icon = "✅" if status else "❌"
                print(f"   {component}: {status_icon}")
            
            return all(components.values())
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error checking health: {e}")
        return False

def test_profit_scraping_connection():
    """Test that profit scraping is connected to paper trading"""
    try:
        # Get profit scraping opportunities
        response = requests.get("http://localhost:8000/api/v1/profit-scraping/opportunities", timeout=10)
        if response.status_code == 200:
            data = response.json()
            opportunities = data.get('data', {})
            total_opportunities = sum(len(opps) for opps in opportunities.values())
            
            print(f"🔍 Profit Scraping Opportunities: {total_opportunities}")
            for symbol, opps in opportunities.items():
                if opps:
                    print(f"   {symbol}: {len(opps)} opportunities")
            
            return total_opportunities > 0
        else:
            print(f"❌ Failed to get opportunities: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error checking opportunities: {e}")
        return False

def main():
    print("🧪 Testing Profit Scraping Auto-Start Fix")
    print("=" * 60)
    
    # Step 1: Check initial PM2 status
    if not test_pm2_status():
        print("❌ PM2 not running properly")
        sys.exit(1)
    
    # Step 2: Restart PM2 to simulate server restart
    if not restart_pm2():
        print("❌ Failed to restart PM2")
        sys.exit(1)
    
    # Step 3: Wait for API to be ready
    if not wait_for_api_ready(60):
        print("❌ API failed to start")
        sys.exit(1)
    
    # Step 4: Check paper trading auto-started
    print("\n" + "=" * 40)
    print("📊 CHECKING PAPER TRADING AUTO-START")
    print("=" * 40)
    
    paper_trading_running = check_paper_trading_status()
    
    # Step 5: Check profit scraping auto-started
    print("\n" + "=" * 40)
    print("🎯 CHECKING PROFIT SCRAPING AUTO-START")
    print("=" * 40)
    
    profit_scraping_active = check_profit_scraping_status()
    
    # Step 6: Check overall health
    print("\n" + "=" * 40)
    print("🏥 CHECKING OVERALL HEALTH")
    print("=" * 40)
    
    health_ok = check_health_status()
    
    # Step 7: Test profit scraping connection
    print("\n" + "=" * 40)
    print("🔗 TESTING PROFIT SCRAPING CONNECTION")
    print("=" * 40)
    
    connection_ok = test_profit_scraping_connection()
    
    # Final results
    print("\n" + "=" * 60)
    print("📋 FINAL TEST RESULTS")
    print("=" * 60)
    
    results = {
        "Paper Trading Auto-Start": paper_trading_running,
        "Profit Scraping Auto-Start": profit_scraping_active,
        "Overall Health": health_ok,
        "Profit Scraping Connection": connection_ok
    }
    
    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {test_name}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
        print("✅ Profit scraping auto-starts with paper trading on PM2 restart")
        print("✅ No manual intervention required")
        print("\n🚀 SYSTEM READY FOR PRODUCTION!")
    else:
        print("❌ SOME TESTS FAILED!")
        print("🔧 Manual intervention may be required")
        print("\n📝 Check the logs for more details:")
        print("   - API logs: pm2 logs crypto-trading-api")
        print("   - Frontend logs: pm2 logs crypto-trading-frontend")
        sys.exit(1)

if __name__ == "__main__":
    main()
