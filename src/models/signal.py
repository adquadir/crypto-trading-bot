from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from src.database.base import Base

class TradingSignal(Base):
    """Trading signal model for storing trading signals."""
    
    __tablename__ = 'trading_signals'
    
    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), nullable=False)
    signal_type = Column(String(20), nullable=False)  # 'buy' or 'sell'
    strategy_id = Column(Integer, ForeignKey('strategies.id'), nullable=False)
    price = Column(Float, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    parameters = Column(JSON, nullable=True)
    confidence = Column(Float, nullable=True)
    status = Column(String(20), nullable=False, default='pending')  # 'pending', 'executed', 'cancelled'
    
    # Relationships
    strategy = relationship("Strategy", back_populates="signals")
    
    def __repr__(self):
        return f"<TradingSignal(symbol='{self.symbol}', type='{self.signal_type}', price={self.price})>"
        
    def to_dict(self):
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'symbol': self.symbol,
            'signal_type': self.signal_type,
            'strategy_id': self.strategy_id,
            'price': self.price,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'parameters': self.parameters,
            'confidence': self.confidence,
            'status': self.status
        } 