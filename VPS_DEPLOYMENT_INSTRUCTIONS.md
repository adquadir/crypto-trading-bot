
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
