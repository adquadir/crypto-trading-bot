#!/usr/bin/env python3

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.database.database import Database
from src.market_data.exchange_client import ExchangeClient
from src.strategies.profit_scraping.profit_scraping_engine import ProfitScrapingEngine
from src.trading.enhanced_paper_trading_engine import EnhancedPaperTradingEngine
from src.utils.config import load_config
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def diagnose_profit_scraping_logs():
    """Diagnose why profit scraping isn't showing in logs"""
    
    print("🔍 DIAGNOSING PROFIT SCRAPING LOG ISSUE...")
    print("=" * 60)
    
    try:
        # 1. Check if profit scraping engine exists and is active
        print("\n1. CHECKING PROFIT SCRAPING ENGINE STATUS...")
        
        config = load_config()
        exchange_client = ExchangeClient()
        
        # Initialize paper trading engine
        paper_engine = EnhancedPaperTradingEngine(config=config, exchange_client=exchange_client)
        
        # Initialize profit scraping engine
        profit_engine = ProfitScrapingEngine(
            exchange_client=exchange_client,
            paper_trading_engine=paper_engine
        )
        
        print(f"✅ Profit scraping engine created: {profit_engine}")
        print(f"   Active: {profit_engine.active}")
        print(f"   Monitored symbols: {profit_engine.monitored_symbols}")
        print(f"   Paper trading engine connected: {profit_engine.paper_trading_engine is not None}")
        
        # 2. Check database for profit scraping positions
        print("\n2. CHECKING DATABASE FOR PROFIT SCRAPING POSITIONS...")
        
        db = Database()
        
        # Check paper trading positions
        paper_positions = await db.fetch_all("""
            SELECT symbol, side, quantity, entry_price, current_price, unrealized_pnl, 
                   created_at, strategy_type
            FROM paper_trading_positions 
            WHERE strategy_type = 'profit_scraping'
            ORDER BY created_at DESC 
            LIMIT 10
        """)
        
        print(f"   Paper trading profit scraping positions: {len(paper_positions)}")
        for pos in paper_positions:
            print(f"     {pos['symbol']} {pos['side']} - Entry: ${pos['entry_price']:.4f} - P&L: ${pos['unrealized_pnl']:.2f}")
        
        # Check paper trading trades
        paper_trades = await db.fetch_all("""
            SELECT symbol, side, quantity, entry_price, exit_price, pnl, 
                   created_at, strategy_type
            FROM paper_trading_trades 
            WHERE strategy_type = 'profit_scraping'
            ORDER BY created_at DESC 
            LIMIT 10
        """)
        
        print(f"   Paper trading profit scraping trades: {len(paper_trades)}")
        for trade in paper_trades:
            print(f"     {trade['symbol']} {trade['side']} - Entry: ${trade['entry_price']:.4f} Exit: ${trade['exit_price']:.4f} P&L: ${trade['pnl']:.2f}")
        
        # 3. Test profit scraping engine startup
        print("\n3. TESTING PROFIT SCRAPING ENGINE STARTUP...")
        
        test_symbols = ['BTCUSDT', 'ETHUSDT']
        
        try:
            # Start paper trading first
            await paper_engine.start()
            print("✅ Paper trading engine started")
            
            # Connect engines
            profit_engine.paper_trading_engine = paper_engine
            paper_engine.profit_scraping_engine = profit_engine
            
            # Start profit scraping
            result = await profit_engine.start_scraping(test_symbols)
            print(f"   Start scraping result: {result}")
            print(f"   Engine active after start: {profit_engine.active}")
            print(f"   Monitored symbols after start: {profit_engine.monitored_symbols}")
            
            # Check if monitoring tasks are running
            if hasattr(profit_engine, 'monitoring_tasks'):
                print(f"   Monitoring tasks: {len(profit_engine.monitoring_tasks) if profit_engine.monitoring_tasks else 0}")
            
            # Wait a moment and check for activity
            print("\n   Waiting 10 seconds for activity...")
            await asyncio.sleep(10)
            
            # Check if any signals were generated
            recent_signals = await db.fetch_all("""
                SELECT symbol, signal_type, confidence, created_at
                FROM signals 
                WHERE created_at > datetime('now', '-1 minute')
                ORDER BY created_at DESC
            """)
            
            print(f"   Recent signals (last minute): {len(recent_signals)}")
            for signal in recent_signals:
                print(f"     {signal['symbol']} {signal['signal_type']} - Confidence: {signal['confidence']:.2f}")
            
        except Exception as e:
            print(f"❌ Error testing profit scraping startup: {e}")
            import traceback
            traceback.print_exc()
        
        # 4. Check API health endpoint
        print("\n4. CHECKING API HEALTH STATUS...")
        
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get('http://localhost:8000/health') as response:
                    if response.status == 200:
                        health_data = await response.json()
                        print("✅ API is running")
                        print("   Component status:")
                        for component, status in health_data.get('components', {}).items():
                            print(f"     {component}: {'✅' if status else '❌'}")
                    else:
                        print(f"❌ API health check failed: {response.status}")
        except Exception as e:
            print(f"❌ Could not check API health: {e}")
        
        # 5. Check profit scraping API endpoints
        print("\n5. CHECKING PROFIT SCRAPING API ENDPOINTS...")
        
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                # Check status endpoint
                async with session.get('http://localhost:8000/api/v1/profit-scraping/status') as response:
                    if response.status == 200:
                        status_data = await response.json()
                        print("✅ Profit scraping status endpoint working")
                        print(f"   Active: {status_data.get('active', False)}")
                        print(f"   Monitored symbols: {status_data.get('monitored_symbols', [])}")
                    else:
                        print(f"❌ Profit scraping status endpoint failed: {response.status}")
                        
                # Check positions endpoint
                async with session.get('http://localhost:8000/api/v1/profit-scraping/positions') as response:
                    if response.status == 200:
                        positions_data = await response.json()
                        print(f"✅ Profit scraping positions endpoint working - {len(positions_data)} positions")
                    else:
                        print(f"❌ Profit scraping positions endpoint failed: {response.status}")
                        
        except Exception as e:
            print(f"❌ Could not check profit scraping API endpoints: {e}")
        
        await db.close()
        
    except Exception as e:
        print(f"❌ CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("🎯 DIAGNOSIS COMPLETE!")
    print("\nPOSSIBLE CAUSES FOR MISSING PROFIT SCRAPING LOGS:")
    print("1. Profit scraping engine not starting during API initialization")
    print("2. Profit scraping engine starting but not generating signals")
    print("3. Profit scraping engine running but logging at different level")
    print("4. Profit scraping engine failing silently during operation")
    print("5. PM2 not capturing profit scraping logs properly")

if __name__ == "__main__":
    asyncio.run(diagnose_profit_scraping_logs())
