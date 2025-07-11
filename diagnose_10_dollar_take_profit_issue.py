#!/usr/bin/env python3
"""
Comprehensive diagnostic script to identify why $10 take profit isn't working
This will check all aspects of the paper trading system to find the root cause
"""

import asyncio
import logging
import sys
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def diagnose_10_dollar_take_profit():
    """Comprehensive diagnosis of the $10 take profit issue"""
    
    logger.info("🔍 STARTING COMPREHENSIVE $10 TAKE PROFIT DIAGNOSIS")
    logger.info("=" * 80)
    
    issues_found = []
    recommendations = []
    
    # STEP 1: Check if paper trading API is accessible
    logger.info("\n📡 STEP 1: Testing Paper Trading API Connectivity")
    try:
        import requests
        
        # Test basic API connectivity
        api_url = "http://localhost:8000"  # Adjust if different
        
        try:
            response = requests.get(f"{api_url}/api/v1/paper-trading/status", timeout=10)
            if response.status_code == 200:
                status_data = response.json()
                logger.info(f"✅ API accessible: {status_data}")
                
                # Check if paper trading is enabled
                if status_data.get('data', {}).get('enabled', False):
                    logger.info("✅ Paper trading is ENABLED")
                else:
                    logger.error("❌ Paper trading is DISABLED")
                    issues_found.append("Paper trading is not enabled")
                    recommendations.append("Enable paper trading via API or frontend")
                    
            else:
                logger.error(f"❌ API returned status {response.status_code}")
                issues_found.append(f"API not accessible (status {response.status_code})")
                
        except requests.exceptions.ConnectionError:
            logger.error("❌ Cannot connect to API - is the server running?")
            issues_found.append("API server not running or not accessible")
            recommendations.append("Start the API server: python src/api/main.py")
            
        except Exception as e:
            logger.error(f"❌ API test failed: {e}")
            issues_found.append(f"API test failed: {e}")
            
    except ImportError:
        logger.warning("⚠️ requests module not available, skipping API test")
    
    # STEP 2: Check current positions
    logger.info("\n📊 STEP 2: Analyzing Current Positions")
    try:
        import requests
        response = requests.get(f"{api_url}/api/v1/paper-trading/positions", timeout=10)
        if response.status_code == 200:
            positions_data = response.json()
            positions = positions_data.get('data', [])
            
            logger.info(f"📈 Found {len(positions)} active positions")
            
            high_profit_positions = []
            for pos in positions:
                pnl = pos.get('unrealized_pnl', 0)
                symbol = pos.get('symbol', 'UNKNOWN')
                entry_price = pos.get('entry_price', 0)
                current_price = pos.get('current_price', 0)
                
                logger.info(f"   {symbol}: ${pnl:.2f} profit (Entry: ${entry_price:.4f}, Current: ${current_price:.4f})")
                
                if pnl >= 10.0:
                    high_profit_positions.append(pos)
                    logger.error(f"❌ FOUND ISSUE: {symbol} has ${pnl:.2f} profit (>= $10) but not closed!")
            
            if high_profit_positions:
                issues_found.append(f"Found {len(high_profit_positions)} positions with $10+ profit not closed")
                recommendations.append("Position monitoring loop is not working correctly")
                
                # Detailed analysis of high profit positions
                for pos in high_profit_positions:
                    logger.error(f"🚨 PROBLEM POSITION: {json.dumps(pos, indent=2)}")
            else:
                logger.info("✅ No positions with $10+ profit found (or they were properly closed)")
                
        else:
            logger.error(f"❌ Failed to get positions: {response.status_code}")
            
    except Exception as e:
        logger.error(f"❌ Position analysis failed: {e}")
        issues_found.append(f"Position analysis failed: {e}")
    
    # STEP 3: Check recent completed trades
    logger.info("\n📋 STEP 3: Analyzing Recent Completed Trades")
    try:
        response = requests.get(f"{api_url}/api/v1/paper-trading/trades", timeout=10)
        if response.status_code == 200:
            trades_data = response.json()
            trades = trades_data.get('trades', [])
            
            logger.info(f"📊 Found {len(trades)} completed trades")
            
            # Analyze recent trades (last 20)
            recent_trades = trades[-20:] if len(trades) > 20 else trades
            
            high_profit_trades = []
            primary_target_trades = []
            
            for trade in recent_trades:
                pnl = trade.get('pnl', 0)
                exit_reason = trade.get('exit_reason', 'unknown')
                symbol = trade.get('symbol', 'UNKNOWN')
                
                if pnl >= 10.0:
                    high_profit_trades.append(trade)
                    
                if exit_reason == 'primary_target_10_dollars':
                    primary_target_trades.append(trade)
                    
                logger.info(f"   {symbol}: ${pnl:.2f} profit, exit: {exit_reason}")
            
            logger.info(f"📈 High profit trades (>=$10): {len(high_profit_trades)}")
            logger.info(f"🎯 Primary target exits: {len(primary_target_trades)}")
            
            if high_profit_trades and not primary_target_trades:
                issues_found.append("Found high profit trades but none with 'primary_target_10_dollars' exit reason")
                recommendations.append("The $10 target detection is not working")
                
                # Show examples of high profit trades with wrong exit reasons
                for trade in high_profit_trades[:5]:  # Show first 5
                    logger.error(f"❌ HIGH PROFIT WRONG EXIT: {trade.get('symbol')} ${trade.get('pnl', 0):.2f} exit: {trade.get('exit_reason')}")
            
            elif primary_target_trades:
                logger.info(f"✅ Found {len(primary_target_trades)} trades that properly exited at $10 target")
                
        else:
            logger.error(f"❌ Failed to get trades: {response.status_code}")
            
    except Exception as e:
        logger.error(f"❌ Trade analysis failed: {e}")
        issues_found.append(f"Trade analysis failed: {e}")
    
    # STEP 4: Check paper trading engine status directly
    logger.info("\n🔧 STEP 4: Direct Paper Trading Engine Analysis")
    try:
        # Try to import and check the engine directly
        from src.trading.enhanced_paper_trading_engine import EnhancedPaperTradingEngine
        from src.market_data.exchange_client import ExchangeClient
        
        # Create a test engine to check the code
        config = {
            'paper_trading': {
                'initial_balance': 10000.0,
                'risk_per_trade_pct': 0.02,
                'max_positions': 50,
                'leverage': 10.0
            }
        }
        
        # Create exchange client
        exchange_client = ExchangeClient()
        await exchange_client.initialize()
        
        # Create engine
        engine = EnhancedPaperTradingEngine(config, exchange_client)
        
        # Check if the monitoring loop method exists and has the fix
        if hasattr(engine, '_position_monitoring_loop'):
            logger.info("✅ Position monitoring loop method exists")
            
            # Check the source code for the fix
            import inspect
            source = inspect.getsource(engine._position_monitoring_loop)
            
            if 'primary_target_10_dollars' in source:
                logger.info("✅ $10 target code is present in monitoring loop")
            else:
                logger.error("❌ $10 target code NOT found in monitoring loop")
                issues_found.append("$10 target code missing from position monitoring loop")
                
            if 'position.closed = True' in source:
                logger.info("✅ Atomic position closing code is present")
            else:
                logger.error("❌ Atomic position closing code NOT found")
                issues_found.append("Atomic position closing code missing")
                
        else:
            logger.error("❌ Position monitoring loop method does not exist")
            issues_found.append("Position monitoring loop method missing")
            
    except Exception as e:
        logger.error(f"❌ Direct engine analysis failed: {e}")
        issues_found.append(f"Direct engine analysis failed: {e}")
    
    # STEP 5: Check if monitoring loop is actually running
    logger.info("\n🔄 STEP 5: Checking if Monitoring Loop is Running")
    try:
        # Check recent logs for monitoring activity
        import subprocess
        import os
        
        # Try to find recent log files
        log_patterns = [
            "/var/log/crypto-trading-bot.log",
            "./crypto-trading-bot.log",
            "./logs/app.log",
            "/tmp/crypto-trading-bot.log"
        ]
        
        monitoring_activity_found = False
        
        for log_file in log_patterns:
            if os.path.exists(log_file):
                logger.info(f"📄 Checking log file: {log_file}")
                
                try:
                    # Check for recent monitoring activity
                    result = subprocess.run(
                        ['tail', '-n', '1000', log_file], 
                        capture_output=True, 
                        text=True, 
                        timeout=10
                    )
                    
                    log_content = result.stdout
                    
                    # Look for monitoring loop indicators
                    if '🎯 PROFIT TRACKING' in log_content:
                        logger.info("✅ Found profit tracking activity in logs")
                        monitoring_activity_found = True
                        
                    if '🎯 PRIMARY TARGET HIT' in log_content:
                        logger.info("✅ Found primary target detection in logs")
                        
                    if 'position monitoring loop' in log_content.lower():
                        logger.info("✅ Found position monitoring loop activity")
                        monitoring_activity_found = True
                        
                except Exception as log_error:
                    logger.warning(f"⚠️ Could not read log file {log_file}: {log_error}")
                    
        if not monitoring_activity_found:
            logger.error("❌ No monitoring loop activity found in logs")
            issues_found.append("Position monitoring loop appears to not be running")
            recommendations.append("Check if paper trading engine is properly started")
            
    except Exception as e:
        logger.error(f"❌ Log analysis failed: {e}")
    
    # STEP 6: Test the $10 target logic directly
    logger.info("\n🧪 STEP 6: Testing $10 Target Logic Directly")
    try:
        # Create a mock position with $13 profit
        from src.trading.enhanced_paper_trading_engine import PaperPosition
        from datetime import datetime
        
        test_position = PaperPosition(
            id="test-position",
            symbol="BTCUSDT",
            strategy_type="test",
            side="LONG",
            entry_price=50000.0,
            quantity=0.04,
            entry_time=datetime.utcnow(),
            capital_allocated=200.0,
            leverage=10.0,
            notional_value=2000.0
        )
        
        # Simulate $13 profit
        test_position.unrealized_pnl = 13.0
        test_position.current_price = 50325.0  # Price that gives $13 profit
        
        # Test the logic
        current_pnl_dollars = test_position.unrealized_pnl
        primary_target_profit = test_position.primary_target_profit  # Should be 10.0
        
        logger.info(f"🧪 Test position profit: ${current_pnl_dollars:.2f}")
        logger.info(f"🧪 Primary target: ${primary_target_profit:.2f}")
        
        if current_pnl_dollars >= primary_target_profit:
            logger.info("✅ $10 target logic test PASSED - would trigger exit")
        else:
            logger.error("❌ $10 target logic test FAILED - would NOT trigger exit")
            issues_found.append("$10 target logic test failed")
            
    except Exception as e:
        logger.error(f"❌ Logic test failed: {e}")
        issues_found.append(f"Logic test failed: {e}")
    
    # STEP 7: Check for multiple engine instances
    logger.info("\n🔀 STEP 7: Checking for Multiple Engine Instances")
    try:
        # Check if multiple processes are running
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        processes = result.stdout
        
        python_processes = [line for line in processes.split('\n') if 'python' in line and 'crypto' in line]
        
        logger.info(f"🔍 Found {len(python_processes)} relevant Python processes:")
        for proc in python_processes:
            logger.info(f"   {proc}")
            
        if len(python_processes) > 1:
            logger.warning("⚠️ Multiple Python processes found - possible engine conflicts")
            recommendations.append("Check for multiple running instances of the trading system")
            
    except Exception as e:
        logger.warning(f"⚠️ Process check failed: {e}")
    
    # FINAL SUMMARY
    logger.info("\n" + "=" * 80)
    logger.info("🔍 DIAGNOSIS SUMMARY")
    logger.info("=" * 80)
    
    if issues_found:
        logger.error(f"❌ FOUND {len(issues_found)} ISSUES:")
        for i, issue in enumerate(issues_found, 1):
            logger.error(f"   {i}. {issue}")
            
        logger.info(f"\n💡 RECOMMENDATIONS:")
        for i, rec in enumerate(recommendations, 1):
            logger.info(f"   {i}. {rec}")
            
        # Determine most likely root cause
        if "Position monitoring loop appears to not be running" in issues_found:
            logger.error("\n🎯 MOST LIKELY ROOT CAUSE: Position monitoring loop is not running")
            logger.error("   The $10 target code exists but the monitoring loop that checks it is not active")
            
        elif "Found high profit trades but none with 'primary_target_10_dollars' exit reason" in issues_found:
            logger.error("\n🎯 MOST LIKELY ROOT CAUSE: Monitoring loop running but $10 target not triggering")
            logger.error("   The loop is active but the $10 target condition is not being met or executed")
            
        elif "positions with $10+ profit not closed" in str(issues_found):
            logger.error("\n🎯 MOST LIKELY ROOT CAUSE: Active positions with $10+ profit exist")
            logger.error("   The system has positions that should have been closed but weren't")
            
    else:
        logger.info("✅ NO CRITICAL ISSUES FOUND")
        logger.info("   The $10 take profit system appears to be working correctly")
        logger.info("   If you're still seeing issues, they may be intermittent or in edge cases")
    
    return {
        'issues_found': issues_found,
        'recommendations': recommendations,
        'diagnosis_complete': True
    }

async def main():
    """Main diagnostic function"""
    try:
        result = await diagnose_10_dollar_take_profit()
        
        if result['issues_found']:
            logger.error("\n❌ DIAGNOSIS COMPLETE: Issues found that need to be fixed")
            sys.exit(1)
        else:
            logger.info("\n✅ DIAGNOSIS COMPLETE: No issues found")
            sys.exit(0)
            
    except Exception as e:
        logger.error(f"\n💥 DIAGNOSIS FAILED: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
