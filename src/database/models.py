from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class MarketData(Base):
    __tablename__ = 'market_data'
    
    id = Column(Integer, primary_key=True)
    symbol = Column(String, index=True)
    timestamp = Column(DateTime, index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
    indicators = Column(JSON)  # Store technical indicators
    
    def __repr__(self):
        return f"<MarketData(symbol='{self.symbol}', timestamp='{self.timestamp}')>"

class OrderBook(Base):
    __tablename__ = 'orderbook'
    
    id = Column(Integer, primary_key=True)
    symbol = Column(String, index=True)
    timestamp = Column(DateTime, index=True)
    bid_volume = Column(Float)
    ask_volume = Column(Float)
    bid_wap = Column(Float)
    ask_wap = Column(Float)
    spread = Column(Float)
    spread_pct = Column(Float)
    imbalance = Column(Float)
    
    def __repr__(self):
        return f"<OrderBook(symbol='{self.symbol}', timestamp='{self.timestamp}')>"

class TradingSignal(Base):
    __tablename__ = 'trading_signals'
    
    id = Column(Integer, primary_key=True)
    symbol = Column(String, index=True)
    timestamp = Column(DateTime, index=True)
    signal_type = Column(String)  # 'LONG' or 'SHORT'
    action = Column(String) # e.g., 'OPEN_LONG', 'CLOSE_SHORT', 'HOLD'
    confidence = Column(Float)
    price = Column(Float)
    indicators = Column(JSON)  # Store indicators used for signal generation
    strategy = Column(String)  # Name of the strategy that generated the signal
    
    def __repr__(self):
        return f"<TradingSignal(symbol='{self.symbol}', type='{self.signal_type}', confidence={self.confidence})>"

class Trade(Base):
    __tablename__ = 'trades'
    
    id = Column(Integer, primary_key=True)
    symbol = Column(String, index=True)
    entry_time = Column(DateTime, index=True)
    exit_time = Column(DateTime, nullable=True)
    signal_id = Column(Integer, ForeignKey('trading_signals.id'))
    entry_price = Column(Float)
    exit_price = Column(Float, nullable=True)
    position_size = Column(Float)
    leverage = Column(Float)
    pnl = Column(Float, nullable=True)
    pnl_pct = Column(Float, nullable=True)
    status = Column(String)  # 'OPEN', 'CLOSED', 'CANCELLED'
    
    signal = relationship("TradingSignal")
    
    def __repr__(self):
        return f"<Trade(symbol='{self.symbol}', status='{self.status}', pnl={self.pnl})>"

class PerformanceMetrics(Base):
    __tablename__ = 'performance_metrics'
    
    id = Column(Integer, primary_key=True)
    symbol = Column(String, index=True)
    timestamp = Column(DateTime, index=True)
    strategy = Column(String, index=True)
    total_trades = Column(Integer)
    winning_trades = Column(Integer)
    losing_trades = Column(Integer)
    win_rate = Column(Float)
    avg_win = Column(Float)
    avg_loss = Column(Float)
    profit_factor = Column(Float)
    sharpe_ratio = Column(Float)
    max_drawdown = Column(Float)
    
    def __repr__(self):
        return f"<PerformanceMetrics(symbol='{self.symbol}', strategy='{self.strategy}', win_rate={self.win_rate})>"

class Strategy(Base):
    __tablename__ = 'strategies'

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, index=True)
    description = Column(String, nullable=True)
    active = Column(Boolean, default=True)
    parameters = Column(JSON) # Store strategy-specific parameters

    def __repr__(self):
        return f"<Strategy(name='{self.name}', active={self.active})>" 