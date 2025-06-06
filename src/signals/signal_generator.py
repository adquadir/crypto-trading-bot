from typing import Dict, List, Optional
import logging
import numpy as np
import pandas as pd
from datetime import datetime
from ta.trend import SMAIndicator, EMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands
from ..strategy.dynamic_config import DynamicStrategyConfig

logger = logging.getLogger(__name__)

class SignalGenerator:
    def __init__(self):
        self.signals = []
        self.indicators = {}
        self.strategy_config = DynamicStrategyConfig()
        self.strategy_config.set_profile("moderate")  # Default to moderate profile
        
    def calculate_indicators(self, data: pd.DataFrame, params: Dict) -> Dict:
        """Calculate technical indicators with dynamic parameters."""
        try:
            # MACD
            exp1 = data['close'].ewm(span=params['macd_fast_period'], adjust=False).mean()
            exp2 = data['close'].ewm(span=params['macd_slow_period'], adjust=False).mean()
            macd = exp1 - exp2
            signal = macd.ewm(span=params['macd_signal_period'], adjust=False).mean()
            
            # RSI
            delta = data['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            # Bollinger Bands
            sma = data['close'].rolling(window=20).mean()
            std = data['close'].rolling(window=20).std()
            upper_band = sma + (std * params['bb_std_dev'])
            lower_band = sma - (std * params['bb_std_dev'])
            
            # ADX
            tr1 = pd.DataFrame(data['high'] - data['low'])
            tr2 = pd.DataFrame(abs(data['high'] - data['close'].shift(1)))
            tr3 = pd.DataFrame(abs(data['low'] - data['close'].shift(1)))
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(14).mean()
            
            up_move = data['high'] - data['high'].shift(1)
            down_move = data['low'].shift(1) - data['low']
            
            plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
            minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
            
            plus_di = 100 * (pd.Series(plus_dm).rolling(14).mean() / atr)
            minus_di = 100 * (pd.Series(minus_dm).rolling(14).mean() / atr)
            
            dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
            adx = dx.rolling(14).mean()
            
            # CCI
            tp = (data['high'] + data['low'] + data['close']) / 3
            sma_tp = tp.rolling(window=20).mean()
            mean_deviation = tp.rolling(window=20).apply(lambda x: np.mean(np.abs(x - np.mean(x))))
            cci = (tp - sma_tp) / (0.015 * mean_deviation)
            
            # Ichimoku Cloud
            high_9 = data['high'].rolling(window=9).max()
            low_9 = data['low'].rolling(window=9).min()
            tenkan_sen = (high_9 + low_9) / 2
            
            high_26 = data['high'].rolling(window=26).max()
            low_26 = data['low'].rolling(window=26).min()
            kijun_sen = (high_26 + low_26) / 2
            
            senkou_span_a = ((tenkan_sen + kijun_sen) / 2).shift(26)
            senkou_span_b = ((high_52 := data['high'].rolling(window=52).max()) + 
                            (low_52 := data['low'].rolling(window=52).min())) / 2
            
            return {
                'macd': macd.iloc[-1],
                'macd_signal': signal.iloc[-1],
                'rsi': rsi.iloc[-1],
                'bb_upper': upper_band.iloc[-1],
                'bb_middle': sma.iloc[-1],
                'bb_lower': lower_band.iloc[-1],
                'adx': adx.iloc[-1],
                'plus_di': plus_di.iloc[-1],
                'minus_di': minus_di.iloc[-1],
                'cci': cci.iloc[-1],
                'tenkan_sen': tenkan_sen.iloc[-1],
                'kijun_sen': kijun_sen.iloc[-1],
                'senkou_span_a': senkou_span_a.iloc[-1],
                'senkou_span_b': senkou_span_b.iloc[-1],
                'current_price': data['close'].iloc[-1]
            }
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return {}
            
    def generate_signals(self, symbol: str, indicators: Dict, confidence_score: float) -> Dict:
        """Generate trading signals with dynamic parameters."""
        try:
            # Get symbol-specific parameters based on confidence score
            params = self.strategy_config.get_symbol_specific_params(symbol, confidence_score)
            if not params:
                return {}
                
            # Calculate signal strength
            signal_strength = 0
            signal_type = None
            
            # MACD Signal
            if indicators['macd'] > indicators['macd_signal']:
                signal_strength += 1
            else:
                signal_strength -= 1
                
            # RSI Signal
            if indicators['rsi'] < params['rsi_oversold']:
                signal_strength += 2
            elif indicators['rsi'] > params['rsi_overbought']:
                signal_strength -= 2
                
            # Bollinger Bands Signal
            if indicators['current_price'] < indicators['bb_lower']:
                signal_strength += 1
            elif indicators['current_price'] > indicators['bb_upper']:
                signal_strength -= 1
                
            # ADX Signal
            if indicators['adx'] > 25:  # Strong trend
                if indicators['plus_di'] > indicators['minus_di']:
                    signal_strength += 1
                else:
                    signal_strength -= 1
                    
            # CCI Signal
            if indicators['cci'] > 100:
                signal_strength -= 1
            elif indicators['cci'] < -100:
                signal_strength += 1
                
            # Ichimoku Signal
            if (indicators['current_price'] > indicators['senkou_span_a'] and 
                indicators['current_price'] > indicators['senkou_span_b']):
                signal_strength += 1
            elif (indicators['current_price'] < indicators['senkou_span_a'] and 
                  indicators['current_price'] < indicators['senkou_span_b']):
                signal_strength -= 1
                
            # Determine signal type and strength
            if signal_strength >= 3:
                signal_type = "STRONG_BUY"
            elif signal_strength >= 1:
                signal_type = "BUY"
            elif signal_strength <= -3:
                signal_type = "STRONG_SELL"
            elif signal_strength <= -1:
                signal_type = "SELL"
            else:
                signal_type = "NEUTRAL"
                
            return {
                'symbol': symbol,
                'signal_type': signal_type,
                'signal_strength': abs(signal_strength),
                'confidence_score': confidence_score,
                'timestamp': datetime.now().isoformat(),
                'indicators': indicators,
                'parameters': params
            }
            
        except Exception as e:
            logger.error(f"Error generating signals for {symbol}: {e}")
            return {}
            
    def update_volatility(self, symbol: str, volatility: float):
        """Update strategy parameters based on market volatility."""
        self.strategy_config.adapt_to_volatility(symbol, volatility)
        
    def update_performance(self, trade_result: Dict):
        """Update strategy parameters based on trading performance."""
        self.strategy_config.adapt_to_performance(trade_result)
        
    def set_strategy_profile(self, profile_name: str):
        """Set the current strategy profile."""
        self.strategy_config.set_profile(profile_name)
        
    def get_risk_limits(self) -> Dict:
        """Get current risk management parameters."""
        return self.strategy_config.get_risk_limits()
        
    def get_signal_history(self) -> List[Dict]:
        """Get history of generated signals."""
        return self.signals
        
    def add_signal(self, signal: Dict):
        """Add a new signal to the history."""
        self.signals.append(signal)
        # Keep only last 1000 signals
        if len(self.signals) > 1000:
            self.signals = self.signals[-1000:] 