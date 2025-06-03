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
        self.risk_manager = RiskManager()
        
        # Initialize database
        self._init_database()
        
        # Trading state
        self.is_running = False
        self.symbols = {'BTCUSDT'}  # Default symbol
        
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
        """Start the trading bot."""
        try:
            self.is_running = True
            logger.info("Starting trading bot...")
            
            # Initialize exchange client
            await self.exchange_client.initialize()
            
            # Start main trading loop
            while self.is_running:
                await self._trading_loop()
                await asyncio.sleep(1)  # Prevent excessive CPU usage
                
        except Exception as e:
            logger.error(f"Error in trading bot: {e}")
            self.is_running = False
            raise
            
    async def stop(self):
        """Stop the trading bot."""
        self.is_running = False
        await self.exchange_client.close()
        logger.info("Trading bot stopped")
        
    async def _trading_loop(self):
        """Main trading loop."""
        try:
            for symbol in self.symbols:
                # Get market data
                market_data = await self.exchange_client.get_historical_data(symbol, interval="1m", limit=100)
                if not market_data:
                    continue
                    
                # Process market data
                self.market_processor.update_ohlcv(symbol, market_data)
                market_state = self.market_processor.get_market_state(symbol)
                
                # Generate signals
                signals = self.signal_engine.generate_signals(market_state)
                if not signals:
                    continue
                    
                # Process each signal
                for signal in signals:
                    await self._process_signal(symbol, signal, market_state)
                    
        except Exception as e:
            logger.error(f"Error in trading loop: {e}")
            
    async def _process_signal(
        self,
        symbol: str,
        signal: Dict,
        market_state: Dict
    ):
        """Process a trading signal."""
        try:
            # Calculate position parameters
            entry_price = signal['price']
            direction = signal['signal_type']
            
            # Calculate stop loss
            stop_loss = self.risk_manager.calculate_stop_loss(
                symbol, entry_price, direction, market_state
            )
            
            # Calculate position size and leverage
            position_size, leverage = self.risk_manager.calculate_position_size(
                symbol, entry_price, stop_loss, direction, market_state
            )
            
            # Check risk limits
            if not self.risk_manager.check_risk_limits(symbol, position_size, leverage):
                logger.warning(f"Risk limits exceeded for {symbol}")
                return
                
            # Calculate take profit
            take_profit = self.risk_manager.calculate_take_profit(
                symbol, entry_price, stop_loss, direction, market_state
            )
            
            # Add position to risk manager
            if self.risk_manager.add_position(
                symbol, position_size, entry_price,
                stop_loss, take_profit, leverage, direction
            ):
                # Execute trade
                await self._execute_trade(symbol, signal, position_size, leverage)
                
        except Exception as e:
            logger.error(f"Error processing signal for {symbol}: {e}")
            
    async def _execute_trade(
        self,
        symbol: str,
        signal: Dict,
        position_size: float,
        leverage: float
    ):
        """Execute a trade and persist data."""
        try:
            # Create database session
            db = self._get_db_session()
            
            try:
                # Save signal
                db_signal = TradingSignal(
                    symbol=symbol,
                    timestamp=datetime.fromtimestamp(signal['timestamp']),
                    signal_type=signal['signal_type'],
                    confidence=signal['confidence'],
                    price=signal['price'],
                    indicators=signal['indicators'],
                    strategy=signal['strategy']
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
                
                # Commit changes
                db.commit()
                logger.info(f"Trade executed for {symbol}: {signal['signal_type']} at {signal['price']}")
                
            except Exception as e:
                db.rollback()
                logger.error(f"Database error executing trade: {e}")
                raise
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error executing trade for {symbol}: {e}")
            
    def get_performance_summary(self) -> Dict:
        """Get performance summary of the trading bot."""
        try:
            db = self._get_db_session()
            
            try:
                # Get all closed trades
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
                winning_trades = len([t for t in trades if t.pnl > 0])
                total_pnl = sum(t.pnl for t in trades)
                
                # Calculate win rate
                win_rate = winning_trades / total_trades if total_trades > 0 else 0
                
                # Calculate Sharpe ratio (simplified)
                returns = [t.pnl_pct for t in trades if t.pnl_pct is not None]
                if returns:
                    sharpe_ratio = np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0
                else:
                    sharpe_ratio = 0
                    
                return {
                    'total_trades': total_trades,
                    'win_rate': win_rate,
                    'total_pnl': total_pnl,
                    'sharpe_ratio': sharpe_ratio
                }
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error getting performance summary: {e}")
            return {
                'total_trades': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0,
                'sharpe_ratio': 0.0
            } 