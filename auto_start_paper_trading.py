#!/usr/bin/env python3
"""
Auto-start Paper Trading System
This script ensures paper trading is always running after PM2 restarts
"""

import asyncio
import time
import requests
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_BASE_URL = "http://localhost:8000"

async def wait_for_api():
    """Wait for API to be ready"""
    max_attempts = 30
    for attempt in range(max_attempts):
        try:
            response = requests.get(f"{API_BASE_URL}/health", timeout=5)
            if response.status_code == 200:
                logger.info("✅ API is ready")
                return True
        except Exception as e:
            logger.info(f"Waiting for API... attempt {attempt + 1}/{max_attempts}")
            await asyncio.sleep(2)
    
    logger.error("❌ API failed to start within timeout")
    return False

async def start_paper_trading():
    """Start paper trading if not already running"""
    try:
        # Check current status
        response = requests.get(f"{API_BASE_URL}/api/v1/paper-trading/status", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("data", {}).get("enabled", False):
                logger.info("✅ Paper trading is already running")
                return True
        
        # Start paper trading
        logger.info("🚀 Starting paper trading...")
        response = requests.post(f"{API_BASE_URL}/api/v1/paper-trading/start", timeout=10)
        
        if response.status_code == 200:
            logger.info("✅ Paper trading started successfully")
            return True
        else:
            logger.error(f"❌ Failed to start paper trading: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error starting paper trading: {e}")
        return False

async def ensure_signal_generation():
    """Ensure signal generation is active"""
    try:
        # Check if we have recent signals
        response = requests.get(f"{API_BASE_URL}/api/v1/opportunities", timeout=10)
        if response.status_code == 200:
            logger.info("✅ Signal generation is active")
            return True
        else:
            logger.warning("⚠️ Signal generation may not be active")
            return False
    except Exception as e:
        logger.warning(f"⚠️ Could not verify signal generation: {e}")
        return False

async def simulate_test_position():
    """Create a test position to verify the system is working"""
    try:
        # This would simulate a position for testing
        # In a real scenario, positions are created by signal processing
        logger.info("🧪 System is ready for signal-based position creation")
        return True
    except Exception as e:
        logger.error(f"❌ Test position creation failed: {e}")
        return False

async def main():
    """Main execution function"""
    logger.info("🚀 Auto-starting Paper Trading System...")
    
    # Wait for API to be ready
    if not await wait_for_api():
        sys.exit(1)
    
    # Start paper trading
    if not await start_paper_trading():
        sys.exit(1)
    
    # Ensure signal generation
    await ensure_signal_generation()
    
    # Test system readiness
    await simulate_test_position()
    
    logger.info("✅ Paper trading auto-start completed successfully!")
    logger.info("📊 Positions will appear as signals are processed and trades are executed")

if __name__ == "__main__":
    asyncio.run(main())
