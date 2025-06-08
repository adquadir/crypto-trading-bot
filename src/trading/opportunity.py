from dataclasses import dataclass
from typing import Dict, Any, Optional

@dataclass
class TradingOpportunity:
    """Trading opportunity data class."""
    symbol: str
    signal_type: str  # 'LONG' or 'SHORT'
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float
    timestamp: int
    regime: str
    mtf_alignment: Optional[Dict[str, Any]] = None
    data_freshness: Optional[Dict[str, int]] = None  # Timestamps of when each data type was last updated
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert opportunity to dictionary.
        
        Returns:
            Dict[str, Any]: Dictionary representation
        """
        return {
            'symbol': self.symbol,
            'signal_type': self.signal_type,
            'entry_price': self.entry_price,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'confidence': self.confidence,
            'timestamp': self.timestamp,
            'regime': self.regime,
            'mtf_alignment': self.mtf_alignment,
            'data_freshness': self.data_freshness
        } 