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

from src.database.database import Database

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
    
    def __init__(self, config: Dict[str, Any], exchange_client=None, opportunity_manager=None):
        self.config = config.get('paper_trading', {})
        self.exchange_client = exchange_client
        self.opportunity_manager = opportunity_manager
        
        # Initialize database - MUST work, no fallbacks
        self.db = Database()
        logger.info("✅ Database initialized for paper trading")
        
        # Trading state
        self.is_running = False
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
        
        # Risk management - RELAXED FOR AGGRESSIVE PAPER TRADING
        self.max_position_size = self.config.get('max_position_size_pct', 0.02)  # Keep 2% per position
        self.max_total_exposure = self.config.get('max_total_exposure_pct', 1.0)  # 100% total exposure allowed
        self.max_daily_loss = self.config.get('max_daily_loss_pct', 0.50)  # 50% daily loss limit
        
        logger.info("🟢 Enhanced Paper Trading Engine initialized")
    
    async def start(self):
        """Start paper trading engine"""
        if self.is_running:
            logger.warning("Paper trading engine already running")
            return
        
        self.is_running = True
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
        self.is_running = False
        logger.info("🛑 Paper Trading Engine stopped")
    
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
            
            # Risk checks
            logger.info(f"🎯 Paper Trading: Checking risk limits for {symbol}")
            if not await self._check_risk_limits(symbol, current_price):
                logger.warning(f"❌ Paper Trading: Risk limits exceeded for {symbol}")
                return None
            
            logger.info(f"🎯 Paper Trading: Risk checks passed for {symbol}")
            
            # Calculate position size
            position_size = self._calculate_position_size(symbol, current_price, confidence)
            logger.info(f"🎯 Paper Trading: Calculated position size {position_size} for {symbol}")
            
            # Create position
            position_id = str(uuid.uuid4())
            position = PaperPosition(
                id=position_id,
                symbol=symbol,
                strategy_type=strategy_type,
                side=side,
                entry_price=current_price,
                quantity=position_size,
                entry_time=datetime.utcnow(),
                confidence_score=confidence,
                ml_score=ml_score,
                entry_reason=entry_reason,
                market_regime=signal.get('market_regime', ''),
                volatility_regime=signal.get('volatility_regime', ''),
                current_price=current_price
            )
            
            logger.info(f"🎯 Paper Trading: Created position object for {symbol}")
            
            # Set stop loss and take profit
            position.stop_loss = self._calculate_stop_loss(current_price, side, symbol)
            position.take_profit = self._calculate_take_profit(current_price, side, symbol)
            
            logger.info(f"🎯 Paper Trading: Set SL/TP for {symbol} - SL: {position.stop_loss}, TP: {position.take_profit}")
            
            # Store position
            self.positions[position_id] = position
            logger.info(f"🎯 Paper Trading: Stored position {position_id} for {symbol}")
            
            # Update account
            self.account.equity -= position_size * current_price * 0.001  # Simulated fees
            
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
        """Close a paper position"""
        try:
            if position_id not in self.positions:
                logger.error(f"Position not found: {position_id}")
                return None
            
            position = self.positions[position_id]
            
            # Get current price
            current_price = await self._get_current_price(position.symbol)
            if not current_price:
                logger.error(f"Could not get price for {position.symbol}")
                return None
            
            # Calculate P&L
            if position.side == 'LONG':
                pnl = (current_price - position.entry_price) * position.quantity
                pnl_pct = (current_price - position.entry_price) / position.entry_price
            else:  # SHORT
                pnl = (position.entry_price - current_price) * position.quantity
                pnl_pct = (position.entry_price - current_price) / position.entry_price
            
            # Calculate fees
            fees = (position.quantity * position.entry_price + position.quantity * current_price) * 0.001
            net_pnl = pnl - fees
            
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
                entry_time=position.entry_time,
                exit_time=datetime.utcnow()
            )
            
            # Update account
            self.account.realized_pnl += net_pnl
            self.account.balance += net_pnl
            self.account.equity = self.account.balance + self._calculate_unrealized_pnl()
            self.account.total_trades += 1
            
            if net_pnl > 0:
                self.account.winning_trades += 1
            else:
                self.account.losing_trades += 1
            
            self.account.win_rate = self.account.winning_trades / self.account.total_trades
            
            # Update strategy performance
            self._update_strategy_performance(trade)
            
            # Store completed trade
            self.completed_trades.append(trade)
            self.trade_history.append(trade)
            
            # Remove position
            del self.positions[position_id]
            
            # Log trade
            logger.info(f"📉 Paper Trade Closed: {position.symbol} {position.side} @ {current_price:.4f} "
                       f"P&L: {net_pnl:.2f} ({pnl_pct:.2%}) Duration: {trade.duration_minutes}m")
            
            # Store in database
            await self._store_trade(trade)
            
            # Collect ML training data
            await self._collect_ml_data(trade)
            
            return trade
            
        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return None
    
    async def _position_monitoring_loop(self):
        """Monitor positions for stop loss/take profit"""
        while self.is_running:
            try:
                positions_to_close = []
                
                for position_id, position in self.positions.items():
                    current_price = await self._get_current_price(position.symbol)
                    if not current_price:
                        continue
                    
                    # Update unrealized P&L
                    if position.side == 'LONG':
                        position.unrealized_pnl = (current_price - position.entry_price) * position.quantity
                        position.unrealized_pnl_pct = ((current_price - position.entry_price) / position.entry_price) * 100
                    else:  # SHORT
                        position.unrealized_pnl = (position.entry_price - current_price) * position.quantity
                        position.unrealized_pnl_pct = ((position.entry_price - current_price) / position.entry_price) * 100
                    
                    position.current_price = current_price
                    
                    # Check stop loss
                    if position.stop_loss:
                        if (position.side == 'LONG' and current_price <= position.stop_loss) or \
                           (position.side == 'SHORT' and current_price >= position.stop_loss):
                            positions_to_close.append((position_id, "stop_loss"))
                    
                    # Check take profit
                    if position.take_profit:
                        if (position.side == 'LONG' and current_price >= position.take_profit) or \
                           (position.side == 'SHORT' and current_price <= position.take_profit):
                            positions_to_close.append((position_id, "take_profit"))
                    
                    # Check maximum hold time (24 hours for scalping)
                    if position.strategy_type == 'scalping':
                        hold_time = datetime.utcnow() - position.entry_time
                        if hold_time > timedelta(hours=24):
                            positions_to_close.append((position_id, "max_time"))
                
                # Close positions
                for position_id, reason in positions_to_close:
                    await self.close_position(position_id, reason)
                
                # Update account equity
                self.account.unrealized_pnl = self._calculate_unrealized_pnl()
                self.account.equity = self.account.balance + self.account.unrealized_pnl
                
                await asyncio.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                logger.error(f"Error in position monitoring loop: {e}")
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
                        logger.info(f"🎯 Paper Trading: Processing opportunity: {opportunity.get('symbol')} {opportunity.get('side')} (confidence: {opportunity.get('confidence')})")
                        
                        # Convert opportunity to trading signal
                        signal = self._convert_opportunity_to_signal(opportunity)
                        
                        if signal:
                            logger.info(f"🎯 Paper Trading: Converted to signal: {signal}")
                            
                            if self._should_trade_signal(signal):
                                logger.info(f"🚀 Paper Trading: Executing trade for {signal['symbol']} {signal['side']}")
                                position_id = await self.execute_trade(signal)
                                
                                if position_id:
                                    logger.info(f"✅ Paper Trade executed: {signal['symbol']} {signal['side']} (Position: {position_id})")
                                else:
                                    logger.warning(f"❌ Failed to execute paper trade: {signal['symbol']} {signal['side']}")
                            else:
                                logger.info(f"🎯 Paper Trading: Signal rejected by filters: {signal['symbol']} {signal['side']}")
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
        """Get fresh trading opportunities from opportunity manager - AGGRESSIVE FILTERING"""
        try:
            if not self.opportunity_manager:
                return []
            
            # Get current opportunities
            opportunities = self.opportunity_manager.get_opportunities()
            
            # Filter for opportunities suitable for aggressive paper trading
            fresh_opportunities = []
            for opp in opportunities:
                # Lower confidence threshold for more trades (reduced from 0.7 to 0.5)
                if opp.get('confidence', 0) >= 0.5:
                    # Check if we haven't already traded this signal recently (1 minute cooldown)
                    symbol = opp.get('symbol')
                    if not self._recently_traded_symbol(symbol):
                        fresh_opportunities.append(opp)
            
            return fresh_opportunities
            
        except Exception as e:
            logger.error(f"Error getting fresh opportunities: {e}")
            return []
    
    def _convert_opportunity_to_signal(self, opportunity: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Convert opportunity to trading signal"""
        try:
            signal = {
                'symbol': opportunity.get('symbol'),
                'strategy_type': 'scalping',  # Default to scalping for paper trading
                'side': opportunity.get('side', 'LONG'),
                'confidence': opportunity.get('confidence', 0.0),
                'ml_score': opportunity.get('ml_score', opportunity.get('confidence', 0.0)),
                'reason': f"auto_signal_{opportunity.get('strategy_type', 'unknown')}",
                'market_regime': opportunity.get('market_regime', 'unknown'),
                'volatility_regime': opportunity.get('volatility_regime', 'medium')
            }
            
            return signal
            
        except Exception as e:
            logger.error(f"Error converting opportunity to signal: {e}")
            return None
    
    def _should_trade_signal(self, signal: Dict[str, Any]) -> bool:
        """Determine if we should trade this signal - AGGRESSIVE PAPER TRADING"""
        try:
            # Basic filters
            if not signal.get('symbol') or not signal.get('side'):
                return False
            
            # Lower confidence threshold for more trades
            if signal.get('confidence', 0) < 0.5:  # Reduced from 0.7 to 0.5
                return False
            
            # REMOVED: One position per symbol limit - allow multiple positions
            # REMOVED: Position count limits - take all validated signals
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking if should trade signal: {e}")
            return False
    
    def _recently_traded_symbol(self, symbol: str) -> bool:
        """Check if we recently traded this symbol - RELAXED COOLDOWN"""
        try:
            # Check if we traded this symbol in the last 1 minute (reduced from 30 minutes)
            cutoff_time = datetime.utcnow() - timedelta(minutes=1)
            
            for trade in reversed(self.completed_trades):
                if trade.symbol == symbol and trade.entry_time >= cutoff_time:
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking recently traded symbol: {e}")
            return False
    
    async def _get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for symbol"""
        try:
            if self.exchange_client:
                ticker = await self.exchange_client.get_ticker_24h(symbol)
                return float(ticker.get('lastPrice', 0))
            else:
                # Mock price for testing
                import random
                base_price = 50000 if 'BTC' in symbol else 3000
                return base_price * (1 + random.uniform(-0.02, 0.02))
        except Exception as e:
            logger.error(f"Error getting price for {symbol}: {e}")
            return None
    
    def _calculate_position_size(self, symbol: str, price: float, confidence: float) -> float:
        """Calculate position size with REAL Binance-style 10x leverage"""
        try:
            # REAL LEVERAGE CALCULATION
            margin_per_trade = 200.0  # Only $200 margin required per trade
            leverage = 10.0
            notional_value = margin_per_trade * leverage  # $2,000 notional position
            
            # Calculate crypto quantity based on notional value
            position_size = notional_value / price
            
            logger.info(f"💰 REAL Leverage: Margin ${margin_per_trade} × {leverage}x = ${notional_value} notional → {position_size:.6f} {symbol}")
            logger.info(f"💰 Risk: Only ${margin_per_trade} at risk (not ${notional_value})")
            
            return position_size
            
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return 0.0
    
    def _calculate_stop_loss(self, entry_price: float, side: str, symbol: str) -> float:
        """Calculate stop loss price at 15% to avoid false negatives"""
        try:
            # 15% stop loss - gives more room for temporary reversals
            stop_loss_pct = 0.15
            
            if side == 'LONG':
                sl_price = entry_price * (1 - stop_loss_pct)
            else:  # SHORT
                sl_price = entry_price * (1 + stop_loss_pct)
            
            logger.info(f"🛡️ Stop Loss: {side} @ {entry_price:.4f} → SL @ {sl_price:.4f} ({stop_loss_pct:.1%})")
            return sl_price
                
        except Exception as e:
            logger.error(f"Error calculating stop loss: {e}")
            # Fallback to default
            stop_loss_pct = 0.15
            if side == 'LONG':
                return entry_price * (1 - stop_loss_pct)
            else:
                return entry_price * (1 + stop_loss_pct)
    
    def _calculate_take_profit(self, entry_price: float, side: str, symbol: str) -> float:
        """Calculate take profit price"""
        try:
            # 15% take profit
            profit_target_pct = 0.15
            
            if side == 'LONG':
                return entry_price * (1 + profit_target_pct)
            else:  # SHORT
                return entry_price * (1 - profit_target_pct)
                
        except Exception as e:
            logger.error(f"Error calculating take profit: {e}")
            # Fallback to default
            profit_target_pct = 0.15
            if side == 'LONG':
                return entry_price * (1 + profit_target_pct)
            else:
                return entry_price * (1 - profit_target_pct)
    
    def _calculate_unrealized_pnl(self) -> float:
        """Calculate total unrealized P&L"""
        return sum(pos.unrealized_pnl for pos in self.positions.values())
    
    async def _check_risk_limits(self, symbol: str, price: float) -> bool:
        """Check if trade passes risk limits - WITH DETAILED LOGGING"""
        try:
            logger.info(f"🔍 Risk Check for {symbol}: Starting detailed analysis...")
            
            # Check daily loss limit
            daily_loss_limit = -self.account.balance * self.max_daily_loss
            logger.info(f"🔍 Daily P&L: ${self.account.daily_pnl:.2f}, Limit: ${daily_loss_limit:.2f}")
            
            if self.account.daily_pnl < daily_loss_limit:
                logger.warning(f"❌ REJECTED {symbol}: Daily loss limit exceeded (${self.account.daily_pnl:.2f} < ${daily_loss_limit:.2f})")
                return False
            
            # Check total MARGIN exposure (REAL leverage calculation)
            current_margin_used = 0.0
            for pos in self.positions.values():
                # Each position uses $200 margin regardless of notional value
                current_margin_used += 200.0  # Fixed $200 margin per position
            
            max_exposure = self.account.balance * self.max_total_exposure
            margin_per_trade = 200.0  # Only $200 margin required per trade
            
            logger.info(f"🔍 Current Margin Used: ${current_margin_used:.2f}")
            logger.info(f"🔍 Max Exposure: ${max_exposure:.2f} ({self.max_total_exposure * 100:.0f}% of ${self.account.balance:.2f})")
            logger.info(f"🔍 New Position Margin: ${margin_per_trade:.2f}")
            logger.info(f"🔍 Total Margin After Trade: ${current_margin_used + margin_per_trade:.2f}")
            logger.info(f"🔍 Active Positions: {len(self.positions)}")
            logger.info(f"🔍 Max Possible Positions: {max_exposure / margin_per_trade:.0f}")
            
            # Check margin usage (this is the real constraint)
            if current_margin_used >= max_exposure:
                logger.warning(f"❌ REJECTED {symbol}: Margin limit exceeded (${current_margin_used:.2f} >= ${max_exposure:.2f})")
                return False
            
            # Check if new position would exceed margin limit
            if (current_margin_used + margin_per_trade) > max_exposure:
                logger.warning(f"❌ REJECTED {symbol}: New position would exceed margin limit (${current_margin_used + margin_per_trade:.2f} > ${max_exposure:.2f})")
                logger.info(f"🔍 Note: With ${max_exposure:.2f} available, you can have {max_exposure/200:.0f} simultaneous positions")
                return False
            
            logger.info(f"✅ PASSED {symbol}: All risk checks passed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error checking risk limits for {symbol}: {e}")
            return False
    
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
        """Collect ML training data from completed trade"""
        try:
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
            
            # Keep only recent data
            if len(self.ml_training_data) > 10000:
                self.ml_training_data = self.ml_training_data[-5000:]
            
        except Exception as e:
            logger.error(f"Error collecting ML data: {e}")
    
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
        account_data['capital_per_position'] = 200.0  # Fixed $200 per position
        
        return {
            'account': account_data,
            'positions': {pid: asdict(pos) for pid, pos in self.positions.items()},
            'recent_trades': [asdict(t) for t in list(self.trade_history)[-10:]],
            'strategy_performance': dict(self.strategy_performance),
            'is_running': self.is_running
        }
    
    def get_ml_training_data(self) -> List[Dict[str, Any]]:
        """Get collected ML training data"""
        return self.ml_training_data.copy()
    
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
