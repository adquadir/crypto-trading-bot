#!/usr/bin/env python3
"""Main script to run the trading bot."""

import asyncio
import logging
import os
import warnings
from typing import Dict, List, Optional

from dotenv import load_dotenv

from src.trading_bot import TradingBot
from src.main import main

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Suppress numpy warnings
warnings.filterwarnings(
    "ignore",
    message="invalid value encountered in scalar divide"
)


async def main():
    """Main function to run the trading bot."""
    # Load environment variables
    load_dotenv()
    
    # Check required environment variables
    required_vars = ['BINANCE_API_KEY', 'BINANCE_API_SECRET']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(
            f"Missing required environment variables: {', '.join(missing_vars)}"
        )
        return
        
    # Create and start the trading bot
    bot = TradingBot()
    
    try:
        # Start the bot
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt. Shutting down...")
    except Exception as e:
        logger.error(f"Error running bot: {e}")
        raise
    finally:
        # Stop the bot
        await bot.stop()
        
        # Print final performance summary
        performance = bot.get_performance_summary()
        logger.info("Final Performance Summary:")
        logger.info(f"Total Trades: {performance.get('total_trades', 0)}")
        logger.info(f"Win Rate: {performance.get('win_rate', 0):.2%}")
        logger.info(f"Total PnL: {performance.get('total_pnl', 0):.2f}")
        logger.info(f"Sharpe Ratio: {performance.get('sharpe_ratio', 0):.2f}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt. Shutting down...")
    except Exception as e:
        logger.error(f"Error running bot: {e}")
        raise