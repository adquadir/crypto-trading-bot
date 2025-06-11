from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, JSON, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from src.database.base import Base

@dataclass
class StrategyParameters:
    """Base class for strategy parameters"""
    name: str
    description: str
    timeframe: str
    symbols: List[str]
    parameters: Dict

class Strategy(Base):
    """Strategy model for storing trading strategies."""
    
    __tablename__ = 'strategies'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False, unique=True)
    description = Column(String(255), nullable=True)
    type = Column(String(50), nullable=False)
    parameters = Column(JSON, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    signals = relationship("TradingSignal", back_populates="strategy")
    
    def __repr__(self):
        return f"<Strategy(name='{self.name}', type='{self.type}')>"
        
    def to_dict(self):
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'type': self.type,
            'parameters': self.parameters,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class MACDStrategy(Strategy):
    """MACD Strategy implementation."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "MACD"
        self.type = "technical"
        self.description = "Moving Average Convergence Divergence Strategy"
        self.parameters = {
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9
        }

class RSIStrategy(Strategy):
    """RSI Strategy implementation."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "RSI"
        self.type = "technical"
        self.description = "Relative Strength Index Strategy"
        self.parameters = {
            "period": 14,
            "overbought": 70,
            "oversold": 30
        }

class BollingerBandsStrategy(Strategy):
    """Bollinger Bands Strategy implementation."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "Bollinger Bands"
        self.type = "technical"
        self.description = "Bollinger Bands Strategy"
        self.parameters = {
            "period": 20,
            "std_dev": 2
        }

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