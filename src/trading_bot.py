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
        self.debug_mode = True  # Set to False in production
        
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
            
            if self.debug_mode:
                logger.info("=== DEBUG MODE ===")
                test_data = await self.exchange_client.get_historical_data(
                    next(iter(self.symbols)), "1m", 5
                )
                logger.debug(f"Test data sample: {test_data[:1] if test_data else 'No data'}")
                
                if test_data:
                    processed = self.market_processor.update_ohlcv(next(iter(self.symbols)), test_data)
                    logger.info(f"Data processing test: {'SUCCESS' if processed else 'FAILED'}")
                    
                    if processed:
                        market_state = self.market_processor.get_market_state(next(iter(self.symbols)))
                        logger.debug(f"Market state test: {market_state}")
            
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
        await self.exchange_client.close()
        logger.info("Trading bot stopped")
        
    async def _trading_loop(self):
        """Main trading loop."""
        test_limit = 5 if self.debug_mode else 100
        
        for symbol in self.symbols:
            try:
                logger.info(f"Fetching {test_limit} data points for {symbol}")
                
                market_data = await self.exchange_client.get_historical_data(
                    symbol, 
                    interval="1m", 
                    limit=test_limit
                )
                
                if not market_data:
                    logger.warning(f"No market data received for {symbol}")
                    continue
                    
                if self.debug_mode:
                    logger.debug(f"First data point: {market_data[0]}")
                
                # Process market data
                processed = self.market_processor.update_ohlcv(symbol, market_data)
                if not processed:
                    logger.warning(f"Failed to process market data for {symbol}")
                    continue
                    
                market_state = self.market_processor.get_market_state(symbol)
                if not market_state:
                    logger.warning(f"No market state available for {symbol}")
                    continue
                
                # Generate signals
                signals = self.signal_engine.generate_signals(market_state)
                if not signals:
                    continue
                    
                # Process each signal
                for signal in signals:
                    try:
                        await self._process_signal(symbol, signal, market_state)
                    except Exception as e:
                        logger.error(f"Error processing signal for {symbol}: {e}")
                        continue
                    
            except Exception as e:
                logger.error(f"Error processing symbol {symbol}: {e}")
                continue
            
    async def _process_signal(
        self,
        symbol: str,
        signal: Dict,
        market_state: Dict
    ):
        """Process a trading signal."""
        try:
            # Validate signal
            required_signal_keys = {'price', 'signal_type', 'timestamp'}
            if not all(k in signal for k in required_signal_keys):
                missing = required_signal_keys - set(signal.keys())
                logger.error(f"Invalid signal for {symbol}. Missing keys: {missing}")
                return
                
            logger.info(f"Processing {signal['signal_type']} signal for {symbol} at {signal['price']}")

            # Calculate position parameters
            entry_price = float(signal['price'])
            direction = signal['signal_type']
            
            # Risk management calculations
            stop_loss = self.risk_manager.calculate_stop_loss(
                symbol, entry_price, direction, market_state
            )
            if stop_loss is None:
                logger.error(f"Failed to calculate stop loss for {symbol}")
                return
            
            position_size, leverage = self.risk_manager.calculate_position_size(
                symbol, entry_price, stop_loss, direction, market_state
            )
            if position_size is None or leverage is None:
                logger.error(f"Failed to calculate position size for {symbol}")
                return
            
            if not self.risk_manager.check_risk_limits(symbol, position_size, leverage):
                logger.warning(f"Risk limits exceeded for {symbol}")
                return
                
            take_profit = self.risk_manager.calculate_take_profit(
                symbol, entry_price, stop_loss, direction, market_state
            )
            if take_profit is None:
                logger.error(f"Failed to calculate take profit for {symbol}")
                return
            
            # Add position to risk manager
            if self.risk_manager.add_position(
                symbol, position_size, entry_price,
                stop_loss, take_profit, leverage, direction
            ):
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