from typing import Dict, Optional
import logging
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)

class RiskMode(Enum):
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"

class RiskManager:
    def __init__(self, account_balance: float, risk_mode: RiskMode = RiskMode.BALANCED):
        self.account_balance = account_balance
        self.risk_mode = risk_mode
        self.positions = {}
        
        # Risk parameters based on mode
        self.risk_params = {
            RiskMode.CONSERVATIVE: {
                'max_position_size': 0.05,  # 5% of account
                'max_leverage': 5,
                'stop_loss_pct': 0.02,  # 2%
                'take_profit_pct': 0.04,  # 4%
                'max_daily_loss': 0.02  # 2%
            },
            RiskMode.BALANCED: {
                'max_position_size': 0.1,  # 10% of account
                'max_leverage': 10,
                'stop_loss_pct': 0.03,  # 3%
                'take_profit_pct': 0.06,  # 6%
                'max_daily_loss': 0.05  # 5%
            },
            RiskMode.AGGRESSIVE: {
                'max_position_size': 0.2,  # 20% of account
                'max_leverage': 20,
                'stop_loss_pct': 0.05,  # 5%
                'take_profit_pct': 0.1,  # 10%
                'max_daily_loss': 0.1  # 10%
            }
        }
        
    def calculate_position_size(self, signal: Dict) -> Optional[Dict]:
        """Calculate position size and risk parameters for a signal."""
        try:
            params = self.risk_params[self.risk_mode]
            current_price = signal['price']
            
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
            else:  # SHORT
                stop_loss = current_price * (1 + params['stop_loss_pct'])
                take_profit = current_price * (1 - params['take_profit_pct'])
                
            # Calculate liquidation price
            liquidation_price = self._calculate_liquidation_price(
                current_price,
                stop_loss,
                suggested_leverage,
                signal['direction']
            )
            
            return {
                'timestamp': datetime.now().timestamp(),
                'symbol': signal['symbol'],
                'direction': signal['direction'],
                'entry_price': current_price,
                'position_size': position_value,
                'leverage': suggested_leverage,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'liquidation_price': liquidation_price,
                'risk_reward_ratio': params['take_profit_pct'] / params['stop_loss_pct'],
                'max_loss_amount': position_value * params['stop_loss_pct'],
                'max_profit_amount': position_value * params['take_profit_pct']
            }
            
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return None
            
    def _calculate_liquidation_price(
        self,
        entry_price: float,
        stop_loss: float,
        leverage: int,
        direction: str
    ) -> float:
        """Calculate liquidation price based on entry, stop loss, and leverage."""
        try:
            # Simplified liquidation calculation
            # In practice, you'd want to use exchange-specific formulas
            if direction == 'LONG':
                return entry_price * (1 - (1 / leverage))
            else:  # SHORT
                return entry_price * (1 + (1 / leverage))
        except Exception as e:
            logger.error(f"Error calculating liquidation price: {e}")
            return 0.0
            
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