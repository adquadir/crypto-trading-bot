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
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

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
        'user': os.getenv('DB_USER', 'trader'),
        'password': os.getenv('DB_PASSWORD', 'current_password')
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
        
        # Step 2: Create database and all required tables
        print(f"\n2️⃣ Creating database '{db_config['database']}' and all tables...")
        try:
            # Connect to the trading database directly
            db_url = f"postgresql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}"
            
            # Use SQLAlchemy to create all tables from models
            engine = create_engine(db_url)
            
            # Import all models to ensure they're registered
            sys.path.append('src')
            from src.database.models import Base, MarketData, OrderBook, TradingSignal, Trade, PerformanceMetrics, Strategy
            
            # Create all tables
            Base.metadata.create_all(engine)
            print("   ✅ Created all tables from SQLAlchemy models")
            
            # Create additional tables for enhanced functionality
            with engine.connect() as conn:
                # Create enhanced_signals table for signal tracking
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS enhanced_signals (
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
                        
                        -- Enhanced Learning Fields
                        fakeout_detected BOOLEAN DEFAULT FALSE,
                        post_sl_peak_pct DECIMAL(10,6),
                        virtual_tp_hit BOOLEAN DEFAULT FALSE,
                        is_virtual_golden BOOLEAN DEFAULT FALSE,
                        max_profit_pct DECIMAL(10,6),
                        stop_loss_hit BOOLEAN DEFAULT FALSE,
                        learning_outcome VARCHAR(50),
                        
                        -- Metadata
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """))
                
                # Create historical_signals table (legacy compatibility)
                conn.execute(text("""
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
                """))
                
                # Create indexes for performance
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_trades_entry_time ON trades(entry_time);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_trading_signals_symbol ON trading_signals(symbol);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_trading_signals_timestamp ON trading_signals(timestamp);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_enhanced_signals_symbol ON enhanced_signals(symbol);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_enhanced_signals_strategy ON enhanced_signals(strategy);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_enhanced_signals_timestamp ON enhanced_signals(timestamp);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_enhanced_signals_status ON enhanced_signals(status);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_historical_signals_symbol ON historical_signals(symbol);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_historical_signals_strategy ON historical_signals(strategy);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_historical_signals_timestamp ON historical_signals(timestamp);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_historical_signals_status ON historical_signals(status);"))
                
                conn.commit()
                print("   ✅ Created enhanced signal tracking tables and indexes")
            
            engine.dispose()
            
        except Exception as e:
            print(f"   ❌ Database connection failed: {e}")
            print("   💡 Make sure PostgreSQL is running and credentials are correct")
            print("   💡 You may need to create the database manually:")
            print(f"      sudo -u postgres createdb {db_config['database']}")
            print(f"      sudo -u postgres createuser {db_config['user']}")
            print(f"      sudo -u postgres psql -c \"ALTER USER {db_config['user']} WITH PASSWORD '{db_config['password']}'\"")
            return False
        
        # Step 3: Test database connectivity
        print(f"\n3️⃣ Testing database connectivity...")
        try:
            # Test with asyncpg
            conn = await asyncpg.connect(
                host=db_config['host'],
                port=db_config['port'],
                database=db_config['database'],
                user=db_config['user'],
                password=db_config['password']
            )
            
            # Test basic queries
            result = await conn.fetchval("SELECT COUNT(*) FROM trades")
            print(f"   ✅ Trades table accessible (count: {result})")
            
            result = await conn.fetchval("SELECT COUNT(*) FROM trading_signals")
            print(f"   ✅ Trading signals table accessible (count: {result})")
            
            result = await conn.fetchval("SELECT COUNT(*) FROM enhanced_signals")
            print(f"   ✅ Enhanced signals table accessible (count: {result})")
            
            await conn.close()
            
        except Exception as e:
            print(f"   ❌ Database connectivity test failed: {e}")
            return False
        
        # Step 4: Test signal tracking (if available)
        print(f"\n4️⃣ Testing signal tracking functionality...")
        try:
            # Import and test signal tracker
            from src.signals.signal_tracker import real_signal_tracker
            
            # Initialize tracker
            await real_signal_tracker.initialize()
            
            if real_signal_tracker.enabled and real_signal_tracker.connection_pool:
                print("   ✅ Signal tracker initialized successfully")
                await real_signal_tracker.close()
            else:
                print("   ⚠️ Signal tracker not fully initialized (this is OK)")
            
        except Exception as e:
            print(f"   ⚠️ Signal tracking test failed: {e} (this is OK for basic functionality)")
        
        # Success!
        print("\n" + "=" * 60)
        print("🎉 DATABASE SETUP COMPLETE!")
        print("=" * 60)
        print("✅ Database connection successful")
        print("✅ All required tables created")
        print("✅ Signal tracking tables created")
        print("✅ Database indexes created for performance")
        print("✅ Database connectivity tested")
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
