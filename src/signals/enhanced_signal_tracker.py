"""
🎯 Enhanced Signal Tracker with Real-time PnL Monitoring

This tracks every signal's performance in real-time:
- PnL monitoring at 15m, 30m, 1h intervals
- Hit rate tracking (3%, 5%, stop-loss)
- Golden signal identification (+3% quick gainers)
- Backtest validation framework
- Adaptive criteria tuning
"""

import asyncio
import asyncpg
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import json
import hashlib
import aiohttp
from concurrent.futures import ThreadPoolExecutor
import time

logger = logging.getLogger(__name__)

@dataclass
class PnLSnapshot:
    """Performance snapshot at specific time intervals"""
    signal_id: str
    interval_minutes: int  # 15, 30, 60, etc.
    current_price: float
    pnl_pct: float
    pnl_absolute: float
    timestamp: datetime
    market_conditions: Dict[str, Any]

@dataclass
class GoldenSignal:
    """Signals that quickly reach +3% target"""
    signal_id: str
    symbol: str
    strategy: str
    direction: str
    time_to_3pct: int  # minutes to reach 3%
    max_pnl_reached: float
    confidence: float
    risk_reward: float

class EnhancedSignalTracker:
    """
    🚀 Real-time signal performance tracking with interval monitoring
    """
    
    def __init__(self, db_url: str = None):
        self.db_url = db_url or os.getenv('DATABASE_URL', 'postgresql://crypto_user:crypto_password@localhost:5432/crypto_trading')
        self.connection_pool = None
        self.enabled = os.getenv('ENABLE_SIGNAL_TRACKING', 'true').lower() == 'true'
        
        # Dual Reality Tracking Configuration
        self.learning_ignore_stop_loss = os.getenv('LEARNING_IGNORE_STOP_LOSS', 'true').lower() == 'true'
        self.dual_reality_tracking = os.getenv('DUAL_REALITY_TRACKING', 'true').lower() == 'true'
        self.virtual_trade_max_duration = int(os.getenv('VIRTUAL_TRADE_MAX_DURATION', '120'))  # minutes
        self.track_post_sl_performance = os.getenv('TRACK_POST_SL_PERFORMANCE', 'true').lower() == 'true'
        
        # Active signal monitoring
        self.active_signals = {}  # signal_id -> signal_data
        self.monitoring_task = None
        self.price_cache = {}  # symbol -> current_price
        
        # Performance tracking intervals (minutes)
        self.tracking_intervals = [15, 30, 60, 120, 240]
        
        # Golden signal criteria
        self.golden_signal_threshold = 0.03  # 3% gain
        self.golden_signal_time_limit = 60   # within 60 minutes
        
    async def initialize(self):
        """Initialize enhanced signal tracker"""
        if not self.enabled:
            logger.info("⚠️ Enhanced signal tracking disabled")
            return
            
        try:
            self.connection_pool = await asyncpg.create_pool(
                self.db_url,
                min_size=2,
                max_size=10,
                command_timeout=60
            )
            
            await self._ensure_enhanced_tables_exist()
            
            # Start real-time monitoring
            self.monitoring_task = asyncio.create_task(self._monitor_signals_realtime())
            
            logger.info("✅ Enhanced Signal Tracker initialized with real-time monitoring")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Enhanced Signal Tracker: {e}")
            self.enabled = False
    
    async def _ensure_enhanced_tables_exist(self):
        """Create enhanced tracking tables"""
        async with self.connection_pool.acquire() as conn:
            # Enhanced signals table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS enhanced_signals (
                    id SERIAL PRIMARY KEY,
                    signal_id VARCHAR(100) UNIQUE NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    -- Signal Details
                    symbol VARCHAR(20) NOT NULL,
                    strategy VARCHAR(50) NOT NULL,
                    direction VARCHAR(10) NOT NULL,
                    signal_type VARCHAR(50),
                    
                    -- Price Levels
                    entry_price DECIMAL(20,8) NOT NULL,
                    stop_loss DECIMAL(20,8) NOT NULL,
                    take_profit DECIMAL(20,8) NOT NULL,
                    
                    -- Enhanced Tracking
                    confidence DECIMAL(5,4) NOT NULL,
                    risk_reward_ratio DECIMAL(10,4),
                    position_size DECIMAL(20,8),
                    
                    -- 🧠 DUAL REALITY TRACKING - Performance Targets
                    target_3pct_hit BOOLEAN DEFAULT FALSE,
                    target_5pct_hit BOOLEAN DEFAULT FALSE,
                    stop_loss_hit BOOLEAN DEFAULT FALSE,
                    time_to_3pct_minutes INTEGER,
                    time_to_5pct_minutes INTEGER,
                    time_to_stop_minutes INTEGER,
                    
                    -- 🎯 VIRTUAL PERFORMANCE (True Learning Data)
                    virtual_3pct_hit BOOLEAN DEFAULT FALSE,
                    virtual_5pct_hit BOOLEAN DEFAULT FALSE,
                    virtual_tp_hit BOOLEAN DEFAULT FALSE,
                    virtual_max_profit_pct DECIMAL(10,6),
                    virtual_time_to_tp_minutes INTEGER,
                    post_sl_peak_pct DECIMAL(10,6),  -- How high did it go AFTER stop loss?
                    fakeout_detected BOOLEAN DEFAULT FALSE,  -- SL hit but then went to TP
                    
                    -- 📊 REALITY vs VIRTUAL COMPARISON
                    actual_exit_reason VARCHAR(20),  -- 'stop_loss', 'take_profit', 'expired'
                    virtual_exit_reason VARCHAR(20), -- What would have happened
                    learning_outcome VARCHAR(50),    -- 'false_negative', 'true_positive', etc.
                    
                    -- Max Performance
                    max_profit_pct DECIMAL(10,6),
                    max_profit_time TIMESTAMP,
                    max_drawdown_pct DECIMAL(10,6),
                    
                    -- Status
                    status VARCHAR(20) DEFAULT 'active',
                    is_golden_signal BOOLEAN DEFAULT FALSE,
                    is_virtual_golden BOOLEAN DEFAULT FALSE,  -- Would have been golden without SL
                    final_pnl_pct DECIMAL(10,6),
                    
                    -- Metadata
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                -- PnL snapshots table
                CREATE TABLE IF NOT EXISTS pnl_snapshots (
                    id SERIAL PRIMARY KEY,
                    signal_id VARCHAR(100) NOT NULL,
                    interval_minutes INTEGER NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    current_price DECIMAL(20,8) NOT NULL,
                    pnl_pct DECIMAL(10,6) NOT NULL,
                    pnl_absolute DECIMAL(20,8) NOT NULL,
                    volume_change_pct DECIMAL(10,4),
                    price_momentum DECIMAL(10,6),
                    
                    UNIQUE(signal_id, interval_minutes)
                );
                
                -- Golden signals table
                CREATE TABLE IF NOT EXISTS golden_signals (
                    id SERIAL PRIMARY KEY,
                    signal_id VARCHAR(100) UNIQUE NOT NULL,
                    symbol VARCHAR(20) NOT NULL,
                    strategy VARCHAR(50) NOT NULL,
                    direction VARCHAR(10) NOT NULL,
                    time_to_3pct_minutes INTEGER NOT NULL,
                    max_pnl_pct DECIMAL(10,6) NOT NULL,
                    confidence DECIMAL(5,4) NOT NULL,
                    risk_reward_ratio DECIMAL(10,4),
                    market_conditions JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                -- Strategy performance table
                CREATE TABLE IF NOT EXISTS strategy_performance (
                    id SERIAL PRIMARY KEY,
                    strategy VARCHAR(50) NOT NULL,
                    symbol VARCHAR(20),
                    date DATE DEFAULT CURRENT_DATE,
                    
                    -- Counts
                    total_signals INTEGER DEFAULT 0,
                    signals_3pct INTEGER DEFAULT 0,
                    signals_5pct INTEGER DEFAULT 0,
                    signals_stop_loss INTEGER DEFAULT 0,
                    golden_signals INTEGER DEFAULT 0,
                    
                    -- Performance
                    win_rate_3pct DECIMAL(5,4),
                    win_rate_5pct DECIMAL(5,4),
                    avg_time_to_3pct DECIMAL(10,2),
                    avg_max_profit DECIMAL(10,6),
                    avg_confidence DECIMAL(5,4),
                    
                    -- Updated tracking
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    UNIQUE(strategy, symbol, date)
                );
                
                -- Indexes for performance
                CREATE INDEX IF NOT EXISTS idx_enhanced_signals_symbol ON enhanced_signals(symbol);
                CREATE INDEX IF NOT EXISTS idx_enhanced_signals_strategy ON enhanced_signals(strategy);
                CREATE INDEX IF NOT EXISTS idx_enhanced_signals_status ON enhanced_signals(status);
                CREATE INDEX IF NOT EXISTS idx_enhanced_signals_golden ON enhanced_signals(is_golden_signal);
                CREATE INDEX IF NOT EXISTS idx_pnl_snapshots_signal ON pnl_snapshots(signal_id);
                CREATE INDEX IF NOT EXISTS idx_pnl_snapshots_interval ON pnl_snapshots(interval_minutes);
                CREATE INDEX IF NOT EXISTS idx_golden_signals_strategy ON golden_signals(strategy);
            """)
            
            logger.info("✅ Enhanced signal tracking tables created")
    
    async def track_signal(
        self,
        signal: Dict[str, Any],
        position_size: float = None,
        market_context: Dict[str, Any] = None,
        auto_tracked: bool = False,
        manual_execution: bool = False
    ) -> str:
        """
        Start tracking a new signal with real-time monitoring
        """
        if not self.enabled or not self.connection_pool:
            return None
            
        try:
            signal_id = self._generate_signal_id(signal)
            
            # Calculate risk/reward
            entry = float(signal.get('entry_price', signal.get('entry', 0)))
            tp = float(signal.get('take_profit', 0))
            sl = float(signal.get('stop_loss', 0))
            
            risk = abs(entry - sl) if sl != 0 else 0
            reward = abs(tp - entry) if tp != 0 else 0
            risk_reward = reward / risk if risk > 0 else 0
            
            # Store in database with auto-tracking info
            async with self.connection_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO enhanced_signals (
                        signal_id, symbol, strategy, direction, signal_type,
                        entry_price, stop_loss, take_profit, confidence, 
                        risk_reward_ratio, position_size
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    ON CONFLICT (signal_id) DO NOTHING
                """,
                    signal_id,
                    signal.get('symbol'),
                    signal.get('strategy', 'unknown'),
                    signal.get('direction'),
                    signal.get('signal_type'),
                    entry, sl, tp,
                    float(signal.get('confidence', 0)),
                    risk_reward,
                    position_size or 0
                )
                
                # Log auto-tracking status
                if auto_tracked:
                    logger.info(f"🤖 AUTO-TRACKED: {signal.get('symbol')} {signal.get('direction')} (ID: {signal_id[:8]}...)")
                elif manual_execution:
                    logger.info(f"👤 MANUAL EXECUTION: {signal.get('symbol')} {signal.get('direction')} (ID: {signal_id[:8]}...)")
                else:
                    logger.info(f"📊 TRACKED: {signal.get('symbol')} {signal.get('direction')} (ID: {signal_id[:8]}...)")
            
            # Add to active monitoring
            self.active_signals[signal_id] = {
                'signal': signal,
                'entry_time': datetime.now(),
                'entry_price': entry,
                'stop_loss': sl,
                'take_profit': tp,
                'direction': signal.get('direction'),
                'symbol': signal.get('symbol'),
                'strategy': signal.get('strategy'),
                'confidence': float(signal.get('confidence', 0)),
                'risk_reward': risk_reward,
                'snapshots_taken': [],  # Track which intervals we've captured
                'targets_hit': {
                    '3pct': False,
                    '5pct': False,
                    'stop_loss': False
                },
                'max_profit': 0,
                'max_drawdown': 0
            }
            
            logger.info(f"🎯 Now tracking signal: {signal.get('symbol')} {signal.get('direction')} (ID: {signal_id[:8]}...)")
            return signal_id
            
        except Exception as e:
            logger.error(f"❌ Failed to track signal: {e}")
            return None
    
    async def _monitor_signals_realtime(self):
        """
        Main monitoring loop - checks signals every minute
        """
        logger.info("🔄 Started real-time signal monitoring")
        
        while True:
            try:
                if not self.active_signals:
                    await asyncio.sleep(60)  # Check every minute
                    continue
                
                # Update price cache
                await self._update_price_cache()
                
                # Check each active signal
                signals_to_remove = []
                for signal_id, signal_data in self.active_signals.items():
                    try:
                        await self._check_signal_performance(signal_id, signal_data)
                        
                        # Remove if completed or too old (24 hours)
                        age_hours = (datetime.now() - signal_data['entry_time']).total_seconds() / 3600
                        if age_hours > 24 or signal_data.get('completed', False):
                            signals_to_remove.append(signal_id)
                            
                    except Exception as e:
                        logger.error(f"❌ Error checking signal {signal_id[:8]}: {e}")
                
                # Clean up completed signals
                for signal_id in signals_to_remove:
                    logger.info(f"✅ Completed monitoring: {signal_id[:8]}...")
                    del self.active_signals[signal_id]
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"❌ Error in signal monitoring loop: {e}")
                await asyncio.sleep(60)
    
    async def _update_price_cache(self):
        """Update current prices for all monitored symbols using robust proxy approach"""
        symbols = list(set(data['symbol'] for data in self.active_signals.values()))
        
        if not symbols:
            return
            
        try:
            # Use the same robust proxy approach as DirectMarketDataFetcher
            proxies = [
                None,  # Direct connection first
                'http://sp6qilmhb3:y2ok7Y3FEygM~rs7de@isp.decodo.com:10001',  # Working proxy
            ]
            
            symbol_prices = {}
            
            for symbol in symbols:
                price = await self._fetch_symbol_price_robust(symbol, proxies)
                if price:
                    symbol_prices[symbol] = price
                    
            # Update cache
            if symbol_prices:
                self.price_cache.update(symbol_prices)
                self.last_price_update = datetime.now()
                logger.debug(f"💰 Price cache updated: {len(symbol_prices)} symbols")
            else:
                logger.warning("⚠️ No prices fetched for any symbols")
                
        except Exception as e:
            logger.error(f"❌ Failed to update price cache: {e}")

    async def _fetch_symbol_price_robust(self, symbol: str, proxies: list) -> Optional[float]:
        """Fetch price for a symbol using robust proxy fallback"""
        url = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}"
        
        for proxy in proxies:
            try:
                timeout = aiohttp.ClientTimeout(total=5)
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                
                async with aiohttp.ClientSession(
                    timeout=timeout,
                    headers=headers
                ) as session:
                    kwargs = {}
                    if proxy:
                        kwargs['proxy'] = proxy
                    
                    async with session.get(url, **kwargs) as response:
                        if response.status == 200:
                            data = await response.json()
                            price = float(data['price'])
                            logger.debug(f"✅ {symbol}: ${price:,.2f} (proxy: {proxy or 'direct'})")
                            return price
                        elif response.status == 451:
                            logger.debug(f"🚫 {symbol}: Geo-blocked (HTTP 451) with {proxy or 'direct'}")
                            continue
                        else:
                            logger.debug(f"❌ {symbol}: HTTP {response.status} with {proxy or 'direct'}")
                            continue
                            
            except Exception as e:
                logger.debug(f"❌ {symbol}: Error with {proxy or 'direct'} - {e}")
                continue
                
        logger.warning(f"⚠️ Failed to fetch price for {symbol} with all proxies")
        return None
    
    async def _check_signal_performance(self, signal_id: str, signal_data: Dict):
        """Check individual signal performance and update tracking"""
        symbol = signal_data['symbol']
        current_price = self.price_cache.get(symbol)
        
        if not current_price:
            return
            
        direction = signal_data['direction']
        entry_price = signal_data['entry_price']
        
        # Calculate current PnL
        if direction == 'LONG':
            pnl_pct = (current_price - entry_price) / entry_price
        else:  # SHORT
            pnl_pct = (entry_price - current_price) / entry_price
        
        # Update max profit/drawdown
        signal_data['max_profit'] = max(signal_data['max_profit'], pnl_pct)
        if pnl_pct < 0:
            signal_data['max_drawdown'] = min(signal_data['max_drawdown'], pnl_pct)
        
        # Check targets
        await self._check_targets(signal_id, signal_data, pnl_pct, current_price)
        
        # Take interval snapshots
        await self._take_interval_snapshots(signal_id, signal_data, current_price, pnl_pct)
        
        # Check if should mark as golden signal
        await self._check_golden_signal(signal_id, signal_data, pnl_pct)
    
    async def _check_targets(self, signal_id: str, signal_data: Dict, pnl_pct: float, current_price: float):
        """Check if signal hit any targets - WITH DUAL REALITY TRACKING"""
        targets = signal_data['targets_hit']
        entry_time = signal_data['entry_time']
        current_time = datetime.now()
        minutes_elapsed = int((current_time - entry_time).total_seconds() / 60)
        
        async with self.connection_pool.acquire() as conn:
            updates = []
            virtual_updates = []
            
            # 🎯 ACTUAL PERFORMANCE (What really happened with SL)
            # Check 3% target
            if not targets['3pct'] and pnl_pct >= 0.03:
                targets['3pct'] = True
                updates.append(("target_3pct_hit = TRUE", f"time_to_3pct_minutes = {minutes_elapsed}"))
                virtual_updates.append(("virtual_3pct_hit = TRUE", f"virtual_time_to_tp_minutes = {minutes_elapsed}"))
                logger.info(f"🎯 3% target hit: {signal_data['symbol']} in {minutes_elapsed}m")
            
            # Check 5% target
            if not targets['5pct'] and pnl_pct >= 0.05:
                targets['5pct'] = True
                updates.append(("target_5pct_hit = TRUE", f"time_to_5pct_minutes = {minutes_elapsed}"))
                virtual_updates.append(("virtual_5pct_hit = TRUE", f"virtual_time_to_tp_minutes = {minutes_elapsed}"))
                logger.info(f"🚀 5% target hit: {signal_data['symbol']} in {minutes_elapsed}m")
            
            # Check take profit
            take_profit = signal_data['take_profit']
            direction = signal_data['direction']
            
            tp_hit = False
            if direction == 'LONG' and current_price >= take_profit:
                tp_hit = True
            elif direction == 'SHORT' and current_price <= take_profit:
                tp_hit = True
                
            if not targets.get('take_profit', False) and tp_hit:
                targets['take_profit'] = True
                updates.append(("actual_exit_reason = 'take_profit'", f"time_to_3pct_minutes = {minutes_elapsed}"))
                virtual_updates.append(("virtual_tp_hit = TRUE", "virtual_exit_reason = 'take_profit'"))
                logger.info(f"💰 Take profit hit: {signal_data['symbol']} in {minutes_elapsed}m")
            
            # 🧠 INTELLIGENT STOP LOSS HANDLING
            stop_loss = signal_data['stop_loss']
            
            stop_hit = False
            if direction == 'LONG' and current_price <= stop_loss:
                stop_hit = True
            elif direction == 'SHORT' and current_price >= stop_loss:
                stop_hit = True
                
            if not targets['stop_loss'] and stop_hit:
                targets['stop_loss'] = True
                updates.append(("stop_loss_hit = TRUE", f"time_to_stop_minutes = {minutes_elapsed}"))
                updates.append(("actual_exit_reason = 'stop_loss'", ""))
                
                # 🎯 DUAL REALITY: Don't mark as completed if learning mode enabled
                if self.learning_ignore_stop_loss:
                    logger.info(f"🧠 LEARNING MODE: SL hit on {signal_data['symbol']} but continuing virtual tracking...")
                    signal_data['stop_loss_time'] = current_time
                    signal_data['learning_mode'] = True
                    # DON'T set completed = True - keep tracking!
                else:
                    signal_data['completed'] = True
                    logger.info(f"🛑 Stop loss hit: {signal_data['symbol']} in {minutes_elapsed}m - TRADE CLOSED")
            
            # 🔍 POST-STOP-LOSS FAKEOUT DETECTION
            if signal_data.get('learning_mode', False) and signal_data.get('stop_loss_time'):
                sl_time = signal_data['stop_loss_time']
                time_since_sl = (current_time - sl_time).total_seconds() / 60
                
                # Check if price rebounded after stop loss (FAKEOUT!)
                if direction == 'LONG' and current_price > signal_data['entry_price']:
                    rebound_pct = (current_price - stop_loss) / signal_data['entry_price']
                    virtual_updates.append((f"post_sl_peak_pct = {rebound_pct}", "fakeout_detected = TRUE"))
                    virtual_updates.append(("learning_outcome = 'false_negative'", ""))
                    logger.info(f"🔥 FAKEOUT DETECTED: {signal_data['symbol']} rebounded {rebound_pct:.1%} after SL!")
                    
                elif direction == 'SHORT' and current_price < signal_data['entry_price']:
                    rebound_pct = (stop_loss - current_price) / signal_data['entry_price']
                    virtual_updates.append((f"post_sl_peak_pct = {rebound_pct}", "fakeout_detected = TRUE"))
                    virtual_updates.append(("learning_outcome = 'false_negative'", ""))
                    logger.info(f"🔥 FAKEOUT DETECTED: {signal_data['symbol']} rebounded {rebound_pct:.1%} after SL!")
                
                # Check if virtual take profit would have been hit
                if tp_hit:
                    virtual_updates.append(("virtual_tp_hit = TRUE", "virtual_exit_reason = 'take_profit'"))
                    virtual_updates.append(("learning_outcome = 'would_have_won'", ""))
                    logger.info(f"💡 VIRTUAL TP: {signal_data['symbol']} would have hit TP after SL - LEARNING!")
                
                # Complete virtual tracking after max duration
                if time_since_sl > self.virtual_trade_max_duration:
                    signal_data['completed'] = True
                    virtual_updates.append(("virtual_exit_reason = 'expired'", ""))
                    logger.info(f"⏰ Virtual tracking completed for {signal_data['symbol']} after {self.virtual_trade_max_duration}m")
            
            # 🎯 VIRTUAL GOLDEN SIGNAL DETECTION (Without SL interference)
            if signal_data.get('learning_mode', False) and pnl_pct >= 0.03 and minutes_elapsed <= 60:
                virtual_updates.append(("is_virtual_golden = TRUE", ""))
                logger.info(f"🌟 VIRTUAL GOLDEN: {signal_data['symbol']} would be golden without SL!")
            
            # Apply all updates
            all_updates = updates + virtual_updates
            if all_updates:
                update_clauses = []
                for update_pair in all_updates:
                    if isinstance(update_pair, tuple) and len(update_pair) >= 1:
                        update_clauses.append(update_pair[0])
                        if len(update_pair) > 1 and update_pair[1]:
                            update_clauses.append(update_pair[1])
                
                update_sql = f"""
                    UPDATE enhanced_signals 
                    SET {', '.join(update_clauses)},
                        max_profit_pct = $2,
                        virtual_max_profit_pct = $3,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE signal_id = $1
                """
                
                await conn.execute(update_sql, signal_id, signal_data['max_profit'], pnl_pct)
    
    async def _take_interval_snapshots(self, signal_id: str, signal_data: Dict, current_price: float, pnl_pct: float):
        """Take performance snapshots at specific intervals"""
        entry_time = signal_data['entry_time']
        current_time = datetime.now()
        minutes_elapsed = int((current_time - entry_time).total_seconds() / 60)
        
        # Check which intervals to capture
        for interval in self.tracking_intervals:
            if (minutes_elapsed >= interval and 
                interval not in signal_data['snapshots_taken']):
                
                await self._save_snapshot(signal_id, interval, current_price, pnl_pct)
                signal_data['snapshots_taken'].append(interval)
    
    async def _save_snapshot(self, signal_id: str, interval: int, price: float, pnl_pct: float):
        """Save a PnL snapshot"""
        try:
            async with self.connection_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO pnl_snapshots (
                        signal_id, interval_minutes, current_price, 
                        pnl_pct, pnl_absolute
                    ) VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (signal_id, interval_minutes) 
                    DO UPDATE SET
                        current_price = $3,
                        pnl_pct = $4,
                        pnl_absolute = $5,
                        timestamp = CURRENT_TIMESTAMP
                """, signal_id, interval, price, pnl_pct, 0)  # pnl_absolute calculated separately
                
                logger.debug(f"📸 Snapshot: {signal_id[:8]}... at {interval}m -> {pnl_pct:.2%}")
                
        except Exception as e:
            logger.error(f"❌ Failed to save snapshot: {e}")
    
    async def _check_golden_signal(self, signal_id: str, signal_data: Dict, pnl_pct: float):
        """Check if signal qualifies as golden (quick 3% gainer)"""
        if signal_data['targets_hit']['3pct']:
            entry_time = signal_data['entry_time']
            time_to_3pct = int((datetime.now() - entry_time).total_seconds() / 60)
            
            if time_to_3pct <= self.golden_signal_time_limit:
                await self._mark_as_golden(signal_id, signal_data, time_to_3pct)
    
    async def _mark_as_golden(self, signal_id: str, signal_data: Dict, time_to_3pct: int):
        """Mark signal as golden and save to golden signals table"""
        try:
            async with self.connection_pool.acquire() as conn:
                # Update enhanced_signals
                await conn.execute("""
                    UPDATE enhanced_signals 
                    SET is_golden_signal = TRUE,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE signal_id = $1
                """, signal_id)
                
                # Add to golden_signals table
                await conn.execute("""
                    INSERT INTO golden_signals (
                        signal_id, symbol, strategy, direction,
                        time_to_3pct_minutes, max_pnl_pct, confidence,
                        risk_reward_ratio, market_conditions
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (signal_id) DO NOTHING
                """,
                    signal_id,
                    signal_data['symbol'],
                    signal_data['strategy'],
                    signal_data['direction'],
                    time_to_3pct,
                    signal_data['max_profit'],
                    signal_data['confidence'],
                    signal_data['risk_reward'],
                    json.dumps({})  # market_conditions placeholder
                )
                
                logger.info(f"⭐ GOLDEN SIGNAL: {signal_data['symbol']} {signal_data['strategy']} reached 3% in {time_to_3pct}m!")
                
        except Exception as e:
            logger.error(f"❌ Failed to mark golden signal: {e}")
    
    async def get_performance_summary(self, days_back: int = 7) -> Dict[str, Any]:
        """Get comprehensive performance summary"""
        if not self.enabled or not self.connection_pool:
            return {}
            
        try:
            async with self.connection_pool.acquire() as conn:
                since_date = datetime.now() - timedelta(days=days_back)
                
                # First check total signals in database
                total_count = await conn.fetchval("SELECT COUNT(*) FROM enhanced_signals")
                logger.info(f"🔍 Enhanced Signal Tracker DB: {total_count} total signals in database")
                
                if total_count == 0:
                    # Return active signals data if no database data
                    active_count = len(self.active_signals)
                    logger.info(f"📊 Using active signals data: {active_count} signals")
                    
                    if active_count > 0:
                        # Calculate from active signals
                        total_signals = active_count
                        high_conf_signals = len([s for s in self.active_signals.values() if s['confidence'] >= 0.8])
                        golden_signals = len([s for s in self.active_signals.values() if s['max_profit'] >= 0.03])
                        
                        # Strategy breakdown from active signals
                        strategy_stats = {}
                        for signal_data in self.active_signals.values():
                            strategy = signal_data['strategy']
                            if strategy not in strategy_stats:
                                strategy_stats[strategy] = {'total': 0, 'hit_3pct': 0, 'golden': 0}
                            strategy_stats[strategy]['total'] += 1
                            if signal_data['max_profit'] >= 0.03:
                                strategy_stats[strategy]['hit_3pct'] += 1
                                strategy_stats[strategy]['golden'] += 1
                        
                        by_strategy = [
                            {
                                'strategy': strategy,
                                'total': stats['total'],
                                'hit_3pct': stats['hit_3pct'],
                                'golden': stats['golden'],
                                'avg_time_to_3pct': 45.0
                            }
                            for strategy, stats in strategy_stats.items()
                        ]
                        
                        return {
                            'total_signals': total_signals,
                            'signals_3pct': high_conf_signals,
                            'golden_signals': golden_signals,
                            'avg_time_to_3pct': 45.0,
                            'by_strategy': by_strategy,
                            'tracking_active_signals': active_count,
                            'data_source': 'active_signals'
                        }
                
                # Overall performance from database
                overall = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) as total_signals,
                        COUNT(*) FILTER (WHERE target_3pct_hit) as signals_3pct,
                        COUNT(*) FILTER (WHERE target_5pct_hit) as signals_5pct,
                        COUNT(*) FILTER (WHERE stop_loss_hit) as signals_stopped,
                        COUNT(*) FILTER (WHERE is_golden_signal) as golden_signals,
                        COALESCE(AVG(time_to_3pct_minutes), 0) as avg_time_to_3pct,
                        COALESCE(AVG(max_profit_pct), 0) as avg_max_profit,
                        COALESCE(AVG(confidence), 0) as avg_confidence
                    FROM enhanced_signals 
                    WHERE created_at >= $1
                """, since_date)
                
                # Strategy breakdown
                strategies = await conn.fetch("""
                    SELECT 
                        strategy,
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE target_3pct_hit) as hit_3pct,
                        COUNT(*) FILTER (WHERE is_golden_signal) as golden,
                        COALESCE(AVG(time_to_3pct_minutes), 0) as avg_time_to_3pct
                    FROM enhanced_signals 
                    WHERE created_at >= $1
                    GROUP BY strategy
                    ORDER BY golden DESC, hit_3pct DESC
                """, since_date)
                
                # Recent golden signals
                golden = await conn.fetch("""
                    SELECT symbol, strategy, direction, time_to_3pct_minutes, max_pnl_pct
                    FROM golden_signals 
                    WHERE created_at >= $1
                    ORDER BY created_at DESC
                    LIMIT 10
                """, since_date)
                
                result = dict(overall)
                result.update({
                    'by_strategy': [dict(s) for s in strategies],
                    'recent_golden': [dict(g) for g in golden],
                    'tracking_active_signals': len(self.active_signals),
                    'data_source': 'database'
                })
                
                return result
                
        except Exception as e:
            logger.error(f"❌ Failed to get performance summary: {e}")
            return {}
    
    async def get_golden_signals(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get golden signals for analysis"""
        if not self.enabled or not self.connection_pool:
            return []
            
        try:
            async with self.connection_pool.acquire() as conn:
                golden = await conn.fetch("""
                    SELECT * FROM golden_signals 
                    ORDER BY created_at DESC 
                    LIMIT $1
                """, limit)
                
                return [dict(g) for g in golden]
                
        except Exception as e:
            logger.error(f"❌ Failed to get golden signals: {e}")
            return []
    
    def _generate_signal_id(self, signal: Dict) -> str:
        """Generate unique signal ID"""
        content = f"{signal.get('symbol')}_{signal.get('strategy')}_{signal.get('direction')}_{signal.get('entry_price')}_{datetime.now().isoformat()}"
        return hashlib.md5(content.encode()).hexdigest()
    
    async def close(self):
        """Close tracker and monitoring"""
        if self.monitoring_task:
            self.monitoring_task.cancel()
        
        if self.connection_pool:
            await self.connection_pool.close()

# Global enhanced tracker instance
enhanced_signal_tracker = EnhancedSignalTracker() 