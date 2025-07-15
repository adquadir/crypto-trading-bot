"""
Profit Scraping Engine
Main engine that coordinates level analysis, monitoring, and trade execution
"""

import asyncio
import logging
from typing import Dict, List, Optional, Set, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import json

from .price_level_analyzer import PriceLevelAnalyzer, PriceLevel
from .magnet_level_detector import MagnetLevelDetector, MagnetLevel
from .statistical_calculator import StatisticalCalculator, TradingTargets

# Import ML learning service
try:
    from src.ml.ml_learning_service import get_ml_learning_service, TradeOutcome
except ImportError:
    async def get_ml_learning_service():
        return None
    
    class TradeOutcome:
        pass

logger = logging.getLogger(__name__)

@dataclass
class ScrapingOpportunity:
    """Represents a profit scraping opportunity"""
    symbol: str
    level: PriceLevel
    magnet_level: Optional[MagnetLevel]
    targets: TradingTargets
    current_price: float
    distance_to_level: float
    opportunity_score: int  # 0-100 overall opportunity score
    created_at: datetime
    
    def to_dict(self) -> Dict:
        return {
            'symbol': self.symbol,
            'level': self.level.to_dict(),
            'magnet_level': self.magnet_level.to_dict() if self.magnet_level else None,
            'targets': self.targets.to_dict(),
            'current_price': self.current_price,
            'distance_to_level': self.distance_to_level,
            'opportunity_score': self.opportunity_score,
            'created_at': self.created_at.isoformat()
        }

@dataclass
class ActiveTrade:
    """Represents an active profit scraping trade"""
    trade_id: str
    symbol: str
    side: str  # 'LONG' or 'SHORT'
    entry_price: float
    quantity: float
    leverage: int
    profit_target: float
    stop_loss: float
    entry_time: datetime
    level_type: str
    confidence_score: int
    
    def to_dict(self) -> Dict:
        return asdict(self)

class ProfitScrapingEngine:
    """Main profit scraping engine"""
    
    def __init__(self, exchange_client=None, paper_trading_engine=None, real_trading_engine=None):
        self.exchange_client = exchange_client
        self.paper_trading_engine = paper_trading_engine
        self.real_trading_engine = real_trading_engine
        
        # Determine which trading engine to use
        self.trading_engine = real_trading_engine if real_trading_engine else paper_trading_engine
        self.is_real_trading = real_trading_engine is not None
        
        # Core components
        self.level_analyzer = PriceLevelAnalyzer()
        self.magnet_detector = MagnetLevelDetector()
        self.stat_calculator = StatisticalCalculator()
        
        # State management
        self.active = False
        self.monitored_symbols: Set[str] = set()
        self.identified_levels: Dict[str, List[PriceLevel]] = {}
        self.magnet_levels: Dict[str, List[MagnetLevel]] = {}
        self.active_opportunities: Dict[str, List[ScrapingOpportunity]] = {}
        self.active_trades: Dict[str, ActiveTrade] = {}
        
        # Configuration
        self.max_symbols = 100  # Increased from 5 to allow more symbols
        self.max_trades_per_symbol = 2
        self.leverage = 10
        self.account_balance = 10000  # Mock balance
        self.max_risk_per_trade = 0.02  # 2% risk per trade
        
        # Performance tracking
        self.total_trades = 0
        self.winning_trades = 0
        self.total_profit = 0.0
        self.start_time = None
        
    async def start_scraping(self, symbols: List[str]) -> bool:
        """Start profit scraping for specified symbols"""
        try:
            logger.info(f"🚀 Starting profit scraping for {len(symbols)} symbols")
            
            if len(symbols) > self.max_symbols:
                symbols = symbols[:self.max_symbols]
                logger.warning(f"Limited to {self.max_symbols} symbols")
            
            self.monitored_symbols = set(symbols)
            self.active = True
            self.start_time = datetime.now()
            
            # Initial analysis for all symbols
            for symbol in symbols:
                await self._analyze_symbol(symbol)
            
            # Start monitoring loop
            asyncio.create_task(self._monitoring_loop())
            
            logger.info("✅ Profit scraping started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error starting profit scraping: {e}")
            return False
    
    async def stop_scraping(self) -> bool:
        """Stop profit scraping and close all positions"""
        try:
            logger.info("🛑 Stopping profit scraping")
            
            self.active = False
            
            # Close all active trades
            for trade_id in list(self.active_trades.keys()):
                await self._close_trade(trade_id, "MANUAL_STOP")
            
            # Clear state
            self.monitored_symbols.clear()
            self.identified_levels.clear()
            self.magnet_levels.clear()
            self.active_opportunities.clear()
            
            logger.info("✅ Profit scraping stopped")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping profit scraping: {e}")
            return False
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        try:
            while self.active:
                # Update opportunities for all symbols
                for symbol in self.monitored_symbols:
                    await self._update_opportunities(symbol)
                    await self._check_entry_conditions(symbol)
                
                # Monitor active trades
                await self._monitor_active_trades()
                
                # Re-analyze levels periodically (every 10 minutes)
                if datetime.now().minute % 10 == 0:
                    for symbol in self.monitored_symbols:
                        await self._analyze_symbol(symbol)
                
                # Wait before next iteration
                await asyncio.sleep(5)  # 5-second monitoring cycle
                
        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}")
    
    async def _analyze_symbol(self, symbol: str):
        """Analyze a symbol to identify price levels and magnets"""
        try:
            logger.info(f"🔍 Analyzing {symbol}")
            
            # Get current price
            current_price = await self._get_current_price(symbol)
            if not current_price:
                return
            
            # Analyze price levels
            price_levels = await self.level_analyzer.analyze_symbol(symbol, self.exchange_client)
            self.identified_levels[symbol] = price_levels
            
            # Detect magnet levels
            historical_data = await self.level_analyzer._get_historical_data(symbol, self.exchange_client)
            magnet_levels = self.magnet_detector.detect_magnet_levels(
                symbol, current_price, price_levels, historical_data
            )
            self.magnet_levels[symbol] = magnet_levels
            
            logger.info(f"✅ {symbol}: Found {len(price_levels)} price levels, {len(magnet_levels)} magnets")
            
        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}")
    
    async def _update_opportunities(self, symbol: str):
        """Update profit scraping opportunities for a symbol"""
        try:
            current_price = await self._get_current_price(symbol)
            if not current_price:
                return
            
            opportunities = []
            price_levels = self.identified_levels.get(symbol, [])
            magnet_levels = self.magnet_levels.get(symbol, [])
            
            # Check each price level for opportunities
            for level in price_levels:
                # Skip if too far from current price
                distance = abs(level.price - current_price) / current_price
                if distance > 0.03:  # More than 3% away
                    continue
                
                # Find matching magnet level
                matching_magnet = None
                for magnet in magnet_levels:
                    if abs(magnet.price - level.price) / level.price < 0.01:  # Within 1%
                        matching_magnet = magnet
                        break
                
                # Calculate trading targets
                historical_data = await self.level_analyzer._get_historical_data(symbol, self.exchange_client)
                if historical_data is not None:
                    targets = self.stat_calculator.calculate_targets(
                        level, current_price, historical_data, matching_magnet
                    )
                    
                    if targets and self.stat_calculator.validate_targets(targets, current_price):
                        # Calculate opportunity score
                        opportunity_score = self._calculate_opportunity_score(
                            level, targets, distance, matching_magnet
                        )
                        
                        opportunity = ScrapingOpportunity(
                            symbol=symbol,
                            level=level,
                            magnet_level=matching_magnet,
                            targets=targets,
                            current_price=current_price,
                            distance_to_level=distance,
                            opportunity_score=opportunity_score,
                            created_at=datetime.now()
                        )
                        opportunities.append(opportunity)
            
            # Sort by opportunity score and keep top opportunities
            opportunities.sort(key=lambda x: x.opportunity_score, reverse=True)
            self.active_opportunities[symbol] = opportunities[:3]  # Keep top 3
            
        except Exception as e:
            logger.error(f"Error updating opportunities for {symbol}: {e}")
    
    async def _check_entry_conditions(self, symbol: str):
        """Check if any opportunities meet entry conditions"""
        try:
            opportunities = self.active_opportunities.get(symbol, [])
            current_trades = sum(1 for trade in self.active_trades.values() if trade.symbol == symbol)
            
            # Skip if already at max trades for this symbol
            if current_trades >= self.max_trades_per_symbol:
                return
            
            current_price = await self._get_current_price(symbol)
            if not current_price:
                return
            
            for opportunity in opportunities:
                # Check if price is near the level (within 0.5%)
                distance_to_level = abs(current_price - opportunity.level.price) / opportunity.level.price
                
                if distance_to_level <= 0.005:  # Within 0.5%
                    # Additional entry validation
                    if await self._validate_entry_conditions(opportunity, current_price):
                        await self._execute_trade(opportunity, current_price)
                        break  # Only one trade per check
            
        except Exception as e:
            logger.error(f"Error checking entry conditions for {symbol}: {e}")
    
    async def _validate_entry_conditions(self, opportunity: ScrapingOpportunity, current_price: float) -> bool:
        """Validate additional entry conditions with RELAXED TREND AWARENESS for profit scraping"""
        try:
            level = opportunity.level
            symbol = opportunity.symbol
            
            # PROFIT SCRAPING FIX: Use relaxed trend filtering to allow more trades
            market_trend = await self._detect_market_trend(symbol)
            
            if level.level_type == 'support':
                # RELAXED TREND CHECK: Only block in EXTREME downtrends, allow counter-trend scalping
                if market_trend == 'strong_downtrend':
                    # Check if support is VERY strong before blocking
                    if level.strength_score < 80:  # Only block weak support in strong downtrends
                        logger.info(f"❌ TREND FILTER: Skipping weak LONG {symbol} - strong downtrend + weak support")
                        return False
                    else:
                        logger.info(f"✅ ALLOWING COUNTER-TREND: Strong support {symbol} @ {level.price:.2f} (strength: {level.strength_score})")
                
                # Validate support is holding (bounce confirmation) - RELAXED
                if not await self._validate_support_bounce(symbol, level.price, current_price):
                    # Don't block completely, just log warning
                    logger.warning(f"⚠️ SUPPORT WARNING: {symbol} support not fully confirmed, but allowing trade")
                
                # Price approach validation
                return current_price <= level.price * 1.005  # Within 0.5% above
            
            elif level.level_type == 'resistance':
                # RELAXED TREND CHECK: Only block in EXTREME uptrends, allow counter-trend scalping
                if market_trend == 'strong_uptrend':
                    # Check if resistance is VERY strong before blocking
                    if level.strength_score < 80:  # Only block weak resistance in strong uptrends
                        logger.info(f"❌ TREND FILTER: Skipping weak SHORT {symbol} - strong uptrend + weak resistance")
                        return False
                    else:
                        logger.info(f"✅ ALLOWING COUNTER-TREND: Strong resistance {symbol} @ {level.price:.2f} (strength: {level.strength_score})")
                
                # Price approach validation
                return current_price >= level.price * 0.995  # Within 0.5% below
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating entry conditions: {e}")
            return False
    
    async def _execute_trade(self, opportunity: ScrapingOpportunity, current_price: float):
        """Execute a profit scraping trade"""
        try:
            logger.info(f"🎯 Executing trade for {opportunity.symbol} at ${current_price:.2f}")
            
            # Determine trade direction
            if opportunity.level.level_type == 'support':
                side = 'LONG'  # Buy at support
            else:  # resistance
                side = 'SHORT'  # Sell at resistance
            
            # Calculate position size
            position_size = self.stat_calculator.get_optimal_position_size(
                opportunity.targets, self.account_balance, self.max_risk_per_trade
            )
            
            # Get ML recommendation before executing trade
            ml_service = await get_ml_learning_service()
            if ml_service:
                signal_data = {
                    'strategy_type': 'profit_scraping',
                    'confidence': opportunity.targets.confidence_score / 100.0,
                    'market_regime': 'level_based',
                    'volatility_regime': 'medium',
                    'symbol': opportunity.symbol,
                    'side': side
                }
                
                recommendation = await ml_service.get_signal_recommendation(signal_data)
                
                if not recommendation.should_take_trade:
                    logger.info(f"❌ ML recommendation: Skip trade for {opportunity.symbol} - {recommendation.reasoning}")
                    return
                
                # Adjust position size based on ML recommendation
                position_size *= recommendation.recommended_position_size / 0.01  # Scale based on ML recommendation
                logger.info(f"🧠 ML recommendation: Take trade with adjusted confidence {recommendation.confidence_adjustment:+.2f}")
            
            # Execute trade through appropriate trading engine
            trade_result = None
            
            if self.is_real_trading and self.real_trading_engine:
                # REAL TRADING EXECUTION
                logger.warning(f"🚨 EXECUTING REAL TRADE: {side} {opportunity.symbol} @ ${current_price:.2f}")
                logger.warning(f"💰 REAL MONEY: Position size {position_size:.6f}")
                
                # Create signal for real trading engine
                signal = {
                    'symbol': opportunity.symbol,
                    'side': side,
                    'confidence': opportunity.targets.confidence_score / 100.0,
                    'strategy_type': 'profit_scraping',
                    'entry_price': current_price,
                    'profit_target': opportunity.targets.profit_target,
                    'stop_loss': opportunity.targets.stop_loss
                }
                
                position_id = await self.real_trading_engine.execute_trade(signal)
                trade_result = {'success': position_id is not None, 'position_id': position_id}
                
            elif self.paper_trading_engine:
                # PAPER TRADING EXECUTION - Create signal dictionary for enhanced paper trading engine
                signal = {
                    'symbol': opportunity.symbol,
                    'side': side,
                    'confidence': opportunity.targets.confidence_score / 100.0,
                    'strategy_type': 'profit_scraping',
                    'ml_score': opportunity.targets.confidence_score / 100.0,
                    'entry_reason': f"profit_scraping_{opportunity.level.level_type}",
                    'market_regime': 'level_based',
                    'volatility_regime': 'medium',
                    'quantity': position_size,
                    'price': current_price,
                    'leverage': self.leverage,
                    'profit_target': opportunity.targets.profit_target,
                    'stop_loss': opportunity.targets.stop_loss
                }
                
                position_id = await self.paper_trading_engine.execute_trade(signal)
                trade_result = {'success': position_id is not None, 'position_id': position_id}
            
            if trade_result and trade_result.get('success'):
                # Track active trade
                trade_id = trade_result.get('position_id', f"{opportunity.symbol}_{datetime.now().strftime('%H%M%S')}")
                
                active_trade = ActiveTrade(
                    trade_id=trade_id,
                    symbol=opportunity.symbol,
                    side=side,
                    entry_price=current_price,
                    quantity=position_size,
                    leverage=self.leverage,
                    profit_target=opportunity.targets.profit_target,
                    stop_loss=opportunity.targets.stop_loss,
                    entry_time=datetime.now(),
                    level_type=opportunity.level.level_type,
                    confidence_score=opportunity.targets.confidence_score
                )
                
                self.active_trades[trade_id] = active_trade
                self.total_trades += 1
                
                trading_type = "REAL" if self.is_real_trading else "PAPER"
                logger.info(f"✅ {trading_type} Trade executed: {trade_id} - {side} {opportunity.symbol} @ ${current_price:.2f}")
            
        except Exception as e:
            logger.error(f"Error executing trade: {e}")
    
    async def _monitor_active_trades(self):
        """Monitor active trades for exit conditions"""
        try:
            current_time = datetime.now()
            
            for trade_id, trade in list(self.active_trades.items()):
                current_price = await self._get_current_price(trade.symbol)
                if not current_price:
                    continue
                
                # Check for profit target hit
                profit_hit = False
                if trade.side == 'LONG':
                    profit_hit = current_price >= trade.profit_target
                else:  # SHORT
                    profit_hit = current_price <= trade.profit_target
                
                # Check for stop loss hit
                stop_hit = False
                if trade.side == 'LONG':
                    stop_hit = current_price <= trade.stop_loss
                else:  # SHORT
                    stop_hit = current_price >= trade.stop_loss
                
                # PROFIT SCRAPING: Add time-based exits for quick scalping
                time_elapsed_minutes = (current_time - trade.entry_time).total_seconds() / 60
                
                # Quick exit conditions for profit scraping
                quick_exit = False
                exit_reason_time = ""
                
                # Exit after 15 minutes if flat or slightly losing
                if time_elapsed_minutes > 15:
                    if trade.side == 'LONG':
                        price_change_pct = (current_price - trade.entry_price) / trade.entry_price
                    else:  # SHORT
                        price_change_pct = (trade.entry_price - current_price) / trade.entry_price
                    
                    # Exit if flat or losing after 15 minutes
                    if price_change_pct <= 0.002:  # Less than 0.2% profit
                        quick_exit = True
                        exit_reason_time = "TIME_EXIT_FLAT"
                
                # Force exit after 60 minutes regardless (profit scraping shouldn't hold this long)
                elif time_elapsed_minutes > 60:
                    quick_exit = True
                    exit_reason_time = "TIME_EXIT_MAX"
                
                # Safety net for extremely long positions (24 hours) - only if losing
                time_elapsed_hours = time_elapsed_minutes / 60
                safety_time_exit = time_elapsed_hours > 24 and (
                    (trade.side == 'LONG' and current_price < trade.entry_price * 0.95) or
                    (trade.side == 'SHORT' and current_price > trade.entry_price * 1.05)
                )
                
                # Exit trade if any condition met
                if profit_hit:
                    await self._close_trade(trade_id, "PROFIT_TARGET")
                elif stop_hit:
                    await self._close_trade(trade_id, "STOP_LOSS")
                elif quick_exit:
                    await self._close_trade(trade_id, exit_reason_time)
                    logger.info(f"⏰ Profit scraping time exit: {trade_id} after {time_elapsed_minutes:.1f} minutes - {exit_reason_time}")
                elif safety_time_exit:
                    await self._close_trade(trade_id, "SAFETY_TIME_EXIT")
                    logger.warning(f"⚠️ Closing losing position {trade_id} after 24 hours for safety")
            
        except Exception as e:
            logger.error(f"Error monitoring active trades: {e}")
    
    async def _close_trade(self, trade_id: str, exit_reason: str):
        """Close an active trade"""
        try:
            if trade_id not in self.active_trades:
                return
            
            trade = self.active_trades[trade_id]
            current_price = await self._get_current_price(trade.symbol)
            
            if current_price:
                # Calculate P&L
                if trade.side == 'LONG':
                    pnl_pct = (current_price - trade.entry_price) / trade.entry_price
                else:  # SHORT
                    pnl_pct = (trade.entry_price - current_price) / trade.entry_price
                
                # Apply leverage
                leveraged_pnl_pct = pnl_pct * trade.leverage
                pnl_amount = leveraged_pnl_pct * (trade.quantity * trade.entry_price)
                
                # Update performance tracking
                self.total_profit += pnl_amount
                if pnl_amount > 0:
                    self.winning_trades += 1
                
                # Store trade outcome in ML learning service
                ml_service = await get_ml_learning_service()
                if ml_service:
                    duration_minutes = int((datetime.now() - trade.entry_time).total_seconds() / 60)
                    
                    trade_outcome = TradeOutcome(
                        trade_id=trade_id,
                        symbol=trade.symbol,
                        strategy_type='profit_scraping',
                        system_type='profit_scraping' if self.is_real_trading else 'paper_trading',
                        confidence_score=trade.confidence_score / 100.0,
                        ml_score=None,
                        entry_price=trade.entry_price,
                        exit_price=current_price,
                        pnl_pct=leveraged_pnl_pct,
                        duration_minutes=duration_minutes,
                        market_regime='level_based',
                        volatility_regime='medium',
                        exit_reason=exit_reason,
                        success=pnl_amount > 0,
                        features={
                            'level_type': trade.level_type,
                            'leverage': trade.leverage,
                            'profit_target': trade.profit_target,
                            'stop_loss': trade.stop_loss,
                            'side': trade.side
                        },
                        entry_time=trade.entry_time,
                        exit_time=datetime.now()
                    )
                    
                    await ml_service.store_trade_outcome(trade_outcome)
                    logger.info(f"🧠 Trade outcome stored in ML learning service")
                
                # Close position in real trading engine if applicable
                if self.is_real_trading and self.real_trading_engine:
                    await self.real_trading_engine.close_position(trade_id, exit_reason)
                
                logger.info(f"🔚 Trade closed: {trade_id} - {exit_reason} - P&L: ${pnl_amount:.2f}")
            
            # Remove from active trades
            del self.active_trades[trade_id]
            
        except Exception as e:
            logger.error(f"Error closing trade {trade_id}: {e}")
    
    async def _get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for a symbol"""
        try:
            if self.exchange_client:
                ticker = await self.exchange_client.get_ticker_24h(symbol)
                return float(ticker.get('lastPrice', 0)) if ticker else None
            else:
                # Mock price for testing
                base_price = 50000 if 'BTC' in symbol else 3000
                import random
                return base_price * (1 + random.uniform(-0.02, 0.02))
                
        except Exception as e:
            logger.error(f"Error getting current price for {symbol}: {e}")
            return None
    
    def _calculate_opportunity_score(self, level: PriceLevel, targets: TradingTargets,
                                   distance: float, magnet_level: Optional[MagnetLevel]) -> int:
        """Calculate overall opportunity score"""
        try:
            # Base score from level strength
            base_score = level.strength_score * 0.3
            
            # Score from targets confidence
            targets_score = targets.confidence_score * 0.4
            
            # Score from distance (closer = better)
            distance_score = (1 - min(distance / 0.03, 1)) * 20  # Max 20 points
            
            # Bonus for magnet level
            magnet_bonus = 0
            if magnet_level and magnet_level.strength >= 60:
                magnet_bonus = 10
            
            total_score = base_score + targets_score + distance_score + magnet_bonus
            return min(int(total_score), 100)
            
        except Exception as e:
            logger.error(f"Error calculating opportunity score: {e}")
            return 50
    
    def get_status(self) -> Dict[str, Any]:
        """Get current profit scraping engine status"""
        try:
            win_rate = self.winning_trades / self.total_trades if self.total_trades > 0 else 0.0
            
            return {
                'active': self.active,
                'monitored_symbols': list(self.monitored_symbols),
                'active_trades': len(self.active_trades),
                'total_trades': self.total_trades,
                'winning_trades': self.winning_trades,
                'win_rate': win_rate,
                'total_profit': self.total_profit,
                'start_time': self.start_time.isoformat() if self.start_time else None,
                'uptime_minutes': (datetime.now() - self.start_time).total_seconds() / 60 if self.start_time else 0,
                'opportunities_count': sum(len(opps) for opps in self.active_opportunities.values()),
                'identified_levels_count': sum(len(levels) for levels in self.identified_levels.values()),
                'magnet_levels_count': sum(len(levels) for levels in self.magnet_levels.values()),
                'is_real_trading': self.is_real_trading,
                'trading_engine_type': 'real' if self.is_real_trading else 'paper'
            }
        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return {
                'active': False,
                'error': str(e)
            }
    

    
    def get_opportunities(self) -> Dict[str, List[Dict]]:
        """Get current opportunities for all symbols"""
        try:
            result = {}
            for symbol, opportunities in self.active_opportunities.items():
                result[symbol] = [opp.to_dict() for opp in opportunities]
            return result
            
        except Exception as e:
            logger.error(f"Error getting opportunities: {e}")
            return {}
    
    def get_active_trades(self) -> List[Dict]:
        """Get all active trades"""
        try:
            return [trade.to_dict() for trade in self.active_trades.values()]
            
        except Exception as e:
            logger.error(f"Error getting active trades: {e}")
            return []
    
    def get_identified_levels(self, symbol: str) -> Dict:
        """Get identified levels for a symbol"""
        try:
            price_levels = self.identified_levels.get(symbol, [])
            magnet_levels = self.magnet_levels.get(symbol, [])
            
            return {
                'price_levels': [level.to_dict() for level in price_levels],
                'magnet_levels': [magnet.to_dict() for magnet in magnet_levels]
            }
            
        except Exception as e:
            logger.error(f"Error getting levels for {symbol}: {e}")
            return {'price_levels': [], 'magnet_levels': []}
    
    async def _detect_market_trend(self, symbol: str) -> str:
        """Detect market trend for trend-aware filtering"""
        try:
            # Get recent price data
            historical_data = await self.level_analyzer._get_historical_data(symbol, self.exchange_client)
            if historical_data is None or len(historical_data) < 20:
                return 'neutral'
            
            # Calculate moving averages
            recent_prices = historical_data['close'].tail(20).astype(float)
            sma_5 = recent_prices.tail(5).mean()
            sma_10 = recent_prices.tail(10).mean()
            sma_20 = recent_prices.tail(20).mean()
            
            current_price = recent_prices.iloc[-1]
            
            # Determine trend strength
            if sma_5 > sma_10 > sma_20 and current_price > sma_5 * 1.02:
                return 'strong_uptrend'
            elif sma_5 < sma_10 < sma_20 and current_price < sma_5 * 0.98:
                return 'strong_downtrend'
            elif sma_5 > sma_10 and current_price > sma_10:
                return 'uptrend'
            elif sma_5 < sma_10 and current_price < sma_10:
                return 'downtrend'
            else:
                return 'neutral'
                
        except Exception as e:
            logger.error(f"Error detecting market trend for {symbol}: {e}")
            return 'neutral'
    
    async def _validate_support_bounce(self, symbol: str, support_level: float, current_price: float) -> bool:
        """Validate that support level is actually holding with bounce confirmation"""
        try:
            # Get recent price data
            historical_data = await self.level_analyzer._get_historical_data(symbol, self.exchange_client)
            if historical_data is None or len(historical_data) < 10:
                return True  # Default to allow if no data
            
            # Check recent 10 periods for bounce behavior
            recent_data = historical_data.tail(10)
            tolerance = support_level * 0.005  # 0.5% tolerance
            
            # Look for recent touches of this support level
            touches = 0
            bounces = 0
            
            for _, row in recent_data.iterrows():
                low_price = float(row['low'])
                high_price = float(row['high'])
                
                # Check if price touched support level
                if low_price <= support_level + tolerance and low_price >= support_level - tolerance:
                    touches += 1
                    
                    # Check if it bounced (high is significantly above support)
                    if high_price > support_level * 1.003:  # At least 0.3% bounce
                        bounces += 1
            
            # Require at least 1 recent touch with bounce, or no recent touches (fresh level)
            if touches == 0:
                return True  # Fresh level, allow
            elif touches > 0 and bounces > 0:
                bounce_rate = bounces / touches
                return bounce_rate >= 0.5  # At least 50% bounce rate
            else:
                logger.info(f"❌ Support validation failed: {symbol} @ {support_level:.2f} - {touches} touches, {bounces} bounces")
                return False
                
        except Exception as e:
            logger.error(f"Error validating support bounce for {symbol}: {e}")
            return True  # Default to allow on error
