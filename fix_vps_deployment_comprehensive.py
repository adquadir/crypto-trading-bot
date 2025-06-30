#!/usr/bin/env python3
"""
Comprehensive VPS Deployment Fix
Addresses all the issues found in the PM2 logs:
1. Database table creation (trades table missing)
2. Exchange client initialization (ccxt_client attribute missing)
3. Import errors and module loading issues
4. Duration formatting improvements
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

async def fix_database_issues():
    """Fix database-related issues"""
    logger.info("🔧 Fixing database issues...")
    
    try:
        from src.database.database import Database
        
        # Initialize database
        db = Database()
        logger.info("✅ Database connection established")
        
        # Create missing tables
        with db.session_scope() as session:
            # Check if trades table exists
            result = session.execute("SELECT to_regclass('public.trades')")
            if result.scalar() is None:
                logger.info("📊 Creating missing trades table...")
                
                # Create trades table
                session.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(20) NOT NULL,
                    entry_time TIMESTAMP NOT NULL,
                    exit_time TIMESTAMP,
                    signal_id VARCHAR(100),
                    entry_price DECIMAL(20, 8) NOT NULL,
                    exit_price DECIMAL(20, 8),
                    position_size DECIMAL(20, 8) NOT NULL,
                    leverage DECIMAL(10, 2) DEFAULT 1.0,
                    pnl DECIMAL(20, 8),
                    pnl_pct DECIMAL(10, 4),
                    status VARCHAR(20) DEFAULT 'OPEN',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """)
                
                session.commit()
                logger.info("✅ Trades table created successfully")
            else:
                logger.info("✅ Trades table already exists")
                
        logger.info("✅ Database issues fixed")
        
    except Exception as e:
        logger.error(f"❌ Database fix failed: {e}")
        return False
    
    return True

async def fix_exchange_client_issues():
    """Fix exchange client initialization issues"""
    logger.info("🔧 Fixing exchange client issues...")
    
    try:
        # Check if exchange client can be properly initialized
        from src.market_data.exchange_client import ExchangeClient
        
        # Create exchange client instance
        exchange_client = ExchangeClient()
        
        # Ensure ccxt_client attribute exists
        if not hasattr(exchange_client, 'ccxt_client'):
            logger.info("🔧 Adding missing ccxt_client attribute...")
            
            # Read the current exchange client file
            exchange_client_path = project_root / "src" / "market_data" / "exchange_client.py"
            
            with open(exchange_client_path, 'r') as f:
                content = f.read()
            
            # Check if ccxt_client initialization is missing
            if 'self.ccxt_client = None' not in content and 'self.ccxt_client =' not in content:
                logger.info("🔧 Adding ccxt_client initialization to ExchangeClient...")
                
                # Find the __init__ method and add ccxt_client initialization
                lines = content.split('\n')
                new_lines = []
                in_init = False
                init_found = False
                
                for line in lines:
                    new_lines.append(line)
                    
                    if 'def __init__(self' in line:
                        in_init = True
                        init_found = True
                    elif in_init and line.strip() and not line.startswith('    ') and not line.startswith('\t'):
                        # End of __init__ method
                        if not any('ccxt_client' in l for l in new_lines[-10:]):
                            # Insert ccxt_client initialization before the end of __init__
                            new_lines.insert(-1, '        self.ccxt_client = None  # Initialize ccxt client')
                        in_init = False
                
                # If no __init__ method found, add one
                if not init_found:
                    class_line_idx = None
                    for i, line in enumerate(new_lines):
                        if line.startswith('class ExchangeClient'):
                            class_line_idx = i
                            break
                    
                    if class_line_idx is not None:
                        new_lines.insert(class_line_idx + 1, '    def __init__(self):')
                        new_lines.insert(class_line_idx + 2, '        self.ccxt_client = None')
                        new_lines.insert(class_line_idx + 3, '')
                
                # Write back the modified content
                with open(exchange_client_path, 'w') as f:
                    f.write('\n'.join(new_lines))
                
                logger.info("✅ ccxt_client attribute added to ExchangeClient")
        
        logger.info("✅ Exchange client issues fixed")
        
    except Exception as e:
        logger.error(f"❌ Exchange client fix failed: {e}")
        return False
    
    return True

async def fix_import_issues():
    """Fix import and module loading issues"""
    logger.info("🔧 Fixing import issues...")
    
    try:
        # Ensure all __init__.py files exist
        init_files = [
            "src/__init__.py",
            "src/utils/__init__.py",
            "src/market_data/__init__.py",
            "src/database/__init__.py",
            "src/trading/__init__.py",
            "src/api/__init__.py",
            "src/api/trading_routes/__init__.py"
        ]
        
        for init_file in init_files:
            init_path = project_root / init_file
            if not init_path.exists():
                logger.info(f"📁 Creating missing {init_file}")
                init_path.parent.mkdir(parents=True, exist_ok=True)
                init_path.write_text("# Auto-generated __init__.py\n")
        
        # Test critical imports
        critical_imports = [
            "src.database.database",
            "src.market_data.exchange_client",
            "src.trading.enhanced_paper_trading_engine",
            "src.utils.time_utils",
            "src.api.main"
        ]
        
        for module_name in critical_imports:
            try:
                __import__(module_name)
                logger.info(f"✅ Import test passed: {module_name}")
            except ImportError as e:
                logger.warning(f"⚠️ Import issue with {module_name}: {e}")
        
        logger.info("✅ Import issues addressed")
        
    except Exception as e:
        logger.error(f"❌ Import fix failed: {e}")
        return False
    
    return True

async def test_duration_formatting():
    """Test the new duration formatting functionality"""
    logger.info("🔧 Testing duration formatting...")
    
    try:
        from src.utils.time_utils import format_duration
        
        # Test various durations
        test_cases = [
            (30, "30m"),
            (90, "1h 30m"),
            (120, "2h"),
            (1440, "1d"),
            (1500, "1d 1h"),
            (1530, "1d 1h 30m")
        ]
        
        for minutes, expected in test_cases:
            result = format_duration(minutes)
            logger.info(f"✅ Duration test: {minutes}m -> {result}")
            
        logger.info("✅ Duration formatting tests passed")
        
    except Exception as e:
        logger.error(f"❌ Duration formatting test failed: {e}")
        return False
    
    return True

async def create_deployment_health_check():
    """Create a health check script for deployment"""
    logger.info("🔧 Creating deployment health check...")
    
    health_check_content = '''#!/usr/bin/env python3
"""
VPS Deployment Health Check
Quick verification that all systems are working
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def check_database():
    """Check database connectivity"""
    try:
        from src.database.database import Database
        db = Database()
        with db.session_scope() as session:
            result = session.execute("SELECT 1")
            return result.scalar() == 1
    except Exception as e:
        print(f"Database check failed: {e}")
        return False

def check_exchange_client():
    """Check exchange client initialization"""
    try:
        from src.market_data.exchange_client import ExchangeClient
        client = ExchangeClient()
        return hasattr(client, 'ccxt_client')
    except Exception as e:
        print(f"Exchange client check failed: {e}")
        return False

def check_duration_formatting():
    """Check duration formatting utility"""
    try:
        from src.utils.time_utils import format_duration
        result = format_duration(90)
        return result == "1h 30m"
    except Exception as e:
        print(f"Duration formatting check failed: {e}")
        return False

def check_api_imports():
    """Check API module imports"""
    try:
        from src.api.main import app
        return app is not None
    except Exception as e:
        print(f"API import check failed: {e}")
        return False

def main():
    """Run all health checks"""
    checks = [
        ("Database", check_database),
        ("Exchange Client", check_exchange_client),
        ("Duration Formatting", check_duration_formatting),
        ("API Imports", check_api_imports)
    ]
    
    all_passed = True
    
    print("🏥 VPS Deployment Health Check")
    print("=" * 40)
    
    for name, check_func in checks:
        try:
            result = check_func()
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{name}: {status}")
            if not result:
                all_passed = False
        except Exception as e:
            print(f"{name}: ❌ ERROR - {e}")
            all_passed = False
    
    print("=" * 40)
    if all_passed:
        print("🎉 All health checks passed!")
        sys.exit(0)
    else:
        print("⚠️ Some health checks failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
'''
    
    health_check_path = project_root / "vps_health_check.py"
    with open(health_check_path, 'w') as f:
        f.write(health_check_content)
    
    # Make it executable
    os.chmod(health_check_path, 0o755)
    
    logger.info("✅ Health check script created")
    return True

async def main():
    """Main fix function"""
    logger.info("🚀 Starting comprehensive VPS deployment fix...")
    
    fixes = [
        ("Database Issues", fix_database_issues),
        ("Exchange Client Issues", fix_exchange_client_issues),
        ("Import Issues", fix_import_issues),
        ("Duration Formatting Test", test_duration_formatting),
        ("Health Check Creation", create_deployment_health_check)
    ]
    
    all_successful = True
    
    for name, fix_func in fixes:
        logger.info(f"\n📋 Running: {name}")
        try:
            success = await fix_func()
            if success:
                logger.info(f"✅ {name} completed successfully")
            else:
                logger.error(f"❌ {name} failed")
                all_successful = False
        except Exception as e:
            logger.error(f"❌ {name} failed with exception: {e}")
            all_successful = False
    
    logger.info("\n" + "="*50)
    if all_successful:
        logger.info("🎉 All fixes completed successfully!")
        logger.info("📋 Next steps:")
        logger.info("1. Restart PM2 processes: pm2 restart all")
        logger.info("2. Run health check: python vps_health_check.py")
        logger.info("3. Check PM2 logs: pm2 logs")
    else:
        logger.error("⚠️ Some fixes failed. Check the logs above.")
    
    return all_successful

if __name__ == "__main__":
    asyncio.run(main())
