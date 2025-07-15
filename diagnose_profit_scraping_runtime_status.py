#!/usr/bin/env python3

"""
Diagnose Profit Scraping Runtime Status
Check if the profit scraping engine is actually running and generating signals in the live system
"""

import asyncio
import logging
import sys
import requests
import json
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def check_api_health():
    """Check if the API is running and what components are active"""
    try:
        logger.info("🔍 Checking API health status...")
        
        response = requests.get("http://localhost:8000/health", timeout=10)
        if response.status_code == 200:
            health_data = response.json()
            logger.info("✅ API is running")
            
            components = health_data.get('components', {})
            logger.info("📊 Component Status:")
            for component, status in components.items():
                status_icon = "✅" if status else "❌"
                logger.info(f"   {status_icon} {component}: {status}")
            
            return health_data
        else:
            logger.error(f"❌ API health check failed: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Failed to connect to API: {e}")
        return None

async def check_profit_scraping_status():
    """Check profit scraping engine status via API"""
    try:
        logger.info("🎯 Checking profit scraping engine status...")
        
        response = requests.get("http://localhost:8000/api/v1/profit-scraping/status", timeout=10)
        if response.status_code == 200:
            status_data = response.json()
            logger.info("✅ Profit scraping API endpoint accessible")
            
            logger.info("📊 Profit Scraping Status:")
            logger.info(f"   Active: {status_data.get('active', False)}")
            logger.info(f"   Monitored Symbols: {status_data.get('monitored_symbols', [])}")
            logger.info(f"   Active Trades: {status_data.get('active_trades', 0)}")
            logger.info(f"   Total Trades: {status_data.get('total_trades', 0)}")
            logger.info(f"   Uptime (minutes): {status_data.get('uptime_minutes', 0):.1f}")
            
            return status_data
        else:
            logger.error(f"❌ Profit scraping status check failed: {response.status_code}")
            if response.status_code == 404:
                logger.error("   This suggests the profit scraping routes are not properly registered")
            return None
            
    except Exception as e:
        logger.error(f"❌ Failed to check profit scraping status: {e}")
        return None

async def check_profit_scraping_opportunities():
    """Check if profit scraping engine is generating opportunities"""
    try:
        logger.info("🔍 Checking profit scraping opportunities...")
        
        response = requests.get("http://localhost:8000/api/v1/profit-scraping/opportunities", timeout=10)
        if response.status_code == 200:
            opportunities_data = response.json()
            logger.info("✅ Profit scraping opportunities endpoint accessible")
            
            total_opportunities = 0
            for symbol, opportunities in opportunities_data.items():
                if opportunities:
                    logger.info(f"   {symbol}: {len(opportunities)} opportunities")
                    total_opportunities += len(opportunities)
                    
                    # Show first opportunity details
                    if opportunities:
                        opp = opportunities[0]
                        logger.info(f"     Top opportunity: Score {opp.get('opportunity_score', 0)}, Level {opp.get('level', {}).get('level_type', 'unknown')}")
            
            if total_opportunities == 0:
                logger.warning("⚠️ No opportunities found - this could be normal or indicate an issue")
            else:
                logger.info(f"📈 Total opportunities: {total_opportunities}")
            
            return opportunities_data
        else:
            logger.error(f"❌ Profit scraping opportunities check failed: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Failed to check profit scraping opportunities: {e}")
        return None

async def check_paper_trading_status():
    """Check paper trading engine status"""
    try:
        logger.info("📊 Checking paper trading engine status...")
        
        response = requests.get("http://localhost:8000/api/v1/paper-trading/status", timeout=10)
        if response.status_code == 200:
            status_data = response.json()
            logger.info("✅ Paper trading API endpoint accessible")
            
            logger.info("📊 Paper Trading Status:")
            logger.info(f"   Running: {status_data.get('is_running', False)}")
            logger.info(f"   Balance: ${status_data.get('account', {}).get('balance', 0):.2f}")
            logger.info(f"   Active Positions: {status_data.get('account', {}).get('active_positions', 0)}")
            logger.info(f"   Total Trades: {status_data.get('account', {}).get('total_trades', 0)}")
            
            # Check signal sources
            signal_sources = status_data.get('signal_sources', {})
            if signal_sources:
                logger.info("🎯 Signal Sources:")
                for source, enabled in signal_sources.items():
                    status_icon = "✅" if enabled else "❌"
                    logger.info(f"   {status_icon} {source}: {enabled}")
            
            return status_data
        else:
            logger.error(f"❌ Paper trading status check failed: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Failed to check paper trading status: {e}")
        return None

async def check_paper_trading_positions():
    """Check current paper trading positions"""
    try:
        logger.info("📋 Checking paper trading positions...")
        
        response = requests.get("http://localhost:8000/api/v1/paper-trading/positions", timeout=10)
        if response.status_code == 200:
            positions_data = response.json()
            logger.info("✅ Paper trading positions endpoint accessible")
            
            positions = positions_data.get('positions', [])
            if positions:
                logger.info(f"📈 Found {len(positions)} active positions:")
                for pos in positions[:5]:  # Show first 5
                    logger.info(f"   {pos.get('symbol')} {pos.get('side')} - P&L: ${pos.get('unrealized_pnl', 0):.2f}")
            else:
                logger.warning("⚠️ No active positions found")
            
            return positions_data
        else:
            logger.error(f"❌ Paper trading positions check failed: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Failed to check paper trading positions: {e}")
        return None

async def test_signal_generation():
    """Test if signals are being generated"""
    try:
        logger.info("🔄 Testing signal generation...")
        
        # Try to get fresh opportunities from paper trading
        response = requests.post("http://localhost:8000/api/v1/paper-trading/test-signal-generation", timeout=15)
        if response.status_code == 200:
            signal_data = response.json()
            logger.info("✅ Signal generation test successful")
            
            signals = signal_data.get('signals', [])
            if signals:
                logger.info(f"📡 Generated {len(signals)} signals:")
                for signal in signals[:3]:  # Show first 3
                    logger.info(f"   {signal.get('symbol')} {signal.get('side')} (confidence: {signal.get('confidence', 0):.3f})")
            else:
                logger.warning("⚠️ No signals generated - this could indicate an issue")
            
            return signal_data
        else:
            logger.error(f"❌ Signal generation test failed: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Failed to test signal generation: {e}")
        return None

async def main():
    """Main diagnostic function"""
    logger.info("🔧 Starting Profit Scraping Runtime Diagnosis...")
    logger.info("="*60)
    
    # Step 1: Check API health
    health_data = await check_api_health()
    if not health_data:
        logger.error("❌ Cannot proceed - API is not accessible")
        return 1
    
    logger.info("\n" + "="*60)
    
    # Step 2: Check profit scraping status
    profit_status = await check_profit_scraping_status()
    
    logger.info("\n" + "="*60)
    
    # Step 3: Check profit scraping opportunities
    opportunities = await check_profit_scraping_opportunities()
    
    logger.info("\n" + "="*60)
    
    # Step 4: Check paper trading status
    paper_status = await check_paper_trading_status()
    
    logger.info("\n" + "="*60)
    
    # Step 5: Check paper trading positions
    positions = await check_paper_trading_positions()
    
    logger.info("\n" + "="*60)
    
    # Step 6: Test signal generation
    signals = await test_signal_generation()
    
    logger.info("\n" + "="*60)
    
    # Final analysis
    logger.info("📊 DIAGNOSIS SUMMARY:")
    logger.info("="*60)
    
    # Analyze results
    api_healthy = health_data is not None
    profit_scraping_accessible = profit_status is not None
    profit_scraping_active = profit_status and profit_status.get('active', False) if profit_status else False
    paper_trading_running = paper_status and paper_status.get('is_running', False) if paper_status else False
    has_positions = positions and len(positions.get('positions', [])) > 0 if positions else False
    
    logger.info(f"✅ API Health: {'GOOD' if api_healthy else 'FAILED'}")
    logger.info(f"{'✅' if profit_scraping_accessible else '❌'} Profit Scraping API: {'ACCESSIBLE' if profit_scraping_accessible else 'FAILED'}")
    logger.info(f"{'✅' if profit_scraping_active else '❌'} Profit Scraping Active: {'YES' if profit_scraping_active else 'NO'}")
    logger.info(f"{'✅' if paper_trading_running else '❌'} Paper Trading Running: {'YES' if paper_trading_running else 'NO'}")
    logger.info(f"{'✅' if has_positions else '⚠️'} Active Positions: {'YES' if has_positions else 'NO'}")
    
    # Determine root cause
    if not profit_scraping_accessible:
        logger.error("🚨 ROOT CAUSE: Profit scraping API endpoints are not accessible")
        logger.error("   This suggests the profit scraping routes are not properly registered")
    elif not profit_scraping_active:
        logger.error("🚨 ROOT CAUSE: Profit scraping engine is not active")
        logger.error("   The engine may have failed to start or crashed during initialization")
    elif not paper_trading_running:
        logger.error("🚨 ROOT CAUSE: Paper trading engine is not running")
        logger.error("   Paper trading may have failed to start or connect to profit scraping")
    elif not has_positions:
        logger.warning("⚠️ LIKELY CAUSE: No trading opportunities found")
        logger.warning("   This could be normal market conditions or signal filtering issues")
    else:
        logger.info("✅ All systems appear to be working correctly")
    
    logger.info("="*60)
    
    return 0 if api_healthy and profit_scraping_accessible and profit_scraping_active else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
