from typing import Dict, List, Optional, Tuple
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
        """Generate trading signals based on technical indicators and market regime."""
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
            
            # Calculate indicators for multiple timeframes
            timeframes = {
                '1m': df,
                '5m': self._resample_dataframe(df, '5T'),
                '15m': self._resample_dataframe(df, '15T')
            }
            
            indicators = {}
            for tf, tf_df in timeframes.items():
                indicators[tf] = self.calculate_indicators({'klines': tf_df.to_dict('records')}, {})
            
            # Check multi-timeframe alignment
            mtf_alignment = self._calculate_mtf_alignment(indicators)
            if not mtf_alignment or mtf_alignment['strength'] < 0.6:
                logger.debug(f"Insufficient multi-timeframe alignment for {symbol}")
                return {}
            
            # Get market regime
            regime = self._detect_market_regime(indicators)
            if regime['type'] == 'UNKNOWN':
                logger.debug(f"Unable to determine market regime for {symbol}")
                return {}
            
            # Adjust signal generation based on market regime
            signal_strength = initial_confidence
            signal_type = None
            reasons = []
            
            # Only generate signals in appropriate market conditions
            if regime['type'] == 'RANGING':
                # In ranging markets, look for mean reversion signals
                signal_strength, signal_type, reasons = self._generate_ranging_signals(
                    indicators, signal_strength, reasons
                )
            elif regime['type'] == 'TRENDING':
                # In trending markets, look for trend continuation signals
                signal_strength, signal_type, reasons = self._generate_trending_signals(
                    indicators, signal_strength, reasons
                )
            else:  # VOLATILE
                # In volatile markets, be more conservative
                signal_strength, signal_type, reasons = self._generate_volatile_signals(
                    indicators, signal_strength, reasons
                )
            
            if not signal_type:
                return {}
            
            # Calculate entry, stop loss, and take profit levels
            current_price = indicators['1m']['current_price']
            atr = indicators['1m']['atr']
            
            # Adjust levels based on market regime
            if regime['type'] == 'TRENDING':
                sl_multiplier = 2.0
                tp_multiplier = 3.0
            elif regime['type'] == 'RANGING':
                sl_multiplier = 1.5
                tp_multiplier = 2.0
            else:  # VOLATILE
                sl_multiplier = 2.5
                tp_multiplier = 4.0
            
            # Calculate initial levels
            if signal_type == 'LONG':
                stop_loss = current_price - (atr * sl_multiplier)
                take_profit = current_price + (atr * tp_multiplier)
            else:  # SHORT
                stop_loss = current_price + (atr * sl_multiplier)
                take_profit = current_price - (atr * tp_multiplier)
            
            # Adjust levels based on structure
            structure_levels = self._find_nearest_structure_level(
                indicators['1m'],
                current_price,
                signal_type
            )
            
            if structure_levels:
                # Adjust stop loss to nearest structure level
                if signal_type == 'LONG':
                    stop_loss = max(stop_loss, structure_levels['support'])
                else:
                    stop_loss = min(stop_loss, structure_levels['resistance'])
                
                # Adjust take profit to next structure level
                if signal_type == 'LONG':
                    take_profit = min(take_profit, structure_levels['next_resistance'])
                else:
                    take_profit = max(take_profit, structure_levels['next_support'])
            
            # Normalize confidence based on regime
            confidence = min(abs(signal_strength) / 2.5, 1.0)
            if regime['type'] == 'VOLATILE':
                confidence *= 0.8  # Reduce confidence in volatile markets
            
            return {
                'symbol': symbol,
                'signal_type': signal_type,
                'confidence': confidence,
                'price': current_price,
                'entry': current_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'timestamp': int(datetime.now().timestamp()),
                'regime': regime['type'],
                'mtf_alignment': mtf_alignment,
                'reasons': reasons,
                'indicators': indicators['1m']
            }
            
        except Exception as e:
            logger.error(f"Error generating signals for {symbol}: {e}")
            return {}

    def _generate_ranging_signals(self, indicators: Dict, signal_strength: float, reasons: List[str]) -> Tuple[float, str, List[str]]:
        """Generate signals for ranging market conditions."""
        try:
            # Get 1m timeframe indicators
            tf_indicators = indicators['1m']
            
            # Check RSI for mean reversion
            rsi = tf_indicators.get('rsi', 50)
            if rsi < 30:
                signal_strength += 1.0
                reasons.append("RSI oversold in ranging market")
                return signal_strength, 'LONG', reasons
            elif rsi > 70:
                signal_strength -= 1.0
                reasons.append("RSI overbought in ranging market")
                return signal_strength, 'SHORT', reasons
            
            # Check Bollinger Bands
            bb = tf_indicators.get('bollinger_bands', {})
            current_price = tf_indicators.get('current_price', 0)
            if current_price < bb.get('lower', current_price):
                signal_strength += 1.0
                reasons.append("Price below lower Bollinger Band in ranging market")
                return signal_strength, 'LONG', reasons
            elif current_price > bb.get('upper', current_price):
                signal_strength -= 1.0
                reasons.append("Price above upper Bollinger Band in ranging market")
                return signal_strength, 'SHORT', reasons
            
            return signal_strength, None, reasons
            
        except Exception as e:
            logger.error(f"Error generating ranging signals: {e}")
            return signal_strength, None, reasons

    def _generate_trending_signals(self, indicators: Dict, signal_strength: float, reasons: List[str]) -> Tuple[float, str, List[str]]:
        """Generate signals for trending market conditions."""
        try:
            # Get 1m timeframe indicators
            tf_indicators = indicators['1m']
            
            # Check MACD for trend continuation
            macd = tf_indicators.get('macd', {})
            if macd.get('histogram', 0) > 0 and macd.get('value', 0) > macd.get('signal', 0):
                signal_strength += 1.5
                reasons.append("MACD bullish in trending market")
                return signal_strength, 'LONG', reasons
            elif macd.get('histogram', 0) < 0 and macd.get('value', 0) < macd.get('signal', 0):
                signal_strength -= 1.5
                reasons.append("MACD bearish in trending market")
                return signal_strength, 'SHORT', reasons
            
            # Check EMA alignment
            ema_20 = tf_indicators.get('ema_20', 0)
            ema_50 = tf_indicators.get('ema_50', 0)
            if ema_20 > ema_50:
                signal_strength += 1.0
                reasons.append("EMA bullish alignment in trending market")
                return signal_strength, 'LONG', reasons
            elif ema_20 < ema_50:
                signal_strength -= 1.0
                reasons.append("EMA bearish alignment in trending market")
                return signal_strength, 'SHORT', reasons
            
            return signal_strength, None, reasons
            
        except Exception as e:
            logger.error(f"Error generating trending signals: {e}")
            return signal_strength, None, reasons

    def _generate_volatile_signals(self, indicators: Dict, signal_strength: float, reasons: List[str]) -> Tuple[float, str, List[str]]:
        """Generate signals for volatile market conditions."""
        try:
            # Get 1m timeframe indicators
            tf_indicators = indicators['1m']
            
            # Check for extreme RSI readings
            rsi = tf_indicators.get('rsi', 50)
            if rsi < 20:
                signal_strength += 1.0
                reasons.append("Extreme RSI oversold in volatile market")
                return signal_strength, 'LONG', reasons
            elif rsi > 80:
                signal_strength -= 1.0
                reasons.append("Extreme RSI overbought in volatile market")
                return signal_strength, 'SHORT', reasons
            
            # Check for Bollinger Band extremes
            bb = tf_indicators.get('bollinger_bands', {})
            current_price = tf_indicators.get('current_price', 0)
            bb_width = bb.get('width', 0)
            
            if bb_width > 0.05:  # Only trade if volatility is high enough
                if current_price < bb.get('lower', current_price) * 0.99:
                    signal_strength += 1.0
                    reasons.append("Price significantly below lower Bollinger Band in volatile market")
                    return signal_strength, 'LONG', reasons
                elif current_price > bb.get('upper', current_price) * 1.01:
                    signal_strength -= 1.0
                    reasons.append("Price significantly above upper Bollinger Band in volatile market")
                    return signal_strength, 'SHORT', reasons
            
            return signal_strength, None, reasons
            
        except Exception as e:
            logger.error(f"Error generating volatile signals: {e}")
            return signal_strength, None, reasons

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

    def _detect_market_regime(self, indicators: Dict) -> Dict:
        """Detect market regime using ADX, Bollinger Band width, and EMA slope."""
        try:
            # Get indicators from the 1m timeframe
            tf_indicators = indicators['1m']
            
            # Calculate Bollinger Band width
            bb = tf_indicators.get('bollinger_bands', {})
            bb_width = (bb.get('upper', 0) - bb.get('lower', 0)) / bb.get('middle', 1)
            
            # Get ADX values
            adx = tf_indicators.get('adx', {})
            adx_value = adx.get('value', 0)
            di_plus = adx.get('di_plus', 0)
            di_minus = adx.get('di_minus', 0)
            
            # Calculate EMA slope (using 20 and 50 EMAs)
            ema_20 = tf_indicators.get('ema_20', 0)
            ema_50 = tf_indicators.get('ema_50', 0)
            ema_slope = (ema_20 - ema_50) / ema_50 if ema_50 != 0 else 0
            
            # Determine trend strength
            trend_strength = abs(ema_slope)
            
            # Determine volatility
            volatility = bb_width
            
            # Determine market regime
            if adx_value > 25:  # Strong trend
                if abs(di_plus - di_minus) > 10:  # Clear trend direction
                    regime = 'TRENDING'
                    strength = min(adx_value / 50, 1.0)  # Normalize to 0-1
                else:
                    regime = 'VOLATILE'
                    strength = min(volatility * 2, 1.0)
            elif volatility > 0.05:  # High volatility
                regime = 'VOLATILE'
                strength = min(volatility * 2, 1.0)
            else:
                regime = 'RANGING'
                strength = min(1 - trend_strength, 1.0)
            
            return {
                'type': regime,
                'strength': strength,
                'indicators': {
                    'adx': adx_value,
                    'di_plus': di_plus,
                    'di_minus': di_minus,
                    'bb_width': bb_width,
                    'ema_slope': ema_slope,
                    'trend_strength': trend_strength,
                    'volatility': volatility
                }
            }
            
        except Exception as e:
            logger.error(f"Error detecting market regime: {e}")
            return {'type': 'UNKNOWN', 'strength': 0.0, 'indicators': {}}

    def _find_nearest_structure_level(self, indicators: Dict, current_price: float, signal_type: str) -> Optional[Dict]:
        """Find nearest support and resistance levels based on price structure."""
        try:
            # Get recent swing highs and lows
            swing_levels = self._calculate_swing_levels(indicators)
            if not swing_levels:
                return None
            
            # Find nearest levels
            if signal_type == 'LONG':
                support = max([level for level in swing_levels['lows'] if level < current_price], default=None)
                resistance = min([level for level in swing_levels['highs'] if level > current_price], default=None)
                next_resistance = min([level for level in swing_levels['highs'] if level > resistance], default=None)
            else:  # SHORT
                support = max([level for level in swing_levels['lows'] if level < current_price], default=None)
                resistance = min([level for level in swing_levels['highs'] if level > current_price], default=None)
                next_support = max([level for level in swing_levels['lows'] if level < support], default=None)
            
            return {
                'support': support,
                'resistance': resistance,
                'next_support': next_support if signal_type == 'SHORT' else None,
                'next_resistance': next_resistance if signal_type == 'LONG' else None
            }
            
        except Exception as e:
            logger.error(f"Error finding structure levels: {e}")
            return None

    def _calculate_swing_levels(self, indicators: Dict, lookback: int = 20) -> Dict:
        """Calculate recent swing highs and lows."""
        try:
            highs = indicators.get('highs', [])
            lows = indicators.get('lows', [])
            
            if len(highs) < lookback or len(lows) < lookback:
                return {'highs': [], 'lows': []}
            
            # Find swing highs
            swing_highs = []
            for i in range(2, len(highs) - 2):
                if highs[i] > highs[i-1] and highs[i] > highs[i-2] and \
                   highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                    swing_highs.append(highs[i])
                
            # Find swing lows
            swing_lows = []
            for i in range(2, len(lows) - 2):
                if lows[i] < lows[i-1] and lows[i] < lows[i-2] and \
                   lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                    swing_lows.append(lows[i])
                
            return {
                'highs': sorted(swing_highs),
                'lows': sorted(swing_lows)
            }
            
        except Exception as e:
            logger.error(f"Error calculating swing levels: {e}")
            return {'highs': [], 'lows': []}

    def _calculate_mtf_alignment(self, indicators: Dict) -> Dict:
        """Calculate multi-timeframe alignment with enhanced analysis."""
        try:
            # Get indicators from all timeframes
            tf_indicators = {
                '1m': indicators.get('1m', {}),
                '5m': indicators.get('5m', {}),
                '15m': indicators.get('15m', {})
            }
            
            # Calculate technical alignment
            technical_alignment = self._calculate_technical_alignment(tf_indicators)
            
            # Calculate volume alignment
            volume_alignment = self._calculate_volume_alignment(tf_indicators)
            
            # Calculate pattern alignment
            pattern_alignment = self._calculate_pattern_alignment(tf_indicators)
            
            # Calculate overall alignment
            alignment = {
                'strength': (technical_alignment['score'] + volume_alignment['score'] + pattern_alignment['score']) / 3,
                'trend': technical_alignment['trend'],
                'details': {
                    'technical': technical_alignment,
                    'volume': volume_alignment,
                    'patterns': pattern_alignment
                }
            }
            
            logger.info(f"MTF Alignment calculated: {alignment['strength']:.2f}")
            logger.debug(f"MTF Alignment details: {alignment['details']}")
            
            return alignment
            
        except Exception as e:
            logger.error(f"Error calculating MTF alignment: {e}")
            return {'strength': 0.0, 'trend': 'NEUTRAL', 'details': {}}

    def _calculate_technical_alignment(self, tf_indicators: Dict) -> Dict:
        """Calculate technical indicator alignment across timeframes."""
        try:
            alignment_scores = []
            trend_signals = []
            
            for tf, indicators in tf_indicators.items():
                if not indicators:
                    continue
                    
                # Calculate individual indicator alignments
                macd_alignment = self._calculate_macd_alignment(indicators.get('macd', {}))
                rsi_alignment = self._calculate_rsi_alignment(indicators.get('rsi', 50))
                bb_alignment = self._calculate_bb_alignment(indicators.get('bollinger_bands', {}))
                adx_alignment = self._calculate_adx_alignment(indicators.get('adx', {}))
                ema_alignment = self._calculate_ema_alignment(
                    indicators.get('ema_20', 0),
                    indicators.get('ema_50', 0)
                )
                
                # Calculate weighted score for this timeframe
                tf_score = (
                    macd_alignment * 0.3 +
                    rsi_alignment * 0.2 +
                    bb_alignment * 0.2 +
                    adx_alignment * 0.15 +
                    ema_alignment * 0.15
                )
                
                alignment_scores.append(tf_score)
                trend_signals.append(1 if tf_score > 0 else -1 if tf_score < 0 else 0)
            
            # Calculate overall trend
            trend = 'NEUTRAL'
            if all(signal > 0 for signal in trend_signals):
                trend = 'BULLISH'
            elif all(signal < 0 for signal in trend_signals):
                trend = 'BEARISH'
            
            return {
                'score': sum(alignment_scores) / len(alignment_scores) if alignment_scores else 0,
                'trend': trend,
                'details': {
                    'scores': alignment_scores,
                    'trend_signals': trend_signals
                }
            }
            
        except Exception as e:
            logger.error(f"Error calculating technical alignment: {e}")
            return {'score': 0.0, 'trend': 'NEUTRAL', 'details': {}}

    def _calculate_volume_alignment(self, tf_indicators: Dict) -> Dict:
        """Enhanced volume alignment calculation."""
        try:
            volume_scores = []
            volume_trends = []
            volume_details = []

            for tf, indicators in tf_indicators.items():
                if not indicators or 'volume' not in indicators:
                    continue

                volumes = indicators['volume']
                if not volumes or len(volumes) < 20:
                    continue

                # Calculate volume profile
                profile = self._calculate_volume_profile(volumes)
                # Calculate volume delta
                delta = self._calculate_volume_delta(volumes)
                # Calculate volume trend
                trend = self._calculate_volume_trend(volumes)

                # Combine metrics
                volume_score = (
                    profile['score'] * 0.4 +
                    delta['score'] * 0.4 +
                    trend['score'] * 0.2
                )

                volume_scores.append(volume_score)
                volume_trends.append(trend['direction'])
                volume_details.append({
                    'timeframe': tf,
                    'profile': profile,
                    'delta': delta,
                    'trend': trend
                })

            # Calculate overall trend
            trend = 'NEUTRAL'
            if all(t == 'INCREASING' for t in volume_trends):
                trend = 'INCREASING'
            elif all(t == 'DECREASING' for t in volume_trends):
                trend = 'DECREASING'

            return {
                'score': sum(volume_scores) / len(volume_scores) if volume_scores else 0,
                'trend': trend,
                'details': {
                    'scores': volume_scores,
                    'trends': volume_trends,
                    'analysis': volume_details
                }
            }

        except Exception as e:
            logger.error(f"Error calculating volume alignment: {e}")
            return {'score': 0.0, 'trend': 'NEUTRAL', 'details': {}}

    def _calculate_volume_profile(self, volumes: List[float], num_bins: int = 10) -> Dict:
        """Calculate volume profile analysis."""
        try:
            if len(volumes) < 20:
                return {'score': 0.0, 'trend': 'NEUTRAL'}

            # Calculate volume moving averages
            short_ma = np.mean(volumes[-5:])
            long_ma = np.mean(volumes[-20:])

            # Calculate volume distribution
            hist, bins = np.histogram(volumes, bins=num_bins)
            volume_distribution = hist / np.sum(hist)

            # Calculate volume trend
            volume_trend = (short_ma - long_ma) / long_ma

            # Calculate volume consistency
            volume_std = np.std(volumes[-20:])
            volume_mean = np.mean(volumes[-20:])
            volume_consistency = 1 - (volume_std / volume_mean)

            # Calculate overall score
            score = (
                volume_trend * 0.4 +  # Volume trend weight
                volume_consistency * 0.3 +  # Volume consistency weight
                (1 - np.max(volume_distribution)) * 0.3  # Volume distribution weight
            )

            # Determine trend
            trend = 'NEUTRAL'
            if volume_trend > 0.1:
                trend = 'INCREASING'
            elif volume_trend < -0.1:
                trend = 'DECREASING'

            return {
                'score': score,
                'trend': trend,
                'details': {
                    'volume_trend': volume_trend,
                    'volume_consistency': volume_consistency,
                    'distribution': volume_distribution.tolist()
                }
            }

        except Exception as e:
            logger.error(f"Error calculating volume profile: {e}")
            return {'score': 0.0, 'trend': 'NEUTRAL'}

    def _calculate_volume_delta(self, volumes: List[float]) -> Dict:
        """Calculate volume delta analysis."""
        try:
            if len(volumes) < 20:
                return {'score': 0.0, 'trend': 'NEUTRAL'}

            # Calculate volume deltas
            deltas = [volumes[i] - volumes[i-1] for i in range(1, len(volumes))]
            recent_deltas = deltas[-5:]

            # Calculate delta trend
            delta_trend = np.mean(recent_deltas)
            delta_std = np.std(recent_deltas)
            delta_mean = np.mean(deltas)

            # Calculate score
            score = delta_trend / (delta_std + 1e-6)  # Avoid division by zero

            # Determine trend
            trend = 'NEUTRAL'
            if score > 0.5:
                trend = 'INCREASING'
            elif score < -0.5:
                trend = 'DECREASING'

            return {
                'score': score,
                'trend': trend,
                'details': {
                    'delta_trend': delta_trend,
                    'delta_std': delta_std,
                    'delta_mean': delta_mean
                }
            }

        except Exception as e:
            logger.error(f"Error calculating volume delta: {e}")
            return {'score': 0.0, 'trend': 'NEUTRAL'}

    def _calculate_volume_trend(self, volumes: List[float]) -> Dict:
        """Calculate volume trend analysis."""
        try:
            if len(volumes) < 20:
                return {'score': 0.0, 'direction': 'NEUTRAL'}

            # Calculate short and long-term moving averages
            short_ma = np.mean(volumes[-5:])
            long_ma = np.mean(volumes[-20:])

            # Calculate trend strength
            trend_strength = (short_ma - long_ma) / long_ma

            # Determine direction
            direction = 'NEUTRAL'
            if trend_strength > 0.1:
                direction = 'INCREASING'
            elif trend_strength < -0.1:
                direction = 'DECREASING'

            return {
                'score': trend_strength,
                'direction': direction,
                'details': {
                    'short_ma': short_ma,
                    'long_ma': long_ma,
                    'strength': trend_strength
                }
            }

        except Exception as e:
            logger.error(f"Error calculating volume trend: {e}")
            return {'score': 0.0, 'direction': 'NEUTRAL'}

    def _calculate_pattern_alignment(self, tf_indicators: Dict) -> Dict:
        """Calculate price pattern alignment across timeframes."""
        try:
            pattern_scores = []
            pattern_types = []
            
            for tf, indicators in tf_indicators.items():
                if not indicators:
                    continue
                    
                # Get price data
                highs = indicators.get('highs', [])
                lows = indicators.get('lows', [])
                if not highs or not lows or len(highs) < 20 or len(lows) < 20:
                    continue
                
                # Detect patterns
                patterns = self._detect_patterns(highs, lows, indicators['close'])
                if not patterns:
                    continue
                
                # Calculate pattern score
                pattern_score = sum(pattern['strength'] for pattern in patterns) / len(patterns)
                pattern_scores.append(pattern_score)
                pattern_types.append(patterns[0]['type'])  # Use most significant pattern
            
            # Calculate overall pattern trend
            trend = 'NEUTRAL'
            if all(score > 0.6 for score in pattern_scores):
                trend = 'BULLISH'
            elif all(score < -0.6 for score in pattern_scores):
                trend = 'BEARISH'
            
            return {
                'score': sum(pattern_scores) / len(pattern_scores) if pattern_scores else 0,
                'trend': trend,
                'details': {
                    'scores': pattern_scores,
                    'types': pattern_types
                }
            }
            
        except Exception as e:
            logger.error(f"Error calculating pattern alignment: {e}")
            return {'score': 0.0, 'trend': 'NEUTRAL', 'details': {}}

    def _detect_patterns(self, highs: List[float], lows: List[float], closes: List[float]) -> List[Dict]:
        """Enhanced pattern detection with multiple pattern types."""
        try:
            patterns = []
            if len(highs) < 20 or len(lows) < 20:
                return patterns

            # Double Top/Bottom
            if self._is_double_top(highs):
                patterns.append({
                    'type': 'DOUBLE_TOP',
                    'strength': 0.8,
                    'description': 'Bearish reversal pattern'
                })
            if self._is_double_bottom(lows):
                patterns.append({
                    'type': 'DOUBLE_BOTTOM',
                    'strength': 0.8,
                    'description': 'Bullish reversal pattern'
                })

            # Higher Highs/Lows
            if self._is_higher_highs_lows(highs, lows):
                patterns.append({
                    'type': 'HIGHER_HIGHS_LOWS',
                    'strength': 0.7,
                    'description': 'Uptrend continuation'
                })
            elif self._is_lower_highs_lows(highs, lows):
                patterns.append({
                    'type': 'LOWER_HIGHS_LOWS',
                    'strength': 0.7,
                    'description': 'Downtrend continuation'
                })

            # Head and Shoulders
            if self._is_head_and_shoulders(highs, lows):
                patterns.append({
                    'type': 'HEAD_AND_SHOULDERS',
                    'strength': 0.9,
                    'description': 'Bearish reversal pattern'
                })
            elif self._is_inverse_head_and_shoulders(highs, lows):
                patterns.append({
                    'type': 'INVERSE_HEAD_AND_SHOULDERS',
                    'strength': 0.9,
                    'description': 'Bullish reversal pattern'
                })

            # Triangle Patterns
            triangle_type = self._detect_triangle_pattern(highs, lows)
            if triangle_type:
                patterns.append({
                    'type': triangle_type,
                    'strength': 0.75,
                    'description': 'Consolidation pattern'
                })

            return patterns

        except Exception as e:
            logger.error(f"Error detecting patterns: {e}")
            return []

    def _is_double_top(self, highs: List[float], threshold: float = 0.02) -> bool:
        """Detect double top pattern."""
        try:
            if len(highs) < 20:
                return False

            # Find local maxima
            peaks = []
            for i in range(2, len(highs) - 2):
                if highs[i] > highs[i-1] and highs[i] > highs[i-2] and \
                   highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                    peaks.append((i, highs[i]))

            if len(peaks) < 2:
                return False

            # Check last two peaks
            last_two_peaks = peaks[-2:]
            price_diff = abs(last_two_peaks[1][1] - last_two_peaks[0][1])
            avg_price = (last_two_peaks[0][1] + last_two_peaks[1][1]) / 2

            return price_diff / avg_price < threshold

        except Exception as e:
            logger.error(f"Error detecting double top: {e}")
            return False

    def _is_double_bottom(self, lows: List[float], threshold: float = 0.02) -> bool:
        """Detect double bottom pattern."""
        try:
            if len(lows) < 20:
                return False

            # Find local minima
            troughs = []
            for i in range(2, len(lows) - 2):
                if lows[i] < lows[i-1] and lows[i] < lows[i-2] and \
                   lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                    troughs.append((i, lows[i]))

            if len(troughs) < 2:
                return False

            # Check last two troughs
            last_two_troughs = troughs[-2:]
            price_diff = abs(last_two_troughs[1][1] - last_two_troughs[0][1])
            avg_price = (last_two_troughs[0][1] + last_two_troughs[1][1]) / 2

            return price_diff / avg_price < threshold

        except Exception as e:
            logger.error(f"Error detecting double bottom: {e}")
            return False

    def _is_higher_highs_lows(self, highs: List[float], lows: List[float], lookback: int = 5) -> bool:
        """Detect higher highs and higher lows pattern."""
        try:
            if len(highs) < lookback or len(lows) < lookback:
                return False

            recent_highs = highs[-lookback:]
            recent_lows = lows[-lookback:]

            # Check if highs are making higher highs
            higher_highs = all(recent_highs[i] > recent_highs[i-1] for i in range(1, len(recent_highs)))
            # Check if lows are making higher lows
            higher_lows = all(recent_lows[i] > recent_lows[i-1] for i in range(1, len(recent_lows)))

            return higher_highs and higher_lows

        except Exception as e:
            logger.error(f"Error detecting higher highs and lows: {e}")
            return False

    def _is_lower_highs_lows(self, highs: List[float], lows: List[float], lookback: int = 5) -> bool:
        """Detect lower highs and lower lows pattern."""
        try:
            if len(highs) < lookback or len(lows) < lookback:
                return False

            recent_highs = highs[-lookback:]
            recent_lows = lows[-lookback:]

            # Check if highs are making lower highs
            lower_highs = all(recent_highs[i] < recent_highs[i-1] for i in range(1, len(recent_highs)))
            # Check if lows are making lower lows
            lower_lows = all(recent_lows[i] < recent_lows[i-1] for i in range(1, len(recent_lows)))

            return lower_highs and lower_lows

        except Exception as e:
            logger.error(f"Error detecting lower highs and lows: {e}")
            return False

    def _is_head_and_shoulders(self, highs: List[float], lows: List[float]) -> bool:
        """Detect head and shoulders pattern."""
        try:
            if len(highs) < 5 or len(lows) < 5:
                return False

            # Find local maxima and minima
            peaks = []
            troughs = []
            for i in range(2, len(highs) - 2):
                if highs[i] > highs[i-1] and highs[i] > highs[i-2] and \
                   highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                    peaks.append((i, highs[i]))
                if lows[i] < lows[i-1] and lows[i] < lows[i-2] and \
                   lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                    troughs.append((i, lows[i]))

            if len(peaks) < 3 or len(troughs) < 3:
                return False

            # Check head and shoulders pattern
            if peaks[0][1] > peaks[1][1] and peaks[1][1] > peaks[2][1] and \
               troughs[0][1] < troughs[1][1] and troughs[1][1] < troughs[2][1]:
                return True

            return False

        except Exception as e:
            logger.error(f"Error detecting head and shoulders: {e}")
            return False

    def _is_inverse_head_and_shoulders(self, highs: List[float], lows: List[float]) -> bool:
        """Detect inverse head and shoulders pattern."""
        try:
            if len(highs) < 5 or len(lows) < 5:
                return False

            # Find local maxima and minima
            peaks = []
            troughs = []
            for i in range(2, len(highs) - 2):
                if highs[i] > highs[i-1] and highs[i] > highs[i-2] and \
                   highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                    peaks.append((i, highs[i]))
                if lows[i] < lows[i-1] and lows[i] < lows[i-2] and \
                   lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                    troughs.append((i, lows[i]))

            if len(peaks) < 3 or len(troughs) < 3:
                return False

            # Check inverse head and shoulders pattern
            if peaks[0][1] < peaks[1][1] and peaks[1][1] < peaks[2][1] and \
               troughs[0][1] > troughs[1][1] and troughs[1][1] > troughs[2][1]:
                return True

            return False

        except Exception as e:
            logger.error(f"Error detecting inverse head and shoulders: {e}")
            return False

    def _detect_triangle_pattern(self, highs: List[float], lows: List[float]) -> Optional[str]:
        """Detect various triangle patterns."""
        try:
            if len(highs) < 20 or len(lows) < 20:
                return None

            recent_highs = highs[-20:]
            recent_lows = lows[-20:]

            # Calculate slopes of highs and lows
            high_slope = np.polyfit(range(len(recent_highs)), recent_highs, 1)[0]
            low_slope = np.polyfit(range(len(recent_lows)), recent_lows, 1)[0]

            # Determine triangle type based on slopes
            if abs(high_slope) < 0.001 and abs(low_slope) < 0.001:
                return 'RECTANGLE'
            elif high_slope < -0.001 and low_slope > 0.001:
                return 'SYMMETRICAL_TRIANGLE'
            elif high_slope < -0.001 and abs(low_slope) < 0.001:
                return 'ASCENDING_TRIANGLE'
            elif abs(high_slope) < 0.001 and low_slope > 0.001:
                return 'DESCENDING_TRIANGLE'

            return None

        except Exception as e:
            logger.error(f"Error detecting triangle pattern: {e}")
            return None

    def _calculate_ema_alignment(self, ema_20: float, ema_50: float) -> float:
        """Calculate EMA alignment score."""
        try:
            if not ema_20 or not ema_50:
                return 0.0
            
            # Calculate EMA slope
            slope = (ema_20 - ema_50) / ema_50
            
            # Normalize slope to -1 to 1 range
            return max(min(slope * 10, 1.0), -1.0)
            
        except Exception as e:
            logger.error(f"Error calculating EMA alignment: {e}")
            return 0.0

    def _calculate_macd_alignment(self, macd1: Dict, macd2: Dict) -> float:
        """Calculate MACD alignment between two timeframes."""
        try:
            # Get MACD values
            value1 = macd1.get('value', 0)
            signal1 = macd1.get('signal', 0)
            value2 = macd2.get('value', 0)
            signal2 = macd2.get('signal', 0)
            
            # Calculate MACD alignment
            if value1 > signal1 and value2 > signal2:
                return 1.0
            elif value1 < signal1 and value2 < signal2:
                return -1.0
            else:
                return 0.0
            
        except Exception as e:
            logger.error(f"Error calculating MACD alignment: {e}")
            return 0.0

    def _calculate_rsi_alignment(self, rsi1: float, rsi2: float) -> float:
        """Calculate RSI alignment between two timeframes."""
        try:
            # Calculate RSI alignment
            if rsi1 > 50 and rsi2 > 50:
                return 1.0
            elif rsi1 < 50 and rsi2 < 50:
                return -1.0
            else:
                return 0.0
            
        except Exception as e:
            logger.error(f"Error calculating RSI alignment: {e}")
            return 0.0

    def _calculate_bb_alignment(self, bb1: Dict, bb2: Dict) -> float:
        """Calculate Bollinger Bands alignment between two timeframes."""
        try:
            # Get Bollinger Bands values
            upper1 = bb1.get('upper', 0)
            middle1 = bb1.get('middle', 0)
            lower1 = bb1.get('lower', 0)
            upper2 = bb2.get('upper', 0)
            middle2 = bb2.get('middle', 0)
            lower2 = bb2.get('lower', 0)
            
            # Calculate Bollinger Bands alignment
            if upper1 > middle1 and upper2 > middle2:
                return 1.0
            elif upper1 < middle1 and upper2 < middle2:
                return -1.0
            else:
                return 0.0
            
        except Exception as e:
            logger.error(f"Error calculating Bollinger Bands alignment: {e}")
            return 0.0

    def _calculate_adx_alignment(self, adx1: Dict, adx2: Dict) -> float:
        """Calculate ADX alignment between two timeframes."""
        try:
            # Get ADX values
            value1 = adx1.get('value', 0)
            value2 = adx2.get('value', 0)
            
            # Calculate ADX alignment
            if value1 > 25 and value2 > 25:
                return 1.0
            elif value1 < 25 and value2 < 25:
                return -1.0
            else:
                return 0.0
            
        except Exception as e:
            logger.error(f"Error calculating ADX alignment: {e}")
            return 0.0 