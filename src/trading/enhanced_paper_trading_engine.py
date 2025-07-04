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
    
    def __init__(self, config: Dict[str, Any], exchange_client=None, opportunity_manager=None, profit_scraping_engine=None):
        self.config = config.get('paper_trading', {})
        self.exchange_client = exchange_client
        self.opportunity_manager = opportunity_manager
        self.profit_scraping_engine = profit_scraping_engine  # NEW: Direct connection to profit scraping
        
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
            position.stop_loss = await self._calculate_stop_loss(current_price, side, symbol)
            position.take_profit = await self._calculate_take_profit(current_price, side, symbol)
            
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
            
            # Log trade with formatted duration
            duration_formatted = format_duration(trade.duration_minutes)
            logger.info(f"📉 Paper Trade Closed: {position.symbol} {position.side} @ {current_price:.4f} "
                       f"P&L: {net_pnl:.2f} ({pnl_pct:.2%}) Duration: {duration_formatted}")
            
            # Store in database
            await self._store_trade(trade)
            
            # Collect ML training data
            await self._collect_ml_data(trade)
            
            return trade
            
        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return None
    
    async def _position_monitoring_loop(self):
        """Monitor positions for stop loss/take profit AND trend reversal exits"""
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
                    
                    # CRITICAL: Check for level breakdown/breakout BEFORE normal SL/TP
                    breakdown_exit = await self._check_level_breakdown_exit(position, current_price)
                    if breakdown_exit:
                        positions_to_close.append((position_id, breakdown_exit))
                        continue  # Skip other checks if level breakdown detected
                    
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
                    
                    # Check for trend reversal exit
                    trend_reversal_exit = await self._check_trend_reversal_exit(position, current_price)
                    if trend_reversal_exit:
                        positions_to_close.append((position_id, trend_reversal_exit))
                    
                    # Optional: Add safety net for extremely long positions (7 days)
                    # Only close if position is losing money to prevent runaway losses
                    hold_time = datetime.utcnow() - position.entry_time
                    if hold_time > timedelta(days=7) and position.unrealized_pnl < 0:
                        positions_to_close.append((position_id, "safety_time_limit"))
                        logger.warning(f"⚠️ Closing losing position {position_id} after 7 days for safety")
                
                # Close positions
                for position_id, reason in positions_to_close:
                    await self.close_position(position_id, reason)
                
                # Update account equity
                self.account.unrealized_pnl = self._calculate_unrealized_pnl()
                self.account.equity = self.account.balance + self.account.unrealized_pnl
                
                await asyncio.sleep(5)  # Check every 5 seconds for faster breakdown detection
                
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
        """Get fresh trading opportunities from FLOW TRADING SYSTEM"""
        try:
            # PRIORITY 1: Use Flow Trading System (adaptive, market-aware)
            flow_opportunities = await self._get_flow_trading_opportunities()
            if flow_opportunities:
                logger.info(f"🌊 Flow Trading: Found {len(flow_opportunities)} adaptive opportunities")
                return flow_opportunities
            
            # FALLBACK: Use profit scraping engine if Flow Trading not available
            elif self.profit_scraping_engine and self.profit_scraping_engine.active:
                logger.info("🎯 Fallback: Using static profit scraping engine")
                
                # Get profit scraping opportunities (these are the magnet level opportunities)
                scraping_opportunities = self.profit_scraping_engine.get_opportunities()
                
                fresh_opportunities = []
                for symbol, opportunities in scraping_opportunities.items():
                    for opp in opportunities:
                        # Check if we haven't already traded this symbol recently
                        if not self._recently_traded_symbol(symbol):
                            # Convert profit scraping opportunity to our format
                            converted_opp = self._convert_scraping_opportunity(opp, symbol)
                            if converted_opp:
                                fresh_opportunities.append(converted_opp)
                
                logger.info(f"🎯 Static Profit Scraping: Found {len(fresh_opportunities)} magnet level opportunities")
                return fresh_opportunities
            
            # FALLBACK 2: Use opportunity manager if nothing else available
            elif self.opportunity_manager:
                logger.info("🎯 Fallback: Using opportunity manager (generic signals)")
                
                opportunities = self.opportunity_manager.get_opportunities()
                
                fresh_opportunities = []
                for opp in opportunities:
                    if opp.get('confidence', 0) >= 0.5:
                        symbol = opp.get('symbol')
                        if not self._recently_traded_symbol(symbol):
                            fresh_opportunities.append(opp)
                
                return fresh_opportunities
            
            else:
                logger.warning("🎯 No Flow Trading, profit scraping engine OR opportunity manager available")
                return []
            
        except Exception as e:
            logger.error(f"Error getting fresh opportunities: {e}")
            return []
    
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
    
    async def _calculate_stop_loss(self, entry_price: float, side: str, symbol: str) -> float:
        """Calculate DYNAMIC stop loss based on market conditions and support/resistance validation"""
        try:
            # Get market trend and volatility
            market_trend = await self._detect_market_trend(symbol)
            volatility = await self._calculate_volatility(symbol)
            
            # CRITICAL: Validate support/resistance before setting SL
            level_validation = await self._validate_support_resistance_holding(symbol, entry_price, side)
            
            # Base stop loss percentage
            base_sl_pct = 0.003  # 0.3% base
            
            # SUPPORT/RESISTANCE VALIDATION ADJUSTMENT
            if not level_validation['is_holding']:
                # Level is breaking - use wider SL for protection
                sl_pct = base_sl_pct * 2.0  # 0.6% wider SL
                logger.warning(f"⚠️ LEVEL BREAKING: Wider SL - {level_validation['reason']}")
                
            elif level_validation['strength'] == 'strong':
                # Strong level holding - can use tighter SL
                sl_pct = base_sl_pct * 0.7  # 0.21% tighter SL
                logger.info(f"💪 STRONG LEVEL: Tighter SL - {level_validation['reason']}")
                
            else:
                # Standard level validation
                sl_pct = base_sl_pct
            
            # DYNAMIC ADJUSTMENTS based on market conditions
            if market_trend == 'strong_uptrend' and side == 'LONG' and level_validation['is_holding']:
                # In strong uptrend with holding support, use tighter SL
                sl_pct *= 0.8  # Further tighten
                logger.info(f"🔥 TREND + SUPPORT: Tighter SL for LONG in strong uptrend")
                
            elif market_trend == 'strong_downtrend' and side == 'SHORT' and level_validation['is_holding']:
                # In strong downtrend with holding resistance, use tighter SL
                sl_pct *= 0.8  # Further tighten
                logger.info(f"🔥 TREND + RESISTANCE: Tighter SL for SHORT in strong downtrend")
                
            elif market_trend == 'strong_downtrend' and side == 'LONG':
                # LONG in downtrend - very risky, wider SL
                sl_pct *= 2.0  # Much wider SL
                logger.warning(f"🚨 HIGH RISK: LONG against strong downtrend - wider SL")
                
            elif market_trend == 'strong_uptrend' and side == 'SHORT':
                # SHORT in uptrend - very risky, wider SL
                sl_pct *= 2.0  # Much wider SL
                logger.warning(f"🚨 HIGH RISK: SHORT against strong uptrend - wider SL")
            
            # VOLATILITY ADJUSTMENT
            if volatility > 2.0:  # High volatility
                sl_pct *= 1.3  # Wider SL for volatile markets
                logger.info(f"📈 HIGH VOLATILITY: Wider SL ({volatility:.1f})")
            elif volatility < 0.5:  # Low volatility
                sl_pct *= 0.8  # Tighter SL for calm markets
                logger.info(f"📉 LOW VOLATILITY: Tighter SL ({volatility:.1f})")
            
            # Cap SL at reasonable limits
            sl_pct = max(0.002, min(0.015, sl_pct))  # Between 0.2% and 1.5%
            
            # Calculate final SL price
            if side == 'LONG':
                sl_price = entry_price * (1 - sl_pct)
            else:  # SHORT
                sl_price = entry_price * (1 + sl_pct)
            
            logger.info(f"🛡️ VALIDATED SL: {side} @ {entry_price:.4f} → SL @ {sl_price:.4f} ({sl_pct:.3%}) [Trend: {market_trend}, Level: {level_validation['strength']}, Vol: {volatility:.1f}]")
            return sl_price
                
        except Exception as e:
            logger.error(f"Error calculating dynamic stop loss: {e}")
            # Fallback to conservative SL
            sl_pct = 0.006  # 0.6% conservative
            if side == 'LONG':
                return entry_price * (1 - sl_pct)
            else:
                return entry_price * (1 + sl_pct)
    
    async def _calculate_take_profit(self, entry_price: float, side: str, symbol: str) -> float:
        """Calculate DYNAMIC take profit based on market conditions and momentum"""
        try:
            # Get market trend and volatility
            market_trend = await self._detect_market_trend(symbol)
            volatility = await self._calculate_volatility(symbol)
            momentum = await self._calculate_momentum(symbol)
            
            # Base take profit percentage
            base_tp_pct = 0.008  # 0.8% base
            
            # DYNAMIC ADJUSTMENTS for MAXIMUM PROFIT EXTRACTION
            if market_trend == 'strong_uptrend' and side == 'LONG':
                # Strong uptrend LONG - much higher TP to ride the trend
                tp_pct = base_tp_pct * 3.0  # 2.4% TP
                logger.info(f"🚀 TREND RIDING: Higher TP for LONG in strong uptrend")
                
            elif market_trend == 'strong_downtrend' and side == 'SHORT':
                # Strong downtrend SHORT - much higher TP to ride the trend
                tp_pct = base_tp_pct * 3.0  # 2.4% TP
                logger.info(f"🚀 TREND RIDING: Higher TP for SHORT in strong downtrend")
                
            elif market_trend in ['uptrend', 'downtrend']:
                # Moderate trend - higher TP
                if (market_trend == 'uptrend' and side == 'LONG') or (market_trend == 'downtrend' and side == 'SHORT'):
                    tp_pct = base_tp_pct * 2.0  # 1.6% TP
                    logger.info(f"📈 TREND FOLLOWING: Higher TP with trend")
                else:
                    tp_pct = base_tp_pct * 1.2  # 0.96% TP (counter-trend)
                    logger.info(f"⚠️ COUNTER-TREND: Moderate TP against trend")
            else:
                # Sideways market - standard TP
                tp_pct = base_tp_pct
            
            # MOMENTUM BOOST
            if momentum > 70:  # Strong momentum
                tp_pct *= 1.5  # Boost TP for strong momentum
                logger.info(f"⚡ MOMENTUM BOOST: Higher TP for strong momentum ({momentum:.0f})")
            elif momentum < 30:  # Weak momentum
                tp_pct *= 0.8  # Reduce TP for weak momentum
                logger.info(f"🐌 WEAK MOMENTUM: Lower TP for weak momentum ({momentum:.0f})")
            
            # VOLATILITY ADJUSTMENT
            if volatility > 2.0:  # High volatility - bigger moves possible
                tp_pct *= 1.4
                logger.info(f"🎢 HIGH VOLATILITY: Higher TP for big moves")
            elif volatility < 0.5:  # Low volatility - smaller moves
                tp_pct *= 0.9
                logger.info(f"😴 LOW VOLATILITY: Lower TP for small moves")
            
            # Cap maximum TP at 5% for safety
            tp_pct = min(tp_pct, 0.05)
            
            # Calculate final TP price
            if side == 'LONG':
                tp_price = entry_price * (1 + tp_pct)
            else:  # SHORT
                tp_price = entry_price * (1 - tp_pct)
            
            logger.info(f"🎯 DYNAMIC TP: {side} @ {entry_price:.4f} → TP @ {tp_price:.4f} ({tp_pct:.3%}) [Trend: {market_trend}, Mom: {momentum:.0f}, Vol: {volatility:.1f}]")
            return tp_price
                
        except Exception as e:
            logger.error(f"Error calculating dynamic take profit: {e}")
            # Fallback to conservative TP
            tp_pct = 0.012  # 1.2%
            if side == 'LONG':
                return entry_price * (1 + tp_pct)
            else:
                return entry_price * (1 - tp_pct)
    
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
        """
        try:
            # Define breakdown thresholds
            breakdown_threshold = 0.01  # 1% break below support or above resistance
            
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
