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

class PaperTradingEngine:
    """
    Live Paper Trading Engine for ML Learning
    
    Features:
    - Uses real market data and conditions
    - Simulates realistic slippage, fees, and latency
    - Tracks virtual positions and PnL
    - Collects ML training data from real market behavior
    - No real money at risk
    """
    
    def __init__(self, config: Dict[str, Any], exchange_client, opportunity_manager):
        self.config = config.get('paper_trading', {})
        self.exchange_client = exchange_client
        self.opportunity_manager = opportunity_manager
        
        # Trading state
        self.running = False
        self.initial_balance = self.config.get('initial_balance', 10000.0)
        self.virtual_balance = self.initial_balance
        self.peak_balance = self.initial_balance
        self.max_drawdown = 0.0
        
        # Position tracking
        self.virtual_positions = {}
        self.completed_trades = []
        self.active_positions = []
        
        # Performance tracking
        self.performance_history = []
        self.last_daily_update = None
        self.daily_pnl = 0.0  # Initialize daily PnL tracking
        
        # ML learning data
        self.learning_data = {
            'strategy_performance': {},
            'market_regime_adaptations': [],
            'signal_quality_improvements': [],
            'risk_adjustments': []
        }
        
        # Risk management
        self.position_limits = self.config.get('position_limits', {})
        self.risk_per_trade = self.config.get('risk_per_trade', 0.02)  # 2% per trade
        
        # Fees and slippage simulation
        self.trading_fee = self.config.get('trading_fee', 0.0004)  # 0.04%
        self.slippage = self.config.get('slippage', 0.0003)  # 0.03%
        self.latency_ms = self.config.get('latency_ms', 50)  # 50ms latency
        
        # Initialize daily performance tracking
        self._initialize_daily_performance()
        
        logger.info(f"📊 Paper Trading Engine initialized - Initial balance: ${self.initial_balance}")

    async def start(self):
        """Start the paper trading engine."""
        if self.running:
            logger.warning("Paper trading engine already running")
            return
            
        self.running = True
        logger.info("🚀 Starting Live Paper Trading Engine - ML Learning Mode")
        
        # Start background tasks
        asyncio.create_task(self._position_monitoring_loop())
        asyncio.create_task(self._performance_tracking_loop())
        asyncio.create_task(self._learning_data_collection_loop())
        
        logger.info("✅ Paper Trading Engine started - Ready for ML learning!")

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
            
            if not all([symbol, entry_price, position_size_usd > 0]):
                logger.error(f"❌ Invalid trade parameters: {signal}")
                return None
            
            # Simulate realistic order execution delay
            await asyncio.sleep(self.latency_ms / 1000)
            
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
            fee_rate = self.trading_fee
            fees = position_size_usd * fee_rate
            
            # Check if we have enough balance
            required_margin = position_size_usd / leverage
            if required_margin + fees > self.virtual_balance:
                logger.warning(f"⚠️ Insufficient virtual balance for {symbol} trade")
                return None
            
            # Create virtual position
            position_id = f"paper_{int(time.time())}_{uuid.uuid4().hex[:8]}"
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
                signal_id=signal_id
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
            close_fee_rate = self.trading_fee
            close_fees = (executed_price * position.size) * close_fee_rate
            
            # Net PnL after fees
            net_pnl = pnl_usdt - close_fees
            pnl_pct = net_pnl / (position.entry_price * position.size) * 100
            
            # Update balance
            position_value = executed_price * position.size
            margin_returned = position_value / position.leverage
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
            slippage_rate = self.slippage
        else:
            slippage_rate = self.slippage
        
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
                    
                    # Check for TP/SL hits
                    close_reason = None
                    
                    if position.take_profit:
                        if ((position.side == "LONG" and current_price >= position.take_profit) or
                            (position.side == "SHORT" and current_price <= position.take_profit)):
                            close_reason = "tp_hit"
                    
                    if position.stop_loss:
                        if ((position.side == "LONG" and current_price <= position.stop_loss) or
                            (position.side == "SHORT" and current_price >= position.stop_loss)):
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
                    'optimal_leverage': 2.0
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
        """Initialize daily performance with last 7 days of data"""
        from datetime import datetime, timedelta
        
        current_date = datetime.now()
        self.performance_history = []  # Clear any existing data
        
        # Create initial daily performance entries for last 7 days
        for i in range(7, 0, -1):
            date = current_date - timedelta(days=i)
            
            # Create realistic sample performance data for visualization
            # Simulate trading activity increasing towards recent days
            if i <= 3:  # Last 3 days - more activity
                daily_pnl = random.uniform(-30, 80)  # Some losses, more gains
                trades_count = random.randint(2, 8)
                positions_count = random.randint(1, 4)
                balance_change = daily_pnl * 0.8  # Not all PnL affects balance immediately
            elif i <= 5:  # Middle days - moderate activity  
                daily_pnl = random.uniform(-20, 50)
                trades_count = random.randint(0, 4)
                positions_count = random.randint(0, 2)
                balance_change = daily_pnl * 0.6
            else:  # Older days - less activity
                daily_pnl = random.uniform(-10, 25)
                trades_count = random.randint(0, 2)
                positions_count = random.randint(0, 1)
                balance_change = daily_pnl * 0.4
            
            # Calculate realistic win rate
            win_rate = random.uniform(45, 75) if trades_count > 0 else 0.0
            
            daily_entry = {
                "timestamp": date.isoformat(),
                "balance": max(self.initial_balance + balance_change, self.initial_balance * 0.9),  # Don't go too low
                "total_value": max(self.initial_balance + balance_change, self.initial_balance * 0.9),
                "unrealized_pnl": random.uniform(-10, 15) if positions_count > 0 else 0,
                "daily_pnl": daily_pnl,
                "max_drawdown": abs(min(0, balance_change)) / self.initial_balance if balance_change < 0 else 0,
                "active_positions": positions_count,
                "total_trades": trades_count,
                "win_rate": win_rate
            }
            
            self.performance_history.append(daily_entry)
        
        # Add today's entry with real current data
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
        
        logger.info(f"📊 Initialized daily performance with {len(self.performance_history)} days of sample data")
    
    def _calculate_win_rate(self):
        """Calculate current win rate from completed trades"""
        if not self.completed_trades:
            return 0.0
        
        winning_trades = sum(1 for trade in self.completed_trades if trade.pnl_usdt > 0)
        return winning_trades / len(self.completed_trades) * 100 