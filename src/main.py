#!/usr/bin/env python3
import asyncio
import logging
from fastapi import FastAPI
import uvicorn
from src.api.routes import router
from src.trading_bot import trading_bot

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="Crypto Trading Bot API")

# Include API routes
app.include_router(router, prefix="/api/v1")

@app.on_event("startup")
async def startup_event():
    """Initialize the trading bot on startup."""
    try:
        await trading_bot.initialize()
    except Exception as e:
        logger.error(f"Error initializing trading bot: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown the trading bot on shutdown."""
    try:
        await trading_bot.shutdown()
    except Exception as e:
        logger.error(f"Error shutting down trading bot: {e}")
        raise

def main():
    """Run the FastAPI application."""
    try:
        # Run the FastAPI application
        uvicorn.run(
            "src.main:app",
            host="0.0.0.0",
            port=8000,
            reload=False,
            log_level="info"
        )
    except Exception as e:
        logger.error(f"Error running application: {e}")
        raise

if __name__ == "__main__":
    main() 