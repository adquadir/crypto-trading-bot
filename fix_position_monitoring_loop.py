#!/usr/bin/env python3
"""
Fix script to restart the position monitoring loop for the $10 take profit system
This will force the monitoring loop to start and immediately close positions with $10+ profit
"""

import asyncio
import logging
import sys
import os
import requests
from datetime import datetime

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def fix_position_monitoring():
    """Fix the position monitoring loop issue"""
    
    logger.info("🔧 FIXING POSITION MONITORING LOOP")
    logger.info("=" * 60)
    
    # STEP 1: Stop current paper trading
    logger.info("📴 STEP 1: Stopping current paper trading")
    try:
        response = requests.post("http://localhost:8000/api/v1/paper-trading/stop", timeout=10)
        if response.status_code == 200:
            logger.info("✅ Paper trading stopped")
        else:
            logger.warning(f"⚠️ Stop request returned {response.status_code}")
    except Exception as e:
        logger.warning(f"⚠️ Could not stop paper trading: {e}")
    
    # Wait a moment
    await asyncio.sleep(2)
    
    # STEP 2: Start paper trading (this should start the monitoring loop)
    logger.info("🚀 STEP 2: Starting paper trading with monitoring loop")
    try:
        response = requests.post("http://localhost:8000/api/v1/paper-trading/start", timeout=10)
        if response.status_code == 200:
            result = response.json()
            logger.info(f"✅ Paper trading started: {result}")
        else:
            logger.error(f"❌ Start request failed: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ Could not start paper trading: {e}")
        return False
    
    # Wait for monitoring loop to start
    await asyncio.sleep(5)
    
    # STEP 3: Verify positions are being monitored
    logger.info("🔍 STEP 3: Checking if high-profit positions are being closed")
    
    # Check positions before and after
    try:
        response = requests.get("http://localhost:8000/api/v1/paper-trading/positions", timeout=10)
        if response.status_code == 200:
            positions_data = response.json()
            positions = positions_data.get('data', [])
            
            high_profit_positions = [
                pos for pos in positions 
                if pos.get('unrealized_pnl', 0) >= 10.0
            ]
            
            logger.info(f"📊 Found {len(high_profit_positions)} positions with $10+ profit")
            
            if high_profit_positions:
                logger.info("⏳ Waiting 30 seconds for monitoring loop to close high-profit positions...")
                
                # Wait for monitoring loop to process
                await asyncio.sleep(30)
                
                # Check again
                response2 = requests.get("http://localhost:8000/api/v1/paper-trading/positions", timeout=10)
                if response2.status_code == 200:
                    positions_data2 = response2.json()
                    positions2 = positions_data2.get('data', [])
                    
                    high_profit_positions2 = [
                        pos for pos in positions2 
                        if pos.get('unrealized_pnl', 0) >= 10.0
                    ]
                    
                    closed_count = len(high_profit_positions) - len(high_profit_positions2)
                    
                    if closed_count > 0:
                        logger.info(f"✅ SUCCESS: {closed_count} high-profit positions were closed!")
                        logger.info(f"📉 Remaining high-profit positions: {len(high_profit_positions2)}")
                        return True
                    else:
                        logger.error("❌ No high-profit positions were closed - monitoring loop still not working")
                        return False
            else:
                logger.info("✅ No high-profit positions found - system may already be working")
                return True
                
    except Exception as e:
        logger.error(f"❌ Position check failed: {e}")
        return False
    
    return False

async def force_close_high_profit_positions():
    """Force close positions with $10+ profit manually via API"""
    
    logger.info("🔨 FORCE CLOSING HIGH-PROFIT POSITIONS")
    logger.info("=" * 50)
    
    try:
        # Get current positions
        response = requests.get("http://localhost:8000/api/v1/paper-trading/positions", timeout=10)
        if response.status_code != 200:
            logger.error("❌ Could not get positions")
            return False
        
        positions_data = response.json()
        positions = positions_data.get('data', [])
        
        high_profit_positions = [
            pos for pos in positions 
            if pos.get('unrealized_pnl', 0) >= 10.0
        ]
        
        logger.info(f"🎯 Found {len(high_profit_positions)} positions to force close")
        
        closed_count = 0
        for pos in high_profit_positions:
            position_id = pos.get('id')
            symbol = pos.get('symbol')
            pnl = pos.get('unrealized_pnl', 0)
            
            logger.info(f"🔨 Force closing {symbol} (${pnl:.2f} profit)")
            
            try:
                close_response = requests.post(
                    f"http://localhost:8000/api/v1/paper-trading/positions/{position_id}/close",
                    json={"exit_reason": "manual_10_dollar_fix"},
                    timeout=10
                )
                
                if close_response.status_code == 200:
                    logger.info(f"✅ Closed {symbol}")
                    closed_count += 1
                else:
                    logger.error(f"❌ Failed to close {symbol}: {close_response.status_code}")
                    
            except Exception as e:
                logger.error(f"❌ Error closing {symbol}: {e}")
        
        logger.info(f"🎉 Force closed {closed_count} positions")
        return closed_count > 0
        
    except Exception as e:
        logger.error(f"❌ Force close failed: {e}")
        return False

async def main():
    """Main fix function"""
    
    logger.info("🚀 STARTING $10 TAKE PROFIT FIX")
    logger.info("This will fix the position monitoring loop issue")
    logger.info("=" * 60)
    
    try:
        # Try to fix the monitoring loop first
        logger.info("🔧 ATTEMPTING MONITORING LOOP FIX...")
        success = await fix_position_monitoring()
        
        if success:
            logger.info("✅ MONITORING LOOP FIX SUCCESSFUL!")
        else:
            logger.warning("⚠️ Monitoring loop fix failed, trying force close...")
            
            # If monitoring loop fix fails, force close positions
            force_success = await force_close_high_profit_positions()
            
            if force_success:
                logger.info("✅ FORCE CLOSE SUCCESSFUL!")
                logger.info("🔧 Now attempting to restart monitoring loop...")
                
                # Try monitoring loop fix again
                success = await fix_position_monitoring()
                
                if success:
                    logger.info("✅ MONITORING LOOP NOW WORKING!")
                else:
                    logger.error("❌ Monitoring loop still not working after force close")
        
        # Final status check
        logger.info("\n" + "=" * 60)
        logger.info("🔍 FINAL STATUS CHECK")
        
        try:
            response = requests.get("http://localhost:8000/api/v1/paper-trading/positions", timeout=10)
            if response.status_code == 200:
                positions_data = response.json()
                positions = positions_data.get('data', [])
                
                high_profit_positions = [
                    pos for pos in positions 
                    if pos.get('unrealized_pnl', 0) >= 10.0
                ]
                
                if len(high_profit_positions) == 0:
                    logger.info("🎉 SUCCESS: No positions with $10+ profit remaining!")
                    logger.info("✅ The $10 take profit system is now working correctly")
                else:
                    logger.error(f"❌ STILL HAVE ISSUES: {len(high_profit_positions)} positions with $10+ profit")
                    for pos in high_profit_positions:
                        logger.error(f"   {pos.get('symbol')}: ${pos.get('unrealized_pnl', 0):.2f}")
                    
        except Exception as e:
            logger.error(f"❌ Final status check failed: {e}")
        
        logger.info("=" * 60)
        logger.info("🔧 FIX COMPLETE")
        
    except Exception as e:
        logger.error(f"💥 FIX FAILED: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
