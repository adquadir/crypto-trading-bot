"""
Real Trading Engine
For actual money trading with real exchange connections using OpportunityManager signals only
"""

import asyncio
import logging
import time
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional, List

from ..market_data.exchange_client import ExchangeClient
from ..database.database import Database
from ..utils.logger import setup_logger
from ..utils.time_utils import format_duration
from .trade_sync_service import TradeSyncService

logger = setup_logger(__name__)

@dataclass
class LivePosition:
    """Represents a live trading position"""
    position_id: str
    symbol: str
    side: str               # LONG / SHORT
    entry_price: float
    qty: float
    stake_usd: float
    leverage: float
    entry_time: datetime
    tp_order_id: Optional[str] = None
    sl_order_id: Optional[str] = None
    tp_price: Optional[float] = None     # Take profit price for UI display
    sl_price: Optional[float] = None     # Stop loss price for UI display
    highest_profit_ever: float = 0.0     # gross PnL tracking
    profit_floor_activated: bool = False # $7 floor tracking
    status: str = 'OPEN'    # OPEN, CLOSED, CANCELLED
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    pnl: float = 0.0
    pnl_pct: float = 0.0
    # NEW: trailing floor that ratchets in $10 steps
    dynamic_trailing_floor: float = 0.0
    # NEW: Live P&L fields for frontend display
    current_price: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    unrealized_pnl_pct: Optional[float] = None
    # NEW: Exchange state verification
    first_seen_open: bool = False
    entry_exchange_verified_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        """Convert position to dictionary for API responses"""
        return {
            'position_id': self.position_id,
            'symbol': self.symbol,
            'side': self.side,
            'entry_price': self.entry_price,
            'qty': self.qty,
            'stake_usd': self.stake_usd,
            'leverage': self.leverage,
            'entry_time': self.entry_time.isoformat(),
            'tp_order_id': self.tp_order_id,
            'sl_order_id': self.sl_order_id,
            'tp_price': self.tp_price,  # Include TP price for UI display
            'sl_price': self.sl_price,  # Include SL price for UI display
            'highest_profit_ever': self.highest_profit_ever,
            'profit_floor_activated': self.profit_floor_activated,
            'status': self.status,
            'exit_price': self.exit_price,
            'exit_time': self.exit_time.isoformat() if self.exit_time else None,
            'pnl': self.pnl,
            'pnl_pct': self.pnl_pct,
            # NEW: Live P&L fields for frontend display
            'current_price': self.current_price,
            'unrealized_pnl': self.unrealized_pnl,
            'unrealized_pnl_pct': self.unrealized_pnl_pct,
        }

class RealTradingEngine:
    """
    Real trading engine that mirrors paper trading behavior but executes live orders.
    - Uses only Opportunity Manager signals
    - Fixed $200 stake per trade
    - Pure 3-rule mode: $10 TP → $7 floor → 0.5% SL
    """
    
    def __init__(self, config: Dict[str, Any], exchange_client: Optional[ExchangeClient] = None):
        if exchange_client is None:
            raise ValueError("RealTradingEngine requires an exchange_client")
        
        self.config = config
        self.cfg = config.get("real_trading", {}) or {}
        self.enabled = bool(self.cfg.get("enabled", False))
        self.exchange_client = exchange_client
        self.db_manager = Database()
        
        # OpportunityManager connection (set via connect_opportunity_manager)
        self.opportunity_manager = None
        
        # Real trading configuration - CONSERVATIVE FOR REAL MONEY
        self.stake_usd = float(self.cfg.get("stake_usd", 100.0))  # $100 capital per position
        self.stake_mode = str(self.cfg.get("stake_mode", "NOTIONAL")).upper()  # NOTIONAL | MARGIN
        self.margin_mode = str(self.cfg.get("margin_mode", "ISOLATED")).upper()  # ISOLATED | CROSS
        self.default_leverage = float(self.cfg.get("default_leverage", 10))  # Default 10x leverage
        self.max_positions = int(self.cfg.get("max_positions", 20))
        self.accept_sources = set(self.cfg.get("accept_sources", ["opportunity_manager"]))
        
        # NEW: order placement toggles
        self.enable_take_profit = bool(self.cfg.get("enable_take_profit", True))
        self.enable_stop_loss = bool(self.cfg.get("enable_stop_loss", True))
        
        # Pure 3-rule mode configuration
        self.pure_3_rule_mode = bool(self.cfg.get("pure_3_rule_mode", True))
        self.primary_target_dollars = float(self.cfg.get("primary_target_dollars", 10.0))
        self.absolute_floor_dollars = float(self.cfg.get("absolute_floor_dollars", 7.0))
        self.stop_loss_percent = float(self.cfg.get("stop_loss_percent", 0.5)) / 100.0  # 0.5%
        
        # Position tracking
        self.positions: Dict[str, LivePosition] = {}   # key: position_id
        self.positions_by_symbol: Dict[str, str] = {}  # symbol -> position_id
        
        # Engine state
        self.is_running = False
        self.start_time = None
        self.total_pnl = 0.0
        self.total_trades = 0
        self.winning_trades = 0
        self.daily_pnl = 0.0
        self.last_reset_date = datetime.now().date()
        
        # Frontend compatibility - in-memory completed trades list
        self.completed_trades: List[Dict[str, Any]] = []
        
        # NEW: Comprehensive statistics tracking for observability
        self.stats = {
            'rejections': {
                'missing_fields': 0,
                'not_tradable': 0,
                'not_real_data': 0,
                'low_confidence': 0,
                'source_mismatch': 0,
                'total': 0
            },
            'skips': {
                'stale_signal': 0,
                'price_drift': 0,
                'min_notional': 0,
                'symbol_exists': 0,
                'max_positions': 0,
                'total': 0
            },
            'successes': {
                'positions_opened': 0,
                'positions_closed': 0,
                'total': 0
            },
            'errors': {
                'exchange_errors': 0,
                'order_failures': 0,
                'price_lookup_failures': 0,
                'total': 0
            },
            'last_reset': datetime.now().isoformat()
        }
        
        # Safety controls
        self.emergency_stop = False
        self.max_daily_loss = 500.0  # Conservative $500 daily loss limit
        
        # Poll intervals
        self.signal_poll_sec = 5
        self.position_poll_sec = 3
        
        # Manual trade learning
        self.trade_sync_service = TradeSyncService(self.exchange_client)
        
        logger.info("🚀 Real Trading Engine initialized - OpportunityManager only, $%.2f per trade", self.stake_usd)
    
    # =========================
    # PROFIT-FIRST RANKING HELPERS (NEW)
    # =========================
    def _compute_expected_profit_usd(self, s: Dict[str, Any], stake_amount: float, leverage: float) -> float:
        """
        Best-effort expected profit in USD for ranking.
        Preference order:
          1) explicit fields from strategies/OM: expected_profit, tp_net_usd, expected_profit_100
          2) derive from entry/TP and notional = stake * leverage / entry
        """
        # 1) Prefer explicit fields if present
        for k in ("expected_profit", "tp_net_usd", "expected_profit_100"):
            v = s.get(k)
            if v is None:
                continue
            try:
                v = float(v)
                if v > 0:
                    return v
            except Exception:
                pass

        # 2) Derive from prices
        try:
            direction = (s.get("direction") or s.get("side") or "LONG").upper()
            entry = float(s.get("entry_price") or s.get("entry") or 0.0)
            tp    = float(s.get("take_profit") or 0.0)
            if entry <= 0 or tp <= 0:
                return 0.0
            qty   = (stake_amount * float(leverage)) / entry
            delta = (tp - entry) if direction == "LONG" else (entry - tp)
            pnl   = max(0.0, qty * delta)  # upside-only for ranking
            return pnl
        except Exception:
            return 0.0

    def _rank_signals(self, signals: List[Dict[str, Any]], stake_amount: float, leverage: float) -> List[Dict[str, Any]]:
        """
        Sort signals so we always try the most profitable first, then by:
           expected_profit_usd DESC → confidence DESC → risk/reward DESC → volatility ASC → tiny deterministic jitter
        """
        ranked: List[Dict[str, Any]] = []

        # Optional config weights (safe defaults if not present)
        ranking_cfg = (self.cfg or {}).get("ranking", {})
        weight_profit = float(ranking_cfg.get("weight_profit", 1.0))
        weight_conf   = float(ranking_cfg.get("weight_confidence", 0.0))  # can be >0 later if desired

        minute_bucket = int(time.time() // 60)

        for s in signals:
            x = dict(s)  # avoid mutating caller's object

            # Normalize fields present in OpportunityManager outputs
            # (OM already supplies these fields; see OM opportunity fields) 
            try:
                x["confidence"] = float(x.get("confidence", x.get("confidence_score", 0.0)) or 0.0)
            except Exception:
                x["confidence"] = 0.0
            try:
                x["risk_reward"] = float(x.get("risk_reward", 0.0) or 0.0)
            except Exception:
                x["risk_reward"] = 0.0
            try:
                # OM publishes volatility as percent in some flows; lower is better. If missing, set high number.
                x["volatility"] = float(x.get("volatility", 999.0) or 999.0)
            except Exception:
                x["volatility"] = 999.0

            ep = self._compute_expected_profit_usd(x, stake_amount, leverage)
            # Bucket to cents to avoid noisy reordering
            x["_ep_bucket"] = round(ep, 2)

            # Deterministic micro-jitter so exact ties don't always pick the same symbol
            sym = x.get("symbol", "UNKNOWN")
            x["_jitter"] = (hash(f"{sym}:{minute_bucket}") % 1000) / 1e9

            # Linear score (optional) = weight_profit * EP + weight_conf * confidence
            x["_lin_score"] = (weight_profit * x["_ep_bucket"]) + (weight_conf * x["confidence"])

            ranked.append(x)

        # Sort by tuple: EP/score → confidence → R/R → lower volatility → jitter
        ranked.sort(
            key=lambda r: (
                r["_lin_score"],                # primary aggregate
                r["confidence"],
                r["risk_reward"],
                -r["volatility"],               # lower vol first
                r["_jitter"]
            ),
            reverse=True
        )
        return ranked

    def connect_opportunity_manager(self, manager: Any) -> None:
        """Connect the OpportunityManager to this engine"""
        self.opportunity_manager = manager
        logger.info("🔗 OpportunityManager connected to Real Trading Engine")
    
    async def start_trading(self, symbols: List[str] = None) -> bool:
        """Start real trading for specified symbols"""
        try:
            if self.is_running:
                logger.warning("Real trading is already running")
                return False
            
            if not self.enabled:
                logger.error("❌ Real trading is disabled in configuration")
                return False
            
            if not self.opportunity_manager:
                logger.error("❌ OpportunityManager not connected - cannot start real trading")
                return False
            
            # Test exchange connection (real health check)
            try:
                balance = await self.exchange_client.get_account_balance()
                if not balance or balance.get('total', 0) < 100:
                    logger.error("❌ SAFETY: Insufficient account balance for real trading")
                    return False
                logger.info(f"✅ Account balance verified: ${balance.get('total', 0):.2f}")
            except Exception as e:
                logger.error(f"❌ SAFETY: Cannot connect to exchange: {e}")
                return False
            
            self.is_running = True
            self.start_time = datetime.now()
            
            # Start trade sync service for manual trade learning
            if self.trade_sync_service:
                await self.trade_sync_service.start_sync()
                logger.info("🔄 Trade synchronization service started")
            
            # Start core loops
            asyncio.create_task(self._signal_collection_loop())
            asyncio.create_task(self._position_monitoring_loop())
            
            logger.info(f"🚀 Real Trading started - OpportunityManager only")
            logger.warning("⚠️  REAL MONEY TRADING IS NOW ACTIVE")
            logger.warning("⚠️  ALL TRADES WILL USE ACTUAL FUNDS")
            logger.info(f"💰 Configuration: ${self.stake_usd} per trade, max {self.max_positions} positions")
            
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
            for position_id in list(self.positions.keys()):
                await self._market_close_position(position_id, "SYSTEM_STOP")
            
            self.is_running = False
            
            logger.info("✅ Real trading stopped")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping real trading: {e}")
            return False
    
    async def _signal_collection_loop(self):
        """Collect signals from OpportunityManager and execute trades"""
        logger.info("🔄 Starting OpportunityManager signal collection loop")
        
        while self.is_running:
            try:
                # Respect max open positions
                if len(self.positions) >= self.max_positions:
                    await asyncio.sleep(self.signal_poll_sec)
                    continue
                
                # Safety checks
                if self.emergency_stop:
                    logger.warning("Emergency stop is active - no new trades")
                    await asyncio.sleep(self.signal_poll_sec)
                    continue
                
                # Get opportunities from OpportunityManager
                if self.opportunity_manager:
                    opportunities = self.opportunity_manager.get_opportunities() or []
                    
                    # Handle both dict and list formats
                    signals = []
                    if isinstance(opportunities, dict):
                        # Legacy format: {symbol: [opportunities...]}
                        for symbol, opp_list in opportunities.items():
                            for opp in opp_list:
                                if self._is_acceptable_opportunity(opp):
                                    signals.append(opp)
                    elif isinstance(opportunities, list):
                        # New format: [opportunity, ...]
                        for opp in opportunities:
                            if self._is_acceptable_opportunity(opp):
                                signals.append(opp)
                    
                    # 🎯 PROFIT-FIRST RANKING: Rank signals by expected profit (highest first)
                    if signals:
                        # Get stake amount and leverage for ranking calculations
                        stake_amount = self.stake_usd
                        leverage = self.default_leverage

                        # Rank signals by expected profit (highest first)
                        ranked_signals = self._rank_signals(signals, stake_amount, leverage)
                        
                        logger.info(f"🎯 PROFIT-FIRST RANKING: {len(ranked_signals)} signals ranked by expected profit")
                        # Log top 3 for visibility
                        for i, s in enumerate(ranked_signals[:3]):
                            ep = s.get('_ep_bucket', 0)
                            conf = s.get('confidence', 0)
                            logger.info(f"  #{i+1}: {s.get('symbol', 'UNKNOWN')} {s.get('direction', 'UNKNOWN')} - "
                                       f"Expected: ${ep:.2f}, Confidence: {conf:.2f}")

                        # Execute signals in profit-first order
                        executed_count = 0
                        for signal in ranked_signals:
                            if len(self.positions) >= self.max_positions:
                                logger.debug(f"Max positions reached ({self.max_positions}), stopping execution")
                                break
                            
                            symbol = signal.get('symbol')
                            if symbol in self.positions_by_symbol:
                                continue  # Already have position in this symbol
                            
                            # Execute the trade
                            await self._open_live_position_from_opportunity(signal)
                            executed_count += 1
                            
                            ep = signal.get('_ep_bucket', 0)
                            logger.info(f"✅ EXECUTED #{executed_count}: {symbol} {signal.get('direction')} - Expected: ${ep:.2f}")

                        if executed_count > 0:
                            logger.info(f"🎯 PROFIT-FIRST EXECUTION: {executed_count} trades executed from {len(ranked_signals)} ranked signals")
                
                await asyncio.sleep(self.signal_poll_sec)
                
            except Exception as e:
                logger.error(f"Error in signal collection loop: {e}")
                await asyncio.sleep(5)
    
    async def _position_monitoring_loop(self):
        """Monitor live positions for TP/SL hits and floor rule enforcement"""
        logger.info("🔍 Starting position monitoring loop")
        
        while self.is_running:
            try:
                positions_to_close = []
                
                for position_id, position in list(self.positions.items()):
                    try:
                        # Get current market price
                        ticker = await self.exchange_client.get_ticker_24h(position.symbol)
                        current_price = float(ticker.get("lastPrice", 0))
                        
                        if current_price <= 0:
                            continue
                        
                        # Calculate gross PnL
                        if position.entry_price and position.qty:
                            if position.side == "LONG":
                                gross_pnl = (current_price - position.entry_price) * position.qty
                            else:  # SHORT
                                gross_pnl = (position.entry_price - current_price) * position.qty
                        else:
                            gross_pnl = 0.0
                        
                        # Update live P&L fields for frontend display
                        position.current_price = float(current_price)
                        position.unrealized_pnl = float(gross_pnl)
                        position.pnl = float(gross_pnl)  # For frontend compatibility
                        
                        # Calculate percentage P&L
                        notional = position.entry_price * position.qty if position.entry_price and position.qty else 0.0
                        if notional > 0:
                            position.unrealized_pnl_pct = float((gross_pnl / notional) * 100.0)
                            position.pnl_pct = float((gross_pnl / notional) * 100.0)  # For frontend compatibility
                        else:
                            position.unrealized_pnl_pct = 0.0
                            position.pnl_pct = 0.0
                        
                        # Exchange state verification with grace period
                        is_open = await self._has_open_position_on_exchange(position.symbol)
                        if is_open and not position.first_seen_open:
                            position.first_seen_open = True
                            position.entry_exchange_verified_at = datetime.now()
                        
                        # --- Trailing Profit Floor Logic (Real Trading; GROSS dollars) ---
                        # Read steps/cap from config or use defaults
                        increment_step = float(self.cfg.get('trailing_increment_dollars', 10.0))
                        max_take_profit = float(self.cfg.get('trailing_cap_dollars', 100.0))

                        # Ensure property exists for old positions
                        if getattr(position, "dynamic_trailing_floor", 0.0) <= 0.0:
                            position.dynamic_trailing_floor = self.absolute_floor_dollars

                        # Update best-ever gross profit
                        position.highest_profit_ever = max(position.highest_profit_ever, gross_pnl)

                        # Ratchet floor up in $10 steps, capped at $100
                        while (
                            position.highest_profit_ever - position.dynamic_trailing_floor >= increment_step
                            and position.dynamic_trailing_floor < max_take_profit
                        ):
                            position.dynamic_trailing_floor = min(
                                position.dynamic_trailing_floor + increment_step,
                                max_take_profit
                            )
                            logger.info(
                                f"📈 Trailing floor ↑ {position.symbol}: ${position.dynamic_trailing_floor:.2f} "
                                f"(best ${position.highest_profit_ever:.2f})"
                            )

                        # Activate trailing behavior as soon as we surpass starting floor
                        if position.highest_profit_ever >= self.absolute_floor_dollars:
                            position.profit_floor_activated = True

                        # Check for TP/SL hits using trailing floor system
                        close_reason = None
                        
                        # RULE 1: Hard TP at cap (bank the big win)
                        if gross_pnl >= max_take_profit:
                            close_reason = "tp_cap_100_hit"
                            positions_to_close.append((position_id, close_reason))
                            continue

                        # RULE 2: Trailing floor stop-out
                        elif position.profit_floor_activated and gross_pnl <= position.dynamic_trailing_floor:
                            close_reason = f"trailing_floor_${int(position.dynamic_trailing_floor)}_hit"
                            positions_to_close.append((position_id, close_reason))
                            continue
                        
                        # Check if position was closed by exchange (TP/SL hit) with grace period
                        if not is_open:
                            if position.first_seen_open:
                                # Only close if we've seen it open and grace period has passed
                                if (datetime.now() - position.entry_exchange_verified_at).total_seconds() >= 10:
                                    logger.info(f"✅ Position closed on exchange (TP/SL): {position.symbol}")
                                    await self._mark_position_closed(position_id, reason="tp_sl_hit_exchange")
                                    continue
                            # Still within initial update lag — skip closing this tick
                            continue
                    
                    except Exception as e:
                        logger.error(f"Error monitoring position {position_id}: {e}")
                        continue
                
                # Close positions that need closing
                for position_id, reason in positions_to_close:
                    await self._market_close_position(position_id, reason)
                
                # Check for emergency conditions
                await self._check_emergency_conditions()
                
                await asyncio.sleep(self.position_poll_sec)
                
            except Exception as e:
                logger.error(f"Error in position monitoring loop: {e}")
                await asyncio.sleep(10)
    
    def _is_acceptable_opportunity(self, opp: Dict[str, Any]) -> bool:
        """Check if opportunity is acceptable for real trading with comprehensive logging and statistics"""
        try:
            symbol = opp.get("symbol", "UNKNOWN")
            
            # Must have required fields
            if not opp.get("symbol") or not opp.get("entry_price") or not opp.get("direction"):
                self.stats['rejections']['missing_fields'] += 1
                self.stats['rejections']['total'] += 1
                logger.info(f"🚫 REJECT {symbol}: missing_fields (symbol={bool(opp.get('symbol'))}, "
                           f"entry_price={bool(opp.get('entry_price'))}, direction={bool(opp.get('direction'))})")
                return False
            
            # Must be tradable
            if not opp.get("tradable", True):
                self.stats['rejections']['not_tradable'] += 1
                self.stats['rejections']['total'] += 1
                logger.info(f"🚫 REJECT {symbol}: not_tradable (tradable={opp.get('tradable')})")
                return False
            
            # Optional: require real data tag if available
            if opp.get("is_real_data") is False:
                self.stats['rejections']['not_real_data'] += 1
                self.stats['rejections']['total'] += 1
                logger.info(f"🚫 REJECT {symbol}: not_real_data (is_real_data={opp.get('is_real_data')})")
                return False
            
            # Confidence check - configurable threshold
            confidence = opp.get("confidence", opp.get("confidence_score", 0))
            min_conf = float(self.cfg.get("min_confidence", 0.50))
            if confidence < min_conf:
                self.stats['rejections']['low_confidence'] += 1
                self.stats['rejections']['total'] += 1
                logger.info(f"🚫 REJECT {symbol}: low_confidence (confidence={confidence:.3f} < {min_conf:.3f})")
                return False
            
            # If we get here, opportunity is acceptable
            logger.debug(f"✅ ACCEPT {symbol}: confidence={confidence:.3f}, tradable={opp.get('tradable', True)}, "
                        f"real_data={opp.get('is_real_data', 'N/A')}")
            return True
            
        except Exception as e:
            self.stats['errors']['total'] += 1
            logger.error(f"🚫 REJECT {opp.get('symbol', 'UNKNOWN')}: error checking acceptability: {e}")
            return False
    
    async def _open_live_position_from_opportunity(self, opp: Dict[str, Any]):
        """Open a live position from an opportunity with comprehensive skip tracking"""
        symbol = opp.get("symbol", "UNKNOWN")
        
        # FIXED: Configurable freshness guard - use config value instead of hardcoded 300
        gen_ts = float(opp.get("signal_timestamp", 0) or 0)
        max_age_sec = float(self.cfg.get("signal_freshness_max_sec", 90))  # Use config value, default 90s
        
        if gen_ts and (time.time() - gen_ts) > max_age_sec:
            age_sec = time.time() - gen_ts
            self.stats['skips']['stale_signal'] += 1
            self.stats['skips']['total'] += 1
            logger.warning("⏭️ SKIP %s: stale_signal age=%.1fs > %.1fs (configured threshold)", 
                          symbol, age_sec, max_age_sec)
            return

        # Check if symbol already has position
        if symbol in self.positions_by_symbol:
            self.stats['skips']['symbol_exists'] += 1
            self.stats['skips']['total'] += 1
            logger.info(f"⏭️ SKIP {symbol}: symbol_exists (already have position)")
            return

        # Check max positions limit
        if len(self.positions) >= self.max_positions:
            self.stats['skips']['max_positions'] += 1
            self.stats['skips']['total'] += 1
            logger.info(f"⏭️ SKIP {symbol}: max_positions ({len(self.positions)}/{self.max_positions})")
            return

        # Optional: price drift guard (disabled by default to mirror paper trading)
        try:
            entry_price = float(opp["entry_price"])
            drift_check_enabled = bool(self.cfg.get("entry_drift_check_enabled", False))
            
            if drift_check_enabled and entry_price > 0:
                # Get current market price
                live_price = None
                try:
                    live_price = float(await self.exchange_client.get_price(symbol))
                except Exception:
                    # fallback to ticker lastPrice
                    ticker = await self.exchange_client.get_ticker_24h(symbol)
                    live_price = float(ticker.get("lastPrice"))

                drift = abs(live_price - entry_price) / entry_price
                max_drift = float(self.cfg.get("entry_drift_pct", 0.6)) / 100.0
                if drift > max_drift:
                    self.stats['skips']['price_drift'] += 1
                    self.stats['skips']['total'] += 1
                    logger.warning("⏭️ SKIP %s: price_drift %.3f%% > %.2f%% (live=$%.6f, entry=$%.6f)",
                                   symbol, drift*100.0, max_drift*100.0, live_price, entry_price)
                    return
        except Exception as e:
            logger.warning("Drift check failed for %s, continuing: %s", symbol, e)

        """Open a live position from an opportunity"""
        try:
            symbol = opp["symbol"]
            direction = opp["direction"].upper()  # LONG/SHORT
            entry_hint = float(opp["entry_price"])
            
            logger.info(f"🎯 Opening live position: {symbol} {direction} @ ${entry_hint:.6f}")
            
            # Set leverage and margin mode BEFORE placing orders
            try:
                # Set margin mode (ISOLATED or CROSS)
                await self.exchange_client.set_margin_type(symbol, self.margin_mode)
                
                # Calculate bounded leverage
                recommended_leverage = float(opp.get("recommended_leverage", self.default_leverage))
                max_leverage = int(self.cfg.get("max_leverage", 20))
                leverage = int(min(recommended_leverage, max_leverage))
                
                # Set leverage for this symbol
                await self.exchange_client.set_leverage(symbol, leverage)
                
                logger.info(f"✅ Leverage setup: {symbol} {self.margin_mode} margin, {leverage}x leverage")
                
            except Exception as e:
                logger.warning(f"Leverage/margin setup failed for {symbol}: {e}")
                # Continue with trade - some exchanges may not support these calls
                leverage = int(self.default_leverage)  # Use default leverage if setup failed
            
            # Get symbol precision info
            try:
                symbol_info = await self.exchange_client.get_symbol_info(symbol)
                step_size = float(symbol_info.get("stepSize", "0.001"))
                tick_size = float(symbol_info.get("tickSize", "0.01"))
                min_notional = float(symbol_info.get("minNotional", "10"))
            except Exception as e:
                logger.error(f"Failed to get symbol info for {symbol}: {e}")
                # Use defaults
                step_size = 0.001
                tick_size = 0.01
                min_notional = 10
            
            # Compute target notional from stake mode
            if self.stake_mode == "MARGIN":
                notional_target = self.stake_usd * leverage   # capital × leverage
                logger.info(f"💰 MARGIN mode: ${self.stake_usd} capital × {leverage}x = ${notional_target:.2f} notional")
            else:
                notional_target = self.stake_usd              # backwards-compatible (treat stake as size)
                logger.info(f"💰 NOTIONAL mode: ${self.stake_usd} notional (legacy)")
            
            # Convert notional to quantity and round
            qty = max(notional_target / entry_hint, step_size)
            qty = self._round_step(qty, step_size)
            
            # Check minimum notional
            notional = qty * entry_hint
            if notional < min_notional:
                self.stats['skips']['min_notional'] += 1
                self.stats['skips']['total'] += 1
                logger.warning("⏭️ SKIP %s: min_notional notional=$%.2f < $%.2f (qty=%.6f entry=$%.6f)",
                               symbol, notional, min_notional, qty, entry_hint)
                return
            
            # Execute market entry order
            side_for_market = "BUY" if direction == "LONG" else "SELL"
            
            logger.warning(f"🚨 EXECUTING REAL ORDER: {side_for_market} {qty:.6f} {symbol}")
            logger.warning(f"💰 REAL MONEY: ${notional:.2f} notional value")
            
            entry_order = await self.exchange_client.create_order(
                symbol=symbol,
                side=side_for_market,
                type="MARKET",
                quantity=qty
            )
            
            if not entry_order or not entry_order.get("orderId"):
                logger.error(f"❌ Failed to execute entry order for {symbol}")
                return
            
            # Get actual fill price with safe fallback
            try:
                fill_price = await self._determine_entry_price(entry_order, symbol, direction, entry_hint)
            except Exception as e:
                logger.error(f"❌ Abort open {symbol}: {e}")
                return
            
            # Calculate TP/SL prices using Pure 3-rule mode
            if direction == "LONG":
                # TP: $10 profit target
                tp_price = fill_price + (self.primary_target_dollars / qty)
                # SL: 0.5% below entry
                sl_price = fill_price * (1.0 - self.stop_loss_percent)
                tp_side = "SELL"
                sl_side = "SELL"
            else:  # SHORT
                # TP: $10 profit target
                tp_price = fill_price - (self.primary_target_dollars / qty)
                # SL: 0.5% above entry
                sl_price = fill_price * (1.0 + self.stop_loss_percent)
                tp_side = "BUY"
                sl_side = "BUY"
            
            # Apply TP/SL safety guards to prevent instant triggers
            tp_price, sl_price = self._finalize_tp_sl_prices(direction, fill_price, tp_price, sl_price, tick_size)
            
            # Place TP and/or SL orders (now gated by config toggles)
            tp_order = None
            sl_order = None

            try:
                if self.enable_take_profit:
                    tp_order = await self.exchange_client.create_order(
                        symbol=symbol,
                        side=tp_side,
                        type="TAKE_PROFIT_MARKET",
                        quantity=qty,
                        stopPrice=tp_price,
                        reduceOnly=True
                    )
                else:
                    logger.info("🧰 TP placement disabled by config (enable_take_profit=false)")

                if self.enable_stop_loss:
                    sl_order = await self.exchange_client.create_order(
                        symbol=symbol,
                        side=sl_side,
                        type="STOP_MARKET",
                        quantity=qty,
                        stopPrice=sl_price,
                        reduceOnly=True
                    )
                else:
                    logger.info("🛡️ SL placement disabled by config (enable_stop_loss=false)")

            except Exception as e:
                logger.error(f"Failed to place TP/SL orders for {symbol}: {e}")
                # Continue without TP/SL - position monitoring will handle exits
            
            # Create position record
            position = LivePosition(
                position_id=f"live_{int(time.time())}_{symbol}",
                symbol=symbol,
                side=direction,
                entry_price=fill_price,
                qty=qty,
                stake_usd=self.stake_usd,
                leverage=float(opp.get("recommended_leverage", 1.0)),
                entry_time=datetime.now(),
                tp_order_id=str(tp_order.get("orderId")) if tp_order else None,
                sl_order_id=str(sl_order.get("orderId")) if sl_order else None,
                tp_price=tp_price if self.enable_take_profit else None,  # UI display
                sl_price=sl_price if self.enable_stop_loss else None,   # UI display
                dynamic_trailing_floor=self.absolute_floor_dollars  # NEW: start at absolute floor
            )
            
            # Store position
            self.positions[position.position_id] = position
            self.positions_by_symbol[symbol] = position.position_id
            
            # Update statistics
            self.total_trades += 1
            self.stats['successes']['positions_opened'] += 1
            self.stats['successes']['total'] += 1
            
            # Store in database
            await self._store_position_in_db(position)
            
            # Register with trade sync service
            if self.trade_sync_service:
                await self.trade_sync_service.register_system_trade(position.position_id, position.to_dict())
            
            logger.info(f"✅ LIVE POSITION OPENED: {symbol} {direction} qty={qty:.6f} entry=${fill_price:.6f} "
                       f"TP=${tp_price:.6f} SL=${sl_price:.6f} (stake ${self.stake_usd:.2f})")
            
        except Exception as e:
            logger.error(f"❌ Error opening live position for {opp.get('symbol', 'UNKNOWN')}: {e}")
    
    async def _market_close_position(self, position_id: str, reason: str = "MANUAL"):
        """Close a position at market price"""
        try:
            if position_id not in self.positions:
                logger.warning(f"Position {position_id} not found")
                return False
            
            position = self.positions[position_id]
            
            # Cancel existing TP/SL orders first
            try:
                if position.tp_order_id:
                    await self.exchange_client.cancel_order(position.symbol, position.tp_order_id)
                if position.sl_order_id:
                    await self.exchange_client.cancel_order(position.symbol, position.sl_order_id)
            except Exception as e:
                logger.debug(f"Error canceling orders for {position.symbol}: {e}")
            
            # Execute market close order
            close_side = "SELL" if position.side == "LONG" else "BUY"
            
            logger.warning(f"🚨 CLOSING REAL POSITION: {close_side} {position.qty:.6f} {position.symbol}")
            
            close_order = await self.exchange_client.create_order(
                symbol=position.symbol,
                side=close_side,
                type="MARKET",
                quantity=position.qty,
                reduceOnly=True
            )
            
            if close_order and close_order.get("orderId"):
                # Get exit price
                exit_price = float(close_order.get("avgPrice") or close_order.get("price") or 0)
                
                # Calculate final PnL
                if position.side == "LONG":
                    pnl = (exit_price - position.entry_price) * position.qty
                else:  # SHORT
                    pnl = (position.entry_price - exit_price) * position.qty
                
                pnl_pct = (pnl / (position.entry_price * position.qty)) * 100
                
                # Update position
                position.exit_price = exit_price
                position.exit_time = datetime.now()
                position.pnl = pnl
                position.pnl_pct = pnl_pct
                position.status = 'CLOSED'
                
                # Update statistics
                self.total_pnl += pnl
                self.daily_pnl += pnl
                if pnl > 0:
                    self.winning_trades += 1
                
                # Store completed trade
                trade_record = position.to_dict()
                trade_record['exit_reason'] = reason
                self.completed_trades.append(trade_record)
                
                # Update in database
                await self._update_position_in_db(position)
                
                # Unregister with trade sync service
                if self.trade_sync_service:
                    close_data = {
                        'exit_price': exit_price,
                        'exit_time': position.exit_time,
                        'pnl': pnl,
                        'reason': reason
                    }
                    await self.trade_sync_service.unregister_system_trade(position_id, close_data)
                
                duration_minutes = int((position.exit_time - position.entry_time).total_seconds() / 60)
                duration_formatted = format_duration(duration_minutes)
                
                logger.info(f"✅ REAL POSITION CLOSED: {position.symbol} {position.side} @ ${exit_price:.6f} "
                           f"P&L: ${pnl:.2f} ({pnl_pct:.2f}%) Duration: {duration_formatted} Reason: {reason}")
                logger.warning(f"💰 REAL MONEY P&L: ${pnl:.2f}")
                
                # Remove from active positions
                del self.positions[position_id]
                del self.positions_by_symbol[position.symbol]
                
                return True
            else:
                logger.error(f"❌ Failed to close position {position_id}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error closing position {position_id}: {e}")
            return False
    
    async def _has_open_position_on_exchange(self, symbol: str) -> bool:
        """
        Return True if exchange shows a *non-zero* positionAmt for symbol.
        Handles dict or single-item list payloads from the exchange client.
        """
        try:
            info = await self.exchange_client.get_position(symbol)

            # Normalize list → dict
            if isinstance(info, list):
                info = info[0] if info else {}

            amt_str = (info or {}).get("positionAmt")  # Binance USDT-M field
            size = float(amt_str) if amt_str not in (None, "") else 0.0

            # Consider tiny dust as zero
            return abs(size) > 1e-12
        except Exception as e:
            logger.warning("position check failed for %s: %s", symbol, e)
            # On error, do NOT prematurely declare closed; keep monitoring.
            return True
    
    async def _mark_position_closed(self, position_id: str, reason: str):
        """Mark position as closed locally without sending market order"""
        try:
            position = self.positions.get(position_id)
            if not position:
                return
            
            # Try to get actual exit price from recent trades
            try:
                recent_trades = await self.exchange_client.get_account_trades(position.symbol, limit=10)
                exit_price = position.entry_price  # Fallback
                
                # Find the most recent trade for this position
                for trade in recent_trades:
                    if abs(float(trade.get('qty', 0))) >= position.qty * 0.9:  # Match quantity
                        exit_price = float(trade.get('price', position.entry_price))
                        break
                        
            except Exception as e:
                logger.debug(f"Could not fetch recent trades for {position.symbol}: {e}")
                exit_price = position.entry_price  # Use entry price as fallback
            
            # Calculate PnL
            if position.side == "LONG":
                pnl = (exit_price - position.entry_price) * position.qty
            else:  # SHORT
                pnl = (position.entry_price - exit_price) * position.qty
            
            pnl_pct = (pnl / (position.entry_price * position.qty)) * 100
            
            # Update position
            position.status = "CLOSED"
            position.exit_time = datetime.now()
            position.exit_price = exit_price
            position.pnl = pnl
            position.pnl_pct = pnl_pct
            
            # Update statistics
            self.total_pnl += pnl
            self.daily_pnl += pnl
            if pnl > 0:
                self.winning_trades += 1
            
            # Store completed trade
            trade_record = position.to_dict()
            trade_record['exit_reason'] = reason
            self.completed_trades.append(trade_record)
            
            # Update in database
            await self._update_position_in_db(position)
            
            # Unregister with trade sync service
            if self.trade_sync_service:
                close_data = {
                    'exit_price': exit_price,
                    'exit_time': position.exit_time,
                    'pnl': pnl,
                    'reason': reason
                }
                await self.trade_sync_service.unregister_system_trade(position_id, close_data)
            
            # Remove from active positions
            self.positions_by_symbol.pop(position.symbol, None)
            self.positions.pop(position_id, None)
            
            duration_minutes = int((position.exit_time - position.entry_time).total_seconds() / 60)
            duration_formatted = format_duration(duration_minutes)
            
            logger.info(f"✅ POSITION MARKED CLOSED: {position.symbol} {position.side} @ ${exit_price:.6f} "
                       f"P&L: ${pnl:.2f} ({pnl_pct:.2f}%) Duration: {duration_formatted} Reason: {reason}")
            
        except Exception as e:
            logger.error(f"Error marking position closed {position_id}: {e}")
    
    async def _determine_entry_price(self, order_resp: Dict, symbol: str, side: str, entry_hint: float = None) -> float:
        """
        Resolve a *non-zero* entry price for market orders.
        Priority: avgPrice -> price -> fills -> side-aware best (ask for LONG, bid for SHORT) -> mark price.
        NEVER returns zero to prevent fake massive profits.
        """
        def _num(x):
            try:
                return float(x)
            except Exception:
                return 0.0

        # 1) Direct from order response
        if order_resp:
            p = _num(order_resp.get("avgPrice"))
            if p > 0:
                logger.info(f"Using avgPrice ${p:.6f} as entry for {symbol} {side}")
                return p
            p = _num(order_resp.get("price"))
            if p > 0:
                logger.info(f"Using price ${p:.6f} as entry for {symbol} {side}")
                return p
            # Some Binance responses include fills array; try there too
            fills = order_resp.get("fills") or []
            for f in fills:
                p = _num(f.get("price"))
                if p > 0:
                    logger.info(f"Using fill price ${p:.6f} as entry for {symbol} {side}")
                    return p

        logger.warning(f"No valid fill price from order response for {symbol}, using fallbacks")

        # 2) Side-aware orderbook fallback (best ask for LONG, best bid for SHORT)
        try:
            # Try to get orderbook top for side-aware pricing
            ticker = await self.exchange_client.get_ticker_24h(symbol)
            if ticker:
                # For now, use lastPrice since we don't have separate bid/ask in ticker
                # In a full implementation, you'd call get_orderbook_top(symbol)
                last_price = _num(ticker.get("lastPrice"))
                if last_price > 0:
                    logger.info(f"Using last price ${last_price:.6f} as entry for {symbol} {side}")
                    return last_price
        except Exception as e:
            logger.debug(f"Ticker fallback failed for {symbol}: {e}")

        # 3) Mark price fallback
        try:
            # Try to get mark price
            ticker = await self.exchange_client.get_ticker_24h(symbol)
            if ticker:
                mark_price = _num(ticker.get("lastPrice"))  # Using lastPrice as mark price proxy
                if mark_price > 0:
                    logger.warning(f"Using mark price ${mark_price:.6f} as entry for {symbol} {side}")
                    return mark_price
        except Exception as e:
            logger.debug(f"Mark price fallback failed for {symbol}: {e}")

        # 4) Entry hint fallback
        if entry_hint and entry_hint > 0:
            logger.warning(f"Using entry hint ${entry_hint:.6f} as entry for {symbol} {side}")
            return float(entry_hint)

        # 5) Last-chance: fetch latest account trade as entry
        try:
            trades = await self.exchange_client.get_account_trades(symbol, limit=1)
            if trades and float(trades[0].get("price", 0)) > 0:
                p = float(trades[0]["price"])
                logger.info(f"Using account trade price ${p:.6f} as entry for {symbol} {side}")
                return p
        except Exception as e:
            logger.warning(f"Account trade fallback failed for {symbol}: {e}")

        # Hard abort — no trustworthy price
        raise RuntimeError(f"Cannot determine entry price for {symbol} (no valid fills)")
    
    def _extract_fill_price(self, order_resp: Dict) -> Optional[float]:
        """Extract fill price from order response"""
        try:
            if not order_resp:
                return None
            
            # Try avgPrice first (most accurate for market orders)
            if "avgPrice" in order_resp and float(order_resp["avgPrice"]) > 0:
                return float(order_resp["avgPrice"])
            
            # Try price field
            if "price" in order_resp and float(order_resp["price"]) > 0:
                return float(order_resp["price"])
            
            # Try fills array if available
            fills = order_resp.get("fills", [])
            if fills and isinstance(fills, list):
                total_qty = 0.0
                total_value = 0.0
                for fill in fills:
                    qty = float(fill.get("qty", 0))
                    price = float(fill.get("price", 0))
                    if qty > 0 and price > 0:
                        total_qty += qty
                        total_value += qty * price
                
                if total_qty > 0:
                    return total_value / total_qty  # Weighted average price
            
            return None
            
        except Exception as e:
            logger.debug(f"Error extracting fill price: {e}")
            return None

    def _finalize_tp_sl_prices(self, side: str, fill_price: float, tp_price: float, sl_price: float, tick_size: float) -> tuple:
        """
        Enforce minimum gap and side-correct TP/SL prices before placing reduce-only stops.
        Prevents instant triggers due to rounding or volatility.
        """
        try:
            min_gap = max(tick_size, fill_price * 0.0002)  # e.g., 2 bps or tick_size, whichever is larger
            
            if side == "LONG":
                # For LONG: TP must be above entry, SL must be below entry
                tp_price = max(tp_price, fill_price + min_gap)
                sl_price = min(sl_price, fill_price - min_gap)
            else:  # SHORT
                # For SHORT: TP must be below entry, SL must be above entry
                tp_price = min(tp_price, fill_price - min_gap)
                sl_price = max(sl_price, fill_price + min_gap)
            
            # Round to exchange tick size
            tp_price = self._round_tick(tp_price, tick_size)
            sl_price = self._round_tick(sl_price, tick_size)
            
            logger.debug(f"TP/SL finalized for {side}: TP=${tp_price:.6f} SL=${sl_price:.6f} (min_gap=${min_gap:.6f})")
            
            return tp_price, sl_price
            
        except Exception as e:
            logger.error(f"Error finalizing TP/SL prices: {e}")
            # Return original prices as fallback
            return self._round_tick(tp_price, tick_size), self._round_tick(sl_price, tick_size)

    async def _check_emergency_conditions(self):
        """Check for emergency stop conditions"""
        try:
            # Reset daily PnL if new day
            current_date = datetime.now().date()
            if current_date != self.last_reset_date:
                self.daily_pnl = 0.0
                self.last_reset_date = current_date
                logger.info("📅 Daily P&L reset for new trading day")
            
            # Check daily loss limit
            if self.daily_pnl < -self.max_daily_loss:
                logger.error(f"🚨 EMERGENCY STOP: Daily loss limit exceeded: ${self.daily_pnl:.2f}")
                self.emergency_stop = True
                await self.stop_trading()
            
            # Manual emergency stop
            if self.emergency_stop:
                logger.error("🚨 EMERGENCY STOP: Manual emergency stop activated")
                await self.stop_trading()
                
        except Exception as e:
            logger.error(f"Error checking emergency conditions: {e}")
    
    @staticmethod
    def _round_step(qty: float, step: float) -> float:
        """Round quantity to exchange step size"""
        if step <= 0:
            return qty
        return (qty // step) * step
    
    @staticmethod
    def _round_tick(price: float, tick: float) -> float:
        """Round price to exchange tick size"""
        if tick <= 0:
            return price
        return round(price / tick) * tick
    
    async def _store_position_in_db(self, position: LivePosition):
        """Store position in database"""
        try:
            # For now, just log the position data
            # In a full implementation, you would create a Trade model and save it
            logger.debug(f"Storing position in database: {position.position_id}")
        except Exception as e:
            logger.error(f"Error storing position in database: {e}")
    
    async def _update_position_in_db(self, position: LivePosition):
        """Update position in database"""
        try:
            # For now, just log the position update
            # In a full implementation, you would update the Trade model
            logger.debug(f"Updating position in database: {position.position_id}")
        except Exception as e:
            logger.error(f"Error updating position in database: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current real trading status with comprehensive observability statistics"""
        try:
            win_rate = self.winning_trades / self.total_trades if self.total_trades > 0 else 0.0
            uptime_minutes = 0
            
            if self.start_time:
                uptime_minutes = (datetime.now() - self.start_time).total_seconds() / 60
            
            return {
                'is_running': self.is_running,
                'enabled': self.enabled,
                'emergency_stop': self.emergency_stop,
                'active_positions': len(self.positions),
                'total_trades': self.total_trades,
                'winning_trades': self.winning_trades,
                'win_rate': win_rate,
                'total_pnl': self.total_pnl,
                'daily_pnl': self.daily_pnl,
                'uptime_minutes': uptime_minutes,
                'max_daily_loss': self.max_daily_loss,
                'stake_usd': self.stake_usd,
                'stake_mode': self.stake_mode,
                'margin_mode': self.margin_mode,
                'default_leverage': self.default_leverage,
                'max_positions': self.max_positions,
                'mode': 'real',
                'engine': 'opportunity_manager_only',
                'pure_3_rule_mode': self.pure_3_rule_mode,
                'primary_target_dollars': self.primary_target_dollars,
                'absolute_floor_dollars': self.absolute_floor_dollars,
                'stop_loss_percent': self.stop_loss_percent * 100,
                'enable_take_profit': self.enable_take_profit,
                'enable_stop_loss': self.enable_stop_loss,
                # NEW: Comprehensive observability statistics
                'stats': self.stats.copy(),
                'signal_freshness_max_sec': float(self.cfg.get("signal_freshness_max_sec", 90)),
                'entry_drift_check_enabled': bool(self.cfg.get("entry_drift_check_enabled", False)),
                'entry_drift_pct': float(self.cfg.get("entry_drift_pct", 0.6)),
                'min_confidence': float(self.cfg.get("min_confidence", 0.50))
            }
            
        except Exception as e:
            logger.error(f"Error getting real trading status: {e}")
            return {'is_running': False, 'error': str(e)}
    
    def get_active_positions(self) -> List[Dict[str, Any]]:
        """Get all active real positions"""
        return [pos.to_dict() for pos in self.positions.values()]
    
    def get_completed_trades(self) -> List[Dict[str, Any]]:
        """Get all completed trades"""
        return self.completed_trades.copy()
    
    # Frontend compatibility property aliases
    @property
    def active(self) -> bool:
        """Routes expect 'active' field instead of 'is_running'"""
        return self.is_running
