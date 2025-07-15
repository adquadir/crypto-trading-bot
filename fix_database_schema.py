#!/usr/bin/env python3
"""
Fix Database Schema - Add missing winning_trades column to flow_performance table
"""

import logging
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Get database configuration from environment variables
DB_USER = os.getenv("POSTGRES_USER", "trader")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "current_password")
DB_NAME = os.getenv("POSTGRES_DB", "crypto_trading")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")

# Construct database URL
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def fix_database_schema():
    """Fix the missing winning_trades column in flow_performance table"""
    try:
        # Create engine
        engine = create_engine(DATABASE_URL)
        
        logger.info("🔧 Connecting to database...")
        
        with engine.connect() as conn:
            # Check if flow_performance table exists
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'flow_performance'
                );
            """))
            
            table_exists = result.scalar()
            
            if not table_exists:
                logger.info("📋 Creating flow_performance table...")
                conn.execute(text("""
                    CREATE TABLE flow_performance (
                        id SERIAL PRIMARY KEY,
                        symbol VARCHAR(20) NOT NULL,
                        strategy_type VARCHAR(50) NOT NULL,
                        total_pnl DECIMAL(20, 8) NOT NULL DEFAULT 0,
                        trades_count INTEGER NOT NULL DEFAULT 0,
                        winning_trades INTEGER NOT NULL DEFAULT 0,
                        losing_trades INTEGER NOT NULL DEFAULT 0,
                        win_rate DECIMAL(5, 4) DEFAULT 0,
                        max_drawdown_pct DECIMAL(10, 6) DEFAULT 0,
                        sharpe_ratio DECIMAL(10, 6) DEFAULT 0,
                        profit_factor DECIMAL(10, 6) DEFAULT 0,
                        avg_trade_duration_minutes DECIMAL(10, 2) DEFAULT 0,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """))
                logger.info("✅ Created flow_performance table")
            else:
                logger.info("📋 Checking for missing columns...")
                
                # Check if winning_trades column exists
                result = conn.execute(text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.columns 
                        WHERE table_name = 'flow_performance' 
                        AND column_name = 'winning_trades'
                    );
                """))
                
                column_exists = result.scalar()
                
                if not column_exists:
                    logger.info("🔧 Adding missing winning_trades column...")
                    conn.execute(text("""
                        ALTER TABLE flow_performance 
                        ADD COLUMN winning_trades INTEGER NOT NULL DEFAULT 0;
                    """))
                    logger.info("✅ Added winning_trades column")
                else:
                    logger.info("✅ winning_trades column already exists")
                
                # Check if losing_trades column exists
                result = conn.execute(text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.columns 
                        WHERE table_name = 'flow_performance' 
                        AND column_name = 'losing_trades'
                    );
                """))
                
                column_exists = result.scalar()
                
                if not column_exists:
                    logger.info("🔧 Adding missing losing_trades column...")
                    conn.execute(text("""
                        ALTER TABLE flow_performance 
                        ADD COLUMN losing_trades INTEGER NOT NULL DEFAULT 0;
                    """))
                    logger.info("✅ Added losing_trades column")
                else:
                    logger.info("✅ losing_trades column already exists")
            
            # Commit changes
            conn.commit()
            logger.info("✅ Database schema fixed successfully!")
            
    except Exception as e:
        logger.error(f"❌ Error fixing database schema: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = fix_database_schema()
    if success:
        logger.info("🎉 Database schema fix completed successfully!")
        sys.exit(0)
    else:
        logger.error("❌ Database schema fix failed!")
        sys.exit(1)
