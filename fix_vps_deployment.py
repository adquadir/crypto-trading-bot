#!/usr/bin/env python3
"""
VPS Deployment Fix Script
Fixes the DatabaseManager import error and provides deployment instructions
"""

import os
import sys

def create_deployment_instructions():
    """Create deployment instructions for VPS"""
    
    instructions = """
# 🚀 VPS Deployment Fix Instructions

## ✅ Import Error Fixed
The `DatabaseManager` import error has been fixed:
- Changed `from ..database.database import DatabaseManager` to `from ..database.database import Database`
- Updated `self.db_manager = DatabaseManager()` to `self.db_manager = Database()`
- Removed unused pandas import from database.py

## 🔧 VPS Setup Commands

Run these commands on your VPS to ensure proper deployment:

### 1. Activate Virtual Environment
```bash
cd /root/crypto-trading-bot
source venv/bin/activate  # or wherever your venv is
```

### 2. Install/Update Dependencies
```bash
pip install -r requirements.txt
```

### 3. Restart PM2 Services
```bash
pm2 restart crypto-trading-api
pm2 restart crypto-trading-frontend
```

### 4. Check Logs
```bash
pm2 logs crypto-trading-api --lines 20
```

## 🎯 Root Cause Analysis

The error was:
```
ImportError: cannot import name 'DatabaseManager' from 'src.database.database'
```

**What happened:**
- The `real_trading_engine.py` was trying to import `DatabaseManager`
- But the database module only exports `Database` class
- This caused the entire API to crash on startup

**What was fixed:**
- Updated import statement to use correct class name
- Updated instantiation to use correct class
- Removed unused dependencies

## 🚨 If Still Having Issues

If you're still getting import errors on VPS, check:

1. **Virtual Environment**: Make sure you're in the correct venv
2. **Python Path**: Ensure the project directory is in Python path
3. **Dependencies**: Run `pip list` to verify all packages are installed
4. **Permissions**: Check file permissions on the project directory

## 🔍 Quick Test

Run this on your VPS to test the fix:
```bash
cd /root/crypto-trading-bot
python3 -c "from src.api.main import app; print('✅ Import successful!')"
```

If this works, your API should start successfully with PM2.
"""
    
    with open('VPS_DEPLOYMENT_INSTRUCTIONS.md', 'w') as f:
        f.write(instructions)
    
    print("📝 Created VPS_DEPLOYMENT_INSTRUCTIONS.md")

def main():
    print("🔧 VPS Deployment Fix")
    print("=" * 50)
    
    print("✅ Import fixes applied:")
    print("   - Fixed DatabaseManager -> Database import")
    print("   - Updated class instantiation")
    print("   - Removed unused pandas import")
    
    create_deployment_instructions()
    
    print("\n🎯 Next Steps for VPS:")
    print("1. Activate your virtual environment")
    print("2. Run: pip install -r requirements.txt")
    print("3. Run: pm2 restart crypto-trading-api")
    print("4. Check: pm2 logs crypto-trading-api")
    
    print("\n📋 See VPS_DEPLOYMENT_INSTRUCTIONS.md for detailed steps")

if __name__ == "__main__":
    main()
