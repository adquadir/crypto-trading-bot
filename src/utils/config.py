import yaml
from pathlib import Path
import os
import logging
from typing import Dict, Any
import re
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

def load_config(config_path: str = "config/config.yaml"):
    """Loads configuration from a YAML file with environment variable substitution."""
    config_file = Path(config_path)
    if not config_file.exists():
        logger.error(f"Configuration file not found at {config_file}")
        raise FileNotFoundError(f"Configuration file not found at {config_file}")

    try:
        with open(config_file, 'r') as f:
            config_content = f.read()
            
        # Substitute environment variables
        config_content = _substitute_env_vars(config_content)
        
        config = yaml.safe_load(config_content)
        logger.info(f"Configuration loaded from {config_file}")
        return config
    except yaml.YAMLError as e:
        logger.error(f"Error parsing configuration file {config_file}: {e}")
        raise ValueError(f"Error parsing configuration file {config_file}: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred while loading configuration from {config_file}: {e}")
        raise

def _substitute_env_vars(content: str) -> str:
    """Substitute environment variables in the format ${VAR} or ${VAR:-default}."""
    def replace_var(match):
        var_expr = match.group(1)
        if ':-' in var_expr:
            var_name, default_value = var_expr.split(':-', 1)
            return os.getenv(var_name, default_value)
        else:
            var_name = var_expr
            value = os.getenv(var_name)
            if value is None:
                logger.warning(f"Environment variable {var_name} not found, using empty string")
                return ""
            return value
    
    # Pattern to match ${VAR} or ${VAR:-default}
    pattern = r'\$\{([^}]+)\}'
    return re.sub(pattern, replace_var, content)

def validate_config(config: Dict[str, Any]) -> bool:
    """Validate the configuration dictionary."""
    try:
        # Check required sections
        required_sections = ['exchange', 'trading', 'risk', 'monitoring']
        for section in required_sections:
            if section not in config:
                logger.error(f"Missing required section: {section}")
                return False
                
        # Validate exchange configuration
        exchange = config['exchange']
        required_exchange = ['name', 'api_key', 'api_secret']
        for key in required_exchange:
            if key not in exchange:
                logger.error(f"Missing required exchange config: {key}")
                return False
                
        # Validate trading configuration
        trading = config['trading']
        required_trading = ['risk_per_trade', 'max_open_trades']
        for key in required_trading:
            if key not in trading:
                logger.error(f"Missing required trading config: {key}")
                return False
                
        # Validate risk configuration
        risk = config['risk']
        required_risk = ['max_drawdown', 'max_leverage']
        for key in required_risk:
            if key not in risk:
                logger.error(f"Missing required risk config: {key}")
                return False
                
        # Validate monitoring configuration
        monitoring = config['monitoring']
        required_monitoring = ['health_check_interval']
        for key in required_monitoring:
            if key not in monitoring:
                logger.error(f"Missing required monitoring config: {key}")
                return False
                
        # Add default for health_check_interval if not present in monitoring section
        if 'health_check_interval' not in monitoring:
            env_val = os.getenv('HEALTH_CHECK_INTERVAL')
            if env_val is not None:
                try:
                    monitoring['health_check_interval'] = int(env_val)
                except ValueError:
                    monitoring['health_check_interval'] = 60
            else:
                monitoring['health_check_interval'] = 60  # Default to 60 seconds
                
        logger.info("Configuration validation successful")
        return True
        
    except Exception as e:
        logger.error(f"Error validating configuration: {e}")
        return False 

def get_default_config() -> Dict[str, Any]:
    """Get default configuration."""
    return {
        'exchange': {
            'name': 'binance',
            'api_key': '',
            'api_secret': '',
            'testnet': True
        },
        'trading': {
            'base_currency': 'USDT',
            'max_open_trades': 3,
            'stake_amount': 100,
            'stake_currency': 'USDT',
            'dry_run': True,
            'health_check_interval': 60,  # Health check every 60 seconds
            'position_check_interval': 300,  # Check positions every 5 minutes
            'funding_rate_check_interval': 3600  # Check funding rates every hour
        },
        'risk_management': {
            'max_daily_loss': 5.0,  # 5% max daily loss
            'max_drawdown': 10.0,  # 10% max drawdown
            'max_leverage': 3.0,  # Maximum leverage
            'position_size_limit': 0.1  # 10% of portfolio per position
        },
        'monitoring': {
            'health_check_interval': 60,  # Health check every 60 seconds
            'log_level': 'INFO',
            'enable_telegram': False,
            'telegram_token': '',
            'telegram_chat_id': '',
            'metrics_enabled': True
        },
        'strategy': {
            'default_profile': 'default',
            'profiles': {
                'default': {
                    'name': 'default',
                    'description': 'Default trading strategy',
                    'parameters': {
                        'entry_threshold': 0.02,
                        'exit_threshold': 0.01,
                        'stop_loss': 0.03,
                        'take_profit': 0.05,
                        'max_position_size': 0.1,
                        'leverage': 1.0,
                        'min_volume': 1000000.0,
                        'min_market_cap': 100000000.0,
                        'max_spread': 0.5,
                        'min_volatility': 0.5,
                        'max_volatility': 5.0
                    }
                }
            }
        }
    } 