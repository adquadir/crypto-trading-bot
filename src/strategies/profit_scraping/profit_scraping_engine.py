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
import pandas as pd
import numpy as np

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
    """Main profit scraping engine - RULE COMPLIANT"""
    
    def __init__(self, exchange_client=None, paper_trading_engine=None, real_trading_engine=None, config=None):
        self.exchange_client = exchange_client
        self.paper_trading_engine = paper_trading_engine
        self.real_trading_engine = real_trading_engine
        self.config = config or {}
        
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
        
        # ATR-adaptive tolerance caching
        self.atr_cache = {}  # symbol -> {'atr_pct': float, 'timestamp': datetime}
        self.atr_cache_duration = timedelta(minutes=30)  # Cache ATR for 30 minutes
        
        # RULE COMPLIANT Configuration
        self.max_symbols = None  # No enforced limit; monitor all passed symbols
        self.max_trades_per_symbol = 2
        self.leverage = 10                    # RULE COMPLIANT: 10x leverage
        self.account_balance = 10000          # RULE COMPLIANT: $10,000 virtual balance
        self.max_risk_per_trade = 0.05       # RULE COMPLIANT: 5% risk per trade = $500
        
        # Rule-based target configuration
        paper_config = self.config.get('paper_trading', {})
        self.primary_target_dollars = float(paper_config.get('primary_target_dollars', 18.0))  # $18 gross
        self.absolute_floor_dollars = float(paper_config.get('absolute_floor_dollars', 15.0))  # $15 gross
        self.stop_loss_dollars = float(paper_config.get('stop_loss_dollars', 18.0))  # $18 gross
        self.position_size_usd = float(paper_config.get('stake_amount', 500.0))  # $500 per position
        
        logger.info(f"🎯 RULE-BASED TARGETS: TP=${self.primary_target_dollars}, Floor=${self.absolute_floor_dollars}, SL=${self.stop_loss_dollars}")
    
    async def _get_atr_adaptive_tolerance(self, symbol: str, period: int = 14, days: int = 7,
                                        min_pct: float = 0.0015, max_pct: float = 0.008, 
                                        atr_fraction: float = 0.3, base_pct: float = 0.003) -> float:
        """
        Enhanced ATR-adaptive percentage tolerance that breathes with market volatility.
        
        Args:
            symbol: Trading symbol
            period: ATR calculation period (default 14)
            days: Historical data lookback days (default 7)
            min_pct: Minimum tolerance (0.15% for very calm markets)
            max_pct: Maximum tolerance (0.8% for very volatile markets)
            atr_fraction: Fraction of ATR to use as tolerance (30%)
            base_pct: Fallback tolerance if ATR calculation fails (0.3%)
            
        Returns:
            Adaptive tolerance percentage based on market volatility
        """
        try:
            # Check cache first
            now = datetime.now()
            if symbol in self.atr_cache:
                cache_entry = self.atr_cache[symbol]
                if now - cache_entry['timestamp'] < self.atr_cache_duration:
                    logger.debug(f"📊 ATR CACHE HIT: {symbol} = {cache_entry['atr_pct']*100:.2f}%")
                    return cache_entry['atr_pct']
            
            # Fetch historical data
            df = await self.level_analyzer._get_historical_data(symbol, self.exchange_client, days=days)
            if df is None or len(df) < period + 5:
                logger.warning(f"⚠️ ATR FALLBACK: Insufficient data for {symbol}, using base {base_pct*100:.2f}%")
                return base_pct
            
            # Ensure numeric types
            highs = pd.to_numeric(df['high'], errors='coerce')
            lows = pd.to_numeric(df['low'], errors='coerce')
            closes = pd.to_numeric(df['close'], errors='coerce')
            
            # Drop any NaN values
            valid_mask = ~(highs.isna() | lows.isna() | closes.isna())
            if valid_mask.sum() < period + 2:
                logger.warning(f"⚠️ ATR FALLBACK: Invalid data for {symbol}, using base {base_pct*100:.2f}%")
                return base_pct
            
            highs = highs[valid_mask]
            lows = lows[valid_mask]
            closes = closes[valid_mask]
            
            # Calculate True Range components
            prev_close = closes.shift(1)
            tr1 = highs - lows                    # High - Low
            tr2 = (highs - prev_close).abs()     # |High - Previous Close|
            tr3 = (lows - prev_close).abs()      # |Low - Previous Close|
            
            # True Range is the maximum of the three
            true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            
            # Calculate ATR (Average True Range)
            atr = true_range.rolling(window=period, min_periods=period).mean()
            
            # Get the most recent ATR and price
            current_atr = atr.iloc[-1]
            current_price = closes.iloc[-1]
            
            if pd.isna(current_atr) or pd.isna(current_price) or current_price <= 0:
                logger.warning(f"⚠️ ATR FALLBACK: Invalid ATR/price for {symbol}, using base {base_pct*100:.2f}%")
                return base_pct
            
            # Calculate ATR as percentage of price
            atr_pct = float(current_atr / current_price)
            
            # Apply fraction and bounds
            adaptive_tolerance = atr_pct * atr_fraction
            final_tolerance = max(min_pct, min(max_pct, adaptive_tolerance))
            
            # Cache the result
            self.atr_cache[symbol] = {
                'atr_pct': final_tolerance,
                'timestamp': now
            }
            
            # Calculate volatility regime for logging
            if final_tolerance <= 0.002:
                regime = "CALM"
            elif final_tolerance <= 0.004:
                regime = "NORMAL"
            elif final_tolerance <= 0.006:
                regime = "ACTIVE"
            else:
                regime = "VOLATILE"
            
            logger.info(f"📊 ATR ADAPTIVE: {symbol} = {final_tolerance*100:.2f}% [{regime}] (ATR: {atr_pct*100:.2f}%)")
            return final_tolerance
            
        except Exception as e:
            logger.warning(f"⚠️ ATR ERROR: {symbol} calculation failed ({e}), using base {base_pct*100:.2f}%")
            return base_pct
    
    def _calculate_rule_based_targets(self, level: PriceLevel, current_price: float, symbol: str) -> TradingTargets:
        """Calculate targets based on rule mode configuration instead of statistical analysis"""
        try:
            # Calculate position size and leverage
            position_size_usd = self.position_size_usd
            leverage = self.leverage
            notional_value = position_size_usd * leverage
            
            # Fee basis: stake (position_size_usd) to match rule expectations (~$0.40 total)
            fee_rate = 0.0004
            entry_fee = position_size_usd * fee_rate
            exit_fee = position_size_usd * fee_rate
            total_fees = entry_fee + exit_fee
            
            # RULE-BASED TARGET CALCULATIONS aligned to desired net
            net_target = 17.60
            net_stop = 17.60
            net_floor = 14.60
            gross_target = net_target + total_fees
            gross_stop = net_stop + total_fees
            gross_floor = net_floor + total_fees
            
            # Calculate price movement needed so that hitting price yields desired net PnL
            if level.level_type == 'support':  # LONG
                profit_target = level.price + (gross_target / notional_value) * level.price
            else:  # SHORT - resistance
                profit_target = level.price - (gross_target / notional_value) * level.price
            
            # Calculate stop loss price
            if level.level_type == 'support':  # LONG
                stop_loss = level.price - (gross_stop / notional_value) * level.price
            else:  # SHORT - resistance
                stop_loss = level.price + (gross_stop / notional_value) * level.price
            
            # Calculate floor activation price
            if level.level_type == 'support':  # LONG
                floor_activation_price = level.price + (gross_floor / notional_value) * level.price
            else:  # SHORT - resistance
                floor_activation_price = level.price - (gross_floor / notional_value) * level.price
            
            # Create TradingTargets object
            targets = TradingTargets(
                entry_price=level.price,
                profit_target=profit_target,
                stop_loss=stop_loss,
                profit_probability=0.75,  # Conservative estimate for rule-based
                risk_reward_ratio=1.0,  # 1:1 risk/reward for rule-based
                expected_duration_minutes=30,  # Conservative estimate
                confidence_score=80,  # High confidence for rule-based
                take_profit_net_usd=net_target,  # Net USD take profit
                stop_loss_net_usd=net_stop,      # Net USD stop loss
                floor_net_usd=net_floor          # Net USD floor
            )
            
            logger.info(f"🎯 RULE-BASED TARGETS for {symbol} {level.level_type}:")
            logger.info(f"   Entry: ${level.price:.4f}")
            logger.info(f"   TP: ${profit_target:.4f} (${net_target:.2f} net)")
            logger.info(f"   SL: ${stop_loss:.4f} (${net_stop:.2f} net)")
            logger.info(f"   Floor Activation: ${floor_activation_price:.4f} (${net_floor:.2f} net)")
            
            return targets
            
        except Exception as e:
            logger.error(f"Error calculating rule-based targets: {e}")
            return None
    
    async def start_scraping(self, symbols: List[str]) -> bool:
        """Start profit scraping for specified symbols"""
        try:
            logger.info(f"🚀 Starting profit scraping for {len(symbols)} symbols")
            
            if self.max_symbols is not None and len(symbols) > self.max_symbols:
                symbols = symbols[:self.max_symbols]
                logger.warning(f"Limited to {self.max_symbols} symbols")
            
            self.monitored_symbols = set(symbols)
            self.active = True
            self.start_time = datetime.now()
            
            # Start monitoring loop immediately (analysis will happen in background)
            asyncio.create_task(self._monitoring_loop())
            
            # Start background analysis for all symbols (non-blocking)
            asyncio.create_task(self._background_initial_analysis(symbols))
            
            logger.info("✅ Profit scraping started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error starting profit scraping: {e}")
            return False
    
    async def _background_initial_analysis(self, symbols: List[str]):
        """Perform initial analysis of all symbols in background"""
        try:
            logger.info(f"🔍 Starting background analysis of {len(symbols)} symbols")
            
            # Analyze symbols in small batches to avoid overwhelming the system
            batch_size = 5
            for i in range(0, len(symbols), batch_size):
                batch = symbols[i:i + batch_size]
                
                # Process batch concurrently
                tasks = [self._analyze_symbol(symbol) for symbol in batch]
                await asyncio.gather(*tasks, return_exceptions=True)
                
                # Small delay between batches
                await asyncio.sleep(2)
                
                logger.info(f"📊 Completed analysis batch {i//batch_size + 1}/{(len(symbols) + batch_size - 1)//batch_size}")
            
            logger.info("✅ Background initial analysis completed")
            
        except Exception as e:
            logger.error(f"Error in background analysis: {e}")
    
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
        """Main monitoring loop with enhanced error handling"""
        restart_count = 0
        max_restarts = 3
        
        while self.active and restart_count < max_restarts:
            try:
                logger.info(f"🔍 Starting profit scraping monitoring loop (attempt {restart_count + 1})")
                
                while self.active:
                    try:
                        # Update opportunities for all symbols (with individual error handling)
                        for symbol in self.monitored_symbols:
                            try:
                                await self._update_opportunities(symbol)
                                await self._check_entry_conditions(symbol)
                            except Exception as symbol_error:
                                logger.warning(f"⚠️ Error processing {symbol}: {symbol_error}")
                                continue  # Skip this symbol, continue with others
                        
                        # Monitor active trades
                        try:
                            await self._monitor_active_trades()
                        except Exception as trade_error:
                            logger.warning(f"⚠️ Error monitoring trades: {trade_error}")
                        
                        # Re-analyze levels periodically (every 10 minutes)
                        if datetime.now().minute % 10 == 0:
                            for symbol in self.monitored_symbols:
                                try:
                                    await self._analyze_symbol(symbol)
                                except Exception as analyze_error:
                                    logger.warning(f"⚠️ Error analyzing {symbol}: {analyze_error}")
                                    continue
                        
                        # Wait before next iteration
                        await asyncio.sleep(5)  # 5-second monitoring cycle
                        
                    except Exception as cycle_error:
                        logger.error(f"❌ Error in monitoring cycle: {cycle_error}")
                        # Don't break the loop for individual cycle errors
                        await asyncio.sleep(10)  # Wait a bit longer on cycle errors
                        continue
                        
            except Exception as e:
                restart_count += 1
                logger.error(f"❌ Profit scraping monitoring loop crashed (attempt {restart_count}/{max_restarts}): {e}")
                
                if restart_count < max_restarts:
                    logger.info(f"🔄 Restarting profit scraping monitoring loop in 15 seconds...")
                    await asyncio.sleep(15)
                else:
                    logger.error("🚨 Profit scraping monitoring loop exceeded max restarts, stopping")
                    break
        
        logger.warning("🛑 Profit scraping monitoring loop stopped")
    
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
                
                # Calculate trading targets using RULE-BASED approach
                targets = self._calculate_rule_based_targets(level, current_price, symbol)
                
                if targets:
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
                # Check if price is near the level (within 0.2%)
                distance_to_level = abs(current_price - opportunity.level.price) / opportunity.level.price
                
                if distance_to_level <= 0.003:  # Within 0.3% (BALANCED - was 0.2%)
                    # Additional entry validation
                    if await self._validate_entry_conditions(opportunity, current_price):
                        # FIXED: Only emit signals - do NOT execute trades directly
                        logger.info(f"🎯 PROFIT SCRAPING: Entry conditions met for {opportunity.symbol} - signal ready")
                        # Trade execution is handled by paper trading engine via get_ready_to_trade_signals()
                    break  # Only one trade per check
            
        except Exception as e:
            logger.error(f"Error checking entry conditions for {symbol}: {e}")
    
    async def _validate_entry_conditions(self, opportunity: ScrapingOpportunity, current_price: float) -> bool:
        """Validate additional entry conditions with STRICT BOUNDS and CONFIRMATION REQUIREMENTS"""
        try:
            level = opportunity.level
            symbol = opportunity.symbol
            
            # ARCHITECTURAL IMPROVEMENT: Validate level is still relevant
            if not await self._validate_level_relevance(level, symbol):
                logger.info(f"❌ STALE LEVEL: {symbol} level @ {level.price:.6f} no longer relevant")
                return False
            
            # PROFIT SCRAPING FIX: Use trend filtering with bounds validation
            market_trend = await self._detect_market_trend(symbol)
            
            if level.level_type == 'support':
                # FIX #1: Two-sided bounds - price must be ABOVE the level, not below
                lower = level.price * 1.000   # ≥ level (don't go long below support)
                upper = level.price * 1.003   # ≤ +0.3% above level (BALANCED - was 0.2%)
                if not (lower <= current_price <= upper):
                    logger.info(f"❌ BOUNDS CHECK: {symbol} price ${current_price:.6f} not in support range [${lower:.6f}, ${upper:.6f}]")
                    return False
                
                # HARDENED TREND CHECK: Block more counter-trend trades
                if market_trend in ['strong_downtrend', 'downtrend']:
                    if level.strength_score < 85:  # Raised threshold for counter-trend
                        logger.info(f"❌ TREND FILTER: Skipping LONG {symbol} - downtrend + insufficient support strength ({level.strength_score})")
                        return False
                    else:
                        logger.info(f"✅ ALLOWING COUNTER-TREND: Very strong support {symbol} @ {level.price:.6f} (strength: {level.strength_score})")
                
                # FIX #3: Hard block when support bounce not confirmed (no more warnings)
                if not await self._validate_support_bounce(symbol, level.price, current_price):
                    logger.info(f"❌ BOUNCE CONFIRMATION: {symbol} support bounce not confirmed - blocking trade")
                    return False
                
                # ARCHITECTURAL IMPROVEMENT: Wait for confirmation candle close
                if not await self._wait_for_confirmation_candle(symbol, level, 'LONG'):
                    logger.info(f"❌ CONFIRMATION CANDLE: {symbol} LONG confirmation not received")
                    return False
                
                return True
            
            elif level.level_type == 'resistance':
                # FIX #1: Two-sided bounds - price must be BELOW the level, not above  
                lower = level.price * 0.997   # ≥ -0.3% below level (BALANCED - was 0.2%)
                upper = level.price * 1.000   # ≤ level (don't go short above resistance)
                if not (lower <= current_price <= upper):
                    logger.info(f"❌ BOUNDS CHECK: {symbol} price ${current_price:.6f} not in resistance range [${lower:.6f}, ${upper:.6f}]")
                    return False
                
                # HARDENED TREND CHECK: Block more counter-trend trades
                if market_trend in ['strong_uptrend', 'uptrend']:
                    if level.strength_score < 85:  # Raised threshold for counter-trend
                        logger.info(f"❌ TREND FILTER: Skipping SHORT {symbol} - uptrend + insufficient resistance strength ({level.strength_score})")
                        return False
                    else:
                        logger.info(f"✅ ALLOWING COUNTER-TREND: Very strong resistance {symbol} @ {level.price:.6f} (strength: {level.strength_score})")
                
                # FIX #2: Add resistance rejection validation (was missing!)
                if not await self._validate_resistance_rejection(symbol, level.price):
                    logger.info(f"❌ REJECTION CONFIRMATION: {symbol} resistance rejection not confirmed - blocking trade")
                    return False
                
                # ARCHITECTURAL IMPROVEMENT: Wait for confirmation candle close
                if not await self._wait_for_confirmation_candle(symbol, level, 'SHORT'):
                    logger.info(f"❌ CONFIRMATION CANDLE: {symbol} SHORT confirmation not received")
                    return False
            
            return True
            
            return False  # Unknown level type
            
        except Exception as e:
            logger.error(f"Error validating entry conditions: {e}")
            return False
    
    async def _wait_for_confirmation_candle(self, symbol: str, level: PriceLevel, direction: str) -> bool:
        """Wait for a confirmation candle to close before entering trade"""
        try:
            # Get the most recent candle data
            recent_data = await self.level_analyzer._get_historical_data(symbol, self.exchange_client, days=1)
            if recent_data is None or len(recent_data) < 2:
                logger.warning(f"Insufficient data for confirmation candle check: {symbol}")
                return False  # Fail safe - don't allow trades without candle confirmation
            
            # Get the last completed candle (not the current forming one)
            last_candle = recent_data.iloc[-2]  # Previous candle
            current_candle = recent_data.iloc[-1]  # Current candle
            
            open_price = float(last_candle['open'])
            high_price = float(last_candle['high'])
            low_price = float(last_candle['low'])
            close_price = float(last_candle['close'])
            
            if direction == 'LONG' and level.level_type == 'support':
                # For LONG: Need a hammer/bullish candle that touched support and closed above it
                touched_support = low_price <= level.price * 1.003  # Wick touched support (BALANCED - was 0.2%)
                closed_above_support = close_price >= level.price * 1.002  # Closed above support
                bullish_close = close_price > open_price  # Bullish candle
                
                confirmation = touched_support and closed_above_support and bullish_close
                logger.info(f"🕯️ LONG confirmation {symbol}: Touch={touched_support}, CloseAbove={closed_above_support}, Bullish={bullish_close} → {confirmation}")
                return confirmation
                
            elif direction == 'SHORT' and level.level_type == 'resistance':
                # For SHORT: Need a shooting star/bearish candle that touched resistance and closed below it
                touched_resistance = high_price >= level.price * 0.997  # Wick touched resistance (BALANCED - was 0.2%)
                closed_below_resistance = close_price <= level.price * 0.998  # Closed below resistance
                bearish_close = close_price < open_price  # Bearish candle
                
                confirmation = touched_resistance and closed_below_resistance and bearish_close
                logger.info(f"🕯️ SHORT confirmation {symbol}: Touch={touched_resistance}, CloseBelow={closed_below_resistance}, Bearish={bearish_close} → {confirmation}")
                return confirmation
            
            return False
            
        except Exception as e:
            logger.error(f"Error waiting for confirmation candle: {e}", exc_info=True)
            return False  # Fail safe - don't allow trades when confirmation data is flaky
    
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
            
            # TEMPORARILY DISABLED: ML recommendation to allow trades through for testing
            # TODO: Re-enable ML filtering after system is working
            logger.info(f"🎯 PROFIT SCRAPING: Executing trade without ML filtering (temporarily disabled)")
            
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
                
                # Use the correct method for paper trading engine
                # Create proper signal for execute_virtual_trade
                trading_signal = {
                    'symbol': signal['symbol'],
                    'direction': side,
                    'entry_price': current_price,
                    'strategy': 'profit_scraping_engine',  # Changed from strategy_type to strategy
                    'confidence': signal['confidence'],
                    'signal_id': f"profit_scraping_{opportunity.symbol}_{int(datetime.now().timestamp())}",  # Generate unique signal ID
                    'stop_loss': opportunity.targets.stop_loss,  # Add stop loss
                    'take_profit': opportunity.targets.profit_target,  # Add take profit
                    'optimal_leverage': self.leverage,  # Add leverage (10x)
                    'tp_net_usd': opportunity.targets.take_profit_net_usd,  # Net USD take profit
                    'sl_net_usd': opportunity.targets.stop_loss_net_usd,     # Net USD stop loss
                    'floor_net_usd': opportunity.targets.floor_net_usd       # Net USD floor
                }
                
                position_id = await self.paper_trading_engine.execute_virtual_trade(
                    trading_signal,
                    500.0  # position_size_usd (fixed $500 per trade)
                )
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
                
                # Force exit after 60 minutes regardless (profit scraping shouldn't hold this long)
                if time_elapsed_minutes > 60:
                    quick_exit = True
                    exit_reason_time = "TIME_EXIT_MAX"
                # Exit after 15 minutes if flat or slightly losing
                elif time_elapsed_minutes > 15:
                    if trade.side == 'LONG':
                        price_change_pct = (current_price - trade.entry_price) / trade.entry_price
                    else:  # SHORT
                        price_change_pct = (trade.entry_price - current_price) / trade.entry_price
                    
                    # Exit if flat or losing after 15 minutes
                    if price_change_pct <= 0.002:  # Less than 0.2% profit
                        quick_exit = True
                        exit_reason_time = "TIME_EXIT_FLAT"
                
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
    
    async def get_ready_to_trade_signals(self) -> List[Dict[str, Any]]:
        """Get signals that are ready to trade (meet entry conditions) for paper trading engine"""
        try:
            ready_signals = []
            
            for symbol in self.monitored_symbols:
                try:
                    opportunities = self.active_opportunities.get(symbol, [])
                    if not opportunities:
                        continue
                    
                    current_price = await self._get_current_price(symbol)
                    if not current_price:
                        continue
                    
                    for opportunity in opportunities:
                        # Check if price is near the level (within 0.2%)
                        distance_to_level = abs(current_price - opportunity.level.price) / opportunity.level.price
                        
                        if distance_to_level <= 0.003:  # Within 0.3% (BALANCED - was 0.2%)
                            # Additional entry validation
                            if await self._validate_entry_conditions(opportunity, current_price):
                                # Create trading signal
                                side = 'LONG' if opportunity.level.level_type == 'support' else 'SHORT'
                                
                                signal = {
                                    'symbol': opportunity.symbol,
                                    'direction': side,  # FIXED: Use 'direction' to match paper trading engine expectation
                                    'confidence': opportunity.targets.confidence_score / 100.0,
                                    'strategy': 'profit_scraping_engine',  # FIXED: Use 'strategy' to match paper trading engine expectation
                                    'signal_source': 'profit_scraping_engine',
                                    'ml_score': opportunity.targets.confidence_score / 100.0,
                                    'entry_reason': f"profit_scraping_{opportunity.level.level_type}",
                                    'market_regime': 'level_based',
                                    'volatility_regime': 'medium',
                                    'entry_price': current_price,
                                    'profit_target': opportunity.targets.profit_target,
                                    'stop_loss': opportunity.targets.stop_loss,
                                    'opportunity_score': opportunity.opportunity_score,
                                    'optimal_leverage': self.leverage,  # Add leverage for consistency
                                    'tp_net_usd': opportunity.targets.take_profit_net_usd,  # Add net targets
                                    'sl_net_usd': opportunity.targets.stop_loss_net_usd,
                                    'floor_net_usd': opportunity.targets.floor_net_usd
                                }
                                
                                ready_signals.append(signal)
                                logger.info(f"🎯 PROFIT SCRAPING SIGNAL: {symbol} {side} @ ${current_price:.4f} (distance: {distance_to_level:.3f}%)")
                                
                except Exception as symbol_error:
                    logger.warning(f"⚠️ Error checking ready signals for {symbol}: {symbol_error}")
                    continue
            
            if ready_signals:
                logger.info(f"📊 PROFIT SCRAPING: {len(ready_signals)} ready-to-trade signals available")
            
            return ready_signals
            
        except Exception as e:
            logger.error(f"Error getting ready to trade signals: {e}")
            return []
    
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
        """Enhanced multi-timeframe trend detection for better directional bias"""
        try:
            # Get multiple timeframes for trend analysis
            short_tf = await self.level_analyzer._get_historical_data(symbol, self.exchange_client, days=7)   # 1 week
            medium_tf = await self.level_analyzer._get_historical_data(symbol, self.exchange_client, days=21)  # 3 weeks
            long_tf = await self.level_analyzer._get_historical_data(symbol, self.exchange_client, days=60)   # 2 months
            
            if any(df is None or len(df) < 20 for df in [short_tf, medium_tf, long_tf]):
                logger.warning(f"Insufficient data for multi-timeframe trend analysis: {symbol}")
                return 'neutral'
            
            # Calculate trend scores for each timeframe
            short_trend = self._calculate_trend_score(short_tf)
            medium_trend = self._calculate_trend_score(medium_tf)
            long_trend = self._calculate_trend_score(long_tf)
            
            # Weighted trend score (recent gets more weight)
            combined_score = (short_trend * 0.5) + (medium_trend * 0.3) + (long_trend * 0.2)
            
            logger.info(f"📊 Multi-TF trend {symbol}: Short={short_trend:.3f}, Medium={medium_trend:.3f}, Long={long_trend:.3f}, Combined={combined_score:.3f}")
            
            # Classify trend strength
            if combined_score > 0.015:
                return 'strong_uptrend'
            elif combined_score > 0.005:
                return 'uptrend'
            elif combined_score < -0.015:
                return 'strong_downtrend'
            elif combined_score < -0.005:
                return 'downtrend'
            else:
                return 'neutral'
                
        except Exception as e:
            logger.error(f"Error detecting multi-timeframe trend for {symbol}: {e}")
            return 'neutral'
    
    def _calculate_trend_score(self, df: pd.DataFrame) -> float:
        """Calculate trend score from price data using multiple indicators"""
        try:
            closes = df['close'].astype(float)
            
            # 1. Price momentum (recent vs older)
            recent_avg = closes.tail(5).mean()
            older_avg = closes.head(5).mean()
            momentum_score = (recent_avg - older_avg) / older_avg
            
            # 2. Moving average slope
            ma_20 = closes.rolling(20).mean()
            ma_slope = (ma_20.iloc[-1] - ma_20.iloc[-10]) / ma_20.iloc[-10] if len(ma_20) >= 10 else 0
            
            # 3. Higher highs / Lower lows pattern
            highs = df['high'].astype(float)
            lows = df['low'].astype(float)
            
            recent_high = highs.tail(10).max()
            recent_low = lows.tail(10).min()
            earlier_high = highs.head(10).max()
            earlier_low = lows.head(10).min()
            
            hh_ll_score = 0
            if recent_high > earlier_high and recent_low > earlier_low:
                hh_ll_score = 0.01  # Higher highs and higher lows = uptrend
            elif recent_high < earlier_high and recent_low < earlier_low:
                hh_ll_score = -0.01  # Lower highs and lower lows = downtrend
            
            # Combine scores
            trend_score = (momentum_score * 0.5) + (ma_slope * 0.3) + (hh_ll_score * 0.2)
            
            return trend_score
            
        except Exception as e:
            logger.error(f"Error calculating trend score: {e}")
            return 0.0
    
    async def _validate_level_relevance(self, level: PriceLevel, symbol: str) -> bool:
        """Validate that a historical level is still relevant in current market structure"""
        try:
            # Get recent data to check level relevance
            recent_data = await self.level_analyzer._get_historical_data(symbol, self.exchange_client, days=7)
            if recent_data is None or len(recent_data) < 20:
                logger.warning(f"Insufficient data for level relevance check: {symbol}")
                return False  # Fail safe - don't allow trades without proper level validation
            
            current_price = float(recent_data['close'].iloc[-1])
            
            # 1. Age check - levels older than 30 days are stale
            days_since_last_test = (datetime.now() - level.last_tested).days
            if days_since_last_test > 30:
                logger.info(f"⏰ STALE LEVEL: {symbol} level @ {level.price:.6f} last tested {days_since_last_test} days ago")
                return False
            
            # 2. Distance check - levels too far from current price are irrelevant
            distance_pct = abs(level.price - current_price) / current_price
            if distance_pct > 0.15:  # 15% away
                logger.info(f"📏 DISTANT LEVEL: {symbol} level @ {level.price:.6f} is {distance_pct:.1%} from current price")
                return False
            
            # 3. Volume confirmation - levels should have decent volume when formed
            if level.volume_confirmation < 0.8:  # Below 80% of average volume
                logger.info(f"📊 LOW VOLUME LEVEL: {symbol} level @ {level.price:.6f} formed on low volume ({level.volume_confirmation:.2f})")
                return False
            
            # 4. Recent interaction check - level should have been tested recently to be valid
            recent_touches = 0
            tolerance = level.price * 0.01  # 1% tolerance for recent touches
            
            for _, candle in recent_data.tail(20).iterrows():  # Last 20 candles
                high = float(candle['high'])
                low = float(candle['low'])
                
                if level.level_type == 'support' and low <= level.price + tolerance:
                    recent_touches += 1
                elif level.level_type == 'resistance' and high >= level.price - tolerance:
                    recent_touches += 1
            
            if recent_touches == 0:
                logger.info(f"🔍 UNTESTED LEVEL: {symbol} level @ {level.price:.6f} not tested in recent 20 candles")
                return False
            
            logger.info(f"✅ VALID LEVEL: {symbol} level @ {level.price:.6f} - Recent touches: {recent_touches}, Age: {days_since_last_test}d")
            return True
            
        except Exception as e:
            logger.error(f"Error validating level relevance for {symbol}: {e}", exc_info=True)
            return False  # Fail safe - don't allow trades when level validation fails
    
    async def _validate_support_bounce(self, symbol: str, support_level: float, current_price: float) -> bool:
        """Validate that support level is actually bouncing (not breaking)"""
        try:
            # Get recent price data
            historical_data = await self.level_analyzer._get_historical_data(symbol, self.exchange_client)
            if historical_data is None or len(historical_data) < 10:
                logger.warning(f"Insufficient data to validate support bounce for {symbol}")
                return False  # Fail safe - don't allow trades without bounce confirmation
            
            # Check recent 10 candles for bounce pattern
            recent_candles = historical_data.tail(10)
            tolerance = support_level * 0.003  # 0.3% tolerance (BALANCED - was 0.2%)
            
            touches = 0
            bounces = 0
            
            for _, candle in recent_candles.iterrows():
                low = float(candle['low'])
                close = float(candle['close'])
                
                # Check if candle touched the support level
                if support_level - tolerance <= low <= support_level + tolerance:
                    touches += 1
                    # Check if it bounced (closed above support + buffer)
                    if close >= support_level * 1.002:  # Closed 0.2% above support
                        bounces += 1
            
            if touches == 0:
                return True  # No recent tests, allow
            
                bounce_rate = bounces / touches
            logger.info(f"🔍 Support validation {symbol}: {bounces}/{touches} bounces ({bounce_rate:.2%})")
            
                return bounce_rate >= 0.5  # At least 50% bounce rate
                
        except Exception as e:
            logger.error(f"Error validating support bounce: {e}", exc_info=True)
            return False  # Fail safe - don't allow trades when bounce validation fails
    
    async def _validate_resistance_rejection(self, symbol: str, resistance_level: float) -> bool:
        """Validate that resistance level is actually rejecting price (not being broken)"""
        try:
            # Get recent price data
            historical_data = await self.level_analyzer._get_historical_data(symbol, self.exchange_client)
            if historical_data is None or len(historical_data) < 10:
                logger.warning(f"Insufficient data to validate resistance rejection for {symbol}")
                return False  # Fail safe - don't allow trades without rejection confirmation
            
            # Check recent 10 candles for rejection pattern
            recent_candles = historical_data.tail(10)
            tolerance = resistance_level * 0.003  # 0.3% tolerance (BALANCED - was 0.2%)
            
            touches = 0
            rejections = 0
            
            for _, candle in recent_candles.iterrows():
                high = float(candle['high'])
                close = float(candle['close'])
                
                # Check if candle touched the resistance level
                if resistance_level - tolerance <= high <= resistance_level + tolerance:
                    touches += 1
                    # Check if it was rejected (closed below resistance - buffer)
                    if close <= resistance_level * 0.997:  # Closed 0.3% below resistance
                        rejections += 1
            
            if touches == 0:
                return True  # No recent tests, allow
            
            rejection_rate = rejections / touches
            logger.info(f"🔍 Resistance validation {symbol}: {rejections}/{touches} rejections ({rejection_rate:.2%})")
            
            return rejection_rate >= 0.5  # At least 50% rejection rate
            
        except Exception as e:
            logger.error(f"Error validating resistance rejection: {e}", exc_info=True)
            return False  # Fail safe - don't allow trades when rejection validation fails
