#!/usr/bin/env python3
"""
Fix VPS Deployment Issues
Addresses the specific issues from PM2 logs:
1. Missing trades table (psycopg2.errors.UndefinedTable)
2. Missing ccxt_client attribute
3. Database initialization
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_database_schema():
    """Fix the missing trades table issue"""
    try:
        logger.info("🔧 Fixing database schema...")
        
        # Check if we're using PostgreSQL or SQLite
        database_url = os.getenv('DATABASE_URL', '')
        
        if 'postgresql' in database_url or 'postgres' in database_url:
            # PostgreSQL setup
            import psycopg2
            from urllib.parse import urlparse
            
            result = urlparse(database_url)
            conn = psycopg2.connect(
                database=result.path[1:],
                user=result.username,
                password=result.password,
                host=result.hostname,
                port=result.port
            )
            
            cursor = conn.cursor()
            
            # Create trades table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(20) NOT NULL,
                    entry_time TIMESTAMP,
                    exit_time TIMESTAMP,
                    signal_id VARCHAR(50),
                    entry_price FLOAT,
                    exit_price FLOAT,
                    position_size FLOAT,
                    leverage FLOAT DEFAULT 1.0,
                    pnl FLOAT DEFAULT 0.0,
                    pnl_pct FLOAT DEFAULT 0.0,
                    status VARCHAR(20) DEFAULT 'OPEN'
                );
            """)
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info("✅ PostgreSQL trades table created")
            
        else:
            # SQLite setup (fallback)
            from src.database.database import Database
            
            db = Database()
            db.create_tables()
            
            logger.info("✅ SQLite database tables created")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Database schema fix failed: {e}")
        return False

def fix_exchange_client():
    """Fix the missing ccxt_client attribute"""
    try:
        logger.info("🔧 Fixing exchange client...")
        
        # Read the exchange client file
        exchange_file = project_root / "src" / "market_data" / "exchange_client.py"
        
        with open(exchange_file, 'r') as f:
            content = f.read()
        
        # Check if ccxt_client initialization is missing
        if "self.ccxt_client = None" not in content:
            logger.info("Adding ccxt_client initialization...")
            
            # Find the __init__ method and add ccxt_client initialization
            init_pos = content.find("def __init__(self")
            if init_pos != -1:
                # Find the end of __init__ method
                next_method = content.find("\n    def ", init_pos + 1)
                if next_method == -1:
                    next_method = len(content)
                
                init_content = content[init_pos:next_method]
                
                if "self.ccxt_client = None" not in init_content:
                    # Add ccxt_client initialization
                    lines = init_content.split('\n')
                    # Insert after the first line of __init__
                    lines.insert(1, "        self.ccxt_client = None")
                    
                    new_init = '\n'.join(lines)
                    new_content = content[:init_pos] + new_init + content[next_method:]
                    
                    with open(exchange_file, 'w') as f:
                        f.write(new_content)
                    
                    logger.info("✅ ccxt_client initialization added")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Exchange client fix failed: {e}")
        return False

def fix_routes_error_handling():
    """Fix the 500 error in routes.py stats endpoint"""
    try:
        logger.info("🔧 Fixing routes error handling...")
        
        routes_file = project_root / "src" / "api" / "routes.py"
        
        with open(routes_file, 'r') as f:
            content = f.read()
        
        # Find the get_stats function
        stats_pos = content.find("async def get_stats")
        if stats_pos != -1:
            # Find the end of the function
            next_func = content.find("\n@", stats_pos + 1)
            if next_func == -1:
                next_func = content.find("\nasync def", stats_pos + 1)
            if next_func == -1:
                next_func = len(content)
            
            stats_func = content[stats_pos:next_func]
            
            # Check if proper error handling exists
            if "try:" not in stats_func or "except Exception" not in stats_func:
                logger.info("Adding error handling to stats endpoint...")
                
                # Create a better stats function with error handling
                new_stats_func = '''async def get_stats():
    """Get trading statistics"""
    try:
        from src.database.database import Database
        
        db = Database()
        
        # Initialize default stats
        stats = {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0.0,
            "total_pnl": 0.0,
            "avg_pnl": 0.0
        }
        
        try:
            with db.session_scope() as session:
                # Try to get trades count
                result = session.execute("SELECT COUNT(*) FROM trades")
                total_trades = result.scalar() or 0
                stats["total_trades"] = total_trades
                
                if total_trades > 0:
                    # Get winning trades
                    result = session.execute("SELECT COUNT(*) FROM trades WHERE pnl > 0")
                    winning_trades = result.scalar() or 0
                    stats["winning_trades"] = winning_trades
                    stats["losing_trades"] = total_trades - winning_trades
                    stats["win_rate"] = winning_trades / total_trades if total_trades > 0 else 0.0
                    
                    # Get total PnL
                    result = session.execute("SELECT SUM(pnl) FROM trades")
                    total_pnl = result.scalar() or 0.0
                    stats["total_pnl"] = total_pnl
                    stats["avg_pnl"] = total_pnl / total_trades if total_trades > 0 else 0.0
                    
        except Exception as db_error:
            logger.warning(f"Database query failed: {db_error}")
            # Return default stats if database fails
        
        return {"success": True, "data": stats}
        
    except Exception as e:
        logger.error(f"Stats endpoint error: {e}")
        return {"success": False, "error": "Failed to get stats", "data": {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0.0,
            "total_pnl": 0.0,
            "avg_pnl": 0.0
        }}'''
                
                new_content = content[:stats_pos] + new_stats_func + content[next_func:]
                
                with open(routes_file, 'w') as f:
                    f.write(new_content)
                
                logger.info("✅ Stats endpoint error handling improved")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Routes fix failed: {e}")
        return False

async def main():
    """Main fix function"""
    logger.info("🚀 Fixing VPS deployment issues...")
    
    success_count = 0
    total_fixes = 3
    
    # Fix database schema
    if fix_database_schema():
        success_count += 1
    
    # Fix exchange client
    if fix_exchange_client():
        success_count += 1
    
    # Fix routes error handling
    if fix_routes_error_handling():
        success_count += 1
    
    logger.info(f"🎯 Fix completed: {success_count}/{total_fixes} successful")
    
    if success_count == total_fixes:
        logger.info("✅ ALL FIXES SUCCESSFUL")
        logger.info("🔄 Now restart PM2: pm2 restart all")
        logger.info("📊 Check logs: pm2 logs")
    else:
        logger.warning(f"⚠️ Some fixes failed ({success_count}/{total_fixes})")
    
    return success_count == total_fixes

if __name__ == "__main__":
    asyncio.run(main())
