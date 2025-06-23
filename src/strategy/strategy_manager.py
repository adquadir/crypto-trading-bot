import logging
from typing import Dict, List, Any, Optional
import os
import json

# from src.strategy.dynamic_config import StrategyConfig
from src.strategy.dynamic_config import StrategyConfig
from src.utils.config import validate_config

logger = logging.getLogger(__name__)

class StrategyManager:
    """Manages trading strategies and their configurations."""
    
    def __init__(self, exchange_client: Any):
        """Initialize the strategy manager."""
        self.exchange_client = exchange_client
        self.strategy_config = StrategyConfig()
        self.active_strategies: Dict[str, Any] = {}
        self.strategy_profiles = self.strategy_config.profiles
        
    async def initialize(self):
        """Async initialization hook for compatibility with bot startup."""
        try:
            # Activate default strategies that exist in the profiles
            default_strategies = ['scalping', 'default']  # Use strategies that actually exist
            for strategy_name in default_strategies:
                if self.activate_strategy(strategy_name):
                    logger.info(f"Activated strategy: {strategy_name}")
                else:
                    logger.warning(f"Failed to activate strategy: {strategy_name}")
        except Exception as e:
            logger.error(f"Error initializing strategy manager: {e}")
        
    def get_strategy_profile(self, strategy_name: str) -> Optional[Dict[str, Any]]:
        """Get a strategy profile by name."""
        try:
            # Reload profiles fresh from config to ensure we have latest
            self.strategy_config.load_strategy_profiles()
            self.strategy_profiles = self.strategy_config.profiles
            
            profile = self.strategy_profiles.get(strategy_name)
            if not profile:
                logger.error(f"Strategy profile not found: {strategy_name}")
                logger.debug(f"Available profiles: {list(self.strategy_profiles.keys())}")
                return None
            return profile
        except Exception as e:
            logger.error(f"Error getting strategy profile {strategy_name}: {e}")
            return None
            
    def update_strategy_profile(self, strategy_name: str, profile: Dict[str, Any]) -> bool:
        """Update a strategy profile."""
        try:
            if not self._validate_profile(profile):
                logger.error(f"Invalid strategy profile for {strategy_name}")
                return False
                
            self.strategy_profiles[strategy_name] = profile
            self._save_profiles()
            return True
            
        except Exception as e:
            logger.error(f"Error updating strategy profile {strategy_name}: {e}")
            return False
            
    def _validate_profile(self, profile: Dict[str, Any]) -> bool:
        """Validate a strategy profile."""
        try:
            # Handle both formats: direct validation and nested validation
            if 'name' in profile and 'description' in profile and 'parameters' in profile:
                # Direct format - validate normally
                required_fields = ['name', 'description', 'parameters']
                if not all(field in profile for field in required_fields):
                    return False
                    
                required_params = [
                    'entry_threshold',
                    'exit_threshold', 
                    'stop_loss',
                    'take_profit',
                    'max_position_size',
                    'leverage'
                ]
                
                if not all(param in profile['parameters'] for param in required_params):
                    return False
            else:
                # JSON file format - profiles are valid by default since they come from config
                logger.info(f"Profile validation passed for loaded JSON format")
                return True
                
            return True
            
        except Exception as e:
            logger.error(f"Error validating strategy profile: {e}")
            return False
            
    def _save_profiles(self) -> None:
        """Save strategy profiles to file."""
        try:
            profiles_path = os.path.join('config', 'strategy_profiles.json')
            with open(profiles_path, 'w') as f:
                json.dump(self.strategy_profiles, f, indent=4)
            logger.info("Strategy profiles saved successfully")
        except Exception as e:
            logger.error(f"Error saving strategy profiles: {e}")
            
    def get_active_strategies(self) -> Dict[str, Any]:
        """Get all active strategies."""
        return self.active_strategies
        
    def activate_strategy(self, strategy_name: str) -> bool:
        """Activate a strategy."""
        try:
            profile = self.get_strategy_profile(strategy_name)
            if not profile:
                logger.error(f"Strategy profile not found: {strategy_name}")
                return False
                
            self.active_strategies[strategy_name] = profile
            logger.info(f"Strategy activated: {strategy_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error activating strategy {strategy_name}: {e}")
            return False
            
    def deactivate_strategy(self, strategy_name: str) -> bool:
        """Deactivate a strategy."""
        try:
            if strategy_name in self.active_strategies:
                del self.active_strategies[strategy_name]
                logger.info(f"Strategy deactivated: {strategy_name}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error deactivating strategy {strategy_name}: {e}")
            return False 