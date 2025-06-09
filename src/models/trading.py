from dataclasses import dataclass, field
from typing import Dict, List

@dataclass
class TradingOpportunity:
    """Represents a trading opportunity with its characteristics."""
    symbol: str
    direction: str  # 'LONG' or 'SHORT'
    entry_price: float
    take_profit: float
    stop_loss: float
    confidence: float
    leverage: float
    risk_reward: float
    volume_24h: float
    volatility: float
    score: float
    indicators: Dict = field(default_factory=dict)
    reasoning: List[str] = field(default_factory=list)
    # Market metrics
    book_depth: float = 0.0  # Average depth within 0.25%
    oi_trend: float = 0.0  # Open interest trend over past 10 minutes
    volume_trend: float = 0.0  # Volume trend over past 10 minutes
    slippage: float = 0.0  # Estimated slippage for 0.1 BTC order
    data_freshness: float = 0.0  # Time since last data update in seconds 