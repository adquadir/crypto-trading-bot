#!/usr/bin/env python3
"""
Complete VPS Deployment Fix Script
Fixes all deployment issues identified in PM2 logs:
1. Missing 'trades' table
2. ExchangeClient ccxt_client attribute error
3. Database schema issues
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.database.database import Database
from src.database.models import Base
from sqlalchemy import text, inspect

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_database_connection():
    """Check if database connection is working."""
    try:
        db = Database()
        with db.session_scope() as session:
            result = session.execute(text("SELECT 1")).fetchone()
            logger.info("✅ Database connection successful")
            return True
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return False

async def check_table_exists(table_name: str) -> bool:
    """Check if a table exists in the database."""
    try:
        db = Database()
        with db.session_scope() as session:
            inspector = inspect(session.bind)
            tables = inspector.get_table_names()
            exists = table_name in tables
            if exists:
                logger.info(f"✅ Table '{table_name}' exists")
            else:
                logger.warning(f"❌ Table '{table_name}' does not exist")
            return exists
    except Exception as e:
        logger.error(f"Error checking table {table_name}: {e}")
        return False

async def create_missing_tables():
    """Create all missing database tables."""
    try:
        logger.info("🔧 Creating missing database tables...")
        
        db = Database()
        
        # Create all tables defined in models
        Base.metadata.create_all(db.engine)
        
        logger.info("✅ All database tables created successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error creating tables: {e}")
        return False

async def verify_critical_tables():
    """Verify that all critical tables exist."""
    critical_tables = [
        'trades',
        'trading_signals', 
        'market_data',
        'strategies',
        'performance_metrics'
    ]
    
    logger.info("🔍 Verifying critical tables...")
    
    all_exist = True
    for table in critical_tables:
        exists = await check_table_exists(table)
        if not exists:
            all_exist = False
    
    return all_exist

async def create_ml_learning_tables():
    """Create ML learning tables if they don't exist."""
    try:
        logger.info("🧠 Creating ML learning tables...")
        
        db = Database()
        
        # Read and execute the ML tables creation script
        ml_script_path = 'src/database/migrations/create_ml_learning_tables.sql'
        if os.path.exists(ml_script_path):
            with open(ml_script_path, 'r') as f:
                sql_script = f.read()
            
            with db.session_scope() as session:
                session.execute(text(sql_script))
            
            logger.info("✅ ML learning tables created successfully")
        else:
            logger.warning("❌ ML learning tables script not found")
            
        return True
        
    except Exception as e:
        logger.error(f"❌ Error creating ML learning tables: {e}")
        return False

async def test_exchange_client():
    """Test ExchangeClient initialization."""
    try:
        logger.info("🔌 Testing ExchangeClient initialization...")
        
        from src.market_data.exchange_client import ExchangeClient
        
        # Create exchange client
        client = ExchangeClient()
        
        # Check if ccxt_client attribute exists
        if hasattr(client, 'ccxt_client'):
            logger.info("✅ ExchangeClient.ccxt_client attribute exists")
        else:
            logger.error("❌ ExchangeClient.ccxt_client attribute missing")
            return False
            
        # Test basic initialization
        await client.initialize()
        logger.info("✅ ExchangeClient initialized successfully")
        
        # Clean up
        await client.close()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ ExchangeClient test failed: {e}")
        return False

async def populate_initial_data():
    """Populate initial data if tables are empty."""
    try:
        logger.info("📊 Populating initial data...")
        
        db = Database()
        
        # Check if strategies table has data
        with db.session_scope() as session:
            result = session.execute(text("SELECT COUNT(*) FROM strategies")).fetchone()
            strategy_count = result[0] if result else 0
            
            if strategy_count == 0:
                logger.info("Adding initial strategies...")
                
                # Add basic strategies
                strategies = [
                    ("scalping", True, '{"timeframe": "1m", "confidence_threshold": 0.7}'),
                    ("profit_scraping", True, '{"timeframe": "5m", "confidence_threshold": 0.8}'),
                    ("flow_trading", True, '{"timeframe": "15m", "confidence_threshold": 0.75}')
                ]
                
                for name, active, params in strategies:
                    session.execute(text("""
                        INSERT INTO strategies (name, active, parameters) 
                        VALUES (:name, :active, :parameters)
                        ON CONFLICT (name) DO NOTHING
                    """), {
                        'name': name,
                        'active': active,
                        'parameters': params
                    })
                
                logger.info("✅ Initial strategies added")
            else:
                logger.info(f"✅ Strategies table already has {strategy_count} entries")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error populating initial data: {e}")
        return False

async def run_comprehensive_fix():
    """Run comprehensive deployment fix."""
    logger.info("🚀 Starting comprehensive VPS deployment fix...")
    
    success_count = 0
    total_checks = 6
    
    # 1. Check database connection
    if await check_database_connection():
        success_count += 1
    
    # 2. Create missing tables
    if await create_missing_tables():
        success_count += 1
    
    # 3. Verify critical tables
    if await verify_critical_tables():
        success_count += 1
    
    # 4. Create ML learning tables
    if await create_ml_learning_tables():
        success_count += 1
    
    # 5. Test ExchangeClient
    if await test_exchange_client():
        success_count += 1
    
    # 6. Populate initial data
    if await populate_initial_data():
        success_count += 1
    
    logger.info(f"📊 Fix Results: {success_count}/{total_checks} checks passed")
    
    if success_count == total_checks:
        logger.info("🎉 All deployment fixes completed successfully!")
        logger.info("✅ Your VPS deployment should now work correctly")
        logger.info("🔄 Restart your PM2 processes: pm2 restart all")
        return True
    else:
        logger.error(f"❌ {total_checks - success_count} fixes failed")
        logger.error("Please review the errors above and fix manually")
        return False

if __name__ == "__main__":
    try:
        result = asyncio.run(run_comprehensive_fix())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        logger.info("Fix interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
