"""
Real Trading Engine
For actual money trading with real exchange connections
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import uuid
from dataclasses import dataclass, asdict

from ..market_data.exchange_client import ExchangeClient
from ..database.database import Database
from ..utils.logger import setup_logger
from ..utils.time_utils import format_duration
from .trade_sync_service import TradeSyncService

logger = setup_logger(__name__)

@dataclass
class RealPosition:
    """Represents a real trading position"""
    position_id: str
    symbol: str
    side: str  # 'LONG' or 'SHORT'
    entry_price: float
    position_size: float
    leverage: float
    stop_loss: Optional[float]
    take_profit: Optional[float]
    entry_time: datetime
    strategy: str
    confidence: float
    status: str = 'OPEN'  # 'OPEN', 'CLOSED', 'CANCELLED'
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    pnl: float = 0.0
    pnl_pct: float = 0.0
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        # Convert datetime objects to ISO strings
        if self.entry_time:
            data['entry_time'] = self.entry_time.isoformat()
        if self.exit_time:
            data['exit_time'] = self.exit_time.isoformat()
        return data

class RealTradingEngine:
    """Real trading engine for actual money trading"""
    
    def __init__(self, exchange_client: Optional[ExchangeClient] = None):
        self.exchange_client = exchange_client or ExchangeClient()
        self.db_manager = Database()
        
        # Real trading state
        self.is_running = False
        self.active_positions: Dict[str, RealPosition] = {}
        self.total_pnl = 0.0
        self.total_trades = 0
        self.winning_trades = 0
        self.start_time = None
        
        # Real trading configuration - CONSERVATIVE FOR REAL MONEY
        self.max_daily_loss = 500.0  # Conservative $500 daily loss limit for real money
        self.position_size_usd = 200.0  # Fixed $200 per position (same as paper)
        self.leverage = 10.0  # Fixed 10x leverage (same as paper)
        self.max_total_exposure = 1.0  # 100% exposure like paper trading
        
        # Minimal safety controls (only essential ones)
        self.emergency_stop = False
        self.daily_pnl = 0.0
        self.last_reset_date = datetime.now().date()
        
        # Manual trade learning
        self.trade_sync_service = TradeSyncService(self.exchange_client)
        self.last_sync_time = datetime.now()
        
        logger.info("🚀 Real Trading Engine initialized with Trade Sync Service")
    
    async def start_trading(self, symbols: List[str]) -> bool:
        """Start real trading for specified symbols"""
        try:
            if self.is_running:
                logger.warning("Real trading is already running")
                return False
            
            # Safety check - ensure we have real exchange connection
            if not self.exchange_client or not hasattr(self.exchange_client, 'ccxt_client'):
                logger.error("❌ SAFETY: No real exchange connection available")
                logger.error("❌ SAFETY: Real trading requires valid API keys and exchange connection")
                return False
            
            # Test exchange connection
            try:
                balance = await self.exchange_client.get_account_balance()
                if not balance or balance.get('total', 0) < 100:
                    logger.error("❌ SAFETY: Insufficient account balance for real trading")
                    return False
            except Exception as e:
                logger.error(f"❌ SAFETY: Cannot connect to exchange: {e}")
                return False
            
            self.is_running = True
            self.start_time = datetime.now()
            
            # Start trade sync service for manual trade learning
            if self.trade_sync_service:
                await self.trade_sync_service.start_sync()
                logger.info("🔄 Trade synchronization service started")
            
            logger.info(f"🚀 Real Trading started for {symbols}")
            logger.warning("⚠️  REAL MONEY TRADING IS NOW ACTIVE")
            logger.warning("⚠️  ALL TRADES WILL USE ACTUAL FUNDS")
            
            return True
            
        except Exception as e:
            logger.error(f"Error starting real trading: {e}")
            return False
    
    async def stop_trading(self) -> bool:
        """Stop real trading and close all positions"""
        try:
            if not self.is_running:
                return True
            
            logger.info("🛑 Stopping real trading...")
            
            # Close all open positions
            for position_id in list(self.active_positions.keys()):
                await self.close_position(position_id, "SYSTEM_STOP")
            
            self.is_running = False
            
            logger.info("✅ Real trading stopped")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping real trading: {e}")
            return False
    
    async def execute_trade(self, signal: Dict[str, Any]) -> Optional[str]:
        """Execute a real trade based on signal"""
        try:
            if not self.is_running:
                logger.warning("Real trading is not running")
                return None
            
            if self.emergency_stop:
                logger.warning("Emergency stop is active - no new trades")
                return None
            
            # Safety checks
            if not await self._safety_checks(signal):
                return None
            
            symbol = signal['symbol']
            side = signal['side']
            confidence = signal.get('confidence', 0.5)
            
            # Get current price
            current_price = await self.exchange_client.get_current_price(symbol)
            if not current_price:
                logger.error(f"Cannot get current price for {symbol}")
                return None
            
            # Calculate position size based on risk management
            position_size = self._calculate_position_size(symbol, current_price, confidence)
            if position_size <= 0:
                logger.warning(f"Position size too small for {symbol}")
                return None
            
            # Execute real trade on exchange
            order_result = await self._execute_exchange_order(
                symbol, side, position_size, current_price
            )
            
            if not order_result:
                logger.error(f"Failed to execute order on exchange for {symbol}")
                return None
            
            # Create position record
            position_id = str(uuid.uuid4())
            position = RealPosition(
                position_id=position_id,
                symbol=symbol,
                side=side,
                entry_price=current_price,
                position_size=position_size,
                leverage=self.leverage,
                stop_loss=self._calculate_stop_loss(current_price, side),
                take_profit=self._calculate_take_profit(current_price, side),
                entry_time=datetime.now(),
                strategy=signal.get('strategy_type', 'profit_scraping'),
                confidence=confidence
            )
            
            # Store position
            self.active_positions[position_id] = position
            
            # Store in database
            await self._store_position_in_db(position)
            
            # Register with trade sync service for manual trade learning
            if self.trade_sync_service:
                await self.trade_sync_service.register_system_trade(position_id, position.to_dict())
            
            self.total_trades += 1
            
            logger.info(f"✅ Real Trade Executed: {symbol} {side} @ ${current_price:.2f} "
                       f"Size: {position_size:.6f} Position ID: {position_id}")
            logger.warning(f"💰 REAL MONEY: ${position_size * current_price:.2f} notional value")
            
            return position_id
            
        except Exception as e:
            logger.error(f"Error executing real trade: {e}")
            return None
    
    async def close_position(self, position_id: str, reason: str = "MANUAL") -> bool:
        """Close a real position"""
        try:
            if position_id not in self.active_positions:
                logger.warning(f"Position {position_id} not found")
                return False
            
            position = self.active_positions[position_id]
            
            # Get current price
            current_price = await self.exchange_client.get_current_price(position.symbol)
            if not current_price:
                logger.error(f"Cannot get current price for {position.symbol}")
                return False
            
            # Execute close order on exchange
            close_result = await self._execute_close_order(position, current_price)
            if not close_result:
                logger.error(f"Failed to close position on exchange: {position_id}")
                return False
            
            # Calculate P&L
            if position.side == 'LONG':
                pnl = (current_price - position.entry_price) * position.position_size
                pnl_pct = ((current_price - position.entry_price) / position.entry_price) * 100
            else:  # SHORT
                pnl = (position.entry_price - current_price) * position.position_size
                pnl_pct = ((position.entry_price - current_price) / position.entry_price) * 100
            
            # Apply leverage to P&L
            pnl *= position.leverage
            pnl_pct *= position.leverage
            
            # Update position
            position.exit_price = current_price
            position.exit_time = datetime.now()
            position.pnl = pnl
            position.pnl_pct = pnl_pct
            position.status = 'CLOSED'
            
            # Update statistics
            self.total_pnl += pnl
            self.daily_pnl += pnl
            
            if pnl > 0:
                self.winning_trades += 1
            
            # Update in database
            await self._update_position_in_db(position)
            
            # Unregister with trade sync service
            if self.trade_sync_service:
                close_data = {
                    'exit_price': current_price,
                    'exit_time': position.exit_time,
                    'pnl': pnl,
                    'reason': reason
                }
                await self.trade_sync_service.unregister_system_trade(position_id, close_data)
            
            # Remove from active positions
            del self.active_positions[position_id]
            
            duration_minutes = int((position.exit_time - position.entry_time).total_seconds() / 60)
            duration_formatted = format_duration(duration_minutes)
            
            logger.info(f"📉 Real Position Closed: {position.symbol} {position.side} @ ${current_price:.2f} "
                       f"P&L: ${pnl:.2f} ({pnl_pct:.2f}%) Duration: {duration_formatted}")
            logger.warning(f"💰 REAL MONEY: P&L ${pnl:.2f}")
            
            # Check for emergency stop conditions
            await self._check_emergency_conditions()
            
            return True
            
        except Exception as e:
            logger.error(f"Error closing real position: {e}")
            return False
    
    async def _safety_checks(self, signal: Dict[str, Any]) -> bool:
        """Safety checks using SAME logic as successful paper trading"""
        try:
            # Check signal confidence (HIGH threshold like paper trading)
            confidence = signal.get('confidence', 0)
            if confidence < 0.7:  # HIGH threshold like successful paper trading
                logger.warning(f"❌ SAFETY: Signal confidence too low: {confidence:.2f}")
                return False
            
            # Check daily loss limit (same as paper trading)
            daily_loss_limit = -self.max_daily_loss
            if self.daily_pnl < daily_loss_limit:
                logger.warning(f"❌ SAFETY: Daily loss limit exceeded: ${self.daily_pnl:.2f} < ${daily_loss_limit:.2f}")
                return False
            
            # Check margin exposure (same logic as paper trading)
            current_margin_used = len(self.active_positions) * 200.0  # $200 per position
            
            # Get account balance
            try:
                balance_info = await self.exchange_client.get_account_balance()
                account_balance = balance_info.get('total', 10000.0) if balance_info else 10000.0
            except:
                account_balance = 10000.0  # Fallback
            
            max_exposure = account_balance * self.max_total_exposure
            margin_per_trade = 200.0
            
            if (current_margin_used + margin_per_trade) > max_exposure:
                logger.warning(f"❌ SAFETY: Margin limit exceeded: ${current_margin_used + margin_per_trade:.2f} > ${max_exposure:.2f}")
                logger.info(f"🔍 Available margin: ${max_exposure:.2f}, can have {max_exposure/200:.0f} positions")
                return False
            
            # Reset daily P&L if new day
            current_date = datetime.now().date()
            if current_date != self.last_reset_date:
                self.daily_pnl = 0.0
                self.last_reset_date = current_date
                logger.info("📅 Daily P&L reset for new trading day")
            
            return True
            
        except Exception as e:
            logger.error(f"Error in safety checks: {e}")
            return False
    
    def _calculate_position_size(self, symbol: str, price: float, confidence: float) -> float:
        """Calculate position size based on risk management"""
        try:
            # Fixed $200 per position as requested
            position_size_usd = self.position_size_usd  # $200 fixed
            
            # Calculate position size in base currency
            position_size = position_size_usd / price
            
            logger.info(f"Position size calculated: ${position_size_usd} = {position_size:.6f} {symbol}")
            
            return position_size
            
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return 0.0
    
    def _calculate_stop_loss(self, entry_price: float, side: str) -> float:
        """Calculate FIXED 0.5% stop loss for exactly $10 maximum loss per trade"""
        # FIXED STOP LOSS: 0.5% price movement = $10 loss with current leverage setup
        # $200 capital × 10x leverage = $2000 notional
        # $10 loss ÷ $2000 notional = 0.5% price movement
        fixed_sl_pct = 0.005  # 0.5% FIXED stop-loss for $10 maximum loss
        
        if side == 'LONG':
            sl_price = entry_price * (1 - fixed_sl_pct)
        else:  # SHORT
            sl_price = entry_price * (1 + fixed_sl_pct)
        
        # Calculate expected loss for verification
        if side == 'LONG':
            expected_loss = (entry_price - sl_price) * (200.0 * 10.0 / entry_price)  # $200 capital × 10x leverage
        else:  # SHORT
            expected_loss = (sl_price - entry_price) * (200.0 * 10.0 / entry_price)
        
        logger.info(f"🛡️ REAL TRADING FIXED SL: {side} @ {entry_price:.4f} → SL @ {sl_price:.4f} ({fixed_sl_pct:.1%}) [Expected Loss: ${expected_loss:.2f}]")
        return sl_price
    
    def _calculate_take_profit(self, entry_price: float, side: str) -> float:
        """Calculate take profit price"""
        take_profit_pct = 0.04  # 4% take profit (2:1 risk/reward)
        
        if side == 'LONG':
            return entry_price * (1 + take_profit_pct)
        else:  # SHORT
            return entry_price * (1 - take_profit_pct)
    
    async def _execute_exchange_order(self, symbol: str, side: str, size: float, price: float) -> bool:
        """Execute order on real exchange"""
        try:
            logger.warning(f"🚨 EXECUTING REAL ORDER: {side} {size:.6f} {symbol} @ ${price:.2f}")
            logger.warning(f"💰 REAL MONEY: ${size * price:.2f} notional value")
            
            # Execute real order on exchange
            order = await self.exchange_client.create_market_order(symbol, side, size)
            
            if order and order.get('id'):
                logger.info(f"✅ Real order executed successfully: Order ID {order['id']}")
                return True
            else:
                logger.error(f"❌ Failed to execute real order: {order}")
                return False
            
        except Exception as e:
            logger.error(f"❌ Error executing real exchange order: {e}")
            return False
    
    async def _execute_close_order(self, position: RealPosition, price: float) -> bool:
        """Execute close order on real exchange"""
        try:
            logger.warning(f"🚨 CLOSING REAL POSITION: {position.side} {position.position_size:.6f} {position.symbol} @ ${price:.2f}")
            
            # Determine close side (opposite of entry)
            close_side = 'SELL' if position.side == 'LONG' else 'BUY'
            
            # Execute real close order on exchange
            order = await self.exchange_client.create_market_order(position.symbol, close_side, position.position_size)
            
            if order and order.get('id'):
                logger.info(f"✅ Real position closed successfully: Order ID {order['id']}")
                return True
            else:
                logger.error(f"❌ Failed to close real position: {order}")
                return False
            
        except Exception as e:
            logger.error(f"❌ Error executing real close order: {e}")
            return False
    
    async def _store_position_in_db(self, position: RealPosition):
        """Store position in database"""
        try:
            with self.db_manager.session_scope() as session:
                # For now, just log the position data
                # In a full implementation, you would create a Trade model and save it
                logger.info(f"Storing position in database: {position.position_id}")
                
        except Exception as e:
            logger.error(f"Error storing position in database: {e}")
    
    async def _update_position_in_db(self, position: RealPosition):
        """Update position in database"""
        try:
            with self.db_manager.session_scope() as session:
                # For now, just log the position update
                # In a full implementation, you would update the Trade model
                logger.info(f"Updating position in database: {position.position_id}")
                
        except Exception as e:
            logger.error(f"Error updating position in database: {e}")
    
    async def _check_emergency_conditions(self):
        """Check for emergency stop conditions - MINIMAL CHECKS ONLY"""
        try:
            # NO LOSS LIMITS - removed as requested
            # Only check for critical system errors or manual emergency stop
            
            if self.emergency_stop:
                logger.error("🚨 EMERGENCY STOP: Manual emergency stop activated")
                await self.stop_trading()
            
        except Exception as e:
            logger.error(f"Error checking emergency conditions: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current real trading status"""
        try:
            win_rate = self.winning_trades / self.total_trades if self.total_trades > 0 else 0.0
            uptime_minutes = 0
            
            if self.start_time:
                uptime_minutes = (datetime.now() - self.start_time).total_seconds() / 60
            
            return {
                'active': self.is_running,
                'emergency_stop': self.emergency_stop,
                'active_positions': len(self.active_positions),
                'total_trades': self.total_trades,
                'winning_trades': self.winning_trades,
                'win_rate': win_rate,
                'total_pnl': self.total_pnl,
                'daily_pnl': self.daily_pnl,
                'uptime_minutes': uptime_minutes,
                'max_daily_loss': self.max_daily_loss,
                'positions': [pos.to_dict() for pos in self.active_positions.values()]
            }
            
        except Exception as e:
            logger.error(f"Error getting real trading status: {e}")
            return {'active': False, 'error': str(e)}
    
    def get_active_positions(self) -> List[Dict[str, Any]]:
        """Get all active real positions"""
        return [pos.to_dict() for pos in self.active_positions.values()]
