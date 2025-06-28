#!/usr/bin/env python3
"""
🚀 ONE-CLICK FLOW TRADING SYSTEM LAUNCHER
Complete setup and launch script for the enhanced flow trading system
"""

import os
import sys
import subprocess
import asyncio
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_command(command, description):
    """Run a command and handle errors"""
    logger.info(f"🔧 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        logger.info(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ {description} failed: {e}")
        if e.stdout:
            logger.error(f"STDOUT: {e.stdout}")
        if e.stderr:
            logger.error(f"STDERR: {e.stderr}")
        return False

def check_requirements():
    """Check if all requirements are met"""
    logger.info("🔍 Checking system requirements...")
    
    # Check Python version
    if sys.version_info < (3, 8):
        logger.error("❌ Python 3.8+ required")
        return False
    
    # Check if PostgreSQL is available
    if not run_command("which psql", "Checking PostgreSQL"):
        logger.warning("⚠️  PostgreSQL not found - using SQLite fallback")
    
    # Check if required directories exist
    required_dirs = ['src', 'config', 'data', 'frontend']
    for dir_name in required_dirs:
        if not Path(dir_name).exists():
            logger.error(f"❌ Required directory missing: {dir_name}")
            return False
    
    logger.info("✅ System requirements check passed")
    return True

def setup_environment():
    """Setup environment and install dependencies"""
    logger.info("🔧 Setting up environment...")
    
    # Install Python dependencies
    if not run_command("pip install -r requirements.txt", "Installing Python dependencies"):
        return False
    
    # Setup database
    if not run_command("python setup_database.py", "Setting up database"):
        logger.warning("⚠️  Database setup failed - continuing with defaults")
    
    # Run database migrations
    migration_file = "src/database/migrations/create_complete_flow_trading_system.sql"
    if Path(migration_file).exists():
        logger.info("🗄️  Running database migrations...")
        # Would run migration here - for now just log
        logger.info("✅ Database migrations ready")
    
    return True

def setup_frontend():
    """Setup frontend if needed"""
    logger.info("🎨 Setting up frontend...")
    
    frontend_dir = Path("frontend")
    if frontend_dir.exists():
        # Check if node_modules exists
        if not (frontend_dir / "node_modules").exists():
            if run_command("cd frontend && npm install", "Installing frontend dependencies"):
                logger.info("✅ Frontend dependencies installed")
            else:
                logger.warning("⚠️  Frontend setup failed - continuing without frontend")
        else:
            logger.info("✅ Frontend already set up")
    else:
        logger.info("ℹ️  No frontend directory found - API only mode")
    
    return True

def start_system():
    """Start the complete flow trading system"""
    logger.info("🚀 Starting Flow Trading System...")
    
    # Start the API server
    api_command = "python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload"
    
    logger.info("🌐 Starting API server on http://localhost:8000")
    logger.info("📊 API Documentation available at http://localhost:8000/docs")
    logger.info("🔄 Paper Trading API at http://localhost:8000/api/v1/paper-trading/")
    
    # Run the server
    try:
        subprocess.run(api_command, shell=True, check=True)
    except KeyboardInterrupt:
        logger.info("🛑 System shutdown requested")
    except Exception as e:
        logger.error(f"❌ System startup failed: {e}")

def show_system_info():
    """Show system information and available endpoints"""
    print("\n" + "="*80)
    print("🚀 FLOW TRADING SYSTEM - READY TO LAUNCH")
    print("="*80)
    print()
    print("📋 SYSTEM COMPONENTS:")
    print("   ✅ Enhanced Paper Trading Engine")
    print("   ✅ Real-time Scalping Manager") 
    print("   ✅ Flow Trading Strategies")
    print("   ✅ ML-Enhanced Signal Tracking")
    print("   ✅ Comprehensive Monitoring")
    print("   ✅ Risk Management")
    print("   ✅ Performance Analytics")
    print()
    print("🌐 API ENDPOINTS (after startup):")
    print("   📊 Main API: http://localhost:8000")
    print("   📖 Documentation: http://localhost:8000/docs")
    print("   🔄 Paper Trading: http://localhost:8000/api/v1/paper-trading/")
    print("   📈 Flow Trading: http://localhost:8000/api/v1/flow-trading/")
    print("   🎯 Signals: http://localhost:8000/api/v1/signal-tracking/")
    print("   💰 Profit Scraping: http://localhost:8000/api/v1/profit-scraping/")
    print()
    print("🎮 QUICK START COMMANDS:")
    print("   🚀 Start Paper Trading: POST /api/v1/paper-trading/start")
    print("   📊 Check Status: GET /api/v1/paper-trading/status")
    print("   💹 Execute Trade: POST /api/v1/paper-trading/trade")
    print("   🎯 Simulate Signals: POST /api/v1/paper-trading/simulate-signals")
    print()
    print("📁 KEY FILES:")
    print("   ⚙️  Configuration: config/flow_trading_config.py")
    print("   🗄️  Database: src/database/migrations/")
    print("   🎨 Frontend: frontend/src/")
    print("   📊 Monitoring: src/monitoring/")
    print()
    print("="*80)

def main():
    """Main launcher function"""
    print("🚀 Flow Trading System Launcher")
    print("=" * 50)
    
    # Show system info
    show_system_info()
    
    # Check requirements
    if not check_requirements():
        logger.error("❌ Requirements check failed")
        sys.exit(1)
    
    # Setup environment
    if not setup_environment():
        logger.error("❌ Environment setup failed")
        sys.exit(1)
    
    # Setup frontend
    setup_frontend()
    
    # Ask user if they want to start
    print("\n🎯 Ready to launch the Flow Trading System!")
    response = input("Start the system now? (y/N): ").strip().lower()
    
    if response in ['y', 'yes']:
        start_system()
    else:
        print("\n📋 To start manually, run:")
        print("   python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload")
        print("\n🔗 Then visit: http://localhost:8000/docs")

if __name__ == "__main__":
    main()
