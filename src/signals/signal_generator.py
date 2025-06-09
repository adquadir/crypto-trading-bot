from typing import Dict, List, Optional, Tuple, Any
import json
import logging
from datetime import datetime

import numpy as np
import pandas as pd
import ta
from ta.momentum import RSIIndicator
from ta.trend import (
    ADXIndicator,
    CCIIndicator,
    MACD,
    SMAIndicator,
    EMAIndicator
)
from ta.volatility import BollingerBands, AverageTrueRange

from ..strategy.dynamic_config import strategy_config
from ..strategies.candle_cluster.detector import CandleClusterDetector
from .confidence_calibrator import ConfidenceCalibrator
from .signal_tracker import SignalTracker, SignalProfile

logger = logging.getLogger(__name__)

def safe_float(value) -> float:
    """Safely convert a value to float, handling None and NaN."""
    try:
        if pd.isna(value) or value is None:
            return 0.0
        return float(value)
    except (ValueError, TypeError):
        return 0.0

class SignalGenerator:
    def __init__(self):
        self.signals = []
        self.indicators = {}
        self.strategy_config = strategy_config
        self.strategy_config.set_profile("moderate")  # Default to moderate profile
        self.candle_detector = CandleClusterDetector()
        self.signal_tracker = SignalTracker()
        self.confidence_calibrator = ConfidenceCalibrator()
        
    def calculate_indicators(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate technical indicators for the given dataframe."""
        indicators = {}
        
        try:
            # MACD
            macd = ta.trend.MACD(df['close'])
            indicators['macd'] = {
                'value': safe_float(macd.macd().iloc[-1]),
                'signal': safe_float(macd.macd_signal().iloc[-1]),
                'histogram': safe_float(macd.macd_diff().iloc[-1])
            }
        except Exception as e:
            logger.error(f"Error calculating MACD: {str(e)}")
            indicators['macd'] = {'value': 0, 'signal': 0, 'histogram': 0}
        
        try:
            # RSI
            rsi = ta.momentum.RSIIndicator(df['close'])
            indicators['rsi'] = safe_float(rsi.rsi().iloc[-1])
        except Exception as e:
            logger.error(f"Error calculating RSI: {str(e)}")
            indicators['rsi'] = 50
        
        try:
            # Bollinger Bands
            bb = ta.volatility.BollingerBands(df['close'])
            indicators['bb'] = {
                'upper': safe_float(bb.bollinger_hband().iloc[-1]),
                'middle': safe_float(bb.bollinger_mavg().iloc[-1]),
                'lower': safe_float(bb.bollinger_lband().iloc[-1])
            }
        except Exception as e:
            logger.error(f"Error calculating Bollinger Bands: {str(e)}")
            indicators['bb'] = {'upper': 0, 'middle': 0, 'lower': 0}
        
        try:
            # ADX
            adx = ta.trend.ADXIndicator(df['high'], df['low'], df['close'])
            indicators['adx'] = safe_float(adx.adx().iloc[-1])
        except Exception as e:
            logger.error(f"Error calculating ADX: {str(e)}")
            indicators['adx'] = 0
        
        try:
            # ATR
            atr = ta.volatility.AverageTrueRange(df['high'], df['low'], df['close'])
            indicators['atr'] = safe_float(atr.average_true_range().iloc[-1])
        except Exception as e:
            logger.error(f"Error calculating ATR: {str(e)}")
            indicators['atr'] = 0
        
        try:
            # CCI
            cci = ta.trend.CCIIndicator(df['high'], df['low'], df['close'])
            indicators['cci'] = safe_float(cci.cci().iloc[-1])
        except Exception as e:
            logger.error(f"Error calculating CCI: {str(e)}")
            indicators['cci'] = 0
        
        return indicators

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
            logger.info(
                f"Data freshness for {symbol}: "
                f"{json.dumps({k: f'{v:.1f}s' for k, v in freshness_metrics.items()})}"
            )

            # Check if any critical data is too stale
            max_freshness = {
                'ohlcv': 60,  # 1 minute
                'orderbook': 5,  # 5 seconds
                'ticker': 5,  # 5 seconds
                'open_interest': 60  # 1 minute
            }

            stale_data = {
                k: v for k, v in freshness_metrics.items()
                if v > max_freshness[k]
            }
            if stale_data:
                self.signal_tracker.log_rejection(
                    symbol,
                    f"Stale data detected: "
                    f"{json.dumps({k: f'{v:.1f}s' for k, v in stale_data.items()})}",
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
                'indicators': indicators,
                'market_regime': regime,
                'data_freshness': freshness_metrics
            }

        except Exception as e:
            logger.error(f"Error generating signals: {str(e)}")
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
            bb = indicators.get('bb', {})
            bb_upper = bb.get('upper', 0)
            bb_lower = bb.get('lower', 0)
            bb_middle = bb.get('middle', 0)
            
            # Get RSI
            rsi = indicators.get('rsi', 50)
            
            # Get current price
            current_price = market_data.get('current_price', 0)
            
            # Calculate range width
            range_width = (bb_upper - bb_lower) / bb_middle if bb_middle > 0 else 0
            
            # Check if price is near range boundaries
            if current_price <= bb_lower * 1.01 and rsi < 30:  # Near lower boundary and oversold
                direction = 'LONG'
                entry = current_price
                stop_loss = entry - (range_width * 0.5)  # Tighter stop in ranging market
                take_profit = bb_middle  # Target middle of range
            elif current_price >= bb_upper * 0.99 and rsi > 70:  # Near upper boundary and overbought
                direction = 'SHORT'
                entry = current_price
                stop_loss = entry + (range_width * 0.5)
                take_profit = bb_middle
            else:
                return None  # Not at range boundaries
                
            # Calculate confidence based on range strength
            confidence = 0.7  # Base confidence for range trades
            
            # Adjust confidence based on RSI extremes
            if direction == 'LONG' and rsi < 20:
                confidence += 0.1
            elif direction == 'SHORT' and rsi > 80:
                confidence += 0.1
                
            return {
                'direction': direction,
                'entry': entry,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'confidence': min(confidence, 1.0),
                'regime': 'RANGING',
                'indicators': {
                    'rsi': rsi,
                    'bb_upper': bb_upper,
                    'bb_lower': bb_lower,
                    'bb_middle': bb_middle,
                    'range_width': range_width
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
            bb_width = indicators.get('bb_width', 0)
            
            # Get current price and recent highs/lows
            current_price = market_data.get('current_price', 0)
            recent_high = max([float(c['high']) for c in market_data.get('klines', [])[-5:]])
            recent_low = min([float(c['low']) for c in market_data.get('klines', [])[-5:]])
            
            # Calculate volatility range
            vol_range = recent_high - recent_low
            
            # Determine if price is near recent extremes
            if current_price <= recent_low * 1.01:  # Near recent low
                direction = 'LONG'
                entry = current_price
                stop_loss = entry - (atr * 1.5)  # Tighter stop in volatile market
                take_profit = entry + (atr * 2.0)  # Quick profit target
            elif current_price >= recent_high * 0.99:  # Near recent high
                direction = 'SHORT'
                entry = current_price
                stop_loss = entry + (atr * 1.5)
                take_profit = entry - (atr * 2.0)
            else:
                return None  # Not at volatility extremes
                
            # Calculate confidence based on volatility
            confidence = 0.6  # Base confidence for volatile trades
            
            # Adjust confidence based on volatility strength
            if bb_width > 0.1:  # Very volatile
                confidence -= 0.1
            elif bb_width < 0.05:  # Less volatile
                confidence += 0.1
                
            return {
                'direction': direction,
                'entry': entry,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'confidence': min(confidence, 1.0),
                'regime': 'VOLATILE',
                'indicators': {
                    'atr': atr,
                    'bb_width': bb_width,
                    'vol_range': vol_range,
                    'recent_high': recent_high,
                    'recent_low': recent_low
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating volatile signal: {e}")
            return None

    def should_close_position(self, position: Dict, market_data: Dict) -> bool:
        """Determine if a position should be closed based on market conditions."""
        try:
            symbol = position.get('symbol')
            if not symbol:
                return False
                
            # Get current indicators
            indicators = self._calculate_indicators(market_data)
            
            # Get position details
            position_amt = float(position.get('positionAmt', 0))
            entry_price = float(position.get('entryPrice', 0))
            current_price = float(market_data.get('close', 0))
            
            if position_amt == 0:
                return False
                
            # Check for trend reversal
            if position_amt > 0:  # Long position
                # Check if trend has reversed to bearish
                if (indicators['macd']['histogram'] < 0 and 
                    indicators['rsi'] > 70 and 
                    current_price < indicators['bb']['middle']):
                    logger.info(f"Closing long position for {symbol} - Trend reversal detected")
                    return True
            else:  # Short position
                # Check if trend has reversed to bullish
                if (indicators['macd']['histogram'] > 0 and 
                    indicators['rsi'] < 30 and 
                    current_price > indicators['bb']['middle']):
                    logger.info(f"Closing short position for {symbol} - Trend reversal detected")
                    return True
                    
            # Check for volatility expansion
            atr = indicators.get('atr', 0)
            if atr > self.strategy_config.get('max_atr', 0.05):
                logger.info(f"Closing position for {symbol} - Excessive volatility")
                return True
                
            # Check for momentum loss
            if abs(indicators['macd']['histogram']) < abs(indicators['macd']['histogram'] * 0.5):
                logger.info(f"Closing position for {symbol} - Momentum loss")
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Error in should_close_position: {e}")
            return False

    def should_update_levels(self, position: Dict, market_data: Dict) -> bool:
        """Determine if position levels should be updated based on market conditions."""
        try:
            symbol = position.get('symbol')
            if not symbol:
                return False
                
            # Get current indicators
            indicators = self._calculate_indicators(market_data)
            
            # Get position details
            position_amt = float(position.get('positionAmt', 0))
            entry_price = float(position.get('entryPrice', 0))
            current_price = float(market_data.get('close', 0))
            
            if position_amt == 0:
                return False
                
            # Check for significant price movement
            price_change = abs(current_price - entry_price) / entry_price
            if price_change > 0.02:  # 2% price movement
                logger.info(f"Updating levels for {symbol} - Significant price movement")
                return True
                
            # Check for volatility change
            atr = indicators.get('atr', 0)
            if atr > self.strategy_config.get('atr_threshold', 0.02):
                logger.info(f"Updating levels for {symbol} - Volatility change")
                return True
                
            # Check for trend strength change
            adx = indicators.get('adx', 0)
            if adx > 25:  # Strong trend
                logger.info(f"Updating levels for {symbol} - Trend strength change")
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Error in should_update_levels: {e}")
            return False

    def calculate_new_levels(self, position: Dict, market_data: Dict) -> Dict:
        """Calculate new stop loss and take profit levels based on market conditions."""
        try:
            symbol = position.get('symbol')
            if not symbol:
                return {}
                
            # Get current indicators
            indicators = self._calculate_indicators(market_data)
            
            # Get position details
            position_amt = float(position.get('positionAmt', 0))
            entry_price = float(position.get('entryPrice', 0))
            current_price = float(market_data.get('close', 0))
            
            if position_amt == 0:
                return {}
                
            # Calculate ATR-based levels
            atr = indicators.get('atr', 0)
            atr_multiplier = self.strategy_config.get('atr_multiplier', 2.0)
            
            # Calculate new levels
            if position_amt > 0:  # Long position
                # Move stop loss to break even or higher if in profit
                if current_price > entry_price:
                    new_sl = max(entry_price, current_price - (atr * atr_multiplier))
                else:
                    new_sl = current_price - (atr * atr_multiplier)
                    
                # Adjust take profit based on trend strength
                if indicators['adx'] > 25:  # Strong trend
                    new_tp = current_price + (atr * atr_multiplier * 2)
                else:
                    new_tp = current_price + (atr * atr_multiplier)
                    
            else:  # Short position
                # Move stop loss to break even or lower if in profit
                if current_price < entry_price:
                    new_sl = min(entry_price, current_price + (atr * atr_multiplier))
                else:
                    new_sl = current_price + (atr * atr_multiplier)
                    
                # Adjust take profit based on trend strength
                if indicators['adx'] > 25:  # Strong trend
                    new_tp = current_price - (atr * atr_multiplier * 2)
                else:
                    new_tp = current_price - (atr * atr_multiplier)
                    
            # Ensure minimum distance between current price and levels
            min_distance = atr * 0.5
            if position_amt > 0:  # Long position
                new_sl = min(new_sl, current_price - min_distance)
                new_tp = max(new_tp, current_price + min_distance)
            else:  # Short position
                new_sl = max(new_sl, current_price + min_distance)
                new_tp = min(new_tp, current_price - min_distance)
                
            logger.info(f"New levels for {symbol}: SL={new_sl:.2f}, TP={new_tp:.2f}")
            return {
                'stop_loss': new_sl,
                'take_profit': new_tp
            }
            
        except Exception as e:
            logger.error(f"Error in calculate_new_levels: {e}")
            return {} 