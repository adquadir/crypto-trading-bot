from typing import Dict, List, Optional, Tuple
from enum import Enum
import logging
from datetime import datetime, timedelta
import numpy as np
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

class RiskMode(Enum):
    CONSERVATIVE = 'conservative'
    BALANCED = 'balanced'
    AGGRESSIVE = 'aggressive'

@dataclass
class Position:
    symbol: str
    size: float
    entry_price: float
    current_price: float
    stop_loss: float
    take_profit: float
    leverage: float
    direction: str  # 'LONG' or 'SHORT'
    trailing_stop: Optional[float] = None
    trailing_distance: Optional[float] = None
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())

class RiskManager:
    def __init__(
        self,
        account_balance: float,
        risk_mode: RiskMode = RiskMode.BALANCED,
        max_position_size: float = 0.1,
        max_leverage: float = 3.0,
        risk_per_trade: float = 0.02,
        max_open_trades: int = 5,
        max_correlation: float = 0.7,
        min_risk_reward: float = 2.0
    ):
        self.account_balance = account_balance
        self.risk_mode = risk_mode
        self.positions: Dict[str, Position] = {}  # symbol -> Position
        self.daily_stats = {
            'trades': 0,
            'wins': 0,
            'losses': 0,
            'pnl': 0.0,
            'max_drawdown': 0.0
        }
        self.last_reset = datetime.now()
        
        # Risk parameters based on mode
        self.risk_params = {
            RiskMode.CONSERVATIVE: {
                'max_position_size': 0.02,  # 2% of account
                'max_leverage': 3.0,
                'stop_loss_pct': 0.02,      # 2% stop loss
                'take_profit_pct': 0.04,    # 4% take profit
                'max_daily_loss': 0.03,     # 3% max daily loss
                'max_drawdown': 0.05,       # 5% max drawdown
                'max_correlation': 0.5,     # Maximum correlation between positions
                'trailing_stop_pct': 0.015,  # 1.5% trailing stop
                'max_open_trades': 3
            },
            RiskMode.BALANCED: {
                'max_position_size': 0.05,  # 5% of account
                'max_leverage': 5.0,
                'stop_loss_pct': 0.03,      # 3% stop loss
                'take_profit_pct': 0.06,    # 6% take profit
                'max_daily_loss': 0.05,     # 5% max daily loss
                'max_drawdown': 0.10,       # 10% max drawdown
                'max_correlation': 0.7,     # Maximum correlation between positions
                'trailing_stop_pct': 0.02,   # 2% trailing stop
                'max_open_trades': 5
            },
            RiskMode.AGGRESSIVE: {
                'max_position_size': 0.10,  # 10% of account
                'max_leverage': 10.0,
                'stop_loss_pct': 0.04,      # 4% stop loss
                'take_profit_pct': 0.08,    # 8% take profit
                'max_daily_loss': 0.08,     # 8% max daily loss
                'max_drawdown': 0.15,       # 15% max drawdown
                'max_correlation': 0.8,     # Maximum correlation between positions
                'trailing_stop_pct': 0.025,  # 2.5% trailing stop
                'max_open_trades': 8
            }
        }
        
    def reset_daily_stats(self):
        """Reset daily statistics at the start of each day."""
        if datetime.now().date() > self.last_reset.date():
            self.daily_stats = {
                'trades': 0,
                'wins': 0,
                'losses': 0,
                'pnl': 0.0,
                'max_drawdown': 0.0
            }
            self.last_reset = datetime.now()
            
    def update_position(self, symbol: str, current_price: float):
        """Update position with current price and check trailing stops."""
        if symbol in self.positions:
            position = self.positions[symbol]
            position.current_price = current_price
            
            # Update trailing stop if enabled
            if position.trailing_stop is not None:
                if position.direction == 'LONG':
                    new_stop = current_price * (1 - position.trailing_distance)
                    if new_stop > position.trailing_stop:
                        position.trailing_stop = new_stop
                else:  # SHORT
                    new_stop = current_price * (1 + position.trailing_distance)
                    if new_stop < position.trailing_stop:
                        position.trailing_stop = new_stop
                        
    def check_stop_conditions(self, symbol: str, current_price: float) -> Optional[str]:
        """Check if any stop conditions are triggered."""
        if symbol in self.positions:
            position = self.positions[symbol]
            
            # Check trailing stop
            if position.trailing_stop is not None:
                if (position.direction == 'LONG' and current_price <= position.trailing_stop) or \
                   (position.direction == 'SHORT' and current_price >= position.trailing_stop):
                    return 'trailing_stop'
                    
            # Check regular stop loss
            if (position.direction == 'LONG' and current_price <= position.stop_loss) or \
               (position.direction == 'SHORT' and current_price >= position.stop_loss):
                return 'stop_loss'
                
            # Check take profit
            if (position.direction == 'LONG' and current_price >= position.take_profit) or \
               (position.direction == 'SHORT' and current_price <= position.take_profit):
                return 'take_profit'
                    
        return None
        
    def calculate_position_size(self, symbol: str, current_price: float, direction: str, indicators: Dict, confidence: float) -> float:
        """Calculate position size based on market regime, volatility, and confidence."""
        try:
            # Get account balance
            balance = self.account_balance
            if balance <= 0:
                logger.warning("Invalid account balance for position sizing")
                return 0.0
            
            # Get market regime
            regime = indicators.get('regime', 'UNKNOWN')
            regime_strength = indicators.get('regime_strength', 0.0)
            
            # Get volatility metrics
            atr = indicators.get('atr', 0.0)
            bb_width = indicators.get('bollinger_bands', {}).get('width', 0.0)
            
            # Calculate base risk per trade (percentage of account)
            base_risk = self.risk_params[self.risk_mode]['risk_per_trade']
            
            # Adjust risk based on market regime
            if regime == 'TRENDING':
                risk_multiplier = 1.2  # Increase risk in trending markets
            elif regime == 'RANGING':
                risk_multiplier = 0.8  # Decrease risk in ranging markets
            else:  # VOLATILE
                risk_multiplier = 0.6  # Significantly reduce risk in volatile markets
            
            # Adjust risk based on regime strength
            risk_multiplier *= (0.5 + regime_strength * 0.5)  # Scale between 50% and 100% of multiplier
            
            # Adjust risk based on volatility
            volatility_factor = 1.0
            if atr > 0 and current_price > 0:
                atr_percent = atr / current_price
                if atr_percent > 0.05:  # High volatility
                    volatility_factor = 0.7
                elif atr_percent > 0.02:  # Medium volatility
                    volatility_factor = 0.85
            
            # Adjust risk based on Bollinger Band width
            if bb_width > 0.05:  # Wide bands
                volatility_factor *= 0.8
            
            # Calculate final risk amount
            risk_amount = balance * base_risk * risk_multiplier * volatility_factor
            
            # Adjust for confidence
            risk_amount *= confidence
            
            # Calculate position size based on stop loss distance
            stop_loss = self.calculate_stop_loss(symbol, current_price, direction, indicators)
            if stop_loss is None or stop_loss == current_price:
                logger.warning("Invalid stop loss for position sizing")
                return 0.0
            
            stop_loss_distance = abs(current_price - stop_loss)
            if stop_loss_distance == 0:
                logger.warning("Zero stop loss distance")
                return 0.0
            
            position_size = risk_amount / stop_loss_distance
            
            # Apply position size limits
            max_position = balance * self.risk_params[self.risk_mode]['max_position_size']
            position_size = min(position_size, max_position)
            
            # Apply minimum position size
            min_position = self.risk_params[self.risk_mode]['max_position_size'] * 0.001
            if position_size < min_position:
                logger.debug("Position size below minimum threshold")
                return 0.0
            
            return position_size
            
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return 0.0

    def calculate_stop_loss(self, symbol: str, current_price: float, direction: str, indicators: Dict) -> Optional[float]:
        """Calculate stop loss level based on market structure and volatility."""
        try:
            # Get market regime
            regime = indicators.get('regime', 'UNKNOWN')
            
            # Get volatility metrics
            atr = indicators.get('atr', 0.0)
            
            # Calculate base ATR multiplier based on regime
            if regime == 'TRENDING':
                atr_multiplier = 2.0
            elif regime == 'RANGING':
                atr_multiplier = 1.5
            else:  # VOLATILE
                atr_multiplier = 2.5
            
            # Calculate initial stop loss based on ATR
            if direction == 'LONG':
                stop_loss = current_price - (atr * atr_multiplier)
            else:  # SHORT
                stop_loss = current_price + (atr * atr_multiplier)
            
            # Get structure levels
            structure_levels = indicators.get('structure_levels', {})
            if structure_levels:
                if direction == 'LONG':
                    # Find nearest support level below current price
                    support_levels = [level for level in structure_levels.get('supports', []) if level < current_price]
                    if support_levels:
                        nearest_support = max(support_levels)
                        # Use the higher of ATR-based stop loss or structure-based stop loss
                        stop_loss = max(stop_loss, nearest_support)
                else:  # SHORT
                    # Find nearest resistance level above current price
                    resistance_levels = [level for level in structure_levels.get('resistances', []) if level > current_price]
                    if resistance_levels:
                        nearest_resistance = min(resistance_levels)
                        # Use the lower of ATR-based stop loss or structure-based stop loss
                        stop_loss = min(stop_loss, nearest_resistance)
            
            # Validate stop loss
            if direction == 'LONG' and stop_loss >= current_price:
                logger.warning("Invalid stop loss for LONG position")
                return None
            elif direction == 'SHORT' and stop_loss <= current_price:
                logger.warning("Invalid stop loss for SHORT position")
                return None
                
            return stop_loss
            
        except Exception as e:
            logger.error(f"Error calculating stop loss: {e}")
            return None

    def calculate_take_profit(self, symbol: str, current_price: float, direction: str, indicators: Dict) -> Optional[float]:
        """Calculate take profit level based on market structure and volatility."""
        try:
            # Get market regime
            regime = indicators.get('regime', 'UNKNOWN')
            
            # Get volatility metrics
            atr = indicators.get('atr', 0.0)
            
            # Calculate base ATR multiplier based on regime
            if regime == 'TRENDING':
                atr_multiplier = 3.0  # Wider take profit in trending markets
            elif regime == 'RANGING':
                atr_multiplier = 2.0  # Tighter take profit in ranging markets
            else:  # VOLATILE
                atr_multiplier = 4.0  # Widest take profit in volatile markets
            
            # Calculate initial take profit based on ATR
            if direction == 'LONG':
                take_profit = current_price + (atr * atr_multiplier)
            else:  # SHORT
                take_profit = current_price - (atr * atr_multiplier)
            
            # Get structure levels
            structure_levels = indicators.get('structure_levels', {})
            if structure_levels:
                if direction == 'LONG':
                    # Find next resistance level above current price
                    resistance_levels = [level for level in structure_levels.get('resistances', []) if level > current_price]
                    if resistance_levels:
                        next_resistance = min(resistance_levels)
                        # Use the lower of ATR-based take profit or structure-based take profit
                        take_profit = min(take_profit, next_resistance)
                else:  # SHORT
                    # Find next support level below current price
                    support_levels = [level for level in structure_levels.get('supports', []) if level < current_price]
                    if support_levels:
                        next_support = max(support_levels)
                        # Use the higher of ATR-based take profit or structure-based take profit
                        take_profit = max(take_profit, next_support)
            
            # Validate take profit
            if direction == 'LONG' and take_profit <= current_price:
                logger.warning("Invalid take profit for LONG position")
                return None
            elif direction == 'SHORT' and take_profit >= current_price:
                logger.warning("Invalid take profit for SHORT position")
                return None
                
            return take_profit
            
        except Exception as e:
            logger.error(f"Error calculating take profit: {e}")
            return None
            
    def add_position(
        self,
        symbol: str,
        position_size: float,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        leverage: float,
        direction: str
    ) -> bool:
        """Add a new position to the risk manager."""
        try:
            if symbol in self.positions:
                logger.warning(f"Position already exists for {symbol}")
                return False
                
            params = self.risk_params[self.risk_mode]
            
            # Calculate trailing stop
            trailing_stop = None
            trailing_distance = None
            if params['trailing_stop_pct'] > 0:
                trailing_distance = params['trailing_stop_pct']
                if direction == 'LONG':
                    trailing_stop = entry_price * (1 - trailing_distance)
                else:
                    trailing_stop = entry_price * (1 + trailing_distance)
                
            position = Position(
                symbol=symbol,
                size=position_size,
                entry_price=entry_price,
                current_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                leverage=leverage,
                direction=direction,
                trailing_stop=trailing_stop,
                trailing_distance=trailing_distance
            )
            
            self.positions[symbol] = position
            return True
            
        except Exception as e:
            logger.error(f"Error adding position for {symbol}: {e}")
            return False
            
    def remove_position(self, symbol: str):
        """Remove a position from the risk manager."""
        if symbol in self.positions:
            del self.positions[symbol]
            
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position details for a symbol."""
        return self.positions.get(symbol)
        
    def _check_position_correlation(self, symbol: str, max_correlation: float) -> bool:
        """Check if adding a new position would exceed maximum correlation limit."""
        if not self.positions:
            return True
            
        # In a real implementation, you would calculate actual correlation
        # between the new symbol and existing positions using historical data
        # For now, we'll use a simplified check
        return True
        
    def update_daily_stats(self, pnl: float):
        """Update daily statistics with trade results."""
        self.daily_stats['trades'] += 1
        self.daily_stats['pnl'] += pnl
        
        if pnl > 0:
            self.daily_stats['wins'] += 1
        else:
            self.daily_stats['losses'] += 1
            
        # Update maximum drawdown
        current_drawdown = abs(min(0, self.daily_stats['pnl'])) / self.account_balance
        self.daily_stats['max_drawdown'] = max(self.daily_stats['max_drawdown'], current_drawdown)
        
    def get_risk_metrics(self) -> Dict:
        """Get current risk metrics for the portfolio."""
        try:
            params = self.risk_params[self.risk_mode]
            total_exposure = sum(
                pos.size * pos.entry_price * pos.leverage
                for pos in self.positions.values()
            )
            
            total_risk = sum(
                pos.size * abs(pos.entry_price - pos.stop_loss)
                for pos in self.positions.values()
            )
            
            return {
                'daily_stats': self.daily_stats,
                'total_positions': len(self.positions),
                'total_exposure': total_exposure,
                'exposure_ratio': total_exposure / self.account_balance if self.account_balance > 0 else 0,
                'total_risk': total_risk,
                'risk_ratio': total_risk / self.account_balance if self.account_balance > 0 else 0,
                'max_open_trades': params['max_open_trades'],
                'current_leverage': sum(p.leverage for p in self.positions.values()),
                'max_leverage': params['max_leverage'],
                'daily_loss_limit': self.account_balance * params['max_daily_loss'],
                'max_drawdown': params['max_drawdown'],
                'positions': {
                    symbol: {
                        'size': pos.size,
                        'leverage': pos.leverage,
                        'direction': pos.direction,
                        'entry_price': pos.entry_price,
                        'current_price': pos.current_price,
                        'stop_loss': pos.stop_loss,
                        'take_profit': pos.take_profit,
                        'trailing_stop': pos.trailing_stop
                    }
                    for symbol, pos in self.positions.items()
                }
            }
            
        except Exception as e:
            logger.error(f"Error calculating risk metrics: {e}")
            return {}
            
    def update_account_balance(self, new_balance: float):
        """Update the account balance."""
        self.account_balance = new_balance
        
    def set_risk_mode(self, mode: RiskMode):
        """Change the risk mode."""
        self.risk_mode = mode
        
    def get_risk_parameters(self) -> Dict:
        """Get current risk parameters."""
        return self.risk_params[self.risk_mode]
        
    def check_daily_loss_limit(self, daily_pnl: float) -> bool:
        """Check if daily loss limit has been reached."""
        max_daily_loss = self.account_balance * self.risk_params[self.risk_mode]['max_daily_loss']
        return daily_pnl >= -max_daily_loss 