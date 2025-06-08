from typing import Dict, Optional, Any
import numpy as np
from dataclasses import dataclass, field
import logging
from datetime import datetime, timedelta
import json
from pathlib import Path
import os

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
        self.config_path = Path(__file__).parent / 'config' / 'strategy_profiles.json'
        self.load_strategy_profiles()

    def load_strategy_profiles(self) -> None:
        """Load strategy profiles from JSON file."""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    self.profiles = json.load(f)
                logger.info(f"Loaded {len(self.profiles)} strategy profiles")
            else:
                logger.warning(f"Strategy profiles file not found at {self.config_path}")
                self.profiles = self._get_default_profiles()
                self._save_profiles()
        except Exception as e:
            logger.error(f"Error loading strategy profiles: {str(e)}")
            self.profiles = self._get_default_profiles()

    def _save_profiles(self) -> None:
        """Save strategy profiles to JSON file."""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(self.profiles, f, indent=2)
            logger.info("Strategy profiles saved successfully")
        except Exception as e:
            logger.error(f"Error saving strategy profiles: {str(e)}")

    def _get_default_profiles(self) -> Dict[str, Dict[str, Any]]:
        """Get default strategy profiles."""
        return {
            'conservative': {
                'max_position_size': 0.1,
                'max_leverage': 2,
                'min_risk_reward': 3.0,
                'max_drawdown': 0.05,
                'min_confidence': 0.8,
                'max_correlation': 0.5,
                'min_volume_24h': 1000000,
                'max_spread': 0.02,
                'min_liquidity': 100000,
                'max_volatility': 0.5,
                'min_funding_rate': -0.001,
                'max_funding_rate': 0.001
            },
            'moderate': {
                'max_position_size': 0.2,
                'max_leverage': 3,
                'min_risk_reward': 2.0,
                'max_drawdown': 0.1,
                'min_confidence': 0.6,
                'max_correlation': 0.7,
                'min_volume_24h': 500000,
                'max_spread': 0.03,
                'min_liquidity': 50000,
                'max_volatility': 0.8,
                'min_funding_rate': -0.002,
                'max_funding_rate': 0.002
            },
            'aggressive': {
                'max_position_size': 0.3,
                'max_leverage': 5,
                'min_risk_reward': 1.5,
                'max_drawdown': 0.15,
                'min_confidence': 0.4,
                'max_correlation': 0.8,
                'min_volume_24h': 100000,
                'max_spread': 0.05,
                'min_liquidity': 10000,
                'max_volatility': 1.0,
                'min_funding_rate': -0.003,
                'max_funding_rate': 0.003
            }
        }

    def switch_profile(self, profile_name: str) -> None:
        """Switch to a different strategy profile."""
        if profile_name not in self.profiles:
            logger.error(f"Profile {profile_name} not found")
            return
        
        self.current_profile = profile_name
        logger.info(f"Switched to {profile_name} strategy profile")

    def get_current_profile(self) -> Optional[Dict[str, Any]]:
        """Get the current strategy profile settings."""
        if not self.current_profile:
            logger.warning("No strategy profile selected")
            return None
        return self.profiles.get(self.current_profile)

    def update_profile(self, profile_name: str, settings: Dict[str, Any]) -> None:
        """Update a strategy profile with new settings."""
        if profile_name not in self.profiles:
            logger.error(f"Profile {profile_name} not found")
            return
        
        self.profiles[profile_name].update(settings)
        self._save_profiles()
        logger.info(f"Updated {profile_name} strategy profile")

    def get_profile_names(self) -> list:
        """Get list of available profile names."""
        return list(self.profiles.keys())

# Create a singleton instance
strategy_config = StrategyConfig()

# Export the instance
__all__ = ['strategy_config']

class DynamicStrategyConfig:
    def __init__(self):
        self.profiles = {}
        self.current_profile = None
        self.profile_file = "strategy_profiles.json"
        self.load_strategy_profiles()  # Load profiles on initialization

    def load_strategy_profiles(self):
        """Load strategy profiles from JSON file."""
        try:
            if os.path.exists(self.profile_file):
                with open(self.profile_file, 'r') as f:
                    self.profiles = json.load(f)
                logger.info(f"Loaded {len(self.profiles)} strategy profiles")
            else:
                # Create default profiles if file doesn't exist
                self.profiles = {
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
                self.save_strategy_profiles()
                logger.info("Created default strategy profiles")
        except Exception as e:
            logger.error(f"Error loading strategy profiles: {str(e)}")
            raise

    def save_strategy_profiles(self):
        """Save strategy profiles to JSON file."""
        try:
            with open(self.profile_file, 'w') as f:
                json.dump(self.profiles, f, indent=4)
            logger.info("Strategy profiles saved successfully")
        except Exception as e:
            logger.error(f"Error saving strategy profiles: {e}")

    def set_profile(self, profile_name: str):
        """Set the current strategy profile."""
        if profile_name in self.profiles:
            self.current_profile = self.profiles[profile_name]
            logger.info(f"Switched to {profile_name} strategy profile")
        else:
            logger.error(f"Profile {profile_name} not found")
            
    def update_profile(self, profile_name: str, **kwargs):
        """Update parameters for a specific profile."""
        if profile_name in self.profiles:
            profile = self.profiles[profile_name]
            for key, value in kwargs.items():
                if hasattr(profile, key):
                    setattr(profile, key, value)
            self.save_strategy_profiles()
            logger.info(f"Updated {profile_name} profile parameters")
        else:
            logger.error(f"Profile {profile_name} not found")
            
    def adapt_to_volatility(self, symbol: str, volatility: float):
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
        self.current_profile.bb_std_dev *= volatility_factor
        self.current_profile.max_position_size /= volatility_factor
        self.current_profile.risk_per_trade /= volatility_factor
        
        logger.info(f"Adapted strategy parameters for {symbol} based on volatility")
        
    def adapt_to_performance(self, trade_result: Dict):
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
        if win_rate > 0.6 and avg_win > abs(avg_loss):
            # Increase risk slightly
            self.current_profile.max_position_size *= 1.1
            self.current_profile.risk_per_trade *= 1.1
        elif win_rate < 0.4 or avg_win < abs(avg_loss):
            # Decrease risk
            self.current_profile.max_position_size *= 0.9
            self.current_profile.risk_per_trade *= 0.9
            
        logger.info(f"Adapted strategy parameters based on performance metrics")
        
    def get_symbol_specific_params(self, symbol: str, confidence_score: float) -> Dict:
        """Get symbol-specific strategy parameters based on confidence score."""
        if not self.current_profile:
            return {}
            
        # Adjust parameters based on confidence score
        confidence_factor = confidence_score / self.current_profile.confidence_threshold
        
        return {
            'macd_fast_period': self.current_profile.macd_fast_period,
            'macd_slow_period': self.current_profile.macd_slow_period,
            'macd_signal_period': self.current_profile.macd_signal_period,
            'rsi_overbought': self.current_profile.rsi_overbought,
            'rsi_oversold': self.current_profile.rsi_oversold,
            'bb_std_dev': self.current_profile.bb_std_dev,
            'max_position_size': self.current_profile.max_position_size * confidence_factor,
            'max_leverage': min(self.current_profile.max_leverage * confidence_factor, 20.0),
            'risk_per_trade': self.current_profile.risk_per_trade * confidence_factor
        }
        
    def get_risk_limits(self) -> Dict:
        """Get current risk management parameters."""
        if not self.current_profile:
            return {}
            
        return {
            'max_daily_loss': self.current_profile.max_daily_loss,
            'max_drawdown': self.current_profile.max_drawdown,
            'max_position_size': self.current_profile.max_position_size,
            'max_leverage': self.current_profile.max_leverage,
            'risk_per_trade': self.current_profile.risk_per_trade
        }

    def get_volatility_impact_factor(self, profile):
        """Calculate how much market volatility impacts the profile's parameters."""
        profile_data = self.profiles.get(profile, {})
        if not profile_data:
            return 1.0

        # Calculate impact factor based on profile's risk tolerance
        risk_tolerance = profile_data.get('risk_tolerance', 0.5)
        return 1.0 + (1.0 - risk_tolerance) * 0.5  # Higher impact for conservative profiles

    def get_volatility_adjustments(self, profile):
        """Get parameter adjustments made due to volatility changes."""
        profile_data = self.profiles.get(profile, {})
        if not profile_data:
            return {}

        # Get base parameters
        base_params = profile_data.get('parameters', {})
        
        # Calculate volatility-based adjustments
        adjustments = {}
        for param, value in base_params.items():
            if param in ['macd_fast', 'macd_slow', 'rsi_period']:
                # Adjust technical indicator periods based on volatility
                adjustments[param] = f"{value} ± {int(value * 0.1)}"
            elif param in ['rsi_overbought', 'rsi_oversold']:
                # Adjust RSI thresholds based on volatility
                adjustments[param] = f"{value} ± {int(value * 0.05)}"
            elif param in ['bb_std_dev']:
                # Adjust Bollinger Bands based on volatility
                adjustments[param] = f"{value} ± {value * 0.1:.2f}"
            elif param in ['position_size', 'max_leverage']:
                # Adjust risk parameters based on volatility
                adjustments[param] = f"{value} ± {value * 0.2:.2f}"

        return adjustments

    def adapt_to_volatility(self, profile, current_volatility):
        """Adapt profile parameters based on current market volatility."""
        profile_data = self.profiles.get(profile, {})
        if not profile_data:
            return

        base_params = profile_data.get('parameters', {})
        changes = {}

        # Calculate volatility ratio (current vs historical average)
        vol_ratio = current_volatility / profile_data.get('historical_volatility', current_volatility)
        
        # Adjust parameters based on volatility ratio
        for param, value in base_params.items():
            if param in ['macd_fast', 'macd_slow', 'rsi_period']:
                # Increase periods in high volatility
                new_value = int(value * (1 + (vol_ratio - 1) * 0.2))
                changes[param] = new_value
            elif param in ['rsi_overbought', 'rsi_oversold']:
                # Widen RSI thresholds in high volatility
                adjustment = int(value * (vol_ratio - 1) * 0.1)
                if param == 'rsi_overbought':
                    changes[param] = value + adjustment
                else:
                    changes[param] = value - adjustment
            elif param in ['bb_std_dev']:
                # Increase BB width in high volatility
                changes[param] = value * (1 + (vol_ratio - 1) * 0.2)
            elif param in ['position_size', 'max_leverage']:
                # Reduce position size and leverage in high volatility
                changes[param] = value * (1 - (vol_ratio - 1) * 0.3)

        # Apply changes if any
        if changes:
            self.update_profile(profile, changes)
            return changes
        return None

    def adapt_to_performance(self, profile, win_rate, profit_factor):
        """Adapt profile parameters based on trading performance."""
        profile_data = self.profiles.get(profile, {})
        if not profile_data:
            return

        base_params = profile_data.get('parameters', {})
        changes = {}

        # Adjust parameters based on win rate
        if win_rate < 0.4:  # Poor performance
            # Make strategy more conservative
            for param, value in base_params.items():
                if param in ['position_size', 'max_leverage']:
                    changes[param] = value * 0.8  # Reduce risk
                elif param in ['rsi_overbought', 'rsi_oversold']:
                    # Widen RSI thresholds
                    if param == 'rsi_overbought':
                        changes[param] = value + 5
                    else:
                        changes[param] = value - 5
        elif win_rate > 0.6 and profit_factor > 1.5:  # Good performance
            # Allow more aggressive trading
            for param, value in base_params.items():
                if param in ['position_size', 'max_leverage']:
                    changes[param] = min(value * 1.2, profile_data.get('max_' + param, value * 1.5))
                elif param in ['rsi_overbought', 'rsi_oversold']:
                    # Tighten RSI thresholds
                    if param == 'rsi_overbought':
                        changes[param] = max(value - 3, 70)
                    else:
                        changes[param] = min(value + 3, 30)

        # Apply changes if any
        if changes:
            self.update_profile(profile, changes)
            return changes
        return None

    def get_profiles(self):
        """Return a list of available strategy profile names."""
        return list(self.profiles.keys())

    def switch_profile(self, profile_name: str) -> None:
        """Switch to a different strategy profile.
        
        Args:
            profile_name: Name of the profile to switch to
        """
        if profile_name not in self.profiles:
            raise ValueError(f"Profile '{profile_name}' not found")
        
        self.current_profile = self.profiles[profile_name]
        logger.info(f"Switched to {profile_name} strategy profile")
        
        # Update strategy parameters based on the new profile
        self._update_strategy_parameters()
    
    def _update_strategy_parameters(self) -> None:
        """Update strategy parameters based on current profile."""
        if not self.current_profile:
            return
            
        # Update risk parameters
        self.risk_level = self.current_profile['risk_level']
        self.max_position_size = self.current_profile['max_position_size']
        self.max_leverage = self.current_profile['max_leverage']
        self.stop_loss_pct = self.current_profile['stop_loss_pct']
        self.take_profit_pct = self.current_profile['take_profit_pct']
        self.max_drawdown = self.current_profile['max_drawdown']
        
        # Update market data parameters
        self.min_volume = self.current_profile['min_volume']
        self.min_market_cap = self.current_profile['min_market_cap']
        self.max_spread = self.current_profile['max_spread']
        self.min_liquidity = self.current_profile['min_liquidity']
        self.max_slippage = self.current_profile['max_slippage']
        
        # Update indicator parameters
        self.indicators = self.current_profile['indicators']
        
        # Update timeframes
        self.timeframes = self.current_profile['timeframes']
        
        logger.info(f"Updated strategy parameters for {self.risk_level} risk level") 