"""
Live Paper Trading Engine for ML Learning
Simulates real trading conditions using live market data for safe ML training.
"""

import asyncio
import logging
import time
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import json
import uuid

logger = logging.getLogger(__name__)

@dataclass
class VirtualPosition:
    """Represents a virtual trading position for paper trading."""
    position_id: str
    symbol: str
    side: str  # 'LONG' or 'SHORT'
    entry_price: float
    current_price: float
    size: float
    leverage: float
    entry_time: datetime
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    fees_paid: float = 0.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    strategy: str = "unknown"
    signal_id: Optional[str] = None
    status: str = "active"  # active, closed, liquidated
    # Floor protection fields
    absolute_floor_profit: float = 7.0  # $7 net floor
    highest_profit_ever: float = 0.0
    profit_floor_activated: bool = False
    # Net-dollar targets (after fees)
    tp_net_usd: float = 0.0  # Net USD take profit target
    sl_net_usd: float = 0.0  # Net USD stop loss target
    floor_net_usd: float = 0.0  # Net USD floor target
    # Stake (margin) used for this position
    stake_usd: float = 0.0

@dataclass
class VirtualTrade:
    """Represents a completed virtual trade for ML learning."""
    trade_id: str
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    size: float
    leverage: float
    entry_time: datetime
    exit_time: datetime
    pnl_usdt: float
    pnl_pct: float
    fees_total: float
    strategy: str
    signal_id: Optional[str]
    exit_reason: str  # tp_hit, sl_hit, manual, timeout, liquidation
    market_conditions: Dict[str, Any]

class EnhancedPaperTradingEngine:
    """
    Live Paper Trading Engine for ML Learning
    
    Features:
    - Uses real market data and conditions
    - Simulates realistic slippage, fees, and latency
    - Tracks virtual positions and PnL
    - Collects ML training data from real market behavior
    - No real money at risk
    """
    
    def __init__(self, config: Dict[str, Any], exchange_client, opportunity_manager: Optional[Any] = None):
        """Initialize paper trading engine with virtual balance and ML learning capabilities."""
        if exchange_client is None:
            raise ValueError("EnhancedPaperTradingEngine requires an exchange_client")
        self.config = config.get('paper_trading', {})
        self.exchange_client = exchange_client
        self.opportunity_manager = opportunity_manager
        
        # Core configuration with defaults
        self.initial_balance = float(self.config.get('initial_balance', 10000.0))
        self.virtual_balance = self.initial_balance  # Start with full balance
        self.mode = self.config.get('mode', 'live_learning')
        self.use_real_market_data = self.config.get('use_real_market_data', True)
        self.simulate_real_conditions = self.config.get('simulate_real_conditions', True)
        self.learning_enabled = self.config.get('learning_enabled', True)
        
        # Trading simulation parameters
        self.slippage = self.config.get('slippage', {})
        self.fees = self.config.get('fees', {})
        self.latency = self.config.get('latency', {})
        
        # Position management
        self.virtual_positions: Dict[str, VirtualPosition] = {}
        self.completed_trades: List[VirtualTrade] = []
        self.daily_pnl = 0.0
        self.peak_balance = self.initial_balance
        self.max_drawdown = 0.0
        
        # ML learning data
        self.learning_data = {
            'win_rate': 0.0,
            'strategy_performance': {},
            'learning_insights': [],
            'market_regime_accuracy': 0.0,
            'signal_confidence_improvement': 0.0,
            'trades_executed': 0,
            'total_pnl': 0.0
        }
        
        # Performance tracking
        self.performance_history = []
        self.start_time = None
        self.running = False
        
        # Initialize daily performance with sample data
        self._initialize_daily_performance()
        
        logger.info(f"📊 Paper Trading Engine initialized - Virtual Balance: ${self.virtual_balance:,.2f}")

    async def start(self):
        """Start the paper trading engine and background loops."""
        if self.running:
            return
        self.running = True
        self.start_time = datetime.now()
        # Start monitoring and performance loops
        asyncio.create_task(self._position_monitoring_loop())
        asyncio.create_task(self._performance_tracking_loop())
        asyncio.create_task(self._learning_data_collection_loop())
        # NEW: start unified signal collection loop
        asyncio.create_task(self._signal_collection_loop())

    async def stop(self):
        """Stop the paper trading engine."""
        self.running = False
        
        # Save final learning data
        await self._save_learning_data()
        
        logger.info("🛑 Paper Trading Engine stopped")

    async def execute_virtual_trade(self, signal: Dict[str, Any], position_size_usd: float) -> Optional[str]:
        """
        Execute a virtual trade based on a signal.
        Returns position_id if successful, None if failed.
        """
        try:
            symbol = signal.get('symbol', '')
            direction = signal.get('direction', 'LONG')
            entry_price = signal.get('entry_price', 0)
            stop_loss = signal.get('stop_loss')
            take_profit = signal.get('take_profit')
            strategy = signal.get('strategy', 'unknown')
            signal_id = signal.get('signal_id')
            # Net-dollar targets
            tp_net_usd = signal.get('tp_net_usd', 0.0)
            sl_net_usd = signal.get('sl_net_usd', 0.0)
            floor_net_usd = signal.get('floor_net_usd', 0.0)
            
            if not all([symbol, entry_price, position_size_usd > 0]):
                logger.error(f"❌ Invalid trade parameters: {signal}")
                return None
            
            # Simulate realistic order execution delay
            await asyncio.sleep(self.latency.get('ms', 50) / 1000)
            
            # Get current market price for slippage calculation
            current_price = await self._get_current_market_price(symbol)
            if not current_price:
                logger.error(f"❌ Could not get market price for {symbol}")
                return None
            
            # Apply slippage
            executed_price = self._apply_slippage(current_price, direction, order_type="market")
            
            # Calculate position size
            leverage = signal.get('optimal_leverage', 1.0)
            size = position_size_usd / executed_price
            
            # Calculate fees
            fee_rate = self.fees.get('rate', 0.0004)  # 0.04%
            notional_value = position_size_usd * leverage
            fees = position_size_usd * fee_rate  # Fee on stake (not notional)
            
            # Check if we have enough balance
            required_margin = position_size_usd  # Full position size is the margin stake
            if required_margin + fees > self.virtual_balance:
                logger.warning(f"⚠️ Insufficient virtual balance for {symbol} trade")
                return None
            
            # Create virtual position
            position_id = f"paper_{int(time.time())}_{uuid.uuid4().hex[:8]}"
            
            # Get floor configuration from config
            paper_config = self.config.get('paper_trading', {})
            absolute_floor_dollars = float(paper_config.get('absolute_floor_dollars', 15.0))
            # Convert gross floor to net floor (subtract fees on stake)
            fee_rate = self.fees.get('rate', 0.0004)
            total_fees = position_size_usd * fee_rate * 2  # Entry + exit fees on stake
            net_floor = absolute_floor_dollars - total_fees
            
            position = VirtualPosition(
                position_id=position_id,
                symbol=symbol,
                side=direction,
                entry_price=executed_price,
                current_price=executed_price,
                size=size,
                leverage=leverage,
                entry_time=datetime.now(),
                fees_paid=fees,
                stop_loss=stop_loss,
                take_profit=take_profit,
                strategy=strategy,
                signal_id=signal_id,
                absolute_floor_profit=net_floor,  # Set net floor value
                highest_profit_ever=0.0,
                profit_floor_activated=False,
                tp_net_usd=tp_net_usd,
                sl_net_usd=sl_net_usd,
                floor_net_usd=floor_net_usd,
                stake_usd=position_size_usd
            )
            
            # Update balance
            self.virtual_balance -= (required_margin + fees)
            
            # Store position
            self.virtual_positions[position_id] = position
            
            # Update learning data
            self.learning_data['trades_executed'] += 1
            await self._log_trade_execution(position, signal)
            
            logger.info(f"📈 Virtual {direction} position opened: {symbol} @ ${executed_price:.4f} "
                       f"(Size: ${position_size_usd:.2f}, Fees: ${fees:.2f})")
            
            return position_id
            
        except Exception as e:
            logger.error(f"❌ Error executing virtual trade: {e}")
            return None

    async def close_virtual_position(self, position_id: str, reason: str = "manual") -> Optional[VirtualTrade]:
        """Close a virtual position and return the completed trade."""
        try:
            if position_id not in self.virtual_positions:
                logger.error(f"❌ Position {position_id} not found")
                return None
            
            position = self.virtual_positions[position_id]
            
            # Get current market price
            current_price = await self._get_current_market_price(position.symbol)
            if not current_price:
                logger.error(f"❌ Could not get market price for {position.symbol}")
                return None
            
            # Apply slippage for closing
            executed_price = self._apply_slippage(current_price, 
                                                "SELL" if position.side == "LONG" else "BUY", 
                                                order_type="market")
            
            # Calculate PnL
            if position.side == "LONG":
                pnl_usdt = (executed_price - position.entry_price) * position.size
            else:  # SHORT
                pnl_usdt = (position.entry_price - executed_price) * position.size
            
            # Apply leverage
            pnl_usdt *= position.leverage
            
            # Calculate fees for closing
            close_fee_rate = self.fees.get('close_rate', 0.0004)
            position_value = executed_price * position.size
            notional_value = position_value * position.leverage
            close_fees = position.stake_usd * close_fee_rate  # Fee on stake

            # Net PnL after fees (entry + exit)
            net_pnl = pnl_usdt - position.fees_paid - close_fees
            pnl_pct = net_pnl / (position.entry_price * position.size) * 100
            
            # Update balance
            margin_returned = position.stake_usd  # Return the original stake
            self.virtual_balance += margin_returned + net_pnl
            
            # Create completed trade record
            trade = VirtualTrade(
                trade_id=f"trade_{position_id}",
                symbol=position.symbol,
                side=position.side,
                entry_price=position.entry_price,
                exit_price=executed_price,
                size=position.size,
                leverage=position.leverage,
                entry_time=position.entry_time,
                exit_time=datetime.now(),
                pnl_usdt=net_pnl,
                pnl_pct=pnl_pct,
                fees_total=position.fees_paid + close_fees,
                strategy=position.strategy,
                signal_id=position.signal_id,
                exit_reason=reason,
                market_conditions=await self._get_market_conditions(position.symbol)
            )
            
            # Store completed trade and remove position
            self.completed_trades.append(trade)
            del self.virtual_positions[position_id]
            
            # Update performance metrics
            self.daily_pnl += net_pnl
            self.learning_data['total_pnl'] += net_pnl
            await self._update_performance_metrics()
            
            # Log for ML learning
            await self._log_trade_completion(trade)
            
            logger.info(f"📊 Virtual position closed: {position.symbol} {position.side} "
                       f"PnL: ${net_pnl:.2f} ({pnl_pct:.2f}%) - Reason: {reason}")
            
            return trade
            
        except Exception as e:
            logger.error(f"❌ Error closing virtual position: {e}")
            return None

    def _apply_slippage(self, market_price: float, direction: str, order_type: str = "market") -> float:
        """Apply realistic slippage to order execution."""
        if order_type == "market":
            slippage_rate = self.slippage.get('rate', 0.0003)  # 0.03%
        else:
            slippage_rate = self.slippage.get('rate', 0.0003)  # 0.03%
        
        if direction.upper() in ['LONG', 'BUY']:
            # Buying - slippage increases price
            return market_price * (1 + slippage_rate)
        else:
            # Selling - slippage decreases price
            return market_price * (1 - slippage_rate)

    async def _get_current_market_price(self, symbol: str) -> Optional[float]:
        """Get current market price for a symbol."""
        try:
            if self.exchange_client:
                ticker = await self.exchange_client.get_ticker_24h(symbol)
                return float(ticker.get('lastPrice', 0))
            return None
        except Exception as e:
            logger.error(f"Error getting market price for {symbol}: {e}")
            return None

    async def _get_market_conditions(self, symbol: str) -> Dict[str, Any]:
        """Get current market conditions for ML learning."""
        try:
            conditions = {
                'timestamp': datetime.now().isoformat(),
                'symbol': symbol,
                'market_regime': 'unknown',
                'volatility': 0.0,
                'volume_24h': 0.0,
                'funding_rate': 0.0
            }
            
            if self.exchange_client:
                ticker = await self.exchange_client.get_ticker_24h(symbol)
                conditions.update({
                    'volume_24h': float(ticker.get('volume', 0)),
                    'price_change_24h_pct': float(ticker.get('priceChangePercent', 0))
                })
            
            return conditions
        except Exception as e:
            logger.warning(f"Could not get market conditions for {symbol}: {e}")
            return {'timestamp': datetime.now().isoformat(), 'symbol': symbol}

    async def _position_monitoring_loop(self):
        """Monitor virtual positions for TP/SL hits and updates."""
        logger.info("🔍 Starting position monitoring loop")
        
        while self.running:
            try:
                positions_to_close = []
                
                for position_id, position in self.virtual_positions.items():
                    # Get current price
                    current_price = await self._get_current_market_price(position.symbol)
                    if not current_price:
                        continue
                    
                    position.current_price = current_price
                    
                    # Calculate unrealized PnL
                    if position.side == "LONG":
                        pnl = (current_price - position.entry_price) * position.size * position.leverage
                    else:  # SHORT
                        pnl = (position.entry_price - current_price) * position.size * position.leverage
                    
                    position.unrealized_pnl = pnl
                    
                    # Update highest profit ever for floor protection
                    position.highest_profit_ever = max(position.highest_profit_ever, pnl)
                    
                    # Calculate exit fees for this position
                    exit_fee_rate = self.fees.get('close_rate', 0.0004)
                    # Estimate exit fees on stake basis
                    exit_fees = position.stake_usd * exit_fee_rate

                    # Calculate net PnL after all fees (entry + exit)
                    total_fees = position.fees_paid + exit_fees
                    net_pnl = pnl - total_fees
                    
                    # Use per-position rule-based targets (calculated by profit scraping engine)
                    # These targets already account for fees and are specific to this position
                    net_target = position.tp_net_usd if position.tp_net_usd > 0 else 0
                    net_floor = position.floor_net_usd if position.floor_net_usd > 0 else position.absolute_floor_profit
                    net_stop_loss = -position.sl_net_usd if position.sl_net_usd > 0 else 0  # Negative for stop loss
                    
                    # Check for TP/SL hits using per-position rule-based thresholds
                    close_reason = None
                    
                    # RULE 1: PRIMARY TARGET (per-position take profit)
                    if net_pnl >= net_target and net_target > 0:
                        close_reason = "tp_hit"
                    
                    # RULE 2: FLOOR PROTECTION (per-position floor)
                    elif position.highest_profit_ever >= net_floor and net_floor > 0:
                        if not position.profit_floor_activated:
                            position.profit_floor_activated = True
                            logger.info(f"🛡️ FLOOR ACTIVATED: {position.symbol} reached ${position.highest_profit_ever:.2f}")
                        
                        if net_pnl <= net_floor:  # Close as soon as PnL touches the floor
                            close_reason = "absolute_floor_15_dollars"
                    
                    # RULE 3: STOP LOSS (per-position stop loss)
                    elif net_pnl <= net_stop_loss and net_stop_loss < 0:
                        close_reason = "sl_hit"
                    
                    # Check for liquidation (simplified)
                    liquidation_price = self._calculate_liquidation_price(position)
                    if liquidation_price and ((position.side == "LONG" and current_price <= liquidation_price) or
                                            (position.side == "SHORT" and current_price >= liquidation_price)):
                        close_reason = "liquidation"
                    
                    if close_reason:
                        positions_to_close.append((position_id, close_reason))
                
                # Close positions that hit TP/SL
                for position_id, reason in positions_to_close:
                    await self.close_virtual_position(position_id, reason)
                
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logger.error(f"Error in position monitoring loop: {e}")
                await asyncio.sleep(10)

    def _calculate_liquidation_price(self, position: VirtualPosition) -> Optional[float]:
        """Calculate approximate liquidation price."""
        try:
            # Simplified liquidation calculation
            margin_ratio = 0.05  # 5% maintenance margin
            
            if position.side == "LONG":
                return position.entry_price * (1 - (1/position.leverage) + margin_ratio)
            else:  # SHORT
                return position.entry_price * (1 + (1/position.leverage) - margin_ratio)
        except:
            return None

    async def _performance_tracking_loop(self):
        """Track performance metrics for ML learning."""
        logger.info("📊 Starting performance tracking loop")
        
        while self.running:
            try:
                # Update performance metrics
                await self._update_performance_metrics()
                
                # Log hourly performance summary
                current_time = datetime.now()
                if current_time.minute == 0:  # Top of the hour
                    await self._log_hourly_summary()
                
                await asyncio.sleep(300)  # Update every 5 minutes
                
            except Exception as e:
                logger.error(f"Error in performance tracking: {e}")
                await asyncio.sleep(60)

    async def _learning_data_collection_loop(self):
        """Collect and analyze learning data."""
        logger.info("🧠 Starting ML learning data collection")
        
        while self.running:
            try:
                # Auto-execute trades from opportunities (for testing and learning)
                await self._auto_execute_demo_trades()
                
                # Analyze strategy performance
                await self._analyze_strategy_performance()
                
                # Update learning insights
                await self._generate_learning_insights()
                
                # Save learning data periodically
                await self._save_learning_data()
                
                await asyncio.sleep(600)  # Update every 10 minutes
                
            except Exception as e:
                logger.error(f"Error in learning data collection: {e}")
                await asyncio.sleep(60)

    async def _auto_execute_demo_trades(self):
        """Auto-execute demo trades for learning purposes when opportunities are available."""
        try:
            if not self.opportunity_manager:
                return
            
            # Get current opportunities
            opportunities = self.opportunity_manager.get_opportunities()
            
            # Limit to 3 active positions max for demo
            if len(self.virtual_positions) >= 3:
                return
            
            # Execute 1-2 random trades for learning
            import random
            if opportunities and len(opportunities) > 0 and random.random() < 0.3:  # 30% chance
                selected_opp = random.choice(opportunities)
                
                # Create signal from opportunity
                signal = {
                    'symbol': selected_opp.get('symbol', 'BTCUSDT'),
                    'direction': selected_opp.get('direction', 'LONG'),
                    'entry_price': selected_opp.get('entry_price', 50000),
                    'stop_loss': selected_opp.get('stop_loss'),
                    'take_profit': selected_opp.get('take_profit'),
                    'strategy': 'auto_demo',
                    'signal_id': f"demo_{int(time.time())}",
                    'optimal_leverage': 2.0,
                    'tp_net_usd': 0.0, # No specific target for demo
                    'sl_net_usd': 0.0, # No specific target for demo
                    'floor_net_usd': 0.0 # No specific target for demo
                }
                
                # Execute virtual trade with small position size
                position_size = random.uniform(100, 500)  # $100-500 per trade
                position_id = await self.execute_virtual_trade(signal, position_size)
                
                if position_id:
                    logger.info(f"🎯 Auto-executed demo trade: {signal['symbol']} {signal['direction']} ${position_size:.0f}")
                
        except Exception as e:
            logger.error(f"Error in auto-executing demo trades: {e}")

    async def _update_performance_metrics(self):
        """Update key performance metrics."""
        try:
            current_balance = self.virtual_balance
            
            # Calculate total portfolio value (including unrealized PnL)
            total_unrealized = sum(pos.unrealized_pnl for pos in self.virtual_positions.values())
            total_portfolio_value = current_balance + total_unrealized
            
            # Update peak and drawdown
            if total_portfolio_value > self.peak_balance:
                self.peak_balance = total_portfolio_value
            
            current_drawdown = (self.peak_balance - total_portfolio_value) / self.peak_balance
            if current_drawdown > self.max_drawdown:
                self.max_drawdown = current_drawdown
            
            # Calculate win rate
            if self.completed_trades:
                winning_trades = sum(1 for trade in self.completed_trades if trade.pnl_usdt > 0)
                self.learning_data['win_rate'] = winning_trades / len(self.completed_trades)
            
            # Store performance snapshot
            self.performance_history.append({
                'timestamp': datetime.now().isoformat(),
                'balance': current_balance,
                'total_value': total_portfolio_value,
                'unrealized_pnl': total_unrealized,
                'daily_pnl': self.daily_pnl,
                'max_drawdown': self.max_drawdown,
                'active_positions': len(self.virtual_positions),
                'total_trades': len(self.completed_trades),
                'win_rate': self.learning_data['win_rate']
            })
            
            # Keep only last 1000 performance records
            if len(self.performance_history) > 1000:
                self.performance_history = self.performance_history[-1000:]
                
        except Exception as e:
            logger.error(f"Error updating performance metrics: {e}")

    async def _analyze_strategy_performance(self):
        """Analyze performance by strategy for ML insights."""
        try:
            strategy_stats = {}
            
            for trade in self.completed_trades:
                strategy = trade.strategy
                if strategy not in strategy_stats:
                    strategy_stats[strategy] = {
                        'total_trades': 0,
                        'winning_trades': 0,
                        'total_pnl': 0.0,
                        'avg_pnl': 0.0,
                        'win_rate': 0.0,
                        'symbols': set()
                    }
                
                stats = strategy_stats[strategy]
                stats['total_trades'] += 1
                stats['total_pnl'] += trade.pnl_usdt
                stats['symbols'].add(trade.symbol)
                
                if trade.pnl_usdt > 0:
                    stats['winning_trades'] += 1
                
                # Calculate averages
                stats['avg_pnl'] = stats['total_pnl'] / stats['total_trades']
                stats['win_rate'] = stats['winning_trades'] / stats['total_trades']
            
            # Convert sets to lists for JSON serialization
            for strategy in strategy_stats:
                strategy_stats[strategy]['symbols'] = list(strategy_stats[strategy]['symbols'])
            
            self.learning_data['strategy_performance'] = strategy_stats
            
        except Exception as e:
            logger.error(f"Error analyzing strategy performance: {e}")

    async def _generate_learning_insights(self):
        """Generate ML learning insights from trading data."""
        try:
            insights = []
            
            # Insight 1: Best performing strategies
            if self.learning_data['strategy_performance']:
                best_strategy = max(self.learning_data['strategy_performance'].items(),
                                  key=lambda x: x[1]['win_rate'])
                insights.append(f"Best performing strategy: {best_strategy[0]} "
                              f"(Win rate: {best_strategy[1]['win_rate']:.1%})")
            
            # Insight 2: Portfolio performance
            total_return = (self.virtual_balance - self.initial_balance) / self.initial_balance
            insights.append(f"Total return: {total_return:.1%} "
                          f"(${self.virtual_balance:.2f} from ${self.initial_balance:.2f})")
            
            # Insight 3: Risk metrics
            insights.append(f"Max drawdown: {self.max_drawdown:.1%}")
            
            # Insight 4: Trading activity
            insights.append(f"Total trades executed: {len(self.completed_trades)}, "
                          f"Active positions: {len(self.virtual_positions)}")
            
            self.learning_data['learning_insights'] = insights
            
        except Exception as e:
            logger.error(f"Error generating learning insights: {e}")

    async def _log_trade_execution(self, position: VirtualPosition, signal: Dict[str, Any]):
        """Log trade execution for ML learning."""
        try:
            log_data = {
                'type': 'trade_execution',
                'timestamp': datetime.now().isoformat(),
                'position_id': position.position_id,
                'symbol': position.symbol,
                'strategy': position.strategy,
                'signal_data': signal,
                'execution_price': position.entry_price,
                'market_conditions': await self._get_market_conditions(position.symbol)
            }
            
            # In a real implementation, this would go to a learning database
            logger.info(f"📚 ML Log - Trade Execution: {json.dumps(log_data, indent=2)}")
            
        except Exception as e:
            logger.error(f"Error logging trade execution: {e}")

    async def _log_trade_completion(self, trade: VirtualTrade):
        """Log trade completion for ML learning."""
        try:
            log_data = {
                'type': 'trade_completion',
                'timestamp': datetime.now().isoformat(),
                'trade_id': trade.trade_id,
                'symbol': trade.symbol,
                'strategy': trade.strategy,
                'pnl_usdt': trade.pnl_usdt,
                'pnl_pct': trade.pnl_pct,
                'exit_reason': trade.exit_reason,
                'duration_minutes': (trade.exit_time - trade.entry_time).total_seconds() / 60,
                'market_conditions': trade.market_conditions
            }
            
            # In a real implementation, this would go to a learning database
            logger.info(f"📚 ML Log - Trade Completion: {json.dumps(log_data, indent=2)}")
            
        except Exception as e:
            logger.error(f"Error logging trade completion: {e}")

    async def _log_hourly_summary(self):
        """Log hourly performance summary."""
        try:
            summary = {
                'type': 'hourly_summary',
                'timestamp': datetime.now().isoformat(),
                'virtual_balance': self.virtual_balance,
                'daily_pnl': self.daily_pnl,
                'active_positions': len(self.virtual_positions),
                'completed_trades_today': len([t for t in self.completed_trades 
                                             if t.exit_time.date() == datetime.now().date()]),
                'win_rate': self.learning_data['win_rate'],
                'max_drawdown': self.max_drawdown
            }
            
            logger.info(f"📊 Hourly Summary: Virtual Balance: ${self.virtual_balance:.2f}, "
                       f"Daily PnL: ${self.daily_pnl:.2f}, "
                       f"Active Positions: {len(self.virtual_positions)}, "
                       f"Win Rate: {self.learning_data['win_rate']:.1%}")
            
        except Exception as e:
            logger.error(f"Error logging hourly summary: {e}")

    async def _save_learning_data(self):
        """Save learning data for ML training."""
        try:
            # In a real implementation, this would save to a persistent database
            learning_export = {
                'paper_trading_session': {
                    'start_time': datetime.now().isoformat(),
                    'initial_balance': self.initial_balance,
                    'current_balance': self.virtual_balance,
                    'learning_data': self.learning_data,
                    'performance_history': self.performance_history[-100:],  # Last 100 records
                    'completed_trades': [
                        {
                            'symbol': trade.symbol,
                            'strategy': trade.strategy,
                            'pnl_pct': trade.pnl_pct,
                            'exit_reason': trade.exit_reason,
                            'duration': (trade.exit_time - trade.entry_time).total_seconds() / 60
                        }
                        for trade in self.completed_trades[-50:]  # Last 50 trades
                    ]
                }
            }
            
            logger.debug("💾 Learning data saved for ML training")
            
        except Exception as e:
            logger.error(f"Error saving learning data: {e}")

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get current portfolio summary for monitoring."""
        try:
            total_unrealized = sum(pos.unrealized_pnl for pos in self.virtual_positions.values())
            total_value = self.virtual_balance + total_unrealized
            total_return = (total_value - self.initial_balance) / self.initial_balance
            
            return {
                'virtual_balance': self.virtual_balance,
                'total_portfolio_value': total_value,
                'unrealized_pnl': total_unrealized,
                'total_return_pct': total_return * 100,
                'daily_pnl': self.daily_pnl,
                'max_drawdown_pct': self.max_drawdown * 100,
                'active_positions': len(self.virtual_positions),
                'completed_trades': len(self.completed_trades),
                'win_rate_pct': self.learning_data['win_rate'] * 100,
                'total_fees_paid': sum(trade.fees_total for trade in self.completed_trades),
                'learning_insights': self.learning_data['learning_insights']
            }
        except Exception as e:
            logger.error(f"Error getting portfolio summary: {e}")
            return {}

    def get_active_positions(self) -> List[Dict[str, Any]]:
        """Get list of active virtual positions."""
        try:
            positions = []
            for position in self.virtual_positions.values():
                positions.append({
                    'position_id': position.position_id,
                    'symbol': position.symbol,
                    'side': position.side,
                    'entry_price': position.entry_price,
                    'current_price': position.current_price,
                    'size': position.size,
                    'leverage': position.leverage,
                    'unrealized_pnl': position.unrealized_pnl,
                    'unrealized_pnl_pct': (position.unrealized_pnl / (position.entry_price * position.size)) * 100,
                    'age_minutes': (datetime.now() - position.entry_time).total_seconds() / 60,
                    'strategy': position.strategy,
                    'stop_loss': position.stop_loss,
                    'take_profit': position.take_profit
                })
            return positions
        except Exception as e:
            logger.error(f"Error getting active positions: {e}")
            return []

    def _initialize_daily_performance(self):
        """Initialize daily performance with empty data - no sample data"""
        from datetime import datetime
        
        current_date = datetime.now()
        
        # Force clear all existing data to remove persistent duplicates
        self.performance_history = []
        
        # Add only today's entry with real current data
        today_entry = {
            "timestamp": current_date.isoformat(),
            "balance": self.virtual_balance,
            "total_value": self.virtual_balance,
            "unrealized_pnl": 0,
            "daily_pnl": 0.0,
            "max_drawdown": self.max_drawdown,
            "active_positions": len(self.virtual_positions),
            "total_trades": len(self.completed_trades),
            "win_rate": self._calculate_win_rate()
        }
        
        self.performance_history.append(today_entry)
        self.last_daily_update = current_date.date()
        
        logger.info(f"📊 Initialized fresh daily performance - single entry for today")
    
    def _calculate_win_rate(self):
        """Calculate current win rate from completed trades"""
        if not self.completed_trades:
            return 0.0
        
        winning_trades = sum(1 for trade in self.completed_trades if trade.pnl_usdt > 0)
        return winning_trades / len(self.completed_trades) * 100 

    async def _signal_collection_loop(self):
        """Collect signals from profit scraping and opportunity manager and execute trades."""
        logger.info("🔄 Starting unified signal collection loop")
        poll_interval_sec = 5
        while self.running:
            try:
                # Respect max open positions
                max_positions = int(self.config.get('max_positions', 20))
                if len(self.virtual_positions) >= max_positions:
                    await asyncio.sleep(poll_interval_sec)
                    continue

                # Collect from profit scraping engine if available
                profit_signals: List[Dict[str, Any]] = []
                if hasattr(self, 'profit_scraping_engine') and self.profit_scraping_engine:
                    try:
                        profit_signals = await self.profit_scraping_engine.get_ready_to_trade_signals()
                    except Exception as e:
                        logger.warning(f"Error fetching profit scraping signals: {e}")

                # Collect from opportunity manager if available
                opp_signals: List[Dict[str, Any]] = []
                if self.opportunity_manager:
                    try:
                        opportunities = self.opportunity_manager.get_opportunities()
                        if isinstance(opportunities, dict):
                            # Legacy/dict shape: { symbol: [opportunities...] }
                            for symbol, opp_list in opportunities.items():
                                for opp in opp_list:
                                    if not opp.get('tradable', True):
                                        continue
                                    direction = opp.get('direction') or ('LONG' if opp.get('entry', 0) <= opp.get('take_profit', 0) else 'SHORT')
                                    unified = {
                                        'symbol': symbol,
                                        'direction': direction,
                                        'entry_price': opp.get('entry') or opp.get('entry_price'),
                                        'take_profit': opp.get('take_profit'),
                                        'stop_loss': opp.get('stop_loss'),
                                        'confidence': opp.get('confidence', opp.get('confidence_score', 0.6)),
                                        'strategy': opp.get('strategy', 'opportunity_manager'),
                                        'signal_source': 'opportunity_manager',
                                        'signal_id': f"oppmgr_{symbol}_{int(time.time())}",
                                        'tp_net_usd': opp.get('tp_net_usd', 0.0),
                                        'sl_net_usd': opp.get('sl_net_usd', 0.0),
                                        'floor_net_usd': opp.get('floor_net_usd', 0.0),
                                        'optimal_leverage': float(self.config.get('leverage', 10.0))
                                    }
                                    opp_signals.append(unified)
                        elif isinstance(opportunities, list):
                            # New/list shape: [opportunity, ...]
                            for opp in opportunities:
                                if not opp.get('tradable', True):
                                    continue
                                symbol = opp.get('symbol')
                                if not symbol:
                                    continue
                                direction = opp.get('direction') or ('LONG' if opp.get('entry', 0) <= opp.get('take_profit', 0) else 'SHORT')
                                unified = {
                                    'symbol': symbol,
                                    'direction': direction,
                                    'entry_price': opp.get('entry') or opp.get('entry_price'),
                                    'take_profit': opp.get('take_profit'),
                                    'stop_loss': opp.get('stop_loss'),
                                    'confidence': opp.get('confidence', opp.get('confidence_score', 0.6)),
                                    'strategy': opp.get('strategy', 'opportunity_manager'),
                                    'signal_source': 'opportunity_manager',
                                    'signal_id': f"oppmgr_{symbol}_{int(time.time())}",
                                    'tp_net_usd': opp.get('tp_net_usd', 0.0),
                                    'sl_net_usd': opp.get('sl_net_usd', 0.0),
                                    'floor_net_usd': opp.get('floor_net_usd', 0.0),
                                    'optimal_leverage': float(self.config.get('leverage', 10.0))
                                }
                                opp_signals.append(unified)
                        else:
                            logger.warning("OpportunityManager.get_opportunities() returned unsupported type")
                    except Exception as e:
                        logger.warning(f"Error fetching opportunities: {e}")

                # Merge and execute, respecting limits
                for signal in (*profit_signals, *opp_signals):
                    if len(self.virtual_positions) >= max_positions:
                        break
                    try:
                        # Normalize profit scraper signal shape
                        if 'side' in signal and 'direction' not in signal:
                            signal['direction'] = signal.pop('side')
                        if 'strategy' not in signal:
                            signal['strategy'] = signal.get('signal_source', 'unknown')
                        if 'optimal_leverage' not in signal:
                            signal['optimal_leverage'] = float(self.config.get('leverage', 10.0))
                        # Execute trade with $500 stake (from config)
                        stake_amount = float(self.config.get('stake_amount', 500.0))
                        await self.execute_virtual_trade(signal, stake_amount)
                    except Exception as e:
                        logger.warning(f"Error executing unified signal: {e}")

                await asyncio.sleep(poll_interval_sec)
            except Exception as e:
                logger.error(f"Error in signal collection loop: {e}")
                await asyncio.sleep(5) 

    def connect_opportunity_manager(self, manager: Any) -> None:
        """Attach/replace the opportunity manager after construction."""
        self.opportunity_manager = manager

    def connect_profit_scraping_engine(self, engine: Any) -> None:
        """Attach/replace the profit scraping engine after construction."""
        self.profit_scraping_engine = engine 

    @property
    def is_running(self) -> bool:
        return self.running 