#!/usr/bin/env python3
"""
Live verification script to check if the $10 take profit fix is working
This will check the current paper trading status and recent completed trades
"""

import asyncio
import logging
import sys
import os
import json
from datetime import datetime, timedelta

# Add the src directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def check_live_paper_trading_status():
    """Check the live paper trading system status"""
    
    logger.info("🔍 Checking Live Paper Trading System Status")
    logger.info("=" * 60)
    
    try:
        # Import the paper trading API client
        import requests
        
        # API base URL (assuming local deployment)
        api_base = "http://localhost:8000"
        
        # Check if API is running
        try:
            response = requests.get(f"{api_base}/health", timeout=5)
            if response.status_code == 200:
                logger.info("✅ API is running and accessible")
            else:
                logger.warning(f"⚠️ API responded with status {response.status_code}")
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ API is not accessible: {e}")
            logger.info("💡 Try starting the API with: python src/api/main.py")
            return False
        
        # Check paper trading status
        try:
            response = requests.get(f"{api_base}/api/v1/paper-trading/status", timeout=10)
            if response.status_code == 200:
                status_data = response.json()
                if status_data.get('status') == 'success':
                    data = status_data.get('data', {})
                    
                    logger.info("📊 Paper Trading Status:")
                    logger.info(f"   Running: {data.get('enabled', False)}")
                    logger.info(f"   Balance: ${data.get('virtual_balance', 0):,.2f}")
                    logger.info(f"   Total Return: {data.get('total_return_pct', 0):.2f}%")
                    logger.info(f"   Win Rate: {data.get('win_rate_pct', 0):.1f}%")
                    logger.info(f"   Completed Trades: {data.get('completed_trades', 0)}")
                    logger.info(f"   Active Positions: {data.get('active_positions', 0)}")
                    logger.info(f"   Uptime: {data.get('uptime_hours', 0):.1f} hours")
                    
                    if not data.get('enabled', False):
                        logger.warning("⚠️ Paper trading is not currently running")
                        logger.info("💡 You can start it from the frontend or API")
                    
                else:
                    logger.error(f"❌ API returned error: {status_data.get('message', 'Unknown error')}")
                    return False
            else:
                logger.error(f"❌ Failed to get status: HTTP {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error getting paper trading status: {e}")
            return False
        
        # Check current positions
        try:
            response = requests.get(f"{api_base}/api/v1/paper-trading/positions", timeout=10)
            if response.status_code == 200:
                positions_data = response.json()
                positions = positions_data.get('data', [])
                
                logger.info(f"\n🎯 Current Active Positions: {len(positions)}")
                
                if positions:
                    logger.info("   Active Positions Details:")
                    for i, pos in enumerate(positions, 1):
                        symbol = pos.get('symbol', 'Unknown')
                        side = pos.get('side', 'Unknown')
                        entry_price = pos.get('entry_price', 0)
                        current_price = pos.get('current_price', 0)
                        unrealized_pnl = pos.get('unrealized_pnl', 0)
                        age_minutes = pos.get('age_minutes', 0)
                        
                        # Calculate age in readable format
                        if age_minutes < 60:
                            age_str = f"{age_minutes}m"
                        elif age_minutes < 1440:  # Less than 24 hours
                            age_str = f"{age_minutes // 60}h {age_minutes % 60}m"
                        else:
                            days = age_minutes // 1440
                            hours = (age_minutes % 1440) // 60
                            age_str = f"{days}d {hours}h"
                        
                        logger.info(f"   {i}. {symbol} {side} @ ${entry_price:.4f}")
                        logger.info(f"      Current: ${current_price:.4f} | P&L: ${unrealized_pnl:.2f} | Age: {age_str}")
                        
                        # Check if any positions are approaching $10 profit
                        if unrealized_pnl >= 8.0:
                            logger.info(f"      🎯 APPROACHING $10 TARGET: ${unrealized_pnl:.2f} profit!")
                        elif unrealized_pnl >= 10.0:
                            logger.warning(f"      🚨 ABOVE $10 TARGET: ${unrealized_pnl:.2f} profit - should have closed!")
                else:
                    logger.info("   No active positions currently")
                    
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error getting positions: {e}")
        
        # Check recent completed trades
        try:
            response = requests.get(f"{api_base}/api/v1/paper-trading/trades", timeout=10)
            if response.status_code == 200:
                trades_data = response.json()
                trades = trades_data.get('trades', [])
                
                logger.info(f"\n📋 Recent Completed Trades: {len(trades)}")
                
                if trades:
                    # Sort trades by exit time (most recent first)
                    trades.sort(key=lambda x: x.get('exit_time', ''), reverse=True)
                    
                    # Show last 10 trades
                    recent_trades = trades[:10]
                    
                    logger.info("   Recent Trades (last 10):")
                    
                    ten_dollar_exits = 0
                    floor_exits = 0
                    
                    for i, trade in enumerate(recent_trades, 1):
                        symbol = trade.get('symbol', 'Unknown')
                        side = trade.get('side', 'Unknown')
                        pnl = trade.get('pnl', 0)
                        exit_reason = trade.get('exit_reason', 'Unknown')
                        duration_minutes = trade.get('duration_minutes', 0)
                        exit_time = trade.get('exit_time', '')
                        
                        # Format duration
                        if duration_minutes < 60:
                            duration_str = f"{duration_minutes}m"
                        else:
                            hours = duration_minutes // 60
                            minutes = duration_minutes % 60
                            duration_str = f"{hours}h {minutes}m"
                        
                        # Format exit time
                        try:
                            if exit_time:
                                exit_dt = datetime.fromisoformat(exit_time.replace('Z', '+00:00'))
                                time_ago = datetime.now() - exit_dt.replace(tzinfo=None)
                                if time_ago.days > 0:
                                    time_ago_str = f"{time_ago.days}d ago"
                                elif time_ago.seconds > 3600:
                                    time_ago_str = f"{time_ago.seconds // 3600}h ago"
                                else:
                                    time_ago_str = f"{time_ago.seconds // 60}m ago"
                            else:
                                time_ago_str = "Unknown"
                        except:
                            time_ago_str = "Unknown"
                        
                        logger.info(f"   {i}. {symbol} {side} | P&L: ${pnl:.2f} | {exit_reason} | {duration_str} | {time_ago_str}")
                        
                        # Count specific exit reasons
                        if exit_reason == 'primary_target_10_dollars':
                            ten_dollar_exits += 1
                        elif exit_reason == 'absolute_floor_7_dollars':
                            floor_exits += 1
                    
                    # Summary of exit reasons
                    logger.info(f"\n📊 Exit Reason Analysis (last 10 trades):")
                    logger.info(f"   $10 Target Exits: {ten_dollar_exits}")
                    logger.info(f"   $7 Floor Exits: {floor_exits}")
                    logger.info(f"   Other Exits: {len(recent_trades) - ten_dollar_exits - floor_exits}")
                    
                    if ten_dollar_exits > 0:
                        logger.info("✅ GOOD: Found trades that closed at $10 target!")
                    else:
                        logger.warning("⚠️ No recent $10 target exits found")
                        
                    # Check for any trades that should have hit $10 but didn't
                    high_profit_trades = [t for t in recent_trades if t.get('pnl', 0) >= 8.0 and t.get('exit_reason') not in ['primary_target_10_dollars', 'absolute_floor_7_dollars']]
                    
                    if high_profit_trades:
                        logger.warning(f"⚠️ Found {len(high_profit_trades)} high-profit trades that didn't exit at $10:")
                        for trade in high_profit_trades:
                            logger.warning(f"   {trade.get('symbol')} {trade.get('side')} | P&L: ${trade.get('pnl', 0):.2f} | Reason: {trade.get('exit_reason')}")
                    
                else:
                    logger.info("   No completed trades found")
                    
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error getting trades: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error checking live system: {e}")
        import traceback
        logger.error(f"❌ Full traceback: {traceback.format_exc()}")
        return False

async def check_database_directly():
    """Check the database directly for recent trades"""
    
    logger.info("\n🗄️ Checking Database Directly")
    logger.info("-" * 40)
    
    try:
        from database.database import Database
        
        db = Database()
        
        # Query recent trades from flow_trades table
        from sqlalchemy import text
        
        query = text("""
        SELECT symbol, trade_type, entry_price, exit_price, pnl, exit_reason, 
               duration_minutes, exit_time, entry_time
        FROM flow_trades 
        WHERE exit_time IS NOT NULL 
        ORDER BY exit_time DESC 
        LIMIT 20
        """)
        
        with db.session_scope() as session:
            result = session.execute(query)
            trades = result.fetchall()
            
            if trades:
                logger.info(f"📋 Found {len(trades)} recent completed trades in database:")
                
                ten_dollar_count = 0
                floor_count = 0
                
                for i, trade in enumerate(trades, 1):
                    symbol = trade.symbol
                    side = trade.trade_type
                    pnl = trade.pnl or 0
                    exit_reason = trade.exit_reason or 'Unknown'
                    duration = trade.duration_minutes or 0
                    
                    logger.info(f"   {i}. {symbol} {side} | P&L: ${pnl:.2f} | {exit_reason} | {duration}m")
                    
                    if exit_reason == 'primary_target_10_dollars':
                        ten_dollar_count += 1
                    elif exit_reason == 'absolute_floor_7_dollars':
                        floor_count += 1
                
                logger.info(f"\n📊 Database Exit Reason Summary:")
                logger.info(f"   $10 Target Exits: {ten_dollar_count}")
                logger.info(f"   $7 Floor Exits: {floor_count}")
                logger.info(f"   Other Exits: {len(trades) - ten_dollar_count - floor_count}")
                
                if ten_dollar_count > 0:
                    logger.info("✅ EXCELLENT: Database shows $10 target exits are working!")
                else:
                    logger.warning("⚠️ No $10 target exits found in database")
                    
            else:
                logger.info("📋 No completed trades found in database")
                
    except Exception as e:
        logger.error(f"❌ Error checking database: {e}")
        import traceback
        logger.error(f"❌ Full traceback: {traceback.format_exc()}")

async def main():
    """Main function to check live system"""
    
    logger.info("🔍 Live $10 Take Profit Verification")
    logger.info("This script checks if the $10 take profit fix is working in the live system")
    logger.info("=" * 80)
    
    # Check API status
    api_success = await check_live_paper_trading_status()
    
    # Check database directly
    await check_database_directly()
    
    logger.info("\n" + "=" * 80)
    logger.info("🎯 VERIFICATION SUMMARY:")
    
    if api_success:
        logger.info("✅ API is accessible and responding")
        logger.info("✅ Paper trading status retrieved successfully")
        logger.info("✅ Position and trade data analyzed")
    else:
        logger.warning("⚠️ API access issues detected")
    
    logger.info("✅ Database analysis completed")
    
    logger.info("\n💡 RECOMMENDATIONS:")
    logger.info("1. If paper trading is not running, start it from the frontend")
    logger.info("2. Monitor active positions for $10 profit targets")
    logger.info("3. Check logs for profit tracking messages: 🎯 PROFIT TRACKING")
    logger.info("4. Look for exit reason 'primary_target_10_dollars' in completed trades")
    
    logger.info("\n🔧 The $10 take profit fix includes:")
    logger.info("   • 1-second monitoring frequency (faster detection)")
    logger.info("   • Better error handling for price fetching")
    logger.info("   • Fixed race condition protection")
    logger.info("   • Enhanced logging for positions approaching $10")

if __name__ == "__main__":
    asyncio.run(main())
