from typing import Dict, List, Optional
import logging
import numpy as np
import pandas as pd
from datetime import datetime
from ta.trend import SMAIndicator, EMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands

logger = logging.getLogger(__name__)

class SignalGenerator:
    def __init__(self):
        self.signals = []
        self.indicators = {}
        
    def calculate_indicators(self, data: List[Dict]) -> Dict:
        """Calculate technical indicators from market data."""
        try:
            df = pd.DataFrame(data)
            
            # Calculate RSI
            rsi = RSIIndicator(close=df['close'], window=14)
            df['rsi'] = rsi.rsi()
            
            # Calculate Bollinger Bands
            bb = BollingerBands(close=df['close'], window=20, window_dev=2)
            df['bb_upper'] = bb.bollinger_hband()
            df['bb_lower'] = bb.bollinger_lband()
            
            # Calculate EMAs
            ema_20 = EMAIndicator(close=df['close'], window=20)
            ema_50 = EMAIndicator(close=df['close'], window=50)
            df['ema_20'] = ema_20.ema_indicator()
            df['ema_50'] = ema_50.ema_indicator()
            
            return df.to_dict('records')
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return {}
            
    def generate_signals(self, market_data: Dict, indicators: Dict) -> Optional[Dict]:
        """Generate trading signals based on market data and indicators."""
        try:
            current_price = market_data['price']
            funding_rate = market_data['funding_rate']
            open_interest = market_data['open_interest']
            
            # Get latest indicator values directly from the dictionary
            rsi = indicators.get('rsi')
            bb_upper = indicators.get('bollinger_bands', {}).get('upper')
            bb_lower = indicators.get('bollinger_bands', {}).get('lower')
            ema_20 = indicators.get('ema', {}).get('ema_20')
            ema_50 = indicators.get('ema', {}).get('ema_50')
            macd_value = indicators.get('macd', {}).get('value')
            macd_signal = indicators.get('macd', {}).get('signal')
            # Add other indicators as needed
            
            signal = {
                'timestamp': datetime.now().timestamp(),
                'symbol': market_data.get('symbol', 'UNKNOWN'),
                'price': current_price,
                'direction': None,
                'confidence': 0.0,
                'reasoning': [],
                'indicators': indicators # Include all calculated indicators
            }
            
            # Rule 1: RSI Oversold/Overbought
            if rsi is not None:
                if rsi < 30:
                    signal['direction'] = 'LONG'
                    signal['confidence'] += 0.3
                    signal['reasoning'].append('RSI oversold')
                elif rsi > 70:
                    signal['direction'] = 'SHORT'
                    signal['confidence'] += 0.3
                    signal['reasoning'].append('RSI overbought')
                
            # Rule 2: Bollinger Bands
            if bb_lower is not None and current_price < bb_lower:
                if signal['direction'] == 'LONG':
                    signal['confidence'] += 0.2
                else:
                     # If no initial direction, set based on this rule
                    signal['direction'] = 'LONG'
                    signal['confidence'] += 0.2
                signal['reasoning'].append('Price below lower BB')
            elif bb_upper is not None and current_price > bb_upper:
                if signal['direction'] == 'SHORT':
                    signal['confidence'] += 0.2
                else:
                    # If no initial direction, set based on this rule
                    signal['direction'] = 'SHORT'
                    signal['confidence'] += 0.2
                signal['reasoning'].append('Price above upper BB')
                
            # Rule 3: EMA Crossover
            if ema_20 is not None and ema_50 is not None:
                if ema_20 > ema_50:
                    if signal['direction'] == 'LONG':
                        signal['confidence'] += 0.2
                    else:
                        # If no initial direction, set based on this rule
                        signal['direction'] = 'LONG'
                        signal['confidence'] += 0.2
                    signal['reasoning'].append('EMA 20 crossed above EMA 50')
                elif ema_20 < ema_50:
                    if signal['direction'] == 'SHORT':
                        signal['confidence'] += 0.2
                    else:
                         # If no initial direction, set based on this rule
                        signal['direction'] = 'SHORT'
                        signal['confidence'] += 0.2
                    signal['reasoning'].append('EMA 20 crossed below EMA 50')
                
            # Rule 4: Funding Rate
            if funding_rate is not None:
                if funding_rate < -0.0004:  # -0.04%
                    if signal['direction'] == 'LONG':
                        signal['confidence'] += 0.1
                    signal['reasoning'].append('Negative funding rate')
                elif funding_rate > 0.0004:  # 0.04%
                    if signal['direction'] == 'SHORT':
                        signal['confidence'] += 0.1
                    signal['reasoning'].append('Positive funding rate')
                
            # Only return signals with sufficient confidence
            if signal['confidence'] >= 0.5 and signal['direction'] is not None:
                return signal
            return None
            
        except Exception as e:
            logger.error(f"Error generating signals: {e}")
            return None
            
    def get_signal_history(self) -> List[Dict]:
        """Get history of generated signals."""
        return self.signals
        
    def add_signal(self, signal: Dict):
        """Add a new signal to the history."""
        self.signals.append(signal)
        # Keep only last 1000 signals
        if len(self.signals) > 1000:
            self.signals = self.signals[-1000:] 