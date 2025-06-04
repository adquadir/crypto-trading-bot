from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime

class User(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None

class UserInDB(User):
    hashed_password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class Signal(BaseModel):
    symbol: str
    type: str
    price: float
    timestamp: datetime
    confidence: float

class Position(BaseModel):
    symbol: str
    pnl: float
    entry_price: float
    current_price: float

class PnL(BaseModel):
    total_pnl: float
    daily_pnl: float
    positions: List[Position]

class TradingStats(BaseModel):
    total_trades: int
    win_rate: float
    average_profit: float
    max_drawdown: float
    sharpe_ratio: float

class OrderBookEntry(BaseModel):
    price: float
    quantity: float

class OrderBook(BaseModel):
    symbol: str
    bids: List[OrderBookEntry]
    asks: List[OrderBookEntry]
    timestamp: datetime

class Trade(BaseModel):
    id: str
    symbol: str
    side: str
    price: float
    quantity: float
    timestamp: datetime 