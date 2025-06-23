from typing import Dict, Optional, Any
import numpy as np
from dataclasses import dataclass, field
import logging
from datetime import datetime, timedelta
import json
from pathlib import Path
import os
import yaml

logger = logging.getLogger(__name__)

@dataclass
class StrategyProfile:
    name: str
    description: str
    macd_fast_period: int
    macd_slow_period: int
    macd_signal_period: int
    rsi_overbought: float
    rsi_oversold: float
    bb_std_dev: float
    max_position_size: float
    max_leverage: float
    risk_per_trade: float
    max_daily_loss: float
    max_drawdown: float
    volatility_factor: float = 1.0
    confidence_threshold: float = 0.7

class StrategyConfig:
    def __init__(self):
        self.profiles = {}
        self.current_profile = None
        self.config_path = Path("config/strategy_profiles.json")
        self.volatility_history = {}
        self.performance_history = []
        self.load_strategy_profiles()
        
    def load_strategy_profiles(self) -> None:
        """Load strategy profiles from JSON file."""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    self.profiles = json.load(f)
                logger.info(f"Loaded {len(self.profiles)} strategy profiles from {self.config_path}")
            else:
                logger.info(f"No strategy profile config found at {self.config_path}, using defaults")
                self.profiles = self._get_default_profiles()
        except Exception as e:
            logger.error(f"Error loading strategy profiles: {e}")
            # Only use defaults if loading failed
            self.profiles = self._get_default_profiles()
        
    def set_profile(self, profile_name: str) -> None:
        """Set the current strategy profile."""
        if profile_name not in self.profiles:
            logger.error(f"Profile {profile_name} not found")
            return
        self.current_profile = profile_name
        logger.info(f"Switched to {profile_name} strategy profile")

    def _get_default_profiles(self) -> Dict[str, Dict[str, Any]]:
        """Get default strategy profiles."""
        return {
            'conservative': {
                'risk_level': 'low',
                'max_position_size': 0.1,
                'max_leverage': 2,
                'stop_loss_pct': 0.02,
                'take_profit_pct': 0.04,
                'max_drawdown': 0.05,
                'min_volume': 1000000,
                'min_market_cap': 100000000,
                'max_spread': 0.002,
                'min_liquidity': 100000,
                'max_slippage': 0.001,
                'timeframes': ['1m', '5m', '15m'],
                'indicators': {
                    'rsi': {'period': 14, 'overbought': 70, 'oversold': 30},
                    'macd': {'fast': 12, 'slow': 26, 'signal': 9},
                    'bollinger': {'period': 20, 'std_dev': 2},
                    'atr': {'period': 14}
                }
            },
            'moderate': {
                'risk_level': 'medium',
                'max_position_size': 0.2,
                'max_leverage': 3,
                'stop_loss_pct': 0.03,
                'take_profit_pct': 0.06,
                'max_drawdown': 0.1,
                'min_volume': 500000,
                'min_market_cap': 50000000,
                'max_spread': 0.003,
                'min_liquidity': 50000,
                'max_slippage': 0.002,
                'timeframes': ['1m', '5m', '15m', '1h'],
                'indicators': {
                    'rsi': {'period': 14, 'overbought': 75, 'oversold': 25},
                    'macd': {'fast': 12, 'slow': 26, 'signal': 9},
                    'bollinger': {'period': 20, 'std_dev': 2.5},
                    'atr': {'period': 14}
                }
            },
            'aggressive': {
                'risk_level': 'high',
                'max_position_size': 0.3,
                'max_leverage': 5,
                'stop_loss_pct': 0.04,
                'take_profit_pct': 0.08,
                'max_drawdown': 0.15,
                'min_volume': 250000,
                'min_market_cap': 25000000,
                'max_spread': 0.004,
                'min_liquidity': 25000,
                'max_slippage': 0.003,
                'timeframes': ['1m', '5m', '15m', '1h', '4h'],
                'indicators': {
                    'rsi': {'period': 14, 'overbought': 80, 'oversold': 20},
                    'macd': {'fast': 12, 'slow': 26, 'signal': 9},
                    'bollinger': {'period': 20, 'std_dev': 3},
                    'atr': {'period': 14}
                }
            }
        }

    def save_strategy_profiles(self) -> None:
        """Save strategy profiles to JSON file."""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(self.profiles, f, indent=2)
            logger.info("Strategy profiles saved successfully")
        except Exception as e:
            logger.error(f"Error saving strategy profiles: {str(e)}")
            
    def update_profile(self, profile_name: str, settings: Dict[str, Any]) -> None:
        """Update a strategy profile with new settings."""
        if profile_name not in self.profiles:
            logger.error(f"Profile {profile_name} not found")
            return
        
        self.profiles[profile_name].update(settings)
        self.save_strategy_profiles()
        logger.info(f"Updated {profile_name} strategy profile")

    def get_current_profile(self) -> Optional[Dict[str, Any]]:
        """Get the current strategy profile settings."""
        if not self.current_profile:
            logger.warning("No strategy profile selected")
            return None
        return self.profiles.get(self.current_profile)

    def get_profile_names(self) -> list:
        """Get list of available profile names."""
        return list(self.profiles.keys())
            
    def adapt_to_volatility(self, symbol: str, volatility: float) -> None:
        """Adapt strategy parameters based on market volatility."""
        if not self.current_profile:
            return
            
        # Update volatility history
        if symbol not in self.volatility_history:
            self.volatility_history[symbol] = []
        self.volatility_history[symbol].append(volatility)
        
        # Calculate volatility factor based on recent history
        recent_volatility = np.mean(self.volatility_history[symbol][-20:])
        volatility_factor = min(max(recent_volatility / volatility, 0.5), 2.0)
        
        # Adjust parameters based on volatility
        profile = self.profiles[self.current_profile]
        profile['max_position_size'] /= volatility_factor
        profile['stop_loss_pct'] *= volatility_factor
        profile['take_profit_pct'] *= volatility_factor
        
        logger.info(f"Adapted strategy parameters for {symbol} based on volatility")
        
    def adapt_to_performance(self, trade_result: Dict) -> None:
        """Adapt strategy parameters based on trading performance."""
        if not self.current_profile:
            return
            
        self.performance_history.append(trade_result)
        
        # Calculate recent performance metrics
        recent_trades = self.performance_history[-50:]
        win_rate = sum(1 for t in recent_trades if t['pnl'] > 0) / len(recent_trades)
        avg_win = np.mean([t['pnl'] for t in recent_trades if t['pnl'] > 0]) if any(t['pnl'] > 0 for t in recent_trades) else 0
        avg_loss = np.mean([t['pnl'] for t in recent_trades if t['pnl'] < 0]) if any(t['pnl'] < 0 for t in recent_trades) else 0
        
        # Adjust parameters based on performance
        profile = self.profiles[self.current_profile]
        if win_rate > 0.6:  # Good performance
            profile['max_position_size'] *= 1.1
            profile['stop_loss_pct'] *= 0.9
        elif win_rate < 0.4:  # Poor performance
            profile['max_position_size'] *= 0.9
            profile['stop_loss_pct'] *= 1.1
        
        logger.info(f"Adapted strategy parameters based on performance (win rate: {win_rate:.2f})")

def load_strategy_profiles():
    """Load strategy profiles from configuration."""
    try:
        with open('config/strategy_profiles.yaml', 'r') as f:
            profiles = yaml.safe_load(f)
        return profiles
    except Exception as e:
        logger.error(f"Error loading strategy profiles: {e}")
        return {}

# Create a singleton instance
strategy_config = StrategyConfig()

# Export the instance
__all__ = ['strategy_config'] 