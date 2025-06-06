from typing import Dict, List, Optional
import logging
import numpy as np
import pandas as pd
from datetime import datetime
from ta.trend import SMAIndicator, EMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands, ATR
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
            
            # ATR
            atr_indicator = ATR(data['high'], data['low'], data['close'], window=14)
            atr_series = atr_indicator.atr()
            atr_value = atr_series.iloc[-1]
            # Calculate ATR trend (slope over a short window)
            atr_trend_window = 5 # Lookback window for ATR trend
            atr_trend = 0
            if len(atr_series) >= atr_trend_window:
                recent_atrs = atr_series[-atr_trend_window:]
                # Use simple linear regression slope
                x = np.arange(len(recent_atrs))
                atr_trend = np.polyfit(x, recent_atrs, 1)[0] # Get the slope

            # Volume Data
            recent_volumes = data['volume'].tolist()[-lookback_window:] # Reuse the lookback window from hovering strat
            avg_recent_volume = np.mean(recent_volumes) if recent_volumes else 0
            overall_avg_volume = data['volume'].mean() # Average volume over the entire data

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
                'current_price': data['close'].iloc[-1],
                'atr': atr_value,
                'atr_trend': atr_trend,
                'recent_volumes': recent_volumes, # Include recent volume data
                'avg_recent_volume': avg_recent_volume,
                'overall_avg_volume': overall_avg_volume,
                'close_prices': data['close'].tolist(), # Keep recent prices for pattern detection
                'high_prices': data['high'].tolist(),
                'low_prices': data['low'].tolist(),
                'open_prices': data['open'].tolist()
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
                
            # Check for hovering opportunity (new strategy)
            hovering_opportunity = self._detect_hovering_opportunity(symbol, indicators, params)
            if hovering_opportunity:
                # Override with the new signal type and structure if found
                return {
                    "symbol": symbol,
                    "entry": hovering_opportunity['entry'],
                    "take_profit": hovering_opportunity['take_profit'],
                    "stop_loss": hovering_opportunity['stop_loss'],
                    "confidence_score": hovering_opportunity['confidence_score'],
                    "signal_type": hovering_opportunity['signal_type']
                }

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

    def _detect_hovering_opportunity(self, symbol: str, indicators: Dict, params: Dict) -> Optional[Dict]:
        """Detect hovering zones for safe, small-profit opportunities."""
        try:
            close_prices = indicators.get('close_prices', [])
            high_prices = indicators.get('high_prices', [])
            low_prices = indicators.get('low_prices', [])
            atr_value = indicators.get('atr', 0)
            atr_trend = indicators.get('atr_trend', 0)
            recent_volumes = indicators.get('recent_volumes', [])
            avg_recent_volume = indicators.get('avg_recent_volume', 0)
            overall_avg_volume = indicators.get('overall_avg_volume', 0)
            current_price = indicators.get('current_price', close_prices[-1] if close_prices else None)

            if not close_prices or atr_value is None or current_price is None:
                return None # Not enough data

            # Define lookback window (e.g., last 10 candles)
            lookback_window = 10
            if len(close_prices) < lookback_window:
                return None # Not enough candles for analysis

            # Ensure we have enough data for ATR trend and volume analysis if lookback_window > atr_trend_window
            # The ATR trend window is 5, so lookback_window 10 is sufficient.

            recent_closes = close_prices[-lookback_window:]
            recent_highs = high_prices[-lookback_window:]
            recent_lows = low_prices[-lookback_window:]
            recent_range_high = max(recent_highs)
            recent_range_low = min(recent_lows)

            # Criteria for a hovering zone:
            # 1. Price is within a relatively tight range (e.g., max range < 2 * ATR)
            # 2. Small candle bodies (e.g., average body size < 0.5 * ATR)
            # 3. Current price is near the bottom of the recent range (for BUY)
            # 4. Decreasing volatility (ATR trend is negative)
            # 5. Horizontal volume clusters (recent volume is low/stable)

            max_range = recent_range_high - recent_range_low
            avg_candle_body = np.mean([abs(close - open) for close, open in zip(close_prices[-lookback_window:], indicators.get('open_prices', close_prices[-lookback_window:]))])

            is_tight_range = max_range < (2 * atr_value)
            is_small_bodies = avg_candle_body < (0.5 * atr_value)

            # Additional confirmations
            is_decreasing_volatility = atr_trend < 0 # Check if ATR trend slope is negative

            # Check for horizontal volume clusters (simplified: recent volume is below overall average or a threshold)
            # A more sophisticated approach would analyze volume profile.
            is_low_volume = avg_recent_volume < (overall_avg_volume * 0.8) if overall_avg_volume > 0 else True # Check if recent avg volume is less than 80% of overall avg
            # Alternative simplified check: check if recent volume is below a fixed threshold or relatively flat
            # For now, using the comparison to overall average volume.

            # Check for BUY opportunity
            is_near_bottom = (current_price - recent_range_low) < (max_range * 0.3)

            # Define target profit range in USD (e.g., $25 to $35)
            target_profit_min = 25.0
            target_profit_max = 35.0

            # Check if criteria met and potential for target profit exists
            if is_tight_range and is_small_bodies and is_near_bottom and is_decreasing_volatility and is_low_volume:
                # Calculate potential take profit target
                # Option 1: Fixed USD target above entry
                # potential_take_profit = current_price + target_profit_min

                # Option 2: Target near top of the detected range, ensuring minimum profit
                potential_take_profit = recent_range_high
                if potential_take_profit - current_price < target_profit_min:
                    potential_take_profit = current_price + target_profit_min # Ensure minimum gain
                if potential_take_profit - current_price > target_profit_max:
                    potential_take_profit = current_price + target_profit_max # Cap maximum gain

                # Calculate stop loss just below recent lows
                potential_stop_loss = min(recent_lows) * 0.998 # 0.2% below min low
                if current_price - potential_stop_loss < target_profit_min / 2.0: # Ensure SL is not too close
                    potential_stop_loss = current_price - (target_profit_min / 2.0) # Place SL at half the min TP distance

                # Calculate confidence for this signal type (can be a fixed value or dynamic)
                # Lower ATR means higher confidence in tight range
                hovering_confidence = max(0.6, min(1.0, (1.5 * atr_value / max_range))) # Example calculation

                # Ensure entry < take_profit and entry > stop_loss for LONG signal
                if current_price < potential_take_profit and current_price > potential_stop_loss:
                    logger.info(f"Detected hovering BUY opportunity for {symbol} at {current_price}")
                    return {
                        "entry": current_price,
                        "take_profit": potential_take_profit,
                        "stop_loss": potential_stop_loss,
                        "confidence_score": hovering_confidence,
                        "signal_type": "SAFE_BUY"
                    }

            # Criteria for a SAFE_SELL hovering zone:
            # 1. Price is within a relatively tight range (reusing is_tight_range)
            # 2. Small candle bodies (reusing is_small_bodies)
            # 3. Current price is near the top of the recent range
            # 4. Decreasing volatility (reusing is_decreasing_volatility)
            # 5. Horizontal volume clusters (reusing is_low_volume)

            is_near_top = (recent_range_high - current_price) < (max_range * 0.3)

            # Check if SAFE_SELL criteria met and potential for target profit exists
            if is_tight_range and is_small_bodies and is_near_top and is_decreasing_volatility and is_low_volume:
                # Calculate potential take profit target for SHORT
                # Target near bottom of the detected range, ensuring minimum profit
                potential_take_profit = recent_range_low
                if current_price - potential_take_profit < target_profit_min:
                    potential_take_profit = current_price - target_profit_min # Ensure minimum gain (price drops)
                if current_price - potential_take_profit > target_profit_max:
                    potential_take_profit = current_price - target_profit_max # Cap maximum gain

                # Calculate stop loss just above recent highs
                potential_stop_loss = max(recent_highs) * 1.002 # 0.2% above max high
                if potential_stop_loss - current_price < target_profit_min / 2.0: # Ensure SL is not too close
                    potential_stop_loss = current_price + (target_profit_min / 2.0) # Place SL at half the min TP distance

                # Calculate confidence for this signal type (can be a fixed value or dynamic)
                # Lower ATR means higher confidence in tight range
                # Reusing hovering_confidence calculation for symmetry
                sell_hovering_confidence = max(0.6, min(1.0, (1.5 * atr_value / max_range)))

                # Ensure entry > take_profit and entry < stop_loss for SHORT signal
                if current_price > potential_take_profit and current_price < potential_stop_loss:
                    logger.info(f"Detected hovering SELL opportunity for {symbol} at {current_price}")
                    return {
                        "entry": current_price,
                        "take_profit": potential_take_profit,
                        "stop_loss": potential_stop_loss,
                        "confidence_score": sell_hovering_confidence,
                        "signal_type": "SAFE_SELL"
                    }

            # Confirmation checks:
            # 1. Decreasing volatility (ATR trend is negative or close to zero)
            volatility_decreasing = atr_trend <= 0.01 # Allow slight increase or flat

            # 2. Recent volume not significantly higher than overall average
            # This avoids detecting breakouts or high-volume events
            volume_confirmation = avg_recent_volume <= overall_avg_volume * 1.2 # Allow up to 20% higher volume

            if not volatility_decreasing or not volume_confirmation:
                return None # Confirmations failed

            return None # No hovering opportunity found

        except Exception as e:
            logger.error(f"Error detecting hovering opportunity for {symbol}: {e}")
            return None 