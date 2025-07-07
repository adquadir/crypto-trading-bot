#!/usr/bin/env python3

import asyncio
import logging
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import paper trading components
from src.api.trading_routes.paper_trading_routes import router as paper_trading_router, initialize_paper_trading_engine, set_paper_engine
from src.utils.config import load_config

app = FastAPI(
    title="Paper Trading API",
    description="Simple paper trading API",
    version="1.0.0"
)

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include paper trading router
app.include_router(paper_trading_router, prefix="/api/v1")

@app.on_event("startup")
async def startup_event():
    """Initialize paper trading engine on startup"""
    try:
        logger.info("🚀 Starting Paper Trading API...")
        
        # Load config
        config = load_config()
        paper_config = config.get('paper_trading', {}) if config else {}
        paper_config.setdefault('initial_balance', 10000.0)
        paper_config.setdefault('enabled', True)
        
        # Initialize paper trading engine
        paper_engine = await initialize_paper_trading_engine(
            {'paper_trading': paper_config},
            exchange_client=None,  # Mock mode for now
            flow_trading_strategy='adaptive'
        )
        
        if paper_engine:
            set_paper_engine(paper_engine)
            logger.info("✅ Paper Trading Engine initialized successfully")
        else:
            logger.error("❌ Failed to initialize Paper Trading Engine")
        
        logger.info("✅ Paper Trading API started successfully!")
        
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")

@app.get("/")
async def root():
    return {"message": "Paper Trading API", "version": "1.0.0", "status": "running"}

@app.get("/health")
async def health_check():
    from src.api.trading_routes.paper_trading_routes import get_paper_engine
    engine = get_paper_engine()
    return {
        "status": "healthy",
        "paper_trading_engine": engine is not None,
        "engine_running": engine.is_running if engine else False
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
