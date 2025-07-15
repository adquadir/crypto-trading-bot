#!/usr/bin/env python3
"""
Start Paper Trading with Profit Scraping Engine
Implements the adaptive profit scraping fixes for proper signal generation
"""

import asyncio
import logging
import os
import sys
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.trading.enhanced_paper_trading_engine import EnhancedPaperTradingEngine
from src.strategies.profit_scraping.profit_scraping_engine import ProfitScrapingEngine
from src.opportunity.opportunity_manager import OpportunityManager
from src.market_data.exchange_client import ExchangeClient
from src.database.database import Database
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

async def main():
    """Start Paper Trading with Profit Scraping Engine"""
    try:
        logger.info("🚀 Starting Paper Trading with Profit Scraping Engine")
        
        # Initialize database
        db = Database()
        
        # Initialize exchange client
        exchange_client = ExchangeClient()
        
        # Initialize strategy manager
        from src.strategy.strategy_manager import StrategyManager
        strategy_manager = StrategyManager(exchange_client)
        
        # Initialize risk manager
        from src.risk.risk_manager import RiskManager
        from src.utils.config import load_config
        config = load_config()
        risk_manager = RiskManager(config)
        
        # Initialize signal tracker
        from src.signals.enhanced_signal_tracker import EnhancedSignalTracker
        signal_tracker = EnhancedSignalTracker()
        
        # Initialize opportunity manager with correct parameters
        opportunity_manager = OpportunityManager(exchange_client, strategy_manager, risk_manager, signal_tracker)
        
        # Paper trading configuration with tight SL/TP
        paper_config = {
            'initial_balance': 10000.0,
            'max_daily_loss': 0.05,  # 5% max daily loss
            'max_total_exposure': 0.8,  # 80% max exposure
            'leverage': 10,
            'fee_rate': 0.001,
            'stop_loss_pct': 0.005,  # 0.5% stop loss (tight for scalping)
            'take_profit_pct': 0.008,  # 0.8% take profit (tight for scalping)
            'max_positions': 25,  # Allow many positions with $200 margin each
            'position_size_pct': 0.02,  # 2% risk per trade
            'enable_ml_filtering': True,
            'trend_filtering': True,
            'early_exit_enabled': True
        }
        
        # Initialize Enhanced Paper Trading Engine
        paper_engine = EnhancedPaperTradingEngine(
            config=paper_config,
            exchange_client=exchange_client,
            flow_trading_strategy='adaptive'
        )
        
        # Initialize Profit Scraping Engine
        profit_scraping_engine = ProfitScrapingEngine(
            exchange_client=exchange_client,
            paper_trading_engine=paper_engine,
            real_trading_engine=None  # Paper trading only
        )
        
        # Connect engines
        paper_engine.connect_opportunity_manager(opportunity_manager)
        paper_engine.connect_profit_scraping_engine(profit_scraping_engine)
        
        logger.info("✅ All engines connected successfully")
        
        # Start opportunity manager
        await opportunity_manager.start()
        logger.info("✅ Opportunity Manager started")
        
        # Start profit scraping engine with major crypto pairs
        major_symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'SOLUSDT']
        profit_scraping_started = await profit_scraping_engine.start_scraping(major_symbols)
        
        if profit_scraping_started:
            logger.info("✅ Profit Scraping Engine started successfully")
        else:
            logger.warning("⚠️ Profit Scraping Engine failed to start, continuing with fallback")
        
        # Start paper trading engine
        await paper_engine.start()
        logger.info("✅ Paper Trading Engine started")
        
        # Print status
        logger.info("\n" + "="*60)
        logger.info("🎯 ADAPTIVE PROFIT SCRAPING PAPER TRADING ACTIVE")
        logger.info("="*60)
        logger.info(f"📊 Account Balance: ${paper_config['initial_balance']:,.2f}")
        logger.info(f"💰 Max Daily Loss: {paper_config['max_daily_loss']*100:.1f}%")
        logger.info(f"🎯 Max Exposure: {paper_config['max_total_exposure']*100:.1f}%")
        logger.info(f"📈 Leverage: {paper_config['leverage']}x")
        logger.info(f"🛡️ Stop Loss: {paper_config['stop_loss_pct']*100:.3f}%")
        logger.info(f"🎯 Take Profit: {paper_config['take_profit_pct']*100:.3f}%")
        logger.info(f"🔄 Max Positions: {paper_config['max_positions']}")
        logger.info(f"📊 Monitored Symbols: {', '.join(major_symbols)}")
        
        # Status monitoring loop
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                # Get status
                paper_status = paper_engine.get_account_status()
                profit_scraping_status = profit_scraping_engine.get_status()
                
                logger.info("\n" + "="*40)
                logger.info(f"📊 PAPER TRADING STATUS - {datetime.now().strftime('%H:%M:%S')}")
                logger.info("="*40)
                logger.info(f"💰 Balance: ${paper_status['balance']:,.2f}")
                logger.info(f"📈 Equity: ${paper_status['equity']:,.2f}")
                logger.info(f"📊 Unrealized P&L: ${paper_status['unrealized_pnl']:,.2f}")
                logger.info(f"💸 Realized P&L: ${paper_status['realized_pnl']:,.2f}")
                logger.info(f"🎯 Active Positions: {paper_status['active_positions']}")
                logger.info(f"📋 Total Trades: {paper_status['total_trades']}")
                logger.info(f"🏆 Win Rate: {paper_status['win_rate']:.1%}")
                
                logger.info("\n" + "="*40)
                logger.info("🎯 PROFIT SCRAPING STATUS")
                logger.info("="*40)
                logger.info(f"🟢 Active: {profit_scraping_status['active']}")
                logger.info(f"📊 Monitored Symbols: {len(profit_scraping_status.get('monitored_symbols', []))}")
                logger.info(f"🎯 Active Trades: {profit_scraping_status['active_trades']}")
                logger.info(f"📋 Total Trades: {profit_scraping_status['total_trades']}")
                logger.info(f"🏆 Win Rate: {profit_scraping_status.get('win_rate', 0):.1%}")
                logger.info(f"💰 Total Profit: ${profit_scraping_status.get('total_profit', 0):,.2f}")
                
                # Show recent opportunities
                opportunities = profit_scraping_engine.get_opportunities()
                total_opportunities = sum(len(opps) for opps in opportunities.values())
                
                if total_opportunities > 0:
                    logger.info(f"\n🎯 Current Opportunities: {total_opportunities}")
                    for symbol, symbol_opps in opportunities.items():
                        for opp in symbol_opps[:2]:  # Show top 2 per symbol
                            logger.info(f"   {symbol}: {opp['level']['level_type']} @ {opp['level']['price']:.4f} (score: {opp['opportunity_score']})")
                
                # Show recent trades
                if paper_status['total_trades'] > 0:
                    recent_trades = paper_engine.completed_trades[-3:]  # Last 3 trades
                    logger.info(f"\n📋 Recent Trades:")
                    for trade in recent_trades:
                        pnl_color = "🟢" if trade.pnl > 0 else "🔴"
                        logger.info(f"   {pnl_color} {trade.symbol} {trade.side} ${trade.pnl:+.2f} ({trade.pnl_pct:+.2%}) - {trade.exit_reason}")
                
                logger.info("="*40)
                
            except KeyboardInterrupt:
                logger.info("\n🛑 Stopping Paper Trading with Profit Scraping...")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(5)
        
        # Cleanup
        paper_engine.stop()
        await profit_scraping_engine.stop_scraping()
        await opportunity_manager.stop()
        
        logger.info("✅ Paper Trading with Profit Scraping stopped successfully")
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main()) 