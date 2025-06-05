# File: src/trading_bot.py
from typing import Dict, List, Optional
import asyncio
import logging
from datetime import datetime
import os
from dotenv import load_dotenv
import numpy as np

from src.market_data.exchange_client import ExchangeClient
from src.market_data.processor import MarketDataProcessor
from src.signals.engine import SignalEngine
from src.risk.manager import RiskManager
from src.database.models import Base, MarketData, OrderBook, TradingSignal, Trade, PerformanceMetrics
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from src.market_data.symbol_discovery import SymbolDiscovery, TradingOpportunity

logger = logging.getLogger(__name__)

class TradingBot:
    def __init__(self):
        # Load environment variables
        load_dotenv()
        
        # Initialize components
        self.exchange_client = ExchangeClient(
            api_key=os.getenv('BINANCE_API_KEY'),
            api_secret=os.getenv('BINANCE_API_SECRET')
        )
        self.market_processor = MarketDataProcessor()
        self.signal_engine = SignalEngine()
        
        # Initialize database
        self._init_database()
        
        # Trading state
        self.is_running = False
        self.debug_mode = True  # Set to False in production
        self.risk_per_trade = float(os.getenv('RISK_PER_TRADE', '50.0'))
        self.max_open_trades = int(os.getenv('MAX_OPEN_TRADES', '5'))
        
        # Start opportunity scanning in background
        self.opportunity_scan_task = None
        
        # Risk manager will be initialized in start() after getting account balance
        self.risk_manager = None
        self.symbol_discovery = None
        
    def _init_database(self):
        """Initialize database connection and create tables."""
        try:
            database_url = os.getenv('DATABASE_URL')
            if not database_url:
                raise ValueError("DATABASE_URL environment variable not set")
                
            self.engine = create_engine(database_url)
            Base.metadata.create_all(self.engine)
            self.SessionLocal = sessionmaker(bind=self.engine)
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise
            
    def _get_db_session(self) -> Session:
        """Get a new database session."""
        return self.SessionLocal()
        
    async def start(self):
        """Start the trading bot with debug checks."""
        try:
            self.is_running = True
            logger.info("Starting trading bot...")
            
            # Initialize with debug checks
            await self.exchange_client.initialize()
            await self.exchange_client.test_proxy_connection()
            
            # Get account balance and initialize risk manager
            account_info = await asyncio.to_thread(self.exchange_client.client.get_account)
            total_balance = sum(float(b['balance']) for b in account_info['balances'] if float(b['balance']) > 0)
            self.risk_manager = RiskManager(account_balance=total_balance)
            self.symbol_discovery = SymbolDiscovery(self.exchange_client)
            
            # Start opportunity scanning in background
            self.opportunity_scan_task = asyncio.create_task(
                self.symbol_discovery.update_opportunities(self.risk_per_trade)
            )
            
            if self.debug_mode:
                logger.info("=== DEBUG MODE ===")
                # Test symbol discovery
                opportunities = await self.symbol_discovery.scan_opportunities(self.risk_per_trade)
                logger.info(f"Found {len(opportunities)} trading opportunities")
                if opportunities:
                    top_opp = opportunities[0]
                    logger.info(f"Top opportunity: {top_opp.symbol} {top_opp.direction} "
                              f"Score: {top_opp.score:.2f} "
                              f"Confidence: {top_opp.confidence:.2f}")
            
            # Start main trading loop
            while self.is_running:
                try:
                    await self._trading_loop()
                except Exception as e:
                    logger.error(f"Error in trading loop: {e}")
                    await asyncio.sleep(5)
                finally:
                    await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Critical error in trading bot: {e}")
            self.is_running = False
            raise
            
    async def stop(self):
        """Stop the trading bot."""
        self.is_running = False
        if self.opportunity_scan_task:
            self.opportunity_scan_task.cancel()
        await self.exchange_client.close()
        logger.info("Trading bot stopped")
        
    async def _trading_loop(self):
        """Main trading loop."""
        try:
            # Get top opportunities
            opportunities = self.symbol_discovery.get_top_opportunities(self.max_open_trades)
            
            for opportunity in opportunities:
                try:
                    # Check if we already have a position for this symbol
                    if self.risk_manager.has_position(opportunity.symbol):
                        continue
                    
                    # Validate opportunity
                    if not self._validate_opportunity(opportunity):
                        continue
                    
                    # Process the opportunity
                    await self._process_opportunity(opportunity)
                    
                except Exception as e:
                    logger.error(f"Error processing opportunity for {opportunity.symbol}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error in trading loop: {e}")
            
    def _validate_opportunity(self, opportunity: TradingOpportunity) -> bool:
        """Validate a trading opportunity."""
        try:
            # Check minimum requirements
            if opportunity.confidence < 0.7:
                return False
                
            if opportunity.risk_reward < 2.0:
                return False
                
            if opportunity.volume_24h < 1000000:  # Minimum 1M USDT volume
                return False
                
            # Check risk limits
            if not self.risk_manager.check_risk_limits(
                opportunity.symbol,
                opportunity.leverage,
                opportunity.risk_reward
            ):
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error validating opportunity: {e}")
            return False
            
    async def _process_opportunity(self, opportunity: TradingOpportunity):
        """Process a trading opportunity."""
        try:
            logger.info(f"Processing {opportunity.direction} opportunity for {opportunity.symbol}")
            logger.info(f"Entry: {opportunity.entry_price:.2f}")
            logger.info(f"Take Profit: {opportunity.take_profit:.2f}")
            logger.info(f"Stop Loss: {opportunity.stop_loss:.2f}")
            logger.info(f"Leverage: {opportunity.leverage:.1f}x")
            logger.info(f"Confidence: {opportunity.confidence:.2f}")
            logger.info(f"Score: {opportunity.score:.2f}")
            
            # Create signal
            signal = {
                'symbol': opportunity.symbol,
                'timestamp': datetime.now().timestamp(),
                'signal_type': opportunity.direction.lower(),
                'confidence': opportunity.confidence,
                'price': opportunity.entry_price,
                'indicators': opportunity.indicators,
                'strategy': 'opportunity_scanner'
            }
            
            # Execute trade
            await self._execute_trade(
                opportunity.symbol,
                signal,
                self.risk_per_trade,
                opportunity.leverage
            )
            
        except Exception as e:
            logger.error(f"Error processing opportunity: {e}")
            
    async def _execute_trade(
        self,
        symbol: str,
        signal: Dict,
        position_size: float,
        leverage: float
    ):
        """Execute a trade and persist data."""
        db = None
        try:
            db = self._get_db_session()
            
            # Save signal
            db_signal = TradingSignal(
                symbol=symbol,
                timestamp=datetime.fromtimestamp(signal['timestamp']),
                signal_type=signal['signal_type'],
                confidence=signal.get('confidence', 0.5),
                price=signal['price'],
                indicators=signal.get('indicators', {}),
                strategy=signal.get('strategy', 'default')
            )
            db.add(db_signal)
            db.flush()
            
            # Create trade
            trade = Trade(
                symbol=symbol,
                entry_time=datetime.fromtimestamp(signal['timestamp']),
                entry_price=signal['price'],
                position_size=position_size,
                leverage=leverage,
                status='OPEN',
                signal_id=db_signal.id
            )
            db.add(trade)
            
            db.commit()
            logger.info(f"Trade executed for {symbol}: {signal['signal_type']} at {signal['price']}")
            
        except Exception as e:
            if db:
                db.rollback()
            logger.error(f"Error executing trade for {symbol}: {e}")
            raise
        finally:
            if db:
                db.close()
            
    def get_performance_summary(self) -> Dict:
        """Get performance summary of the trading bot."""
        db = None
        try:
            db = self._get_db_session()
            
            trades = db.query(Trade).filter(Trade.status == 'CLOSED').all()
            
            if not trades:
                return {
                    'total_trades': 0,
                    'win_rate': 0.0,
                    'total_pnl': 0.0,
                    'sharpe_ratio': 0.0
                }
                
            # Calculate metrics
            total_trades = len(trades)
            winning_trades = len([t for t in trades if t.pnl and t.pnl > 0])
            total_pnl = sum(t.pnl for t in trades if t.pnl is not None)
            
            win_rate = winning_trades / total_trades if total_trades > 0 else 0
            
            returns = [t.pnl_pct for t in trades if t.pnl_pct is not None]
            sharpe_ratio = np.mean(returns) / np.std(returns) if returns and np.std(returns) > 0 else 0
                
            return {
                'total_trades': total_trades,
                'win_rate': win_rate,
                'total_pnl': total_pnl,
                'sharpe_ratio': sharpe_ratio
            }
            
        except Exception as e:
            logger.error(f"Error getting performance summary: {e}")
            return {
                'total_trades': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0,
                'sharpe_ratio': 0.0
            }
        finally:
            if db:
                db.close()