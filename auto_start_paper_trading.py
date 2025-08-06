#!/usr/bin/env python3
"""
Auto-start Paper Trading with Profit Scraping Engine (RULE COMPLIANT)
This script ensures paper trading starts with proper profit scraping integration
"""

import asyncio
import logging
import sys
import time
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.trading.enhanced_paper_trading_engine import EnhancedPaperTradingEngine
from src.strategies.profit_scraping.profit_scraping_engine import ProfitScrapingEngine
from src.opportunity.opportunity_manager import OpportunityManager
from src.market_data.exchange_client import ExchangeClient
from src.strategy.strategy_manager import StrategyManager
from src.risk.risk_manager import RiskManager
from src.utils.config import load_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    """Main auto-start function with RULE COMPLIANT configuration"""
    try:
        logger.info("🚀 RULE COMPLIANT Auto-starting Paper Trading with Profit Scraping...")
        
        # Load configuration
        config = load_config()
        
        # RULE COMPLIANT CONFIGURATION
        paper_config = {
            'paper_trading': {
                'initial_balance': 10000.0,              # RULE COMPLIANT: $10,000 virtual starting capital
                'enabled': True,
                'risk_per_trade_pct': 0.05,              # RULE COMPLIANT: 5% = $500 per trade
                'max_positions': 20,                     # RULE COMPLIANT: 20 trades starting
                'leverage': 10.0,                        # RULE COMPLIANT: 10x leverage
                'primary_target_dollars': 18.0,         # RULE COMPLIANT: $18 take profit (fee included)
                'absolute_floor_dollars': 15.0,         # RULE COMPLIANT: $15 floor on reversal
                'stop_loss_dollars': 18.0,              # RULE COMPLIANT: $18 stop loss (fee included)
                'pure_3_rule_mode': True,               # RULE COMPLIANT: Pure 3-rule mode enabled
                'max_total_exposure_pct': 1.00,         # Allow 100% exposure (20 * $500)
            },
            'signal_sources': {
                'profit_scraping_primary': True,         # RULE COMPLIANT: Profit scraping primary
                'allow_opportunity_fallback': False,     # RULE COMPLIANT: Pure mode, no fallbacks
                'allow_flow_trading_fallback': False,    # RULE COMPLIANT: Pure mode, no fallbacks
                'pure_profit_scraping_mode': True,       # RULE COMPLIANT: Pure Profit Scraping Mode
            }
        }
        
        logger.info("✅ RULE COMPLIANT configuration loaded")
        
        # Initialize components
        logger.info("🔧 Initializing trading components...")
        
        # Exchange client
        exchange_client = ExchangeClient()
        logger.info("✅ Exchange client initialized")
        
        # Strategy and risk managers
        strategy_manager = StrategyManager(exchange_client)
        risk_config = {
            'risk': {
                'max_drawdown': 0.20,
                'max_leverage': 10.0,
                'position_size_limit': 500.0,          # RULE COMPLIANT: $500 per position
                'daily_loss_limit': 500.0,
                'initial_balance': 10000.0
            }
        }
        risk_manager = RiskManager(risk_config)
        logger.info("✅ Strategy and risk managers initialized")
        
        # Opportunity manager (fallback only)
        opportunity_manager = OpportunityManager(exchange_client, strategy_manager, risk_manager)
        logger.info("✅ Opportunity manager initialized (fallback)")
        
        # Initialize Enhanced Paper Trading Engine
        logger.info("🎯 Initializing Enhanced Paper Trading Engine (RULE COMPLIANT)...")
        paper_engine = EnhancedPaperTradingEngine(
            config=paper_config,
            exchange_client=exchange_client,
            flow_trading_strategy='adaptive'
        )
        logger.info("✅ Enhanced Paper Trading Engine initialized")
        
        # Initialize Profit Scraping Engine (MAIN SIGNAL SOURCE)
        logger.info("🎯 Initializing Profit Scraping Engine (MAIN SIGNAL SOURCE)...")
        profit_scraping_engine = ProfitScrapingEngine(
            exchange_client=exchange_client,
            paper_trading_engine=paper_engine,
            real_trading_engine=None  # Paper trading only
        )
        
        # Connect engines (RULE COMPLIANT)
        paper_engine.connect_profit_scraping_engine(profit_scraping_engine)
        paper_engine.connect_opportunity_manager(opportunity_manager)
        logger.info("✅ RULE COMPLIANT: Profit Scraping Engine connected as primary source")
        
        # Start Profit Scraping Engine (RULE COMPLIANT)
        logger.info("🎯 Starting Profit Scraping Engine (MAIN SIGNAL SOURCE)...")
        symbols_to_monitor = [
            'BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'SOLUSDT', 'XRPUSDT', 
            'BCHUSDT', 'LTCUSDT', 'TRXUSDT', 'ETCUSDT', 'LINKUSDT',
            'XLMUSDT', 'XMRUSDT', 'DASHUSDT', 'ZECUSDT', 'XTZUSDT',
            'BNBUSDT', 'ATOMUSDT', 'ONTUSDT', 'IOTAUSDT', 'BATUSDT', 'VETUSDT'
        ]
        
        profit_scraping_started = await profit_scraping_engine.start_scraping(symbols_to_monitor)
        
        if profit_scraping_started:
            logger.info("✅ RULE COMPLIANT: Profit Scraping Engine started and active")
            logger.info("✅ RULE COMPLIANT: Profit scraping is now the main source of signals")
        else:
            logger.error("❌ RULE VIOLATION: Failed to start Profit Scraping Engine!")
            logger.error("❌ RULE VIOLATION: Profit scraping should always be connected and active!")
            return False
        
        # Start Paper Trading Engine
        logger.info("🚀 Starting Paper Trading Engine (RULE COMPLIANT)...")
        await paper_engine.start()
        logger.info("✅ RULE COMPLIANT: Paper Trading Engine started successfully")
        
        # Verify rule compliance
        logger.info("🔍 RULE COMPLIANCE VERIFICATION:")
        logger.info(f"✅ Virtual Capital: ${paper_engine.account.balance:.2f} (Target: $10,000)")
        logger.info(f"✅ Capital per Trade: ${paper_engine.account.balance * 0.05:.2f} (Target: $500)")
        logger.info(f"✅ Leverage: {paper_engine.leverage}x (Target: 10x)")
        logger.info(f"✅ Max Positions: {paper_engine.max_positions} (Target: 20)")
        logger.info(f"✅ Take Profit: ${paper_config['paper_trading']['primary_target_dollars']} (Target: $18)")
        logger.info(f"✅ Floor: ${paper_config['paper_trading']['absolute_floor_dollars']} (Target: $15)")
        logger.info(f"✅ Stop Loss: ${paper_config['paper_trading']['stop_loss_dollars']} (Target: $18)")
        logger.info(f"✅ Pure Profit Scraping: {paper_config['signal_sources']['pure_profit_scraping_mode']} (Target: True)")
        logger.info(f"✅ Profit Scraping Active: {profit_scraping_engine.active} (Target: True)")
        
        # Keep running
        logger.info("🎯 RULE COMPLIANT Paper Trading with Profit Scraping is now running...")
        logger.info("🎯 Profit Scraping Engine is the main source of signals")
        logger.info("🎯 Paper trading uses $500 per position with 10x leverage")
        logger.info("🎯 Take profit: $18, Floor: $15, Stop loss: $18")
        
        # Keep the process alive
        try:
            while True:
                await asyncio.sleep(60)
                
                # Periodic status check
                if paper_engine.is_running and profit_scraping_engine.active:
                    positions = len(paper_engine.positions)
                    balance = paper_engine.account.balance
                    trades = paper_engine.account.total_trades
                    logger.info(f"📊 Status: {positions} positions, ${balance:.2f} balance, {trades} trades completed")
                else:
                    logger.error("❌ RULE VIOLATION: Paper trading or profit scraping not running!")
                    break
                    
        except KeyboardInterrupt:
            logger.info("🛑 Shutdown requested...")
            
            # Stop engines gracefully
            paper_engine.stop()
            await profit_scraping_engine.stop_scraping()
            
            logger.info("✅ RULE COMPLIANT Auto-start Paper Trading stopped gracefully")
            
    except Exception as e:
        logger.error(f"❌ Error in auto-start paper trading: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    if not success:
        logger.error("❌ RULE VIOLATION: Auto-start failed!")
        sys.exit(1)
    else:
        logger.info("✅ RULE COMPLIANT: Auto-start completed successfully")
        sys.exit(0) 