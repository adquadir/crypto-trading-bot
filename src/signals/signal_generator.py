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
            
            # Handle potential NaN/inf values from ta calculations
            def safe_float(val, default=0.0):
                try:
                    f = float(val)
                    if not np.isfinite(f):
                        return default
                    return f
                except Exception:
                    return default

            macd_value = safe_float(macd.macd().iloc[-1])
            macd_signal = safe_float(macd.macd_signal().iloc[-1])
            macd_histogram = safe_float(macd.macd_diff().iloc[-1])
            rsi_value = safe_float(rsi.rsi().iloc[-1], 50.0) # RSI default to 50
            
            bb_upper = safe_float(bb.bollinger_hband().iloc[-1], current_price)
            bb_middle = safe_float(bb.bollinger_mavg().iloc[-1], current_price)
            bb_lower = safe_float(bb.bollinger_lband().iloc[-1], current_price)
            
            # After ADX calculation, fill NaN/inf with 0
            adx_df = pd.DataFrame({
                'adx': adx.adx(),
                'adx_pos': adx.adx_pos(),
                'adx_neg': adx.adx_neg()
            })
            adx_df = adx_df.replace([np.inf, -np.inf], np.nan).fillna(0)
            adx_value = float(adx_df['adx'].iloc[-1])
            adx_di_plus = float(adx_df['adx_pos'].iloc[-1])
            adx_di_minus = float(adx_df['adx_neg'].iloc[-1])
            
            atr_value = safe_float(atr.average_true_range().iloc[-1])
            cci_value = safe_float(cci.cci().iloc[-1])

            return {
                'macd': {
                    'value': macd_value,
                    'signal': macd_signal,
                    'histogram': macd_histogram
                },
                'macd_signal': macd_signal,
                'rsi': rsi_value,
                'bollinger_bands': {
                    'upper': bb_upper,
                    'middle': bb_middle,
                    'lower': bb_lower
                },
                'bb_upper': bb_upper,
                'bb_lower': bb_lower,
                'adx': {
                    'value': adx_value,
                    'di_plus': adx_di_plus,
                    'di_minus': adx_di_minus
                },
                'plus_di': adx_di_plus,
                'minus_di': adx_di_minus,
                'atr': atr_value,
                'cci': cci_value,
                'current_price': current_price
            }
            
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return {}
            
    def generate_signals(self, symbol: str, market_data: Dict, initial_confidence: float = 0.0) -> Dict:
        """Generate trading signals based on technical indicators."""
        try:
            if not market_data:
                logger.warning(f"No market data available for {symbol}")
                return {}
            
            # Validate required market data fields
            required_fields = ['klines', 'ticker_24h', 'orderbook', 'funding_rate', 'open_interest']
            missing_fields = [field for field in required_fields if field not in market_data]
            if missing_fields:
                logger.warning(f"Missing required market data fields for {symbol}: {missing_fields}")
                return {}
                
            # Convert klines to DataFrame for indicator calculation
            df = pd.DataFrame(market_data['klines'])
            if df.empty:
                logger.warning(f"Empty klines data for {symbol}")
                return {}
                
            df['close'] = pd.to_numeric(df['close'])
            df['high'] = pd.to_numeric(df['high'])
            df['low'] = pd.to_numeric(df['low'])
            df['volume'] = pd.to_numeric(df['volume'])
            
            # Calculate indicators
            indicators = self.calculate_indicators(market_data, {})
            if not indicators:
                logger.warning(f"Failed to calculate indicators for {symbol}")
                return {}
                
            signal_strength = initial_confidence
            signal_type = None
            reasons = []
            
            # Amplified indicator scoring
            macd = indicators.get('macd', {})
            macd_value = macd.get('value', 0)
            macd_signal = macd.get('signal', 0)
            if macd_value > macd_signal:
                signal_strength += 1.5
                reasons.append("MACD bullish")
            else:
                signal_strength -= 1.5
                reasons.append("MACD bearish")

            rsi = indicators.get('rsi', 50)
            if rsi < 35:
                signal_strength += 1.0
                reasons.append("RSI bullish (oversold)")
            elif rsi > 65:
                signal_strength -= 1.0
                reasons.append("RSI bearish (overbought)")

            current_price = indicators.get('current_price', 0)
            bb = indicators.get('bollinger_bands', {})
            bb_lower = bb.get('lower', current_price)
            bb_upper = bb.get('upper', current_price)
            if current_price < bb_lower:
                signal_strength += 1.0
                reasons.append("Price below lower Bollinger Band (bullish)")
            elif current_price > bb_upper:
                signal_strength -= 1.0
                reasons.append("Price above upper Bollinger Band (bearish)")
                
            # Dynamic ADX influence for scalping
            adx = indicators.get('adx', {})
            adx_value = adx.get('value', 0)
            if adx_value > 15:
                signal_strength *= 1.2
                reasons.append("Strong trend (ADX > 15)")
            elif adx_value < 10:
                signal_strength *= 0.8
                reasons.append("Weak trend (ADX < 10)")

            # Lower confidence normalization for scalping
            confidence = min(abs(signal_strength) / 2.5, 1.0)
            
            # More sensitive direction thresholds for scalping
            if signal_strength >= 0.75:
                direction = 'LONG'
            elif signal_strength <= -0.75:
                direction = 'SHORT'
            else:
                direction = 'NEUTRAL'

            if direction not in ("LONG", "SHORT"):
                logger.warning(f"Invalid direction generated: {direction}")
                return {}

            # If we reach here, it means a BUY or SELL signal was generated.
            # Calculate entry, take profit, and stop loss levels
            atr = indicators.get('atr', 0)
            MIN_DIST_PCT = 0.002  # 0.2%
            if pd.isna(atr) or atr <= 0:
                entry = current_price
                min_dist = entry * MIN_DIST_PCT
                take_profit = entry + min_dist if direction == "LONG" else entry - min_dist
                stop_loss = entry - min_dist if direction == "LONG" else entry + min_dist
            else:
                entry = current_price
                min_dist = entry * MIN_DIST_PCT
                if direction == "LONG":
                    tp_dist = max(atr * 2, min_dist)
                    sl_dist = max(atr * 1, min_dist)
                    take_profit = entry + tp_dist
                    stop_loss = entry - sl_dist
                else:
                    tp_dist = max(atr * 2, min_dist)
                    sl_dist = max(atr * 1, min_dist)
                    take_profit = entry - tp_dist
                    stop_loss = entry + sl_dist

            # Validation log for suspicious TP
            if abs(entry - take_profit) < 1e-6:
                logger.warning(f"Suspicious TP detected for {symbol}: Entry ({entry}) ~= TP ({take_profit})")

            # Fallback stop loss / take profit
            if stop_loss is None:
                stop_loss = entry - entry * 0.005  # 0.5% stop loss
            if take_profit is None:
                take_profit = entry + entry * 0.01  # 1% take profit

            logger.debug(f"Generated signal for {symbol}: {direction} with strength {signal_strength}")
            
            return {
                'symbol': symbol,
                'signal_type': direction,
                'direction': direction,
                'strength': signal_strength,
                'confidence': confidence,
                'reasons': reasons,
                'timestamp': datetime.now().isoformat(),
                'price': current_price,
                'entry': entry,
                'take_profit': take_profit,
                'stop_loss': stop_loss,
                'indicators': {
                    'macd': macd,
                    'rsi': rsi,
                    'bollinger_bands': bb,
                    'adx': adx,
                    'atr': atr,
                    'current_price': current_price
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating signals for {symbol}: {str(e)}")
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