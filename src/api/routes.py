from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict
from datetime import datetime
from .models import User
from .auth import get_current_user

router = APIRouter(prefix="/api/trading")

@router.get("/signals")
async def get_trading_signals(current_user: User = Depends(get_current_user)):
    """Get recent trading signals."""
    # Mock data - replace with real data from your trading bot
    return {
        "signals": [
            {
                "symbol": "BTCUSDT",
                "type": "BUY",
                "price": 50000,
                "timestamp": datetime.utcnow().isoformat(),
                "confidence": 0.85
            }
        ]
    }

@router.get("/pnl")
async def get_pnl(current_user: User = Depends(get_current_user)):
    """Get current PnL information."""
    # Mock data - replace with real data from your trading bot
    return {
        "total_pnl": 1500.50,
        "daily_pnl": 250.75,
        "positions": [
            {
                "symbol": "BTCUSDT",
                "pnl": 750.25,
                "entry_price": 48000,
                "current_price": 50000
            }
        ]
    }

@router.get("/stats")
async def get_trading_stats(current_user: User = Depends(get_current_user)):
    """Get trading statistics."""
    # Mock data - replace with real data from your trading bot
    return {
        "total_trades": 100,
        "win_rate": 0.65,
        "average_profit": 150.50,
        "max_drawdown": 500.00,
        "sharpe_ratio": 1.85
    }

@router.get("/orderbook/{symbol}")
async def get_orderbook(symbol: str, current_user: User = Depends(get_current_user)):
    """Get order book for a symbol."""
    # Mock data - replace with real data from your trading bot
    return {
        "symbol": symbol,
        "bids": [
            {"price": 49900, "quantity": 1.5},
            {"price": 49800, "quantity": 2.0},
        ],
        "asks": [
            {"price": 50100, "quantity": 1.0},
            {"price": 50200, "quantity": 2.5},
        ],
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/trades/{symbol}")
async def get_trades(symbol: str, current_user: User = Depends(get_current_user)):
    """Get recent trades for a symbol."""
    # Mock data - replace with real data from your trading bot
    return {
        "trades": [
            {
                "id": "1",
                "symbol": symbol,
                "side": "BUY",
                "price": 50000,
                "quantity": 0.1,
                "timestamp": datetime.utcnow().isoformat()
            }
        ]
    } 