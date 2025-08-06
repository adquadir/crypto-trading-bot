#!/usr/bin/env python3
"""
RULE COMPLIANT: Dedicated Profit Scraping Engine Service
This service ensures profit scraping is ALWAYS active as the primary signal source.
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global state
profit_scraping_engine = None
paper_trading_engine = None
exchange_client = None
running = True

async def ensure_profit_scraping_active():
    """RULE COMPLIANT: Ensure profit scraping engine is always active"""
    global profit_scraping_engine, paper_trading_engine, exchange_client
    
    restart_count = 0
    max_restarts = 10
    
    while running and restart_count < max_restarts:
        try:
            logger.info(f"🎯 RULE COMPLIANT: Starting profit scraping engine (attempt {restart_count + 1})")
            
            # Import required modules
            from src.utils.config import load_config
            from src.market_data.exchange_client import ExchangeClient
            from src.trading.enhanced_paper_trading_engine import EnhancedPaperTradingEngine
            from src.strategies.profit_scraping.profit_scraping_engine import ProfitScrapingEngine
            
            # Load RULE COMPLIANT configuration
            config = load_config()
            
            # FORCE Pure Profit Scraping Mode configuration
            config.setdefault('signal_sources', {})
            config['signal_sources'].update({
                'pure_profit_scraping_mode': True,         # RULE COMPLIANT: Default ON
                'profit_scraping_primary': True,           # RULE COMPLIANT: Primary source
                'allow_opportunity_fallback': False,       # RULE COMPLIANT: No fallbacks
                'allow_flow_trading_fallback': False,      # RULE COMPLIANT: No fallbacks
            })
            
            # FORCE Paper trading RULE COMPLIANT settings
            config.setdefault('paper_trading', {})
            config['paper_trading'].update({
                'mode': 'pure_profit_scraping',      # RULE COMPLIANT: Mode
                'initial_balance': 10000.0,          # RULE COMPLIANT: $10,000 virtual starting capital
                'risk_per_trade_pct': 0.05,          # RULE COMPLIANT: 5% = $500 per trade
                'max_positions': 20,                 # RULE COMPLIANT: 20 trades starting
                'leverage': 10.0,                    # RULE COMPLIANT: 10x leverage
                'primary_target_dollars': 18.0,      # RULE COMPLIANT: $18 take profit (fee included)
                'absolute_floor_dollars': 15.0,      # RULE COMPLIANT: $15 floor on reversal
                'stop_loss_dollars': 18.0,           # RULE COMPLIANT: $18 stop loss (fee included)
                'pure_3_rule_mode': True,            # RULE COMPLIANT: Pure 3-rule mode
                'enabled': True
            })
            
            logger.info("✅ RULE COMPLIANT: Configuration loaded")
            
            # Initialize exchange client
            if not exchange_client:
                exchange_client = ExchangeClient()
                logger.info("✅ Exchange client initialized")
            
            # Initialize paper trading engine
            if not paper_trading_engine:
                paper_trading_engine = EnhancedPaperTradingEngine(
                    config=config, 
                    exchange_client=exchange_client,
                    flow_trading_strategy='adaptive'
                )
                logger.info("✅ Paper trading engine initialized")
            
            # Initialize profit scraping engine
            if not profit_scraping_engine:
                profit_scraping_engine = ProfitScrapingEngine(
                    exchange_client=exchange_client,
                    paper_trading_engine=paper_trading_engine,
                    real_trading_engine=None  # Paper trading only
                )
                logger.info("✅ Profit scraping engine initialized")
            
            # CRITICAL: Connect profit scraping to paper trading engine
            if paper_trading_engine and profit_scraping_engine:
                paper_trading_engine.connect_profit_scraping_engine(profit_scraping_engine)
                logger.info("✅ RULE COMPLIANT: Bidirectional connection established")
            
            # RULE COMPLIANT: Start profit scraping with comprehensive symbol list
            symbols_to_monitor = [
                'BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'SOLUSDT', 'XRPUSDT', 
                'BCHUSDT', 'LTCUSDT', 'TRXUSDT', 'ETCUSDT', 'LINKUSDT',
                'XLMUSDT', 'XMRUSDT', 'DASHUSDT', 'ZECUSDT', 'XTZUSDT',
                'BNBUSDT', 'ATOMUSDT', 'ONTUSDT', 'IOTAUSDT', 'BATUSDT', 
                'VETUSDT', 'DOGEUSDT', 'MATICUSDT', 'DOTUSDT', 'AVAXUSDT',
                'UNIUSDT', 'FILUSDT', 'ALGOUSDT', 'SANDUSDT', 'MANAUSDT'
            ]
            
            logger.info(f"🎯 RULE COMPLIANT: Starting profit scraping for {len(symbols_to_monitor)} symbols")
            scraping_started = await profit_scraping_engine.start_scraping(symbols_to_monitor)
            
            if not scraping_started:
                raise ValueError("Failed to start profit scraping - CRITICAL")
                
            if not profit_scraping_engine.active:
                raise ValueError("Profit scraping engine is not active after start - CRITICAL")
            
            logger.info("✅ RULE COMPLIANT: Profit scraping engine ACTIVE and running")
            logger.info(f"✅ RULE COMPLIANT: Monitoring {len(profit_scraping_engine.monitored_symbols)} symbols")
            
            # Start paper trading engine if not already running
            if paper_trading_engine and not paper_trading_engine.is_running:
                logger.info("🎯 RULE COMPLIANT: Starting paper trading engine...")
                await paper_trading_engine.start()
                
                if not paper_trading_engine.is_running:
                    raise ValueError("Paper trading engine failed to start - CRITICAL")
                    
                logger.info("✅ RULE COMPLIANT: Paper trading engine started")
            
            # MONITORING LOOP: Keep profit scraping active
            logger.info("🔄 RULE COMPLIANT: Starting monitoring loop to ensure profit scraping stays active")
            
            while running:
                try:
                    # Check profit scraping engine health every 30 seconds
                    await asyncio.sleep(30)
                    
                    if not profit_scraping_engine.active:
                        logger.error("🚨 RULE VIOLATION: Profit scraping engine went inactive - restarting")
                        raise ValueError("Profit scraping engine went inactive")
                    
                    if len(profit_scraping_engine.monitored_symbols) == 0:
                        logger.error("🚨 RULE VIOLATION: Profit scraping engine has no monitored symbols - restarting")
                        raise ValueError("No monitored symbols")
                    
                    # Log status every 5 minutes
                    current_time = datetime.now()
                    if current_time.minute % 5 == 0 and current_time.second < 30:
                        logger.info(f"✅ RULE COMPLIANT: Profit scraping active - {len(profit_scraping_engine.monitored_symbols)} symbols monitored")
                        logger.info(f"✅ RULE COMPLIANT: Paper trading running - {len(paper_trading_engine.positions)} active positions")
                    
                except Exception as monitor_error:
                    logger.error(f"🚨 Monitoring error: {monitor_error}")
                    raise  # Trigger restart
            
        except Exception as e:
            restart_count += 1
            logger.error(f"❌ Profit scraping service error (attempt {restart_count}): {e}")
            
            if restart_count >= max_restarts:
                logger.error(f"🚨 CRITICAL: Max restarts ({max_restarts}) reached - shutting down")
                break
            
            # Clean up before restart
            profit_scraping_engine = None
            paper_trading_engine = None
            exchange_client = None
            
            # Wait before restart
            wait_time = min(60, restart_count * 10)  # Exponential backoff up to 60s
            logger.info(f"⏳ Waiting {wait_time}s before restart...")
            await asyncio.sleep(wait_time)
    
    logger.error("🚨 CRITICAL: Profit scraping service shutting down")

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    global running
    logger.info(f"🛑 Received signal {signum}, shutting down profit scraping service...")
    running = False

async def main():
    """Main service entry point"""
    logger.info("🚀 RULE COMPLIANT: Starting dedicated profit scraping service")
    logger.info("🎯 RULE COMPLIANT: Pure Profit Scraping Mode - profit scraping is the ONLY signal source")
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await ensure_profit_scraping_active()
    except KeyboardInterrupt:
        logger.info("🛑 Service interrupted by user")
    except Exception as e:
        logger.error(f"🚨 CRITICAL: Service failed: {e}")
        sys.exit(1)
    
    logger.info("🛑 Profit scraping service stopped")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Service interrupted")
    except Exception as e:
        logger.error(f"🚨 CRITICAL: Service startup failed: {e}")
        sys.exit(1) 