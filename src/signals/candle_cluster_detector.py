from typing import Optional, Dict
import pandas as pd
from log import logger

class CandleClusterDetector:
    def detect(self, df: pd.DataFrame) -> Optional[Dict]:
        """Detect a hovering pattern in the price action.
        
        Args:
            df: DataFrame with OHLCV data and ATR
            
        Returns:
            Dict with pattern details if detected, None otherwise
        """
        try:
            # Get the last 20 candles
            recent = df.tail(20)
            
            # Calculate metrics
            atr = recent['atr'].iloc[-1]
            max_range = (recent['high'].max() - recent['low'].min()) / recent['close'].iloc[-1]
            avg_candle_body = abs(recent['close'] - recent['open']).mean() / recent['close'].iloc[-1]
            
            # Check if price is hovering (low volatility)
            if max_range <= 2 * atr and avg_candle_body <= 0.5 * atr:
                # Calculate trend direction
                sma20 = recent['close'].rolling(20).mean().iloc[-1]
                current_price = recent['close'].iloc[-1]
                
                # Determine if we're hovering above or below SMA
                if current_price > sma20:
                    return {
                        'type': 'hovering_buy',
                        'strength': 0.7,
                        'atr': atr,
                        'max_range': max_range,
                        'avg_body': avg_candle_body
                    }
                else:
                    return {
                        'type': 'hovering_sell',
                        'strength': 0.7,
                        'atr': atr,
                        'max_range': max_range,
                        'avg_body': avg_candle_body
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Error detecting candle cluster: {e}")
            return None 