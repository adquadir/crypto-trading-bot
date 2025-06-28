#!/usr/bin/env python3
"""
Minimal test server to verify API routes work
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Import the route modules directly
from src.api.trading_routes.paper_trading_routes import router as paper_trading_router
from src.api.trading_routes.profit_scraping_routes import router as profit_scraping_router
from src.api.trading_routes.flow_trading_routes import router as flow_trading_router

app = FastAPI(title="Crypto Trading Bot Test API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(paper_trading_router, prefix="/api/v1")
app.include_router(profit_scraping_router, prefix="/api/v1")
app.include_router(flow_trading_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {"message": "Crypto Trading Bot Test API", "status": "running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "Test server running"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
