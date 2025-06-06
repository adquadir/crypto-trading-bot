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
        
    def calculate_position_size(
        self,
        symbol: str,
        entry_price: float,
        direction: str,
        market_state: Dict,
        signal_confidence: float = 1.0
    ) -> Tuple[float, float]:
        """
        Calculate position size and leverage based on risk parameters.
        Returns (position_size, leverage)
        """
        try:
            self.reset_daily_stats()
            params = self.risk_params[self.risk_mode]
            
            # Check daily loss limit
            if abs(self.daily_stats['pnl']) >= self.account_balance * params['max_daily_loss']:
                logger.warning("Daily loss limit reached")
                return 0.0, 1.0
                
            # Check maximum drawdown
            if self.daily_stats['max_drawdown'] >= params['max_drawdown']:
                logger.warning("Maximum drawdown reached")
                return 0.0, 1.0
                
            # Check maximum open trades
            if len(self.positions) >= params['max_open_trades']:
                logger.warning("Maximum open trades reached")
                return 0.0, 1.0
                
            # Calculate base position size
            position_value = self.account_balance * params['max_position_size']
            
            # Adjust for signal confidence
            position_value *= signal_confidence
            
            # Calculate leverage based on volatility
            atr = market_state.get('indicators', {}).get('atr', 0)
            if atr > 0:
                # Adjust leverage based on volatility (lower leverage for higher volatility)
                volatility_factor = min(1.0, 0.02 / atr)  # Normalize ATR to 2% of price
                leverage = min(
                    params['max_leverage'],
                    params['max_leverage'] * volatility_factor
                )
            else:
                leverage = 1.0
                
            # Adjust position size for leverage
            position_size = (position_value * leverage) / entry_price
            
            # Check position correlation
            if not self._check_position_correlation(symbol, params['max_correlation']):
                logger.warning(f"Position correlation too high for {symbol}")
                return 0.0, 1.0
                
            return position_size, leverage
            
        except Exception as e:
            logger.error(f"Error calculating position size for {symbol}: {e}")
            return 0.0, 1.0
            
    def calculate_stop_loss(
        self,
        symbol: str,
        entry_price: float,
        direction: str,
        market_state: Dict
    ) -> float:
        """Calculate stop loss level based on market conditions."""
        try:
            params = self.risk_params[self.risk_mode]
            indicators = market_state.get('indicators', {})
            
            # Get ATR for volatility-based stop loss
            atr = indicators.get('atr', 0)
            if atr == 0:
                # Fallback to percentage-based stop loss
                return entry_price * (1 - params['stop_loss_pct'] if direction == 'LONG' else 1 + params['stop_loss_pct'])
                
            # Calculate stop loss based on ATR
            if direction == 'LONG':
                stop_loss = entry_price - (2 * atr)  # 2 ATR below entry
            else:
                stop_loss = entry_price + (2 * atr)  # 2 ATR above entry
                
            # Ensure stop loss is not too close to entry
            min_distance = entry_price * params['stop_loss_pct']
            if abs(stop_loss - entry_price) < min_distance:
                stop_loss = entry_price * (1 - params['stop_loss_pct'] if direction == 'LONG' else 1 + params['stop_loss_pct'])
                
            return stop_loss
            
        except Exception as e:
            logger.error(f"Error calculating stop loss for {symbol}: {e}")
            return entry_price * (0.98 if direction == 'LONG' else 1.02)
            
    def calculate_take_profit(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        direction: str,
        market_state: Dict
    ) -> float:
        """Calculate take profit level based on risk:reward ratio."""
        try:
            params = self.risk_params[self.risk_mode]
            
            # Calculate risk amount
            risk = abs(entry_price - stop_loss)
            
            # Calculate take profit based on minimum risk:reward ratio
            reward = risk * (params['take_profit_pct'] / params['stop_loss_pct'])
            
            if direction == 'LONG':
                take_profit = entry_price + reward
            else:
                take_profit = entry_price - reward
                
            return take_profit
            
        except Exception as e:
            logger.error(f"Error calculating take profit for {symbol}: {e}")
            return entry_price * (1.02 if direction == 'LONG' else 0.98)
            
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