import yaml
from pathlib import Path
import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def load_config(config_path: str = "config/config.yaml"):
    """Loads configuration from a YAML file."""
    config_file = Path(config_path)
    if not config_file.exists():
        logger.error(f"Configuration file not found at {config_file}")
        raise FileNotFoundError(f"Configuration file not found at {config_file}")

    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
            logger.info(f"Configuration loaded from {config_file}")
            return config
    except yaml.YAMLError as e:
        logger.error(f"Error parsing configuration file {config_file}: {e}")
        raise ValueError(f"Error parsing configuration file {config_file}: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred while loading configuration from {config_file}: {e}")
        raise 

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
                
        logger.info("Configuration validation successful")
        return True
        
    except Exception as e:
        logger.error(f"Error validating configuration: {e}")
        return False 