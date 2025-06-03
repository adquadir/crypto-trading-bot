from typing import Dict, List, Optional
import logging
from datetime import datetime
import numpy as np
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class Strategy(ABC):
    """Base class for trading strategies."""
    
    @abstractmethod
    def generate_signal(self, market_state: Dict) -> Optional[Dict]:
        """Generate trading signal based on market state."""
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Get strategy name."""
        pass

class MACDStrategy(Strategy):
    def __init__(self, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
        
    def get_name(self) -> str:
        return "MACD"
        
    def generate_signal(self, market_state: Dict) -> Optional[Dict]:
        try:
            indicators = market_state.get('indicators', {})
            if not indicators:
                return None
                
            macd = indicators.get('macd', 0)
            macd_signal = indicators.get('macd_signal', 0)
            macd_diff = indicators.get('macd_diff', 0)
            
            # Generate signal based on MACD crossover
            if macd_diff > 0 and macd > macd_signal:
                return {
                    'signal_type': 'LONG',
                    'confidence': min(abs(macd_diff) / 2, 1.0),  # Normalize confidence
                    'price': market_state['price'],
                    'indicators': {
                        'macd': macd,
                        'macd_signal': macd_signal,
                        'macd_diff': macd_diff
                    }
                }
            elif macd_diff < 0 and macd < macd_signal:
                return {
                    'signal_type': 'SHORT',
                    'confidence': min(abs(macd_diff) / 2, 1.0),
                    'price': market_state['price'],
                    'indicators': {
                        'macd': macd,
                        'macd_signal': macd_signal,
                        'macd_diff': macd_diff
                    }
                }
            return None
            
        except Exception as e:
            logger.error(f"Error generating MACD signal: {e}")
            return None

class RSIStrategy(Strategy):
    def __init__(self, overbought: float = 70, oversold: float = 30):
        self.overbought = overbought
        self.oversold = oversold
        
    def get_name(self) -> str:
        return "RSI"
        
    def generate_signal(self, market_state: Dict) -> Optional[Dict]:
        try:
            indicators = market_state.get('indicators', {})
            if not indicators:
                return None
                
            rsi = indicators.get('rsi', 50)
            
            # Generate signal based on RSI levels
            if rsi < self.oversold:
                confidence = (self.oversold - rsi) / self.oversold
                return {
                    'signal_type': 'LONG',
                    'confidence': confidence,
                    'price': market_state['price'],
                    'indicators': {'rsi': rsi}
                }
            elif rsi > self.overbought:
                confidence = (rsi - self.overbought) / (100 - self.overbought)
                return {
                    'signal_type': 'SHORT',
                    'confidence': confidence,
                    'price': market_state['price'],
                    'indicators': {'rsi': rsi}
                }
            return None
            
        except Exception as e:
            logger.error(f"Error generating RSI signal: {e}")
            return None

class BollingerBandsStrategy(Strategy):
    def __init__(self, std_dev: float = 2.0):
        self.std_dev = std_dev
        
    def get_name(self) -> str:
        return "BollingerBands"
        
    def generate_signal(self, market_state: Dict) -> Optional[Dict]:
        try:
            indicators = market_state.get('indicators', {})
            if not indicators:
                return None
                
            price = market_state['price']
            bb_high = indicators.get('bb_high', price)
            bb_low = indicators.get('bb_low', price)
            bb_mid = indicators.get('bb_mid', price)
            
            # Calculate distance from middle band
            distance = (price - bb_mid) / (bb_high - bb_mid)
            
            # Generate signal based on price position relative to bands
            if price < bb_low:
                confidence = min((bb_mid - price) / (bb_mid - bb_low), 1.0)
                return {
                    'signal_type': 'LONG',
                    'confidence': confidence,
                    'price': price,
                    'indicators': {
                        'bb_high': bb_high,
                        'bb_low': bb_low,
                        'bb_mid': bb_mid
                    }
                }
            elif price > bb_high:
                confidence = min((price - bb_mid) / (bb_high - bb_mid), 1.0)
                return {
                    'signal_type': 'SHORT',
                    'confidence': confidence,
                    'price': price,
                    'indicators': {
                        'bb_high': bb_high,
                        'bb_low': bb_low,
                        'bb_mid': bb_mid
                    }
                }
            return None
            
        except Exception as e:
            logger.error(f"Error generating Bollinger Bands signal: {e}")
            return None

class SignalEngine:
    def __init__(self):
        self.strategies = [
            MACDStrategy(),
            RSIStrategy(),
            BollingerBandsStrategy()
        ]
        
    def generate_signals(self, market_state: Dict) -> List[Dict]:
        """Generate trading signals from all strategies."""
        signals = []
        
        for strategy in self.strategies:
            try:
                signal = strategy.generate_signal(market_state)
                if signal:
                    signal['strategy'] = strategy.get_name()
                    signal['timestamp'] = datetime.now().timestamp()
                    signals.append(signal)
            except Exception as e:
                logger.error(f"Error generating signal for {strategy.get_name()}: {e}")
                
        return signals
        
    def get_combined_signal(self, market_state: Dict) -> Optional[Dict]:
        """Get a combined signal from all strategies."""
        signals = self.generate_signals(market_state)
        if not signals:
            return None
            
        # Calculate weighted average of signals
        long_signals = [s for s in signals if s['signal_type'] == 'LONG']
        short_signals = [s for s in signals if s['signal_type'] == 'SHORT']
        
        long_confidence = sum(s['confidence'] for s in long_signals) / len(self.strategies)
        short_confidence = sum(s['confidence'] for s in short_signals) / len(self.strategies)
        
        if long_confidence > short_confidence and long_confidence > 0.5:
            return {
                'signal_type': 'LONG',
                'confidence': long_confidence,
                'price': market_state['price'],
                'timestamp': datetime.now().timestamp(),
                'strategy': 'COMBINED',
                'indicators': {
                    'long_signals': len(long_signals),
                    'short_signals': len(short_signals),
                    'long_confidence': long_confidence,
                    'short_confidence': short_confidence
                }
            }
        elif short_confidence > long_confidence and short_confidence > 0.5:
            return {
                'signal_type': 'SHORT',
                'confidence': short_confidence,
                'price': market_state['price'],
                'timestamp': datetime.now().timestamp(),
                'strategy': 'COMBINED',
                'indicators': {
                    'long_signals': len(long_signals),
                    'short_signals': len(short_signals),
                    'long_confidence': long_confidence,
                    'short_confidence': short_confidence
                }
            }
        return None 