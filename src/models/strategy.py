from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional
import pandas as pd
import numpy as np
from datetime import datetime

@dataclass
class StrategyParameters:
    """Base class for strategy parameters"""
    name: str
    description: str
    timeframe: str
    symbols: List[str]
    parameters: Dict

class Strategy(ABC):
    """Base class for all trading strategies"""
    
    def __init__(self, parameters: StrategyParameters):
        self.parameters = parameters
        self.name = parameters.name
        self.description = parameters.description
        self.timeframe = parameters.timeframe
        self.symbols = parameters.symbols
    
    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> Dict:
        """Generate trading signals from market data"""
        pass
    
    @abstractmethod
    def calculate_indicators(self, data: pd.DataFrame) -> Dict:
        """Calculate technical indicators for the strategy"""
        pass
    
    @abstractmethod
    def validate_parameters(self) -> bool:
        """Validate strategy parameters"""
        pass

class MACDStrategy(Strategy):
    """Moving Average Convergence Divergence Strategy"""
    
    def __init__(self, parameters: StrategyParameters):
        super().__init__(parameters)
        self.fast_period = parameters.parameters.get('fast_period', 12)
        self.slow_period = parameters.parameters.get('slow_period', 26)
        self.signal_period = parameters.parameters.get('signal_period', 9)
    
    def calculate_indicators(self, data: pd.DataFrame) -> Dict:
        # Calculate MACD
        exp1 = data['close'].ewm(span=self.fast_period, adjust=False).mean()
        exp2 = data['close'].ewm(span=self.slow_period, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=self.signal_period, adjust=False).mean()
        hist = macd - signal
        
        return {
            'macd': macd,
            'signal': signal,
            'histogram': hist
        }
    
    def generate_signals(self, data: pd.DataFrame) -> Dict:
        indicators = self.calculate_indicators(data)
        
        # Generate signals based on MACD crossover
        signals = pd.DataFrame(index=data.index)
        signals['signal'] = 0
        signals.loc[indicators['macd'] > indicators['signal'], 'signal'] = 1
        signals.loc[indicators['macd'] < indicators['signal'], 'signal'] = -1
        
        return {
            'signals': signals,
            'indicators': indicators
        }
    
    def validate_parameters(self) -> bool:
        return (
            self.fast_period > 0 and
            self.slow_period > self.fast_period and
            self.signal_period > 0
        )

class RSIStrategy(Strategy):
    """Relative Strength Index Strategy"""
    
    def __init__(self, parameters: StrategyParameters):
        super().__init__(parameters)
        self.period = parameters.parameters.get('period', 14)
        self.overbought = parameters.parameters.get('overbought', 70)
        self.oversold = parameters.parameters.get('oversold', 30)
    
    def calculate_indicators(self, data: pd.DataFrame) -> Dict:
        # Calculate RSI
        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return {'rsi': rsi}
    
    def generate_signals(self, data: pd.DataFrame) -> Dict:
        indicators = self.calculate_indicators(data)
        
        # Generate signals based on RSI levels
        signals = pd.DataFrame(index=data.index)
        signals['signal'] = 0
        signals.loc[indicators['rsi'] < self.oversold, 'signal'] = 1
        signals.loc[indicators['rsi'] > self.overbought, 'signal'] = -1
        
        return {
            'signals': signals,
            'indicators': indicators
        }
    
    def validate_parameters(self) -> bool:
        return (
            self.period > 0 and
            self.overbought > 50 and
            self.oversold < 50 and
            self.overbought > self.oversold
        )

class BollingerBandsStrategy(Strategy):
    """Bollinger Bands Strategy"""
    
    def __init__(self, parameters: StrategyParameters):
        super().__init__(parameters)
        self.period = parameters.parameters.get('period', 20)
        self.std_dev = parameters.parameters.get('std_dev', 2)
    
    def calculate_indicators(self, data: pd.DataFrame) -> Dict:
        # Calculate Bollinger Bands
        sma = data['close'].rolling(window=self.period).mean()
        std = data['close'].rolling(window=self.period).std()
        upper_band = sma + (std * self.std_dev)
        lower_band = sma - (std * self.std_dev)
        
        return {
            'sma': sma,
            'upper_band': upper_band,
            'lower_band': lower_band
        }
    
    def generate_signals(self, data: pd.DataFrame) -> Dict:
        indicators = self.calculate_indicators(data)
        
        # Generate signals based on price crossing bands
        signals = pd.DataFrame(index=data.index)
        signals['signal'] = 0
        signals.loc[data['close'] < indicators['lower_band'], 'signal'] = 1
        signals.loc[data['close'] > indicators['upper_band'], 'signal'] = -1
        
        return {
            'signals': signals,
            'indicators': indicators
        }
    
    def validate_parameters(self) -> bool:
        return (
            self.period > 0 and
            self.std_dev > 0
        ) 