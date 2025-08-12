"""
Profit Scraping Engine (ATR-Adjusted)
Main engine that coordinates level analysis, monitoring, and trade execution
with volatility-aware (ATR) tolerances, softened confirmations, and calmer trailing.
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

@dataclass
class ToleranceProfile:
    """Single source of truth for all ATR-based tolerances per symbol"""
    atr_pct: float
    regime: str
    clustering_pct: float
    validation_pct: float
    entry_pct: float
    proximity_pct: float
    close_buffer_pct: float
    ts: datetime

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
    # --- PATCHED: Dollar/percent step trail state (calmer defaults) ---
    locked_profit_usd: float = 0.0
    last_step_usd: float = 0.0
    max_trail_cap_usd: float = 60.0         # was 100.0
    step_increment_usd: float = 15.0        # was 10.0
    step_mode_percent: bool = False         # False = $ steps, True = % steps
    step_increment_pct: float = 0.002       # 0.2% per step if in % mode
    # --- Anti-whipsaw & timing ---
    step_cooldown_sec: int = 40             # was 20
    last_step_time: Optional[datetime] = None
    hysteresis_pct: float = 0.0012          # was ~0.0008
    # --- Start criteria / fee aware ---
    trail_start_net_usd: float = 20.0       # was 18.0
    fee_buffer_usd: float = 0.40
    # --- Cap hand-off to ATR trail ---
    cap_handoff_tight_atr: bool = True
    cap_trail_mult: float = 0.40            # was 0.55
    
    def to_dict(self) -> Dict:
        return asdict(self)

class ProfitScrapingEngine:
    """Main profit scraping engine - RULE COMPLIANT with ATR-aware behavior"""
    
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
        self.max_risk_per_trade = 0.05        # RULE COMPLIANT: 5% risk per trade = $500
        
        # Performance tracking metrics
        self.total_trades = 0
        self.winning_trades = 0
        self.total_profit = 0.0
        self.start_time = None
        
        # Rule-based target configuration
        paper_config = self.config.get('paper_trading', {})
        self.primary_target_dollars = float(paper_config.get('primary_target_dollars', 18.0))  # $18 gross
        self.absolute_floor_dollars = float(paper_config.get('absolute_floor_dollars', 15.0))  # $15 gross
        self.stop_loss_dollars = float(paper_config.get('stop_loss_dollars', 18.0))            # $18 gross
        self.position_size_usd = float(paper_config.get('stake_amount', 500.0))                # $500 per position
        
        logger.info(f"🎯 RULE-BASED TARGETS: TP=${self.primary_target_dollars}, Floor=${self.absolute_floor_dollars}, SL=${self.stop_loss_dollars}")
    
    # --- ATR% + volatility helpers ---------------------------------
    async def _get_atr_pct_latest(self, symbol: str, period: int = 14, days: int = 7) -> Optional[float]:
        """Return latest ATR as a % of price (e.g. 0.018 == 1.8%). Cached via atr_cache."""
        now = datetime.now()
        cache = self.atr_cache.get(symbol, {})
        if cache and 'raw_atr_pct' in cache and now - cache.get('timestamp', now) < self.atr_cache_duration:
            return cache['raw_atr_pct']

        df = await self.level_analyzer._get_historical_data(symbol, self.exchange_client, days=days)
        if df is None or len(df) < period + 5:
            return None

        highs = pd.to_numeric(df['high'], errors='coerce')
        lows = pd.to_numeric(df['low'], errors='coerce')
        closes = pd.to_numeric(df['close'], errors='coerce')
        valid = ~(highs.isna() | lows.isna() | closes.isna())
        if valid.sum() < period + 2:
            return None

        highs, lows, closes = highs[valid], lows[valid], closes[valid]
        prev_close = closes.shift(1)
        tr = pd.concat([(highs - lows), (highs - prev_close).abs(), (lows - prev_close).abs()], axis=1).max(axis=1)
        atr = tr.rolling(window=period, min_periods=period).mean().iloc[-1]
        price = float(closes.iloc[-1])
        if pd.isna(atr) or price <= 0:
            return None

        atr_pct = float(atr / price)
        self.atr_cache[symbol] = {'atr_pct': cache.get('atr_pct', 0.003),
                                  'raw_atr_pct': atr_pct,
                                  'timestamp': now}
        return atr_pct

    def _vol_mults_from_regime(self, atr_pct: float) -> Dict[str, float]:
        """
        Choose TP/SL/trail multipliers by regime. Keeps SL sane on HIGH vol,
        and prevents impossible TP on CALM pairs.
        """
        regime = self._get_volatility_regime(atr_pct or 0.02)  # default NORMAL-ish
        if regime == "CALM":      # <1.5%
            return {"tp_mult": 0.8, "sl_mult": 0.7, "trail_mult": 0.5, "be_mult": 0.6}
        if regime == "NORMAL":    # 1.5–3.5%
            return {"tp_mult": 1.1, "sl_mult": 0.9, "trail_mult": 0.7, "be_mult": 0.8}
        if regime == "ELEVATED":  # 3.5–5.5%
            return {"tp_mult": 1.3, "sl_mult": 1.0, "trail_mult": 0.9, "be_mult": 1.0}
        # HIGH
        return {"tp_mult": 1.6, "sl_mult": 1.1, "trail_mult": 1.2, "be_mult": 1.1}

    async def _build_tolerance_profile(self, symbol: str) -> ToleranceProfile:
        """Single source of truth for all ATR-based tolerances per symbol"""
        atr_pct = await self._get_atr_pct_latest(symbol) or 0.02
        regime = self._get_volatility_regime(atr_pct)

        clustering = min(max(atr_pct * 0.20, 0.0010), 0.0050)
        validation = min(max(atr_pct * 0.40, 0.0030), 0.0120)
        entry      = min(max(atr_pct * 0.25, 0.0020), 0.0080)
        proximity  = min(max(atr_pct * 0.50, 0.0050), 0.0200)

        base_close = validation * 0.8
        if regime == "CALM":      close_buf = max(0.0015, base_close * 0.75)
        elif regime == "NORMAL":  close_buf = max(0.0020, base_close * 0.85)
        elif regime == "ELEVATED":close_buf = max(0.0025, base_close * 0.95)
        else:                     close_buf = max(0.0035, base_close * 1.00)

        return ToleranceProfile(
            atr_pct=atr_pct, regime=regime,
            clustering_pct=clustering, validation_pct=validation,
            entry_pct=entry, proximity_pct=proximity,
            close_buffer_pct=close_buf, ts=datetime.now()
        )
    # ----------------------------------------------------------------------
    
    async def _get_atr_adaptive_tolerance(self, symbol: str, period: int = 14, days: int = 7,
                                        min_pct: float = 0.0015, max_pct: float = 0.008, 
                                        atr_fraction: float = 0.3, base_pct: float = 0.003) -> float:
        """
        Enhanced ATR-adaptive percentage tolerance that breathes with market volatility.
        """
        try:
            now = datetime.now()
            if symbol in self.atr_cache:
                cache_entry = self.atr_cache[symbol]
                if now - cache_entry['timestamp'] < self.atr_cache_duration:
                    logger.debug(f"📊 ATR CACHE HIT: {symbol} = {cache_entry['atr_pct']*100:.2f}%")
                    return cache_entry['atr_pct']
            
            df = await self.level_analyzer._get_historical_data(symbol, self.exchange_client, days=days)
            if df is None or len(df) < period + 5:
                logger.warning(f"⚠️ ATR FALLBACK: Insufficient data for {symbol}, using base {base_pct*100:.2f}%")
                return base_pct
            
            highs = pd.to_numeric(df['high'], errors='coerce')
            lows = pd.to_numeric(df['low'], errors='coerce')
            closes = pd.to_numeric(df['close'], errors='coerce')
            valid_mask = ~(highs.isna() | lows.isna() | closes.isna())
            if valid_mask.sum() < period + 2:
                logger.warning(f"⚠️ ATR FALLBACK: Invalid data for {symbol}, using base {base_pct*100:.2f}%")
                return base_pct
            
            highs = highs[valid_mask]
            lows = lows[valid_mask]
            closes = closes[valid_mask]
            prev_close = closes.shift(1)
            tr1 = highs - lows
            tr2 = (highs - prev_close).abs()
            tr3 = (lows - prev_close).abs()
            true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = true_range.rolling(window=period, min_periods=period).mean()
            current_atr = atr.iloc[-1]
            current_price = closes.iloc[-1]
            
            if pd.isna(current_atr) or pd.isna(current_price) or current_price <= 0:
                logger.warning(f"⚠️ ATR FALLBACK: Invalid ATR/price for {symbol}, using base {base_pct*100:.2f}%")
                return base_pct
            
            atr_pct = float(current_atr / current_price)
            adaptive_tolerance = atr_pct * atr_fraction
            final_tolerance = max(min_pct, min(max_pct, adaptive_tolerance))
            
            self.atr_cache[symbol] = {
                'atr_pct': final_tolerance,
                'timestamp': now
            }
            
            volatility_regime = self._get_volatility_regime(atr_pct)
            logger.info(f"📊 ATR ADAPTIVE: {symbol} = {final_tolerance*100:.2f}% "
                        f"(ATR: {atr_pct*100:.2f}%, Regime: {volatility_regime})")
            return final_tolerance
            
        except Exception as e:
            logger.error(f"❌ ATR calculation error for {symbol}: {e}")
            return base_pct
    
    # --- ATR-aware target calculator --------------------------------
    async def _calculate_targets_atr_aware(self, level: PriceLevel, current_price: float, symbol: str) -> Optional[TradingTargets]:
        try:
            position_size_usd = self.position_size_usd
            notional_value = position_size_usd * self.leverage
            fee_rate = 0.0004
            total_fees = position_size_usd * fee_rate * 2
            net_target, net_stop, net_floor = 17.60, 17.60, 14.60
            gross_target = net_target + total_fees
            gross_stop   = net_stop   + total_fees
            gross_floor  = net_floor  + total_fees

            min_tp_pct = float(gross_target / notional_value)
            min_sl_pct = float(gross_stop   / notional_value)
            min_fl_pct = float(gross_floor  / notional_value)

            atr_pct = await self._get_atr_pct_latest(symbol) or 0.02  # 2% fallback
            mults = self._vol_mults_from_regime(atr_pct)

            tp_pct_atr = atr_pct * mults["tp_mult"]
            sl_pct_atr = atr_pct * mults["sl_mult"]
            fl_pct_atr = atr_pct * mults["trail_mult"]

            tp_pct = max(min_tp_pct, tp_pct_atr)
            sl_pct = max(min_sl_pct, sl_pct_atr)
            fl_pct = max(min_fl_pct, fl_pct_atr)

            if level.level_type == 'support':  # LONG
                tp  = level.price * (1 + tp_pct)
                sl  = level.price * (1 - sl_pct)
                flp = level.price * (1 + fl_pct)
            else:                               # SHORT
                tp  = level.price * (1 - tp_pct)
                sl  = level.price * (1 + sl_pct)
                flp = level.price * (1 - fl_pct)

            return TradingTargets(
                entry_price=level.price,
                profit_target=tp,
                stop_loss=sl,
                profit_probability=0.72,
                risk_reward_ratio=tp_pct / sl_pct if sl_pct > 0 else 1.0,
                expected_duration_minutes=35,
                confidence_score=min(95, int(level.strength_score*0.6 + (1-abs(tp_pct-sl_pct))*40)),
                take_profit_net_usd=net_target,
                stop_loss_net_usd=net_stop,
                floor_net_usd=net_floor
            )
        except Exception as e:
            logger.error(f"ATR-aware target calc error for {symbol}: {e}")
            return None
    # ----------------------------------------------------------------------
    
    def _get_volatility_regime(self, atr_pct: float) -> str:
        """Classify market volatility regime based on ATR percentage"""
        if atr_pct < 0.015:  # < 1.5%
            return "CALM"
        elif atr_pct < 0.035:  # 1.5-3.5%
            return "NORMAL"
        elif atr_pct < 0.055:  # 3.5-5.5%
            return "ELEVATED"
        else:  # > 5.5%
            return "HIGH"
    
    def _price_for_locked_usd(self, trade: ActiveTrade, locked_usd: float) -> float:
        """Convert locked USD profit to stop-loss price."""
        try:
            denom = max(1e-12, trade.quantity * trade.leverage)
            delta = locked_usd / denom
            return trade.entry_price + delta if trade.side == 'LONG' else trade.entry_price - delta
        except Exception as e:
            logger.error(f"Error calculating price for locked USD {locked_usd}: {e}")
            return trade.stop_loss
    
    async def get_level_clustering_tolerance(self, symbol: str) -> float:
        """Get ATR-adaptive tolerance for price level clustering"""
        return await self._get_atr_adaptive_tolerance(
            symbol, 
            min_pct=0.001,      # 0.1% minimum for tight clustering
            max_pct=0.005,      # 0.5% maximum
            atr_fraction=0.2,   # 20% of ATR
            base_pct=0.002      # 0.2% fallback
        )
    
    async def get_level_validation_tolerance(self, symbol: str) -> float:
        """Get ATR-adaptive tolerance for level validation (touches, bounces)"""
        return await self._get_atr_adaptive_tolerance(
            symbol,
            min_pct=0.003,      # 0.3% minimum
            max_pct=0.012,      # 1.2% maximum
            atr_fraction=0.4,   # 40% of ATR
            base_pct=0.005      # 0.5% fallback
        )
    
    async def get_entry_tolerance(self, symbol: str) -> float:
        """Get ATR-adaptive tolerance for trade entry points (PATCHED: tighter like Main)"""
        return await self._get_atr_adaptive_tolerance(
            symbol,
            min_pct=0.0015,     # was 0.002
            max_pct=0.0030,     # was 0.008
            atr_fraction=0.15,  # was 0.25
            base_pct=0.0020     # was 0.003
        )
    
    async def get_proximity_tolerance(self, symbol: str) -> float:
        """Get ATR-adaptive tolerance for proximity checks (PATCHED: tighter)"""
        return await self._get_atr_adaptive_tolerance(
            symbol,
            min_pct=0.0030,     # was 0.005
            max_pct=0.0100,     # was 0.020
            atr_fraction=0.30,  # was 0.50
            base_pct=0.0040     # was 0.010
        )
    
    def _calculate_rule_based_targets(self, level: PriceLevel, current_price: float, symbol: str) -> TradingTargets:
        """Calculate targets based on rule mode configuration instead of statistical analysis"""
        try:
            position_size_usd = self.position_size_usd
            leverage = self.leverage
            notional_value = position_size_usd * leverage
            
            fee_rate = 0.0004
            entry_fee = position_size_usd * fee_rate
            exit_fee = position_size_usd * fee_rate
            total_fees = entry_fee + exit_fee
            
            net_target = 17.60
            net_stop = 17.60
            net_floor = 14.60
            gross_target = net_target + total_fees
            gross_stop = net_stop + total_fees
            gross_floor = net_floor + total_fees
            
            if level.level_type == 'support':  # LONG
                profit_target = level.price + (gross_target / notional_value) * level.price
            else:  # SHORT
                profit_target = level.price - (gross_target / notional_value) * level.price
            
            if level.level_type == 'support':  # LONG
                stop_loss = level.price - (gross_stop / notional_value) * level.price
            else:  # SHORT
                stop_loss = level.price + (gross_stop / notional_value) * level.price
            
            if level.level_type == 'support':  # LONG
                floor_activation_price = level.price + (gross_floor / notional_value) * level.price
            else:  # SHORT
                floor_activation_price = level.price - (gross_floor / notional_value) * level.price
            
            targets = TradingTargets(
                entry_price=level.price,
                profit_target=profit_target,
                stop_loss=stop_loss,
                profit_probability=0.75,
                risk_reward_ratio=1.0,
                expected_duration_minutes=30,
                confidence_score=80,
                take_profit_net_usd=net_target,
                stop_loss_net_usd=net_stop,
                floor_net_usd=net_floor
            )
            
            logger.info(f"🎯 RULE-BASED TARGETS for {symbol} {level.level_type}: "
                        f"Entry ${level.price:.4f}, TP ${profit_target:.4f}, SL ${stop_loss:.4f}")
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
            
            asyncio.create_task(self._monitoring_loop())
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
            batch_size = 5
            for i in range(0, len(symbols), batch_size):
                batch = symbols[i:i + batch_size]
                tasks = [self._analyze_symbol(symbol) for symbol in batch]
                await asyncio.gather(*tasks, return_exceptions=True)
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
            for trade_id in list(self.active_trades.keys()):
                await self._close_trade(trade_id, "MANUAL_STOP")
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
                        for symbol in self.monitored_symbols:
                            try:
                                await self._update_opportunities(symbol)
                                await self._check_entry_conditions(symbol)
                            except Exception as symbol_error:
                                logger.warning(f"⚠️ Error processing {symbol}: {symbol_error}")
                                continue
                        
                        try:
                            await self._monitor_active_trades()
                        except Exception as trade_error:
                            logger.warning(f"⚠️ Error monitoring trades: {trade_error}")
                        
                        if datetime.now().minute % 10 == 0:
                            for symbol in self.monitored_symbols:
                                try:
                                    await self._analyze_symbol(symbol)
                                except Exception as analyze_error:
                                    logger.warning(f"⚠️ Error analyzing {symbol}: {analyze_error}")
                                    continue
                        
                        await asyncio.sleep(5)
                    except Exception as cycle_error:
                        logger.error(f"❌ Error in monitoring cycle: {cycle_error}")
                        await asyncio.sleep(10)
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
            current_price = await self._get_current_price(symbol)
            if not current_price:
                return
            
            # ATR-aware analysis path enabled via self reference if analyzer supports it
            price_levels = await self.level_analyzer.analyze_symbol(symbol, self.exchange_client, profit_scraping_engine=self)
            self.identified_levels[symbol] = price_levels
            
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
            
            for level in price_levels:
                distance = abs(level.price - current_price) / current_price
                if distance > 0.03:  # More than 3% away
                    continue
                
                matching_magnet = None
                for magnet in magnet_levels:
                    if abs(magnet.price - level.price) / level.price < 0.01:  # Within 1%
                        matching_magnet = magnet
                        break
                
                # Keep rule-based targets for stability (as per our plan)
                targets = self._calculate_rule_based_targets(level, current_price, symbol)
                
                if targets:
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
            
            opportunities.sort(key=lambda x: x.opportunity_score, reverse=True)
            self.active_opportunities[symbol] = opportunities[:3]
        except Exception as e:
            logger.error(f"Error updating opportunities for {symbol}: {e}")
    
    async def _check_entry_conditions(self, symbol: str):
        """Check if any opportunities meet entry conditions"""
        try:
            opportunities = self.active_opportunities.get(symbol, [])
            current_trades = sum(1 for trade in self.active_trades.values() if trade.symbol == symbol)
            if current_trades >= self.max_trades_per_symbol:
                return
            
            current_price = await self._get_current_price(symbol)
            if not current_price:
                return
            
            for opportunity in opportunities:
                distance_to_level = abs(current_price - opportunity.level.price) / opportunity.level.price
                proximity_tolerance = await self.get_proximity_tolerance(opportunity.symbol)
                
                if distance_to_level <= proximity_tolerance:
                    if await self._validate_entry_conditions(opportunity, current_price):
                        logger.info(f"🎯 PROFIT SCRAPING: Entry conditions met for {opportunity.symbol} - signal ready")
                    break
        except Exception as e:
            logger.error(f"Error checking entry conditions for {symbol}: {e}")
    
    async def _validate_entry_conditions(self, opportunity: ScrapingOpportunity, current_price: float) -> bool:
        """Validate additional entry conditions with STRICT BOUNDS and CONFIRMATION REQUIREMENTS"""
        try:
            level = opportunity.level
            symbol = opportunity.symbol
            
            if not await self._validate_level_relevance(level, symbol):
                logger.info(f"❌ STALE LEVEL: {symbol} level @ {level.price:.6f} no longer relevant")
                return False
            
            tol_pct = await self.get_entry_tolerance(symbol)
            market_trend = await self._detect_market_trend(symbol)
            
            # Determine if this trade is counter-trend (for stricter gating)
            is_counter = ((level.level_type == 'support' and market_trend in ['downtrend','strong_downtrend']) or
                          (level.level_type == 'resistance' and market_trend in ['uptrend','strong_uptrend']))
            if is_counter:
                proximity_tolerance = await self.get_proximity_tolerance(symbol)
                # PATCHED: slightly softer than before but still strict
                if level.strength_score < 88:  # was 92
                    logger.info(f"❌ COUNTER-TREND BLOCK: {symbol} level strength {level.strength_score} < 88")
                    return False
                if abs(current_price - level.price)/level.price > (proximity_tolerance * 0.75):  # was * 0.5
                    logger.info(f"❌ COUNTER-TREND BLOCK: {symbol} too far from level for counter-trend entry")
                    return False
            
            if level.level_type == 'support':
                lower = level.price * 1.000
                upper = level.price * (1 + tol_pct)
                if not (lower <= current_price <= upper):
                    logger.info(f"❌ BOUNDS CHECK: {symbol} price ${current_price:.6f} not in support range "
                                f"[${lower:.6f}, ${upper:.6f}] (tol: {tol_pct*100:.3f}%)")
                    return False
                
                if market_trend in ['strong_downtrend', 'downtrend'] and level.strength_score < 85:
                    logger.info(f"❌ TREND FILTER: Skipping LONG {symbol} - downtrend + insufficient support strength ({level.strength_score})")
                    return False
                
                if not await self._validate_support_bounce(symbol, level.price, current_price):
                    logger.info(f"❌ BOUNCE CONFIRMATION: {symbol} support bounce not confirmed - blocking trade")
                    return False
                
                if not await self._wait_for_confirmation_candle(symbol, level, 'LONG'):
                    logger.info(f"❌ CONFIRMATION CANDLE: {symbol} LONG confirmation not received")
                    return False
                
                return True
            
            elif level.level_type == 'resistance':
                lower = level.price * (1 - tol_pct)
                upper = level.price * 1.000
                if not (lower <= current_price <= upper):
                    logger.info(f"❌ BOUNDS CHECK: {symbol} price ${current_price:.6f} not in resistance range "
                                f"[${lower:.6f}, ${upper:.6f}] (tol: {tol_pct*100:.3f}%)")
                    return False
                
                if market_trend in ['strong_uptrend', 'uptrend'] and level.strength_score < 85:
                    logger.info(f"❌ TREND FILTER: Skipping SHORT {symbol} - uptrend + insufficient resistance strength ({level.strength_score})")
                    return False
                
                if not await self._validate_resistance_rejection(symbol, level.price):
                    logger.info(f"❌ REJECTION CONFIRMATION: {symbol} resistance rejection not confirmed - blocking trade")
                    return False
                
                if not await self._wait_for_confirmation_candle(symbol, level, 'SHORT'):
                    logger.info(f"❌ CONFIRMATION CANDLE: {symbol} SHORT confirmation not received")
                    return False
            
            return True
        except Exception as e:
            logger.error(f"Error validating entry conditions: {e}")
            return False
    
    async def _wait_for_confirmation_candle(self, symbol: str, level: PriceLevel, direction: str) -> bool:
        """Wait for a confirmation candle to close before entering trade"""
        try:
            recent_data = await self.level_analyzer._get_historical_data(symbol, self.exchange_client, days=1)
            if recent_data is None or len(recent_data) < 2:
                logger.warning(f"Insufficient data for confirmation candle check: {symbol}")
                return False
            
            tol_pct = await self.get_level_validation_tolerance(symbol)
            regime = self._get_volatility_regime(await self._get_atr_pct_latest(symbol) or 0.02)

            # PATCHED: softer minima to avoid late/expensive fills
            if regime == "CALM":
                close_pct = max(0.0012, tol_pct * 0.6)  # was 0.0015
            elif regime == "NORMAL":
                close_pct = max(0.0015, tol_pct * 0.7)  # was 0.0020
            elif regime == "ELEVATED":
                close_pct = max(0.0020, tol_pct * 0.8)  # was 0.0025
            else:  # HIGH
                close_pct = max(0.0030, tol_pct * 0.9)  # was 0.0035
            
            last_candle = recent_data.iloc[-2]
            open_price = float(last_candle['open'])
            high_price = float(last_candle['high'])
            low_price = float(last_candle['low'])
            close_price = float(last_candle['close'])
            
            if direction == 'LONG' and level.level_type == 'support':
                touched = low_price <= level.price * (1 + tol_pct)
                closed = close_price >= level.price * (1 + close_pct)
                bullish = close_price > open_price
                confirmation = touched and closed and bullish
                logger.info(f"🕯️ LONG confirmation {symbol}: Touch={touched}, Close={closed}, Bullish={bullish} "
                            f"→ {confirmation} (touch: {tol_pct*100:.3f}%, close: {close_pct*100:.3f}%)")
                return confirmation
                
            elif direction == 'SHORT' and level.level_type == 'resistance':
                touched = high_price >= level.price * (1 - tol_pct)
                closed = close_price <= level.price * (1 - close_pct)
                bearish = close_price < open_price
                confirmation = touched and closed and bearish
                logger.info(f"🕯️ SHORT confirmation {symbol}: Touch={touched}, Close={closed}, Bearish={bearish} "
                            f"→ {confirmation} (touch: {tol_pct*100:.3f}%, close: {close_pct*100:.3f}%)")
                return confirmation
            
            logger.warning(f"Invalid direction/level combination: {direction}/{level.level_type}")
            return False
        except Exception as e:
            logger.error(f"Error checking confirmation candle: {e}")
            return False
    
    async def _execute_trade(self, opportunity: ScrapingOpportunity, current_price: float):
        """Execute a profit scraping trade"""
        try:
            logger.info(f"🎯 Executing trade for {opportunity.symbol} at ${current_price:.2f}")
            side = 'LONG' if opportunity.level.level_type == 'support' else 'SHORT'
            
            position_size = self.stat_calculator.get_optimal_position_size(
                opportunity.targets, self.account_balance, self.max_risk_per_trade
            )
            
            logger.info(f"🎯 PROFIT SCRAPING: Executing trade without ML filtering (temporarily disabled)")
            
            trade_result = None
            if self.is_real_trading and self.real_trading_engine:
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
                trading_signal = {
                    'symbol': opportunity.symbol,
                    'direction': side,
                    'entry_price': current_price,
                    'strategy': 'profit_scraping_engine',
                    'confidence': opportunity.targets.confidence_score / 100.0,
                    'signal_id': f"profit_scraping_{opportunity.symbol}_{int(datetime.now().timestamp())}",
                    'stop_loss': opportunity.targets.stop_loss,
                    'take_profit': opportunity.targets.profit_target,
                    'optimal_leverage': self.leverage,
                    'tp_net_usd': opportunity.targets.take_profit_net_usd,
                    'sl_net_usd': opportunity.targets.stop_loss_net_usd,
                    'floor_net_usd': opportunity.targets.floor_net_usd
                }
                position_id = await self.paper_trading_engine.execute_virtual_trade(
                    trading_signal, 500.0
                )
                trade_result = {'success': position_id is not None, 'position_id': position_id}
            
            if trade_result and trade_result.get('success'):
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
        """Monitor active trades for exit conditions with enhanced step-trailing."""
        try:
            current_time = datetime.now()

            for trade_id, trade in list(self.active_trades.items()):
                current_price = await self._get_current_price(trade.symbol)
                if not current_price:
                    continue

                profit_hit = current_price >= trade.profit_target if trade.side == 'LONG' else current_price <= trade.profit_target
                stop_hit = current_price <= trade.stop_loss if trade.side == 'LONG' else current_price >= trade.stop_loss

                # Step-trailing
                if trade.quantity > 0:
                    pnl_pct = ((current_price - trade.entry_price) if trade.side == 'LONG'
                               else (trade.entry_price - current_price)) / max(1e-12, trade.entry_price)
                    notional = trade.quantity * trade.entry_price
                    unrealized_usd = pnl_pct * trade.leverage * notional

                    if unrealized_usd > 0:
                        start_threshold = trade.trail_start_net_usd + trade.fee_buffer_usd
                        if unrealized_usd >= start_threshold:
                            step_usd = (trade.step_increment_pct * trade.leverage * notional
                                        if trade.step_mode_percent else trade.step_increment_usd)

                            next_step_base = max(step_usd, trade.last_step_usd + step_usd)
                            target_to_lock = min(trade.max_trail_cap_usd, next_step_base)
                            hysteresis_add = max(0.0, trade.hysteresis_pct * trade.entry_price * trade.quantity * trade.leverage)
                            arm_level_usd = target_to_lock + hysteresis_add

                            now = datetime.now()
                            cooled = (trade.last_step_time is None) or ((now - trade.last_step_time).total_seconds() >= trade.step_cooldown_sec)

                            if unrealized_usd >= arm_level_usd and cooled:
                                trade.locked_profit_usd = target_to_lock
                                new_sl_price = self._price_for_locked_usd(trade, trade.locked_profit_usd)

                                if trade.side == 'LONG':
                                    if new_sl_price > trade.stop_loss:
                                        trade.stop_loss = new_sl_price
                                        trade.last_step_usd = target_to_lock
                                        trade.last_step_time = now
                                        logger.info(f"🔒 STEP TRAIL {trade.trade_id}: SL -> {trade.stop_loss:.6f} (locked ${trade.locked_profit_usd:.2f})")
                                else:
                                    if (trade.stop_loss == 0) or (new_sl_price < trade.stop_loss):
                                        trade.stop_loss = new_sl_price
                                        trade.last_step_usd = target_to_lock
                                        trade.last_step_time = now
                                        logger.info(f"🔒 STEP TRAIL {trade.trade_id}: SL -> {trade.stop_loss:.6f} (locked ${trade.locked_profit_usd:.2f})")

                            # Cap hand-off
                            if trade.cap_handoff_tight_atr and trade.locked_profit_usd >= trade.max_trail_cap_usd:
                                atr_pct = await self._get_atr_pct_latest(trade.symbol) or 0.02
                                tight_gap = max(atr_pct * trade.cap_trail_mult, 0.0012)
                                cap_sl = (current_price * (1 - tight_gap) if trade.side == 'LONG'
                                          else current_price * (1 + tight_gap))

                                if trade.side == 'LONG':
                                    if cap_sl > trade.stop_loss:
                                        trade.stop_loss = cap_sl
                                        logger.info(f"🎯 CAP HANDOFF {trade.trade_id}: Tight ATR SL -> {trade.stop_loss:.6f}")
                                else:
                                    if (trade.stop_loss == 0) or (cap_sl < trade.stop_loss):
                                        trade.stop_loss = cap_sl
                                        logger.info(f"🎯 CAP HANDOFF {trade.trade_id}: Tight ATR SL -> {trade.stop_loss:.6f}")

                # ATR breakeven & trail
                atr_pct = await self._get_atr_pct_latest(trade.symbol) or 0.02
                mults = self._vol_mults_from_regime(atr_pct)

                favor_pct = ((current_price - trade.entry_price) if trade.side == 'LONG'
                             else (trade.entry_price - current_price)) / trade.entry_price

                if favor_pct >= (atr_pct * mults["be_mult"]):
                    be_buffer = max(0.0006, atr_pct * 0.1)
                    new_sl = (trade.entry_price * (1 - be_buffer) if trade.side == 'LONG'
                              else trade.entry_price * (1 + be_buffer))
                    if (trade.side == 'LONG' and new_sl > trade.stop_loss) or (trade.side == 'SHORT' and new_sl < trade.stop_loss):
                        trade.stop_loss = new_sl
                        logger.info(f"🔒 BE SET {trade.trade_id}: SL -> {trade.stop_loss:.6f}")

                if favor_pct >= (atr_pct * (mults["be_mult"] + mults["trail_mult"])):
                    trail_gap = atr_pct * mults["trail_mult"]
                    new_sl = (current_price * (1 - trail_gap) if trade.side == 'LONG'
                              else current_price * (1 + trail_gap))
                    if (trade.side == 'LONG' and new_sl > trade.stop_loss) or (trade.side == 'SHORT' and new_sl < trade.stop_loss):
                        trade.stop_loss = new_sl
                        logger.info(f"📈 ATR TRAIL {trade.trade_id}: SL -> {trade.stop_loss:.6f}")

                # Time-based exits
                time_elapsed_minutes = (current_time - trade.entry_time).total_seconds() / 60
                market_trend = await self._detect_market_trend(trade.symbol)
                aligned = ((trade.side == 'LONG'  and market_trend in ['uptrend','strong_uptrend']) or
                           (trade.side == 'SHORT' and market_trend in ['downtrend','strong_downtrend']))
                counter = ((trade.side == 'LONG'  and market_trend in ['downtrend','strong_downtrend']) or
                           (trade.side == 'SHORT' and market_trend in ['uptrend','strong_uptrend']))

                max_hold = 90 if aligned else 45 if counter else 60
                flat_cut = 30 if aligned else 10 if counter else 15

                quick_exit = False
                exit_reason_time = ""
                if time_elapsed_minutes > max_hold:
                    quick_exit = True
                    exit_reason_time = "TIME_EXIT_MAX"
                elif time_elapsed_minutes > flat_cut:
                    min_edge = max(0.0020, (await self._get_atr_pct_latest(trade.symbol) or 0.02) * 0.8)
                    edge = ((current_price - trade.entry_price) if trade.side == 'LONG'
                            else (trade.entry_price - current_price)) / trade.entry_price
                    if edge <= min_edge:
                        quick_exit = True
                        exit_reason_time = "TIME_EXIT_FLAT"

                safety_time_exit = (time_elapsed_minutes / 60 > 24) and (
                    (trade.side == 'LONG' and current_price < trade.entry_price * 0.95) or
                    (trade.side == 'SHORT' and current_price > trade.entry_price * 1.05)
                )

                if profit_hit:
                    await self._close_trade(trade_id, "PROFIT_TARGET")
                elif stop_hit:
                    await self._close_trade(trade_id, "STOP_LOSS")
                elif quick_exit:
                    await self._close_trade(trade_id, exit_reason_time)
                    logger.info(f"⏰ Time exit: {trade_id} after {time_elapsed_minutes:.1f} minutes - {exit_reason_time}")
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
                if trade.side == 'LONG':
                    pnl_pct = (current_price - trade.entry_price) / trade.entry_price
                else:  # SHORT
                    pnl_pct = (trade.entry_price - current_price) / trade.entry_price
                
                leveraged_pnl_pct = pnl_pct * trade.leverage
                pnl_amount = leveraged_pnl_pct * (trade.quantity * trade.entry_price)
                
                self.total_profit += pnl_amount
                if pnl_amount > 0:
                    self.winning_trades += 1
                
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
                
                if self.is_real_trading and self.real_trading_engine:
                    await self.real_trading_engine.close_position(trade_id, exit_reason)
                
                logger.info(f"🔚 Trade closed: {trade_id} - {exit_reason} - P&L: ${pnl_amount:.2f}")
            
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
            base_score = level.strength_score * 0.3
            targets_score = targets.confidence_score * 0.4
            distance_score = (1 - min(distance / 0.03, 1)) * 20
            magnet_bonus = 10 if (magnet_level and magnet_level.strength >= 60) else 0
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
            return {'active': False, 'error': str(e)}
    
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
                        distance_to_level = abs(current_price - opportunity.level.price) / opportunity.level.price
                        proximity_tolerance = await self.get_proximity_tolerance(opportunity.symbol)
                        
                        if distance_to_level <= proximity_tolerance:
                            if await self._validate_entry_conditions(opportunity, current_price):
                                side = 'LONG' if opportunity.level.level_type == 'support' else 'SHORT'
                                signal = {
                                    'symbol': opportunity.symbol,
                                    'direction': side,
                                    'confidence': opportunity.targets.confidence_score / 100.0,
                                    'strategy': 'profit_scraping_engine',
                                    'signal_source': 'profit_scraping_engine',
                                    'ml_score': opportunity.targets.confidence_score / 100.0,
                                    'entry_reason': f"profit_scraping_{opportunity.level.level_type}",
                                    'market_regime': 'level_based',
                                    'volatility_regime': 'medium',
                                    'entry_price': current_price,
                                    'profit_target': opportunity.targets.profit_target,
                                    'stop_loss': opportunity.targets.stop_loss,
                                    'opportunity_score': opportunity.opportunity_score,
                                    'optimal_leverage': self.leverage,
                                    'tp_net_usd': opportunity.targets.take_profit_net_usd,
                                    'sl_net_usd': opportunity.targets.stop_loss_net_usd,
                                    'floor_net_usd': opportunity.targets.floor_net_usd
                                }
                                
                                ready_signals.append(signal)
                                logger.info(f"🎯 PROFIT SCRAPING SIGNAL: {symbol} {side} @ ${current_price:.4f} "
                                            f"(distance: {distance_to_level:.3f}%)")
                                
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
            short_tf = await self.level_analyzer._get_historical_data(symbol, self.exchange_client, days=7)
            medium_tf = await self.level_analyzer._get_historical_data(symbol, self.exchange_client, days=21)
            long_tf = await self.level_analyzer._get_historical_data(symbol, self.exchange_client, days=60)
            
            if any(df is None or len(df) < 20 for df in [short_tf, medium_tf, long_tf]):
                logger.warning(f"Insufficient data for multi-timeframe trend analysis: {symbol}")
                return 'neutral'
            
            short_trend = self._calculate_trend_score(short_tf)
            medium_trend = self._calculate_trend_score(medium_tf)
            long_trend = self._calculate_trend_score(long_tf)
            combined_score = (short_trend * 0.5) + (medium_trend * 0.3) + (long_trend * 0.2)
            
            logger.info(f"📊 Multi-TF trend {symbol}: Short={short_trend:.3f}, Medium={medium_trend:.3f}, Long={long_trend:.3f}, Combined={combined_score:.3f}")
            
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
            recent_avg = closes.tail(5).mean()
            older_avg = closes.head(5).mean()
            momentum_score = (recent_avg - older_avg) / older_avg
            
            ma_20 = closes.rolling(20).mean()
            ma_slope = (ma_20.iloc[-1] - ma_20.iloc[-10]) / ma_20.iloc[-10] if len(ma_20) >= 10 else 0
            
            highs = df['high'].astype(float)
            lows = df['low'].astype(float)
            recent_high = highs.tail(10).max()
            recent_low = lows.tail(10).min()
            earlier_high = highs.head(10).max()
            earlier_low = lows.head(10).min()
            
            hh_ll_score = 0
            if recent_high > earlier_high and recent_low > earlier_low:
                hh_ll_score = 0.01
            elif recent_high < earlier_high and recent_low < earlier_low:
                hh_ll_score = -0.01
            
            trend_score = (momentum_score * 0.5) + (ma_slope * 0.3) + (hh_ll_score * 0.2)
            return trend_score
        except Exception as e:
            logger.error(f"Error calculating trend score: {e}")
            return 0.0
    
    async def _validate_level_relevance(self, level: PriceLevel, symbol: str) -> bool:
        """Validate that a historical level is still relevant in current market structure"""
        try:
            recent_data = await self.level_analyzer._get_historical_data(symbol, self.exchange_client, days=7)
            if recent_data is None or len(recent_data) < 20:
                logger.warning(f"Insufficient data for level relevance check: {symbol}")
                return False
            
            current_price = float(recent_data['close'].iloc[-1])
            days_since_last_test = (datetime.now() - level.last_tested).days
            if days_since_last_test > 30:
                logger.info(f"⏰ STALE LEVEL: {symbol} level @ {level.price:.6f} last tested {days_since_last_test} days ago")
                return False
            
            distance_pct = abs(level.price - current_price) / current_price
            if distance_pct > 0.15:
                logger.info(f"📏 DISTANT LEVEL: {symbol} level @ {level.price:.6f} is {distance_pct:.1%} from current price")
                return False
            
            if level.volume_confirmation < 0.8:
                logger.info(f"📊 LOW VOLUME LEVEL: {symbol} level @ {level.price:.6f} formed on low volume ({level.volume_confirmation:.2f})")
                return False
            
            recent_touches = 0
            validation_tolerance_pct = await self.get_level_validation_tolerance(symbol)
            tolerance = level.price * validation_tolerance_pct
            
            logger.debug(f"📊 Using adaptive validation tolerance: {validation_tolerance_pct*100:.3f}% for {symbol}")
            
            for _, candle in recent_data.tail(20).iterrows():
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
            return False
    
    async def _validate_support_bounce(self, symbol: str, support_level: float, current_price: float) -> bool:
        """Validate that support level is actually bouncing (not breaking)"""
        try:
            historical_data = await self.level_analyzer._get_historical_data(symbol, self.exchange_client)
            if historical_data is None or len(historical_data) < 10:
                logger.warning(f"Insufficient data to validate support bounce for {symbol}")
                return False
            
            tol_pct = await self.get_level_validation_tolerance(symbol)
            tolerance = support_level * tol_pct
            close_up_pct = max(0.002, tol_pct * 0.8)
            
            recent_candles = historical_data.tail(10)
            touches = 0
            bounces = 0
            
            for _, candle in recent_candles.iterrows():
                low = float(candle['low'])
                close = float(candle['close'])
                
                if support_level - tolerance <= low <= support_level + tolerance:
                    touches += 1
                    if close >= support_level * (1 + close_up_pct):
                        bounces += 1
            
            if touches == 0:
                return True  # No recent tests, allow
            
            bounce_rate = bounces / touches
            logger.info(f"🔍 Support validation {symbol}: {bounces}/{touches} bounces ({bounce_rate:.2%}) "
                        f"(touch: {tol_pct*100:.3f}%, close: {close_up_pct*100:.3f}%)")
            return bounce_rate >= 0.5
        except Exception as e:
            logger.error(f"Error validating support bounce: {e}", exc_info=True)
            return False
    
    async def _validate_resistance_rejection(self, symbol: str, resistance_level: float) -> bool:
        """Validate that resistance level is actually rejecting price (not being broken)"""
        try:
            historical_data = await self.level_analyzer._get_historical_data(symbol, self.exchange_client)
            if historical_data is None or len(historical_data) < 10:
                logger.warning(f"Insufficient data to validate resistance rejection for {symbol}")
                return False
            
            tol_pct = await self.get_level_validation_tolerance(symbol)
            tolerance = resistance_level * tol_pct
            close_dn_pct = max(0.002, tol_pct * 0.8)
            
            recent_candles = historical_data.tail(10)
            touches = 0
            rejections = 0
            
            for _, candle in recent_candles.iterrows():
                high = float(candle['high'])
                close = float(candle['close'])
                
                if resistance_level - tolerance <= high <= resistance_level + tolerance:
                    touches += 1
                    if close <= resistance_level * (1 - close_dn_pct):
                        rejections += 1
            
            if touches == 0:
                return True  # No recent tests, allow
            
            rejection_rate = rejections / touches
            logger.info(f"🔍 Resistance validation {symbol}: {rejections}/{touches} rejections ({rejection_rate:.2%}) "
                        f"(touch: {tol_pct*100:.3f}%, close: {close_dn_pct*100:.3f}%)")
            return rejection_rate >= 0.5
        except Exception as e:
            logger.error(f"Error validating resistance rejection: {e}", exc_info=True)
            return False
