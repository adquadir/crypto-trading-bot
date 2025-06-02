from typing import Dict
from enum import Enum

class RiskMode(Enum):
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"

# Default configuration
DEFAULT_CONFIG = {
    'initial_balance': 10000.0,
    'risk_mode': RiskMode.BALANCED,
    'supported_pairs': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'],
    'timeframe': '1h',
    'min_confidence': 0.7,
    'max_active_trades': 3,
    
    # Risk parameters
    'risk_params': {
        RiskMode.CONSERVATIVE: {
            'max_position_size': 0.05,  # 5% of account
            'max_leverage': 5,
            'stop_loss_pct': 0.02,  # 2%
            'take_profit_pct': 0.04,  # 4%
            'max_daily_loss': 0.02  # 2%
        },
        RiskMode.BALANCED: {
            'max_position_size': 0.1,  # 10% of account
            'max_leverage': 10,
            'stop_loss_pct': 0.03,  # 3%
            'take_profit_pct': 0.06,  # 6%
            'max_daily_loss': 0.05  # 5%
        },
        RiskMode.AGGRESSIVE: {
            'max_position_size': 0.2,  # 20% of account
            'max_leverage': 20,
            'stop_loss_pct': 0.05,  # 5%
            'take_profit_pct': 0.1,  # 10%
            'max_daily_loss': 0.1  # 10%
        }
    },
    
    # Technical indicators
    'indicators': {
        'rsi': {
            'window': 14,
            'overbought': 70,
            'oversold': 30
        },
        'bollinger_bands': {
            'window': 20,
            'std_dev': 2
        },
        'ema': {
            'fast': 20,
            'slow': 50
        }
    },
    
    # Exchange settings
    'exchange': {
        'name': 'binance',
        'testnet': False,
        'rate_limit': 1200,  # requests per minute
        'websocket_timeout': 30
    },
    
    # Logging
    'logging': {
        'level': 'INFO',
        'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        'file': 'trading_bot.log'
    }
}

def get_config() -> Dict:
    """Get the current configuration."""
    return DEFAULT_CONFIG.copy()

def update_config(new_config: Dict):
    """Update the configuration with new values."""
    DEFAULT_CONFIG.update(new_config) 