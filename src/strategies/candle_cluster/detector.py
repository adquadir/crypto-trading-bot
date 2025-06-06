from typing import Dict, List, Optional
import logging
import numpy as np

logger = logging.getLogger(__name__)

class CandleClusterDetector:
    def __init__(self):
        # Any necessary initialization for the detector can go here
        pass

    def detect(self, symbol: str, indicators: Dict, params: Dict) -> Optional[Dict]:
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
                if potential_take_profit - current_take_profit > target_profit_max:
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

            return None # No hovering opportunity found

        except Exception as e:
            logger.error(f"Error detecting hovering opportunity for {symbol}: {e}")
            return None 