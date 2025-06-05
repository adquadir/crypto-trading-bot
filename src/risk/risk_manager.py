from typing import Dict, List, Optional
from enum import Enum
import logging
from datetime import datetime, timedelta
import numpy as np
from dataclasses import dataclass

logger = logging.getLogger(__name__)

class RiskMode(Enum):
    CONSERVATIVE = 'conservative'
    BALANCED = 'balanced'
    AGGRESSIVE = 'aggressive'

@dataclass
class Position:
    symbol: str
    entry_price: float
    current_price: float
    size: float
    leverage: float
    direction: str  # 'LONG' or 'SHORT'
    stop_loss: float
    take_profit: float
    trailing_stop: Optional[float] = None
    trailing_distance: Optional[float] = None
    entry_time: datetime = datetime.now()

class RiskManager:
    def __init__(self, account_balance: float, risk_mode: RiskMode = RiskMode.BALANCED):
        self.account_balance = account_balance
        self.risk_mode = risk_mode
        self.positions: List[Position] = []
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
        for position in self.positions:
            if position.symbol == symbol:
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
        for position in self.positions:
            if position.symbol == symbol:
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
        
    def calculate_position_size(self, signal: Dict) -> Optional[Dict]:
        """Calculate position size and risk parameters for a signal."""
        try:
            self.reset_daily_stats()
            params = self.risk_params[self.risk_mode]
            current_price = signal['price']
            
            # Check daily loss limit
            if abs(self.daily_stats['pnl']) >= self.account_balance * params['max_daily_loss']:
                logger.warning("Daily loss limit reached")
                return None
                
            # Check maximum drawdown
            if self.daily_stats['max_drawdown'] >= params['max_drawdown']:
                logger.warning("Maximum drawdown reached")
                return None
                
            # Check maximum open trades
            if len(self.positions) >= params['max_open_trades']:
                logger.warning("Maximum open trades reached")
                return None
                
            # Calculate base position size
            position_value = self.account_balance * params['max_position_size']
            
            # Adjust for signal confidence
            confidence_multiplier = signal['confidence']
            position_value *= confidence_multiplier
            
            # Calculate leverage (capped by max_leverage)
            suggested_leverage = min(
                params['max_leverage'],
                int(position_value / (self.account_balance * 0.1))  # Max 10% margin per position
            )
            
            # Calculate stop loss and take profit levels
            if signal['direction'] == 'LONG':
                stop_loss = current_price * (1 - params['stop_loss_pct'])
                take_profit = current_price * (1 + params['take_profit_pct'])
                trailing_stop = current_price * (1 - params['trailing_stop_pct'])
            else:  # SHORT
                stop_loss = current_price * (1 + params['stop_loss_pct'])
                take_profit = current_price * (1 - params['take_profit_pct'])
                trailing_stop = current_price * (1 + params['trailing_stop_pct'])
                
            # Calculate liquidation price
            liquidation_price = self._calculate_liquidation_price(
                current_price,
                stop_loss,
                suggested_leverage,
                signal['direction']
            )
            
            # Check position correlation
            if not self._check_position_correlation(signal['symbol'], params['max_correlation']):
                logger.warning(f"Position correlation too high for {signal['symbol']}")
                return None
            
            return {
                'position_size': position_value,
                'leverage': suggested_leverage,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'trailing_stop': trailing_stop,
                'trailing_distance': params['trailing_stop_pct'],
                'liquidation_price': liquidation_price
            }
            
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return None
            
    def _calculate_liquidation_price(self, entry_price: float, stop_loss: float, leverage: float, direction: str) -> float:
        """Calculate liquidation price based on leverage and stop loss."""
        try:
            margin = entry_price / leverage
            if direction == 'LONG':
                return entry_price - margin
            else:  # SHORT
                return entry_price + margin
        except Exception as e:
            logger.error(f"Error calculating liquidation price: {e}")
            return 0.0
            
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
        """Get current risk metrics."""
        return {
            'daily_stats': self.daily_stats,
            'open_positions': len(self.positions),
            'max_open_trades': self.risk_params[self.risk_mode]['max_open_trades'],
            'current_leverage': sum(p.leverage for p in self.positions),
            'max_leverage': self.risk_params[self.risk_mode]['max_leverage'],
            'daily_loss_limit': self.account_balance * self.risk_params[self.risk_mode]['max_daily_loss'],
            'max_drawdown': self.risk_params[self.risk_mode]['max_drawdown']
        }
        
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