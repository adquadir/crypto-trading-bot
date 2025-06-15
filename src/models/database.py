from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON, Boolean, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()

class StrategyType(enum.Enum):
    MACD = "macd"
    RSI = "rsi"
    BOLLINGER = "bollinger"
    CUSTOM = "custom"

class Strategy(Base):
    __tablename__ = 'strategies'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(String)
    type = Column(Enum(StrategyType), nullable=False)
    parameters = Column(JSON)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    signals = relationship("TradingSignal", back_populates="strategy")
    trades = relationship("Trade", back_populates="strategy")
    performance = relationship("PerformanceMetrics", back_populates="strategy")

class MarketData(Base):
    __tablename__ = 'market_data'
    
    id = Column(Integer, primary_key=True)
    symbol = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
    data = Column(JSON)

class OrderBook(Base):
    __tablename__ = 'order_books'
    
    id = Column(Integer, primary_key=True)
    symbol = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    bids = Column(JSON)
    asks = Column(JSON)
    spread = Column(Float)

class TradingSignal(Base):
    __tablename__ = 'trading_signals'
    
    id = Column(Integer, primary_key=True)
    strategy_id = Column(Integer, ForeignKey('strategies.id'))
    symbol = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    signal_type = Column(String, nullable=False)  # 'BUY' or 'SELL'
    price = Column(Float)
    confidence = Column(Float)
    indicators = Column(JSON)
    
    # Relationships
    strategy = relationship("Strategy", back_populates="signals")
    trade = relationship("Trade", back_populates="signal", uselist=False)

class Trade(Base):
    __tablename__ = 'trades'
    
    id = Column(Integer, primary_key=True)
    strategy_id = Column(Integer, ForeignKey('strategies.id'))
    signal_id = Column(Integer, ForeignKey('trading_signals.id'))
    symbol = Column(String, nullable=False)
    entry_time = Column(DateTime, nullable=False)
    exit_time = Column(DateTime)
    entry_price = Column(Float)
    exit_price = Column(Float)
    position_size = Column(Float)
    leverage = Column(Float, default=1.0)
    pnl = Column(Float)
    pnl_pct = Column(Float)
    status = Column(String)  # 'OPEN', 'CLOSED', 'CANCELLED'
    
    # Relationships
    strategy = relationship("Strategy", back_populates="trades")
    signal = relationship("TradingSignal", back_populates="trade")

class PerformanceMetrics(Base):
    __tablename__ = 'performance_metrics'
    
    id = Column(Integer, primary_key=True)
    strategy_id = Column(Integer, ForeignKey('strategies.id'))
    timestamp = Column(DateTime, nullable=False)
    total_trades = Column(Integer)
    winning_trades = Column(Integer)
    losing_trades = Column(Integer)
    win_rate = Column(Float)
    profit_factor = Column(Float)
    sharpe_ratio = Column(Float)
    max_drawdown = Column(Float)
    total_pnl = Column(Float)
    
    # Relationships
    strategy = relationship("Strategy", back_populates="performance") 