from typing import Dict, List, Optional
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
            
            # Handle potential NaN values from ta calculations
            macd_value = float(macd.macd().iloc[-1]) if not pd.isna(macd.macd().iloc[-1]) else 0.0
            macd_signal = float(macd.macd_signal().iloc[-1]) if not pd.isna(macd.macd_signal().iloc[-1]) else 0.0
            macd_histogram = float(macd.macd_diff().iloc[-1]) if not pd.isna(macd.macd_diff().iloc[-1]) else 0.0
            rsi_value = float(rsi.rsi().iloc[-1]) if not pd.isna(rsi.rsi().iloc[-1]) else 50.0 # RSI default to 50
            
            bb_upper = float(bb.bollinger_hband().iloc[-1]) if not pd.isna(bb.bollinger_hband().iloc[-1]) else current_price
            bb_middle = float(bb.bollinger_mavg().iloc[-1]) if not pd.isna(bb.bollinger_mavg().iloc[-1]) else current_price
            bb_lower = float(bb.bollinger_lband().iloc[-1]) if not pd.isna(bb.bollinger_lband().iloc[-1]) else current_price
            
            # Handle ADX calculations with zero division protection
            try:
                adx_value = float(adx.adx().iloc[-1]) if not pd.isna(adx.adx().iloc[-1]) else 0.0
                adx_di_plus = float(adx.adx_pos().iloc[-1]) if not pd.isna(adx.adx_pos().iloc[-1]) else 0.0
                adx_di_minus = float(adx.adx_neg().iloc[-1]) if not pd.isna(adx.adx_neg().iloc[-1]) else 0.0
            except (ZeroDivisionError, ValueError) as e:
                logger.warning(f"ADX calculation error for {symbol}: {e}. Using default values.")
                adx_value = 0.0
                adx_di_plus = 0.0
                adx_di_minus = 0.0
            
            atr_value = float(atr.average_true_range().iloc[-1]) if not pd.isna(atr.average_true_range().iloc[-1]) else 0.0
            cci_value = float(cci.cci().iloc[-1]) if not pd.isna(cci.cci().iloc[-1]) else 0.0

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
        """Generate trading signals based on technical indicators."""
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
            
            # Calculate indicators
            indicators = self.calculate_indicators(market_data, {})
            if not indicators:
                logger.warning(f"Failed to calculate indicators for {symbol}")
                return {}
                
            signal_strength = initial_confidence
            signal_type = None
            reasons = []
            
            # MACD Analysis
            if indicators['macd']['value'] > indicators['macd']['signal']:
                signal_strength += 0.5
                reasons.append("MACD above signal line")
            else:
                signal_strength -= 0.5
                reasons.append("MACD below signal line")
                
            # RSI Analysis
            rsi = indicators['rsi']
            if rsi < 35:
                signal_strength += 1.0
                reasons.append("RSI oversold")
            elif rsi > 65:
                signal_strength -= 1.0
                reasons.append("RSI overbought")
                
            # Bollinger Bands Analysis
            current_price = indicators['current_price']
            bb = indicators['bollinger_bands']
            if current_price < bb['lower']:
                signal_strength += 1.0
                reasons.append("Price below lower Bollinger Band")
            elif current_price > bb['upper']:
                signal_strength -= 1.0
                reasons.append("Price above upper Bollinger Band")
                
            # ADX Analysis
            adx = indicators['adx']
            if adx['value'] > 20:
                if adx['di_plus'] > adx['di_minus']:
                    signal_strength += 0.5
                    reasons.append("Strong uptrend (ADX)")
                else:
                    signal_strength -= 0.5
                    reasons.append("Strong downtrend (ADX)")
                    
            # CCI Analysis
            cci = indicators['cci']
            if cci > 100:
                signal_strength += 1
                reasons.append("CCI bullish")
            elif cci < -100:
                signal_strength -= 1
                reasons.append("CCI bearish")
                
            # Determine signal type and direction based on final strength
            if signal_strength >= 2:
                signal_type = "BUY"
                direction = "LONG"
            elif signal_strength <= -2:
                signal_type = "SELL"
                direction = "SHORT"
            else:
                # If signal is NEUTRAL, we explicitly return None.
                # This prevents NEUTRAL signals from ever reaching validation.
                logger.debug(f"Generated NEUTRAL signal for {symbol} with strength {signal_strength}. Skipping signal generation and returning None.")
                return None
                
            # If we reach here, it means a BUY or SELL signal was generated.
            # Calculate entry, take profit, and stop loss levels
            atr = indicators.get('atr', 0)
            # Ensure ATR is a valid number
            if pd.isna(atr) or atr <= 0:
                logger.warning(f"Invalid or zero ATR for {symbol}. Setting default trading levels.")
                entry = current_price
                take_profit = current_price * (1.0 + 0.005) if direction == "LONG" else current_price * (1.0 - 0.005)
                stop_loss = current_price * (1.0 - 0.002) if direction == "LONG" else current_price * (1.0 + 0.002)
            else:
                if direction == "LONG":
                    entry = current_price
                    take_profit = entry + (atr * 2)  # 2 ATR for take profit
                    stop_loss = entry - (atr * 1)    # 1 ATR for stop loss
                else:  # SHORT
                    entry = current_price
                    take_profit = entry - (atr * 2)  # 2 ATR for take profit
                    stop_loss = entry + (atr * 1)    # 1 ATR for stop loss
                
            logger.debug(f"Generated signal for {symbol}: {signal_type} ({direction}) with strength {signal_strength}")
            
            return {
                'symbol': symbol,
                'signal_type': signal_type,
                'direction': direction,
                'strength': signal_strength,
                'confidence': abs(signal_strength) / 5.0,  # Normalize to 0-1 range
                'reasons': reasons,
                'timestamp': datetime.now().isoformat(),
                'price': current_price,
                'entry': entry,
                'take_profit': take_profit,
                'stop_loss': stop_loss,
                'indicators': {
                    'macd': indicators['macd'],
                    'rsi': rsi,
                    'bollinger_bands': bb,
                    'adx': indicators['adx'], # Use the full adx dictionary
                    'cci': cci,
                    'atr': atr
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating signals for {symbol}: {str(e)}")
            return {}
            
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