from typing import Dict, Optional
import numpy as np
from dataclasses import dataclass, field
import logging
from datetime import datetime, timedelta
import json
from pathlib import Path

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

class DynamicStrategyConfig:
    def __init__(self, config_path: str = "config/strategy_profiles.json"):
        self.config_path = Path(config_path)
        self.config_path.parent.mkdir(exist_ok=True)
        self.profiles: Dict[str, StrategyProfile] = {}
        self.current_profile: Optional[StrategyProfile] = None
        self.performance_history = []
        self.volatility_history = {}
        self._load_profiles()
        
    def _load_profiles(self):
        """Load strategy profiles from JSON file."""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                    for profile_data in data['profiles']:
                        profile = StrategyProfile(**profile_data)
                        self.profiles[profile.name] = profile
                logger.info(f"Loaded {len(self.profiles)} strategy profiles")
            except Exception as e:
                logger.error(f"Error loading strategy profiles: {e}")
                self._create_default_profiles()
        else:
            self._create_default_profiles()
            
    def _create_default_profiles(self):
        """Create default strategy profiles if none exist."""
        default_profiles = {
            "conservative": StrategyProfile(
                name="conservative",
                description="Low risk, stable returns",
                macd_fast_period=12,
                macd_slow_period=26,
                macd_signal_period=9,
                rsi_overbought=70,
                rsi_oversold=30,
                bb_std_dev=2.0,
                max_position_size=0.1,
                max_leverage=2.0,
                risk_per_trade=0.01,
                max_daily_loss=0.02,
                max_drawdown=0.05,
                volatility_factor=0.8,
                confidence_threshold=0.8
            ),
            "moderate": StrategyProfile(
                name="moderate",
                description="Balanced risk and returns",
                macd_fast_period=10,
                macd_slow_period=21,
                macd_signal_period=7,
                rsi_overbought=75,
                rsi_oversold=25,
                bb_std_dev=2.2,
                max_position_size=0.15,
                max_leverage=3.0,
                risk_per_trade=0.015,
                max_daily_loss=0.03,
                max_drawdown=0.08,
                volatility_factor=1.0,
                confidence_threshold=0.7
            ),
            "aggressive": StrategyProfile(
                name="aggressive",
                description="Higher risk, higher potential returns",
                macd_fast_period=8,
                macd_slow_period=17,
                macd_signal_period=5,
                rsi_overbought=80,
                rsi_oversold=20,
                bb_std_dev=2.5,
                max_position_size=0.2,
                max_leverage=5.0,
                risk_per_trade=0.02,
                max_daily_loss=0.04,
                max_drawdown=0.12,
                volatility_factor=1.2,
                confidence_threshold=0.6
            )
        }
        self.profiles = default_profiles
        self._save_profiles()
        
    def _save_profiles(self):
        """Save strategy profiles to JSON file."""
        try:
            data = {
                'profiles': [
                    {
                        'name': profile.name,
                        'description': profile.description,
                        'macd_fast_period': profile.macd_fast_period,
                        'macd_slow_period': profile.macd_slow_period,
                        'macd_signal_period': profile.macd_signal_period,
                        'rsi_overbought': profile.rsi_overbought,
                        'rsi_oversold': profile.rsi_oversold,
                        'bb_std_dev': profile.bb_std_dev,
                        'max_position_size': profile.max_position_size,
                        'max_leverage': profile.max_leverage,
                        'risk_per_trade': profile.risk_per_trade,
                        'max_daily_loss': profile.max_daily_loss,
                        'max_drawdown': profile.max_drawdown,
                        'volatility_factor': profile.volatility_factor,
                        'confidence_threshold': profile.confidence_threshold
                    }
                    for profile in self.profiles.values()
                ]
            }
            with open(self.config_path, 'w') as f:
                json.dump(data, f, indent=4)
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
            self._save_profiles()
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