#!/usr/bin/env python3
"""
Connect Paper Trading to Profit Scraping Signals
This script integrates the profit scraping engine with paper trading
"""

import asyncio
import logging
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append('/home/ubuntu/crypto-trading-bot')

from src.trading.enhanced_paper_trading_engine import EnhancedPaperTradingEngine
from src.strategies.profit_scraping.profit_scraping_engine import ProfitScrapingEngine
from src.opportunity.opportunity_manager import OpportunityManager
from src.signals.realtime_scalping_manager import RealtimeScalpingManager
from src.market_data.exchange_client import ExchangeClient
from src.database.database import Database

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PaperTradingWithSignals:
    def __init__(self):
        self.db = Database()
        self.exchange_client = ExchangeClient()
        self.profit_scraping_engine = ProfitScrapingEngine()
        self.scalping_manager = RealtimeScalpingManager()
        self.opportunity_manager = OpportunityManager()
        self.paper_trading_engine = None
        
    async def initialize(self):
        """Initialize all components"""
        logger.info("🚀 Initializing Paper Trading with Signals...")
        
        # Initialize database
        await self.db.initialize()
        
        # Initialize exchange client
        await self.exchange_client.initialize()
        
        # Initialize profit scraping engine
        await self.profit_scraping_engine.initialize()
        
        # Initialize scalping manager
        await self.scalping_manager.initialize()
        
        # Initialize opportunity manager with signal sources
        self.opportunity_manager.add_signal_source(self.profit_scraping_engine)
        self.opportunity_manager.add_signal_source(self.scalping_manager)
        
        # Initialize paper trading engine with opportunity manager
        self.paper_trading_engine = EnhancedPaperTradingEngine(
            opportunity_manager=self.opportunity_manager
        )
        await self.paper_trading_engine.initialize()
        
        logger.info("✅ All components initialized successfully")
        
    async def start_trading(self):
        """Start the paper trading with live signals"""
        logger.info("🎯 Starting Paper Trading with Live Signals...")
        
        # Start all signal sources
        await self.profit_scraping_engine.start()
        await self.scalping_manager.start()
        await self.opportunity_manager.start()
        
        # Start paper trading
        await self.paper_trading_engine.start()
        
        logger.info("🚀 Paper Trading with Signals is now ACTIVE!")
        logger.info("📊 Monitoring for trading opportunities...")
        
        # Keep running and log status periodically
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                # Get current status
                status = await self.paper_trading_engine.get_status()
                positions = await self.paper_trading_engine.get_positions()
                
                logger.info(f"💰 Balance: ${status.get('virtual_balance', 0):.2f}")
                logger.info(f"📈 Active Positions: {len(positions)}")
                logger.info(f"🎯 Total Trades: {status.get('completed_trades', 0)}")
                logger.info(f"📊 Return: {status.get('total_return_pct', 0):.2f}%")
                
                # Check for new signals
                signals = await self.opportunity_manager.get_recent_signals(limit=5)
                if signals:
                    logger.info(f"🔔 Recent Signals: {len(signals)} new opportunities detected")
                
            except Exception as e:
                logger.error(f"❌ Error in monitoring loop: {e}")
                await asyncio.sleep(5)
                
    async def stop(self):
        """Stop all components"""
        logger.info("🛑 Stopping Paper Trading with Signals...")
        
        if self.paper_trading_engine:
            await self.paper_trading_engine.stop()
        
        await self.opportunity_manager.stop()
        await self.scalping_manager.stop()
        await self.profit_scraping_engine.stop()
        
        logger.info("✅ All components stopped")

async def main():
    """Main entry point"""
    system = PaperTradingWithSignals()
    
    try:
        await system.initialize()
        await system.start_trading()
    except KeyboardInterrupt:
        logger.info("🛑 Received shutdown signal...")
    except Exception as e:
        logger.error(f"❌ System error: {e}")
    finally:
        await system.stop()

if __name__ == "__main__":
    print("=" * 80)
    print("🎯 PAPER TRADING WITH PROFIT SCRAPING SIGNALS")
    print("=" * 80)
    print()
    print("📋 FEATURES:")
    print("   ✅ Live Profit Scraping Signals")
    print("   ✅ Real-time Scalping Opportunities")
    print("   ✅ Paper Trading Execution")
    print("   ✅ Risk Management")
    print("   ✅ Performance Tracking")
    print()
    print("🚀 Starting system...")
    print()
    
    asyncio.run(main())
