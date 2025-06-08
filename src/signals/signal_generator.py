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
from .signal_tracker import SignalTracker, SignalProfile
import json

logger = logging.getLogger(__name__)

class SignalGenerator:
    def __init__(self):
        self.signals = []
        self.indicators = {}
        self.strategy_config = DynamicStrategyConfig()
        self.strategy_config.set_profile("moderate")  # Default to moderate profile
        self.candle_detector = CandleClusterDetector()
        self.signal_tracker = SignalTracker()
        
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

    def _calculate_mtf_alignment(self, indicators: Dict) -> Dict:
        """Calculate multi-timeframe alignment with enhanced analysis."""
        try:
            # Get indicators from all timeframes
            tf_indicators = {
                '1m': indicators.get('1m', {}),
                '5m': indicators.get('5m', {}),
                '15m': indicators.get('15m', {})
            }
            
            # Validate minimum data points
            min_data_points = 20
            for tf, tf_data in tf_indicators.items():
                if len(tf_data.get('close', [])) < min_data_points:
                    logger.warning(f"Insufficient data points for {tf} timeframe")
                    return {'strength': 0.0, 'trend': 'NEUTRAL', 'details': {}}
            
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
                macd_alignment = self._calculate_macd_alignment(indicators.get('macd', {}), indicators.get('macd', {}))
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