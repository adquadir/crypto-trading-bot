import asyncio
import logging
import logging.config
from typing import Optional
import signal
import sys

from config import LOGGING_CONFIG, validate_config
from trading_bot import TradingBot

# Configure logging
logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)

class TradingBotApp:
    def __init__(self):
        self.bot: Optional[TradingBot] = None
        self.running = False
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown."""
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}. Initiating graceful shutdown...")
        self.running = False
        if self.bot:
            asyncio.create_task(self.bot.stop())

    async def start(self):
        """Start the trading bot."""
        try:
            # Validate configuration
            if not validate_config():
                logger.error("Configuration validation failed. Exiting...")
                sys.exit(1)

            # Initialize and start the trading bot
            self.bot = TradingBot()
            self.running = True
            
            logger.info("Starting trading bot...")
            await self.bot.start()

            # Keep the main thread alive
            while self.running:
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Error in trading bot: {str(e)}", exc_info=True)
            if self.bot:
                await self.bot.stop()
            sys.exit(1)

def main():
    """Main entry point for the trading bot application."""
    app = TradingBotApp()
    
    try:
        # Run the async main loop
        asyncio.run(app.start())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt. Shutting down...")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
    finally:
        logger.info("Trading bot shutdown complete.")

if __name__ == "__main__":
    main() 