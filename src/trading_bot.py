# File: src/trading_bot.py
from typing import Dict, List, Optional, Any
import asyncio
import logging
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import numpy as np
import json
from pathlib import Path
import time
import pandas as pd
import yaml
import sys
import signal

# Add src directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.market_data.exchange_client import ExchangeClient
from src.market_data.processor import MarketDataProcessor
from src.signals.engine import SignalEngine
from src.risk.manager import RiskManager
from src.database.models import Base, MarketData, OrderBook, TradingSignal, Trade, PerformanceMetrics
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from src.market_data.symbol_discovery import SymbolDiscovery, TradingOpportunity
from src.signals.signal_generator import SignalGenerator
from src.utils.config import load_config, validate_config
from src.market_data.websocket_client import MarketDataWebSocket
from src.models import Strategy as StrategyModel
from src.database.database import Database
from src.strategy.dynamic_config import strategy_config
from src.strategy.strategy_manager import StrategyManager
from src.opportunity.opportunity_manager import OpportunityManager
from src.utils.logger import setup_logger

logger = logging.getLogger(__name__)

load_dotenv()

# Create a global instance of TradingBot that can be imported by other modules
trading_bot = None

class TradingBot:
    def __init__(self):
        """Initialize the trading bot."""
        # Load environment variables
        load_dotenv()
        
        # Load configuration
        self.config = self._load_config()
        
        # Initialize components as None
        self.exchange_client = None
        self.ws_manager = None
        self.symbol_discovery = None
        self.risk_manager = None
        self.strategy_manager = None
        self.opportunity_manager = None
        self.signal_generator = None
        
        # Initialize task tracking
        self.health_check_task = None
        self.funding_rate_task = None
        self.position_task = None
        self.running = False
        
        # Initialize state
        self.position_levels = {}
        self.opportunities = {}
        self.profiles = self._get_default_profiles()
        self._balance_cache = None
        self._last_balance_update = 0
        self._balance_cache_ttl = 60  # Cache balance for 60 seconds
        
        # Set strategy config
        self.strategy_config = {}
        
        # Do NOT call async _initialize_components here
        # self._initialize_components()
        
        # Set trading intervals with defaults
        self.health_check_interval = self.config.get('trading', {}).get('health_check_interval', 60)
        self.funding_rate_interval = self.config.get('trading', {}).get('funding_rate_interval', 300)
        self.position_interval = self.config.get('trading', {}).get('position_interval', 30)
        self.signal_interval = self.config.get('trading', {}).get('signal_interval', 15)
        self.scan_interval = self.config.get('trading', {}).get('scan_interval', 10)
        
        # Trading state
        self.debug_mode = True  # Set to False in production
        self.risk_per_trade = float(os.getenv('RISK_PER_TRADE', '50.0'))
        self.max_open_trades = int(os.getenv('MAX_OPEN_TRADES', '5'))
        
        # Start opportunity scanning in background
        self.opportunity_scan_task = None
        
        # Risk manager will be initialized in start() after getting account balance
        self.active_trades = {}
        self.trade_history = []
        self._shutdown_event = asyncio.Event()
        
        # New attributes for profile performance tracking
        self.parameter_history = []
        
        # Initialize WebSocket manager
        self.ws_manager = MarketDataWebSocket(
            exchange_client=self.exchange_client,
            symbols=[]
        )
        
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
        
    async def _get_account_balance(self) -> float:
        """Get total account balance with caching and error handling."""
        current_time = datetime.now().timestamp()
        
        # Return cached balance if still valid
        if (self._balance_cache is not None and 
            current_time - self._last_balance_update < self._balance_cache_ttl):
            return self._balance_cache
            
        try:
            # Get account info using CCXT's fetch_balance
            account_info = await asyncio.to_thread(
                self.exchange_client.client.fetch_balance
            )
            
            if not account_info or 'total' not in account_info:
                raise ValueError("Invalid account info response")
                
            # Calculate total balance
            total_balance = 0
            asset_balances = {}
            
            for asset, amount in account_info['total'].items():
                try:
                    if amount and amount > 0:
                        asset_balances[asset] = amount
                        total_balance += amount
                except (ValueError, TypeError) as e:
                    logger.warning(f"Error processing balance for asset {asset}: {e}")
                    continue
            
            # Log detailed balance information
            logger.info(f"Account balance breakdown:")
            for asset, amount in asset_balances.items():
                logger.info(f"  {asset}: {amount:.8f}")
            logger.info(f"Total balance: {total_balance:.8f}")
            
            # Update cache
            self._balance_cache = total_balance
            self._last_balance_update = current_time
            
            return total_balance
            
        except Exception as e:
            logger.error(f"Error getting account balance: {e}")
            # If we have a cached balance, use it as fallback
            if self._balance_cache is not None:
                logger.warning(f"Using cached balance: {self._balance_cache}")
                return self._balance_cache
            # If no cache, use a safe default
            default_balance = float(os.getenv('DEFAULT_ACCOUNT_BALANCE', '1000.0'))
            logger.warning(f"Using default balance: {default_balance}")
            return default_balance

    async def _initialize_components(self):
        """Initialize all trading bot components."""
        try:
            # Initialize exchange client first
            self.exchange_client = ExchangeClient()
            await self.exchange_client.initialize()
            
            # Initialize WebSocket client
            self.ws_manager = MarketDataWebSocket(
                exchange_client=self.exchange_client,
                symbols=[]
            )
            await self.ws_manager.initialize()
            
            # Initialize symbol discovery
            self.symbol_discovery = SymbolDiscovery(self.exchange_client)
            await self.symbol_discovery.initialize()
            
            # Update WebSocket manager with discovered symbols
            if self.symbol_discovery.symbols:
                self.ws_manager.update_symbols(list(self.symbol_discovery.symbols))
            
            # Initialize risk manager
            self.risk_manager = RiskManager(self.config)
            await self.risk_manager.initialize()
            
            # Initialize strategy manager
            self.strategy_manager = StrategyManager(self.config)
            await self.strategy_manager.initialize()
            
            # Initialize opportunity manager
            self.opportunity_manager = OpportunityManager(
                self.exchange_client,
                self.risk_manager,
                self.strategy_manager
            )
            await self.opportunity_manager.initialize()
            
            # Initialize signal generator
            self.signal_generator = SignalGenerator()
            await self.signal_generator.initialize()
            
            logger.info("All components initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing components: {e}")
            raise

    async def initialize(self):
        """Initialize the trading bot components."""
        try:
            # Initialize components
            await self._initialize_components()
            
            # Set strategy config after signal generator is initialized
            if self.signal_generator:
                self.strategy_config = self.signal_generator.strategy_config
            
            logger.info("Trading bot initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing trading bot: {e}")
            raise

    async def start(self):
        """Start the trading bot."""
        try:
            logger.info("Starting trading bot...")
            self.running = True
            
            # Initialize components
            await self._initialize_components()
            
            # Start monitoring tasks
            self.health_check_task = asyncio.create_task(self._health_check_loop())
            self.funding_rate_task = asyncio.create_task(self._monitor_funding_rates())
            self.position_task = asyncio.create_task(self._monitor_positions())
            
            # Start WebSocket manager in background
            self.ws_manager.connect()
            
            logger.info("Trading bot started successfully")
            
        except Exception as e:
            logger.error(f"Error starting trading bot: {e}")
            await self.stop()
            raise

    async def stop(self):
        """Stop the trading bot and clean up resources."""
        try:
            logger.info("Stopping trading bot...")
            self.running = False
            
            # Cancel all tasks
            if self.health_check_task:
                self.health_check_task.cancel()
            if self.funding_rate_task:
                self.funding_rate_task.cancel()
            if self.position_task:
                self.position_task.cancel()
                
            # Stop WebSocket manager
            if self.exchange_client and self.exchange_client.ws_manager:
                await self.exchange_client.ws_manager.stop()
                
            # Close exchange client
            if self.exchange_client:
                await self.exchange_client.close()
                
            logger.info("Trading bot stopped successfully")
            
        except Exception as e:
            logger.error(f"Error stopping trading bot: {e}")
            raise
        
    def get_trade_history(self) -> List[Dict]:
        """Get the trade history."""
        return self.trade_history
        
    def get_active_trades(self) -> Dict[str, Dict]:
        """Get currently active trades."""
        return self.active_trades

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

    def get_profile_performance(self):
        """Get performance metrics for each trading profile."""
        try:
            # Get all trades from database
            with self._get_db_session() as session:
                trades = session.query(Trade).all()
                
            # Group trades by profile
            profile_trades = {}
            for trade in trades:
                if trade.profile not in profile_trades:
                    profile_trades[trade.profile] = []
                profile_trades[trade.profile].append(trade)
                
            # Calculate metrics for each profile
            profile_metrics = {}
            for profile, trades in profile_trades.items():
                total_trades = len(trades)
                winning_trades = sum(1 for t in trades if t.pnl > 0)
                total_pnl = sum(t.pnl for t in trades)
                avg_pnl = total_pnl / total_trades if total_trades > 0 else 0
                win_rate = winning_trades / total_trades if total_trades > 0 else 0
                
                profile_metrics[profile] = {
                    'total_trades': total_trades,
                    'winning_trades': winning_trades,
                    'total_pnl': total_pnl,
                    'avg_pnl': avg_pnl,
                    'win_rate': win_rate
                }
                
            return profile_metrics
            
        except Exception as e:
            logger.error(f"Error getting profile performance: {e}")
            return {}

    def get_parameter_history(self):
        """Get history of parameter adjustments."""
        return sorted(self.parameter_history, 
                     key=lambda x: x.get('timestamp', 0), 
                     reverse=True)[:100]  # Last 100 adjustments

    def get_volatility_impact(self):
        """Get impact of market volatility on each profile."""
        impact = {}
        for profile in self.strategy_config.get_profiles():
            current_volatility = self.market_data.get_current_volatility()
            impact_factor = self.strategy_config.get_volatility_impact_factor(profile)
            
            impact[profile] = {
                'current_volatility': current_volatility,
                'impact_factor': impact_factor,
                'parameter_adjustments': self.strategy_config.get_volatility_adjustments(profile)
            }
        return impact

    def record_parameter_adjustment(self, profile, trigger, changes):
        """Record a parameter adjustment in the history."""
        self.parameter_history.append({
            'timestamp': time.time(),
            'profile': profile,
            'trigger': trigger,
            'changes': changes
        })
        # Keep only last 1000 adjustments
        self.parameter_history = self.parameter_history[-1000:]

    async def _monitor_market_conditions(self):
        """Monitor market conditions and update strategy parameters."""
        while True:
            try:
                # Get current market conditions
                market_conditions = await self.symbol_discovery.get_market_conditions()
                
                # Update strategy parameters based on market conditions
                for symbol, conditions in market_conditions.items():
                    self.signal_generator.update_market_conditions(symbol, conditions)
                
                # Sleep for monitoring interval
                await asyncio.sleep(self.config['trading']['monitor_interval'])
                
            except Exception as e:
                logger.error(f"Error in market monitoring: {str(e)}")
                await asyncio.sleep(5)

    async def _process_signals(self):
        """Process trading signals and execute trades."""
        while True:
            try:
                # Get trading opportunities
                opportunities = await self.symbol_discovery.scan_opportunities()
                
                for opportunity in opportunities:
                    symbol = opportunity.symbol
                    
                    # Get market data
                    market_data = await self.symbol_discovery.get_market_data(symbol)
                    if not market_data:
                        continue
                    
                    # Calculate indicators
                    indicators = self.signal_generator.calculate_indicators(
                        market_data,
                        self.signal_generator.strategy_config.get_symbol_specific_params(
                            symbol,
                            opportunity.confidence
                        )
                    )
                    
                    # Generate signals
                    signal = self.signal_generator.generate_signals(
                        symbol,
                        indicators,
                        opportunity.confidence
                    )
                    
                    if signal and signal['signal_type'] != "NEUTRAL":
                        # Check risk limits
                        risk_limits = self.signal_generator.get_risk_limits()
                        if self.risk_manager.can_open_trade(symbol, risk_limits):
                            # Execute trade
                            trade_result = await self._execute_trade(symbol, signal)
                            if trade_result:
                                # Update strategy parameters
                                self.signal_generator.update_performance(trade_result)
                                
                                # Update volatility parameters
                                if 'volatility' in opportunity:
                                    self.signal_generator.update_volatility(
                                        symbol,
                                        opportunity.volatility
                                    )
                
                # Sleep for signal processing interval
                await asyncio.sleep(self.config['trading']['signal_interval'])
                
            except Exception as e:
                logger.error(f"Error in signal processing: {str(e)}")
                await asyncio.sleep(5)

    async def _update_positions(self):
        """Update all open positions."""
        try:
            logger.debug("Updating positions")
            
            # Get all open positions
            positions = await self.exchange_client.get_open_positions()
            
            # Update each position
            for position in positions:
                symbol = position.get('symbol')
                if symbol:
                    await self._update_position_levels(symbol)
                    
            # Check for positions that need to be closed
            for symbol in list(self.active_trades.keys()):
                position = await self.exchange_client.get_position(symbol)
                if not position or float(position.get('positionAmt', 0)) == 0:
                    await self._close_position(symbol, "position_closed")
                    
            logger.debug("Positions update completed")
            
        except Exception as e:
            logger.error(f"Error updating positions: {e}")

    async def _handle_health_check_failure(self):
        """Handle health check failures by attempting recovery."""
        try:
            logger.info("Attempting to recover from health check failure...")
            
            # Try to reconnect to exchange
            if not await self.exchange_client.check_connection():
                logger.info("Attempting to reconnect to exchange...")
                await self.exchange_client.reconnect()
            
            # Try to reconnect WebSocket
            if not self.exchange_client.ws_manager.is_connected():
                logger.info("Attempting to reconnect WebSocket...")
                await self.exchange_client.ws_manager.reconnect()
            
            # Verify recovery
            if await self._health_check():
                logger.info("Successfully recovered from health check failure")
            else:
                logger.error("Failed to recover from health check failure")
                
        except Exception as e:
            logger.error(f"Error during health check recovery: {e}")

    async def _health_check(self):
        """Perform a single health check of the trading system."""
        try:
            # Check exchange connection
            if not await self.exchange_client.check_connection():
                logger.error("Exchange connection check failed")
                return False
                
            # Check WebSocket connection
            if not self.exchange_client.ws_manager.is_connected():
                logger.error("WebSocket connection check failed")
                return False
                
            # Check account balance
            try:
                balance = await self._get_account_balance()
                if balance <= 0:
                    logger.error(f"Invalid account balance: {balance}")
                    return False
            except Exception as e:
                logger.error(f"Error checking account balance: {e}")
                return False
                
            # Check active trades
            for symbol, trade in self.active_trades.items():
                try:
                    position = await self.exchange_client.get_position(symbol)
                    if not position:
                        logger.error(f"Failed to get position for {symbol}")
                        return False
                        
                    # Check data freshness for the symbol
                    market_data = await self.exchange_client.get_market_data(symbol)
                    if not market_data:
                        logger.error(f"Failed to get market data for {symbol}")
                        return False
                        
                    if not self.symbol_discovery.check_data_freshness(market_data):
                        logger.error(f"Data freshness check failed for {symbol}")
                        return False
                        
                except Exception as e:
                    logger.error(f"Error checking position for {symbol}: {e}")
                    return False
                    
            logger.info("Health check passed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error during health check: {e}")
            return False

    async def _health_check_loop(self):
        """Run periodic health checks."""
        while self.running:
            try:
                if not await self._health_check():
                    logger.error("Health check failed, attempting recovery...")
                    await self._handle_health_check_failure()
                    
                await asyncio.sleep(self.health_check_interval)
                
            except asyncio.CancelledError:
                logger.info("Health check loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
                await asyncio.sleep(self.health_check_interval)

    async def _update_funding_rates(self):
        """Update funding rates for the trading system."""
        while self.running:
            try:
                # Implementation of funding rate update logic
                await asyncio.sleep(self.config['trading']['funding_rate_interval'])
            except Exception as e:
                logger.error(f"Error in funding rate update: {str(e)}")
            await asyncio.sleep(self.config['trading']['funding_rate_interval'])

    async def _close_position(self, symbol: str, reason: str = "manual_close") -> bool:
        """Close a position for a symbol with optional reason."""
        try:
            logger.info(f"Closing position for {symbol} - Reason: {reason}")
            
            # Get current position
            position = await self.exchange_client.get_position(symbol)
            if not position or float(position.get('positionAmt', 0)) == 0:
                logger.info(f"No position to close for {symbol}")
                return True
                
            # Close position
            result = await self.exchange_client.close_position(symbol)
            
            if result and result.get('status') != 'no_position':
                logger.info(f"Successfully closed position for {symbol}")
                return True
            else:
                logger.warning(f"Failed to close position for {symbol}")
                return False
                
        except Exception as e:
            logger.error(f"Error closing position for {symbol}: {e}")
            return False

    async def _update_position_levels(self, symbol: str) -> None:
        """Update position levels and risk metrics for a symbol."""
        try:
            # Get current position
            position = await self.exchange_client.get_position(symbol)
            if not position:
                return
                
            position_amt = float(position.get('positionAmt', 0))
            if position_amt == 0:
                return
                
            # Get current market price
            ticker = await self.exchange_client.get_ticker(symbol)
            if not ticker:
                return
                
            current_price = float(ticker.get('last', 0))
            if current_price == 0:
                return
                
            # Calculate position metrics
            entry_price = float(position.get('entryPrice', 0))
            unrealized_pnl = float(position.get('unRealizedProfit', 0))
            leverage = float(position.get('leverage', 0))
            
            # Calculate price levels
            price_change = ((current_price - entry_price) / entry_price) * 100
            pnl_percentage = (unrealized_pnl / (abs(position_amt) * entry_price)) * 100
            
            # Update position levels in state
            self.position_levels[symbol] = {
                'entry_price': entry_price,
                'current_price': current_price,
                'position_amt': position_amt,
                'unrealized_pnl': unrealized_pnl,
                'price_change_pct': price_change,
                'pnl_percentage': pnl_percentage,
                'leverage': leverage,
                'last_update': datetime.now().timestamp()
            }
            
            # Log position update
            logger.info(
                f"Position levels updated for {symbol}: "
                f"Entry: {entry_price:.2f}, Current: {current_price:.2f}, "
                f"Change: {price_change:.2f}%, PnL: {pnl_percentage:.2f}%"
            )
            
        except Exception as e:
            logger.error(f"Error updating position levels for {symbol}: {e}")

    async def _monitor_funding_rates(self):
        """Monitor funding rates for active positions."""
        while self.running:
            try:
                for symbol in self.active_trades:
                    funding_rate = await self.exchange_client.get_funding_rate(symbol)
                    if funding_rate is not None:
                        logger.info(f"Funding rate for {symbol}: {funding_rate}")
                        # Add funding rate monitoring logic here
                await asyncio.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Error monitoring funding rates: {e}")
                await asyncio.sleep(5)

    async def _monitor_positions(self):
        """Monitor active positions and update their status."""
        while self.running:
            try:
                for symbol in self.active_trades:
                    await self._update_position_levels(symbol)
                await asyncio.sleep(10)  # Update every 10 seconds
            except Exception as e:
                logger.error(f"Error monitoring positions: {e}")
                await asyncio.sleep(5)

    def load_strategy_profiles(self):
        """Load strategy profiles from JSON file."""
        try:
            profiles_path = os.path.join('config', 'strategy_profiles.json')
            if os.path.exists(profiles_path):
                with open(profiles_path, 'r') as f:
                    loaded_profiles = json.load(f)
                    if loaded_profiles:
                        self.profiles = loaded_profiles
                        logger.info("Loaded strategy profiles from file")
                        return
            logger.warning("No strategy profiles found, using defaults")
            self.profiles = self._get_default_profiles()
        except Exception as e:
            logger.error(f"Error loading strategy profiles: {e}")
            self.profiles = self._get_default_profiles()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            config_path = os.path.join('config', 'config.yaml')
            if not os.path.exists(config_path):
                logger.warning(f"Config file not found at {config_path}, using defaults")
                return self._get_default_config()
                
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                if not config:
                    logger.warning("Empty config file, using defaults")
                    return self._get_default_config()
                    
                # Validate configuration
                if not validate_config(config):
                    logger.error("Configuration validation failed, using defaults")
                    return self._get_default_config()
                    
                return config
                
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return self._get_default_config()
            
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            'exchange': {
                'name': 'binance',
                'testnet': os.getenv('USE_TESTNET', 'false').lower() == 'true',
                'api_key': os.getenv('BINANCE_API_KEY', ''),
                'api_secret': os.getenv('BINANCE_API_SECRET', ''),
                'base_url': os.getenv('BINANCE_API_URL', 'https://api.binance.com'),
                'ws_url': os.getenv('BINANCE_WS_URL', 'wss://stream.binance.com:9443/ws/stream')
            },
            'trading': {
                'risk_per_trade': float(os.getenv('RISK_PER_TRADE', '50.0')),
                'max_open_trades': int(os.getenv('MAX_OPEN_TRADES', '5')),
                'min_volume': float(os.getenv('MIN_VOLUME', '1000000.0')),
                'min_market_cap': float(os.getenv('MIN_MARKET_CAP', '100000000.0')),
                'max_spread': float(os.getenv('MAX_SPREAD', '0.5')),
                'min_volatility': float(os.getenv('MIN_VOLATILITY', '0.5')),
                'max_volatility': float(os.getenv('MAX_VOLATILITY', '5.0'))
            },
            'risk': {
                'max_drawdown': float(os.getenv('MAX_DRAWDOWN', '10.0')),
                'max_leverage': float(os.getenv('MAX_LEVERAGE', '3.0')),
                'position_size_limit': float(os.getenv('POSITION_SIZE_LIMIT', '10000.0')),
                'daily_loss_limit': float(os.getenv('DAILY_LOSS_LIMIT', '1000.0'))
            },
            'monitoring': {
                'health_check_interval': int(os.getenv('HEALTH_CHECK_INTERVAL', '60')),
                'position_update_interval': int(os.getenv('POSITION_UPDATE_INTERVAL', '10')),
                'funding_rate_check_interval': int(os.getenv('FUNDING_RATE_CHECK_INTERVAL', '60'))
            }
        }

    async def _execute_trade(self, symbol: str, signal: Dict[str, Any]) -> bool:
        """Execute a trade based on the signal."""
        try:
            # Validate signal
            if not self._validate_signal(signal):
                logger.error(f"Invalid signal for {symbol}")
                return False
                
            # Check risk limits
            if not self.risk_manager.check_risk_limits(symbol, signal):
                logger.warning(f"Risk limits exceeded for {symbol}")
                return False
                
            # Get current position
            position = await self.exchange_client.get_position(symbol)
            if position and float(position.get('positionAmt', 0)) != 0:
                logger.warning(f"Position already exists for {symbol}")
                return False
                
            # Calculate position size
            balance = await self._get_account_balance()
            position_size = self.risk_manager.calculate_position_size(
                symbol=symbol,
                balance=balance,
                risk_per_trade=self.config['trading']['risk_per_trade']
            )
            
            # Execute order
            order = await self.exchange_client.create_order(
                symbol=symbol,
                order_type='MARKET',
                side=signal['side'],
                amount=position_size
            )
            
            if order:
                logger.info(f"Trade executed for {symbol}: {order}")
                return True
            else:
                logger.error(f"Failed to execute trade for {symbol}")
                return False
                
        except Exception as e:
            logger.error(f"Error executing trade for {symbol}: {e}")
            return False
            
    def _validate_signal(self, signal: Dict[str, Any]) -> bool:
        """Validate a trading signal."""
        try:
            required_fields = ['symbol', 'side', 'price', 'timestamp']
            if not all(field in signal for field in required_fields):
                return False
                
            if signal['side'] not in ['BUY', 'SELL']:
                return False
                
            if not isinstance(signal['price'], (int, float)) or signal['price'] <= 0:
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error validating signal: {e}")
            return False

    def _get_default_profiles(self) -> Dict[str, Any]:
        """Get default strategy profiles."""
        return {
            'default': {
                'name': 'default',
                'description': 'Default trading strategy',
                'parameters': {
                    'entry_threshold': 0.02,
                    'exit_threshold': 0.01,
                    'stop_loss': 0.03,
                    'take_profit': 0.05,
                    'max_position_size': 0.1,
                    'leverage': 1.0,
                    'min_volume': 1000000.0,
                    'min_market_cap': 100000000.0,
                    'max_spread': 0.5,
                    'min_volatility': 0.5,
                    'max_volatility': 5.0
                }
            },
            'scalping': {
                'name': 'scalping',
                'description': 'Scalping strategy for high-frequency trading',
                'parameters': {
                    'entry_threshold': 0.005,
                    'exit_threshold': 0.003,
                    'stop_loss': 0.01,
                    'take_profit': 0.015,
                    'max_position_size': 0.05,
                    'leverage': 2.0,
                    'min_volume': 5000000.0,
                    'min_market_cap': 500000000.0,
                    'max_spread': 0.2,
                    'min_volatility': 0.3,
                    'max_volatility': 2.0
                }
            },
            'swing': {
                'name': 'swing',
                'description': 'Swing trading strategy for medium-term positions',
                'parameters': {
                    'entry_threshold': 0.05,
                    'exit_threshold': 0.03,
                    'stop_loss': 0.08,
                    'take_profit': 0.15,
                    'max_position_size': 0.2,
                    'leverage': 1.0,
                    'min_volume': 2000000.0,
                    'min_market_cap': 200000000.0,
                    'max_spread': 1.0,
                    'min_volatility': 1.0,
                    'max_volatility': 10.0
                }
            }
        }

# Create the global instance
trading_bot = TradingBot()





if __name__ == "__main__":
    import asyncio
    import signal

    bot = TradingBot()

    async def main():
        await bot.start()
        try:
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            pass

    def handle_shutdown(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        for task in asyncio.all_tasks():
            task.cancel()

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
    except Exception as e:
        logger.error(f"Error running bot: {e}")
        raise

