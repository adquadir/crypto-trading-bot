from typing import Dict, List, Optional, Tuple, Any
import json
import logging
from datetime import datetime, timedelta
import time

import numpy as np
import pandas as pd
import ta
from ta.momentum import RSIIndicator
from ta.trend import ADXIndicator, CCIIndicator, MACD, SMAIndicator, EMAIndicator
from ta.volatility import BollingerBands, AverageTrueRange

from src.strategy.dynamic_config import strategy_config
from src.strategies.candle_cluster.detector import CandleClusterDetector
from .confidence_calibrator import ConfidenceCalibrator
from .signal_tracker import SignalTracker, SignalProfile
from src.market_data.exchange_client import ExchangeClient
from src.models.signal import TradingSignal
from src.models.strategy import Strategy

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
        
    async def initialize(self):
        """Async initialization hook for compatibility with bot startup."""
        pass

    def calculate_indicators(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate technical indicators for the given dataframe."""
        indicators = {}
        
        try:
            # MACD
            macd = ta.trend.MACD(df["close"])
            indicators["macd"] = {
                "value": safe_float(macd.macd().iloc[-1]),
                "signal": safe_float(macd.macd_signal().iloc[-1]),
                "histogram": safe_float(macd.macd_diff().iloc[-1]),
            }
        except Exception as e:
            logger.error(f"Error calculating MACD: {str(e)}")
            indicators["macd"] = {"value": 0, "signal": 0, "histogram": 0}
        
        try:
            # RSI
            rsi = ta.momentum.RSIIndicator(df["close"])
            indicators["rsi"] = safe_float(rsi.rsi().iloc[-1])
        except Exception as e:
            logger.error(f"Error calculating RSI: {str(e)}")
            indicators["rsi"] = 50
        
        try:
            # Bollinger Bands
            bb = ta.volatility.BollingerBands(df["close"])
            indicators["bb_upper"] = safe_float(bb.bollinger_hband().iloc[-1])
            indicators["bb_middle"] = safe_float(bb.bollinger_mavg().iloc[-1])
            indicators["bb_lower"] = safe_float(bb.bollinger_lband().iloc[-1])
            indicators["bb_width"] = safe_float(
                (indicators["bb_upper"] - indicators["bb_lower"])
                / indicators["bb_middle"]
            )
        except Exception as e:
            logger.error(f"Error calculating Bollinger Bands: {str(e)}")
            indicators["bb_upper"] = 0
            indicators["bb_middle"] = 0
            indicators["bb_lower"] = 0
            indicators["bb_width"] = 0
        
        try:
            # ADX
            adx = ta.trend.ADXIndicator(df["high"], df["low"], df["close"])
            indicators["adx"] = safe_float(adx.adx().iloc[-1])
            indicators["adx_trend"] = safe_float(
                adx.adx().iloc[-1] - adx.adx().iloc[-2]
            )
        except Exception as e:
            logger.error(f"Error calculating ADX: {str(e)}")
            indicators["adx"] = 0
            indicators["adx_trend"] = 0
        
        try:
            # ATR
            atr = ta.volatility.AverageTrueRange(df["high"], df["low"], df["close"])
            indicators["atr"] = safe_float(atr.average_true_range().iloc[-1])

            # Calculate ATR trend (positive if increasing, negative if decreasing)
            atr_values = atr.average_true_range()
            indicators["atr_trend"] = safe_float(
                atr_values.iloc[-1] - atr_values.iloc[-2]
            )
            indicators["atr_percent"] = safe_float(
                indicators["atr"] / df["close"].iloc[-1]
            )
        except Exception as e:
            logger.error(f"Error calculating ATR: {str(e)}")
            indicators["atr"] = 0
            indicators["atr_trend"] = 0
            indicators["atr_percent"] = 0

        try:
            # EMAs
            ema20 = ta.trend.EMAIndicator(df["close"], window=20)
            ema50 = ta.trend.EMAIndicator(df["close"], window=50)
            ema200 = ta.trend.EMAIndicator(df["close"], window=200)
            indicators["ema20"] = safe_float(ema20.ema_indicator().iloc[-1])
            indicators["ema50"] = safe_float(ema50.ema_indicator().iloc[-1])
            indicators["ema200"] = safe_float(ema200.ema_indicator().iloc[-1])

            # Calculate EMA trends
            indicators["ema20_trend"] = safe_float(
                ema20.ema_indicator().iloc[-1] - ema20.ema_indicator().iloc[-2]
            )
            indicators["ema50_trend"] = safe_float(
                ema50.ema_indicator().iloc[-1] - ema50.ema_indicator().iloc[-2]
            )
            indicators["ema200_trend"] = safe_float(
                ema200.ema_indicator().iloc[-1] - ema200.ema_indicator().iloc[-2]
            )
        except Exception as e:
            logger.error(f"Error calculating EMAs: {str(e)}")
            indicators["ema20"] = 0
            indicators["ema50"] = 0
            indicators["ema200"] = 0
            indicators["ema20_trend"] = 0
            indicators["ema50_trend"] = 0
            indicators["ema200_trend"] = 0

        try:
            # Volume MA
            volume_ma = ta.volume.VolumeWeightedAveragePrice(
                high=df["high"],
                low=df["low"],
                close=df["close"],
                volume=df["volume"],
                window=20,
            )
            indicators["volume_ma"] = safe_float(
                volume_ma.volume_weighted_average_price().iloc[-1]
            )

            # Calculate volume trend
            volume_values = df["volume"].values
            indicators["volume_trend"] = safe_float(
                volume_values[-1] - volume_values[-2]
            )
            indicators["volume_ratio"] = safe_float(
                volume_values[-1] / np.mean(volume_values[-20:])
            )
        except Exception as e:
            logger.error(f"Error calculating Volume MA: {str(e)}")
            indicators["volume_ma"] = 0
            indicators["volume_trend"] = 0
            indicators["volume_ratio"] = 0
        
        try:
            # CCI
            cci = ta.trend.CCIIndicator(df["high"], df["low"], df["close"])
            indicators["cci"] = safe_float(cci.cci().iloc[-1])
            indicators["cci_trend"] = safe_float(
                cci.cci().iloc[-1] - cci.cci().iloc[-2]
            )
        except Exception as e:
            logger.error(f"Error calculating CCI: {str(e)}")
            indicators["cci"] = 0
            indicators["cci_trend"] = 0

        try:
            # Stochastic Oscillator
            stoch = ta.momentum.StochasticOscillator(df["high"], df["low"], df["close"])
            indicators["stoch_k"] = safe_float(stoch.stoch().iloc[-1])
            indicators["stoch_d"] = safe_float(stoch.stoch_signal().iloc[-1])
            indicators["stoch_trend"] = safe_float(
                stoch.stoch().iloc[-1] - stoch.stoch().iloc[-2]
            )
        except Exception as e:
            logger.error(f"Error calculating Stochastic Oscillator: {str(e)}")
            indicators["stoch_k"] = 0
            indicators["stoch_d"] = 0
            indicators["stoch_trend"] = 0

        try:
            # Ichimoku Cloud
            ichimoku = ta.trend.IchimokuIndicator(df["high"], df["low"])
            indicators["tenkan_sen"] = safe_float(
                ichimoku.ichimoku_conversion_line().iloc[-1]
            )
            indicators["kijun_sen"] = safe_float(ichimoku.ichimoku_base_line().iloc[-1])
            indicators["senkou_span_a"] = safe_float(ichimoku.ichimoku_a().iloc[-1])
            indicators["senkou_span_b"] = safe_float(ichimoku.ichimoku_b().iloc[-1])
        except Exception as e:
            logger.error(f"Error calculating Ichimoku Cloud: {str(e)}")
            indicators["tenkan_sen"] = 0
            indicators["kijun_sen"] = 0
            indicators["senkou_span_a"] = 0
            indicators["senkou_span_b"] = 0

        # Add raw price data for structure analysis
        indicators["highs"] = df["high"].values
        indicators["lows"] = df["low"].values
        indicators["closes"] = df["close"].values
        indicators["volumes"] = df["volume"].values

        # Add price trends
        indicators["price_trend"] = safe_float(
            df["close"].iloc[-1] - df["close"].iloc[-2]
        )
        indicators["price_trend_5"] = safe_float(
            df["close"].iloc[-1] - df["close"].iloc[-5]
        )
        indicators["price_trend_10"] = safe_float(
            df["close"].iloc[-1] - df["close"].iloc[-10]
        )
        
        return indicators

    async def generate_signals(self, market_data: Dict) -> Optional[Dict]:
        """Generate trading signals based on market data."""
        try:
            symbol = market_data.get("symbol")
            if not symbol:
                return None

            # Calculate freshness metrics for each data type
            current_time = time.time()
            freshness_metrics = {
                "ohlcv": current_time - market_data.get("timestamp", current_time),
                "orderbook": current_time - market_data.get("timestamp", current_time),
                "ticker": current_time - market_data.get("timestamp", current_time),
                "open_interest": current_time
                - market_data.get("timestamp", current_time),
            }

            # Log freshness metrics
            logger.info(
                f"Data freshness for {symbol}: "
                f"{json.dumps({k: f'{v:.1f}s' for k, v in freshness_metrics.items()})}"
            )

            # Check if any critical data is too stale
            max_freshness = {
                "ohlcv": 1800,  # 30 minutes
                "orderbook": 300,  # 5 minutes
                "ticker": 300,  # 5 minutes
                "open_interest": 1800,  # 30 minutes
            }

            stale_data = {
                k: v for k, v in freshness_metrics.items() if v > max_freshness[k]
            }
            if stale_data:
                self.signal_tracker.log_rejection(
                    symbol,
                    f"Stale data detected: "
                    f"{json.dumps({k: f'{v:.1f}s' for k, v in stale_data.items()})}",
                    market_data,
                )
                return None

            # Convert klines data to DataFrame for indicator calculation
            klines = market_data.get("klines", [])
            if not klines:
                logger.warning(f"No klines data available for {symbol}")
                return None

            df = pd.DataFrame(klines)
            if df.empty:
                logger.warning(f"Empty DataFrame for {symbol}")
                return None

            # Calculate indicators
            indicators = self.calculate_indicators(df)
            if not indicators:
                logger.warning(f"Failed to calculate indicators for {symbol}")
                return None

            # Add indicators to market data for regime determination
            market_data["indicators"] = indicators

            # Determine market regime
            regime = self._determine_market_regime(market_data)
            if not regime:
                logger.warning(f"Could not determine market regime for {symbol}")
                return None

            # Log regime determination
            logger.info(
                f"Market regime for {symbol}: {regime['regime']} with confidence {regime['confidence']:.2f}"
            )

            # Generate signal based on regime
            signal = await self._generate_regime_signal(
                market_data, regime["regime"], indicators
            )
            if not signal:
                logger.debug(
                    f"No signal generated for {symbol} in {regime['regime']} regime"
                )
                return None

            # Add freshness metrics to signal
            signal["data_freshness"] = freshness_metrics
            signal["max_allowed_freshness"] = max_freshness

            # Calculate entry, TP, and SL
            entry, tp, sl = self._calculate_levels(market_data, signal["direction"])
            if not all([entry, tp, sl]):
                self.signal_tracker.log_rejection(
                    symbol, "Invalid price levels", {**market_data, **signal}
                )
                return None

            # Calculate risk/reward ratio
            rr_ratio = abs(tp - entry) / max(
                abs(sl - entry), entry * 0.001
            )  # Use 0.1% of entry as minimum risk
            if rr_ratio < 1.01:  # Lowered from 1.05 (just need any positive R:R)
                logger.debug(
                    f"Signal rejected for {symbol}: Poor risk/reward ratio: {rr_ratio:.2f}"
                )
                self.signal_tracker.log_rejection(
                    symbol,
                    f"Poor risk/reward ratio: {rr_ratio:.2f}",
                    {**market_data, **signal},
                )
                return None

            # Check spread
            spread = market_data.get("spread", float("inf"))
            if spread > 0.01:  # Increased from 0.008 (1% max spread)
                logger.debug(
                    f"Signal rejected for {symbol}: Spread too high: {spread:.4f}"
                )
                self.signal_tracker.log_rejection(
                    symbol, f"Spread too high: {spread:.4f}", {**market_data, **signal}
                )
                return None

            # Market regime checks
            if regime.get("confidence", 0) < 0.3:  # Lowered from 0.6
                logger.debug(
                    f"Signal rejected for {symbol}: Low regime confidence: {regime.get('confidence', 0):.2f}"
                )
                self.signal_tracker.log_rejection(
                    symbol,
                    f"Low regime confidence: {regime.get('confidence', 0):.2f}",
                    {**market_data, **signal},
                )
                return None

            # Volume checks
            volume_ma = indicators.get("volume_ma", 0)
            current_volume = float(market_data["klines"][-1]["volume"])
            if current_volume < volume_ma * 0.5:  # Lowered from 0.8
                logger.debug(
                    f"Signal rejected for {symbol}: Low volume: {current_volume:.2f} < {volume_ma * 0.5:.2f}"
                )
                self.signal_tracker.log_rejection(
                    symbol,
                    f"Low volume: {current_volume:.2f} < {volume_ma * 0.5:.2f}",
                    {**market_data, **signal},
                )
                return None

            # Trend strength checks
            adx = indicators.get("adx", 0)
            if adx < 15:  # Lowered from 20
                logger.debug(
                    f"Signal rejected for {symbol}: Weak trend (ADX): {adx:.2f}"
                )
                self.signal_tracker.log_rejection(
                    symbol, f"Weak trend (ADX): {adx:.2f}", {**market_data, **signal}
                )
                return None

            # RSI checks
            rsi = indicators.get("rsi", 50)
            if (signal["direction"] == "LONG" and rsi > 80) or (
                signal["direction"] == "SHORT" and rsi < 20
            ):
                logger.debug(f"Signal rejected for {symbol}: Extreme RSI: {rsi:.2f}")
                self.signal_tracker.log_rejection(
                    symbol, f"Extreme RSI: {rsi:.2f}", {**market_data, **signal}
                )
                return None

            # MACD checks
            macd = indicators.get("macd", {})
            macd_value = macd.get("value", 0)
            macd_signal = macd.get("signal", 0)
            if (signal["direction"] == "LONG" and macd_value <= macd_signal) or (
                signal["direction"] == "SHORT" and macd_value >= macd_signal
            ):
                logger.debug(
                    f"Signal rejected for {symbol}: MACD not confirming direction: {macd_value:.2f} vs {macd_signal:.2f}"
                )
                self.signal_tracker.log_rejection(
                    symbol,
                    f"MACD not confirming direction: {macd_value:.2f} vs {macd_signal:.2f}",
                    {**market_data, **signal},
                )
                return None

            # Create final signal with proper data types
            final_signal = {
                "symbol": str(symbol),
                "direction": str(signal["direction"]),
                "entry": float(entry),
                "take_profit": float(tp),
                "stop_loss": float(sl),
                "confidence": float(signal["confidence"]),
                "indicators": {
                    k: float(v) if isinstance(v, (int, float)) else v
                    for k, v in indicators.items()
                },
                "market_regime": str(regime["regime"]),
                "data_freshness": {k: float(v) for k, v in freshness_metrics.items()},
                "timestamp": float(current_time),
            }

            # Log the signal
            logger.info(
                f"Generated signal for {symbol}: {signal['direction']} at {entry:.2f}, TP: {tp:.2f}, SL: {sl:.2f}"
            )

            return final_signal

        except Exception as e:
            logger.error(f"Error generating signals for {symbol}: {str(e)}")
            return None
            
    def _determine_market_regime(self, market_data: Dict) -> Dict:
        """Determine the current market regime with confidence score."""
        try:
            symbol = market_data.get("symbol", "unknown")
            indicators = market_data.get("indicators", {})
            adx = indicators.get("adx", 0)
            bb_upper = indicators.get("bb_upper", 0)
            bb_lower = indicators.get("bb_lower", 0)
            bb_middle = indicators.get(
                "bb_middle", 1
            )  # Use 1 as fallback to avoid division by zero
            atr = indicators.get("atr", 0)
            current_price = (
                float(market_data["klines"][-1]["close"])
                if market_data.get("klines")
                else 1
            )

            # Add debug logging
            logger.debug(
                f"Determining market regime for {symbol} - ADX: {adx:.2f}, BB Width: {(bb_upper - bb_lower) / bb_middle:.4f}, ATR: {atr:.4f}"
            )
            
            # Calculate regime scores
            trend_score = 0
            range_score = 0
            volatile_score = 0
            
            # ADX contribution (0-1)
            if adx > 25:  # Strong trend
                trend_score += 0.6
            elif adx > 20:  # Moderate trend
                trend_score += 0.3
            elif adx < 15:  # Weak trend, likely ranging
                range_score += 0.4
            
            # BB Width contribution (0-1)
            epsilon = 1e-8
            if abs(bb_middle) > epsilon:  # Avoid division by zero
                bb_width = (bb_upper - bb_lower) / bb_middle
                if bb_width < 0.02:  # Tight range
                    range_score += 0.4
                elif bb_width < 0.03:  # Moderate range
                    range_score += 0.2
                elif bb_width > 0.05:  # Wide range, likely volatile
                    volatile_score += 0.3
            else:
                bb_width = 0
            
            # ATR contribution (0-1)
            if atr > epsilon and current_price > epsilon:
                atr_percent = atr / current_price
                if atr_percent > 0.03:  # High volatility
                    volatile_score += 0.4
                elif atr_percent > 0.02:  # Moderate volatility
                    volatile_score += 0.2
            else:
                atr_percent = 0

            # Volume contribution (0-1)
            volume_ma = indicators.get("volume_ma", 0)
            current_volume = float(market_data["klines"][-1]["volume"])
            if current_volume > volume_ma * 1.5:  # High volume
                volatile_score += 0.2
            elif current_volume < volume_ma * 0.5:  # Low volume
                range_score += 0.2

            # RSI contribution (0-1)
            rsi = indicators.get("rsi", 50)
            if rsi > 70 or rsi < 30:  # Extreme RSI
                volatile_score += 0.2
            elif 40 <= rsi <= 60:  # Neutral RSI
                range_score += 0.2

            # MACD contribution (0-1)
            macd = indicators.get("macd", {})
            macd_value = macd.get("value", 0)
            macd_signal = macd.get("signal", 0)
            if abs(macd_value - macd_signal) > abs(
                macd_signal * 0.1
            ):  # Strong MACD divergence
                trend_score += 0.2

            # EMA contribution (0-1)
            ema20 = indicators.get("ema20", current_price)
            ema50 = indicators.get("ema50", current_price)
            ema200 = indicators.get("ema200", current_price)

            # Check EMA alignment
            if ema20 > ema50 > ema200:  # Strong uptrend
                trend_score += 0.3
            elif ema20 < ema50 < ema200:  # Strong downtrend
                trend_score += 0.3
            elif abs(ema20 - ema50) / ema50 < 0.01:  # EMAs close together
                range_score += 0.3
            
            # Calculate final scores
            scores = {
                "trending": trend_score,
                "ranging": range_score,
                "volatile": volatile_score,
            }
            
            # Determine primary regime
            primary_regime = max(scores.items(), key=lambda x: x[1])
            
            # Calculate confidence (0-1)
            total_score = sum(scores.values())
            confidence = (
                primary_regime[1] / total_score if abs(total_score) > epsilon else 0
            )

            # Add debug logging
            logger.debug(
                f"Regime scores for {symbol} - Trending: {trend_score:.2f}, Ranging: {range_score:.2f}, Volatile: {volatile_score:.2f}"
            )
            logger.debug(
                f"Selected regime: {primary_regime[0]} with confidence: {confidence:.2f}"
            )
            
            # Check for regime transitions
            if previous_regime and previous_regime != primary_regime[0]:
                # Require higher confidence for regime changes
                if confidence < 0.7:  # Increased threshold
                    logger.debug(
                        f"Regime change rejected for {symbol} - Insufficient confidence ({confidence:.2f})"
                    )
                    return {
                        "regime": previous_regime,
                        "confidence": confidence,
                        "scores": scores,
                        "is_transitioning": True,
                    }
                elif previous_regime == "trending" and trend_score > 0.3:
                    logger.debug(
                        f"Regime change rejected for {symbol} - Still showing trend characteristics"
                    )
                    return {
                        "regime": previous_regime,
                        "confidence": confidence,
                        "scores": scores,
                        "is_transitioning": True,
                    }
                elif previous_regime == "ranging" and range_score > 0.3:
                    logger.debug(
                        f"Regime change rejected for {symbol} - Still showing range characteristics"
                    )
                    return {
                        "regime": previous_regime,
                        "confidence": confidence,
                        "scores": scores,
                        "is_transitioning": True,
                    }
                elif previous_regime == "volatile" and volatile_score > 0.3:
                    logger.debug(
                        f"Regime change rejected for {symbol} - Still showing volatile characteristics"
                    )
                    return {
                        "regime": previous_regime,
                        "confidence": confidence,
                        "scores": scores,
                        "is_transitioning": True,
                    }

            return {
                "regime": primary_regime[0],
                "confidence": confidence,
                "scores": scores,
                "is_transitioning": False,
            }
                
        except Exception as e:
            logger.error(f"Error determining market regime: {e}")
            return {
                "regime": "unknown",
                "confidence": 0,
                "scores": {"trending": 0, "ranging": 0, "volatile": 0},
                "is_transitioning": False,
            }
            
    def _calculate_indicators(self, market_data: Dict) -> Dict:
        """Calculate technical indicators."""
        try:
            ohlcv = market_data.get("klines", [])
            if not ohlcv:
                return {}
                
            closes = np.array([float(candle["close"]) for candle in ohlcv])
            highs = np.array([float(candle["high"]) for candle in ohlcv])
            lows = np.array([float(candle["low"]) for candle in ohlcv])
            volumes = np.array([float(candle["volume"]) for candle in ohlcv])
            
            # Calculate basic indicators
            sma20 = np.mean(closes[-20:])
            sma50 = np.mean(closes[-50:])
            rsi = self._calculate_rsi(closes)

            return {
                "sma20": float(sma20),
                "sma50": float(sma50),
                "rsi": float(rsi[-1]),
                "volume_ma": float(np.mean(volumes[-20:])),
                "atr": float(self._calculate_atr(highs, lows, closes)[-1]),
            }
            
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return {}
            
    async def _generate_regime_signal(
        self, market_data: Dict, regime: str, indicators: Dict
    ) -> Optional[Dict]:
        """Generate signal based on market regime."""
        try:
            symbol = market_data.get("symbol", "unknown")
            current_price = float(market_data["klines"][-1]["close"])

            # Add debug logging
            logger.debug(
                f"Generating {regime} signal for {symbol} at price {current_price:.2f}"
            )

            # Get regime-specific signal
            if regime == "trending":
                signal = self._generate_trending_signal(market_data, indicators)
            elif regime == "ranging":
                signal = self._generate_ranging_signal(market_data, indicators)
            else:  # volatile
                signal = self._generate_volatile_signal(market_data, indicators)

            if not signal:
                logger.debug(f"No {regime} signal generated for {symbol}")
                return None

            # Add regime-specific checks
            if regime == "trending":
                # Check trend strength
                adx = indicators.get("adx", 0)
                if adx < 20:  # Lowered from 25
                    logger.debug(
                        f"Trending signal rejected for {symbol}: Weak trend (ADX: {adx:.2f})"
                    )
                    return None

                # Check trend direction
                ema20 = indicators.get("ema20", current_price)
                ema50 = indicators.get("ema50", current_price)
                if (signal["direction"] == "LONG" and ema20 <= ema50) or (
                    signal["direction"] == "SHORT" and ema20 >= ema50
                ):
                    logger.debug(
                        f"Trending signal rejected for {symbol}: EMA not confirming direction"
                    )
                    return None

            elif regime == "ranging":
                # Check range boundaries
                bb_upper = indicators.get("bb_upper", current_price * 1.1)
                bb_lower = indicators.get("bb_lower", current_price * 0.9)
                if current_price > bb_upper or current_price < bb_lower:
                    logger.debug(
                        f"Ranging signal rejected for {symbol}: Price outside Bollinger Bands"
                    )
                    return None

            else:  # volatile
                # Check volatility
                atr = indicators.get("atr", 0)
                if atr / current_price < 0.02:  # Low volatility
                    logger.debug(
                        f"Volatile signal rejected for {symbol}: Low volatility"
                    )
                    return None

            return signal
                
        except Exception as e:
            logger.error(f"Error generating regime signal: {e}")
            return None
            
    def _calculate_levels(
        self, market_data: Dict, direction: str
    ) -> Tuple[float, float, float]:
        """Calculate entry, take profit, and stop loss levels using structure and volume clusters."""
        try:
            current_price = float(market_data["klines"][-1]["close"])
            
            # Get indicators and structure levels
            indicators = market_data.get("indicators", {})
            structure_levels = self._find_nearest_structure_level(
                indicators, current_price, direction
            )
            
            # Calculate volume clusters
            volume_clusters = self.candle_detector.detect(
                market_data["symbol"],
                {
                    "close_prices": [float(c["close"]) for c in market_data["klines"]],
                    "high_prices": [float(c["high"]) for c in market_data["klines"]],
                    "low_prices": [float(c["low"]) for c in market_data["klines"]],
                    "atr": indicators.get("atr", 0),
                    "atr_trend": indicators.get("atr_trend", 0),
                    "recent_volumes": [
                        float(c["volume"]) for c in market_data["klines"][-10:]
                    ],
                    "avg_recent_volume": np.mean(
                        [float(c["volume"]) for c in market_data["klines"][-5:]]
                    ),
                    "overall_avg_volume": np.mean(
                        [float(c["volume"]) for c in market_data["klines"]]
                    ),
                    "current_price": current_price,
                },
                {},
            )
            
            # Use volume cluster levels if available
            if volume_clusters:
                return (
                    volume_clusters["entry"],
                    volume_clusters["take_profit"],
                    volume_clusters["stop_loss"],
                )
            
            # Fallback to structure-based levels
            if structure_levels:
                if direction == "LONG":
                    entry = current_price
                    tp = (
                        structure_levels["next_resistance"]
                        if structure_levels["next_resistance"]
                        else (
                            entry
                            + (2 * max(indicators.get("atr", 0), current_price * 0.01))
                        )
                    )
                    sl = (
                        structure_levels["support"]
                        if structure_levels["support"]
                        else (
                            entry - max(indicators.get("atr", 0), current_price * 0.01)
                        )
                    )
                else:  # SHORT
                    entry = current_price
                    tp = (
                        structure_levels["next_support"]
                        if structure_levels["next_support"]
                        else (
                            entry
                            - (2 * max(indicators.get("atr", 0), current_price * 0.01))
                        )
                    )
                    sl = (
                        structure_levels["resistance"]
                        if structure_levels["resistance"]
                        else (
                            entry + max(indicators.get("atr", 0), current_price * 0.01)
                        )
                    )
                
                return entry, tp, sl
            
            # Fallback to ATR-based levels if no structure found
            atr = max(
                indicators.get("atr", 0), current_price * 0.01
            )  # Use 1% of price as minimum ATR
            if direction == "LONG":
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
            
        rs = avg_gain / avg_loss if abs(avg_loss) > 1e-8 else 0
        rsi = 100 - (100 / (1 + rs))
        
        return np.concatenate(([np.nan], rsi))
        
    def _calculate_atr(
        self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14
    ) -> np.ndarray:
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

    def _find_nearest_structure_level(
        self, indicators: Dict, current_price: float, signal_type: str
    ) -> Optional[Dict]:
        """Find nearest support and resistance levels based on price structure."""
        try:
            # Get recent swing highs and lows
            swing_levels = self._calculate_swing_levels(indicators)
            if not swing_levels:
                return None
            
            # Find nearest levels
            if signal_type == "LONG":
                support = max(
                    [level for level in swing_levels["lows"] if level < current_price],
                    default=None,
                )
                resistance = min(
                    [level for level in swing_levels["highs"] if level > current_price],
                    default=None,
                )
                next_resistance = min(
                    [level for level in swing_levels["highs"] if level > resistance],
                    default=None,
                )
            else:  # SHORT
                support = max(
                    [level for level in swing_levels["lows"] if level < current_price],
                    default=None,
                )
                resistance = min(
                    [level for level in swing_levels["highs"] if level > current_price],
                    default=None,
                )
                next_support = max(
                    [level for level in swing_levels["lows"] if level < support],
                    default=None,
                )
            
            return {
                "support": support,
                "resistance": resistance,
                "next_support": next_support if signal_type == "SHORT" else None,
                "next_resistance": next_resistance if signal_type == "LONG" else None,
            }
            
        except Exception as e:
            logger.error(f"Error finding structure levels: {e}")
            return None

    def _calculate_swing_levels(self, indicators: Dict, lookback: int = 20) -> Dict:
        """Calculate recent swing highs and lows with wick filters and clustering."""
        try:
            highs = indicators.get("highs", [])
            lows = indicators.get("lows", [])
            closes = indicators.get("closes", [])
            volumes = indicators.get("volumes", [])
            
            if len(highs) < lookback or len(lows) < lookback:
                return {"highs": [], "lows": []}
            
            # Calculate average candle body size
            body_sizes = [abs(closes[i] - closes[i - 1]) for i in range(1, len(closes))]
            avg_body = np.mean(body_sizes)
            
            # Calculate average wick size
            wick_sizes = []
            for i in range(len(highs)):
                upper_wick = highs[i] - max(
                    closes[i], closes[i - 1] if i > 0 else closes[i]
                )
                lower_wick = (
                    min(closes[i], closes[i - 1] if i > 0 else closes[i]) - lows[i]
                )
                wick_sizes.append(max(upper_wick, lower_wick))
            avg_wick = np.mean(wick_sizes)
            
            # Find swing highs with wick filter
            swing_highs = []
            for i in range(2, len(highs) - 2):
                # Check if it's a swing high
                if (
                    highs[i] > highs[i - 1]
                    and highs[i] > highs[i - 2]
                    and highs[i] > highs[i + 1]
                    and highs[i] > highs[i + 2]
                ):
                    # Check if the wick is not too large
                    upper_wick = highs[i] - max(closes[i], closes[i - 1])
                    if upper_wick <= avg_wick * 1.5:  # Allow wicks up to 1.5x average
                        swing_highs.append(highs[i])
                
            # Find swing lows with wick filter
            swing_lows = []
            for i in range(2, len(lows) - 2):
                # Check if it's a swing low
                if (
                    lows[i] < lows[i - 1]
                    and lows[i] < lows[i - 2]
                    and lows[i] < lows[i + 1]
                    and lows[i] < lows[i + 2]
                ):
                    # Check if the wick is not too large
                    lower_wick = min(closes[i], closes[i - 1]) - lows[i]
                    if lower_wick <= avg_wick * 1.5:  # Allow wicks up to 1.5x average
                        swing_lows.append(lows[i])
            
            # Cluster nearby levels
            def cluster_levels(
                levels: List[float], threshold: float = 0.002
            ) -> List[float]:
                if not levels:
                    return []
                    
                clusters = []
                current_cluster = [levels[0]]
                
                for level in sorted(levels)[1:]:
                    if (
                        abs(level - np.mean(current_cluster)) / np.mean(current_cluster)
                        <= threshold
                    ):
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
                        if (
                            is_high
                            and highs[i] >= level * 0.995
                            and highs[i] <= level * 1.005
                        ):
                            nearby_candles.append(volumes[i])
                        elif (
                            not is_high
                            and lows[i] >= level * 0.995
                            and lows[i] <= level * 1.005
                        ):
                            nearby_candles.append(volumes[i])
                    
                    # Keep level if it has significant volume
                    if (
                        nearby_candles
                        and np.mean(nearby_candles) > np.mean(volumes) * 0.8
                    ):
                        filtered_levels.append(level)
                
                return filtered_levels
            
            # Apply volume filtering
            volume_filtered_highs = filter_by_volume(clustered_highs, True)
            volume_filtered_lows = filter_by_volume(clustered_lows, False)
            
            return {
                "highs": sorted(volume_filtered_highs),
                "lows": sorted(volume_filtered_lows),
            }
            
        except Exception as e:
            logger.error(f"Error calculating swing levels: {e}")
            return {"highs": [], "lows": []}

    def _generate_trending_signal(
        self, market_data: Dict, indicators: Dict
    ) -> Optional[Dict]:
        """Generate signal for trending market regime."""
        try:
            symbol = market_data.get("symbol", "unknown")
            current_price = float(market_data["klines"][-1]["close"])

            # Add debug logging
            logger.debug(
                f"Generating trending signal for {symbol} at price {current_price:.2f}"
            )

            # Get trend indicators
            ema20 = indicators.get("ema20", current_price)
            ema50 = indicators.get("ema50", current_price)
            ema200 = indicators.get("ema200", current_price)
            adx = indicators.get("adx", 0)
            macd = indicators.get("macd", {})
            macd_value = macd.get("value", 0)
            macd_signal = macd.get("signal", 0)
            rsi = indicators.get("rsi", 50)

            # Check trend strength
            if adx < 20:  # Lowered from 25
                logger.debug(
                    f"Trending signal rejected for {symbol}: Weak trend (ADX: {adx:.2f})"
                )
                return None

            # Check trend direction
            if ema20 <= ema50:
                logger.debug(
                    f"Trending signal rejected for {symbol}: EMA not confirming uptrend"
                )
                return None

            # Check MACD
            if macd_value <= macd_signal:
                logger.debug(
                    f"Trending signal rejected for {symbol}: MACD not confirming uptrend"
                )
                return None

            # Check RSI
            if rsi > 70:
                logger.debug(
                    f"Trending signal rejected for {symbol}: Extreme RSI ({rsi:.2f})"
                )
                return None

            # Check price relative to EMAs
            if current_price <= ema20:
                logger.debug(
                    f"Trending signal rejected for {symbol}: Price below EMA20"
                )
                return None

            # Check volume
            volume_ma = indicators.get("volume_ma", 0)
            current_volume = float(market_data["klines"][-1]["volume"])
            if current_volume < volume_ma * 0.5:  # Lowered from 0.8
                logger.debug(f"Trending signal rejected for {symbol}: Low volume")
                return None

            # Check ATR
            atr = indicators.get("atr", current_price * 0.01)
            atr_percent = atr / current_price
            if atr_percent < 0.01:  # Lowered from 0.015
                logger.debug(
                    f"Trending signal rejected for {symbol}: Low volatility (ATR: {atr_percent:.4f})"
                )
                return None

            # Check ATR trend
            atr_trend = indicators.get("atr_trend", 0)
            if atr_trend <= 0:
                logger.debug(
                    f"Trending signal rejected for {symbol}: ATR trend not confirming uptrend"
                )
                return None

            # Check price structure
            structure_levels = self._find_nearest_structure_level(
                indicators, current_price, "LONG"
            )
            if not structure_levels:
                logger.debug(
                    f"Trending signal rejected for {symbol}: No structure levels found"
                )
                return None

            # Check if price is near support
            if current_price > structure_levels["support"] * 1.01:
                logger.debug(
                    f"Trending signal rejected for {symbol}: Price not near support"
                )
                return None

            # Check if next resistance is far enough
            if (
                structure_levels["next_resistance"]
                and (structure_levels["next_resistance"] - current_price)
                / current_price
                < 0.01
            ):
                logger.debug(
                    f"Trending signal rejected for {symbol}: Next resistance too close"
                )
                return None

            # Generate signal
            signal = {
                "direction": "LONG",
                "confidence": min(0.8, adx / 100),  # Cap confidence at 0.8
                "indicators": {
                    "ema20": ema20,
                    "ema50": ema50,
                    "ema200": ema200,
                    "adx": adx,
                    "macd": macd,
                    "rsi": rsi,
                    "atr": atr,
                    "atr_trend": atr_trend,
                    "volume_ma": volume_ma,
                    "current_volume": current_volume,
                    "structure_levels": structure_levels,
                },
            }

            logger.info(
                f"Generated trending signal for {symbol}: LONG at {current_price:.2f}"
            )
            return signal

        except Exception as e:
            logger.error(f"Error generating trending signal: {e}")
            return None
            
    def _generate_ranging_signal(
        self, market_data: Dict, indicators: Dict
    ) -> Optional[Dict]:
        """Generate signal for ranging market regime."""
        try:
            symbol = market_data.get("symbol", "unknown")
            current_price = float(market_data["klines"][-1]["close"])

            # Add debug logging
            logger.debug(
                f"Generating ranging signal for {symbol} at price {current_price:.2f}"
            )

            # Get range indicators
            bb_upper = indicators.get("bb_upper", current_price * 1.02)
            bb_lower = indicators.get("bb_lower", current_price * 0.98)
            bb_middle = indicators.get("bb_middle", current_price)
            rsi = indicators.get("rsi", 50)
            macd = indicators.get("macd", {})
            macd_value = macd.get("value", 0)
            macd_signal = macd.get("signal", 0)
            adx = indicators.get("adx", 0)

            # Check if market is actually ranging
            if adx > 25:  # Market is trending
                logger.debug(
                    f"Ranging signal rejected for {symbol}: Market is trending (ADX: {adx:.2f})"
                )
                return None

            # Calculate distance from middle band
            distance_from_middle = abs(current_price - bb_middle) / bb_middle
            if distance_from_middle < 0.005:  # Price too close to middle band
                logger.debug(
                    f"Ranging signal rejected for {symbol}: Price too close to middle band"
                )
                return None

            # Check volume
            volume_ma = indicators.get("volume_ma", 0)
            current_volume = float(market_data["klines"][-1]["volume"])
            if current_volume < volume_ma * 0.5:  # Lowered from 0.8
                logger.debug(f"Ranging signal rejected for {symbol}: Low volume")
                return None

            # Check price structure
            structure_levels = self._find_nearest_structure_level(
                indicators, current_price, "LONG"
            )
            if not structure_levels:
                logger.debug(
                    f"Ranging signal rejected for {symbol}: No structure levels found"
                )
                return None

            # Determine signal direction based on RSI, Bollinger Bands, and MACD
            if (
                rsi < 30
                and current_price <= bb_lower * 1.01
                and macd_value > macd_signal
            ):
                direction = "LONG"
                confidence = 0.7
            elif (
                rsi > 70
                and current_price >= bb_upper * 0.99
                and macd_value < macd_signal
            ):
                direction = "SHORT"
                confidence = 0.7
            else:
                logger.debug(
                    f"Ranging signal rejected for {symbol}: RSI: {rsi:.2f}, Price vs BB: {distance_from_middle:.4f}, MACD: {macd_value:.2f}"
                )
                return None

            # Check if price is near structure level
            if (
                direction == "LONG"
                and current_price > structure_levels["support"] * 1.01
            ):
                logger.debug(
                    f"Ranging signal rejected for {symbol}: Price not near support"
                )
                return None
            elif (
                direction == "SHORT"
                and current_price < structure_levels["resistance"] * 0.99
            ):
                logger.debug(
                    f"Ranging signal rejected for {symbol}: Price not near resistance"
                )
                return None

            # Check if next level is far enough
            if (
                direction == "LONG"
                and structure_levels["next_resistance"]
                and (structure_levels["next_resistance"] - current_price)
                / current_price
                < 0.01
            ):
                logger.debug(
                    f"Ranging signal rejected for {symbol}: Next resistance too close"
                )
                return None
            elif (
                direction == "SHORT"
                and structure_levels["next_support"]
                and (current_price - structure_levels["next_support"]) / current_price
                < 0.01
            ):
                logger.debug(
                    f"Ranging signal rejected for {symbol}: Next support too close"
                )
                return None

            # Generate signal
            signal = {
                "direction": direction,
                "confidence": confidence,
                "indicators": {
                    "bb_upper": bb_upper,
                    "bb_lower": bb_lower,
                    "bb_middle": bb_middle,
                    "rsi": rsi,
                    "macd": macd,
                    "adx": adx,
                    "volume_ma": volume_ma,
                    "current_volume": current_volume,
                    "structure_levels": structure_levels,
                },
            }

            logger.info(
                f"Generated ranging signal for {symbol}: {direction} at {current_price:.2f}"
            )
            return signal

        except Exception as e:
            logger.error(f"Error generating ranging signal: {e}")
            return None
            
    def _generate_volatile_signal(
        self, market_data: Dict, indicators: Dict
    ) -> Optional[Dict]:
        """Generate signal for volatile market regime."""
        try:
            symbol = market_data.get("symbol", "unknown")
            current_price = float(market_data["klines"][-1]["close"])

            # Add debug logging
            logger.debug(
                f"Generating volatile signal for {symbol} at price {current_price:.2f}"
            )

            # Get volatility indicators
            atr = indicators.get("atr", current_price * 0.01)
            atr_trend = indicators.get("atr_trend", 0)
            rsi = indicators.get("rsi", 50)
            macd = indicators.get("macd", {})
            macd_value = macd.get("value", 0)
            macd_signal = macd.get("signal", 0)
            adx = indicators.get("adx", 0)

            # Calculate ATR percentage
            atr_percent = atr / current_price

            # Check if market is actually volatile
            if atr_percent < 0.015:  # Market is not volatile enough
                logger.debug(
                    f"Volatile signal rejected for {symbol}: Low volatility (ATR: {atr_percent:.4f})"
                )
                return None

            # Check if market is trending
            if adx > 25:  # Market is trending
                logger.debug(
                    f"Volatile signal rejected for {symbol}: Market is trending (ADX: {adx:.2f})"
                )
                return None

            # Check volume
            volume_ma = indicators.get("volume_ma", 0)
            current_volume = float(market_data["klines"][-1]["volume"])
            if current_volume < volume_ma * 0.5:  # Lowered from 0.8
                logger.debug(f"Volatile signal rejected for {symbol}: Low volume")
                return None

            # Check price structure
            structure_levels = self._find_nearest_structure_level(
                indicators, current_price, "LONG"
            )
            if not structure_levels:
                logger.debug(
                    f"Volatile signal rejected for {symbol}: No structure levels found"
                )
                return None

            # Determine signal direction based on ATR trend, RSI, and MACD
            if atr_trend > 0 and rsi < 40 and macd_value > macd_signal:
                direction = "LONG"
                confidence = 0.6
            elif atr_trend < 0 and rsi > 60 and macd_value < macd_signal:
                direction = "SHORT"
                confidence = 0.6
            else:
                logger.debug(
                    f"Volatile signal rejected for {symbol}: ATR Trend: {atr_trend:.4f}, RSI: {rsi:.2f}, MACD: {macd_value:.2f}"
                )
                return None

            # Check if price is near structure level
            if (
                direction == "LONG"
                and current_price > structure_levels["support"] * 1.01
            ):
                logger.debug(
                    f"Volatile signal rejected for {symbol}: Price not near support"
                )
                return None
            elif (
                direction == "SHORT"
                and current_price < structure_levels["resistance"] * 0.99
            ):
                logger.debug(
                    f"Volatile signal rejected for {symbol}: Price not near resistance"
                )
                return None

            # Check if next level is far enough
            if (
                direction == "LONG"
                and structure_levels["next_resistance"]
                and (structure_levels["next_resistance"] - current_price)
                / current_price
                < 0.01
            ):
                logger.debug(
                    f"Volatile signal rejected for {symbol}: Next resistance too close"
                )
                return None
            elif (
                direction == "SHORT"
                and structure_levels["next_support"]
                and (current_price - structure_levels["next_support"]) / current_price
                < 0.01
            ):
                logger.debug(
                    f"Volatile signal rejected for {symbol}: Next support too close"
                )
                return None

            # Generate signal
            signal = {
                "direction": direction,
                "confidence": confidence,
                "indicators": {
                    "atr": atr,
                    "atr_trend": atr_trend,
                    "rsi": rsi,
                    "macd": macd,
                    "adx": adx,
                    "volume_ma": volume_ma,
                    "current_volume": current_volume,
                    "structure_levels": structure_levels,
                },
            }

            logger.info(
                f"Generated volatile signal for {symbol}: {direction} at {current_price:.2f}"
            )
            return signal

        except Exception as e:
            logger.error(f"Error generating volatile signal: {e}")
            return None

    def should_close_position(
        self, symbol: str, position_data: Dict, market_data: Dict
    ) -> Tuple[bool, str]:
        """
        Determine if a position should be closed based on current market conditions.
        
        Args:
            symbol: Trading symbol
            position_data: Current position information
            market_data: Current market data including indicators
            
        Returns:
            Tuple of (should_close: bool, reason: str)
        """
        try:
            if not position_data or not market_data:
                return False, "missing_data"
                
            # Get position metrics
            position_amt = float(position_data.get("positionAmt", 0))
            entry_price = float(position_data.get("entryPrice", 0))
            current_price = float(market_data.get("price", 0))
            unrealized_pnl = float(position_data.get("unRealizedProfit", 0))
            
            if position_amt == 0 or entry_price == 0 or current_price == 0:
                return False, "invalid_position"
                
            # Calculate PnL percentage
            pnl_percentage = (unrealized_pnl / (abs(position_amt) * entry_price)) * 100
            
            # Get technical indicators
            rsi = float(market_data.get("rsi", 50))
            macd = market_data.get("macd", {})
            macd_line = float(macd.get("macd", 0))
            signal_line = float(macd.get("signal", 0))
            
            # Check stop loss conditions
            if position_amt > 0:  # Long position
                if pnl_percentage <= -self.strategy_config.get(
                    "risk_management", {}
                ).get("stop_loss_pct", 0):
                    return True, "stop_loss"
                if rsi > 70 and macd_line < signal_line:
                    return True, "overbought_reversal"
            else:  # Short position
                if pnl_percentage <= -self.strategy_config.get(
                    "risk_management", {}
                ).get("stop_loss_pct", 0):
                    return True, "stop_loss"
                if rsi < 30 and macd_line > signal_line:
                    return True, "oversold_reversal"
                    
            # Check take profit conditions
            if pnl_percentage >= self.strategy_config.get("risk_management", {}).get(
                "take_profit_pct", 0
            ):
                return True, "take_profit"
                
            return False, "hold"
            
        except Exception as e:
            logger.error(f"Error in should_close_position for {symbol}: {e}")
            return False, "error"

    def should_update_levels(
        self, symbol: str, position_data: Dict, market_data: Dict
    ) -> bool:
        """
        Determine if position levels should be updated based on market conditions.
        
        Args:
            symbol: Trading symbol
            position_data: Current position information
            market_data: Current market data including indicators
            
        Returns:
            bool: True if levels should be updated
        """
        try:
            if not position_data or not market_data:
                return False
                
            # Get position metrics
            position_amt = float(position_data.get("positionAmt", 0))
            if position_amt == 0:
                return False
                
            # Get market metrics
            price = float(market_data.get("price", 0))
            volume = float(market_data.get("volume", 0))
            volatility = float(market_data.get("volatility", 0))
            
            if price == 0 or volume == 0:
                return False
                
            # Check if enough time has passed since last update
            last_update = float(position_data.get("last_update", 0))
            if time.time() - last_update < self.strategy_config.get("trading", {}).get(
                "position_interval", 0
            ):
                return False
                
            # Check for significant price movement
            price_change = abs(float(market_data.get("price_change_pct", 0)))
            if price_change >= self.strategy_config.get("risk_management", {}).get(
                "level_update_threshold", 0
            ):
                return True
                
            # Check for high volatility
            if volatility >= self.strategy_config.get("risk_management", {}).get(
                "volatility_threshold", 0
            ):
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Error in should_update_levels for {symbol}: {e}")
            return False

    def calculate_new_levels(
        self, symbol: str, position_data: Dict, market_data: Dict
    ) -> Dict:
        """
        Calculate new position levels based on current market conditions.
        
        Args:
            symbol: Trading symbol
            position_data: Current position information
            market_data: Current market data including indicators
            
        Returns:
            Dict containing new position levels
        """
        try:
            if not position_data or not market_data:
                return {}
                
            # Get current position metrics
            position_amt = float(position_data.get("positionAmt", 0))
            entry_price = float(position_data.get("entryPrice", 0))
            current_price = float(market_data.get("price", 0))
            
            if position_amt == 0 or entry_price == 0 or current_price == 0:
                return {}
                
            # Get technical indicators
            rsi = float(market_data.get("rsi", 50))
            macd = market_data.get("macd", {})
            macd_line = float(macd.get("macd", 0))
            signal_line = float(macd.get("signal", 0))
            
            # Calculate base levels
            atr = float(market_data.get("atr", 0))
            volatility = float(market_data.get("volatility", 0))
            
            # Calculate dynamic stop loss and take profit levels
            if position_amt > 0:  # Long position
                stop_loss = current_price - (
                    atr
                    * self.strategy_config.get("risk_management", {}).get(
                        "stop_loss_atr_multiplier", 2.0
                    )
                )
                take_profit = current_price + (
                    atr
                    * self.strategy_config.get("risk_management", {}).get(
                        "take_profit_atr_multiplier", 2.0
                    )
                )
            else:  # Short position
                stop_loss = current_price + (
                    atr
                    * self.strategy_config.get("risk_management", {}).get(
                        "stop_loss_atr_multiplier", 2.0
                    )
                )
                take_profit = current_price - (
                    atr
                    * self.strategy_config.get("risk_management", {}).get(
                        "take_profit_atr_multiplier", 2.0
                    )
                )
                
            # Adjust levels based on market conditions
            if rsi > 70 or rsi < 30:  # Extreme RSI
                stop_loss = current_price  # Tighten stop loss
                
            if macd_line > signal_line and position_amt > 0:  # Strong trend
                take_profit *= 1.2  # Extend take profit
                
            # Calculate trailing stop
            trailing_stop = current_price * (
                1
                - self.strategy_config.get("risk_management", {}).get(
                    "trailing_stop_pct", 0.05
                )
            )
            
            return {
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "trailing_stop": trailing_stop,
                "volatility": volatility,
                "atr": atr,
                "last_update": time.time(),
            }
            
        except Exception as e:
            logger.error(f"Error in calculate_new_levels for {symbol}: {e}")
            return {} 
