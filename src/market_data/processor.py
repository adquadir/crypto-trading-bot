# File: src/market_data/processor.py
from typing import Dict, List, Optional
import pandas as pd
import numpy as np
import ta
from datetime import datetime
import logging
import time

logger = logging.getLogger(__name__)

class MarketDataProcessor:
    def __init__(self, window_sizes: List[int] = [20, 50, 200]):
        self.window_sizes = window_sizes
        self.data_cache = {}  # symbol -> DataFrame
        self._resample_cache = {}
        self._cache_ttl = 300  # 5 minutes cache TTL
        self._last_cache_cleanup = time.time()
        
    def _cleanup_cache(self):
        """Clean up expired cache entries."""
        current_time = time.time()
        if current_time - self._last_cache_cleanup > 60:  # Cleanup every minute
            expired_keys = [
                key for key, (_, timestamp) in self._resample_cache.items()
                if current_time - timestamp > self._cache_ttl
            ]
            for key in expired_keys:
                del self._resample_cache[key]
            self._last_cache_cleanup = current_time
        
    def update_ohlcv(self, symbol: str, data: List[Dict]) -> bool:
        """Process and store OHLCV data with validation."""
        if not data:
            logger.error(f"No data provided for {symbol}")
            return False
            
        # Validate first data point
        sample = data[0]
        required_keys = {'timestamp', 'open', 'high', 'low', 'close', 'volume'}
        missing_keys = required_keys - set(sample.keys())
        if missing_keys:
            logger.error(f"Invalid data format for {symbol}. Missing keys: {missing_keys}")
            logger.debug(f"Sample data received: {sample}")
            return False
            
        # Convert to DataFrame
        try:
            df = pd.DataFrame(data)
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]  # Ensure correct columns
            
            # Initialize cache if needed
            if symbol not in self.data_cache:
                self.data_cache[symbol] = df
            else:
                # Concatenate new data
                self.data_cache[symbol] = pd.concat([self.data_cache[symbol], df]).drop_duplicates('timestamp')
            
            # Keep only necessary data
            max_window = max(self.window_sizes)
            if len(self.data_cache[symbol]) > max_window * 2:
                self.data_cache[symbol] = self.data_cache[symbol].tail(max_window * 2)
                
            logger.debug(f"Processed {len(df)} new data points for {symbol}. Total: {len(self.data_cache[symbol])}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing data for {symbol}: {str(e)}")
            return False
            
    def calculate_indicators(self, market_data: Dict, params: Dict = None) -> Dict:
        """Calculate technical indicators from market data for multiple timeframes."""
        try:
            # Extract price data
            df = pd.DataFrame(market_data['klines'])
            df['close'] = pd.to_numeric(df['close'])
            df['high'] = pd.to_numeric(df['high'])
            df['low'] = pd.to_numeric(df['low'])
            df['volume'] = pd.to_numeric(df['volume'])
            
            # Create timeframes dictionary with proper error handling
            timeframes = {}
            try:
                timeframes['1m'] = df
                timeframes['5m'] = self._resample_dataframe(df, '5T')
                timeframes['15m'] = self._resample_dataframe(df, '15T')
            except Exception as e:
                logger.error(f"Error creating timeframes: {e}")
            return {}
            
            # Calculate indicators for each timeframe
            tf_indicators = {}
            for tf, tf_df in timeframes.items():
                if tf_df.empty:
                    logger.warning(f"Empty dataframe for {tf} timeframe")
                    continue
                    
                try:
                    # Calculate MACD
                    macd = ta.trend.MACD(
                        tf_df['close'],
                        window_slow=params.get('macd_slow_period', 26),
                        window_fast=params.get('macd_fast_period', 12),
                        window_sign=params.get('macd_signal_period', 9)
                    )
                    
                    # Calculate RSI
                    rsi = ta.momentum.RSIIndicator(
                        tf_df['close'],
                        window=14
                    )
                    
                    # Calculate Bollinger Bands
                    bb = ta.volatility.BollingerBands(
                        tf_df['close'],
                        window=20,
                        window_dev=params.get('bb_std_dev', 2)
                    )
                    
                    # Calculate ADX
                    adx = ta.trend.ADXIndicator(
                        tf_df['high'],
                        tf_df['low'],
                        tf_df['close'],
                        window=14
                    )
                    
                    # Calculate ATR
                    atr = ta.volatility.AverageTrueRange(
                        tf_df['high'],
                        tf_df['low'],
                        tf_df['close'],
                        window=14
                    )
                    
                    # Calculate CCI
                    cci = ta.trend.CCIIndicator(
                        tf_df['high'],
                        tf_df['low'],
                        tf_df['close'],
                        window=20
                    )
                    
                    # Calculate EMAs
                    ema_20 = ta.trend.EMAIndicator(tf_df['close'], window=20)
                    ema_50 = ta.trend.EMAIndicator(tf_df['close'], window=50)
                    
                    # Get current price
                    current_price = float(tf_df['close'].iloc[-1])
                    
                    # Handle potential NaN/inf values
                    def safe_float(val, default=0.0):
                        try:
                            f = float(val)
                            if not np.isfinite(f):
                                return default
                            return f
                        except Exception:
                            return default
                    
                    # Calculate indicator values with proper error handling
                    tf_indicators[tf] = {
                        'macd': {
                            'value': safe_float(macd.macd().iloc[-1]),
                            'signal': safe_float(macd.macd_signal().iloc[-1]),
                            'histogram': safe_float(macd.macd_diff().iloc[-1])
                        },
                        'rsi': safe_float(rsi.rsi().iloc[-1], 50.0),
                        'bollinger_bands': {
                            'upper': safe_float(bb.bollinger_hband().iloc[-1], current_price),
                            'middle': safe_float(bb.bollinger_mavg().iloc[-1], current_price),
                            'lower': safe_float(bb.bollinger_lband().iloc[-1], current_price),
                            'width': safe_float((bb.bollinger_hband().iloc[-1] - bb.bollinger_lband().iloc[-1]) / bb.bollinger_mavg().iloc[-1])
                        },
                        'adx': {
                            'value': safe_float(adx.adx().iloc[-1]),
                            'di_plus': safe_float(adx.adx_pos().iloc[-1]),
                            'di_minus': safe_float(adx.adx_neg().iloc[-1])
                        },
                        'atr': safe_float(atr.average_true_range().iloc[-1]),
                        'cci': safe_float(cci.cci().iloc[-1]),
                        'ema_20': safe_float(ema_20.ema_indicator().iloc[-1]),
                        'ema_50': safe_float(ema_50.ema_indicator().iloc[-1]),
                        'current_price': current_price,
                        'highs': tf_df['high'].tolist(),
                        'lows': tf_df['low'].tolist(),
                        'volume': tf_df['volume'].tolist()
                    }
                    
                    logger.debug(f"Successfully calculated indicators for {tf} timeframe")
                    
                except Exception as e:
                    logger.error(f"Error calculating indicators for {tf} timeframe: {e}")
                    continue
            
            return tf_indicators
            
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return {}

    def _resample_dataframe(self, df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
        """Resample dataframe to a different timeframe with caching."""
        try:
            # Cleanup expired cache entries
            self._cleanup_cache()
            
            # Generate cache key
            cache_key = f"{timeframe}_{df.index[-1] if not df.empty else 'empty'}"
            
            # Check cache
            if cache_key in self._resample_cache:
                cached_data, _ = self._resample_cache[cache_key]
                logger.debug(f"Using cached resampled data for {timeframe}")
                return cached_data
            
            # Convert timestamp to datetime if needed
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('timestamp', inplace=True)
            
            # Validate data before resampling
            if df.empty:
                logger.warning(f"Empty dataframe provided for {timeframe} resampling")
                return pd.DataFrame()
                
            # Check for sufficient data points
            min_points = {
                '1T': 1,    # 1 minute
                '5T': 5,    # 5 minutes
                '15T': 15   # 15 minutes
            }.get(timeframe, 1)
            
            if len(df) < min_points:
                logger.warning(f"Insufficient data points for {timeframe} resampling: {len(df)} < {min_points}")
                return df
            
            # Resample OHLCV data with proper aggregation
            resampled = df.resample(timeframe).agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            })
            
            # Handle any NaN values
            resampled = resampled.fillna(method='ffill').fillna(method='bfill')
            
            # Store in cache
            self._resample_cache[cache_key] = (resampled, time.time())
            
            logger.debug(f"Successfully resampled data to {timeframe} timeframe")
            return resampled
            
        except Exception as e:
            logger.error(f"Error resampling dataframe to {timeframe}: {e}")
            return df

    def _calculate_mtf_alignment(self, indicators: Dict) -> Dict:
        """Calculate multi-timeframe alignment score and trend direction."""
        try:
            alignment = {
                'score': 0.0,
                'trend': 'NEUTRAL',
                'strength': 0.0,
                'details': {}
            }
            
            # Check trend alignment across timeframes
            trends = {}
            for tf in ['1m', '5m', '15m']:
                if tf not in indicators:
                    continue
                    
                tf_indicators = indicators[tf]
                
                # Determine trend using multiple indicators
                trend_signals = []
                
                # EMA trend
                ema_20 = tf_indicators.get('ema_20', 0)
                ema_50 = tf_indicators.get('ema_50', 0)
                if ema_20 and ema_50:
                    trend_signals.append(1 if ema_20 > ema_50 else -1)
                
                # MACD trend
                macd = tf_indicators.get('macd', {})
                if macd:
                    trend_signals.append(1 if macd['histogram'] > 0 else -1)
                
                # ADX trend
                adx = tf_indicators.get('adx', {})
                if adx:
                    di_plus = adx.get('di_plus', 0)
                    di_minus = adx.get('di_minus', 0)
                    if di_plus > di_minus:
                        trend_signals.append(1)
                    elif di_minus > di_plus:
                        trend_signals.append(-1)
                
                # Calculate trend strength
                if trend_signals:
                    trend_score = sum(trend_signals) / len(trend_signals)
                    trends[tf] = {
                        'direction': 'BULLISH' if trend_score > 0 else 'BEARISH' if trend_score < 0 else 'NEUTRAL',
                        'strength': abs(trend_score),
                        'score': trend_score
                    }
            
            # Calculate overall alignment
            if trends:
                # Weight higher timeframes more heavily
                weights = {'1m': 0.2, '5m': 0.3, '15m': 0.5}
                weighted_score = sum(trends[tf]['score'] * weights[tf] for tf in trends.keys())
                
                # Determine overall trend
                if weighted_score > 0.3:
                    alignment['trend'] = 'BULLISH'
                elif weighted_score < -0.3:
                    alignment['trend'] = 'BEARISH'
                
                alignment['score'] = abs(weighted_score)
                alignment['strength'] = min(alignment['score'] * 2, 1.0)  # Scale to 0-1
                alignment['details'] = trends
            
            return alignment
            
        except Exception as e:
            logger.error(f"Error calculating multi-timeframe alignment: {e}")
            return {
                'score': 0.0,
                'trend': 'NEUTRAL',
                'strength': 0.0,
                'details': {}
            }
            
    def get_market_state(self, symbol: str) -> Dict:
        """Get current market state including all indicators."""
        if symbol not in self.data_cache or self.data_cache[symbol].empty:
            logger.error(f"No data available for {symbol}")
            return {}
            
        indicators = self.calculate_indicators(self.data_cache[symbol])
        if not indicators:
            return {}
            
        # Get latest price data
        latest = self.data_cache[symbol].iloc[-1]
        
        market_state = {
            'symbol': symbol,
            'timestamp': int(latest['timestamp']),
            'price': float(latest['close']),
            'open': float(latest['open']),
            'high': float(latest['high']),
            'low': float(latest['low']),
            'volume': float(latest['volume']),
            'indicators': indicators
        }
        
        logger.debug(f"Market state for {symbol} at {market_state['timestamp']}")
        return market_state

    def get_raw_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """Get raw data for debugging."""
        return self.data_cache.get(symbol)