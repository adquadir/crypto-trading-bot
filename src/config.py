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
            'level': 'DEBUG',
            'formatter': 'standard',
            'stream': 'ext://sys.stdout',
        },
        'file': {
            'class': 'logging.FileHandler',
            'level': 'DEBUG',
            'formatter': 'standard',
            'filename': BASE_DIR / 'trading_bot.log',
        },
    },
    'loggers': {
        '': {  # root logger
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
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
    'testnet': os.getenv('BINANCE_TESTNET', 'true').lower() == 'true',
    'symbols': os.getenv('TRADING_SYMBOLS', 'BTCUSDT').split(','),  # Default fallback symbols
    'timeframe': os.getenv('TIMEFRAME', '1m'),
    'discovery': {
        'mode': os.getenv('SYMBOL_DISCOVERY_MODE', 'static'),  # 'static' or 'dynamic'
        'min_volume_24h': float(os.getenv('MIN_24H_VOLUME', '1000000')),
        'min_market_cap': float(os.getenv('MIN_MARKET_CAP', '100000000')),
        'max_spread': float(os.getenv('MAX_SPREAD', '0.002')),
        'min_liquidity': float(os.getenv('MIN_LIQUIDITY', '500000')),
        'max_correlation': float(os.getenv('MAX_CORRELATION', '0.7')),
        'min_volatility': float(os.getenv('MIN_VOLATILITY', '0.01')),
        'max_volatility': float(os.getenv('MAX_VOLATILITY', '0.05')),
        'min_funding_rate': float(os.getenv('MIN_FUNDING_RATE', '-0.0001')),
        'max_funding_rate': float(os.getenv('MAX_FUNDING_RATE', '0.0001')),
        'min_open_interest': float(os.getenv('MIN_OPEN_INTEREST', '1000000')),
        'update_interval': int(os.getenv('SYMBOL_UPDATE_INTERVAL', '3600')),
        'max_symbols': int(os.getenv('MAX_SYMBOLS', '50')),
        'fallback_symbols': os.getenv('FALLBACK_SYMBOLS', 'BTCUSDT,ETHUSDT,BNBUSDT').split(','),
        'cache_duration': int(os.getenv('SYMBOL_CACHE_DURATION', '3600')),
        'retry_attempts': int(os.getenv('SYMBOL_RETRY_ATTEMPTS', '3')),
        'retry_delay': int(os.getenv('SYMBOL_RETRY_DELAY', '60'))
    }
}

# Trading symbols configuration
TRADING_SYMBOLS = os.getenv('TRADING_SYMBOLS', 'BTCUSDT,ETHUSDT,BNBUSDT').split(',')

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
    
    # Check required variables
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logging.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        return False
    
    # Check proxy configuration if proxy is enabled
    if os.getenv('USE_PROXY', 'false').lower() == 'true':
        proxy_vars = ['PROXY_HOST', 'PROXY_PORT', 'PROXY_USER', 'PROXY_PASS']
        missing_proxy = [var for var in proxy_vars if not os.getenv(var)]
        if missing_proxy:
            logging.error(f"Missing required proxy configuration: {', '.join(missing_proxy)}")
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