
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Test server running", "status": "ok"}

@app.get("/api/v1/paper-trading/status")
async def paper_trading_status():
    return {
        "status": "success",
        "data": {
            "enabled": True,
            "virtual_balance": 10000.0,
            "total_return_pct": 0.0,
            "win_rate_pct": 0.0,
            "completed_trades": 0,
            "active_positions": 0
        }
    }

@app.get("/api/v1/paper-trading/positions")
async def paper_trading_positions():
    return {"status": "success", "data": []}

@app.get("/api/v1/paper-trading/trades")
async def paper_trading_trades():
    return {"status": "success", "trades": []}

@app.get("/api/v1/paper-trading/performance")
async def paper_trading_performance():
    return {"status": "success", "data": {}}

if __name__ == "__main__":
    print("🚀 Starting simple test server on port 8000...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
