from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
import asyncio
import json
from typing import List

from .models import Token, User
from .auth import (
    authenticate_user,
    create_access_token,
    get_current_user,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    fake_users_db
)
from .websocket import manager
from .routes import router as trading_router

app = FastAPI(title="Crypto Trading Bot API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include trading routes
app.include_router(trading_router)

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2RequestForm = Depends()):
    user = authenticate_user(fake_users_db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_text()
            # Handle incoming messages if needed
            await manager.send_personal_message({"message": "Message received"}, client_id)
    except WebSocketDisconnect:
        manager.disconnect(websocket, client_id)

# Mock data generation for testing
async def generate_mock_data():
    """Generate mock data for testing WebSocket functionality."""
    while True:
        # Generate mock trading signal
        signal = {
            "symbol": "BTCUSDT",
            "type": "BUY",
            "price": 50000.0,
            "timestamp": "2024-02-20T12:00:00Z"
        }
        await manager.broadcast_trading_signal(signal)

        # Generate mock PnL update
        pnl = {
            "total_pnl": 1000.0,
            "daily_pnl": 100.0,
            "positions": [
                {
                    "symbol": "BTCUSDT",
                    "pnl": 500.0,
                    "position_size": 0.1
                }
            ]
        }
        await manager.broadcast_pnl_update(pnl)

        # Wait for 5 seconds before next update
        await asyncio.sleep(5)

@app.on_event("startup")
async def startup_event():
    """Start the mock data generation task."""
    asyncio.create_task(generate_mock_data())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 