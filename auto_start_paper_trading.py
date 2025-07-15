#!/usr/bin/env python3
"""
Auto-start Paper Trading with Profit Scraping
Ensures paper trading and profit scraping engines start automatically on system boot
"""

import asyncio
import logging
import os
import sys
import time
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.utils.logger import setup_logger

logger = setup_logger(__name__)

async def wait_for_api():
    """Wait for API to be ready before starting paper trading"""
    import requests
    
    max_retries = 30  # Wait up to 5 minutes
    retry_delay = 10  # 10 seconds between retries
    
    for attempt in range(max_retries):
        try:
            response = requests.get("http://localhost:8000/health", timeout=5)
            if response.status_code == 200:
                logger.info("✅ API is ready!")
                return True
        except Exception as e:
            logger.info(f"⏳ Waiting for API... (attempt {attempt + 1}/{max_retries})")
            await asyncio.sleep(retry_delay)
    
    logger.error("❌ API not ready after waiting")
    return False

async def start_paper_trading():
    """Start paper trading via API"""
    import requests
    
    try:
        logger.info("🚀 Starting paper trading...")
        response = requests.post("http://localhost:8000/api/v1/paper-trading/start", timeout=10)
        
        if response.status_code == 200:
            logger.info("✅ Paper trading started successfully")
            return True
        else:
            logger.error(f"❌ Failed to start paper trading: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ Error starting paper trading: {e}")
        return False

async def start_profit_scraping():
    """Start profit scraping via API"""
    import requests
    
    try:
        logger.info("🎯 Starting profit scraping...")
        
        # Get all available symbols
        symbols_response = requests.get("http://localhost:8000/api/v1/profit-scraping/symbols", timeout=10)
        if symbols_response.status_code == 200:
            symbols = symbols_response.json().get('symbols', [])
            # Use top 20 most liquid symbols
            symbols = symbols[:20]
        else:
            # Fallback to hardcoded symbols
            symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'SOLUSDT', 'DOGEUSDT', 'XRPUSDT', 'LTCUSDT', 'AVAXUSDT', 'DOTUSDT']
        
        logger.info(f"📊 Starting profit scraping with {len(symbols)} symbols")
        
        # Start profit scraping
        response = requests.post(
            "http://localhost:8000/api/v1/profit-scraping/start",
            json={"symbols": symbols},
            timeout=30
        )
        
        if response.status_code == 200:
            logger.info("✅ Profit scraping started successfully")
            return True
        else:
            logger.error(f"❌ Failed to start profit scraping: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ Error starting profit scraping: {e}")
        return False

async def monitor_systems():
    """Monitor paper trading and profit scraping systems"""
    import requests
    
    while True:
        try:
            # Check paper trading status
            paper_response = requests.get("http://localhost:8000/api/v1/paper-trading/status", timeout=5)
            profit_response = requests.get("http://localhost:8000/api/v1/profit-scraping/status", timeout=5)
            
            if paper_response.status_code == 200 and profit_response.status_code == 200:
                paper_status = paper_response.json()
                profit_status = profit_response.json()
                
                logger.info(f"📊 Paper Trading: {paper_status.get('status', 'unknown')} | Profit Scraping: {profit_status.get('status', 'unknown')}")
                
                # Restart if needed
                if not paper_status.get('running', False):
                    logger.warning("⚠️ Paper trading not running, restarting...")
                    await start_paper_trading()
                
                if not profit_status.get('active', False):
                    logger.warning("⚠️ Profit scraping not active, restarting...")
                    await start_profit_scraping()
            
            await asyncio.sleep(60)  # Check every minute
            
        except KeyboardInterrupt:
            logger.info("🛑 Monitoring stopped")
            break
        except Exception as e:
            logger.error(f"❌ Error in monitoring: {e}")
            await asyncio.sleep(30)

async def main():
    """Main auto-start routine"""
    try:
        logger.info("🚀 Starting auto-start paper trading system...")
        
        # Wait for API to be ready
        if not await wait_for_api():
            logger.error("❌ API not ready, cannot start paper trading")
            return
        
        # Start paper trading
        paper_started = await start_paper_trading()
        if not paper_started:
            logger.error("❌ Failed to start paper trading")
            return
        
        # Start profit scraping
        profit_started = await start_profit_scraping()
        if not profit_started:
            logger.error("❌ Failed to start profit scraping")
            return
        
        logger.info("✅ Auto-start completed successfully!")
        logger.info("🔄 Starting monitoring loop...")
        
        # Monitor systems
        await monitor_systems()
        
    except Exception as e:
        logger.error(f"❌ Error in auto-start: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main()) 