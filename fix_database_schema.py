#!/usr/bin/env python3
"""
Fix Database Schema Issues
Adds missing columns to flow_performance table
"""

import asyncio
import logging
from src.database.database import DatabaseManager
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

async def fix_database_schema():
    """Fix database schema issues"""
    try:
        logger.info("🔧 Fixing database schema issues...")
        
        db_manager = DatabaseManager()
        
        # Add missing columns to flow_performance table
        alter_queries = [
            """
            ALTER TABLE flow_performance 
            ADD COLUMN IF NOT EXISTS winning_trades INTEGER DEFAULT 0
            """,
            """
            ALTER TABLE flow_performance 
            ADD COLUMN IF NOT EXISTS losing_trades INTEGER DEFAULT 0
            """
        ]
        
        for query in alter_queries:
            try:
                await db_manager.execute_query(query)
                logger.info(f"✅ Executed: {query.strip()}")
            except Exception as e:
                if "already exists" in str(e).lower():
                    logger.info(f"✅ Column already exists, skipping")
                else:
                    logger.error(f"❌ Error executing query: {e}")
        
        # Test the table structure
        test_query = """
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'flow_performance'
        ORDER BY ordinal_position
        """
        
        result = await db_manager.fetch_all(test_query)
        
        logger.info("📊 Current flow_performance table structure:")
        for row in result:
            logger.info(f"   {row['column_name']}: {row['data_type']}")
        
        # Test inserting a record
        test_insert = """
        INSERT INTO flow_performance 
        (symbol, strategy_type, total_pnl, trades_count, winning_trades, losing_trades, win_rate, max_drawdown_pct, sharpe_ratio)
        VALUES ('TEST', 'test', 0.0, 0, 0, 0, 0.0, 0.0, 0.0)
        ON CONFLICT DO NOTHING
        """
        
        await db_manager.execute_query(test_insert)
        logger.info("✅ Test insert successful")
        
        # Clean up test record
        await db_manager.execute_query("DELETE FROM flow_performance WHERE symbol = 'TEST'")
        
        logger.info("🎉 Database schema fixed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Error fixing database schema: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(fix_database_schema())
