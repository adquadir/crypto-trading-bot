#!/usr/bin/env python3
"""
Check Paper Trading Signal Sources
Debug script to see where paper trading signals are coming from
"""

import asyncio
import sys
import json
import requests
from datetime import datetime

def check_api_status():
    """Check if API is responding"""
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            print("✅ API is online")
            return True
        else:
            print(f"❌ API returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot reach API: {e}")
        return False

def check_paper_trading_status():
    """Check paper trading status and signal sources"""
    try:
        response = requests.get("http://localhost:8000/api/v1/paper-trading/status", timeout=10)
        if response.status_code == 200:
            data = response.json()['data']
            
            print("\n" + "="*60)
            print("📊 PAPER TRADING STATUS")
            print("="*60)
            print(f"Running: {data.get('enabled', False)}")
            print(f"Balance: ${data.get('virtual_balance', 0):,.2f}")
            print(f"Completed Trades: {data.get('completed_trades', 0)}")
            print(f"Active Positions: {data.get('active_positions', 0)}")
            print(f"Win Rate: {data.get('win_rate_pct', 0):.1f}%")
            
            # Show signal sources
            signal_sources = data.get('signal_sources', {})
            if signal_sources:
                print("\n📡 SIGNAL SOURCES:")
                for source, stats in signal_sources.items():
                    print(f"  {source}: {stats['total_trades']} trades, {stats['win_rate']:.1%} win rate, ${stats['total_pnl']:+.2f} PnL")
            
            # Show active positions with signal sources
            active_positions = data.get('active_positions_detail', [])
            if active_positions:
                print(f"\n🎯 ACTIVE POSITIONS ({len(active_positions)}):")
                for pos in active_positions:
                    print(f"  {pos['symbol']} {pos['side']} @ ${pos['entry_price']:.4f} | Signal: {pos['signal_source']} | Strategy: {pos['strategy_type']} | PnL: ${pos['unrealized_pnl']:+.2f}")
            
            # Show strategy performance
            strategy_performance = data.get('strategy_performance', {})
            if strategy_performance:
                print(f"\n📈 STRATEGY PERFORMANCE:")
                for strategy, stats in strategy_performance.items():
                    print(f"  {strategy}: {stats['total_trades']} trades, {stats['win_rate']:.1%} win rate, ${stats['total_pnl']:+.2f} PnL")
            
            return True
        else:
            print(f"❌ Paper trading status check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error checking paper trading status: {e}")
        return False

def check_profit_scraping_status():
    """Check profit scraping status"""
    try:
        response = requests.get("http://localhost:8000/api/v1/profit-scraping/status", timeout=10)
        if response.status_code == 200:
            data = response.json()['data']
            
            print("\n" + "="*60)
            print("🎯 PROFIT SCRAPING STATUS")
            print("="*60)
            print(f"Active: {data.get('active', False)}")
            print(f"Monitored Symbols: {len(data.get('monitored_symbols', []))}")
            print(f"Active Trades: {data.get('active_trades', 0)}")
            print(f"Total Trades: {data.get('total_trades', 0)}")
            print(f"Win Rate: {data.get('win_rate', 0):.1%}")
            print(f"Total Profit: ${data.get('total_profit', 0):,.2f}")
            print(f"Opportunities Found: {data.get('opportunities_count', 0)}")
            print(f"Trading Engine: {data.get('trading_engine_type', 'unknown')}")
            
            return True
        else:
            print(f"❌ Profit scraping status check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error checking profit scraping status: {e}")
        return False

def check_profit_scraping_opportunities():
    """Check available profit scraping opportunities"""
    try:
        response = requests.get("http://localhost:8000/api/v1/profit-scraping/opportunities", timeout=10)
        if response.status_code == 200:
            data = response.json()['data']
            
            print("\n" + "="*60)
            print("🎯 PROFIT SCRAPING OPPORTUNITIES")
            print("="*60)
            
            total_opportunities = 0
            for symbol, opportunities in data.items():
                if opportunities:
                    total_opportunities += len(opportunities)
                    print(f"\n{symbol}: {len(opportunities)} opportunities")
                    for opp in opportunities[:2]:  # Show top 2 per symbol
                        level = opp['level']
                        targets = opp['targets']
                        print(f"  {level['level_type']} @ {level['price']:.4f} (score: {opp['opportunity_score']}, confidence: {targets['confidence_score']}%)")
            
            print(f"\nTotal Opportunities: {total_opportunities}")
            return total_opportunities > 0
        else:
            print(f"❌ Profit scraping opportunities check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error checking profit scraping opportunities: {e}")
        return False

def main():
    """Main function to check all signal sources"""
    print("🚀 CHECKING PAPER TRADING SIGNAL SOURCES")
    print("="*60)
    
    # Check API status
    if not check_api_status():
        return
    
    # Check paper trading status
    paper_trading_ok = check_paper_trading_status()
    
    # Check profit scraping status
    profit_scraping_ok = check_profit_scraping_status()
    
    # Check profit scraping opportunities
    has_opportunities = check_profit_scraping_opportunities()
    
    print("\n" + "="*60)
    print("🎯 SUMMARY")
    print("="*60)
    print(f"Paper Trading: {'✅ Running' if paper_trading_ok else '❌ Issues'}")
    print(f"Profit Scraping: {'✅ Active' if profit_scraping_ok else '❌ Issues'}")
    print(f"Opportunities: {'✅ Available' if has_opportunities else '❌ None found'}")
    
    if profit_scraping_ok and has_opportunities and paper_trading_ok:
        print("\n🎉 All systems operational - profit scraping opportunities should be creating trades!")
    else:
        print("\n⚠️ There may be a disconnect between profit scraping and paper trading")

if __name__ == "__main__":
    main() 