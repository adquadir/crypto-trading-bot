#!/usr/bin/env python3
"""
Test script to verify the import fix for DatabaseManager
"""

import sys
import traceback

def test_imports():
    """Test all the problematic imports"""
    print("🔧 Testing import fixes...")
    
    try:
        print("1. Testing database import...")
        from src.database.database import Database
        print("✅ Database import successful")
        
        print("2. Testing real trading engine import...")
        from src.trading.real_trading_engine import RealTradingEngine
        print("✅ RealTradingEngine import successful")
        
        print("3. Testing profit scraping routes import...")
        from src.api.trading_routes.profit_scraping_routes import router
        print("✅ Profit scraping routes import successful")
        
        print("4. Testing main API import...")
        from src.api.main import app
        print("✅ Main API import successful")
        
        print("\n🎉 ALL IMPORTS SUCCESSFUL!")
        print("✅ The DatabaseManager import error has been fixed")
        return True
        
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_imports()
    if success:
        print("\n🚀 Your VPS API should now start successfully!")
        print("💡 Try restarting PM2: pm2 restart crypto-trading-api")
    else:
        print("\n❌ There are still import issues to fix")
    
    sys.exit(0 if success else 1)
