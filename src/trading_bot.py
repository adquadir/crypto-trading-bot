# File: src/trading_bot.py
from typing import Dict, List, Optional
import asyncio
import logging
from datetime import datetime
import os
from dotenv import load_dotenv
import numpy as np
import json
from pathlib import Path
import time

from src.market_data.exchange_client import ExchangeClient
from src.market_data.processor import MarketDataProcessor
from src.signals.engine import SignalEngine
from src.risk.manager import RiskManager
from src.database.models import Base, MarketData, OrderBook, TradingSignal, Trade, PerformanceMetrics
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from src.market_data.symbol_discovery import SymbolDiscovery, TradingOpportunity
from src.signals.signal_generator import SignalGenerator
from src.utils.config import load_config
from src.market_data.websocket_client import MarketDataWebSocket

logger = logging.getLogger(__name__)

class TradingBot:
    def __init__(self, config_path: str = "config/config.yaml", market_data=None):
        # Load environment variables
        load_dotenv()
        
        # Load configuration from YAML
        # Binance API keys and testnet are loaded directly from environment variables
        # to prioritize the recommended .env configuration method.
        self.config = load_config(config_path)
        
        # Initialize components
        self.exchange_client = ExchangeClient(
            api_key=os.getenv('BINANCE_API_KEY'),
            api_secret=os.getenv('BINANCE_API_SECRET'),
            testnet=os.getenv('USE_TESTNET', 'False').lower() == 'true', # Use USE_TESTNET from .env
            scalping_mode=True
        )
        self.market_processor = MarketDataProcessor()
        self.signal_engine = SignalEngine()
        self.symbol_discovery = SymbolDiscovery(self.exchange_client)
        self.signal_generator = SignalGenerator()
        self.risk_manager = RiskManager(
            account_balance=self.config['risk']['initial_balance'],
        )
        
        # Ensure market_data is always set
        self.market_data = market_data if market_data is not None else self.symbol_discovery
        
        # Initialize database
        self._init_database()
        
        # Trading state
        self.is_running = False
        self.debug_mode = True  # Set to False in production
        self.risk_per_trade = float(os.getenv('RISK_PER_TRADE', '50.0'))
        self.max_open_trades = int(os.getenv('MAX_OPEN_TRADES', '5'))
        
        # Balance tracking
        self._last_balance_update = 0
        self._balance_cache = None
        self._balance_cache_ttl = 300  # 5 minutes cache TTL
        
        # Start opportunity scanning in background
        self.opportunity_scan_task = None
        
        # Risk manager will be initialized in start() after getting account balance
        self.active_trades = {}
        self.trade_history = []
        self._shutdown_event = asyncio.Event()
        
        # New attributes for profile performance tracking
        self.strategy_config = self.signal_generator.strategy_config
        self.parameter_history = []
        
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
            # Get account info
            account_info = await asyncio.to_thread(self.exchange_client.client.get_account)
            
            if not account_info or 'balances' not in account_info:
                raise ValueError("Invalid account info response")
                
            # Calculate total balance
            total_balance = 0
            asset_balances = {}
            
            for balance in account_info['balances']:
                try:
                    free = float(balance.get('free', 0))
                    locked = float(balance.get('locked', 0))
                    total = free + locked
                    
                    if total > 0:
                        asset = balance.get('asset', 'UNKNOWN')
                        asset_balances[asset] = total
                        total_balance += total
                        
                except (ValueError, TypeError) as e:
                    logger.warning(f"Error processing balance for asset {balance.get('asset', 'UNKNOWN')}: {e}")
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

    async def start(self):
        """Start the trading bot."""
        try:
            logger.info("Starting trading bot...")
            
            # Initialize strategy profiles
            self.strategy_config.load_strategy_profiles()
            self.strategy_config.switch_profile('moderate')  # Default to moderate profile
            
            # Initialize exchange client first
            await self.exchange_client.initialize([])  # Initialize with empty symbols list first
            
            # Initialize symbol discovery with exchange client and scalping mode
            self.symbol_discovery = SymbolDiscovery(self.exchange_client, scalping_mode=True)
            await self.symbol_discovery.initialize()
            
            # Get symbols and update exchange client
            symbols = await self.symbol_discovery.get_symbols()
            await self.exchange_client.initialize(symbols)
            
            # Initialize WebSocket manager
            self.ws_manager = MarketDataWebSocket(
                exchange_client=self.exchange_client,
                symbols=symbols
            )
            await self.ws_manager.start()
            
            # Start background tasks
            self.tasks = [
                asyncio.create_task(self._monitor_market_conditions()),
                asyncio.create_task(self._process_signals()),
                asyncio.create_task(self._update_positions()),
                asyncio.create_task(self._health_check())
            ]
            
            logger.info("Trading bot started successfully")
                    
        except Exception as e:
            logger.error(f"Error starting trading bot: {str(e)}")
            await self.stop()
            raise
            
    async def _execute_trade(self, symbol: str, signal: Dict) -> Optional[Dict]:
        """Execute a trade based on the signal."""
        try:
            # Get current position
            position = await self.exchange_client.get_position(symbol)
            
            # Determine trade direction and size
            signal_type = signal['signal_type']
            current_price = signal['indicators']['current_price']

            if signal_type == "SAFE_BUY":
                entry_price = signal['entry']
                take_profit = signal['take_profit']
                stop_loss = signal['stop_loss']
                direction = "LONG"
                # Calculate size based on risk_per_trade and stop loss distance
                # Assuming risk_per_trade is in percentage of account balance for simplicity here,
                # needs to be adjusted based on how risk_per_trade is defined (e.g., fixed amount or percent)
                # Let's use risk_per_trade from dynamic config, which is a percentage.
                risk_percentage = self.signal_generator.get_risk_limits().get('risk_per_trade', 0.015)
                account_balance = await self._get_account_balance()
                risk_amount_usd = account_balance * risk_percentage

                price_distance_to_stop = entry_price - stop_loss # For LONG
                if price_distance_to_stop <= 0:
                    logger.warning(f"Invalid stop loss distance for {symbol} SAFE_BUY signal: {price_distance_to_stop}")
                    return None # Cannot calculate size with invalid SL

                # Calculate size based on risk amount and stop loss distance
                # size = risk_amount_usd / price_distance_to_stop # This is a simplified calculation and might need adjustment
                # For a safer approach, let's use a fixed small size for now in debug mode
                trade_size = 0.001 # Example small size

                # Check if current price is near entry for market order (simplified)
                price_tolerance = entry_price * 0.001 # e.g., 0.1% tolerance
                if abs(current_price - entry_price) <= price_tolerance:
                    order_type = 'MARKET'
                    order_price = None # Market order doesn't need price
                    logger.info(f"Executing {direction} MARKET order for {symbol} with size {trade_size}")
                    # Simulate market order execution
                    # In a real scenario, you'd call exchange_client.create_order here
                    executed_price = current_price # Assume filled at current price for simulation
                    order_id = f"simulated_market_{symbol}_{datetime.now().timestamp()}"
                    executed_qty = trade_size
                    status = "FILLED"

                    # Log and record trade
                    trade_result = {
                        "symbol": symbol,
                        "order_id": order_id,
                        "direction": direction,
                        "entry_price": executed_price,
                        "executed_qty": executed_qty,
                        "timestamp": datetime.now().isoformat(),
                        "status": status,
                        "signal_type": signal_type,
                        "take_profit": take_profit,
                        "stop_loss": stop_loss,
                        "initial_risk_usd": risk_amount_usd # Store initial risk
                    }
                    self.trade_history.append(trade_result)
                    logger.info(f"Trade executed: {trade_result}")
                    return trade_result
                else:
                    logger.info(f"Current price {current_price:.2f} not near entry {entry_price:.2f} for {symbol} SAFE_BUY. Skipping market order.")
                    return None

            elif signal_type == "SAFE_SELL":
                entry_price = signal['entry']
                take_profit = signal['take_profit']
                stop_loss = signal['stop_loss']
                direction = "SHORT"
                # Calculate size based on risk_per_trade and stop loss distance
                risk_percentage = self.signal_generator.get_risk_limits().get('risk_per_trade', 0.015)
                account_balance = await self._get_account_balance()
                risk_amount_usd = account_balance * risk_percentage

                price_distance_to_stop = stop_loss - entry_price # For SHORT
                if price_distance_to_stop <= 0:
                    logger.warning(f"Invalid stop loss distance for {symbol} SAFE_SELL signal: {price_distance_to_stop}")
                    return None # Cannot calculate size with invalid SL

                # Calculate size based on risk amount and stop loss distance
                # size = risk_amount_usd / price_distance_to_stop # Simplified calculation
                # For a safer approach, let's use a fixed small size for now in debug mode
                trade_size = 0.001 # Example small size

                # Check if current price is near entry for market order (simplified)
                price_tolerance = entry_price * 0.001 # e.g., 0.1% tolerance
                if abs(current_price - entry_price) <= price_tolerance:
                    order_type = 'MARKET'
                    order_price = None # Market order doesn't need price
                    logger.info(f"Executing {direction} MARKET order for {symbol} with size {trade_size}")
                    # Simulate market order execution
                    # In a real scenario, you'd call exchange_client.create_order here
                    executed_price = current_price # Assume filled at current price for simulation
                    order_id = f"simulated_market_{symbol}_{datetime.now().timestamp()}"
                    executed_qty = trade_size
                    status = "FILLED"

                    # Log and record trade
                    trade_result = {
                        "symbol": symbol,
                        "order_id": order_id,
                        "direction": direction,
                        "entry_price": executed_price,
                        "executed_qty": executed_qty,
                        "timestamp": datetime.now().isoformat(),
                        "status": status,
                        "signal_type": signal_type,
                        "take_profit": take_profit,
                        "stop_loss": stop_loss,
                        "initial_risk_usd": risk_amount_usd # Store initial risk
                    }
                    self.trade_history.append(trade_result)
                    logger.info(f"Trade executed: {trade_result}")
                    return trade_result
                else:
                    logger.info(f"Current price {current_price:.2f} not near entry {entry_price:.2f} for {symbol} SAFE_SELL. Skipping market order.")
                    return None

            elif signal_type in ["STRONG_BUY", "BUY", "STRONG_SELL", "SELL"]:
                # Existing logic for standard signals
                direction = "LONG" if signal_type in ["STRONG_BUY", "BUY"] else "SHORT"
                # Recalculate size and levels based on standard risk management if not a SAFE signal
                # This might be redundant if signal_generator always provides levels, 
                # but kept for clarity on handling different signal types.
                # For standard signals, calculate levels using risk manager or signal_generator if it provides them
                # Assuming for now that standard signals rely on risk_manager for size/levels calculation approach
                size = self.risk_manager.calculate_position_size(
                     symbol,
                     current_price, # Pass current price or entry if signal provides it
                     direction,
                     signal.get('indicators', {}), # Pass indicators/market state
                     signal.get('confidence_score', 1.0)
                )

                if size == 0:
                    logger.warning(f"Risk manager prevented opening standard trade for {symbol}.")
                    return None

                # For standard signals, TP/SL would typically be calculated here or by signal_generator
                # Assuming signal_generator provides these now in its standard output too
                entry_price = current_price # Or signal['entry'] if available
                take_profit = signal.get('take_profit') # Get from signal if available
                stop_loss = signal.get('stop_loss') # Get from signal if available

                if take_profit is None or stop_loss is None:
                     # Fallback or calculate based on risk_manager if signal didn't provide them
                     stop_loss = self.risk_manager.calculate_stop_loss(symbol, entry_price, direction, signal.get('indicators', {}))
                     # Calculate take profit based on a default risk:reward or from signal
                     take_profit = self.risk_manager.calculate_take_profit(symbol, entry_price, stop_loss, direction, signal.get('indicators', {})) # Assuming calculate_take_profit exists and uses risk:reward

                logger.info(f"Executing Standard {signal_type} for {symbol}: Entry={entry_price:.2f}, TP={take_profit:.2f}, SL={stop_loss:.2f}, Size={size:.4f}")

                if position and position['side'] == "SHORT":
                    await self.exchange_client.close_position(symbol)

                # Place order (simplified - market execution assumed if price is close to entry)
                # In a real bot, use limit orders and manage TP/SL
                if abs(current_price - entry_price) / entry_price < 0.001: # If within 0.1% of entry
                    order_side = 'BUY' if direction == 'LONG' else 'SELL'
                    order = await self.exchange_client.place_order(symbol, order_side, 'MARKET', size)
                    logger.info(f"Placed market {order_side} order for {symbol}. Order ID: {order.get('orderId')}")
                else:
                     logger.warning(f"Current price {current_price:.2f} too far from Standard {signal_type} entry {entry_price:.2f} for {symbol}. Skipping trade.")
                     return None # Skip trade if price moved significantly

            else:
                logger.info(f"Received NEUTRAL signal for {symbol}. No trade executed.")
                return None

            # Record trade - update this to use actual fill price and other order details
            # This is a simplified recording and needs to be enhanced with real order management
            trade = {
                'symbol': symbol,
                'direction': direction,
                'size': size,
                'entry_price': order.get('fills', [{}])[0].get('price', entry_price) if order else entry_price, # Attempt to get fill price, fallback to calculated entry
                'timestamp': datetime.now().isoformat(),
                'signal': signal,
                'take_profit': take_profit, # Record calculated TP/SL
                'stop_loss': stop_loss
            }

            # Add the trade to active_trades (needs unique ID)
            # Using symbol as key assumes only one position per symbol at a time
            # For multiple positions per symbol, active_trades structure needs to change
            trade_id = f"{symbol}_{int(time.time())}" # Simple unique ID
            self.active_trades[trade_id] = trade

            # Add to history (can store less detail here)
            self.trade_history.append({**trade, 'status': 'OPEN'}) # Record status

            logger.info(f"Recorded trade for {symbol}: ID={trade_id}")
            # In a real bot, you would now monitor the active_trade for TP/SL execution or manual closing

            return trade

        except Exception as e:
            logger.error(f"Error executing trade for {symbol} with signal {signal_type}: {e}")
            return None
            
    async def stop(self):
        """Stop the trading bot."""
        logger.info("Stopping trading bot...")

        # Cancel all background tasks
        if hasattr(self, 'tasks'):
            for task in self.tasks:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Close exchange client
        if hasattr(self, 'exchange_client'):
            await self.exchange_client.close()

        # Stop the WebSocket manager
        if hasattr(self, 'ws_manager'):
            await self.ws_manager.stop()

        logger.info("Trading bot stopped")
        
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
        """Get performance metrics for each strategy profile."""
        performance = {}
        for profile in self.strategy_config.get_profiles():
            trades = [t for t in self.trade_history if t.get('profile') == profile]
            if not trades:
                continue

            wins = len([t for t in trades if t.get('pnl', 0) > 0])
            total_trades = len(trades)
            win_rate = wins / total_trades if total_trades > 0 else 0

            total_profit = sum(t.get('pnl', 0) for t in trades if t.get('pnl', 0) > 0)
            total_loss = abs(sum(t.get('pnl', 0) for t in trades if t.get('pnl', 0) < 0))
            profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')

            avg_duration = sum((t.get('exit_time', 0) - t.get('entry_time', 0)) 
                             for t in trades) / total_trades if total_trades > 0 else 0

            performance[profile] = {
                'win_rate': win_rate,
                'profit_factor': profit_factor,
                'total_trades': total_trades,
                'avg_duration': f"{avg_duration/3600:.1f}h",
                'parameter_adjustments': len([h for h in self.parameter_history 
                                           if h.get('profile') == profile and 
                                           h.get('timestamp', 0) > time.time() - 86400])
            }
        return performance

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
        """Update and manage open positions."""
        while True:
            try:
                # Get open positions
                positions = await self.exchange_client.get_open_positions()
                
                for position in positions:
                    symbol = position['symbol']
                    
                    # Get current market data
                    market_data = await self.symbol_discovery.get_market_data(symbol)
                    if not market_data:
                        continue
                    
                    # Check if position should be closed
                    if self.signal_generator.should_close_position(position, market_data):
                        await self._close_position(position)
                    
                    # Update stop loss and take profit
                    elif self.signal_generator.should_update_levels(position, market_data):
                        new_levels = self.signal_generator.calculate_new_levels(position, market_data)
                        await self._update_position_levels(position, new_levels)
                
                # Sleep for position update interval
                await asyncio.sleep(self.config['trading']['position_interval'])
                
            except Exception as e:
                logger.error(f"Error in position updates: {str(e)}")
                await asyncio.sleep(5)

    async def _health_check(self):
        """Perform health checks on the trading system."""
        while True:
            try:
                # Check exchange connection
                if not await self.exchange_client.check_connection():
                    logger.error("Exchange connection lost, attempting to reconnect...")
                    await self.exchange_client.reconnect()
                
                # Check WebSocket connection
                if not await self.ws_manager.check_connection():
                    logger.error("WebSocket connection lost, attempting to reconnect...")
                    await self.ws_manager.reconnect()
                
                # Check data freshness
                stale_data = await self.symbol_discovery.check_data_freshness()
                if stale_data:
                    logger.warning(f"Stale data detected for symbols: {stale_data}")
                
                # Sleep for health check interval
                await asyncio.sleep(self.config['trading']['health_check_interval'])
                
            except Exception as e:
                logger.error(f"Error in health check: {str(e)}")
                await asyncio.sleep(5)