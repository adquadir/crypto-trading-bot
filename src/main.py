import asyncio
import logging
from fastapi import FastAPI
from src.api.routes import router
from src.trading_bot import trading_bot

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Crypto Trading Bot API")
app.include_router(router, prefix="/api/v1")

@app.on_event("startup")
async def startup_event():
    """Initialize the trading bot on startup."""
    try:
        await trading_bot.start()
    except Exception as e:
        logger.error(f"Error starting trading bot: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown."""
    try:
        await trading_bot.stop()
    except Exception as e:
        logger.error(f"Error stopping trading bot: {e}")

async def main():
    """Main entry point for the application."""
    try:
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000)
    except Exception as e:
        logger.error(f"Error running application: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main()) 