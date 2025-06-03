from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime
import numpy as np
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class Position:
    symbol: str
    size: float
    entry_price: float
    stop_loss: float
    take_profit: float
    leverage: float
    direction: str  # 'LONG' or 'SHORT'
    timestamp: float

class RiskManager:
    def __init__(
        self,
        max_position_size: float = 0.1,  # Maximum position size as fraction of portfolio
        max_leverage: float = 3.0,       # Maximum allowed leverage
        risk_per_trade: float = 0.02,    # Risk per trade as fraction of portfolio
        max_open_trades: int = 5,        # Maximum number of open trades
        max_correlation: float = 0.7,    # Maximum correlation between positions
        min_risk_reward: float = 2.0     # Minimum risk:reward ratio
    ):
        self.max_position_size = max_position_size
        self.max_leverage = max_leverage
        self.risk_per_trade = risk_per_trade
        self.max_open_trades = max_open_trades
        self.max_correlation = max_correlation
        self.min_risk_reward = min_risk_reward
        self.positions: Dict[str, Position] = {}  # symbol -> Position
        self.portfolio_value = 0.0
        
    def update_portfolio_value(self, value: float):
        """Update the current portfolio value."""
        self.portfolio_value = value
        
    def calculate_position_size(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        direction: str,
        market_state: Dict
    ) -> Tuple[float, float]:
        """
        Calculate position size and leverage based on risk parameters.
        Returns (position_size, leverage)
        """
        try:
            # Calculate risk amount in base currency
            risk_amount = self.portfolio_value * self.risk_per_trade
            
            # Calculate price risk
            price_risk = abs(entry_price - stop_loss)
            if price_risk == 0:
                logger.warning(f"Invalid stop loss for {symbol}: same as entry price")
                return 0.0, 1.0
                
            # Calculate base position size
            position_size = risk_amount / price_risk
            
            # Calculate leverage based on volatility
            atr = market_state.get('indicators', {}).get('atr', 0)
            if atr > 0:
                # Adjust leverage based on volatility (lower leverage for higher volatility)
                volatility_factor = min(1.0, 0.02 / atr)  # Normalize ATR to 2% of price
                leverage = min(
                    self.max_leverage,
                    self.max_leverage * volatility_factor
                )
            else:
                leverage = 1.0
                
            # Adjust position size for leverage
            position_size *= leverage
            
            # Check maximum position size
            max_size = self.portfolio_value * self.max_position_size
            if position_size * entry_price > max_size:
                position_size = max_size / entry_price
                
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
            indicators = market_state.get('indicators', {})
            
            # Get ATR for volatility-based stop loss
            atr = indicators.get('atr', 0)
            if atr == 0:
                # Fallback to percentage-based stop loss
                return entry_price * (0.98 if direction == 'LONG' else 1.02)
                
            # Calculate stop loss based on ATR
            if direction == 'LONG':
                stop_loss = entry_price - (2 * atr)  # 2 ATR below entry
            else:
                stop_loss = entry_price + (2 * atr)  # 2 ATR above entry
                
            # Ensure stop loss is not too close to entry
            min_distance = entry_price * 0.01  # Minimum 1% distance
            if abs(stop_loss - entry_price) < min_distance:
                stop_loss = entry_price * (0.99 if direction == 'LONG' else 1.01)
                
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
            # Calculate risk amount
            risk = abs(entry_price - stop_loss)
            
            # Calculate take profit based on minimum risk:reward ratio
            reward = risk * self.min_risk_reward
            
            if direction == 'LONG':
                take_profit = entry_price + reward
            else:
                take_profit = entry_price - reward
                
            return take_profit
            
        except Exception as e:
            logger.error(f"Error calculating take profit for {symbol}: {e}")
            return entry_price * (1.02 if direction == 'LONG' else 0.98)
            
    def check_risk_limits(self, symbol: str, position_size: float, leverage: float) -> bool:
        """Check if the proposed position meets risk limits."""
        try:
            # Check number of open positions
            if len(self.positions) >= self.max_open_trades:
                logger.warning(f"Maximum number of open trades reached ({self.max_open_trades})")
                return False
                
            # Check position size
            if position_size * leverage > self.portfolio_value * self.max_position_size:
                logger.warning(f"Position size exceeds maximum allowed ({self.max_position_size * 100}% of portfolio)")
                return False
                
            # Check leverage
            if leverage > self.max_leverage:
                logger.warning(f"Leverage exceeds maximum allowed ({self.max_leverage}x)")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error checking risk limits for {symbol}: {e}")
            return False
            
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
                
            position = Position(
                symbol=symbol,
                size=position_size,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                leverage=leverage,
                direction=direction,
                timestamp=datetime.now().timestamp()
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
        
    def get_risk_metrics(self) -> Dict:
        """Get current risk metrics for the portfolio."""
        try:
            total_exposure = sum(
                pos.size * pos.entry_price * pos.leverage
                for pos in self.positions.values()
            )
            
            total_risk = sum(
                pos.size * abs(pos.entry_price - pos.stop_loss)
                for pos in self.positions.values()
            )
            
            return {
                'total_positions': len(self.positions),
                'total_exposure': total_exposure,
                'exposure_ratio': total_exposure / self.portfolio_value if self.portfolio_value > 0 else 0,
                'total_risk': total_risk,
                'risk_ratio': total_risk / self.portfolio_value if self.portfolio_value > 0 else 0,
                'positions': {
                    symbol: {
                        'size': pos.size,
                        'leverage': pos.leverage,
                        'direction': pos.direction,
                        'entry_price': pos.entry_price,
                        'stop_loss': pos.stop_loss,
                        'take_profit': pos.take_profit
                    }
                    for symbol, pos in self.positions.items()
                }
            }
            
        except Exception as e:
            logger.error(f"Error calculating risk metrics: {e}")
            return {} 