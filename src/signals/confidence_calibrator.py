import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import json
import os
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

@dataclass
class TradeOutcome:
    """Trade outcome data class."""
    symbol: str
    entry_time: int
    exit_time: int
    entry_price: float
    exit_price: float
    signal_type: str
    raw_confidence: float
    regime: str
    mtf_alignment: Optional[Dict[str, Any]]
    pnl: float
    win: bool

class ConfidenceCalibrator:
    """Calibrates signal confidence scores based on historical trade outcomes."""
    
    def __init__(self, history_file: str = "data/trade_history.json"):
        """Initialize confidence calibrator.
        
        Args:
            history_file: Path to trade history JSON file
        """
        self.history_file = history_file
        self.trade_history: List[TradeOutcome] = []
        self.confidence_buckets: Dict[str, Dict[str, float]] = {
            'trending': {},
            'ranging': {},
            'volatile': {}
        }
        self.min_trades_per_bucket = 10
        self.bucket_size = 0.1  # 10% confidence intervals
        self.load_history()
        
    def load_history(self) -> None:
        """Load trade history from file."""
        try:
            if not os.path.exists(self.history_file):
                logger.warning(f"Trade history file not found: {self.history_file}")
                return
                
            with open(self.history_file, 'r') as f:
                data = json.load(f)
                
            self.trade_history = [
                TradeOutcome(
                    symbol=trade['symbol'],
                    entry_time=trade['entry_time'],
                    exit_time=trade['exit_time'],
                    entry_price=trade['entry_price'],
                    exit_price=trade['exit_price'],
                    signal_type=trade['signal_type'],
                    raw_confidence=trade['raw_confidence'],
                    regime=trade['regime'],
                    mtf_alignment=trade.get('mtf_alignment'),
                    pnl=trade['pnl'],
                    win=trade['win']
                )
                for trade in data
            ]
            
            self._calibrate_confidence()
            
        except Exception as e:
            logger.error(f"Error loading trade history: {str(e)}")
            
    def _calibrate_confidence(self) -> None:
        """Calibrate confidence scores based on historical outcomes."""
        try:
            # Group trades by regime
            trades_by_regime = {
                'trending': [],
                'ranging': [],
                'volatile': []
            }
            
            for trade in self.trade_history:
                if trade.regime in trades_by_regime:
                    trades_by_regime[trade.regime].append(trade)
            
            # Calculate win rates for each confidence bucket in each regime
            for regime, trades in trades_by_regime.items():
                if not trades:
                    continue
                    
                # Create confidence buckets
                buckets = {}
                for trade in trades:
                    bucket = round(trade.raw_confidence / self.bucket_size) * self.bucket_size
                    if bucket not in buckets:
                        buckets[bucket] = {'wins': 0, 'total': 0}
                    buckets[bucket]['total'] += 1
                    if trade.win:
                        buckets[bucket]['wins'] += 1
                
                # Calculate win rates and store in regime buckets
                for bucket, stats in buckets.items():
                    if stats['total'] >= self.min_trades_per_bucket:
                        win_rate = stats['wins'] / stats['total']
                        self.confidence_buckets[regime][bucket] = win_rate
                        
            logger.info("Confidence calibration completed")
            
        except Exception as e:
            logger.error(f"Error calibrating confidence: {str(e)}")
            
    def calibrate_confidence(
        self,
        raw_confidence: float,
        regime: str,
        mtf_alignment: Optional[Dict[str, Any]] = None
    ) -> float:
        """Calibrate raw confidence score based on historical outcomes.
        
        Args:
            raw_confidence: Raw confidence score (0-1)
            regime: Market regime ('trending', 'ranging', 'volatile')
            mtf_alignment: Optional MTF alignment data
            
        Returns:
            float: Calibrated confidence score (0-1)
        """
        try:
            if regime not in self.confidence_buckets:
                return raw_confidence
                
            # Find nearest confidence bucket
            bucket = round(raw_confidence / self.bucket_size) * self.bucket_size
            if bucket not in self.confidence_buckets[regime]:
                return raw_confidence
                
            # Get historical win rate for this bucket
            win_rate = self.confidence_buckets[regime][bucket]
            
            # Adjust confidence based on MTF alignment if available
            if mtf_alignment and mtf_alignment.get('strength'):
                alignment_strength = mtf_alignment['strength']
                # Boost confidence by up to 20% based on alignment strength
                win_rate *= (1 + 0.2 * alignment_strength)
            
            # Ensure confidence stays within bounds
            return max(0.0, min(1.0, win_rate))
            
        except Exception as e:
            logger.error(f"Error calibrating confidence: {str(e)}")
            return raw_confidence
            
    def add_trade_outcome(self, trade: TradeOutcome) -> None:
        """Add a new trade outcome to history and update calibration.
        
        Args:
            trade: Trade outcome to add
        """
        try:
            self.trade_history.append(trade)
            
            # Save to file
            with open(self.history_file, 'w') as f:
                json.dump([vars(t) for t in self.trade_history], f, indent=2)
            
            # Recalibrate
            self._calibrate_confidence()
            
        except Exception as e:
            logger.error(f"Error adding trade outcome: {str(e)}")
            
    def get_confidence_stats(self) -> Dict[str, Dict[str, float]]:
        """Get confidence calibration statistics.
        
        Returns:
            Dict[str, Dict[str, float]]: Confidence statistics by regime
        """
        return self.confidence_buckets 