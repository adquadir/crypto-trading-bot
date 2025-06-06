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

logger = logging.getLogger(__name__)

class TradingBot:
    def __init__(self, config_path: str = "config/config.yaml"):
        # Load environment variables
        load_dotenv()
        
        # Initialize components
        self.config = load_config(config_path)
        self.exchange_client = ExchangeClient(
            api_key=self.config['binance']['api_key'],
            api_secret=self.config['binance']['api_secret'],
            testnet=self.config['binance']['testnet']
        )
        self.market_processor = MarketDataProcessor()
        self.signal_engine = SignalEngine()
        self.symbol_discovery = SymbolDiscovery(self.exchange_client)
        self.signal_generator = SignalGenerator()
        self.risk_manager = RiskManager(
            account_balance=self.config['risk']['initial_balance'],
            max_daily_loss=self.config['risk']['max_daily_loss'],
            max_drawdown=self.config['risk']['max_drawdown']
        )
        
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
            
            # Initialize exchange client
            await self.exchange_client.initialize()
            
            # Set initial strategy profile
            self.signal_generator.set_strategy_profile(self.config['strategy']['default_profile'])
            
            # Start main trading loop
            while not self._shutdown_event.is_set():
                try:
                    # Discover trading opportunities
                    opportunities = await self.symbol_discovery.scan_opportunities()
                    
                    for symbol, opportunity in opportunities.items():
                        # Get market data
                        market_data = await self.exchange_client.get_market_data(symbol)
                        if not market_data:
                            continue
                            
                        # Calculate indicators with dynamic parameters
                        indicators = self.signal_generator.calculate_indicators(
                            market_data,
                            self.signal_generator.strategy_config.get_symbol_specific_params(
                                symbol,
                                opportunity['confidence_score']
                            )
                        )
                        
                        # Generate signals
                        signal = self.signal_generator.generate_signals(
                            symbol,
                            indicators,
                            opportunity['confidence_score']
                        )
                        
                        if signal and signal['signal_type'] != "NEUTRAL":
                            # Check risk limits
                            risk_limits = self.signal_generator.get_risk_limits()
                            if self.risk_manager.can_open_trade(symbol, risk_limits):
                                # Execute trade
                                trade_result = await self._execute_trade(symbol, signal)
                                if trade_result:
                                    # Update strategy parameters based on trade result
                                    self.signal_generator.update_performance(trade_result)
                                    
                                    # Update volatility parameters
                                    if 'volatility' in opportunity:
                                        self.signal_generator.update_volatility(
                                            symbol,
                                            opportunity['volatility']
                                        )
                                        
                    # Sleep to prevent excessive API calls
                    await asyncio.sleep(self.config['trading']['scan_interval'])
                    
                except Exception as e:
                    logger.error(f"Error in trading loop: {e}")
                    await asyncio.sleep(5)  # Wait before retrying
                    
        except Exception as e:
            logger.error(f"Fatal error in trading bot: {e}")
            raise
        finally:
            await self.stop()
            
    async def _execute_trade(self, symbol: str, signal: Dict) -> Optional[Dict]:
        """Execute a trade based on the signal."""
        try:
            # Get current position
            position = await self.exchange_client.get_position(symbol)
            
            # Determine trade direction and size
            direction = "LONG" if signal['signal_type'] in ["STRONG_BUY", "BUY"] else "SHORT"
            size = self.risk_manager.calculate_position_size(
                symbol,
                signal['confidence_score'],
                self.signal_generator.get_risk_limits()
            )
            
            # Execute trade
            if direction == "LONG":
                if position and position['side'] == "SHORT":
                    await self.exchange_client.close_position(symbol)
                await self.exchange_client.open_long_position(symbol, size)
            else:
                if position and position['side'] == "LONG":
                    await self.exchange_client.close_position(symbol)
                await self.exchange_client.open_short_position(symbol, size)
                
            # Record trade
            trade = {
                'symbol': symbol,
                'direction': direction,
                'size': size,
                'entry_price': signal['indicators']['current_price'],
                'timestamp': datetime.now().isoformat(),
                'signal': signal
            }
            
            self.active_trades[symbol] = trade
            self.trade_history.append(trade)
            
            logger.info(f"Executed {direction} trade for {symbol}")
            return trade
            
        except Exception as e:
            logger.error(f"Error executing trade for {symbol}: {e}")
            return None
            
    async def stop(self):
        """Stop the trading bot."""
        logger.info("Stopping trading bot...")
        self._shutdown_event.set()
        await self.exchange_client.close()
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