import os
from typing import Dict, Any
from dotenv import load_dotenv
import logging
from pathlib import Path

# Load environment variables
load_dotenv()

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Logging configuration
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
            'formatter': 'standard',
            'stream': 'ext://sys.stdout',
        },
        'file': {
            'class': 'logging.FileHandler',
            'level': 'INFO',
            'formatter': 'standard',
            'filename': BASE_DIR / 'trading_bot.log',
        },
    },
    'loggers': {
        '': {  # root logger
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True
        }
    }
}

# Database configuration
DATABASE_CONFIG = {
    'url': os.getenv('DATABASE_URL', 'sqlite:///trading_bot.db'),
    'pool_size': int(os.getenv('DB_POOL_SIZE', '5')),
    'max_overflow': int(os.getenv('DB_MAX_OVERFLOW', '10')),
    'echo': os.getenv('DB_ECHO', 'False').lower() == 'true'
}

# Exchange configuration
EXCHANGE_CONFIG = {
    'api_key': os.getenv('BINANCE_API_KEY'),
    'api_secret': os.getenv('BINANCE_API_SECRET'),
    'testnet': os.getenv('USE_TESTNET', 'False').lower() == 'true',
    'symbols': os.getenv('TRADING_SYMBOLS', 'BTCUSDT').split(','),
    'timeframe': os.getenv('TIMEFRAME', '1m')
}

# Risk management configuration
RISK_CONFIG = {
    'max_position_size': float(os.getenv('MAX_POSITION_SIZE', '0.1')),
    'max_leverage': float(os.getenv('MAX_LEVERAGE', '3.0')),
    'risk_per_trade': float(os.getenv('RISK_PER_TRADE', '0.02')),
    'max_open_trades': int(os.getenv('MAX_OPEN_TRADES', '5')),
    'max_correlation': float(os.getenv('MAX_CORRELATION', '0.7')),
    'min_risk_reward': float(os.getenv('MIN_RISK_REWARD', '2.0')),
    'max_daily_loss': float(os.getenv('MAX_DAILY_LOSS', '0.05')),
    'max_drawdown': float(os.getenv('MAX_DRAWDOWN', '0.15'))
}

# Trading strategy configuration
STRATEGY_CONFIG = {
    'macd': {
        'fast_period': int(os.getenv('MACD_FAST_PERIOD', '12')),
        'slow_period': int(os.getenv('MACD_SLOW_PERIOD', '26')),
        'signal_period': int(os.getenv('MACD_SIGNAL_PERIOD', '9'))
    },
    'rsi': {
        'overbought': float(os.getenv('RSI_OVERBOUGHT', '70')),
        'oversold': float(os.getenv('RSI_OVERSOLD', '30'))
    },
    'bollinger_bands': {
        'std_dev': float(os.getenv('BB_STD_DEV', '2.0'))
    }
}

# Market data configuration
MARKET_DATA_CONFIG = {
    'window_sizes': [int(x) for x in os.getenv('INDICATOR_WINDOWS', '20,50,200').split(',')],
    'orderbook_depth': int(os.getenv('ORDERBOOK_DEPTH', '10')),
    'update_interval': float(os.getenv('UPDATE_INTERVAL', '1.0'))
}

def validate_config() -> bool:
    """Validate the configuration."""
    required_vars = [
        'BINANCE_API_KEY',
        'BINANCE_API_SECRET',
        'DATABASE_URL'
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logging.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        return False
        
    return True

def get_config() -> Dict[str, Any]:
    """Get the complete configuration."""
    return {
        'logging': LOGGING_CONFIG,
        'database': DATABASE_CONFIG,
        'exchange': EXCHANGE_CONFIG,
        'risk': RISK_CONFIG,
        'strategy': STRATEGY_CONFIG,
        'market_data': MARKET_DATA_CONFIG
    } 