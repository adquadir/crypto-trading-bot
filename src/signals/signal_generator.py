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
            
            return {
                'macd': {
                    'value': float(macd.macd().iloc[-1]),
                    'signal': float(macd.macd_signal().iloc[-1]),
                    'histogram': float(macd.macd_diff().iloc[-1])
                },
                'macd_signal': float(macd.macd_signal().iloc[-1]),
                'rsi': float(rsi.rsi().iloc[-1]),
                'bollinger_bands': {
                    'upper': float(bb.bollinger_hband().iloc[-1]),
                    'middle': float(bb.bollinger_mavg().iloc[-1]),
                    'lower': float(bb.bollinger_lband().iloc[-1])
                },
                'bb_upper': float(bb.bollinger_hband().iloc[-1]),
                'bb_lower': float(bb.bollinger_lband().iloc[-1]),
                'adx': {
                    'value': float(adx.adx().iloc[-1]),
                    'di_plus': float(adx.adx_pos().iloc[-1]),
                    'di_minus': float(adx.adx_neg().iloc[-1])
                },
                'plus_di': float(adx.adx_pos().iloc[-1]),
                'minus_di': float(adx.adx_neg().iloc[-1]),
                'atr': float(atr.average_true_range().iloc[-1]),
                'cci': float(cci.cci().iloc[-1]),
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
                signal_strength += 1
                reasons.append("MACD above signal line")
            else:
                signal_strength -= 1
                reasons.append("MACD below signal line")
                
            # RSI Analysis
            rsi = indicators['rsi']
            if rsi < 30:
                signal_strength += 2
                reasons.append("RSI oversold")
            elif rsi > 70:
                signal_strength -= 2
                reasons.append("RSI overbought")
                
            # Bollinger Bands Analysis
            current_price = indicators['current_price']
            bb = indicators['bollinger_bands']
            if current_price < bb['lower']:
                signal_strength += 2
                reasons.append("Price below lower Bollinger Band")
            elif current_price > bb['upper']:
                signal_strength -= 2
                reasons.append("Price above upper Bollinger Band")
                
            # ADX Analysis
            adx = indicators['adx']
            if adx['value'] > 25:  # Strong trend
                if adx['di_plus'] > adx['di_minus']:
                    signal_strength += 1
                    reasons.append("Strong uptrend (ADX)")
                else:
                    signal_strength -= 1
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
            if signal_strength >= 3:
                signal_type = "BUY"
                direction = "LONG"
            elif signal_strength <= -3:
                signal_type = "SELL"
                direction = "SHORT"
            else:
                signal_type = "NEUTRAL"
                direction = "NEUTRAL"
                
            # Calculate entry, take profit, and stop loss levels
            atr = indicators.get('atr', 0)
            if atr > 0 and direction != "NEUTRAL":
                if direction == "LONG":
                    entry = current_price
                    take_profit = entry + (atr * 2)  # 2 ATR for take profit
                    stop_loss = entry - (atr * 1)    # 1 ATR for stop loss
                else:  # SHORT
                    entry = current_price
                    take_profit = entry - (atr * 2)  # 2 ATR for take profit
                    stop_loss = entry + (atr * 1)    # 1 ATR for stop loss
            else:
                entry = current_price
                take_profit = current_price
                stop_loss = current_price
                
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
                    'adx': adx,
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