# File: src/market_data/processor.py
from typing import Dict, List, Optional
import pandas as pd
import numpy as np
import ta
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class MarketDataProcessor:
    def __init__(self, window_sizes: List[int] = [20, 50, 200]):
        self.window_sizes = window_sizes
        self.data_cache = {}  # symbol -> DataFrame
        
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
            
    def calculate_indicators(self, symbol: str) -> Dict:
        """Calculate technical indicators for a symbol."""
        if symbol not in self.data_cache or len(self.data_cache[symbol]) < max(self.window_sizes):
            logger.warning(f"Insufficient data for {symbol} to calculate indicators")
            return {}
            
        df = self.data_cache[symbol]
        
        try:
            indicators = {}
            
            # Trend Indicators
            for window in self.window_sizes:
                # Moving Averages
                indicators[f'sma_{window}'] = ta.trend.sma_indicator(df['close'], window=window).iloc[-1]
                indicators[f'ema_{window}'] = ta.trend.ema_indicator(df['close'], window=window).iloc[-1]
                
                # MACD (only calculate for smallest window)
                if window == min(self.window_sizes):
                    macd = ta.trend.MACD(df['close'])
                    indicators['macd'] = macd.macd().iloc[-1]
                    indicators['macd_signal'] = macd.macd_signal().iloc[-1]
                    indicators['macd_diff'] = macd.macd_diff().iloc[-1]
            
            # Momentum Indicators
            indicators['rsi'] = ta.momentum.RSIIndicator(df['close']).rsi().iloc[-1]
            indicators['stoch_k'] = ta.momentum.StochasticOscillator(
                df['high'], df['low'], df['close']
            ).stoch().iloc[-1]
            indicators['stoch_d'] = ta.momentum.StochasticOscillator(
                df['high'], df['low'], df['close']
            ).stoch_signal().iloc[-1]
            
            # Volatility Indicators
            bb = ta.volatility.BollingerBands(df['close'])
            indicators['bb_high'] = bb.bollinger_hband().iloc[-1]
            indicators['bb_low'] = bb.bollinger_lband().iloc[-1]
            indicators['bb_mid'] = bb.bollinger_mavg().iloc[-1]
            indicators['atr'] = ta.volatility.AverageTrueRange(
                df['high'], df['low'], df['close']
            ).average_true_range().iloc[-1]
            
            # Volume Indicators
            indicators['obv'] = ta.volume.on_balance_volume(df['close'], df['volume']).iloc[-1]
            indicators['vwap'] = ta.volume.volume_weighted_average_price(
                df['high'], df['low'], df['close'], df['volume']
            ).iloc[-1]
            
            logger.debug(f"Calculated indicators for {symbol}")
            return indicators
            
        except Exception as e:
            logger.error(f"Error calculating indicators for {symbol}: {str(e)}")
            return {}
            
    def get_market_state(self, symbol: str) -> Dict:
        """Get current market state including all indicators."""
        if symbol not in self.data_cache or self.data_cache[symbol].empty:
            logger.error(f"No data available for {symbol}")
            return {}
            
        indicators = self.calculate_indicators(symbol)
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