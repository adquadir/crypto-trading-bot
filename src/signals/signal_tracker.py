from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class SignalProfile:
    """Complete profile of a trading signal."""
    symbol: str
    timestamp: datetime
    market_regime: str
    indicators: Dict
    entry_price: float
    take_profit: float
    stop_loss: float
    risk_reward_ratio: float
    confidence: float
    volume_profile: Dict
    order_book_metrics: Dict
    data_freshness: Dict
    mtf_alignment: Dict
    pattern_alignment: Dict
    technical_alignment: Dict
    volume_alignment: Dict
    rejection_reason: Optional[str] = None
    outcome: Optional[str] = None
    pnl: Optional[float] = None
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    holding_time: Optional[float] = None
    slippage: Optional[float] = None
    execution_quality: Optional[Dict] = None

class SignalTracker:
    """Tracks and logs trading signals for AI model training."""
    
    def __init__(self, log_dir: str = "logs/signals"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.active_signals: Dict[str, SignalProfile] = {}
        self.rejection_stats = {
            'reasons': {},
            'by_regime': {},
            'by_timeframe': {},
            'by_confidence': {}
        }
        
    def log_signal(self, signal: SignalProfile) -> None:
        """Log a new signal or update an existing one."""
        try:
            # Create log entry with enhanced metrics
            log_entry = {
                "symbol": signal.symbol,
                "timestamp": signal.timestamp.isoformat(),
                "market_regime": signal.market_regime,
                "indicators": signal.indicators,
                "entry_price": signal.entry_price,
                "take_profit": signal.take_profit,
                "stop_loss": signal.stop_loss,
                "risk_reward_ratio": signal.risk_reward_ratio,
                "confidence": signal.confidence,
                "volume_profile": signal.volume_profile,
                "order_book_metrics": signal.order_book_metrics,
                "data_freshness": signal.data_freshness,
                "mtf_alignment": signal.mtf_alignment,
                "pattern_alignment": signal.pattern_alignment,
                "technical_alignment": signal.technical_alignment,
                "volume_alignment": signal.volume_alignment,
                "rejection_reason": signal.rejection_reason,
                "outcome": signal.outcome,
                "pnl": signal.pnl,
                "exit_time": signal.exit_time.isoformat() if signal.exit_time else None,
                "exit_price": signal.exit_price,
                "holding_time": signal.holding_time,
                "slippage": signal.slippage,
                "execution_quality": signal.execution_quality
            }
            
            # Save to daily log file
            date_str = signal.timestamp.strftime("%Y-%m-%d")
            log_file = self.log_dir / f"signals_{date_str}.jsonl"
            
            with open(log_file, "a") as f:
                f.write(json.dumps(log_entry) + "\n")
                
            # Store in active signals if not rejected
            if not signal.rejection_reason:
                self.active_signals[signal.symbol] = signal
                
            # Update rejection statistics if rejected
            if signal.rejection_reason:
                self._update_rejection_stats(signal)
                
            logger.info(
                f"Logged signal for {signal.symbol} - "
                f"Regime: {signal.market_regime}, "
                f"Confidence: {signal.confidence:.2f}, "
                f"R/R: {signal.risk_reward_ratio:.2f}, "
                f"MTF: {signal.mtf_alignment.get('strength', 0):.2f}, "
                f"Pattern: {signal.pattern_alignment.get('trend', 'NEUTRAL')}"
            )
                       
        except Exception as e:
            logger.error(f"Error logging signal: {e}")
            
    def _update_rejection_stats(self, signal: SignalProfile) -> None:
        """Update rejection statistics."""
        try:
            # Update reason counts
            reason = signal.rejection_reason
            self.rejection_stats['reasons'][reason] = self.rejection_stats['reasons'].get(reason, 0) + 1
            
            # Update regime stats
            regime = signal.market_regime
            if regime not in self.rejection_stats['by_regime']:
                self.rejection_stats['by_regime'][regime] = {'total': 0, 'rejected': 0}
            self.rejection_stats['by_regime'][regime]['rejected'] += 1
            
            # Update confidence stats
            confidence_bucket = self._get_confidence_bucket(signal.confidence)
            if confidence_bucket not in self.rejection_stats['by_confidence']:
                self.rejection_stats['by_confidence'][confidence_bucket] = {'total': 0, 'rejected': 0}
            self.rejection_stats['by_confidence'][confidence_bucket]['rejected'] += 1
            
            # Log detailed rejection info
            logger.info(
                f"Signal rejected for {signal.symbol}: {reason}\n"
                f"Regime: {regime}, Confidence: {signal.confidence:.2f}\n"
                f"MTF Alignment: {signal.mtf_alignment.get('strength', 0):.2f}\n"
                f"Pattern Alignment: {signal.pattern_alignment.get('trend', 'NEUTRAL')}\n"
                f"Volume Profile: {json.dumps(signal.volume_profile, indent=2)}"
            )
            
        except Exception as e:
            logger.error(f"Error updating rejection stats: {e}")
            
    def _get_confidence_bucket(self, confidence: float) -> str:
        """Get confidence bucket for statistics."""
        if confidence >= 0.8:
            return 'high'
        elif confidence >= 0.6:
            return 'medium'
        elif confidence >= 0.4:
            return 'low'
        else:
            return 'very_low'
            
    def get_rejection_stats(self) -> Dict:
        """Get current rejection statistics."""
        return self.rejection_stats
            
    def update_signal_outcome(self, symbol: str, outcome: str, pnl: Optional[float] = None) -> None:
        """Update the outcome of a signal."""
        try:
            if symbol in self.active_signals:
                signal = self.active_signals[symbol]
                signal.outcome = outcome
                signal.pnl = pnl
                
                # Log the update
                self.log_signal(signal)
                
                # Remove from active signals
                del self.active_signals[symbol]
                
                logger.info(f"Updated outcome for {symbol}: {outcome}, PnL: {pnl}")
                
        except Exception as e:
            logger.error(f"Error updating signal outcome: {e}")
            
    def log_rejection(self, symbol: str, reason: str, signal_data: Dict) -> None:
        """Log a rejected signal with the reason."""
        try:
            signal = SignalProfile(
                symbol=symbol,
                timestamp=datetime.now(),
                market_regime=signal_data.get("market_regime", "unknown"),
                indicators=signal_data.get("indicators", {}),
                entry_price=signal_data.get("entry_price", 0.0),
                take_profit=signal_data.get("take_profit", 0.0),
                stop_loss=signal_data.get("stop_loss", 0.0),
                risk_reward_ratio=signal_data.get("risk_reward_ratio", 0.0),
                confidence=signal_data.get("confidence", 0.0),
                volume_profile=signal_data.get("volume_profile", {}),
                order_book_metrics=signal_data.get("order_book_metrics", {}),
                rejection_reason=reason
            )
            
            self.log_signal(signal)
            logger.info(f"Logged rejection for {symbol}: {reason}")
            
        except Exception as e:
            logger.error(f"Error logging rejection: {e}")
            
    def get_active_signals(self) -> List[SignalProfile]:
        """Get list of currently active signals."""
        return list(self.active_signals.values())
        
    def get_signal_history(self, days: int = 7) -> List[Dict]:
        """Get signal history for the specified number of days."""
        history = []
        try:
            for i in range(days):
                date = datetime.now().date() - timedelta(days=i)
                log_file = self.log_dir / f"signals_{date.strftime('%Y-%m-%d')}.jsonl"
                
                if log_file.exists():
                    with open(log_file, "r") as f:
                        for line in f:
                            history.append(json.loads(line))
                            
        except Exception as e:
            logger.error(f"Error getting signal history: {e}")
            
        return history 