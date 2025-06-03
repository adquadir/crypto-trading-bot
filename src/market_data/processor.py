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
        
    def process_orderbook(self, orderbook: Dict, depth: int = 10) -> Dict:
        """Process orderbook data into useful metrics."""
        try:
            bids = pd.DataFrame(orderbook['bids'], columns=['price', 'quantity'], dtype=float)
            asks = pd.DataFrame(orderbook['asks'], columns=['price', 'quantity'], dtype=float)
            
            # Calculate order book metrics
            bid_volume = bids['quantity'].sum()
            ask_volume = asks['quantity'].sum()
            
            # Calculate weighted average prices
            bid_wap = (bids['price'] * bids['quantity']).sum() / bid_volume
            ask_wap = (asks['price'] * asks['quantity']).sum() / ask_volume
            
            # Calculate spread
            spread = ask_wap - bid_wap
            spread_pct = spread / bid_wap * 100
            
            # Calculate order book imbalance
            imbalance = (bid_volume - ask_volume) / (bid_volume + ask_volume)
            
            return {
                'bid_volume': bid_volume,
                'ask_volume': ask_volume,
                'bid_wap': bid_wap,
                'ask_wap': ask_wap,
                'spread': spread,
                'spread_pct': spread_pct,
                'imbalance': imbalance,
                'timestamp': orderbook['timestamp']
            }
        except Exception as e:
            logger.error(f"Error processing orderbook: {e}")
            return {}
            
    def update_ohlcv(self, symbol: str, candle: Dict):
        """Update OHLCV data for a symbol."""
        if symbol not in self.data_cache:
            self.data_cache[symbol] = pd.DataFrame(columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume'
            ])
            
        df = self.data_cache[symbol]
        new_row = pd.DataFrame([{
            'timestamp': candle['timestamp'],
            'open': candle['open'],
            'high': candle['high'],
            'low': candle['low'],
            'close': candle['close'],
            'volume': candle['volume']
        }])
        
        self.data_cache[symbol] = pd.concat([df, new_row], ignore_index=True)
        
        # Keep only necessary data
        max_window = max(self.window_sizes)
        if len(self.data_cache[symbol]) > max_window * 2:
            self.data_cache[symbol] = self.data_cache[symbol].tail(max_window * 2)
            
    def calculate_indicators(self, symbol: str) -> Dict:
        """Calculate technical indicators for a symbol."""
        if symbol not in self.data_cache or len(self.data_cache[symbol]) < max(self.window_sizes):
            return {}
            
        df = self.data_cache[symbol]
        
        try:
            indicators = {}
            
            # Trend Indicators
            for window in self.window_sizes:
                # Moving Averages
                indicators[f'sma_{window}'] = ta.trend.sma_indicator(df['close'], window=window).iloc[-1]
                indicators[f'ema_{window}'] = ta.trend.ema_indicator(df['close'], window=window).iloc[-1]
                
                # MACD
                if window == 20:  # Only calculate MACD for one window
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
            indicators['bb_high'] = ta.volatility.BollingerBands(df['close']).bollinger_hband().iloc[-1]
            indicators['bb_low'] = ta.volatility.BollingerBands(df['close']).bollinger_lband().iloc[-1]
            indicators['bb_mid'] = ta.volatility.BollingerBands(df['close']).bollinger_mavg().iloc[-1]
            indicators['atr'] = ta.volatility.AverageTrueRange(
                df['high'], df['low'], df['close']
            ).average_true_range().iloc[-1]
            
            # Volume Indicators
            indicators['obv'] = ta.volume.on_balance_volume(df['close'], df['volume']).iloc[-1]
            indicators['vwap'] = ta.volume.volume_weighted_average_price(
                df['high'], df['low'], df['close'], df['volume']
            ).iloc[-1]
            
            return indicators
            
        except Exception as e:
            logger.error(f"Error calculating indicators for {symbol}: {e}")
            return {}
            
    def get_market_state(self, symbol: str) -> Dict:
        """Get current market state including all indicators."""
        if symbol not in self.data_cache:
            return {}
            
        indicators = self.calculate_indicators(symbol)
        if not indicators:
            return {}
            
        # Get latest price data
        latest = self.data_cache[symbol].iloc[-1]
        
        return {
            'price': latest['close'],
            'volume': latest['volume'],
            'timestamp': latest['timestamp'],
            'indicators': indicators
        } 