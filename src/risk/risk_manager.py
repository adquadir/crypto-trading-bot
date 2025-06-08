import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class RiskManager:
    """Manages trading risk and position sizing."""
    
    def __init__(self):
        self.max_position_size = 0.1  # Default to 10% of portfolio
        self.max_leverage = 3.0
        self.max_drawdown = 0.1  # 10% max drawdown
        self.risk_per_trade = 0.01  # 1% risk per trade
        self.max_daily_loss = 0.02  # 2% max daily loss
        self.min_risk_reward = 2.0  # Minimum 2:1 reward-to-risk ratio
        self.position_history = []
        self.daily_pnl = 0.0
        self.last_reset = datetime.now()
    
    def can_open_trade(self, symbol: str, risk_limits: Dict[str, Any]) -> bool:
        """Check if a new trade can be opened based on risk parameters.
        
        Args:
            symbol: Trading pair symbol
            risk_limits: Dictionary of risk limits from strategy config
            
        Returns:
            bool: True if trade can be opened, False otherwise
        """
        try:
            # Reset daily PnL if it's a new day
            self._reset_daily_pnl_if_needed()
            
            # Check if we've exceeded daily loss limit
            if self.daily_pnl <= -self.max_daily_loss:
                logger.warning("Daily loss limit reached")
                return False
            
            # Check if we've exceeded max drawdown
            if self._calculate_drawdown() >= self.max_drawdown:
                logger.warning("Maximum drawdown reached")
                return False
            
            # Check if we've exceeded max position size
            current_exposure = self._calculate_current_exposure()
            if current_exposure >= self.max_position_size:
                logger.warning("Maximum position size reached")
                return False
            
            # Check if we've exceeded max leverage
            if risk_limits.get('leverage', 1.0) > self.max_leverage:
                logger.warning("Maximum leverage exceeded")
                return False
            
            # Check if risk/reward ratio is sufficient
            if risk_limits.get('risk_reward_ratio', 0.0) < self.min_risk_reward:
                logger.warning("Insufficient risk/reward ratio")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking trade eligibility: {str(e)}")
            return False
    
    def update_position_history(self, position: Dict[str, Any]) -> None:
        """Update position history with new trade.
        
        Args:
            position: Dictionary containing position details
        """
        self.position_history.append({
            'symbol': position['symbol'],
            'size': position['size'],
            'entry_price': position['entry_price'],
            'timestamp': datetime.now(),
            'pnl': position.get('pnl', 0.0)
        })
        
        # Update daily PnL
        self.daily_pnl += position.get('pnl', 0.0)
    
    def _reset_daily_pnl_if_needed(self) -> None:
        """Reset daily PnL if it's a new day."""
        now = datetime.now()
        if now.date() > self.last_reset.date():
            self.daily_pnl = 0.0
            self.last_reset = now
    
    def _calculate_drawdown(self) -> float:
        """Calculate current drawdown.
        
        Returns:
            float: Current drawdown as a percentage
        """
        if not self.position_history:
            return 0.0
        
        peak_value = max(p['pnl'] for p in self.position_history)
        current_value = sum(p['pnl'] for p in self.position_history)
        
        if peak_value == 0:
            return 0.0
        
        return (peak_value - current_value) / peak_value
    
    def _calculate_current_exposure(self) -> float:
        """Calculate current total exposure.
        
        Returns:
            float: Current exposure as a percentage of portfolio
        """
        if not self.position_history:
            return 0.0
        
        return sum(p['size'] for p in self.position_history)
    
    def get_risk_metrics(self) -> Dict[str, Any]:
        """Get current risk metrics.
        
        Returns:
            Dict[str, Any]: Dictionary containing risk metrics
        """
        return {
            'daily_pnl': self.daily_pnl,
            'drawdown': self._calculate_drawdown(),
            'current_exposure': self._calculate_current_exposure(),
            'position_count': len(self.position_history),
            'max_position_size': self.max_position_size,
            'max_leverage': self.max_leverage,
            'max_drawdown': self.max_drawdown,
            'risk_per_trade': self.risk_per_trade,
            'max_daily_loss': self.max_daily_loss,
            'min_risk_reward': self.min_risk_reward
        } 