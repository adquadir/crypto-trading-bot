"""
Enhanced Paper Trading Engine
Ready-to-use paper trading system for testing flow trading strategies
"""

import asyncio
import logging
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import uuid
import random

from src.database.database import Database
from src.utils.time_utils import format_duration

# Import with fallbacks for optional dependencies
try:
    from src.config.flow_trading_config import get_config_manager
except ImportError:
    def get_config_manager():
        return None

try:
    from src.monitoring.flow_trading_monitor import get_monitor
except ImportError:
    def get_monitor():
        return None

try:
    from src.ml.ml_learning_service import get_ml_learning_service, TradeOutcome
except ImportError:
    async def get_ml_learning_service():
        return None
    
    class TradeOutcome:
        pass

logger = logging.getLogger(__name__)

@dataclass
class PaperPosition:
    """Paper trading position"""
    id: str
    symbol: str
    strategy_type: str
    side: str  # 'LONG', 'SHORT'
    entry_price: float
    quantity: float
    entry_time: datetime
    signal_source: str = "unknown"  # NEW: Track where the signal came from
    capital_allocated: float = 0.0  # NEW: Actual capital at risk (not leveraged amount)
    leverage: float = 10.0  # NEW: Leverage multiplier
    notional_value: float = 0.0  # NEW: Total position value (capital * leverage)
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    confidence_score: float = 0.0
    ml_score: float = 0.0
    entry_reason: str = ""
    market_regime: str = ""
    volatility_regime: str = ""
    
    # ABSOLUTE FLOOR PROTECTION SYSTEM
    profit_floor_activated: bool = False
    highest_profit_ever: float = 0.0
    absolute_floor_profit: float = 15.0  # $15 GROSS = $7 NET after $8 fees
    primary_target_profit: float = 18.0  # $18 GROSS = $10 NET after $8 fees
    closed: bool = False  # NEW: Prevent double exits and race conditions

@dataclass
class PaperTrade:
    """Completed paper trade"""
    id: str
    symbol: str
    strategy_type: str
    side: str
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    pnl_pct: float
    fees: float
    confidence_score: float
    ml_score: float
    entry_reason: str
    exit_reason: str
    duration_minutes: int
    market_regime: str
    volatility_regime: str
    signal_source: str  # NEW: Track where the signal came from
    entry_time: datetime
    exit_time: datetime

@dataclass
class PaperAccount:
    """Paper trading account"""
    balance: float
    equity: float
    unrealized_pnl: float
    realized_pnl: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: float
    max_drawdown: float
    sharpe_ratio: float
    daily_pnl: float
    last_updated: datetime

class EnhancedPaperTradingEngine:
    """Enhanced paper trading engine with ML integration"""
    
    def __init__(self, config: Dict[str, Any], exchange_client=None, flow_trading_strategy='adaptive'):
        self.config = config.get('paper_trading', {})
        self.exchange_client = exchange_client
        self.flow_trading_strategy = flow_trading_strategy  # NEW: Strategy selection
        
        # 🎯 SIGNAL SOURCE CONFIGURATION - Profit Scraping Primary with Smart Fallbacks
        self.signal_config = config.get('signal_sources', {
            'profit_scraping_primary': True,
            'allow_opportunity_fallback': False,  # Default OFF - Pure mode
            'allow_flow_trading_fallback': False,  # Default OFF - Pure mode
            'pure_profit_scraping_mode': True,     # Default ON - Pure mode
            'adaptive_thresholds': True,           # Lower thresholds in quiet markets
            'multi_timeframe_analysis': True,      # Check multiple timeframes
            'expanded_symbol_pool': True           # More symbols during low activity
        })
        
        # Initialize signal sources based on configuration
        self.profit_scraping_engine = None  # Always available (primary)
        self.opportunity_manager = None     # Only if fallback enabled
        
        logger.info(f"🎯 SIGNAL MODE: Pure Profit Scraping = {self.signal_config['pure_profit_scraping_mode']}")
        if self.signal_config['allow_opportunity_fallback']:
            logger.info("⚠️ Opportunity Manager fallback ENABLED")
        if self.signal_config['allow_flow_trading_fallback']:
            logger.info("⚠️ Flow Trading fallback ENABLED")
        else:
            logger.info("✅ Pure Profit Scraping Mode - No fallbacks enabled")
        
        # Initialize database - MUST work, no fallbacks
        self.db = Database()
        logger.info("✅ Database initialized for paper trading")
        
        # Trading state
        self.is_running = False
        
        # Uptime tracking
        self.start_time = None
        self.total_uptime_seconds = 0.0
        self.last_stop_time = None
        self.account = PaperAccount(
            balance=self.config.get('initial_balance', 10000.0),
            equity=self.config.get('initial_balance', 10000.0),
            unrealized_pnl=0.0,
            realized_pnl=0.0,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            profit_factor=0.0,
            max_drawdown=0.0,
            sharpe_ratio=0.0,
            daily_pnl=0.0,
            last_updated=datetime.utcnow()
        )
        
        # Positions and trades
        self.positions: Dict[str, PaperPosition] = {}  # position_id -> position
        self.completed_trades: List[PaperTrade] = []
        self.trade_history = deque(maxlen=1000)
        
        # Strategy performance tracking
        self.strategy_performance = defaultdict(lambda: {
            'total_trades': 0,
            'winning_trades': 0,
            'total_pnl': 0.0,
            'win_rate': 0.0,
            'profit_factor': 0.0,
            'avg_trade_duration': 0.0
        })
        
        # ML training data collection
        self.ml_training_data = []
        self.feature_history = defaultdict(deque)
        
        # CORRECTED RISK MANAGEMENT - Percentage-based scaling with position limits
        self.risk_per_trade_pct = self.config.get('risk_per_trade_pct', 0.10)  # 10% of balance per trade = $1000 per position
        self.max_positions = self.config.get('max_positions', 50)  # Fixed 50 position limit
        self.leverage = self.config.get('leverage', 10.0)  # 10x leverage
        self.max_total_risk_pct = self.config.get('max_total_risk_pct', 1.0)  # 100% max total risk
        
        # PURE 3-RULE MODE - Clean hierarchy enforcement
        self.pure_3_rule_mode = self.config.get('pure_3_rule_mode', True)  # Enable by default
        
        if self.pure_3_rule_mode:
            logger.info("🎯 PURE 3-RULE MODE ENABLED: Only $10 NET TP, $7 NET Floor, 0.5% SL will trigger exits (fee-corrected)")
        else:
            logger.info("🔧 COMPLEX MODE: All exit conditions active (technical, time-based, etc.)")
        
        logger.info("🟢 Enhanced Paper Trading Engine initialized")
    
    async def start(self):
        """Start paper trading engine"""
        if self.is_running:
            logger.warning("Paper trading engine already running")
            return
        
        self.is_running = True
        self.start_time = datetime.utcnow()  # Record start time for uptime calculation
        logger.info("🚀 Paper Trading Engine started")
        
        # Load existing state
        await self._load_state()
        
        # Start monitoring loops
        asyncio.create_task(self._position_monitoring_loop())
        asyncio.create_task(self._performance_tracking_loop())
        asyncio.create_task(self._ml_data_collection_loop())
        asyncio.create_task(self._signal_processing_loop())  # NEW: Process real signals
        
        # Initialize monitoring
        monitor = get_monitor()
        if monitor:
            await monitor.start_monitoring({
                'paper_trading_engine': self,
                'exchange_client': self.exchange_client,
                'opportunity_manager': self.opportunity_manager
            })
    
    def stop(self):
        """Stop paper trading engine"""
        if self.is_running and self.start_time:
            # Accumulate uptime before stopping
            session_uptime = (datetime.utcnow() - self.start_time).total_seconds()
            self.total_uptime_seconds += session_uptime
            self.last_stop_time = datetime.utcnow()
        
        self.is_running = False
        self.start_time = None
        logger.info("🛑 Paper Trading Engine stopped")
    
    def get_uptime_hours(self) -> float:
        """Get current uptime in hours"""
        try:
            current_session_seconds = 0.0
            
            # Add current session time if running
            if self.is_running and self.start_time:
                current_session_seconds = (datetime.utcnow() - self.start_time).total_seconds()
            
            # Total uptime = accumulated + current session
            total_seconds = self.total_uptime_seconds + current_session_seconds
            return total_seconds / 3600.0  # Convert to hours
            
        except Exception as e:
            logger.error(f"Error calculating uptime: {e}")
            return 0.0
    
    async def execute_trade(self, signal: Dict[str, Any]) -> Optional[str]:
        """Execute a paper trade based on signal"""
        try:
            logger.info(f"🎯 Paper Trading: Starting trade execution for {signal}")
            
            symbol = signal.get('symbol')
            strategy_type = signal.get('strategy_type', 'unknown')
            side = signal.get('side', 'LONG')
            confidence = signal.get('confidence', 0.0)
            ml_score = signal.get('ml_score', 0.0)
            entry_reason = signal.get('reason', '')
            
            logger.info(f"🎯 Paper Trading: Getting current price for {symbol}")
            
            # Get current price
            current_price = await self._get_current_price(symbol)
            if not current_price:
                logger.error(f"❌ Paper Trading: Could not get price for {symbol}")
                return None
            
            logger.info(f"🎯 Paper Trading: Got price {current_price} for {symbol}")
            
            # CRITICAL: ML Confidence Filtering BEFORE any other checks
            ml_recommendation = await self._get_ml_signal_recommendation(symbol, side, strategy_type, confidence)
            if not ml_recommendation['should_trade']:
                logger.warning(f"❌ ML FILTER: Trade rejected - {ml_recommendation['reason']}")
                logger.warning(f"❌ ML Confidence: {ml_recommendation['ml_confidence']:.3f}, Threshold: {ml_recommendation['threshold']:.3f}")
                return None
            
            logger.info(f"✅ ML FILTER: Trade approved - ML confidence {ml_recommendation['ml_confidence']:.3f}")
            
            # Update ML score with recommendation
            ml_score = ml_recommendation['ml_confidence']
            
            # Risk checks
            logger.info(f"🎯 Paper Trading: Checking risk limits for {symbol}")
            if not await self._check_risk_limits(symbol, current_price):
                logger.warning(f"❌ Paper Trading: Risk limits exceeded for {symbol}")
                return None
            
            logger.info(f"🎯 Paper Trading: Risk checks passed for {symbol}")
            
            # Calculate position size
            position_size = self._calculate_position_size(symbol, current_price, confidence)
            logger.info(f"🎯 Paper Trading: Calculated position size {position_size} for {symbol}")
            
            # CRITICAL FIX: Exit if position size is 0 (limits reached)
            if position_size <= 0:
                logger.warning(f"❌ Cannot create position: Invalid position size {position_size} (limits reached or insufficient capital)")
                return None
            
            # Calculate capital allocation for this position
            capital_allocated = self.account.balance * self.risk_per_trade_pct
            notional_value = capital_allocated * self.leverage
            
            # Create position with configurable rule parameters
            position_id = str(uuid.uuid4())
            position = PaperPosition(
                id=position_id,
                symbol=symbol,
                strategy_type=strategy_type,
                side=side,
                entry_price=current_price,
                quantity=position_size,
                entry_time=datetime.utcnow(),
                signal_source=signal.get('signal_source', 'unknown'),
                capital_allocated=capital_allocated,  # NEW: Track actual capital at risk
                leverage=self.leverage,  # NEW: Track leverage used
                notional_value=notional_value,  # NEW: Track total position value
                confidence_score=confidence,
                ml_score=ml_score,
                entry_reason=entry_reason,
                market_regime=signal.get('market_regime', ''),
                volatility_regime=signal.get('volatility_regime', ''),
                current_price=current_price
            )
            
            # Apply configurable rule parameters (fee-corrected defaults)
            position.primary_target_profit = self.config.get('primary_target_dollars', 18.0)  # $18 gross = $10 net after fees
            position.absolute_floor_profit = self.config.get('absolute_floor_dollars', 15.0)  # $15 gross = $7 net after fees
            
            logger.info(f"🎯 Paper Trading: Created position object for {symbol}")
            
            # Set stop loss and take profit
            position.stop_loss = await self._calculate_stop_loss(current_price, side, symbol)
            # FIXED: Re-enable normal take profit to work cooperatively with floor system
            position.take_profit = await self._calculate_take_profit(current_price, side, symbol)
            
            logger.info(f"🎯 Paper Trading: Set SL/TP for {symbol} - SL: {position.stop_loss}, TP: {position.take_profit} (Cooperative with Floor System)")
            
            # Store position
            self.positions[position_id] = position
            logger.info(f"🎯 Paper Trading: Stored position {position_id} for {symbol}")
            
            # Update account
            entry_fee = position_size * current_price * 0.0004  # Binance Futures taker fee: 0.04%
            self.account.equity -= entry_fee
            
            # Log trade
            logger.info(f"✅ Paper Trade Opened: {symbol} {side} @ {current_price:.4f} "
                       f"Size: {position_size:.4f} Confidence: {confidence:.2f} Position ID: {position_id}")
            
            # Store in database
            logger.info(f"🎯 Paper Trading: Storing position in database for {symbol}")
            await self._store_position(position)
            
            logger.info(f"✅ Paper Trading: Trade execution completed successfully for {symbol}")
            return position_id
            
        except Exception as e:
            logger.error(f"❌ Paper Trading: Error executing paper trade: {e}")
            import traceback
            logger.error(f"❌ Paper Trading: Full traceback: {traceback.format_exc()}")
            return None
    
    async def close_position(self, position_id: str, exit_reason: str = "manual") -> Optional[PaperTrade]:
        """Close a paper position with enhanced race condition protection"""
        try:
            logger.info(f"🔄 CLOSE REQUEST: Attempting to close position {position_id} (reason: {exit_reason})")
            
            # CRITICAL: Check if position exists and is not already closed
            if position_id not in self.positions:
                logger.error(f"❌ CLOSE FAILED: Position {position_id} not found in active positions")
                return None
            
            position = self.positions[position_id]
            
            # CRITICAL: Atomic check and mark as closed to prevent race conditions
            if getattr(position, 'closed', False):
                logger.warning(f"⚠️ CLOSE SKIPPED: Position {position_id} already marked as closed")
                return None
            
            # ATOMIC OPERATION: Mark as closed immediately
            position.closed = True
            logger.info(f"🔒 POSITION LOCKED: {position_id} marked as closed to prevent race conditions")
            
            # Get current price with retry logic
            current_price = None
            for attempt in range(3):  # Try up to 3 times
                try:
                    current_price = await self._get_current_price(position.symbol)
                    if current_price and current_price > 0:
                        break
                    logger.warning(f"⚠️ Price attempt {attempt + 1} failed for {position.symbol}: {current_price}")
                except Exception as price_error:
                    logger.warning(f"⚠️ Price fetch attempt {attempt + 1} error: {price_error}")
                    if attempt < 2:  # Not the last attempt
                        await asyncio.sleep(0.5)  # Brief delay before retry
            
            if not current_price or current_price <= 0:
                logger.error(f"❌ CLOSE FAILED: Could not get valid price for {position.symbol} after 3 attempts")
                # Revert closed status if we can't get price
                position.closed = False
                return None
            
            logger.info(f"💰 PRICE OBTAINED: {position.symbol} @ {current_price:.4f} for position {position_id}")
            
            # Calculate P&L with detailed logging
            if position.side == 'LONG':
                pnl = (current_price - position.entry_price) * position.quantity
                pnl_pct = (current_price - position.entry_price) / position.entry_price
                logger.info(f"📊 LONG P&L: ({current_price:.4f} - {position.entry_price:.4f}) * {position.quantity:.6f} = ${pnl:.2f}")
            else:  # SHORT
                pnl = (position.entry_price - current_price) * position.quantity
                pnl_pct = (position.entry_price - current_price) / position.entry_price
                logger.info(f"📊 SHORT P&L: ({position.entry_price:.4f} - {current_price:.4f}) * {position.quantity:.6f} = ${pnl:.2f}")
            
            # Calculate fees (Binance Futures taker fees: 0.04% per side = 0.08% round-trip)
            fee_per_side = 0.0004  # 0.04% taker fee
            entry_fee = position.quantity * position.entry_price * fee_per_side
            exit_fee = position.quantity * current_price * fee_per_side
            fees = entry_fee + exit_fee
            net_pnl = pnl - fees
            
            logger.info(f"💸 FEES: ${fees:.2f}, NET P&L: ${net_pnl:.2f} ({pnl_pct:.2%})")
            
            # Create completed trade
            duration = datetime.utcnow() - position.entry_time
            trade = PaperTrade(
                id=str(uuid.uuid4()),
                symbol=position.symbol,
                strategy_type=position.strategy_type,
                side=position.side,
                entry_price=position.entry_price,
                exit_price=current_price,
                quantity=position.quantity,
                pnl=net_pnl,
                pnl_pct=pnl_pct,
                fees=fees,
                confidence_score=position.confidence_score,
                ml_score=position.ml_score,
                entry_reason=position.entry_reason,
                exit_reason=exit_reason,
                duration_minutes=int(duration.total_seconds() / 60),
                market_regime=position.market_regime,
                volatility_regime=position.volatility_regime,
                signal_source=position.signal_source,  # NEW: Copy signal source from position
                entry_time=position.entry_time,
                exit_time=datetime.utcnow()
            )
            
            logger.info(f"📋 TRADE CREATED: {trade.id} for {position.symbol}")
            
            # Update account with detailed logging
            old_balance = self.account.balance
            old_realized_pnl = self.account.realized_pnl
            
            self.account.realized_pnl += net_pnl
            self.account.balance += net_pnl
            self.account.equity = self.account.balance + self._calculate_unrealized_pnl()
            self.account.total_trades += 1
            
            if net_pnl > 0:
                self.account.winning_trades += 1
            else:
                self.account.losing_trades += 1
            
            self.account.win_rate = self.account.winning_trades / self.account.total_trades
            
            logger.info(f"💰 ACCOUNT UPDATED: Balance ${old_balance:.2f} → ${self.account.balance:.2f} (${net_pnl:+.2f})")
            logger.info(f"📈 STATS: {self.account.winning_trades}W/{self.account.losing_trades}L ({self.account.win_rate:.1%} win rate)")
            
            # Update strategy performance
            self._update_strategy_performance(trade)
            
            # Store completed trade
            self.completed_trades.append(trade)
            self.trade_history.append(trade)
            
            # CRITICAL: Remove position from active positions
            try:
                del self.positions[position_id]
                logger.info(f"🗑️ POSITION REMOVED: {position_id} removed from active positions")
            except KeyError:
                logger.warning(f"⚠️ Position {position_id} already removed from active positions")
            
            # Log trade with formatted duration
            duration_formatted = format_duration(trade.duration_minutes)
            logger.info(f"✅ CLOSE COMPLETE: {position.symbol} {position.side} @ {current_price:.4f} "
                       f"P&L: ${net_pnl:.2f} ({pnl_pct:.2%}) Duration: {duration_formatted} Reason: {exit_reason}")
            
            # Store in database (non-blocking)
            try:
                await self._store_trade(trade)
                logger.info(f"💾 DATABASE: Trade {trade.id} stored successfully")
            except Exception as db_error:
                logger.error(f"❌ DATABASE ERROR: Failed to store trade {trade.id}: {db_error}")
                # Continue - don't fail the close operation due to database issues
            
            # Collect ML training data (non-blocking)
            try:
                await self._collect_ml_data(trade)
                logger.info(f"🧠 ML DATA: Trade {trade.id} added to ML training data")
            except Exception as ml_error:
                logger.error(f"❌ ML ERROR: Failed to collect ML data for trade {trade.id}: {ml_error}")
                # Continue - don't fail the close operation due to ML issues
            
            logger.info(f"🎉 POSITION CLOSED SUCCESSFULLY: {position_id} → Trade {trade.id}")
            return trade
            
        except Exception as e:
            logger.error(f"❌ CRITICAL ERROR closing position {position_id}: {e}")
            import traceback
            logger.error(f"❌ FULL TRACEBACK: {traceback.format_exc()}")
            
            # Try to revert closed status if position still exists
            try:
                if position_id in self.positions:
                    self.positions[position_id].closed = False
                    logger.info(f"🔓 REVERTED: Position {position_id} closed status reverted due to error")
            except Exception as revert_error:
                logger.error(f"❌ Could not revert closed status: {revert_error}")
            
            return None
    
    async def _position_monitoring_loop(self):
        """Monitor positions for stop loss/take profit AND ABSOLUTE $7 FLOOR PROTECTION"""
        while self.is_running:
            try:
                positions_to_close = []
                
                for position_id, position in self.positions.items():
                    # Skip already closed positions to prevent race conditions
                    if getattr(position, 'closed', False):
                        continue
                    
                    try:
                        # EMERGENCY SAFETY: Wrap each position check in try-catch
                        # to prevent one bad position from stopping all monitoring
                        
                        # CRITICAL FIX: Get current price with better error handling
                        current_price = None
                        try:
                            current_price = await self._get_current_price(position.symbol)
                        except Exception as price_error:
                            logger.warning(f"⚠️ Price fetch failed for {position.symbol}: {price_error}")
                            continue  # Skip this position this cycle, try again next cycle
                        
                        if not current_price or current_price <= 0:
                            logger.warning(f"⚠️ Invalid price for {position.symbol}: {current_price}")
                            continue
                        
                        # EMERGENCY: Log critical position info
                        logger.debug(f"📊 MONITORING: {position.symbol} {position.side} @ ${current_price:.4f} (Entry: ${position.entry_price:.4f})")
                        
                        # Update unrealized P&L with DETAILED LOGGING
                        if position.side == 'LONG':
                            position.unrealized_pnl = (current_price - position.entry_price) * position.quantity
                            position.unrealized_pnl_pct = ((current_price - position.entry_price) / position.entry_price) * 100
                        else:  # SHORT
                            position.unrealized_pnl = (position.entry_price - current_price) * position.quantity
                            position.unrealized_pnl_pct = ((position.entry_price - current_price) / position.entry_price) * 100
                        
                        position.current_price = current_price
                        
                        # Calculate current profit in dollars
                        current_pnl_dollars = position.unrealized_pnl
                        
                        # EMERGENCY: Log all critical values for debugging
                        if abs(current_pnl_dollars) > 15.0:  # Log positions with significant P&L
                            logger.info(f"💰 CRITICAL P&L: {position.symbol} {position.side} @ ${current_pnl_dollars:.2f}")
                            logger.info(f"   Entry: ${position.entry_price:.4f} | Current: ${current_price:.4f}")
                            logger.info(f"   Stop Loss: ${position.stop_loss:.4f} | Target: ${position.primary_target_profit:.2f}")
                        
                        # ENHANCED DEBUG LOGGING for positions approaching $10
                        if current_pnl_dollars >= 8.0:  # Log when approaching $10 target
                            logger.info(f"🎯 PROFIT TRACKING: {position.symbol} @ ${current_pnl_dollars:.2f} profit (Target: $10)")
                            logger.info(f"   Entry: ${position.entry_price:.4f} | Current: ${current_price:.4f} | Quantity: {position.quantity:.6f}")
                            logger.info(f"   Side: {position.side} | Calculation: ({current_price:.4f} - {position.entry_price:.4f}) * {position.quantity:.6f} = ${current_pnl_dollars:.2f}")
                        elif current_pnl_dollars >= 5.0:  # Also log $5+ positions
                            logger.info(f"💰 PROFIT UPDATE: {position.symbol} @ ${current_pnl_dollars:.2f} profit")
                        
                        # Update highest profit ever reached
                        position.highest_profit_ever = max(position.highest_profit_ever, current_pnl_dollars)
                        
                        # ============================================================================
                        # RULE 1: PRIMARY TARGET - $10 NET PROFIT (ABSOLUTE HIGHEST PRIORITY)
                        # ============================================================================
                        if current_pnl_dollars >= position.primary_target_profit:
                            logger.info(f"✅ RULE 1 EXIT: {position.symbol} hit $10 NET take profit (${current_pnl_dollars:.2f} gross)")
                            logger.info(f"🎯 PRIMARY TARGET HIT: {position.symbol} reached ${current_pnl_dollars:.2f} >= ${position.primary_target_profit:.2f}")
                            logger.info(f"🎯 IMMEDIATE EXIT: Marking position {position_id} for closure")
                            
                            # CRITICAL FIX: Don't set closed=True here, let close_position handle it
                            positions_to_close.append((position_id, "primary_target_10_dollars"))
                            continue  # Skip ALL other checks - $10 target takes absolute precedence
                        
                        # ============================================================================
                        # RULE 2: ABSOLUTE FLOOR ACTIVATION - Once $7 NET is reached
                        # ============================================================================
                        if position.highest_profit_ever >= position.absolute_floor_profit:
                            # Floor is now ACTIVE - position is protected at $7 NET
                            if not position.profit_floor_activated:
                                position.profit_floor_activated = True
                                logger.info(f"🛡️ FLOOR ACTIVATED: {position.symbol} reached ${position.highest_profit_ever:.2f} gross = $7 NET floor now ACTIVE")
                            
                            # RULE 3: ABSOLUTE FLOOR PROTECTION - Never drop below $7 NET
                            if current_pnl_dollars < position.absolute_floor_profit:
                                logger.info(f"📉 RULE 2 EXIT: {position.symbol} floor violation (${current_pnl_dollars:.2f} gross < $15 gross = $7 NET after peak ${position.highest_profit_ever:.2f})")
                                logger.info(f"💰 FLOOR VIOLATION: {position.symbol} dropped to ${current_pnl_dollars:.2f} gross < $7 NET floor")
                                positions_to_close.append((position_id, "absolute_floor_7_dollars"))
                                continue  # Skip all other checks - floor protection takes precedence
                        
                        # ============================================================================
                        # RULE 3: Below $7 - Apply remaining rules based on mode
                        # ============================================================================
                        
                        if self.pure_3_rule_mode:
                            # PURE 3-RULE MODE: Use DOLLAR-BASED stop loss instead of percentage
                            logger.debug(f"🎯 PURE MODE: {position.symbol} checking $18 dollar-based stop loss")
                            
                            # CRITICAL FIX: Check DOLLAR-BASED stop loss (only if floor not activated)
                            if not position.profit_floor_activated:
                                # Dollar-based stop loss: Limit loss to $18 gross (= $10 net after $8 fees)
                                max_loss_dollars = 18.0
                                
                                # Enhanced logging for dollar-based stop loss
                                logger.info(f"🔍 DOLLAR SL CHECK: {position.symbol} {position.side}")
                                logger.info(f"   Current PnL: ${current_pnl_dollars:.2f} | Max Loss: ${max_loss_dollars:.2f}")
                                logger.info(f"   Floor Active: {position.profit_floor_activated}")
                                
                                if current_pnl_dollars <= -max_loss_dollars:
                                    logger.warning(f"🚨 DOLLAR STOP LOSS TRIGGERED: {position.symbol} loss ${current_pnl_dollars:.2f} >= ${max_loss_dollars:.2f}")
                                    logger.warning(f"🚨 Entry: ${position.entry_price:.4f} | Current: ${current_price:.4f}")
                                    logger.info(f"🔻 RULE 3 EXIT: {position.symbol} $18 dollar stop loss hit (${current_pnl_dollars:.2f} loss)")
                                    positions_to_close.append((position_id, "dollar_stop_loss_18"))
                                    continue
                                else:
                                    logger.debug(f"🔍 DOLLAR SL: ${current_pnl_dollars:.2f} > -${max_loss_dollars:.2f} (no trigger)")
                                
                                # In pure mode, NO other exits are allowed below $7
                                logger.debug(f"🎯 PURE MODE: {position.symbol} no other exits - waiting for $7+ or $18 loss")
                            else:
                                # EMERGENCY: Log why stop loss is disabled
                                logger.debug(f"🔍 SL DISABLED: {position.symbol} - floor active")
                                
                        else:
                            # COMPLEX MODE: All original exit conditions
                            logger.debug(f"🔧 COMPLEX MODE: {position.symbol} checking all exit conditions")
                            
                            # CRITICAL: Check for level breakdown/breakout BEFORE normal SL/TP
                            # FIXED: Use fee-corrected threshold to prevent overriding stop loss
                            breakdown_exit = await self._check_level_breakdown_exit(position, current_price)
                            if breakdown_exit:
                                positions_to_close.append((position_id, breakdown_exit))
                                continue  # Skip other checks if level breakdown detected
                            
                            # Check for trend reversal exit
                            trend_reversal_exit = await self._check_trend_reversal_exit(position, current_price)
                            if trend_reversal_exit:
                                positions_to_close.append((position_id, trend_reversal_exit))
                                continue  # Skip other checks if trend reversal detected
                            
                            # COMPLEX MODE: Use same dollar-based stop loss for consistency
                            if not position.profit_floor_activated:
                                # Dollar-based stop loss: Limit loss to $18 gross (= $10 net after $8 fees)
                                max_loss_dollars = 18.0
                                
                                # Enhanced logging for dollar-based stop loss in complex mode
                                logger.info(f"🔍 COMPLEX DOLLAR SL CHECK: {position.symbol} {position.side}")
                                logger.info(f"   Current PnL: ${current_pnl_dollars:.2f} | Max Loss: ${max_loss_dollars:.2f}")
                                
                                if current_pnl_dollars <= -max_loss_dollars:
                                    logger.warning(f"🚨 COMPLEX DOLLAR STOP LOSS TRIGGERED: {position.symbol} loss ${current_pnl_dollars:.2f} >= ${max_loss_dollars:.2f}")
                                    logger.warning(f"🚨 Entry: ${position.entry_price:.4f} | Current: ${current_price:.4f}")
                                    logger.info(f"🔻 COMPLEX EXIT: {position.symbol} $18 dollar stop loss hit (${current_pnl_dollars:.2f} loss)")
                                    positions_to_close.append((position_id, "dollar_stop_loss_18"))
                                    continue
                            
                            # Check take profit (only if floor not activated)
                            if not position.profit_floor_activated and position.take_profit:
                                if (position.side == 'LONG' and current_price >= position.take_profit) or \
                                   (position.side == 'SHORT' and current_price <= position.take_profit):
                                    positions_to_close.append((position_id, "take_profit"))
                                    continue
                            
                            # Optional: Add safety net for extremely long positions (7 days)
                            # Only close if position is losing money to prevent runaway losses
                            hold_time = datetime.utcnow() - position.entry_time
                            if hold_time > timedelta(days=7) and position.unrealized_pnl < 0:
                                positions_to_close.append((position_id, "safety_time_limit"))
                                logger.warning(f"⚠️ Closing losing position {position_id} after 7 days for safety")
                
                    except Exception as position_error:
                        # EMERGENCY SAFETY: Log position monitoring errors but continue with other positions
                        logger.error(f"❌ Error monitoring position {position_id} ({position.symbol}): {position_error}")
                        import traceback
                        logger.error(f"❌ Position monitoring traceback: {traceback.format_exc()}")
                        # Continue monitoring other positions - don't let one failure stop everything
                
                # Close positions with enhanced logging and error handling
                for position_id, reason in positions_to_close:
                    logger.info(f"🔄 CLOSING POSITION: {position_id} for reason: {reason}")
                    try:
                        await self.close_position(position_id, reason)
                    except Exception as close_error:
                        logger.error(f"❌ Failed to close position {position_id}: {close_error}")
                        # Continue with other positions - don't let one failure stop everything
                
                # Update account equity
                self.account.unrealized_pnl = self._calculate_unrealized_pnl()
                self.account.equity = self.account.balance + self.account.unrealized_pnl
                
                await asyncio.sleep(0.5)  # EMERGENCY FIX: Check every 0.5 seconds for faster stop loss detection
                
            except Exception as e:
                logger.error(f"Error in position monitoring loop: {e}")
                import traceback
                logger.error(f"Full traceback: {traceback.format_exc()}")
                await asyncio.sleep(30)
    
    async def _performance_tracking_loop(self):
        """Track performance metrics"""
        while self.is_running:
            try:
                # Calculate daily P&L
                today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                daily_trades = [t for t in self.completed_trades if t.exit_time >= today_start]
                self.account.daily_pnl = sum(t.pnl for t in daily_trades)
                
                # Calculate profit factor
                winning_pnl = sum(t.pnl for t in self.completed_trades if t.pnl > 0)
                losing_pnl = abs(sum(t.pnl for t in self.completed_trades if t.pnl < 0))
                self.account.profit_factor = winning_pnl / losing_pnl if losing_pnl > 0 else 0
                
                # Calculate max drawdown
                equity_curve = []
                running_equity = self.config.get('initial_balance', 10000.0)
                for trade in self.completed_trades:
                    running_equity += trade.pnl
                    equity_curve.append(running_equity)
                
                if equity_curve:
                    peak = equity_curve[0]
                    max_dd = 0
                    for equity in equity_curve:
                        if equity > peak:
                            peak = equity
                        drawdown = (peak - equity) / peak
                        max_dd = max(max_dd, drawdown)
                    self.account.max_drawdown = max_dd
                
                # Calculate Sharpe ratio (simplified)
                if len(self.completed_trades) > 10:
                    returns = [t.pnl_pct for t in self.completed_trades]
                    avg_return = sum(returns) / len(returns)
                    return_std = (sum((r - avg_return) ** 2 for r in returns) / len(returns)) ** 0.5
                    self.account.sharpe_ratio = avg_return / return_std if return_std > 0 else 0
                
                self.account.last_updated = datetime.utcnow()
                
                # Store performance metrics
                await self._store_performance_metrics()
                
                await asyncio.sleep(300)  # Update every 5 minutes
                
            except Exception as e:
                logger.error(f"Error in performance tracking loop: {e}")
                await asyncio.sleep(300)
    
    async def _ml_data_collection_loop(self):
        """Collect ML training data"""
        while self.is_running:
            try:
                # Collect features for active positions
                for position in self.positions.values():
                    features = await self._extract_features(position)
                    if features:
                        self.feature_history[position.symbol].append({
                            'timestamp': datetime.utcnow(),
                            'features': features,
                            'position_id': position.id
                        })
                
                await asyncio.sleep(60)  # Collect every minute
                
            except Exception as e:
                logger.error(f"Error in ML data collection loop: {e}")
                await asyncio.sleep(60)
    
    async def _signal_processing_loop(self):
        """Process real trading signals from opportunity manager"""
        logger.info("🎯 Paper Trading: Signal processing loop started")
        
        while self.is_running:
            try:
                if not self.opportunity_manager:
                    logger.warning("🎯 Paper Trading: No opportunity manager available, waiting...")
                    await asyncio.sleep(30)
                    continue
                
                logger.info("🎯 Paper Trading: Checking for fresh opportunities...")
                
                # Get fresh opportunities from the opportunity manager
                opportunities = await self._get_fresh_opportunities()
                
                logger.info(f"🎯 Paper Trading: Found {len(opportunities)} opportunities")
                
                if opportunities:
                    logger.info(f"🎯 Paper Trading: Processing {len(opportunities)} fresh opportunities")
                    
                    for opportunity in opportunities:
                        logger.info(f"🎯 Paper Trading: Processing opportunity: {opportunity.get('symbol')} {opportunity.get('side', opportunity.get('direction'))} (confidence: {opportunity.get('confidence')})")
                        
                        # Convert opportunity to trading signal
                        signal = self._convert_opportunity_to_signal(opportunity)
                        
                        if signal:
                            logger.info(f"🎯 Paper Trading: Converted to signal: {signal}")
                            
                            # CRITICAL FIX: Preserve original strategy type from profit scraping
                            if hasattr(opportunity, 'strategy_type'):
                                signal['strategy_type'] = opportunity.strategy_type
                            elif opportunity.get('strategy_type'):
                                signal['strategy_type'] = opportunity['strategy_type']
                            
                            # Add debug: log all filter checks
                            filter_passed = self._should_trade_signal(signal)
                            if not filter_passed:
                                logger.info(f"❌ Signal rejected by filters: {signal['symbol']} {signal['side']} | Details: {signal}")
                            else:
                                logger.info(f"🚀 Paper Trading: Executing trade for {signal['symbol']} {signal['side']} | Strategy: {signal['strategy_type']} | Source: {signal.get('signal_source', 'unknown')}")
                                position_id = await self.execute_trade(signal)
                                
                                if position_id:
                                    logger.info(f"✅ Paper Trade executed: {signal['symbol']} {signal['side']} (Position: {position_id})")
                                else:
                                    logger.warning(f"❌ Failed to execute paper trade: {signal['symbol']} {signal['side']}")
                        else:
                            logger.warning(f"🎯 Paper Trading: Failed to convert opportunity to signal: {opportunity}")
                else:
                    logger.info("🎯 Paper Trading: No fresh opportunities found")
                
                await asyncio.sleep(30)  # Check for new signals every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in signal processing loop: {e}")
                import traceback
                logger.error(f"Full traceback: {traceback.format_exc()}")
                await asyncio.sleep(60)
    
    async def _get_fresh_opportunities(self) -> List[Dict[str, Any]]:
        """Get trading opportunities with PROFIT SCRAPING primary + optional fallbacks"""
        try:
            # PRIORITY 1: Profit Scraping Engine (ALWAYS FIRST)
            if self.profit_scraping_engine and hasattr(self.profit_scraping_engine, 'active') and self.profit_scraping_engine.active:
                logger.info("[SIGNAL] Fetching from Profit Scraping Engine (PRIMARY)")
                profit_opportunities = await self._get_profit_scraping_opportunities()
                
                if profit_opportunities:
                    logger.info(f"[SIGNAL] Pure mode: {len(profit_opportunities)} profit-scraping signals found")
                    for opp in profit_opportunities:
                        logger.info(f"[TRADE EXEC] Pure mode: Profit Scraping signal ready for {opp['symbol']}")
                    return profit_opportunities
                else:
                    logger.info("[SIGNAL] No profit-scraping opportunities this cycle.")
                    
                    # Check if fallbacks are enabled
                    if not self.signal_config.get('allow_opportunity_fallback', False):
                        logger.info("[SIGNAL] Pure mode: No fallbacks enabled, skipping cycle")
                        return []
            
            # FALLBACK 1: Opportunity Manager (ONLY IF ENABLED)
            if self.signal_config.get('allow_opportunity_fallback', False) and self.opportunity_manager:
                logger.warning("[SIGNAL] FALLBACK: Using Opportunity Manager (profit scraping unavailable)")
                opportunities = self.opportunity_manager.get_opportunities()
                if opportunities:
                    tradable_opportunities = [opp for opp in opportunities if opp.get('tradable', False)]
                    if tradable_opportunities:
                        logger.info(f"[SIGNAL] Fallback mode: {len(tradable_opportunities)} opportunity manager signals")
                        return tradable_opportunities
            
            # FALLBACK 2: Flow Trading (ONLY IF ENABLED)
            if self.signal_config.get('allow_flow_trading_fallback', False):
                logger.warning("[SIGNAL] FALLBACK: Using Flow Trading (all other sources failed)")
                flow_opportunities = await self._get_flow_trading_opportunities()
                if flow_opportunities:
                    logger.info(f"[SIGNAL] Flow fallback: {len(flow_opportunities)} flow trading signals")
                    return flow_opportunities
            
            # No signals available
            logger.info("[SIGNAL] No signals from any enabled source this cycle")
            return []
            
        except Exception as e:
            logger.error(f"Error getting opportunities: {e}")
            return []
    
    async def _get_profit_scraping_opportunities(self) -> List[Dict[str, Any]]:
        """Get high-quality opportunities from profit scraping engine"""
        try:
            if not self.profit_scraping_engine:
                logger.warning("❌ No profit scraping engine available")
                return []
            
            # Get current opportunities from profit scraping engine
            opportunities = self.profit_scraping_engine.get_opportunities()
            
            if not opportunities:
                logger.info("📊 No opportunities available from profit scraping engine")
                return []
            
            logger.info(f"📊 Got {len(opportunities)} symbols with opportunities from profit scraping engine")
            
            converted_opportunities = []
            
            for symbol, symbol_opportunities in opportunities.items():
                logger.info(f"📊 Processing {symbol}: {len(symbol_opportunities)} opportunities")
                
                for opp in symbol_opportunities:
                    logger.info(f"📊 Converting opportunity: {symbol} {opp.get('level', {}).get('level_type', 'unknown')} (score: {opp.get('opportunity_score', 0)})")
                    
                    # Convert profit scraping opportunity to signal format
                    signal = self._convert_profit_scraping_opportunity_to_signal(opp)
                    if signal:
                        converted_opportunities.append(signal)
                        logger.info(f"✅ Successfully converted {symbol} opportunity to signal")
                    else:
                        logger.warning(f"❌ Failed to convert {symbol} opportunity to signal")
            
            # Sort by opportunity score (highest first)
            converted_opportunities.sort(key=lambda x: x.get('opportunity_score', 0), reverse=True)
            
            logger.info(f"🎯 Profit Scraping: Converted {len(converted_opportunities)} opportunities to signals")
            
            if converted_opportunities:
                logger.info("🚀 TOP PROFIT SCRAPING SIGNALS:")
                for i, signal in enumerate(converted_opportunities[:5]):  # Show top 5
                    logger.info(f"  {i+1}. {signal['symbol']} {signal['side']} (confidence: {signal['confidence']:.3f}, score: {signal['opportunity_score']})")
            
            return converted_opportunities
            
        except Exception as e:
            logger.error(f"❌ Error getting profit scraping opportunities: {e}")
            import traceback
            logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            return []
    
    def _convert_profit_scraping_opportunity_to_signal(self, opp: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Convert profit scraping opportunity to trading signal format"""
        try:
            # Extract data from profit scraping opportunity
            symbol = opp['symbol']
            level = opp['level']
            targets = opp['targets']
            current_price = opp['current_price']
            distance_to_level = opp['distance_to_level']
            opportunity_score = opp['opportunity_score']
            
            logger.info(f"🔧 Converting profit scraping opportunity: {symbol} {level['level_type']} @ {level['price']:.4f} (score: {opportunity_score})")
            
            # Determine trade direction based on level type
            if level['level_type'] == 'support':
                side = 'LONG'
            elif level['level_type'] == 'resistance':
                side = 'SHORT'
            else:
                logger.warning(f"❌ Unknown level type: {level['level_type']} for {symbol}")
                return None
            
            # Convert confidence score to 0-1 scale
            confidence = targets['confidence_score'] / 100.0
            
            # Convert to signal format
            signal = {
                'symbol': symbol,
                'side': side,
                'confidence': confidence,
                'strategy_type': 'profit_scraping',
                'signal_source': f"profit_scraping_{level['level_type']}",  # More specific signal source
                'entry_price': current_price,
                'stop_loss': targets['stop_loss'],
                'take_profit': targets['profit_target'],
                'leverage': 10,  # Match paper trading leverage
                'opportunity_score': opportunity_score,
                'distance_to_level': distance_to_level,
                'level_type': level['level_type'],
                'level_strength': level['strength_score'],
                'expected_duration_minutes': targets['expected_duration_minutes'],
                'profit_probability': targets['profit_probability'],
                'risk_reward_ratio': targets['risk_reward_ratio'],
                'market_regime': 'level_based',
                'volatility_regime': 'medium',
                'reason': f"Profit scraping: {level['level_type']} @ {level['price']:.4f} (score: {opportunity_score})"
            }
            
            logger.info(f"✅ Converted to signal: {symbol} {side} (confidence: {confidence:.3f}) - PROFIT SCRAPING")
            return signal
            
        except Exception as e:
            logger.error(f"❌ Error converting profit scraping opportunity to signal: {e}")
            logger.error(f"❌ Opportunity data: {opp}")
            import traceback
            logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            return None
    
    def _convert_scraping_opportunity(self, opp: Dict[str, Any], symbol: str) -> Optional[Dict[str, Any]]:
        """Convert profit scraping opportunity to paper trading format"""
        try:
            # Extract data from profit scraping opportunity structure
            level = opp.get('level', {})
            targets = opp.get('targets', {})
            magnet_level = opp.get('magnet_level', {})
            
            # Determine trade direction based on level type
            level_type = level.get('level_type', 'support')
            side = 'LONG' if level_type == 'support' else 'SHORT'
            
            # Use the opportunity score as confidence
            confidence = opp.get('opportunity_score', 0) / 100.0  # Convert 0-100 to 0-1
            
            # Create the opportunity in our expected format
            converted = {
                'symbol': symbol,
                'side': side,
                'confidence': confidence,
                'strategy_type': 'profit_scraping',
                'level_price': level.get('price', 0),
                'profit_target': targets.get('profit_target', 0),
                'stop_loss': targets.get('stop_loss', 0),
                'level_strength': level.get('strength_score', 0),
                'magnet_strength': magnet_level.get('strength', 0) if magnet_level else 0,
                'entry_reason': f"magnet_level_{level_type}",
                'market_regime': 'profit_scraping',
                'volatility_regime': 'medium'
            }
            
            logger.info(f"🎯 Converted profit scraping opportunity: {symbol} {side} @ {level.get('price', 0):.2f} (confidence: {confidence:.2f})")
            
            return converted
            
        except Exception as e:
            logger.error(f"Error converting scraping opportunity: {e}")
            return None
    
    def _convert_opportunity_to_signal(self, opportunity: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Convert opportunity to trading signal"""
        try:
            # CRITICAL FIX: Map 'direction' field to 'side' field
            direction = opportunity.get('direction') or opportunity.get('side', 'LONG')
            
            signal = {
                'symbol': opportunity.get('symbol'),
                'strategy_type': 'scalping',  # Default to scalping for paper trading
                'signal_source': f"opportunity_{opportunity.get('strategy_type', 'unknown')}",  # More specific signal source
                'side': direction,  # Use direction field from opportunity
                'confidence': opportunity.get('confidence', 0.0),
                'ml_score': opportunity.get('ml_score', opportunity.get('confidence', 0.0)),
                'reason': f"auto_signal_{opportunity.get('strategy_type', 'unknown')}",
                'market_regime': opportunity.get('market_regime', 'unknown'),
                'volatility_regime': opportunity.get('volatility_regime', 'medium')
            }
            
            logger.info(f"🔄 Signal conversion: {opportunity.get('symbol')} {direction} (confidence: {opportunity.get('confidence', 0.0):.3f}) - OPPORTUNITY MANAGER")
            
            return signal
            
        except Exception as e:
            logger.error(f"Error converting opportunity to signal: {e}")
            return None
    
    def _should_trade_signal(self, signal: Dict[str, Any]) -> bool:
        """Determine if we should trade this signal - PAPER TRADING MODE: AGGRESSIVE APPROVAL"""
        try:
            # Basic filters
            if not signal.get('symbol') or not signal.get('side'):
                logger.info(f"❌ Signal rejected: Missing symbol or side")
                return False
            
            symbol = signal['symbol']
            strategy_type = signal.get('strategy_type', 'unknown')
            base_confidence = signal.get('confidence', 0)
            
            logger.info(f"🔍 Evaluating signal: {symbol} {signal.get('side')} (strategy: {strategy_type}, confidence: {base_confidence:.3f})")
            
            # PAPER TRADING MODE: Much more aggressive approval
            # Lower confidence thresholds for testing
            if strategy_type == 'profit_scraping':
                min_confidence = 0.50  # Reduced from 0.60
            elif strategy_type == 'flow_trading':
                min_confidence = 0.45  # Reduced from 0.55
            elif strategy_type == 'opportunity_manager':
                min_confidence = 0.50  # Reduced from 0.65
            else:
                min_confidence = 0.40  # Reduced from 0.50
            
            logger.info(f"🔍 Confidence check: {base_confidence:.3f} >= {min_confidence:.3f} ({strategy_type})")
            
            # Basic confidence check
            if base_confidence < min_confidence:
                logger.info(f"❌ {symbol} rejected: Low confidence {base_confidence:.3f} < {min_confidence:.3f} ({strategy_type})")
                return False
            
            # PAPER TRADING: Skip cooldown check (already returns False)
            # PAPER TRADING: Skip recent performance checks for aggressive testing
            
            logger.info(f"✅ {symbol} approved: Confidence {base_confidence:.3f} >= {min_confidence:.3f} ({strategy_type}) - PAPER TRADING MODE")
            return True
            
        except Exception as e:
            logger.error(f"Error checking if should trade signal: {e}")
            return False
    
    def _recently_traded_symbol(self, symbol: str) -> bool:
        """Check if we recently traded this symbol - NO COOLDOWN FOR PAPER TRADING"""
        try:
            # PAPER TRADING FIX: No cooldown restrictions for paper trading
            # We want to test the system aggressively, not limit opportunities
            return False
            
        except Exception as e:
            logger.error(f"Error checking recently traded symbol: {e}")
            return False
    
    async def _get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for symbol - REAL DATA ONLY, NO MOCK PRICES EVER"""
        try:
            if not self.exchange_client:
                logger.error(f"❌ CRITICAL: Exchange client not available for {symbol} - CANNOT GET REAL PRICE")
                raise Exception(f"Exchange client not initialized - real prices unavailable for {symbol}")
            
            # Try primary method: get_ticker_24h
            try:
                ticker = await self.exchange_client.get_ticker_24h(symbol)
                if ticker and ticker.get('lastPrice'):
                    price = float(ticker.get('lastPrice', 0))
                    if price > 0:
                        logger.debug(f"✅ Real price from ticker: {symbol} = ${price:.4f}")
                        return price
                    else:
                        logger.warning(f"⚠️ Invalid price from ticker: {symbol} = {price}")
            except Exception as e:
                logger.warning(f"⚠️ Ticker method failed for {symbol}: {e}")
            
            # Try fallback method: get_current_price
            try:
                price = await self.exchange_client.get_current_price(symbol)
                if price and price > 0:
                    logger.debug(f"✅ Real price from current_price: {symbol} = ${price:.4f}")
                    return price
                else:
                    logger.warning(f"⚠️ Invalid price from current_price: {symbol} = {price}")
            except Exception as e:
                logger.warning(f"⚠️ Current price method failed for {symbol}: {e}")
            
            # Try WebSocket cached data as final real data source
            try:
                if hasattr(self.exchange_client, 'last_trade_price') and symbol in self.exchange_client.last_trade_price:
                    price = self.exchange_client.last_trade_price[symbol]
                    if price and price > 0:
                        logger.debug(f"✅ Real price from WebSocket cache: {symbol} = ${price:.4f}")
                        return price
                    else:
                        logger.warning(f"⚠️ Invalid price from WebSocket cache: {symbol} = {price}")
            except Exception as e:
                logger.warning(f"⚠️ WebSocket cache method failed for {symbol}: {e}")
            
            # CRITICAL: NO MOCK DATA - If we can't get real prices, fail the trade
            logger.error(f"❌ CRITICAL: ALL REAL PRICE SOURCES FAILED for {symbol}")
            logger.error(f"❌ Exchange client status: {type(self.exchange_client).__name__ if self.exchange_client else 'None'}")
            logger.error(f"❌ Exchange client initialized: {getattr(self.exchange_client, 'initialized', False)}")
            
            # Raise exception instead of returning mock data
            raise Exception(f"REAL PRICE UNAVAILABLE: All price sources failed for {symbol} - cannot execute trade without real market data")
            
        except Exception as e:
            logger.error(f"❌ FATAL: Cannot get real price for {symbol}: {e}")
            # NO FALLBACK TO MOCK DATA - Let the trade fail
            raise Exception(f"Real price fetch failed for {symbol}: {e}")
    
    def _calculate_position_size(self, symbol: str, price: float, confidence: float) -> float:
        """Calculate position size with FIXED $1000 capital allocation for consistent stop loss"""
        try:
            # FIXED CAPITAL ALLOCATION - Always use $1000 regardless of current balance
            # This ensures stop loss calculations work correctly for $10k notional positions
            capital_per_position = 1000.0  # Fixed $1000 capital per position
            leverage = self.leverage  # 10x leverage
            
            # Check position limits BEFORE calculating size
            current_positions = len(self.positions)
            if current_positions >= self.max_positions:
                logger.warning(f"❌ Position limit reached: {current_positions}/{self.max_positions} positions")
                return 0.0
            
            # Check if we have enough capital for this position (simplified for fixed allocation)
            current_balance = self.account.balance
            total_allocated = sum(getattr(pos, 'capital_allocated', capital_per_position) for pos in self.positions.values())
            available_capital = current_balance - total_allocated
            
            if available_capital < capital_per_position:
                logger.warning(f"❌ Insufficient capital: Need ${capital_per_position:.2f}, Available ${available_capital:.2f}")
                return 0.0
            
            # Calculate position size with leverage
            notional_value = capital_per_position * leverage  # Total position value
            quantity = notional_value / price  # Crypto quantity
            
            logger.info(f"💰 CORRECTED Leverage: Capital ${capital_per_position:.2f} ({self.risk_per_trade_pct:.1%} of ${current_balance:.2f}) × {leverage}x = ${notional_value:.2f} notional")
            logger.info(f"💰 Position: {quantity:.6f} {symbol} @ ${price:.4f}")
            logger.info(f"💰 Risk: ${capital_per_position:.2f} (actual capital at risk)")
            logger.info(f"💰 Positions: {current_positions + 1}/{self.max_positions}")
            
            return quantity
            
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return 0.0
    
    async def _calculate_stop_loss(self, entry_price: float, side: str, symbol: str) -> float:
        """Calculate stop loss that limits net losses to exactly $10 per trade (after fees) - FIXED FOR ACTUAL FEE CALCULATION"""
        try:
            # FIXED CALCULATION: Use actual $1000 capital allocation (10% of $10k balance)
            # Target: $10 net loss after actual fees = adjusted gross loss limit
            
            # Get the ACTUAL capital and leverage being used (CORRECTED)
            capital_per_position = self.account.balance * self.risk_per_trade_pct  # 10% of $10k = $1000
            leverage = self.leverage  # 10x leverage
            notional_value = capital_per_position * leverage  # $1000 × 10x = $10,000 notional
            quantity = notional_value / entry_price  # Actual quantity being traded
            
            # CRITICAL FIX: Calculate fees the same way as close_position method
            fee_per_side = 0.0004  # 0.04% taker fee
            entry_fee = quantity * entry_price * fee_per_side
            
            # For stop loss calculation, we need to estimate the exit fee
            # We'll use a slightly conservative approach to ensure we don't exceed $10 net
            target_net_loss = 10.0
            
            # Iterative approach to find the right stop loss price
            # Start with an estimate and refine
            if side == 'LONG':
                # For LONG positions, stop loss is below entry price
                sl_price_estimate = entry_price * 0.998  # Start with ~0.2% below
                for _ in range(10):  # Max 10 iterations
                    exit_fee = quantity * sl_price_estimate * fee_per_side
                    total_fees = entry_fee + exit_fee
                    required_gross_loss = target_net_loss + total_fees
                    sl_price_estimate = entry_price - (required_gross_loss / quantity)
                    
                    # Check convergence
                    test_exit_fee = quantity * sl_price_estimate * fee_per_side
                    test_total_fees = entry_fee + test_exit_fee
                    test_gross_loss = (entry_price - sl_price_estimate) * quantity
                    test_net_loss = test_gross_loss - test_total_fees
                    
                    if abs(test_net_loss - target_net_loss) < 0.01:  # Within 1 cent
                        break
                
                sl_price = sl_price_estimate
                
            else:  # SHORT
                # For SHORT positions, stop loss is above entry price
                sl_price_estimate = entry_price * 1.002  # Start with ~0.2% above
                for _ in range(10):  # Max 10 iterations
                    exit_fee = quantity * sl_price_estimate * fee_per_side
                    total_fees = entry_fee + exit_fee
                    required_gross_loss = target_net_loss + total_fees
                    sl_price_estimate = entry_price + (required_gross_loss / quantity)
                    
                    # Check convergence
                    test_exit_fee = quantity * sl_price_estimate * fee_per_side
                    test_total_fees = entry_fee + test_exit_fee
                    test_gross_loss = (sl_price_estimate - entry_price) * quantity
                    test_net_loss = test_gross_loss - test_total_fees
                    
                    if abs(test_net_loss - target_net_loss) < 0.01:  # Within 1 cent
                        break
                
                sl_price = sl_price_estimate
            
            # Calculate final verification
            final_exit_fee = quantity * sl_price * fee_per_side
            final_total_fees = entry_fee + final_exit_fee
            
            if side == 'LONG':
                final_gross_loss = (entry_price - sl_price) * quantity
                sl_pct = (entry_price - sl_price) / entry_price
            else:
                final_gross_loss = (sl_price - entry_price) * quantity
                sl_pct = (sl_price - entry_price) / entry_price
            
            final_net_loss = final_gross_loss - final_total_fees
            
            logger.info(f"🛡️ PRECISE SL CALCULATION: {side} @ {entry_price:.4f} → SL @ {sl_price:.4f} ({sl_pct:.4%})")
            logger.info(f"🛡️ Position: {quantity:.6f} {symbol}, Capital: ${capital_per_position:.2f}, Leverage: {leverage}x, Notional: ${notional_value:.2f}")
            logger.info(f"🛡️ Fees: Entry ${entry_fee:.2f} + Exit ${final_exit_fee:.2f} = ${final_total_fees:.2f}")
            logger.info(f"🛡️ Result: ${final_gross_loss:.2f} gross - ${final_total_fees:.2f} fees = ${final_net_loss:.2f} net")
            
            # VERIFICATION: Ensure we're within 1 cent of target
            if abs(final_net_loss - target_net_loss) > 0.01:
                logger.warning(f"⚠️ SL CALCULATION WARNING: Expected ${final_net_loss:.2f} net loss ≠ ${target_net_loss:.2f} target")
            else:
                logger.info(f"✅ SL VERIFICATION PASSED: ${final_net_loss:.2f} net loss ≈ ${target_net_loss:.2f} target")
            
            return sl_price
                
        except Exception as e:
            logger.error(f"Error calculating precise stop loss: {e}")
            # Fallback: Use a conservative percentage that should limit to ~$10 net loss
            # For $10k position: $10/$10k = 0.1% movement (conservative)
            fallback_sl_pct = 0.001  # 0.1% (more conservative)
            if side == 'LONG':
                return entry_price * (1 - fallback_sl_pct)
            else:
                return entry_price * (1 + fallback_sl_pct)
    
    async def _calculate_take_profit(self, entry_price: float, side: str, symbol: str) -> float:
        """Calculate take profit - FIXED $10 NET PROFIT TARGET (accounting for fees)"""
        try:
            # FIXED NET PROFIT TARGET: $10 per position AFTER fees
            # With $1000 capital at risk and 10x leverage: $10,000 position size
            # Binance Futures taker fees: 0.04% per side = 0.08% round-trip
            
            # Calculate position details
            current_balance = self.account.balance
            capital_per_position = current_balance * self.risk_per_trade_pct  # $1000
            leverage = self.leverage  # 10x
            notional_value = capital_per_position * leverage  # $10,000
            
            # Fee calculation (Binance Futures taker fees)
            fee_per_side = 0.0004  # 0.04% taker fee
            round_trip_fee_pct = fee_per_side * 2  # 0.08% total
            total_fees_dollars = notional_value * round_trip_fee_pct  # $8
            
            # Target: $10 net profit = $10 + $8 fees = $18 gross profit needed
            target_net_profit = 10.0
            required_gross_profit = target_net_profit + total_fees_dollars
            
            # Calculate required price movement percentage
            required_price_move_pct = required_gross_profit / notional_value
            
            # Calculate final TP price
            if side == 'LONG':
                tp_price = entry_price * (1 + required_price_move_pct)
            else:  # SHORT
                tp_price = entry_price * (1 - required_price_move_pct)
            
            logger.info(f"💰 FIXED $10 NET TP: {side} @ {entry_price:.4f} → TP @ {tp_price:.4f} ({required_price_move_pct:.4%}) [Gross: ${required_gross_profit:.2f}, Fees: ${total_fees_dollars:.2f}, Net: ${target_net_profit:.2f}]")
            return tp_price
                
        except Exception as e:
            logger.error(f"Error calculating fixed take profit: {e}")
            # Fallback to 0.18% TP for $10 net profit (includes fees)
            fixed_tp_pct = 0.0018  # 0.18% to account for fees
            if side == 'LONG':
                return entry_price * (1 + fixed_tp_pct)
            else:
                return entry_price * (1 - fixed_tp_pct)
    
    def _calculate_unrealized_pnl(self) -> float:
        """Calculate total unrealized P&L"""
        return sum(pos.unrealized_pnl for pos in self.positions.values())
    
    async def _check_risk_limits(self, symbol: str, price: float) -> bool:
        """Check if trade passes risk limits - NO LIMITS FOR AGGRESSIVE TRADING"""
        try:
            logger.info(f"🔍 Risk Check for {symbol}: NO LIMITS - All trades allowed")
            
            # NO LIMITS: All trades are allowed
            logger.info(f"✅ PASSED {symbol}: No risk limits - aggressive trading enabled")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error checking risk limits for {symbol}: {e}")
            return True  # Allow trade even on error
    
    def _update_strategy_performance(self, trade: PaperTrade):
        """Update strategy performance metrics"""
        try:
            perf = self.strategy_performance[trade.strategy_type]
            perf['total_trades'] += 1
            perf['total_pnl'] += trade.pnl
            
            if trade.pnl > 0:
                perf['winning_trades'] += 1
            
            perf['win_rate'] = perf['winning_trades'] / perf['total_trades']
            
            # Update average trade duration
            total_duration = perf.get('total_duration', 0) + trade.duration_minutes
            perf['total_duration'] = total_duration
            perf['avg_trade_duration'] = total_duration / perf['total_trades']
            
        except Exception as e:
            logger.error(f"Error updating strategy performance: {e}")
    
    async def _extract_features(self, position: PaperPosition) -> Optional[Dict[str, Any]]:
        """Extract features for ML training"""
        try:
            # Would extract technical indicators, market data, etc.
            features = {
                'symbol': position.symbol,
                'strategy_type': position.strategy_type,
                'confidence_score': position.confidence_score,
                'ml_score': position.ml_score,
                'unrealized_pnl_pct': position.unrealized_pnl_pct,
                'hold_time_minutes': (datetime.utcnow() - position.entry_time).total_seconds() / 60,
                'market_regime': position.market_regime,
                'volatility_regime': position.volatility_regime
            }
            
            return features
            
        except Exception as e:
            logger.error(f"Error extracting features: {e}")
            return None
    
    async def _collect_ml_data(self, trade: PaperTrade):
        """Collect ML training data from completed trade and store in persistent ML service"""
        try:
            # Store in memory for backward compatibility
            ml_data = {
                'trade_id': trade.id,
                'symbol': trade.symbol,
                'strategy_type': trade.strategy_type,
                'confidence_score': trade.confidence_score,
                'ml_score': trade.ml_score,
                'pnl_pct': trade.pnl_pct,
                'duration_minutes': trade.duration_minutes,
                'market_regime': trade.market_regime,
                'volatility_regime': trade.volatility_regime,
                'exit_reason': trade.exit_reason,
                'success': trade.pnl > 0,
                'timestamp': trade.exit_time.isoformat()
            }
            
            self.ml_training_data.append(ml_data)
            
            # Keep only recent data in memory
            if len(self.ml_training_data) > 1000:
                self.ml_training_data = self.ml_training_data[-500:]
            
            # NEW: Store in persistent ML learning service
            try:
                ml_service = await get_ml_learning_service()
                if ml_service:
                    # Extract features for ML learning
                    features = await self._extract_trade_features(trade)
                    
                    # Create TradeOutcome for ML service
                    trade_outcome = TradeOutcome(
                        trade_id=trade.id,
                        symbol=trade.symbol,
                        strategy_type=trade.strategy_type,
                        system_type='paper_trading',
                        confidence_score=trade.confidence_score,
                        ml_score=trade.ml_score,
                        entry_price=trade.entry_price,
                        exit_price=trade.exit_price,
                        pnl_pct=trade.pnl_pct,
                        duration_minutes=trade.duration_minutes,
                        market_regime=trade.market_regime,
                        volatility_regime=trade.volatility_regime,
                        exit_reason=trade.exit_reason,
                        success=trade.pnl > 0,
                        features=features,
                        entry_time=trade.entry_time,
                        exit_time=trade.exit_time
                    )
                    
                    # Store in persistent ML service
                    await ml_service.store_trade_outcome(trade_outcome)
                    logger.info(f"🧠 ML Learning: Stored trade outcome for {trade.symbol} (Paper Trading)")
                    
            except Exception as ml_error:
                logger.error(f"Error storing ML data in persistent service: {ml_error}")
                # Continue without ML service - paper trading should work regardless
            
        except Exception as e:
            logger.error(f"Error collecting ML data: {e}")
    
    async def _extract_trade_features(self, trade: PaperTrade) -> Dict[str, Any]:
        """Extract comprehensive features from a completed trade for ML learning"""
        try:
            features = {
                # Basic trade features
                'entry_price': trade.entry_price,
                'exit_price': trade.exit_price,
                'price_change_pct': ((trade.exit_price - trade.entry_price) / trade.entry_price) * 100,
                'trade_side': trade.side,
                'quantity': trade.quantity,
                'fees': trade.fees,
                
                # Performance features
                'pnl': trade.pnl,
                'pnl_pct': trade.pnl_pct,
                'duration_minutes': trade.duration_minutes,
                'exit_reason': trade.exit_reason,
                
                # Signal quality features
                'confidence_score': trade.confidence_score,
                'ml_score': trade.ml_score,
                'entry_reason': trade.entry_reason,
                
                # Market context features
                'market_regime': trade.market_regime,
                'volatility_regime': trade.volatility_regime,
                
                # Timing features
                'entry_hour': trade.entry_time.hour,
                'entry_day_of_week': trade.entry_time.weekday(),
                'exit_hour': trade.exit_time.hour,
                'exit_day_of_week': trade.exit_time.weekday(),
                
                # Strategy features
                'strategy_type': trade.strategy_type,
                
                # Success indicator
                'was_profitable': trade.pnl > 0,
                'hit_take_profit': trade.exit_reason == 'take_profit',
                'hit_stop_loss': trade.exit_reason == 'stop_loss',
                'manual_exit': trade.exit_reason == 'manual',
                'time_exit': trade.exit_reason == 'max_time'
            }
            
            return features
            
        except Exception as e:
            logger.error(f"Error extracting trade features: {e}")
            return {}
    
    async def _store_position(self, position: PaperPosition):
        """Store position in database"""
        try:
            from sqlalchemy import text
            
            query = text("""
            INSERT INTO flow_trades 
            (symbol, strategy_type, trade_type, entry_price, quantity, 
             confidence_score, ml_score, entry_reason, market_regime, 
             volatility_regime, entry_time)
            VALUES (:symbol, :strategy_type, :trade_type, :entry_price, :quantity, 
                    :confidence_score, :ml_score, :entry_reason, :market_regime, 
                    :volatility_regime, :entry_time)
            """)
            
            with self.db.session_scope() as session:
                session.execute(query, {
                    'symbol': position.symbol,
                    'strategy_type': position.strategy_type,
                    'trade_type': position.side,
                    'entry_price': position.entry_price,
                    'quantity': position.quantity,
                    'confidence_score': position.confidence_score,
                    'ml_score': position.ml_score,
                    'entry_reason': position.entry_reason,
                    'market_regime': position.market_regime,
                    'volatility_regime': position.volatility_regime,
                    'entry_time': position.entry_time
                })
            
            logger.info(f"✅ Position stored in database: {position.symbol}")
            
        except Exception as e:
            logger.error(f"Error storing position in database: {e}")
            # Continue without database - paper trading should work regardless
    
    async def _store_trade(self, trade: PaperTrade):
        """Store completed trade in database"""
        try:
            from sqlalchemy import text
            
            query = text("""
            UPDATE flow_trades 
            SET exit_price = :exit_price, pnl = :pnl, pnl_pct = :pnl_pct, fees = :fees, 
                exit_reason = :exit_reason, duration_minutes = :duration_minutes, exit_time = :exit_time
            WHERE symbol = :symbol AND entry_time = :entry_time AND exit_time IS NULL
            """)
            
            with self.db.session_scope() as session:
                session.execute(query, {
                    'exit_price': trade.exit_price,
                    'pnl': trade.pnl,
                    'pnl_pct': trade.pnl_pct,
                    'fees': trade.fees,
                    'exit_reason': trade.exit_reason,
                    'duration_minutes': trade.duration_minutes,
                    'exit_time': trade.exit_time,
                    'symbol': trade.symbol,
                    'entry_time': trade.entry_time
                })
            
            logger.info(f"✅ Trade updated in database: {trade.symbol}")
            
        except Exception as e:
            logger.error(f"Error storing trade in database: {e}")
            # Continue without database - paper trading should work regardless
    
    async def _store_performance_metrics(self):
        """Store performance metrics in database"""
        try:
            from sqlalchemy import text
            
            query = text("""
            INSERT INTO flow_performance 
            (symbol, strategy_type, total_pnl, trades_count, winning_trades, 
             losing_trades, win_rate, max_drawdown_pct, sharpe_ratio)
            VALUES (:symbol, :strategy_type, :total_pnl, :trades_count, :winning_trades, 
                    :losing_trades, :win_rate, :max_drawdown_pct, :sharpe_ratio)
            """)
            
            with self.db.session_scope() as session:
                session.execute(query, {
                    'symbol': 'PORTFOLIO',
                    'strategy_type': 'paper_trading',
                    'total_pnl': self.account.realized_pnl,
                    'trades_count': self.account.total_trades,
                    'winning_trades': self.account.winning_trades,
                    'losing_trades': self.account.losing_trades,
                    'win_rate': self.account.win_rate,
                    'max_drawdown_pct': self.account.max_drawdown,
                    'sharpe_ratio': self.account.sharpe_ratio
                })
            
            logger.info("✅ Performance metrics stored in database")
            
        except Exception as e:
            logger.error(f"Error storing performance metrics in database: {e}")
            # Continue without database - paper trading should work regardless
    
    async def _load_state(self):
        """Load existing paper trading state"""
        try:
            # Load account state from database or file
            # For now, start fresh each time
            logger.info("Paper trading state loaded")
            
        except Exception as e:
            logger.error(f"Error loading state: {e}")
    
    def get_account_status(self) -> Dict[str, Any]:
        """Get current account status"""
        account_data = asdict(self.account)
        # Keep completed_trades as only completed trades (not including open positions)
        account_data['completed_trades'] = self.account.total_trades
        account_data['active_positions'] = len(self.positions)
        account_data['leverage'] = 10.0  # 10x leverage
        account_data['capital_per_position'] = 1000.0  # Fixed $1000 per position (10% of $10k balance)
        
        return {
            'account': account_data,
            'positions': {pid: asdict(pos) for pid, pos in self.positions.items()},
            'recent_trades': [asdict(t) for t in list(self.trade_history)],  # Return all trades instead of just last 10
            'strategy_performance': dict(self.strategy_performance),
            'is_running': self.is_running
        }
    
    def get_ml_training_data(self) -> List[Dict[str, Any]]:
        """Get collected ML training data"""
        return self.ml_training_data.copy()
    
    async def _detect_market_trend(self, symbol: str) -> str:
        """Detect market trend for dynamic SL/TP calculation"""
        try:
            if not self.exchange_client:
                return 'neutral'  # Default for testing
            
            # Get recent klines (1-hour timeframe for trend detection)
            klines = await self.exchange_client.get_klines(symbol, '1h', limit=50)
            if not klines or len(klines) < 20:
                return 'neutral'
            
            # Extract closing prices
            closes = [float(kline[4]) for kline in klines]  # Close price is index 4
            
            # Calculate moving averages
            sma_5 = sum(closes[-5:]) / 5
            sma_10 = sum(closes[-10:]) / 10
            sma_20 = sum(closes[-20:]) / 20
            
            current_price = closes[-1]
            
            # Calculate trend strength based on price movement
            price_change_5 = (closes[-1] - closes[-5]) / closes[-5]
            price_change_20 = (closes[-1] - closes[-20]) / closes[-20]
            
            # Determine trend strength
            if sma_5 > sma_10 > sma_20 and current_price > sma_5 * 1.01:
                if price_change_20 > 0.05:  # 5% gain over 20 periods
                    return 'strong_uptrend'
                else:
                    return 'uptrend'
            elif sma_5 < sma_10 < sma_20 and current_price < sma_5 * 0.99:
                if price_change_20 < -0.05:  # 5% loss over 20 periods
                    return 'strong_downtrend'
                else:
                    return 'downtrend'
            elif sma_5 > sma_10 and current_price > sma_10:
                return 'uptrend'
            elif sma_5 < sma_10 and current_price < sma_10:
                return 'downtrend'
            else:
                return 'neutral'
                
        except Exception as e:
            logger.error(f"Error detecting market trend for {symbol}: {e}")
            return 'neutral'
    
    async def _calculate_volatility(self, symbol: str) -> float:
        """Calculate volatility for dynamic SL/TP adjustment"""
        try:
            if not self.exchange_client:
                return 1.0  # Default volatility for testing
            
            # Get recent klines (15-minute timeframe for volatility)
            klines = await self.exchange_client.get_klines(symbol, '15m', limit=20)
            if not klines or len(klines) < 10:
                return 1.0
            
            # Calculate price changes
            price_changes = []
            for i in range(1, len(klines)):
                prev_close = float(klines[i-1][4])
                curr_close = float(klines[i][4])
                change_pct = abs(curr_close - prev_close) / prev_close
                price_changes.append(change_pct)
            
            # Calculate average volatility
            avg_volatility = sum(price_changes) / len(price_changes)
            
            # Scale to reasonable range (0.5 to 3.0)
            scaled_volatility = max(0.5, min(3.0, avg_volatility * 100))
            
            return scaled_volatility
            
        except Exception as e:
            logger.error(f"Error calculating volatility for {symbol}: {e}")
            return 1.0
    
    async def _calculate_momentum(self, symbol: str) -> float:
        """Calculate momentum for dynamic TP adjustment"""
        try:
            if not self.exchange_client:
                return 50.0  # Neutral momentum for testing
            
            # Get recent klines (5-minute timeframe for momentum)
            klines = await self.exchange_client.get_klines(symbol, '5m', limit=14)
            if not klines or len(klines) < 14:
                return 50.0
            
            # Calculate RSI-like momentum indicator
            closes = [float(kline[4]) for kline in klines]
            
            gains = []
            losses = []
            
            for i in range(1, len(closes)):
                change = closes[i] - closes[i-1]
                if change > 0:
                    gains.append(change)
                    losses.append(0)
                else:
                    gains.append(0)
                    losses.append(abs(change))
            
            if len(gains) == 0:
                return 50.0
            
            avg_gain = sum(gains) / len(gains)
            avg_loss = sum(losses) / len(losses)
            
            if avg_loss == 0:
                return 100.0  # Maximum momentum
            
            # Prevent division by zero and ensure reasonable RSI values
            if avg_gain == 0:
                return 0.0  # No upward momentum
            
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            # For trending markets, boost momentum based on trend direction
            market_trend = await self._detect_market_trend(symbol)
            if market_trend == 'strong_uptrend':
                rsi = max(rsi, 70.0)  # Ensure strong momentum for strong uptrends
            elif market_trend == 'strong_downtrend':
                rsi = min(rsi, 30.0)  # Ensure weak momentum for strong downtrends (good for shorts)
            
            return rsi
            
        except Exception as e:
            logger.error(f"Error calculating momentum for {symbol}: {e}")
            return 50.0
    
    async def _validate_support_resistance_holding(self, symbol: str, entry_price: float, side: str) -> Dict[str, Any]:
        """
        CRITICAL: Validate and SCORE support/resistance levels before trading
        This implements comprehensive level scoring based on multiple factors
        """
        try:
            # Get recent price action data (extended for better analysis)
            klines = await self.exchange_client.get_klines(symbol, '5m', limit=50) if self.exchange_client else None
            
            if not klines or len(klines) < 20:
                # No data available - return low score
                return {
                    'is_holding': False,
                    'strength': 'unknown',
                    'level_score': 0.0,
                    'reason': 'insufficient_data_for_scoring'
                }
            
            # Extract price data
            highs = [float(kline[2]) for kline in klines]
            lows = [float(kline[3]) for kline in klines]
            closes = [float(kline[4]) for kline in klines]
            volumes = [float(kline[5]) for kline in klines]
            opens = [float(kline[1]) for kline in klines]
            
            current_price = closes[-1]
            tolerance = entry_price * 0.005  # 0.5% tolerance around level
            
            if side == 'LONG':
                # Score SUPPORT level
                level_analysis = await self._score_support_level(entry_price, current_price, highs, lows, closes, volumes, opens, tolerance)
            else:
                # Score RESISTANCE level
                level_analysis = await self._score_resistance_level(entry_price, current_price, highs, lows, closes, volumes, opens, tolerance)
            
            # Apply minimum score threshold
            min_score_threshold = 70.0  # Only trade levels with 70+ score
            high_score_threshold = 85.0  # High confidence levels
            
            if level_analysis['level_score'] < min_score_threshold:
                return {
                    'is_holding': False,
                    'strength': 'weak',
                    'level_score': level_analysis['level_score'],
                    'reason': f'level_score_too_low_{level_analysis["level_score"]:.1f}_below_{min_score_threshold}'
                }
            elif level_analysis['level_score'] >= high_score_threshold:
                return {
                    'is_holding': True,
                    'strength': 'strong',
                    'level_score': level_analysis['level_score'],
                    'reason': f'high_quality_level_score_{level_analysis["level_score"]:.1f}'
                }
            else:
                return {
                    'is_holding': True,
                    'strength': 'moderate',
                    'level_score': level_analysis['level_score'],
                    'reason': f'acceptable_level_score_{level_analysis["level_score"]:.1f}'
                }
                
        except Exception as e:
            logger.error(f"Error validating/scoring support/resistance for {symbol}: {e}")
            # Default to rejection on error
            return {
                'is_holding': False,
                'strength': 'error',
                'level_score': 0.0,
                'reason': f'scoring_error_{str(e)[:50]}'
            }
    
    async def _validate_support_level(self, support_price: float, current_price: float, 
                                    highs: List[float], lows: List[float], closes: List[float], 
                                    volumes: List[float], tolerance: float) -> Dict[str, Any]:
        """Validate that a support level is actually holding"""
        try:
            # Check if price is currently near support
            if current_price > support_price + tolerance:
                return {
                    'is_holding': False,
                    'strength': 'weak',
                    'reason': f'price_too_far_above_support_{current_price:.2f}_vs_{support_price:.2f}'
                }
            
            # Look for recent touches and bounces
            recent_touches = 0
            successful_bounces = 0
            failed_breaks = 0
            
            for i in range(len(lows)):
                low = lows[i]
                high = highs[i]
                close = closes[i]
                
                # Check if this candle touched the support level
                if low <= support_price + tolerance and low >= support_price - tolerance:
                    recent_touches += 1
                    
                    # Check if it bounced (closed above support with good wick)
                    if close > support_price + (tolerance * 0.5):  # Closed above support
                        if high > support_price + tolerance:  # Had upward movement
                            successful_bounces += 1
                        else:
                            # Weak bounce - just barely held
                            pass
                    else:
                        # Failed to bounce properly
                        failed_breaks += 1
                
                # Check for clean breaks below support
                elif low < support_price - tolerance:
                    failed_breaks += 1
            
            # Analyze volume on recent touches
            avg_volume = sum(volumes) / len(volumes)
            recent_volume = volumes[-3:] if len(volumes) >= 3 else volumes  # Last 3 candles
            volume_strength = sum(recent_volume) / len(recent_volume) / avg_volume
            
            # VALIDATION LOGIC
            if failed_breaks > 0:
                return {
                    'is_holding': False,
                    'strength': 'broken',
                    'reason': f'support_broken_{failed_breaks}_times_recently'
                }
            
            if recent_touches == 0:
                # No recent test - could be strong or untested
                if current_price > support_price + (tolerance * 2):
                    return {
                        'is_holding': True,
                        'strength': 'untested',
                        'reason': 'support_untested_price_well_above'
                    }
                else:
                    return {
                        'is_holding': True,
                        'strength': 'approaching',
                        'reason': 'approaching_untested_support'
                    }
            
            # Calculate bounce success rate
            bounce_rate = successful_bounces / recent_touches if recent_touches > 0 else 0
            
            if bounce_rate >= 0.8 and volume_strength > 1.2:  # 80%+ bounce rate with good volume
                return {
                    'is_holding': True,
                    'strength': 'strong',
                    'reason': f'strong_support_{successful_bounces}/{recent_touches}_bounces_good_volume'
                }
            elif bounce_rate >= 0.6:  # 60%+ bounce rate
                return {
                    'is_holding': True,
                    'strength': 'moderate',
                    'reason': f'moderate_support_{successful_bounces}/{recent_touches}_bounces'
                }
            else:
                return {
                    'is_holding': False,
                    'strength': 'weak',
                    'reason': f'weak_support_low_bounce_rate_{bounce_rate:.1%}'
                }
                
        except Exception as e:
            logger.error(f"Error validating support level: {e}")
            return {
                'is_holding': False,
                'strength': 'error',
                'reason': f'support_validation_error'
            }
    
    async def _validate_resistance_level(self, resistance_price: float, current_price: float,
                                       highs: List[float], lows: List[float], closes: List[float],
                                       volumes: List[float], tolerance: float) -> Dict[str, Any]:
        """Validate that a resistance level is actually holding"""
        try:
            # Check if price is currently near resistance
            if current_price < resistance_price - tolerance:
                return {
                    'is_holding': False,
                    'strength': 'weak',
                    'reason': f'price_too_far_below_resistance_{current_price:.2f}_vs_{resistance_price:.2f}'
                }
            
            # Look for recent touches and rejections
            recent_touches = 0
            successful_rejections = 0
            failed_breaks = 0
            
            for i in range(len(highs)):
                high = highs[i]
                low = lows[i]
                close = closes[i]
                
                # Check if this candle touched the resistance level
                if high >= resistance_price - tolerance and high <= resistance_price + tolerance:
                    recent_touches += 1
                    
                    # Check if it was rejected (closed below resistance with good wick)
                    if close < resistance_price - (tolerance * 0.5):  # Closed below resistance
                        if low < resistance_price - tolerance:  # Had downward movement
                            successful_rejections += 1
                        else:
                            # Weak rejection - just barely held
                            pass
                    else:
                        # Failed to reject properly
                        failed_breaks += 1
                
                # Check for clean breaks above resistance
                elif high > resistance_price + tolerance:
                    failed_breaks += 1
            
            # Analyze volume on recent touches
            avg_volume = sum(volumes) / len(volumes)
            recent_volume = volumes[-3:] if len(volumes) >= 3 else volumes
            volume_strength = sum(recent_volume) / len(recent_volume) / avg_volume
            
            # VALIDATION LOGIC
            if failed_breaks > 0:
                return {
                    'is_holding': False,
                    'strength': 'broken',
                    'reason': f'resistance_broken_{failed_breaks}_times_recently'
                }
            
            if recent_touches == 0:
                # No recent test - could be strong or untested
                if current_price < resistance_price - (tolerance * 2):
                    return {
                        'is_holding': True,
                        'strength': 'untested',
                        'reason': 'resistance_untested_price_well_below'
                    }
                else:
                    return {
                        'is_holding': True,
                        'strength': 'approaching',
                        'reason': 'approaching_untested_resistance'
                    }
            
            # Calculate rejection success rate
            rejection_rate = successful_rejections / recent_touches if recent_touches > 0 else 0
            
            if rejection_rate >= 0.8 and volume_strength > 1.2:  # 80%+ rejection rate with good volume
                return {
                    'is_holding': True,
                    'strength': 'strong',
                    'reason': f'strong_resistance_{successful_rejections}/{recent_touches}_rejections_good_volume'
                }
            elif rejection_rate >= 0.6:  # 60%+ rejection rate
                return {
                    'is_holding': True,
                    'strength': 'moderate',
                    'reason': f'moderate_resistance_{successful_rejections}/{recent_touches}_rejections'
                }
            else:
                return {
                    'is_holding': False,
                    'strength': 'weak',
                    'reason': f'weak_resistance_low_rejection_rate_{rejection_rate:.1%}'
                }
                
        except Exception as e:
            logger.error(f"Error validating resistance level: {e}")
            return {
                'is_holding': False,
                'strength': 'error',
                'reason': f'resistance_validation_error'
            }
    
    async def _check_level_breakdown_exit(self, position: PaperPosition, current_price: float) -> Optional[str]:
        """
        CRITICAL: Check for immediate exit when support/resistance levels break
        This implements the "Exit-on-Trend-Reversal" mechanism
        FIXED: Use same threshold as stop loss to prevent massive losses
        """
        try:
            # FIXED: Use fee-corrected threshold same as stop loss (0.18% for $10 net loss)
            # This prevents level breakdown from overriding stop loss protection
            breakdown_threshold = 0.0018  # 0.18% = same as stop loss for $10 net loss
            
            if position.side == 'LONG':
                # Check for SUPPORT BREAKDOWN
                support_level = position.entry_price  # Assume entry was near support
                breakdown_price = support_level * (1 - breakdown_threshold)
                
                if current_price < breakdown_price:
                    logger.warning(f"🚨 SUPPORT BREAKDOWN: {position.symbol} LONG @ {current_price:.4f} broke below {breakdown_price:.4f}")
                    logger.warning(f"🚨 Entry was @ {position.entry_price:.4f}, now {((current_price - position.entry_price) / position.entry_price * 100):+.2f}%")
                    return "support_breakdown"
                    
            else:  # SHORT position
                # Check for RESISTANCE BREAKOUT
                resistance_level = position.entry_price  # Assume entry was near resistance
                breakout_price = resistance_level * (1 + breakdown_threshold)
                
                if current_price > breakout_price:
                    logger.warning(f"🚨 RESISTANCE BREAKOUT: {position.symbol} SHORT @ {current_price:.4f} broke above {breakout_price:.4f}")
                    logger.warning(f"🚨 Entry was @ {position.entry_price:.4f}, now {((position.entry_price - current_price) / position.entry_price * 100):+.2f}%")
                    return "resistance_breakout"
            
            return None  # No breakdown detected
            
        except Exception as e:
            logger.error(f"Error checking level breakdown for {position.symbol}: {e}")
            return None
    
    async def _check_trend_reversal_exit(self, position: PaperPosition, current_price: float) -> Optional[str]:
        """
        Check for trend reversal that invalidates the trade thesis
        """
        try:
            # Get current market trend
            current_trend = await self._detect_market_trend(position.symbol)
            
            # Check for trend reversal against position
            if position.side == 'LONG':
                # LONG position in newly formed downtrend = exit
                if current_trend == 'strong_downtrend':
                    # Additional confirmation: price below entry by significant margin
                    price_decline = (position.entry_price - current_price) / position.entry_price
                    if price_decline > 0.005:  # 0.5% decline + strong downtrend = exit
                        logger.warning(f"🔄 TREND REVERSAL: {position.symbol} LONG in strong downtrend, price down {price_decline:.2%}")
                        return "trend_reversal_downtrend"
                        
            else:  # SHORT position
                # SHORT position in newly formed uptrend = exit
                if current_trend == 'strong_uptrend':
                    # Additional confirmation: price above entry by significant margin
                    price_increase = (current_price - position.entry_price) / position.entry_price
                    if price_increase > 0.005:  # 0.5% increase + strong uptrend = exit
                        logger.warning(f"🔄 TREND REVERSAL: {position.symbol} SHORT in strong uptrend, price up {price_increase:.2%}")
                        return "trend_reversal_uptrend"
            
            return None  # No trend reversal exit needed
            
        except Exception as e:
            logger.error(f"Error checking trend reversal for {position.symbol}: {e}")
            return None
    
    async def _get_ml_signal_recommendation(self, symbol: str, side: str, strategy_type: str, base_confidence: float) -> Dict[str, Any]:
        """
        CRITICAL: Get ML-based signal recommendation to filter entry signals
        This implements ML confidence filtering at signal generation time
        """
        try:
            # ML confidence thresholds
            min_confidence_threshold = 0.6  # 60% minimum confidence
            high_confidence_threshold = 0.8  # 80% high confidence
            
            # Get ML service for historical analysis
            ml_service = await get_ml_learning_service()
            
            if ml_service:
                # Get ML recommendation based on historical performance
                try:
                    # Analyze recent performance for this symbol/strategy combination
                    recent_performance = await self._analyze_recent_ml_performance(symbol, strategy_type, side)
                    
                    # Calculate ML confidence based on recent performance
                    ml_confidence = self._calculate_ml_confidence(recent_performance, base_confidence)
                    
                    logger.info(f"🧠 ML Analysis for {symbol} {side}: Recent performance {recent_performance['win_rate']:.1%}, ML confidence {ml_confidence:.3f}")
                    
                except Exception as ml_error:
                    logger.warning(f"ML service error, using fallback: {ml_error}")
                    ml_confidence = base_confidence  # Fallback to base confidence
            else:
                # No ML service available - use enhanced heuristics
                ml_confidence = await self._calculate_heuristic_confidence(symbol, side, strategy_type, base_confidence)
            
            # Apply confidence thresholds
            if ml_confidence < min_confidence_threshold:
                return {
                    'should_trade': False,
                    'ml_confidence': ml_confidence,
                    'threshold': min_confidence_threshold,
                    'reason': f'ml_confidence_too_low_{ml_confidence:.3f}_below_{min_confidence_threshold:.3f}'
                }
            
            # Additional filters based on recent trading history
            recent_trades_filter = self._check_recent_trades_performance(symbol, strategy_type)
            if not recent_trades_filter['should_trade']:
                return {
                    'should_trade': False,
                    'ml_confidence': ml_confidence,
                    'threshold': min_confidence_threshold,
                    'reason': f'recent_performance_filter_{recent_trades_filter["reason"]}'
                }
            
            # Check for symbol-specific performance
            symbol_performance = self._get_symbol_performance(symbol)
            if symbol_performance['total_trades'] >= 5 and symbol_performance['win_rate'] < 0.3:
                # Poor performance on this symbol - require higher confidence
                if ml_confidence < high_confidence_threshold:
                    return {
                        'should_trade': False,
                        'ml_confidence': ml_confidence,
                        'threshold': high_confidence_threshold,
                        'reason': f'poor_symbol_performance_requires_high_confidence_{symbol_performance["win_rate"]:.1%}'
                    }
            
            # All filters passed
            return {
                'should_trade': True,
                'ml_confidence': ml_confidence,
                'threshold': min_confidence_threshold,
                'reason': f'ml_approved_confidence_{ml_confidence:.3f}'
            }
            
        except Exception as e:
            logger.error(f"Error in ML signal recommendation: {e}")
            # Conservative fallback - reject low confidence signals
            if base_confidence < 0.7:
                return {
                    'should_trade': False,
                    'ml_confidence': base_confidence,
                    'threshold': 0.7,
                    'reason': f'ml_error_conservative_fallback'
                }
            else:
                return {
                    'should_trade': True,
                    'ml_confidence': base_confidence,
                    'threshold': 0.7,
                    'reason': f'ml_error_high_confidence_approved'
                }
    
    async def _analyze_recent_ml_performance(self, symbol: str, strategy_type: str, side: str) -> Dict[str, Any]:
        """Analyze recent ML performance for this symbol/strategy combination"""
        try:
            # Look at recent trades for this symbol/strategy
            recent_trades = [
                t for t in self.completed_trades[-50:]  # Last 50 trades
                if t.symbol == symbol and t.strategy_type == strategy_type
            ]
            
            if len(recent_trades) < 3:
                # Not enough data - return neutral performance
                return {
                    'total_trades': len(recent_trades),
                    'win_rate': 0.5,
                    'avg_pnl_pct': 0.0,
                    'confidence': 'insufficient_data'
                }
            
            # Calculate performance metrics
            winning_trades = sum(1 for t in recent_trades if t.pnl > 0)
            win_rate = winning_trades / len(recent_trades)
            avg_pnl_pct = sum(t.pnl_pct for t in recent_trades) / len(recent_trades)
            
            # Side-specific analysis
            side_trades = [t for t in recent_trades if t.side == side]
            side_win_rate = sum(1 for t in side_trades if t.pnl > 0) / len(side_trades) if side_trades else 0.5
            
            return {
                'total_trades': len(recent_trades),
                'win_rate': win_rate,
                'side_win_rate': side_win_rate,
                'avg_pnl_pct': avg_pnl_pct,
                'confidence': 'sufficient_data'
            }
            
        except Exception as e:
            logger.error(f"Error analyzing recent ML performance: {e}")
            return {
                'total_trades': 0,
                'win_rate': 0.5,
                'avg_pnl_pct': 0.0,
                'confidence': 'error'
            }
    
    def _calculate_ml_confidence(self, performance: Dict[str, Any], base_confidence: float) -> float:
        """Calculate ML confidence based on recent performance"""
        try:
            # Start with base confidence
            ml_confidence = base_confidence
            
            # Adjust based on recent performance
            if performance['total_trades'] >= 5:
                win_rate = performance['win_rate']
                side_win_rate = performance['side_win_rate']
                avg_pnl = performance['avg_pnl_pct']
                
                # Win rate adjustment
                if win_rate > 0.7:  # Good win rate
                    ml_confidence *= 1.2
                elif win_rate < 0.4:  # Poor win rate
                    ml_confidence *= 0.7
                
                # Side-specific adjustment
                if side_win_rate > 0.6:
                    ml_confidence *= 1.1
                elif side_win_rate < 0.4:
                    ml_confidence *= 0.8
                
                # Average P&L adjustment
                if avg_pnl > 0.01:  # Profitable on average
                    ml_confidence *= 1.1
                elif avg_pnl < -0.005:  # Losing on average
                    ml_confidence *= 0.8
            
            # Cap confidence between 0.1 and 0.95
            ml_confidence = max(0.1, min(0.95, ml_confidence))
            
            return ml_confidence
            
        except Exception as e:
            logger.error(f"Error calculating ML confidence: {e}")
            return base_confidence
    
    async def _calculate_heuristic_confidence(self, symbol: str, side: str, strategy_type: str, base_confidence: float) -> float:
        """Calculate confidence using heuristics when ML service unavailable"""
        try:
            # Start with base confidence
            heuristic_confidence = base_confidence
            
            # Market condition adjustments
            market_trend = await self._detect_market_trend(symbol)
            
            # Trend alignment bonus
            if (market_trend in ['strong_uptrend', 'uptrend'] and side == 'LONG') or \
               (market_trend in ['strong_downtrend', 'downtrend'] and side == 'SHORT'):
                heuristic_confidence *= 1.2  # Trend following bonus
            elif (market_trend in ['strong_downtrend', 'downtrend'] and side == 'LONG') or \
                 (market_trend in ['strong_uptrend', 'uptrend'] and side == 'SHORT'):
                heuristic_confidence *= 0.7  # Counter-trend penalty
            
            # Volatility adjustment
            volatility = await self._calculate_volatility(symbol)
            if volatility > 2.5:  # Very high volatility
                heuristic_confidence *= 0.8  # Reduce confidence in chaotic markets
            elif volatility < 0.8:  # Low volatility
                heuristic_confidence *= 1.1  # Increase confidence in stable markets
            
            # Time-based adjustments (avoid trading during low-activity periods)
            current_hour = datetime.utcnow().hour
            if 2 <= current_hour <= 6:  # Low activity hours
                heuristic_confidence *= 0.9
            elif 8 <= current_hour <= 16:  # High activity hours
                heuristic_confidence *= 1.1
            
            # Cap confidence
            heuristic_confidence = max(0.1, min(0.95, heuristic_confidence))
            
            return heuristic_confidence
            
        except Exception as e:
            logger.error(f"Error calculating heuristic confidence: {e}")
            return base_confidence
    
    def _check_recent_trades_performance(self, symbol: str, strategy_type: str) -> Dict[str, Any]:
        """Check recent trades performance for additional filtering"""
        try:
            # Look at very recent trades (last 10)
            recent_trades = [
                t for t in self.completed_trades[-10:]
                if t.symbol == symbol and t.strategy_type == strategy_type
            ]
            
            if len(recent_trades) < 3:
                return {'should_trade': True, 'reason': 'insufficient_recent_data'}
            
            # Check for consecutive losses
            last_3_trades = recent_trades[-3:]
            consecutive_losses = all(t.pnl < 0 for t in last_3_trades)
            
            if consecutive_losses:
                return {'should_trade': False, 'reason': 'three_consecutive_losses'}
            
            # Check recent win rate
            recent_wins = sum(1 for t in recent_trades if t.pnl > 0)
            recent_win_rate = recent_wins / len(recent_trades)
            
            if recent_win_rate < 0.2:  # Less than 20% win rate recently
                return {'should_trade': False, 'reason': f'poor_recent_win_rate_{recent_win_rate:.1%}'}
            
            return {'should_trade': True, 'reason': 'recent_performance_acceptable'}
            
        except Exception as e:
            logger.error(f"Error checking recent trades performance: {e}")
            return {'should_trade': True, 'reason': 'error_defaulting_to_trade'}
    
    def _get_symbol_performance(self, symbol: str) -> Dict[str, Any]:
        """Get overall performance statistics for a specific symbol"""
        try:
            symbol_trades = [t for t in self.completed_trades if t.symbol == symbol]
            
            if not symbol_trades:
                return {
                    'total_trades': 0,
                    'win_rate': 0.5,
                    'avg_pnl_pct': 0.0,
                    'total_pnl': 0.0
                }
            
            winning_trades = sum(1 for t in symbol_trades if t.pnl > 0)
            win_rate = winning_trades / len(symbol_trades)
            avg_pnl_pct = sum(t.pnl_pct for t in symbol_trades) / len(symbol_trades)
            total_pnl = sum(t.pnl for t in symbol_trades)
            
            return {
                'total_trades': len(symbol_trades),
                'win_rate': win_rate,
                'avg_pnl_pct': avg_pnl_pct,
                'total_pnl': total_pnl
            }
            
        except Exception as e:
            logger.error(f"Error getting symbol performance: {e}")
            return {
                'total_trades': 0,
                'win_rate': 0.5,
                'avg_pnl_pct': 0.0,
                'total_pnl': 0.0
            }
    
    async def _score_support_level(self, support_price: float, current_price: float,
                                  highs: List[float], lows: List[float], closes: List[float],
                                  volumes: List[float], opens: List[float], tolerance: float) -> Dict[str, Any]:
        """
        COMPREHENSIVE SUPPORT LEVEL SCORING
        Scores support levels based on multiple factors to ensure only highest quality trades
        """
        try:
            score = 0.0
            max_score = 100.0
            scoring_details = []
            
            # FACTOR 1: Historical Bounces (30 points max)
            bounce_score, bounce_details = self._score_historical_bounces(support_price, highs, lows, closes, tolerance)
            score += bounce_score
            scoring_details.extend(bounce_details)
            
            # FACTOR 2: Reaction Strength (25 points max)
            reaction_score, reaction_details = self._score_reaction_strength(support_price, highs, lows, closes, opens, tolerance)
            score += reaction_score
            scoring_details.extend(reaction_details)
            
            # FACTOR 3: Volume Confirmation (25 points max)
            volume_score, volume_details = self._score_volume_around_level(support_price, lows, volumes, tolerance)
            score += volume_score
            scoring_details.extend(volume_details)
            
            # FACTOR 4: Approach Slope (20 points max)
            slope_score, slope_details = self._score_approach_slope(support_price, closes, 'support')
            score += slope_score
            scoring_details.extend(slope_details)
            
            # Cap score at maximum
            final_score = min(score, max_score)
            
            logger.info(f"📊 SUPPORT LEVEL SCORE: {final_score:.1f}/100 for {support_price:.2f}")
            for detail in scoring_details:
                logger.info(f"   {detail}")
            
            return {
                'level_score': final_score,
                'scoring_details': scoring_details,
                'bounce_score': bounce_score,
                'reaction_score': reaction_score,
                'volume_score': volume_score,
                'slope_score': slope_score
            }
            
        except Exception as e:
            logger.error(f"Error scoring support level: {e}")
            return {'level_score': 0.0, 'scoring_details': ['error_in_scoring']}
    
    async def _score_resistance_level(self, resistance_price: float, current_price: float,
                                     highs: List[float], lows: List[float], closes: List[float],
                                     volumes: List[float], opens: List[float], tolerance: float) -> Dict[str, Any]:
        """
        COMPREHENSIVE RESISTANCE LEVEL SCORING
        Scores resistance levels based on multiple factors to ensure only highest quality trades
        """
        try:
            score = 0.0
            max_score = 100.0
            scoring_details = []
            
            # FACTOR 1: Historical Rejections (30 points max)
            rejection_score, rejection_details = self._score_historical_rejections(resistance_price, highs, lows, closes, tolerance)
            score += rejection_score
            scoring_details.extend(rejection_details)
            
            # FACTOR 2: Reaction Strength (25 points max)
            reaction_score, reaction_details = self._score_reaction_strength(resistance_price, highs, lows, closes, opens, tolerance, level_type='resistance')
            score += reaction_score
            scoring_details.extend(reaction_details)
            
            # FACTOR 3: Volume Confirmation (25 points max)
            volume_score, volume_details = self._score_volume_around_level(resistance_price, highs, volumes, tolerance, level_type='resistance')
            score += volume_score
            scoring_details.extend(volume_details)
            
            # FACTOR 4: Approach Slope (20 points max)
            slope_score, slope_details = self._score_approach_slope(resistance_price, closes, 'resistance')
            score += slope_score
            scoring_details.extend(slope_details)
            
            # Cap score at maximum
            final_score = min(score, max_score)
            
            logger.info(f"📊 RESISTANCE LEVEL SCORE: {final_score:.1f}/100 for {resistance_price:.2f}")
            for detail in scoring_details:
                logger.info(f"   {detail}")
            
            return {
                'level_score': final_score,
                'scoring_details': scoring_details,
                'rejection_score': rejection_score,
                'reaction_score': reaction_score,
                'volume_score': volume_score,
                'slope_score': slope_score
            }
            
        except Exception as e:
            logger.error(f"Error scoring resistance level: {e}")
            return {'level_score': 0.0, 'scoring_details': ['error_in_scoring']}
    
    def _score_historical_bounces(self, support_price: float, highs: List[float], lows: List[float], 
                                 closes: List[float], tolerance: float) -> tuple[float, List[str]]:
        """Score based on historical bounces at support level"""
        try:
            touches = 0
            successful_bounces = 0
            recent_touches = 0  # Last 10 candles
            details = []
            
            for i, (high, low, close) in enumerate(zip(highs, lows, closes)):
                # Check if candle touched support
                if low <= support_price + tolerance and low >= support_price - tolerance:
                    touches += 1
                    if i >= len(lows) - 10:  # Recent touch
                        recent_touches += 1
                    
                    # Check for successful bounce
                    if close > support_price + (tolerance * 0.3) and high > support_price + tolerance:
                        successful_bounces += 1
            
            # Calculate bounce rate
            bounce_rate = successful_bounces / touches if touches > 0 else 0
            
            # Scoring logic (30 points max)
            if touches == 0:
                score = 15.0  # Untested level - moderate score
                details.append(f"📍 Untested support level (+15 pts)")
            elif bounce_rate >= 0.8 and touches >= 3:
                score = 30.0  # Excellent bounce rate with multiple tests
                details.append(f"🏆 Excellent: {successful_bounces}/{touches} bounces ({bounce_rate:.1%}) (+30 pts)")
            elif bounce_rate >= 0.6 and touches >= 2:
                score = 22.0  # Good bounce rate
                details.append(f"✅ Good: {successful_bounces}/{touches} bounces ({bounce_rate:.1%}) (+22 pts)")
            elif bounce_rate >= 0.4:
                score = 12.0  # Moderate bounce rate
                details.append(f"⚠️ Moderate: {successful_bounces}/{touches} bounces ({bounce_rate:.1%}) (+12 pts)")
            else:
                score = 0.0  # Poor bounce rate
                details.append(f"❌ Poor: {successful_bounces}/{touches} bounces ({bounce_rate:.1%}) (+0 pts)")
            
            # Bonus for recent activity
            if recent_touches > 0:
                score += 5.0
                details.append(f"🔥 Recent activity: {recent_touches} recent touches (+5 pts)")
            
            return min(score, 30.0), details
            
        except Exception as e:
            return 0.0, [f"Error scoring bounces: {e}"]
    
    def _score_historical_rejections(self, resistance_price: float, highs: List[float], lows: List[float],
                                   closes: List[float], tolerance: float) -> tuple[float, List[str]]:
        """Score based on historical rejections at resistance level"""
        try:
            touches = 0
            successful_rejections = 0
            recent_touches = 0  # Last 10 candles
            details = []
            
            for i, (high, low, close) in enumerate(zip(highs, lows, closes)):
                # Check if candle touched resistance
                if high >= resistance_price - tolerance and high <= resistance_price + tolerance:
                    touches += 1
                    if i >= len(highs) - 10:  # Recent touch
                        recent_touches += 1
                    
                    # Check for successful rejection
                    if close < resistance_price - (tolerance * 0.3) and low < resistance_price - tolerance:
                        successful_rejections += 1
            
            # Calculate rejection rate
            rejection_rate = successful_rejections / touches if touches > 0 else 0
            
            # Scoring logic (30 points max)
            if touches == 0:
                score = 15.0  # Untested level - moderate score
                details.append(f"📍 Untested resistance level (+15 pts)")
            elif rejection_rate >= 0.8 and touches >= 3:
                score = 30.0  # Excellent rejection rate with multiple tests
                details.append(f"🏆 Excellent: {successful_rejections}/{touches} rejections ({rejection_rate:.1%}) (+30 pts)")
            elif rejection_rate >= 0.6 and touches >= 2:
                score = 22.0  # Good rejection rate
                details.append(f"✅ Good: {successful_rejections}/{touches} rejections ({rejection_rate:.1%}) (+22 pts)")
            elif rejection_rate >= 0.4:
                score = 12.0  # Moderate rejection rate
                details.append(f"⚠️ Moderate: {successful_rejections}/{touches} rejections ({rejection_rate:.1%}) (+12 pts)")
            else:
                score = 0.0  # Poor rejection rate
                details.append(f"❌ Poor: {successful_rejections}/{touches} rejections ({rejection_rate:.1%}) (+0 pts)")
            
            # Bonus for recent activity
            if recent_touches > 0:
                score += 5.0
                details.append(f"🔥 Recent activity: {recent_touches} recent touches (+5 pts)")
            
            return min(score, 30.0), details
            
        except Exception as e:
            return 0.0, [f"Error scoring rejections: {e}"]
    
    def _score_reaction_strength(self, level_price: float, highs: List[float], lows: List[float],
                               closes: List[float], opens: List[float], tolerance: float,
                               level_type: str = 'support') -> tuple[float, List[str]]:
        """Score based on strength of reactions at the level"""
        try:
            strong_reactions = 0
            total_reactions = 0
            avg_reaction_strength = 0.0
            details = []
            
            for i, (high, low, close, open_price) in enumerate(zip(highs, lows, closes, opens)):
                if level_type == 'support':
                    # Check if candle touched support
                    if low <= level_price + tolerance and low >= level_price - tolerance:
                        total_reactions += 1
                        # Calculate reaction strength (how far it bounced)
                        reaction_strength = (high - low) / low * 100  # Percentage wick size
                        avg_reaction_strength += reaction_strength
                        
                        if reaction_strength > 1.0:  # Strong reaction (>1% wick)
                            strong_reactions += 1
                else:  # resistance
                    # Check if candle touched resistance
                    if high >= level_price - tolerance and high <= level_price + tolerance:
                        total_reactions += 1
                        # Calculate reaction strength (how far it rejected)
                        reaction_strength = (high - low) / high * 100  # Percentage wick size
                        avg_reaction_strength += reaction_strength
                        
                        if reaction_strength > 1.0:  # Strong reaction (>1% wick)
                            strong_reactions += 1
            
            if total_reactions > 0:
                avg_reaction_strength /= total_reactions
                strong_reaction_rate = strong_reactions / total_reactions
            else:
                avg_reaction_strength = 0.0
                strong_reaction_rate = 0.0
            
            # Scoring logic (25 points max)
            if total_reactions == 0:
                score = 12.0  # No reactions to score - neutral
                details.append(f"📍 No reactions to analyze (+12 pts)")
            elif avg_reaction_strength >= 2.0 and strong_reaction_rate >= 0.7:
                score = 25.0  # Very strong reactions
                details.append(f"💪 Very strong reactions: {avg_reaction_strength:.1f}% avg, {strong_reaction_rate:.1%} strong (+25 pts)")
            elif avg_reaction_strength >= 1.5 and strong_reaction_rate >= 0.5:
                score = 18.0  # Good reactions
                details.append(f"✅ Good reactions: {avg_reaction_strength:.1f}% avg, {strong_reaction_rate:.1%} strong (+18 pts)")
            elif avg_reaction_strength >= 1.0:
                score = 10.0  # Moderate reactions
                details.append(f"⚠️ Moderate reactions: {avg_reaction_strength:.1f}% avg, {strong_reaction_rate:.1%} strong (+10 pts)")
            else:
                score = 0.0  # Weak reactions
                details.append(f"❌ Weak reactions: {avg_reaction_strength:.1f}% avg, {strong_reaction_rate:.1%} strong (+0 pts)")
            
            return score, details
            
        except Exception as e:
            return 0.0, [f"Error scoring reaction strength: {e}"]
    
    def _score_volume_around_level(self, level_price: float, price_data: List[float], volumes: List[float],
                                  tolerance: float, level_type: str = 'support') -> tuple[float, List[str]]:
        """Score based on volume confirmation around the level"""
        try:
            level_volumes = []
            normal_volumes = []
            details = []
            
            # Separate volumes at level vs normal trading
            for price, volume in zip(price_data, volumes):
                if level_type == 'support':
                    if price <= level_price + tolerance and price >= level_price - tolerance:
                        level_volumes.append(volume)
                    else:
                        normal_volumes.append(volume)
                else:  # resistance
                    if price >= level_price - tolerance and price <= level_price + tolerance:
                        level_volumes.append(volume)
                    else:
                        normal_volumes.append(volume)
            
            if not level_volumes or not normal_volumes:
                score = 12.0  # Neutral score when no volume data
                details.append(f"📍 Insufficient volume data (+12 pts)")
                return score, details
            
            # Calculate volume ratios
            avg_level_volume = sum(level_volumes) / len(level_volumes)
            avg_normal_volume = sum(normal_volumes) / len(normal_volumes)
            volume_ratio = avg_level_volume / avg_normal_volume if avg_normal_volume > 0 else 1.0
            
            # Scoring logic (25 points max)
            if volume_ratio >= 2.0:
                score = 25.0  # Excellent volume confirmation
                details.append(f"🔊 Excellent volume: {volume_ratio:.1f}x above average (+25 pts)")
            elif volume_ratio >= 1.5:
                score = 18.0  # Good volume confirmation
                details.append(f"✅ Good volume: {volume_ratio:.1f}x above average (+18 pts)")
            elif volume_ratio >= 1.2:
                score = 12.0  # Moderate volume confirmation
                details.append(f"⚠️ Moderate volume: {volume_ratio:.1f}x above average (+12 pts)")
            elif volume_ratio >= 0.8:
                score = 6.0  # Below average volume
                details.append(f"📉 Below average volume: {volume_ratio:.1f}x average (+6 pts)")
            else:
                score = 0.0  # Poor volume
                details.append(f"❌ Poor volume: {volume_ratio:.1f}x average (+0 pts)")
            
            return score, details
            
        except Exception as e:
            return 0.0, [f"Error scoring volume: {e}"]
    
    def _score_approach_slope(self, level_price: float, closes: List[float], level_type: str) -> tuple[float, List[str]]:
        """Score based on how price approaches the level (gentle vs fast)"""
        try:
            if len(closes) < 5:
                return 10.0, [f"📍 Insufficient data for slope analysis (+10 pts)"]
            
            # Calculate approach slope using last 5 candles
            recent_closes = closes[-5:]
            current_price = closes[-1]
            
            # Calculate slope (price change per candle)
            price_changes = []
            for i in range(1, len(recent_closes)):
                change_pct = (recent_closes[i] - recent_closes[i-1]) / recent_closes[i-1] * 100
                price_changes.append(abs(change_pct))
            
            avg_change_pct = sum(price_changes) / len(price_changes) if price_changes else 0
            
            # Distance from level
            distance_pct = abs(current_price - level_price) / level_price * 100
            
            details = []
            
            # Scoring logic (20 points max)
            if distance_pct > 2.0:
                score = 5.0  # Too far from level
                details.append(f"📏 Too far from level: {distance_pct:.1f}% away (+5 pts)")
            elif avg_change_pct > 3.0:
                score = 8.0  # Approaching too fast (likely to break through)
                details.append(f"🏃 Fast approach: {avg_change_pct:.1f}% avg change (+8 pts)")
            elif avg_change_pct > 1.5:
                score = 12.0  # Moderate approach speed
                details.append(f"🚶 Moderate approach: {avg_change_pct:.1f}% avg change (+12 pts)")
            elif avg_change_pct > 0.5:
                score = 20.0  # Gentle approach (ideal)
                details.append(f"🐌 Gentle approach: {avg_change_pct:.1f}% avg change (+20 pts)")
            else:
                score = 15.0  # Very slow approach
                details.append(f"🔄 Very slow approach: {avg_change_pct:.1f}% avg change (+15 pts)")
            
            # Bonus for being very close to level
            if distance_pct < 0.5:
                score += 5.0
                details.append(f"🎯 Very close to level: {distance_pct:.1f}% away (+5 pts)")
            
            return min(score, 20.0), details
            
        except Exception as e:
            return 0.0, [f"Error scoring approach slope: {e}"]
    
    async def _get_flow_trading_opportunities(self) -> List[Dict[str, Any]]:
        """
        Get opportunities from FLOW TRADING SYSTEM (adaptive, market-aware)
        This implements the 4-layer Flow Strategy approach
        """
        try:
            # Try to import and use Flow Trading components
            try:
                from src.config.flow_trading_config import get_config_manager
                from src.monitoring.flow_trading_monitor import get_monitor
                
                config_manager = get_config_manager()
                monitor = get_monitor()
                
                if not config_manager or not monitor:
                    logger.info("🌊 Flow Trading components not available, using fallback")
                    return []
                
            except ImportError:
                logger.info("🌊 Flow Trading modules not available, using fallback")
                return []
            
            flow_opportunities = []
            
            # Get symbols to analyze (major crypto pairs)
            symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'SOLUSDT']
            
            for symbol in symbols:
                try:
                    # LAYER 1: Market Regime Detection
                    market_regime = await self._detect_market_regime(symbol)
                    
                    # LAYER 2: Dynamic SL/TP based on regime
                    sl_tp_config = await self._calculate_dynamic_sl_tp_config(symbol, market_regime)
                    
                    # LAYER 3: Correlation Filtering
                    correlation_filter = await self._check_correlation_filter(symbol)
                    
                    # LAYER 4: Volume & Momentum Triggers
                    volume_momentum = await self._check_volume_momentum_triggers(symbol)
                    
                    # Only proceed if all Flow Trading layers approve
                    if (market_regime['is_favorable'] and 
                        correlation_filter['should_trade'] and 
                        volume_momentum['has_triggers']):
                        
                        # Create Flow Trading opportunity
                        opportunity = {
                            'symbol': symbol,
                            'side': self._determine_flow_side(market_regime, volume_momentum),
                            'confidence': self._calculate_flow_confidence(market_regime, sl_tp_config, volume_momentum),
                            'strategy_type': 'flow_trading',
                            'market_regime': market_regime['regime'],
                            'volatility_regime': sl_tp_config['volatility_regime'],
                            'sl_config': sl_tp_config['sl_pct'],
                            'tp_config': sl_tp_config['tp_pct'],
                            'volume_strength': volume_momentum['volume_strength'],
                            'momentum_score': volume_momentum['momentum_score'],
                            'correlation_score': correlation_filter['correlation_score'],
                            'entry_reason': f"flow_trading_{market_regime['regime']}_{volume_momentum['trigger_type']}"
                        }
                        
                        flow_opportunities.append(opportunity)
                        logger.info(f"🌊 Flow opportunity: {symbol} {opportunity['side']} (confidence: {opportunity['confidence']:.2f})")
                
                except Exception as symbol_error:
                    logger.error(f"Error analyzing {symbol} for Flow Trading: {symbol_error}")
                    continue
            
            return flow_opportunities
            
        except Exception as e:
            logger.error(f"Error getting Flow Trading opportunities: {e}")
            return []
    
    async def _detect_market_regime(self, symbol: str) -> Dict[str, Any]:
        """
        LAYER 1: Market Regime Detection
        Determines if current market is ranging, trending, or volatile
        """
        try:
            market_trend = await self._detect_market_trend(symbol)
            volatility = await self._calculate_volatility(symbol)
            
            # Determine regime and favorability
            if market_trend in ['strong_uptrend', 'strong_downtrend']:
                regime = 'trending'
                is_favorable = True  # Trending markets are good for breakouts/pullbacks
                strategy_preference = 'breakout' if volatility > 1.5 else 'pullback'
            elif market_trend in ['uptrend', 'downtrend']:
                regime = 'weak_trending'
                is_favorable = volatility < 2.0  # Only if not too volatile
                strategy_preference = 'pullback'
            elif volatility > 2.5:
                regime = 'volatile'
                is_favorable = False  # Avoid volatile markets
                strategy_preference = 'avoid'
            else:
                regime = 'ranging'
                is_favorable = True  # Ranging markets are good for support/resistance
                strategy_preference = 'support_resistance'
            
            return {
                'regime': regime,
                'trend': market_trend,
                'volatility': volatility,
                'is_favorable': is_favorable,
                'strategy_preference': strategy_preference
            }
            
        except Exception as e:
            logger.error(f"Error detecting market regime for {symbol}: {e}")
            return {
                'regime': 'unknown',
                'trend': 'neutral',
                'volatility': 1.0,
                'is_favorable': False,
                'strategy_preference': 'avoid'
            }
    
    async def _calculate_dynamic_sl_tp_config(self, symbol: str, market_regime: Dict[str, Any]) -> Dict[str, Any]:
        """
        LAYER 2: Dynamic SL/TP based on live volatility and regime
        """
        try:
            volatility = market_regime['volatility']
            regime = market_regime['regime']
            
            # Base SL/TP percentages
            base_sl = 0.003  # 0.3%
            base_tp = 0.008  # 0.8%
            
            # Adjust based on regime
            if regime == 'trending':
                # Trending markets: tighter SL, higher TP
                sl_pct = base_sl * 0.8  # 0.24%
                tp_pct = base_tp * 2.5  # 2.0%
                volatility_regime = 'trending'
            elif regime == 'ranging':
                # Ranging markets: standard SL/TP
                sl_pct = base_sl  # 0.3%
                tp_pct = base_tp  # 0.8%
                volatility_regime = 'ranging'
            elif regime == 'volatile':
                # Volatile markets: wider SL, moderate TP
                sl_pct = base_sl * 1.5  # 0.45%
                tp_pct = base_tp * 1.2  # 0.96%
                volatility_regime = 'volatile'
            else:
                # Unknown regime: conservative
                sl_pct = base_sl * 1.2  # 0.36%
                tp_pct = base_tp  # 0.8%
                volatility_regime = 'conservative'
            
            # Volatility adjustments
            if volatility > 2.0:
                sl_pct *= 1.3
                tp_pct *= 1.4
            elif volatility < 0.8:
                sl_pct *= 0.8
                tp_pct *= 0.9
            
            return {
                'sl_pct': sl_pct,
                'tp_pct': tp_pct,
                'volatility_regime': volatility_regime,
                'regime_adjustment': regime
            }
            
        except Exception as e:
            logger.error(f"Error calculating dynamic SL/TP for {symbol}: {e}")
            return {
                'sl_pct': 0.005,  # Conservative fallback
                'tp_pct': 0.010,
                'volatility_regime': 'conservative',
                'regime_adjustment': 'fallback'
            }
    
    async def _check_correlation_filter(self, symbol: str) -> Dict[str, Any]:
        """
        LAYER 3: Correlation Filtering
        Avoids overexposing portfolio to similar assets
        """
        try:
            # Check recent trades for correlated symbols
            correlated_symbols = {
                'BTCUSDT': ['ETHUSDT'],
                'ETHUSDT': ['BTCUSDT'],
                'BNBUSDT': ['BTCUSDT', 'ETHUSDT'],
                'ADAUSDT': ['ETHUSDT'],
                'SOLUSDT': ['ETHUSDT']
            }
            
            related_symbols = correlated_symbols.get(symbol, [])
            
            # Check recent performance of correlated symbols
            recent_failures = 0
            recent_successes = 0
            
            for related_symbol in related_symbols:
                recent_trades = [
                    t for t in self.completed_trades[-10:]  # Last 10 trades
                    if t.symbol == related_symbol
                ]
                
                for trade in recent_trades:
                    if trade.pnl < 0:
                        recent_failures += 1
                    else:
                        recent_successes += 1
            
            # Calculate correlation score
            total_related_trades = recent_failures + recent_successes
            if total_related_trades == 0:
                correlation_score = 1.0  # No correlation data
                should_trade = True
            else:
                success_rate = recent_successes / total_related_trades
                correlation_score = success_rate
                
                # Don't trade if correlated symbols are failing
                should_trade = success_rate >= 0.4  # At least 40% success rate
            
            return {
                'should_trade': should_trade,
                'correlation_score': correlation_score,
                'related_symbols': related_symbols,
                'recent_failures': recent_failures,
                'recent_successes': recent_successes
            }
            
        except Exception as e:
            logger.error(f"Error checking correlation filter for {symbol}: {e}")
            return {
                'should_trade': True,  # Default to allow trading
                'correlation_score': 1.0,
                'related_symbols': [],
                'recent_failures': 0,
                'recent_successes': 0
            }
    
    async def _check_volume_momentum_triggers(self, symbol: str) -> Dict[str, Any]:
        """
        LAYER 4: Volume & Momentum Triggers
        Only enters trades when volume and momentum are favorable
        """
        try:
            # Get current volume and momentum
            if self.exchange_client:
                # Get recent klines for volume analysis
                klines = await self.exchange_client.get_klines(symbol, '5m', limit=20)
                if klines and len(klines) >= 10:
                    volumes = [float(kline[5]) for kline in klines]
                    avg_volume = sum(volumes) / len(volumes)
                    current_volume = volumes[-1]
                    volume_ratio = current_volume / avg_volume
                else:
                    volume_ratio = 1.0
            else:
                volume_ratio = 1.0  # Default for testing
            
            # Get momentum
            momentum = await self._calculate_momentum(symbol)
            
            # Determine volume strength
            if volume_ratio >= 1.5:
                volume_strength = 'high'
                volume_score = 1.0
            elif volume_ratio >= 1.2:
                volume_strength = 'moderate'
                volume_score = 0.8
            elif volume_ratio >= 0.8:
                volume_strength = 'normal'
                volume_score = 0.6
            else:
                volume_strength = 'low'
                volume_score = 0.3
            
            # Determine momentum triggers
            if momentum > 70:
                momentum_trigger = 'strong_bullish'
                momentum_score = 1.0
            elif momentum > 55:
                momentum_trigger = 'moderate_bullish'
                momentum_score = 0.8
            elif momentum < 30:
                momentum_trigger = 'strong_bearish'
                momentum_score = 1.0
            elif momentum < 45:
                momentum_trigger = 'moderate_bearish'
                momentum_score = 0.8
            else:
                momentum_trigger = 'neutral'
                momentum_score = 0.5
            
            # Determine if we have sufficient triggers
            has_triggers = (volume_score >= 0.6 and momentum_score >= 0.6)
            
            # Determine trigger type
            if volume_strength in ['high', 'moderate'] and momentum_trigger in ['strong_bullish', 'moderate_bullish']:
                trigger_type = 'bullish_volume_momentum'
            elif volume_strength in ['high', 'moderate'] and momentum_trigger in ['strong_bearish', 'moderate_bearish']:
                trigger_type = 'bearish_volume_momentum'
            elif volume_strength == 'high':
                trigger_type = 'high_volume'
            else:
                trigger_type = 'weak_triggers'
            
            return {
                'has_triggers': has_triggers,
                'volume_strength': volume_strength,
                'volume_ratio': volume_ratio,
                'volume_score': volume_score,
                'momentum_score': momentum_score,
                'momentum_trigger': momentum_trigger,
                'trigger_type': trigger_type
            }
            
        except Exception as e:
            logger.error(f"Error checking volume/momentum triggers for {symbol}: {e}")
            return {
                'has_triggers': False,
                'volume_strength': 'unknown',
                'volume_ratio': 1.0,
                'volume_score': 0.5,
                'momentum_score': 0.5,
                'momentum_trigger': 'unknown',
                'trigger_type': 'error'
            }
    
    def _determine_flow_side(self, market_regime: Dict[str, Any], volume_momentum: Dict[str, Any]) -> str:
        """Determine trade side based on Flow Trading analysis"""
        try:
            trend = market_regime['trend']
            momentum_trigger = volume_momentum['momentum_trigger']
            
            # Trend-based decisions
            if trend in ['strong_uptrend', 'uptrend']:
                return 'LONG'
            elif trend in ['strong_downtrend', 'downtrend']:
                return 'SHORT'
            
            # Momentum-based decisions for neutral trends
            if momentum_trigger in ['strong_bullish', 'moderate_bullish']:
                return 'LONG'
            elif momentum_trigger in ['strong_bearish', 'moderate_bearish']:
                return 'SHORT'
            
            # Default to LONG for neutral conditions
            return 'LONG'
            
        except Exception as e:
            logger.error(f"Error determining flow side: {e}")
            return 'LONG'
    
    def _calculate_flow_confidence(self, market_regime: Dict[str, Any], sl_tp_config: Dict[str, Any], 
                                 volume_momentum: Dict[str, Any]) -> float:
        """Calculate confidence score for Flow Trading opportunity"""
        try:
            base_confidence = 0.6
            
            # Market regime confidence
            if market_regime['regime'] == 'trending':
                regime_bonus = 0.2
            elif market_regime['regime'] == 'ranging':
                regime_bonus = 0.1
            else:
                regime_bonus = 0.0
            
            # Volume/momentum confidence
            volume_score = volume_momentum['volume_score']
            momentum_score = volume_momentum['momentum_score']
            trigger_bonus = (volume_score + momentum_score) / 2 * 0.2
            
            # Volatility adjustment
            volatility = market_regime['volatility']
            if volatility < 1.5:  # Low volatility is good
                volatility_bonus = 0.1
            elif volatility > 2.5:  # High volatility is bad
                volatility_bonus = -0.1
            else:
                volatility_bonus = 0.0
            
            # Calculate final confidence
            final_confidence = base_confidence + regime_bonus + trigger_bonus + volatility_bonus
            
            # Cap between 0.5 and 0.95
            return max(0.5, min(0.95, final_confidence))
            
        except Exception as e:
            logger.error(f"Error calculating flow confidence: {e}")
            return 0.6
    
    async def reset_account(self):
        """Reset paper trading account"""
        self.positions.clear()
        self.completed_trades.clear()
        self.trade_history.clear()
        self.ml_training_data.clear()
        self.strategy_performance.clear()
        
        self.account = PaperAccount(
            balance=self.config.get('initial_balance', 10000.0),
            equity=self.config.get('initial_balance', 10000.0),
            unrealized_pnl=0.0,
            realized_pnl=0.0,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            profit_factor=0.0,
            max_drawdown=0.0,
            sharpe_ratio=0.0,
            daily_pnl=0.0,
            last_updated=datetime.utcnow()
        )
        
        logger.info("🔄 Paper trading account reset")
    
    def connect_opportunity_manager(self, opportunity_manager):
        """Connect opportunity manager to paper trading engine"""
        self.opportunity_manager = opportunity_manager
        logger.info("🔗 Opportunity Manager connected to Paper Trading Engine")
    
    def connect_profit_scraping_engine(self, profit_scraping_engine):
        """Connect profit scraping engine to paper trading engine"""
        self.profit_scraping_engine = profit_scraping_engine
        logger.info("🔗 Profit Scraping Engine connected to Paper Trading Engine")
