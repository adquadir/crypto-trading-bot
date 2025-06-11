from dataclasses import dataclass, field
from typing import Dict, List

@dataclass
class PerformanceMetrics:
    """Represents performance metrics for a trading strategy."""
    total_trades: int
    win_rate: float
    total_pnl: float
    sharpe_ratio: float
    max_drawdown: float
    avg_trade: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    metrics: Dict = field(default_factory=dict)
    reasoning: List[str] = field(default_factory=list) 