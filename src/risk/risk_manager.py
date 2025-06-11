import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class RiskManager:
    """Manages trading risk and position sizing."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the risk manager."""
        self.config = config
        self.max_drawdown = float(config['risk']['max_drawdown'])
        self.max_leverage = float(config['risk']['max_leverage'])
        self.position_size_limit = float(config['risk']['position_size_limit'])
        self.daily_loss_limit = float(config['risk']['daily_loss_limit'])
        self.initial_balance = float(config['risk'].get('initial_balance', 1000.0))
        
        # Risk tracking
        self.daily_pnl = 0.0
        self.max_drawdown_seen = 0.0
        self.last_balance_update = datetime.now()
        
    async def initialize(self):
        """Initialize the risk manager."""
        try:
            # Perform any necessary setup or validation here
            logger.info("Risk manager initialized")
        except Exception as e:
            logger.error(f"Error initializing risk manager: {e}")
            raise
        
    def check_risk_limits(self, symbol: str, market_data: Dict[str, Any]) -> bool:
        """Check if a trade would exceed risk limits."""
        try:
            # Check daily loss limit
            if not self._check_daily_loss_limit():
                logger.warning("Daily loss limit exceeded")
                return False
                
            # Check drawdown
            if not self._check_drawdown():
                logger.warning("Maximum drawdown exceeded")
                return False
                
            # Check leverage
            if not self._check_leverage(market_data):
                logger.warning("Maximum leverage exceeded")
                return False
                
            # Check position size
            if not self._check_position_size(market_data):
                logger.warning("Position size limit exceeded")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error checking risk limits: {e}")
            return False
            
    def can_open_trade(self, symbol: str, market_data: Dict[str, Any]) -> bool:
        """Check if a new trade can be opened."""
        try:
            # Check risk limits
            if not self.check_risk_limits(symbol, market_data):
                return False
                
            # Check volatility
            volatility = market_data.get('volatility', 0)
            if volatility > self.config['trading']['max_volatility']:
                logger.warning(f"Volatility too high for {symbol}: {volatility}")
                return False
                
            # Check spread
            spread = market_data.get('spread', 0)
            if spread > self.config['trading']['max_spread']:
                logger.warning(f"Spread too high for {symbol}: {spread}")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error checking if trade can be opened: {e}")
            return False
            
    def calculate_position_size(self, symbol: str, balance: float, risk_per_trade: float) -> float:
        """Calculate position size based on risk parameters."""
        try:
            # Get base position size from risk per trade
            base_size = balance * (risk_per_trade / 100.0)
            
            # Apply position size limit
            max_size = min(base_size, self.position_size_limit)
            
            # Apply leverage limit
            max_size = max_size / self.max_leverage
            
            return max_size
            
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return 0.0
            
    def _check_daily_loss_limit(self) -> bool:
        """Check if daily loss limit has been exceeded."""
        try:
            # Reset daily PnL if it's a new day
            if datetime.now().date() > self.last_balance_update.date():
                self.daily_pnl = 0.0
                self.last_balance_update = datetime.now()
                
            return self.daily_pnl >= -self.daily_loss_limit
            
        except Exception as e:
            logger.error(f"Error checking daily loss limit: {e}")
            return False
            
    def _check_drawdown(self) -> bool:
        """Check if maximum drawdown has been exceeded."""
        try:
            current_drawdown = abs(self.daily_pnl / self.initial_balance)
            self.max_drawdown_seen = max(self.max_drawdown_seen, current_drawdown)
            return self.max_drawdown_seen <= self.max_drawdown
            
        except Exception as e:
            logger.error(f"Error checking drawdown: {e}")
            return False
            
    def _check_leverage(self, market_data: Dict[str, Any]) -> bool:
        """Check if leverage is within limits."""
        try:
            leverage = float(market_data.get('leverage', 1.0))
            return leverage <= self.max_leverage
            
        except Exception as e:
            logger.error(f"Error checking leverage: {e}")
            return False
            
    def _check_position_size(self, market_data: Dict[str, Any]) -> bool:
        """Check if position size is within limits."""
        try:
            position_size = float(market_data.get('position_size', 0.0))
            return position_size <= self.position_size_limit
            
        except Exception as e:
            logger.error(f"Error checking position size: {e}")
            return False
            
    def update_pnl(self, pnl: float) -> None:
        """Update the daily PnL."""
        try:
            self.daily_pnl += pnl
            self.last_balance_update = datetime.now()
        except Exception as e:
            logger.error(f"Error updating PnL: {e}") 