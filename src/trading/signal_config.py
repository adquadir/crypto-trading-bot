"""
Signal Configuration Module
Manages signal source preferences for Paper Trading Engine
"""

from dataclasses import dataclass, asdict
from typing import Dict
from threading import RLock
import logging

logger = logging.getLogger(__name__)

@dataclass
class SignalConfig:
    """Signal source configuration for Paper Trading Engine"""
    profit_scraping_enabled: bool = True
    opportunity_manager_enabled: bool = True

# Global signal configuration with thread safety
_signal_config = SignalConfig()
_config_lock = RLock()

def get_signal_config() -> Dict[str, bool]:
    """Get current signal configuration as dictionary"""
    with _config_lock:
        config_dict = asdict(_signal_config)
        logger.debug(f"Signal config retrieved: {config_dict}")
        return config_dict

def set_signal_config(updates: Dict[str, bool]) -> Dict[str, bool]:
    """Update signal configuration with provided values"""
    with _config_lock:
        old_config = asdict(_signal_config)
        
        # Update profit scraping setting
        if 'profit_scraping_enabled' in updates:
            _signal_config.profit_scraping_enabled = bool(updates['profit_scraping_enabled'])
            logger.info(f"Profit Scraping: {old_config['profit_scraping_enabled']} → {_signal_config.profit_scraping_enabled}")
        
        # Update opportunity manager setting
        if 'opportunity_manager_enabled' in updates:
            _signal_config.opportunity_manager_enabled = bool(updates['opportunity_manager_enabled'])
            logger.info(f"Opportunity Manager: {old_config['opportunity_manager_enabled']} → {_signal_config.opportunity_manager_enabled}")
        
        new_config = asdict(_signal_config)
        logger.info(f"Signal configuration updated: {new_config}")
        return new_config

def is_profit_scraping_enabled() -> bool:
    """Check if profit scraping signals are enabled"""
    with _config_lock:
        return _signal_config.profit_scraping_enabled

def is_opportunity_manager_enabled() -> bool:
    """Check if opportunity manager signals are enabled"""
    with _config_lock:
        return _signal_config.opportunity_manager_enabled

def reset_signal_config():
    """Reset signal configuration to defaults"""
    with _config_lock:
        global _signal_config
        _signal_config = SignalConfig()
        logger.info("Signal configuration reset to defaults")
        return asdict(_signal_config)
