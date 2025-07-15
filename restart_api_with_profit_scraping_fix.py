#!/usr/bin/env python3

"""
Restart API Server with Profit Scraping Fix
This script will restart the API server and verify that the profit scraping engine is working
"""

import asyncio
import logging
import sys
import time
import subprocess
import signal
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def kill_existing_api_processes():
    """Kill any existing API server processes"""
    try:
        logger.info("🔍 Checking for existing API server processes...")
        
        # Find processes running on port 8000
        result = subprocess.run(['lsof', '-ti:8000'], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            logger.info(f"Found {len(pids)} processes on port 8000")
            
            for pid in pids:
                try:
                    logger.info(f"Killing process {pid}")
                    os.kill(int(pid), signal.SIGTERM)
                    time.sleep(1)
                    # Force kill if still running
                    try:
                        os.kill(int(pid), signal.SIGKILL)
                    except ProcessLookupError:
                        pass  # Process already dead
                except Exception as e:
                    logger.warning(f"Failed to kill process {pid}: {e}")
        else:
            logger.info("No existing processes found on port 8000")
            
        # Also check for uvicorn processes
        result = subprocess.run(['pkill', '-f', 'uvicorn.*main:app'], capture_output=True, text=True)
        if result.returncode == 0:
            logger.info("Killed existing uvicorn processes")
        
        time.sleep(2)  # Give processes time to die
        
    except Exception as e:
        logger.warning(f"Error killing existing processes: {e}")

def start_api_server():
    """Start the API server"""
    try:
        logger.info("🚀 Starting API server with profit scraping fixes...")
        
        # Start the server in the background
        process = subprocess.Popen([
            'uvicorn', 'src.api.main:app', 
            '--host', '0.0.0.0', 
            '--port', '8000',
            '--reload'
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        logger.info(f"API server started with PID: {process.pid}")
        
        # Wait a bit for startup
        time.sleep(5)
        
        # Check if process is still running
        if process.poll() is None:
            logger.info("✅ API server is running")
            return process
        else:
            stdout, stderr = process.communicate()
            logger.error(f"❌ API server failed to start")
            logger.error(f"STDOUT: {stdout}")
            logger.error(f"STDERR: {stderr}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Failed to start API server: {e}")
        return None

async def wait_for_api_ready():
    """Wait for the API to be ready"""
    import requests
    
    logger.info("⏳ Waiting for API to be ready...")
    
    for attempt in range(30):  # Wait up to 30 seconds
        try:
            response = requests.get("http://localhost:8000/health", timeout=2)
            if response.status_code == 200:
                logger.info("✅ API is ready!")
                return True
        except Exception:
            pass
        
        await asyncio.sleep(1)
    
    logger.error("❌ API failed to become ready within 30 seconds")
    return False

async def test_profit_scraping_integration():
    """Test the profit scraping integration"""
    import requests
    
    logger.info("🧪 Testing profit scraping integration...")
    
    try:
        # Test health endpoint
        response = requests.get("http://localhost:8000/health", timeout=10)
        if response.status_code == 200:
            health_data = response.json()
            logger.info("📊 Component Health Status:")
            
            components = health_data.get('components', {})
            for component, status in components.items():
                status_icon = "✅" if status else "❌"
                logger.info(f"   {status_icon} {component}: {status}")
            
            # Check if profit scraping engine is healthy
            profit_scraping_healthy = components.get('profit_scraping_engine', False)
            if profit_scraping_healthy:
                logger.info("🎯 Profit scraping engine is healthy!")
            else:
                logger.error("❌ Profit scraping engine is not healthy")
                return False
        else:
            logger.error(f"❌ Health check failed: {response.status_code}")
            return False
        
        # Test profit scraping status
        response = requests.get("http://localhost:8000/api/v1/profit-scraping/status", timeout=10)
        if response.status_code == 200:
            status_data = response.json()
            logger.info("📊 Profit Scraping Status:")
            logger.info(f"   Active: {status_data.get('active', False)}")
            logger.info(f"   Monitored Symbols: {status_data.get('monitored_symbols', [])}")
            logger.info(f"   Active Trades: {status_data.get('active_trades', 0)}")
            
            if status_data.get('active', False):
                logger.info("🎯 Profit scraping engine is ACTIVE!")
                return True
            else:
                logger.error("❌ Profit scraping engine is not active")
                return False
        else:
            logger.error(f"❌ Profit scraping status check failed: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Integration test failed: {e}")
        return False

async def main():
    """Main function"""
    logger.info("🔧 Starting API Restart with Profit Scraping Fix...")
    logger.info("="*60)
    
    # Step 1: Kill existing processes
    kill_existing_api_processes()
    
    # Step 2: Start API server
    process = start_api_server()
    if not process:
        logger.error("❌ Failed to start API server")
        return 1
    
    try:
        # Step 3: Wait for API to be ready
        if not await wait_for_api_ready():
            logger.error("❌ API failed to become ready")
            return 1
        
        # Step 4: Test profit scraping integration
        if await test_profit_scraping_integration():
            logger.info("🎉 SUCCESS: Profit scraping integration is working!")
            logger.info("📋 Next steps:")
            logger.info("   1. Check the paper trading page for positions")
            logger.info("   2. Monitor the logs for profit scraping activity")
            logger.info("   3. Run the diagnostic script to verify ongoing operation")
            logger.info("="*60)
            logger.info("🚀 API server is running with profit scraping enabled!")
            logger.info("   Access the API at: http://localhost:8000")
            logger.info("   Health check: http://localhost:8000/health")
            logger.info("   Profit scraping status: http://localhost:8000/api/v1/profit-scraping/status")
            logger.info("="*60)
            
            # Keep the server running
            logger.info("Press Ctrl+C to stop the server...")
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                logger.info("🛑 Shutting down server...")
                process.terminate()
                process.wait()
                logger.info("✅ Server stopped")
            
            return 0
        else:
            logger.error("❌ FAILURE: Profit scraping integration is not working")
            logger.error("💡 Check the server logs for detailed error information")
            return 1
            
    except KeyboardInterrupt:
        logger.info("🛑 Interrupted by user")
        if process:
            process.terminate()
            process.wait()
        return 0
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        if process:
            process.terminate()
            process.wait()
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
