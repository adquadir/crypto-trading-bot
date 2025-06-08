from typing import Dict, List, Optional, Tuple, Any
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from ta.trend import SMAIndicator, EMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from ..strategy.dynamic_config import DynamicStrategyConfig
from ..strategies.candle_cluster.detector import CandleClusterDetector
import ta
from .signal_tracker import SignalTracker, SignalProfile
import json
from .confidence_calibrator import ConfidenceCalibrator

logger = logging.getLogger(__name__)

class SignalGenerator:
    def __init__(self):
        self.signals = []
        self.indicators = {}
        self.strategy_config = DynamicStrategyConfig()
        self.strategy_config.set_profile("moderate")  # Default to moderate profile
        self.candle_detector = CandleClusterDetector()
        self.signal_tracker = SignalTracker()
        self.confidence_calibrator = ConfidenceCalibrator()
        
    def calculate_indicators(self, market_data: Dict, params: Dict = None) -> Dict:
        """Calculate technical indicators from market data."""
        try:
            # Validate market data
            if not market_data or 'klines' not in market_data:
                logger.error("Invalid market data: missing 'klines' key")
                return {}
            
            klines = market_data['klines']
            if not klines or len(klines) == 0:
                logger.error("Empty klines data")
                return {}
            
            logger.debug(f"Processing {len(klines)} klines")
            
            # Extract price data
            df = pd.DataFrame(klines)
            
            # Validate required columns
            required_columns = ['open', 'high', 'low', 'close', 'volume']
            if not all(col in df.columns for col in required_columns):
                logger.error(f"Missing required columns in market data. Available columns: {df.columns.tolist()}")
                return {}
            
            # Convert numeric columns
            for col in required_columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                logger.debug(f"Column {col} stats - min: {df[col].min()}, max: {df[col].max()}, mean: {df[col].mean()}")
            
            # Drop any rows with NaN values
            initial_len = len(df)
            df.dropna(inplace=True)
            if len(df) < initial_len:
                logger.warning(f"Dropped {initial_len - len(df)} rows with NaN values")
            
            # Validate data points
            min_required_points = 20  # Minimum required for most indicators
            if len(df) < min_required_points:
                logger.warning(f"Insufficient data points: {len(df)} < {min_required_points}")
                return {}
            
            # Get current price
            current_price = float(df['close'].iloc[-1])
            logger.debug(f"Current price: {current_price}")
            
            # Handle potential NaN/inf values from ta calculations
            def safe_float(val, default=0.0):
                try:
                    f = float(val)
                    if not np.isfinite(f):
                        logger.debug(f"Non-finite value encountered: {val}, using default: {default}")
                        return default
                    return f
                except Exception as e:
                    logger.debug(f"Error converting to float: {val}, error: {e}, using default: {default}")
                    return default

            # Calculate indicators with error handling
            try:
                logger.debug("Calculating MACD...")
                macd = ta.trend.MACD(
                    df['close'],
                    window_slow=params.get('macd_slow_period', 26),
                    window_fast=params.get('macd_fast_period', 12),
                    window_sign=params.get('macd_signal_period', 9)
                )
            macd_value = safe_float(macd.macd().iloc[-1])
            macd_signal = safe_float(macd.macd_signal().iloc[-1])
            macd_histogram = safe_float(macd.macd_diff().iloc[-1])
                logger.debug(f"MACD values - value: {macd_value}, signal: {macd_signal}, histogram: {macd_histogram}")
            except Exception as e:
                logger.error(f"Error calculating MACD: {e}")
                macd_value = macd_signal = macd_histogram = 0.0

            try:
                logger.debug("Calculating RSI...")
                rsi = ta.momentum.RSIIndicator(
                    df['close'],
                    window=14
                )
                rsi_value = safe_float(rsi.rsi().iloc[-1], 50.0)
                logger.debug(f"RSI value: {rsi_value}")
            except Exception as e:
                logger.error(f"Error calculating RSI: {e}")
                rsi_value = 50.0

            try:
                logger.debug("Calculating Bollinger Bands...")
                bb = ta.volatility.BollingerBands(
                    df['close'],
                    window=20,
                    window_dev=params.get('bb_std_dev', 2)
                )
            bb_upper = safe_float(bb.bollinger_hband().iloc[-1], current_price)
            bb_middle = safe_float(bb.bollinger_mavg().iloc[-1], current_price)
            bb_lower = safe_float(bb.bollinger_lband().iloc[-1], current_price)
                logger.debug(f"Bollinger Bands - upper: {bb_upper}, middle: {bb_middle}, lower: {bb_lower}")
            except Exception as e:
                logger.error(f"Error calculating Bollinger Bands: {e}")
                bb_upper = bb_middle = bb_lower = current_price

            # Adjust ADX window based on available data points
            adx_window = min(14, len(df) - 1)  # Ensure window size doesn't exceed available data
            try:
                logger.debug(f"Calculating ADX with window size {adx_window}...")
                adx = ta.trend.ADXIndicator(
                    df['high'],
                    df['low'],
                    df['close'],
                    window=adx_window
                )
            adx_df = pd.DataFrame({
                'adx': adx.adx(),
                'adx_pos': adx.adx_pos(),
                'adx_neg': adx.adx_neg()
            })
            adx_df = adx_df.replace([np.inf, -np.inf], np.nan).fillna(0)
            adx_value = float(adx_df['adx'].iloc[-1])
            adx_di_plus = float(adx_df['adx_pos'].iloc[-1])
            adx_di_minus = float(adx_df['adx_neg'].iloc[-1])
                logger.debug(f"ADX values - value: {adx_value}, DI+: {adx_di_plus}, DI-: {adx_di_minus}")
            except Exception as e:
                logger.error(f"Error calculating ADX: {e}")
                adx_value = adx_di_plus = adx_di_minus = 0.0

            try:
                logger.debug("Calculating ATR...")
                atr = ta.volatility.AverageTrueRange(
                    df['high'],
                    df['low'],
                    df['close'],
                    window=min(14, len(df) - 1)  # Adjust window size
                )
            atr_value = safe_float(atr.average_true_range().iloc[-1])
                logger.debug(f"ATR value: {atr_value}")
            except Exception as e:
                logger.error(f"Error calculating ATR: {e}")
                atr_value = 0.0

            try:
                logger.debug("Calculating CCI...")
                cci = ta.trend.CCIIndicator(
                    df['high'],
                    df['low'],
                    df['close'],
                    window=min(20, len(df) - 1)  # Adjust window size
                )
            cci_value = safe_float(cci.cci().iloc[-1])
                logger.debug(f"CCI value: {cci_value}")
            except Exception as e:
                logger.error(f"Error calculating CCI: {e}")
                cci_value = 0.0

            indicators = {
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
            
            logger.debug("Successfully calculated all indicators")
            return indicators
            
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return {}
            
    async def generate_signals(self, market_data: Dict) -> Optional[Dict]:
        """Generate trading signals based on market data."""
        try:
            symbol = market_data.get('symbol')
            if not symbol:
                return None
                
            # Calculate freshness metrics for each data type
            freshness_metrics = {
                'ohlcv': market_data.get('ohlcv_freshness', float('inf')),
                'orderbook': market_data.get('orderbook_freshness', float('inf')),
                'ticker': market_data.get('ticker_freshness', float('inf')),
                'open_interest': market_data.get('oi_freshness', float('inf'))
            }
            
            # Log freshness metrics
            logger.info(f"Data freshness for {symbol}: {json.dumps({k: f'{v:.1f}s' for k, v in freshness_metrics.items()})}")
            
            # Check if any critical data is too stale
            max_freshness = {
                'ohlcv': 60,  # 1 minute
                'orderbook': 5,  # 5 seconds
                'ticker': 5,  # 5 seconds
                'open_interest': 60  # 1 minute
            }
            
            stale_data = {k: v for k, v in freshness_metrics.items() if v > max_freshness[k]}
            if stale_data:
                self.signal_tracker.log_rejection(
                    symbol,
                    f"Stale data detected: {json.dumps({k: f'{v:.1f}s' for k, v in stale_data.items()})}",
                    market_data
                )
                return None
                
            # Determine market regime
            regime = self._determine_market_regime(market_data)
            
            # Calculate indicators
            indicators = self._calculate_indicators(market_data)
            
            # Generate signal based on regime
            signal = await self._generate_regime_signal(market_data, regime, indicators)
            if not signal:
                return None
                
            # Add freshness metrics to signal
            signal['data_freshness'] = freshness_metrics
            signal['max_allowed_freshness'] = max_freshness
                
            # Calculate entry, TP, and SL
            entry, tp, sl = self._calculate_levels(market_data, signal['direction'])
            if not all([entry, tp, sl]):
                self.signal_tracker.log_rejection(
                    symbol,
                    "Invalid price levels",
                    {**market_data, **signal}
                )
                return None
                
            # Calculate risk/reward ratio
            rr_ratio = abs(tp - entry) / abs(sl - entry)
            if rr_ratio < 1.5:  # Minimum 1.5:1 reward-to-risk
                self.signal_tracker.log_rejection(
                    symbol,
                    f"Poor risk/reward ratio: {rr_ratio:.2f}",
                    {**market_data, **signal}
                )
                return None
                
            # Check spread
            spread = market_data.get('spread', float('inf'))
            if spread > 0.002:  # 0.2% max spread
                self.signal_tracker.log_rejection(
                    symbol,
                    f"Spread too high: {spread:.4f}",
                    {**market_data, **signal}
                )
                return None
                
            # Create signal profile
            signal_profile = SignalProfile(
                symbol=symbol,
                timestamp=datetime.now(),
                market_regime=regime,
                indicators=indicators,
                entry_price=entry,
                take_profit=tp,
                stop_loss=sl,
                risk_reward_ratio=rr_ratio,
                confidence=signal['confidence'],
                volume_profile=market_data.get('volume_profile', {}),
                order_book_metrics=market_data.get('order_book_metrics', {})
            )
            
            # Log the signal
            self.signal_tracker.log_signal(signal_profile)
            
            return {
                'symbol': symbol,
                'direction': signal['direction'],
                'entry': entry,
                'take_profit': tp,
                'stop_loss': sl,
                'confidence': signal['confidence'],
                'market_regime': regime,
                'risk_reward_ratio': rr_ratio,
                'indicators': indicators,
                'volume_profile': market_data.get('volume_profile', {}),
                'order_book_metrics': market_data.get('order_book_metrics', {}),
                'data_freshness': freshness_metrics,
                'max_allowed_freshness': max_freshness
            }
            
        except Exception as e:
            logger.error(f"Error generating signals: {e}")
            return None
            
    def _determine_market_regime(self, market_data: Dict) -> Dict:
        """Determine the current market regime with confidence score."""
        try:
            indicators = market_data.get('indicators', {})
            adx = indicators.get('adx', {}).get('value', 0)
            bb_width = (indicators.get('bb_upper', 0) - indicators.get('bb_lower', 0)) / indicators.get('bb_middle', 1)
            atr = indicators.get('atr', 0)
            current_price = indicators.get('current_price', 0)
            
            # Calculate regime scores
            trend_score = 0
            range_score = 0
            volatile_score = 0
            
            # ADX contribution (0-1)
            if adx > 25:
                trend_score += 0.6
            elif adx > 20:
                trend_score += 0.3
            elif adx < 15:
                range_score += 0.4
            
            # BB Width contribution (0-1)
            if bb_width < 0.02:
                range_score += 0.4
            elif bb_width < 0.03:
                range_score += 0.2
            elif bb_width > 0.05:
                volatile_score += 0.3
            
            # ATR contribution (0-1)
            if atr > 0 and current_price > 0:
                atr_percent = atr / current_price
                if atr_percent > 0.03:
                    volatile_score += 0.4
                elif atr_percent > 0.02:
                    volatile_score += 0.2
            
            # Calculate final scores
            scores = {
                'trending': trend_score,
                'ranging': range_score,
                'volatile': volatile_score
            }
            
            # Determine primary regime
            primary_regime = max(scores.items(), key=lambda x: x[1])
            
            # Calculate confidence (0-1)
            total_score = sum(scores.values())
            confidence = primary_regime[1] / total_score if total_score > 0 else 0
            
            # Check for regime transition
            previous_regime = market_data.get('previous_regime', 'unknown')
            if previous_regime != primary_regime[0]:
                # Require higher confidence for regime changes
                if confidence < 0.6:
                    return {
                        'regime': previous_regime,
                        'confidence': confidence,
                        'scores': scores,
                        'is_transitioning': True
                    }
            
            return {
                'regime': primary_regime[0],
                'confidence': confidence,
                'scores': scores,
                'is_transitioning': False
            }
                
        except Exception as e:
            logger.error(f"Error determining market regime: {e}")
            return {
                'regime': 'unknown',
                'confidence': 0,
                'scores': {'trending': 0, 'ranging': 0, 'volatile': 0},
                'is_transitioning': False
            }
            
    def _calculate_indicators(self, market_data: Dict) -> Dict:
        """Calculate technical indicators."""
        try:
            ohlcv = market_data.get('klines', [])
            if not ohlcv:
                return {}
                
            closes = np.array([float(candle['close']) for candle in ohlcv])
            highs = np.array([float(candle['high']) for candle in ohlcv])
            lows = np.array([float(candle['low']) for candle in ohlcv])
            volumes = np.array([float(candle['volume']) for candle in ohlcv])
            
            # Calculate basic indicators
            sma20 = np.mean(closes[-20:])
            sma50 = np.mean(closes[-50:])
            rsi = self._calculate_rsi(closes)
            
            return {
                'sma20': float(sma20),
                'sma50': float(sma50),
                'rsi': float(rsi[-1]),
                'volume_ma': float(np.mean(volumes[-20:])),
                'atr': float(self._calculate_atr(highs, lows, closes)[-1])
            }
            
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return {}
            
    async def _generate_regime_signal(self, market_data: Dict, regime: str, indicators: Dict) -> Optional[Dict]:
        """Generate signal based on market regime."""
        try:
            if regime == 'trending':
                return self._generate_trending_signal(market_data, indicators)
            elif regime == 'ranging':
                return self._generate_ranging_signal(market_data, indicators)
            else:  # volatile
                return self._generate_volatile_signal(market_data, indicators)
                
        except Exception as e:
            logger.error(f"Error generating regime signal: {e}")
            return None
            
    def _calculate_levels(self, market_data: Dict, direction: str) -> Tuple[float, float, float]:
        """Calculate entry, take profit, and stop loss levels using structure and volume clusters."""
        try:
            current_price = float(market_data['klines'][-1]['close'])
            
            # Get indicators and structure levels
            indicators = market_data.get('indicators', {})
            structure_levels = self._find_nearest_structure_level(indicators, current_price, direction)
            
            # Calculate volume clusters
            volume_clusters = self.candle_detector.detect(
                market_data['symbol'],
                {
                    'close_prices': [float(c['close']) for c in market_data['klines']],
                    'high_prices': [float(c['high']) for c in market_data['klines']],
                    'low_prices': [float(c['low']) for c in market_data['klines']],
                    'atr': indicators.get('atr', 0),
                    'atr_trend': indicators.get('atr_trend', 0),
                    'recent_volumes': [float(c['volume']) for c in market_data['klines'][-10:]],
                    'avg_recent_volume': np.mean([float(c['volume']) for c in market_data['klines'][-5:]]),
                    'overall_avg_volume': np.mean([float(c['volume']) for c in market_data['klines']]),
                    'current_price': current_price
                },
                {}
            )
            
            # Use volume cluster levels if available
            if volume_clusters:
                return (
                    volume_clusters['entry'],
                    volume_clusters['take_profit'],
                    volume_clusters['stop_loss']
                )
            
            # Fallback to structure-based levels
            if structure_levels:
                if direction == 'LONG':
                    entry = current_price
                    tp = structure_levels['next_resistance'] if structure_levels['next_resistance'] else (entry + (2 * indicators.get('atr', 0)))
                    sl = structure_levels['support'] if structure_levels['support'] else (entry - indicators.get('atr', 0))
                else:  # SHORT
                    entry = current_price
                    tp = structure_levels['next_support'] if structure_levels['next_support'] else (entry - (2 * indicators.get('atr', 0)))
                    sl = structure_levels['resistance'] if structure_levels['resistance'] else (entry + indicators.get('atr', 0))
                
                return entry, tp, sl
            
            # Fallback to ATR-based levels if no structure found
            atr = indicators.get('atr', 0)
            if direction == 'LONG':
                entry = current_price
                tp = entry + (2 * atr)
                sl = entry - atr
            else:  # SHORT
                entry = current_price
                tp = entry - (2 * atr)
                sl = entry + atr
            
            return entry, tp, sl
            
        except Exception as e:
            logger.error(f"Error calculating price levels: {e}")
            return None, None, None
            
    def _calculate_rsi(self, data: np.ndarray, period: int = 14) -> np.ndarray:
        """Calculate Relative Strength Index."""
        delta = np.diff(data)
        gain = (delta > 0) * delta
        loss = (delta < 0) * -delta
        
        avg_gain = np.mean(gain[:period])
        avg_loss = np.mean(loss[:period])
        
        for i in range(period, len(delta)):
            avg_gain = (avg_gain * (period - 1) + gain[i]) / period
            avg_loss = (avg_loss * (period - 1) + loss[i]) / period
            
        rs = avg_gain / avg_loss if avg_loss != 0 else 0
        rsi = 100 - (100 / (1 + rs))
        
        return np.concatenate(([np.nan], rsi))
        
    def _calculate_atr(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> np.ndarray:
        """Calculate Average True Range."""
        tr1 = np.abs(highs[1:] - lows[1:])
        tr2 = np.abs(highs[1:] - closes[:-1])
        tr3 = np.abs(lows[1:] - closes[:-1])
        
        tr = np.maximum(np.maximum(tr1, tr2), tr3)
        atr = np.mean(tr[:period])
        
        for i in range(period, len(tr)):
            atr = (atr * (period - 1) + tr[i]) / period
            
        return np.concatenate(([np.nan], atr))
            
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
        """Calculate recent swing highs and lows with wick filters and clustering."""
        try:
            highs = indicators.get('highs', [])
            lows = indicators.get('lows', [])
            closes = indicators.get('closes', [])
            volumes = indicators.get('volumes', [])
            
            if len(highs) < lookback or len(lows) < lookback:
                return {'highs': [], 'lows': []}
            
            # Calculate average candle body size
            body_sizes = [abs(closes[i] - closes[i-1]) for i in range(1, len(closes))]
            avg_body = np.mean(body_sizes)
            
            # Calculate average wick size
            wick_sizes = []
            for i in range(len(highs)):
                upper_wick = highs[i] - max(closes[i], closes[i-1] if i > 0 else closes[i])
                lower_wick = min(closes[i], closes[i-1] if i > 0 else closes[i]) - lows[i]
                wick_sizes.append(max(upper_wick, lower_wick))
            avg_wick = np.mean(wick_sizes)
            
            # Find swing highs with wick filter
            swing_highs = []
            for i in range(2, len(highs) - 2):
                # Check if it's a swing high
                if highs[i] > highs[i-1] and highs[i] > highs[i-2] and \
                   highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                    # Check if the wick is not too large
                    upper_wick = highs[i] - max(closes[i], closes[i-1])
                    if upper_wick <= avg_wick * 1.5:  # Allow wicks up to 1.5x average
                        swing_highs.append(highs[i])
                
            # Find swing lows with wick filter
            swing_lows = []
            for i in range(2, len(lows) - 2):
                # Check if it's a swing low
                if lows[i] < lows[i-1] and lows[i] < lows[i-2] and \
                   lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                    # Check if the wick is not too large
                    lower_wick = min(closes[i], closes[i-1]) - lows[i]
                    if lower_wick <= avg_wick * 1.5:  # Allow wicks up to 1.5x average
                        swing_lows.append(lows[i])
            
            # Cluster nearby levels
            def cluster_levels(levels: List[float], threshold: float = 0.002) -> List[float]:
                if not levels:
                    return []
                    
                clusters = []
                current_cluster = [levels[0]]
                
                for level in sorted(levels)[1:]:
                    if abs(level - np.mean(current_cluster)) / np.mean(current_cluster) <= threshold:
                        current_cluster.append(level)
                    else:
                        clusters.append(np.mean(current_cluster))
                        current_cluster = [level]
                
                if current_cluster:
                    clusters.append(np.mean(current_cluster))
                
                return clusters
            
            # Cluster swing levels
            clustered_highs = cluster_levels(swing_highs)
            clustered_lows = cluster_levels(swing_lows)
            
            # Filter clusters by volume
            def filter_by_volume(levels: List[float], is_high: bool) -> List[float]:
                filtered_levels = []
                for level in levels:
                    # Find candles near this level
                    nearby_candles = []
                    for i in range(len(closes)):
                        if is_high and highs[i] >= level * 0.995 and highs[i] <= level * 1.005:
                            nearby_candles.append(volumes[i])
                        elif not is_high and lows[i] >= level * 0.995 and lows[i] <= level * 1.005:
                            nearby_candles.append(volumes[i])
                    
                    # Keep level if it has significant volume
                    if nearby_candles and np.mean(nearby_candles) > np.mean(volumes) * 0.8:
                        filtered_levels.append(level)
                
                return filtered_levels
            
            # Apply volume filtering
            volume_filtered_highs = filter_by_volume(clustered_highs, True)
            volume_filtered_lows = filter_by_volume(clustered_lows, False)
            
            return {
                'highs': sorted(volume_filtered_highs),
                'lows': sorted(volume_filtered_lows)
            }
            
        except Exception as e:
            logger.error(f"Error calculating swing levels: {e}")
            return {'highs': [], 'lows': []}

    def _resample_dataframe(self, df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
        """Resample OHLCV data to a different timeframe."""
        try:
            logger.debug(f"Starting resampling to {timeframe} timeframe")
            
            # Create a copy to avoid modifying the original
            df = df.copy()
            logger.debug(f"Original dataframe shape: {df.shape}")
            
            # Ensure all required columns exist
            required_columns = ['open', 'high', 'low', 'close', 'volume']
            if not all(col in df.columns for col in required_columns):
                logger.error(f"Missing required columns. Available columns: {df.columns.tolist()}")
                return pd.DataFrame()
            
            # Convert numeric columns
            for col in required_columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                logger.debug(f"Column {col} stats - min: {df[col].min()}, max: {df[col].max()}, mean: {df[col].mean()}")
            
            # Handle timestamp
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                logger.debug("Using 'timestamp' column for datetime")
            elif 'time' in df.columns:
                df['timestamp'] = pd.to_datetime(df['time'], unit='ms')
                logger.debug("Using 'time' column for datetime")
            else:
                logger.error("No timestamp column found in dataframe")
                return pd.DataFrame()
            
            # Set timestamp as index
            df.set_index('timestamp', inplace=True)
            
            # Sort by timestamp
            df.sort_index(inplace=True)
            logger.debug(f"Data range: {df.index.min()} to {df.index.max()}")
            
            # Calculate minimum required data points based on timeframe
            min_points = {
                '1m': 20,
                '5m': 20,
                '15m': 20,
                '1h': 20,
                '4h': 20,
                '1d': 20
            }.get(timeframe, 20)
            
            if len(df) < min_points:
                logger.warning(f"Insufficient data points for resampling: {len(df)} < {min_points}")
                return pd.DataFrame()
            
            # Resample OHLCV data
            logger.debug(f"Resampling data to {timeframe} timeframe")
            resampled = df.resample(timeframe).agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            })
            
            # Drop any rows with NaN values
            initial_len = len(resampled)
            resampled.dropna(inplace=True)
            if len(resampled) < initial_len:
                logger.warning(f"Dropped {initial_len - len(resampled)} rows with NaN values after resampling")
            
            # Reset index to make timestamp a column again
            resampled.reset_index(inplace=True)
            
            # Validate resampled data
            if len(resampled) < min_points:
                logger.warning(f"Insufficient data points after resampling: {len(resampled)} < {min_points}")
                return pd.DataFrame()
            
            logger.debug(f"Successfully resampled data. New shape: {resampled.shape}")
            return resampled
            
        except Exception as e:
            logger.error(f"Error resampling dataframe: {e}")
            return pd.DataFrame()

    def _calculate_mtf_alignment(
        self,
        symbol: str,
        indicators: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Calculate multi-timeframe alignment.
        
        Args:
            symbol: Trading pair symbol
            indicators: Dictionary of calculated indicators
            
        Returns:
            Optional[Dict[str, Any]]: MTF alignment data or None if not available
        """
        try:
            # Get timeframes from strategy config
            timeframes = self.strategy_config.timeframes
            if not timeframes or len(timeframes) < 2:
                return None
            
            # Calculate alignment for each timeframe
            alignments = {}
            for tf in timeframes:
                if tf not in indicators:
                    continue
                    
                tf_indicators = indicators[tf]
                
                # Check trend alignment
                trend_aligned = (
                    tf_indicators.get('macd', {}).get('histogram', 0) > 0 and
                    tf_indicators.get('rsi', 0) > 50 and
                    tf_indicators.get('adx', 0) > 25
                )
                
                # Check momentum alignment
                momentum_aligned = (
                    tf_indicators.get('rsi', 0) > 50 and
                    tf_indicators.get('stoch_k', 0) > tf_indicators.get('stoch_d', 0)
                )
                
                # Check volatility alignment
                volatility_aligned = (
                    tf_indicators.get('bb_width', 0) < 0.1 and
                    tf_indicators.get('atr', 0) > 0
                )
                
                alignments[tf] = {
                    'trend': trend_aligned,
                    'momentum': momentum_aligned,
                    'volatility': volatility_aligned
                }
            
            if not alignments:
                return None
            
            # Calculate overall alignment strength
            total_alignments = 0
            aligned_count = 0
            
            for tf_data in alignments.values():
                for aligned in tf_data.values():
                    total_alignments += 1
                    if aligned:
                        aligned_count += 1
            
            strength = aligned_count / total_alignments if total_alignments > 0 else 0
            
            return {
                'alignments': alignments,
                'strength': strength,
                'timeframes': list(alignments.keys())
            }
            
        except Exception as e:
            logger.error(f"Error calculating MTF alignment for {symbol}: {str(e)}")
            return None

    def _generate_trending_signal(self, market_data: Dict, indicators: Dict) -> Optional[Dict]:
        """Generate signal for trending market regime."""
        try:
            # Get trend direction and strength
            adx = indicators.get('adx', {}).get('value', 0)
            di_plus = indicators.get('adx', {}).get('di_plus', 0)
            di_minus = indicators.get('adx', {}).get('di_minus', 0)
            
            # Calculate ATR and structure levels
            atr = indicators.get('atr', 0)
            current_price = market_data.get('current_price', 0)
            
            # Determine trend direction
            if di_plus > di_minus and adx > 25:  # Strong uptrend
                direction = 'LONG'
                entry = current_price
                stop_loss = entry - (atr * 2.0)  # Wider stop in trending market
                take_profit = entry + (atr * 3.0)  # Higher reward target
            elif di_minus > di_plus and adx > 25:  # Strong downtrend
                direction = 'SHORT'
                entry = current_price
                stop_loss = entry + (atr * 2.0)
                take_profit = entry - (atr * 3.0)
            else:
                return None  # Not a strong enough trend
                
            # Calculate confidence based on trend strength
            confidence = min(adx / 50, 1.0)  # Normalize ADX to 0-1 range
            
            return {
                'direction': direction,
                'entry': entry,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'confidence': confidence,
                'regime': 'TRENDING',
                'indicators': {
                    'adx': adx,
                    'di_plus': di_plus,
                    'di_minus': di_minus,
                    'atr': atr
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating trending signal: {e}")
            return None
            
    def _generate_ranging_signal(self, market_data: Dict, indicators: Dict) -> Optional[Dict]:
        """Generate signal for ranging market regime."""
        try:
            # Get range boundaries
            bb = indicators.get('bollinger_bands', {})
            bb_upper = bb.get('upper', 0)
            bb_lower = bb.get('lower', 0)
            bb_middle = bb.get('middle', 0)
            current_price = market_data.get('current_price', 0)
            
            # Calculate ATR for stop loss
            atr = indicators.get('atr', 0)
            
            # Check if price is near range boundaries
            range_size = bb_upper - bb_lower
            if range_size == 0:
                return None
                
            price_position = (current_price - bb_lower) / range_size
            
            # Generate signals based on price position
            if price_position < 0.2:  # Near lower boundary
                direction = 'LONG'
                entry = current_price
                stop_loss = entry - (atr * 1.5)  # Tighter stop in ranging market
                take_profit = bb_middle  # Target middle of range
            elif price_position > 0.8:  # Near upper boundary
                direction = 'SHORT'
                entry = current_price
                stop_loss = entry + (atr * 1.5)
                take_profit = bb_middle
            else:
                return None  # Price in middle of range
                
            # Calculate confidence based on range consistency
            bb_width = (bb_upper - bb_lower) / bb_middle
            confidence = max(0.6, 1.0 - (bb_width * 10))  # Higher confidence for tighter ranges
            
            return {
                'direction': direction,
                'entry': entry,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'confidence': confidence,
                'regime': 'RANGING',
                'indicators': {
                    'bb_upper': bb_upper,
                    'bb_lower': bb_lower,
                    'bb_middle': bb_middle,
                    'atr': atr
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating ranging signal: {e}")
            return None
            
    def _generate_volatile_signal(self, market_data: Dict, indicators: Dict) -> Optional[Dict]:
        """Generate signal for volatile market regime."""
        try:
            # Get volatility metrics
            atr = indicators.get('atr', 0)
            current_price = market_data.get('current_price', 0)
            atr_percent = atr / current_price if current_price > 0 else 0
            
            # Get recent price action
            recent_highs = market_data.get('highs', [])[-5:]
            recent_lows = market_data.get('lows', [])[-5:]
            
            if not recent_highs or not recent_lows:
                return None
                
            # Calculate volatility-based levels
            recent_range = max(recent_highs) - min(recent_lows)
            range_percent = recent_range / current_price if current_price > 0 else 0
            
            # Only generate signals if volatility is high enough
            if atr_percent < 0.02 or range_percent < 0.03:  # Minimum volatility thresholds
                return None
                
            # Determine direction based on recent price action
            if current_price > (max(recent_highs) + min(recent_lows)) / 2:
                direction = 'LONG'
                entry = current_price
                stop_loss = entry - (atr * 2.5)  # Wider stop in volatile market
                take_profit = entry + (atr * 4.0)  # Higher reward target
            else:
                direction = 'SHORT'
                entry = current_price
                stop_loss = entry + (atr * 2.5)
                take_profit = entry - (atr * 4.0)
                
            # Calculate confidence based on volatility
            confidence = max(0.5, 1.0 - (atr_percent * 20))  # Lower confidence in high volatility
            
            return {
                'direction': direction,
                'entry': entry,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'confidence': confidence,
                'regime': 'VOLATILE',
                'indicators': {
                    'atr': atr,
                    'atr_percent': atr_percent,
                    'range_percent': range_percent
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating volatile signal: {e}")
            return None

    def generate_signals(
        self,
        symbol: str,
        indicators: Dict[str, Any],
        confidence: float
    ) -> Optional[Dict[str, Any]]:
        """Generate trading signals based on indicators and market data.
        
        Args:
            symbol: Trading pair symbol
            indicators: Dictionary of calculated indicators
            confidence: Base confidence score
            
        Returns:
            Optional[Dict[str, Any]]: Signal data or None if no signal
        """
        try:
            # Calculate multi-timeframe alignment
            mtf_alignment = self._calculate_mtf_alignment(symbol, indicators)
            if not mtf_alignment:
                logger.debug(f"No MTF alignment data for {symbol}")
                return None
            
            # Get market regime
            regime = self._assess_market_regime(indicators)
            
            # Check for strong trend
            if regime == 'trending':
                adx = indicators.get('adx', 0)
                if adx > self.strategy_config.trend_thresholds['strong']:
                    # Check for pullback to EMA
                    current_price = indicators.get('close', 0)
                    ema = indicators.get('ema', 0)
                    if ema and current_price:
                        # Calculate distance from EMA as percentage
                        ema_distance = abs(current_price - ema) / ema * 100
                        
                        # Only allow entry if price has pulled back to EMA
                        if ema_distance > self.strategy_config.trend_thresholds['ema_pullback']:
                            logger.info(
                                f"Suppressing scalping signal for {symbol} - "
                                f"Strong trend (ADX: {adx:.2f}) without pullback "
                                f"(EMA distance: {ema_distance:.2f}%)"
                            )
                            return None
                    
                    # Check for overbought/oversold conditions
                    rsi = indicators.get('rsi', 50)
                    if (rsi > 70 or rsi < 30):  # Price is overbought/oversold
                        logger.info(
                            f"Suppressing scalping signal for {symbol} - "
                            f"Strong trend (ADX: {adx:.2f}) with extreme RSI ({rsi:.2f})"
                        )
                        return None
            
            # Generate signal based on regime
            signal = None
            if regime == 'trending':
                signal = self._generate_trending_signal(symbol, indicators)
            elif regime == 'ranging':
                signal = self._generate_ranging_signal(symbol, indicators)
            elif regime == 'volatile':
                signal = self._generate_volatile_signal(symbol, indicators)
            
            if signal:
                # Calibrate confidence based on historical outcomes
                calibrated_confidence = self.confidence_calibrator.calibrate_confidence(
                    raw_confidence=confidence,
                    regime=regime,
                    mtf_alignment=mtf_alignment
                )
                
                # Add MTF alignment data to signal
                signal.update({
                    'mtf_alignment': mtf_alignment,
                    'regime': regime,
                    'confidence': calibrated_confidence,
                    'raw_confidence': confidence  # Keep original confidence for reference
                })
                
                # Log signal generation
                logger.info(
                    f"Generated {signal['signal_type']} signal for {symbol} "
                    f"(raw confidence: {confidence:.2f}, "
                    f"calibrated: {calibrated_confidence:.2f}, "
                    f"alignment: {mtf_alignment['strength']:.2f}, "
                    f"regime: {regime})"
                )
                
                return signal
            
            return None
            
        except Exception as e:
            logger.error(f"Error generating signals for {symbol}: {str(e)}")
            return None 