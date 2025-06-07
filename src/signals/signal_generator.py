from typing import Dict, List, Optional
import logging
import numpy as np
import pandas as pd
from datetime import datetime
from ta.trend import SMAIndicator, EMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from ..strategy.dynamic_config import DynamicStrategyConfig
from ..strategies.candle_cluster.detector import CandleClusterDetector
import ta

logger = logging.getLogger(__name__)

class SignalGenerator:
    def __init__(self):
        self.signals = []
        self.indicators = {}
        self.strategy_config = DynamicStrategyConfig()
        self.strategy_config.set_profile("moderate")  # Default to moderate profile
        self.candle_detector = CandleClusterDetector()
        
    def calculate_indicators(self, market_data: Dict, params: Dict = None) -> Dict:
        """Calculate technical indicators from market data."""
        try:
            # Extract price data
            df = pd.DataFrame(market_data['klines'])
            df['close'] = pd.to_numeric(df['close'])
            df['high'] = pd.to_numeric(df['high'])
            df['low'] = pd.to_numeric(df['low'])
            df['volume'] = pd.to_numeric(df['volume'])
            
            # Calculate MACD
            macd = ta.trend.MACD(
                df['close'],
                window_slow=params.get('macd_slow_period', 26),
                window_fast=params.get('macd_fast_period', 12),
                window_sign=params.get('macd_signal_period', 9)
            )
            
            # Calculate RSI
            rsi = ta.momentum.RSIIndicator(
                df['close'],
                window=14
            )
            
            # Calculate Bollinger Bands
            bb = ta.volatility.BollingerBands(
                df['close'],
                window=20,
                window_dev=params.get('bb_std_dev', 2)
            )
            
            # Calculate ADX
            adx = ta.trend.ADXIndicator(
                df['high'],
                df['low'],
                df['close'],
                window=14
            )
            
            # Calculate ATR
            atr = ta.volatility.AverageTrueRange(
                df['high'],
                df['low'],
                df['close'],
                window=14
            )
            
            # Calculate CCI
            cci = ta.trend.CCIIndicator(
                df['high'],
                df['low'],
                df['close'],
                window=20
            )
            
            # Get current price
            current_price = float(df['close'].iloc[-1])
            
            return {
                'macd': {
                    'value': float(macd.macd().iloc[-1]),
                    'signal': float(macd.macd_signal().iloc[-1]),
                    'histogram': float(macd.macd_diff().iloc[-1])
                },
                'macd_signal': float(macd.macd_signal().iloc[-1]),
                'rsi': float(rsi.rsi().iloc[-1]),
                'bollinger_bands': {
                    'upper': float(bb.bollinger_hband().iloc[-1]),
                    'middle': float(bb.bollinger_mavg().iloc[-1]),
                    'lower': float(bb.bollinger_lband().iloc[-1])
                },
                'bb_upper': float(bb.bollinger_hband().iloc[-1]),
                'bb_lower': float(bb.bollinger_lband().iloc[-1]),
                'adx': {
                    'value': float(adx.adx().iloc[-1]),
                    'di_plus': float(adx.adx_pos().iloc[-1]),
                    'di_minus': float(adx.adx_neg().iloc[-1])
                },
                'plus_di': float(adx.adx_pos().iloc[-1]),
                'minus_di': float(adx.adx_neg().iloc[-1]),
                'atr': float(atr.average_true_range().iloc[-1]),
                'cci': float(cci.cci().iloc[-1]),
                'current_price': current_price
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
                logger.warning(f"No parameters found for {symbol}")
                return {}
                
            # Validate required indicators
            required_indicators = ['macd', 'macd_signal', 'rsi', 'current_price', 'bb_upper', 'bb_lower', 'adx', 'plus_di', 'minus_di', 'cci']
            missing_indicators = [ind for ind in required_indicators if ind not in indicators]
            if missing_indicators:
                logger.warning(f"Missing required indicators for {symbol}: {missing_indicators}")
                return {}
                
            # Calculate signal strength
            signal_strength = 0
            signal_type = None
            
            # MACD Signal
            if indicators['macd']['value'] > indicators['macd_signal']:
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
            if indicators['adx']['value'] > 25:  # Strong trend
                if indicators['adx']['di_plus'] > indicators['adx']['di_minus']:
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
                
            # Check for hovering opportunity (new strategy)
            hovering_opportunity = self.candle_detector.detect(symbol, indicators, params)
            if hovering_opportunity:
                # Override with the new signal type and structure if found
                return {
                    "symbol": symbol,
                    "price": indicators['current_price'],
                    "direction": "LONG" if hovering_opportunity['signal_type'] == 'SAFE_BUY' else "SHORT",
                    "confidence": hovering_opportunity['confidence_score'],
                    "entry": hovering_opportunity['entry'],
                    "take_profit": hovering_opportunity['take_profit'],
                    "stop_loss": hovering_opportunity['stop_loss'],
                    "signal_type": hovering_opportunity['signal_type'],
                    "indicators": indicators,
                    "reasoning": hovering_opportunity.get('reasoning', [])
                }

            # For standard signals, determine direction from strength and include required fields
            direction = "LONG" if signal_strength > 0 else ("SHORT" if signal_strength < 0 else "NEUTRAL")

            # Determine signal_type based on signal_strength for standard signals
            if signal_strength > 3:  # Example threshold for STRONG signals
                signal_type = "STRONG_BUY" if direction == "LONG" else "STRONG_SELL"
            elif signal_strength > 0:
                signal_type = "BUY" if direction == "LONG" else "SELL"
            else:
                signal_type = "NEUTRAL"

            # Only generate a signal if there's a clear direction
            if direction == "NEUTRAL":
                logger.debug(f"Generated NEUTRAL signal for {symbol}.")
                return {}

            # For standard signals, calculate entry/TP/SL based on price and volatility
            entry_price = indicators['current_price']
            atr = indicators.get('atr', 0)
            
            # Calculate take profit and stop loss based on ATR
            if direction == "LONG":
                take_profit = entry_price + (atr * 2)  # 2 ATR for take profit
                stop_loss = entry_price - (atr * 1)    # 1 ATR for stop loss
            else:  # SHORT
                take_profit = entry_price - (atr * 2)  # 2 ATR for take profit
                stop_loss = entry_price + (atr * 1)    # 1 ATR for stop loss

            return {
                'symbol': symbol,
                'direction': direction,
                'price': indicators['current_price'],
                'confidence': confidence_score,
                'entry': entry_price,
                'take_profit': take_profit,
                'stop_loss': stop_loss,
                'signal_type': signal_type,
                'signal_strength': abs(signal_strength),
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