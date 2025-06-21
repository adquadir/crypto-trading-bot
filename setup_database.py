#!/usr/bin/env python3
"""
🎯 Database Setup Script for Crypto Trading Bot

Sets up PostgreSQL database with all required tables for real money trading.
"""

import asyncio
import asyncpg
import os
import sys
import subprocess
from dotenv import load_dotenv

# Load environment
load_dotenv()

async def setup_database():
    """Complete database setup for production use"""
    print("🚀 CRYPTO TRADING BOT - DATABASE SETUP")
    print("=" * 60)
    print("Setting up PostgreSQL database for REAL MONEY TRADING")
    print("=" * 60)
    
    # Database configuration
    db_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('DB_PORT', 5432)),
        'database': os.getenv('DB_NAME', 'crypto_trading'),
        'user': os.getenv('DB_USER', 'crypto_user'),
        'password': os.getenv('DB_PASSWORD', 'crypto_password')
    }
    
    print(f"📊 Database Configuration:")
    print(f"   Host: {db_config['host']}")
    print(f"   Port: {db_config['port']}")
    print(f"   Database: {db_config['database']}")
    print(f"   User: {db_config['user']}")
    print()
    
    try:
        # Step 1: Check if PostgreSQL is installed
        print("1️⃣ Checking PostgreSQL installation...")
        try:
            result = subprocess.run(['psql', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"   ✅ PostgreSQL found: {result.stdout.strip()}")
            else:
                raise FileNotFoundError
        except FileNotFoundError:
            print("   ❌ PostgreSQL not found!")
            print("   💡 Install PostgreSQL:")
            print("      Ubuntu/Debian: sudo apt install postgresql postgresql-contrib")
            print("      macOS: brew install postgresql")
            print("      Windows: Download from https://www.postgresql.org/download/")
            return False
        
        # Step 2: Create database and user
        print(f"\n2️⃣ Creating database '{db_config['database']}'...")
        try:
            # Connect to the trading database directly
            db_url = f"postgresql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}"
            conn = await asyncpg.connect(db_url)
            
            # Create signal tracking tables
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS historical_signals (
                    id SERIAL PRIMARY KEY,
                    signal_id VARCHAR(100) UNIQUE NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    -- Signal Details
                    symbol VARCHAR(20) NOT NULL,
                    strategy VARCHAR(50) NOT NULL,
                    direction VARCHAR(10) NOT NULL,
                    signal_type VARCHAR(50),
                    
                    -- Price Levels
                    entry_price DECIMAL(20,8) NOT NULL,
                    stop_loss DECIMAL(20,8) NOT NULL,
                    take_profit DECIMAL(20,8) NOT NULL,
                    
                    -- Signal Quality
                    confidence DECIMAL(5,4) NOT NULL,
                    risk_reward_ratio DECIMAL(10,4),
                    
                    -- Market Context
                    market_regime VARCHAR(20),
                    funding_rate DECIMAL(10,8),
                    open_interest BIGINT,
                    volume_24h DECIMAL(20,8),
                    
                    -- Signal Source
                    trading_mode VARCHAR(20),
                    source_system VARCHAR(50) DEFAULT 'opportunity_manager',
                    
                    -- Outcome Tracking
                    status VARCHAR(20) DEFAULT 'active',
                    actual_exit_price DECIMAL(20,8),
                    actual_exit_time TIMESTAMP,
                    actual_pnl DECIMAL(20,8),
                    actual_return_pct DECIMAL(10,6),
                    trade_duration_minutes INTEGER,
                    
                    -- Metadata
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                -- Indexes for performance
                CREATE INDEX IF NOT EXISTS idx_historical_signals_symbol ON historical_signals(symbol);
                CREATE INDEX IF NOT EXISTS idx_historical_signals_strategy ON historical_signals(strategy);
                CREATE INDEX IF NOT EXISTS idx_historical_signals_timestamp ON historical_signals(timestamp);
                CREATE INDEX IF NOT EXISTS idx_historical_signals_status ON historical_signals(status);
                CREATE INDEX IF NOT EXISTS idx_historical_signals_trading_mode ON historical_signals(trading_mode);
            """)
            
            print("   ✅ Created historical_signals table")
            await conn.close()
            
        except Exception as e:
            print(f"   ❌ Database connection failed: {e}")
            print("   💡 Make sure PostgreSQL is running and credentials are correct")
            print("   💡 You may need to create the database manually:")
            print(f"      sudo -u postgres createdb {db_config['database']}")
            return False
        
        # Step 3: Test signal tracking
        print(f"\n3️⃣ Testing signal tracking functionality...")
        try:
            # Import and test signal tracker
            sys.path.append('src')
            from src.signals.signal_tracker import real_signal_tracker
            
            # Initialize tracker
            await real_signal_tracker.initialize()
            
            if real_signal_tracker.enabled and real_signal_tracker.connection_pool:
                print("   ✅ Signal tracker initialized successfully")
                await real_signal_tracker.close()
            else:
                print("   ❌ Signal tracker failed to initialize")
                return False
            
        except Exception as e:
            print(f"   ❌ Signal tracking test failed: {e}")
            return False
        
        # Success!
        print("\n" + "=" * 60)
        print("🎉 DATABASE SETUP COMPLETE!")
        print("=" * 60)
        print("✅ Database connection successful")
        print("✅ Signal tracking tables created")
        print("✅ Signal tracking functionality tested")
        print()
        print("🚀 Your system is ready for REAL MONEY TRADING!")
        print()
        print("📋 Next Steps:")
        print("   1. Configure your Binance API keys in .env")
        print("   2. Start the API: python simple_api.py")
        print("   3. Start the frontend: cd frontend && npm start")
        print("   4. Watch real signals get logged to the database!")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Database setup failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(setup_database())
    sys.exit(0 if success else 1)
