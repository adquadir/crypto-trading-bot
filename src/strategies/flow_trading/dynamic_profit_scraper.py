"""
Dynamic Profit-Scraping Strategy
Adaptively switches between scalping (trending markets) and grid trading (ranging markets)
Continuously scrapes small profits in both up and down market movements
"""

import numpy as np
import pandas as pd
import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict, deque
from enum import Enum

try:
    from .advanced_signal_generator import AdvancedSignalGenerator, MarketSignal
    from .dynamic_grid_optimizer import DynamicGridOptimizer, GridConfiguration
    from .advanced_risk_manager import AdvancedRiskManager, RiskMetrics
except ImportError:
    from advanced_signal_generator import AdvancedSignalGenerator, MarketSignal
    from dynamic_grid_optimizer import DynamicGridOptimizer, GridConfiguration
    from advanced_risk_manager import AdvancedRiskManager, RiskMetrics

logger = logging.getLogger(__name__)

class MarketRegime(Enum):
    """Market regime classification"""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"
    UNKNOWN = "unknown"

class StrategyMode(Enum):
    """Active strategy modes"""
    TREND_SCALPING = "trend_scalping"
    GRID_TRADING = "grid_trading"
    HYBRID = "hybrid"
    STANDBY = "standby"

@dataclass
class ScalpPosition:
    """Individual scalping position"""
    symbol: str
    side: str  # 'LONG' or 'SHORT'
    entry_price: float
    entry_time: datetime
    position_size: float
    take_profit: float
    stop_loss: float
    trailing_stop: Optional[float] = None
    max_profit_seen: float = 0.0
    signal_confidence: float = 0.0
    position_id: str = ""

@dataclass
class GridLevel:
    """Individual grid level"""
    symbol: str
    level_price: float
    side: str  # 'BUY' or 'SELL'
    order_size: float
    filled: bool = False
    fill_time: Optional[datetime] = None
    profit_target: Optional[float] = None
    order_id: Optional[str] = None

@dataclass
class ProfitScrapingMetrics:
    """Performance metrics for profit scraping"""
    total_trades: int = 0
    winning_trades: int = 0
    total_profit: float = 0.0
    avg_profit_per_trade: float = 0.0
    max_drawdown: float = 0.0
    profit_factor: float = 0.0
    scalp_wins: int = 0
    grid_wins: int = 0
    daily_scrapes: int = 0
    last_update: datetime = datetime.utcnow()

class MarketRegimeDetector:
    """Enhanced market regime detection for strategy switching"""
    
    def __init__(self):
        self.regime_history = defaultdict(list)
        self.regime_buffer_length = 5  # Require N consecutive readings before switching
        
    def detect_regime(self, symbol: str, market_data: Dict[str, Any]) -> MarketRegime:
        """Detect current market regime using multiple indicators"""
        try:
            if not market_data or 'klines' not in market_data:
                return MarketRegime.UNKNOWN
            
            klines = market_data['klines']
            if len(klines) < 50:
                return MarketRegime.UNKNOWN
            
            closes = np.array([float(k['close']) for k in klines[-50:]])
            highs = np.array([float(k['high']) for k in klines[-50:]])
            lows = np.array([float(k['low']) for k in klines[-50:]])
            volumes = np.array([float(k['volume']) for k in klines[-50:]])
            
            # Calculate indicators
            sma_20 = np.mean(closes[-20:])
            sma_50 = np.mean(closes[-50:])
            current_price = closes[-1]
            
            # Volatility metrics
            returns = np.diff(closes) / closes[:-1]
            volatility = np.std(returns[-20:]) * np.sqrt(24)  # Daily volatility
            
            # Trend strength using linear regression slope
            x = np.arange(len(closes[-20:]))
            trend_slope = np.polyfit(x, closes[-20:], 1)[0]
            trend_strength = abs(trend_slope) / current_price
            
            # ADX approximation for trend strength
            high_low = highs[-20:] - lows[-20:]
            high_close = np.abs(highs[-20:] - closes[-21:-1])
            low_close = np.abs(lows[-20:] - closes[-21:-1])
            true_range = np.maximum(high_low, np.maximum(high_close, low_close))
            atr = np.mean(true_range)
            
            # Volume analysis
            avg_volume = np.mean(volumes[-20:])
            recent_volume = np.mean(volumes[-5:])
            volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1
            
            # Regime classification logic
            volatility_threshold_low = 0.02   # 2% daily volatility
            volatility_threshold_high = 0.08  # 8% daily volatility
            trend_threshold = 0.001           # 0.1% trend strength
            
            regime = MarketRegime.UNKNOWN
            
            if volatility > volatility_threshold_high:
                regime = MarketRegime.VOLATILE
            elif trend_strength > trend_threshold and volatility > volatility_threshold_low:
                if trend_slope > 0 and current_price > sma_20 > sma_50:
                    regime = MarketRegime.TRENDING_UP
                elif trend_slope < 0 and current_price < sma_20 < sma_50:
                    regime = MarketRegime.TRENDING_DOWN
                else:
                    regime = MarketRegime.RANGING
            else:
                regime = MarketRegime.RANGING
            
            # Apply buffer to prevent frequent switching
            self.regime_history[symbol].append(regime)
            if len(self.regime_history[symbol]) > self.regime_buffer_length:
                self.regime_history[symbol].pop(0)
            
            # Only switch if regime is consistent
            if len(self.regime_history[symbol]) >= self.regime_buffer_length:
                recent_regimes = self.regime_history[symbol][-self.regime_buffer_length:]
                if len(set(recent_regimes)) == 1:  # All same regime
                    return recent_regimes[0]
                else:
                    # Return most common regime
                    regime_counts = {}
                    for r in recent_regimes:
                        regime_counts[r] = regime_counts.get(r, 0) + 1
                    return max(regime_counts, key=regime_counts.get)
            
            return regime
            
        except Exception as e:
            logger.error(f"Error detecting regime for {symbol}: {e}")
            return MarketRegime.UNKNOWN

class TrendScalpingEngine:
    """Scalping engine for trending markets"""
    
    def __init__(self, exchange_client, risk_manager):
        self.exchange_client = exchange_client
        self.risk_manager = risk_manager
        self.active_scalps = {}  # symbol -> ScalpPosition
        self.scalp_history = deque(maxlen=1000)
        
        # Scalping parameters
        self.profit_target_pct = 0.005  # 0.5% profit target
        self.stop_loss_pct = 0.003      # 0.3% stop loss
        self.trailing_stop_pct = 0.002  # 0.2% trailing stop
        self.min_confidence = 0.75      # Minimum signal confidence
        
    async def evaluate_scalp_opportunity(self, symbol: str, market_data: Dict[str, Any], 
                                       regime: MarketRegime) -> Optional[ScalpPosition]:
        """Evaluate if current conditions support a scalp trade"""
        try:
            if regime not in [MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN]:
                return None
            
            if symbol in self.active_scalps:
                return None  # Already have position
            
            # Generate ML signal
            signal_gen = AdvancedSignalGenerator(self.exchange_client)
            signal = await signal_gen.generate_advanced_signal(symbol)
            
            if signal.confidence < self.min_confidence:
                return None
            
            # Check signal alignment with regime
            signal_bullish = signal.signal_type in ['BUY', 'GRID_OPTIMAL'] and signal.ml_score > 0
            signal_bearish = signal.signal_type == 'SELL' and signal.ml_score < 0
            
            if regime == MarketRegime.TRENDING_UP and not signal_bullish:
                return None
            if regime == MarketRegime.TRENDING_DOWN and not signal_bearish:
                return None
            
            # Calculate position parameters
            current_price = float(market_data['klines'][-1]['close'])
            
            # ATR-based targets
            atr = self._calculate_atr(market_data['klines'][-20:])
            
            if regime == MarketRegime.TRENDING_UP:
                side = 'LONG'
                take_profit = current_price * (1 + max(self.profit_target_pct, atr * 2))
                stop_loss = current_price * (1 - max(self.stop_loss_pct, atr))
            else:  # TRENDING_DOWN
                side = 'SHORT'
                take_profit = current_price * (1 - max(self.profit_target_pct, atr * 2))
                stop_loss = current_price * (1 + max(self.stop_loss_pct, atr))
            
            # Position sizing
            risk_amount = await self.risk_manager.calculate_optimal_position_size(
                symbol, signal.confidence, {}, market_data
            )
            
            scalp_position = ScalpPosition(
                symbol=symbol,
                side=side,
                entry_price=current_price,
                entry_time=datetime.utcnow(),
                position_size=risk_amount,
                take_profit=take_profit,
                stop_loss=stop_loss,
                signal_confidence=signal.confidence,
                position_id=f"scalp_{symbol}_{int(datetime.utcnow().timestamp())}"
            )
            
            return scalp_position
            
        except Exception as e:
            logger.error(f"Error evaluating scalp opportunity for {symbol}: {e}")
            return None
    
    def _calculate_atr(self, klines: List[Dict]) -> float:
        """Calculate Average True Range"""
        try:
            if len(klines) < 2:
                return 0.02  # Default 2%
            
            true_ranges = []
            for i in range(1, len(klines)):
                high = float(klines[i]['high'])
                low = float(klines[i]['low'])
                prev_close = float(klines[i-1]['close'])
                
                tr = max(
                    high - low,
                    abs(high - prev_close),
                    abs(low - prev_close)
                )
                true_ranges.append(tr / prev_close)  # Normalize by price
            
            return np.mean(true_ranges) if true_ranges else 0.02
            
        except Exception as e:
            logger.error(f"Error calculating ATR: {e}")
            return 0.02
    
    async def execute_scalp(self, scalp_position: ScalpPosition) -> bool:
        """Execute a scalp trade"""
        try:
            # Mock execution - in real implementation, would place orders
            logger.info(f"Executing scalp {scalp_position.side} on {scalp_position.symbol} "
                       f"at {scalp_position.entry_price:.6f}")
            
            self.active_scalps[scalp_position.symbol] = scalp_position
            return True
            
        except Exception as e:
            logger.error(f"Error executing scalp for {scalp_position.symbol}: {e}")
            return False
    
    async def manage_active_scalps(self, market_data_dict: Dict[str, Dict]) -> List[Dict]:
        """Manage active scalp positions"""
        completed_scalps = []
        
        for symbol, scalp in list(self.active_scalps.items()):
            try:
                if symbol not in market_data_dict:
                    continue
                
                current_price = float(market_data_dict[symbol]['klines'][-1]['close'])
                
                # Calculate current P&L
                if scalp.side == 'LONG':
                    pnl_pct = (current_price - scalp.entry_price) / scalp.entry_price
                else:  # SHORT
                    pnl_pct = (scalp.entry_price - current_price) / scalp.entry_price
                
                # Update max profit seen for trailing stop
                if pnl_pct > scalp.max_profit_seen:
                    scalp.max_profit_seen = pnl_pct
                    # Update trailing stop
                    if scalp.side == 'LONG':
                        scalp.trailing_stop = current_price * (1 - self.trailing_stop_pct)
                    else:
                        scalp.trailing_stop = current_price * (1 + self.trailing_stop_pct)
                
                # Check exit conditions
                should_exit = False
                exit_reason = ""
                
                # Take profit
                if scalp.side == 'LONG' and current_price >= scalp.take_profit:
                    should_exit = True
                    exit_reason = "take_profit"
                elif scalp.side == 'SHORT' and current_price <= scalp.take_profit:
                    should_exit = True
                    exit_reason = "take_profit"
                
                # Stop loss
                elif scalp.side == 'LONG' and current_price <= scalp.stop_loss:
                    should_exit = True
                    exit_reason = "stop_loss"
                elif scalp.side == 'SHORT' and current_price >= scalp.stop_loss:
                    should_exit = True
                    exit_reason = "stop_loss"
                
                # Trailing stop
                elif scalp.trailing_stop:
                    if scalp.side == 'LONG' and current_price <= scalp.trailing_stop:
                        should_exit = True
                        exit_reason = "trailing_stop"
                    elif scalp.side == 'SHORT' and current_price >= scalp.trailing_stop:
                        should_exit = True
                        exit_reason = "trailing_stop"
                
                # Time-based exit (max 30 minutes for scalps)
                elif (datetime.utcnow() - scalp.entry_time).total_seconds() > 1800:
                    should_exit = True
                    exit_reason = "time_limit"
                
                if should_exit:
                    profit_usd = pnl_pct * scalp.position_size
                    
                    completed_scalp = {
                        'symbol': symbol,
                        'side': scalp.side,
                        'entry_price': scalp.entry_price,
                        'exit_price': current_price,
                        'pnl_pct': pnl_pct,
                        'profit_usd': profit_usd,
                        'duration_minutes': (datetime.utcnow() - scalp.entry_time).total_seconds() / 60,
                        'exit_reason': exit_reason,
                        'confidence': scalp.signal_confidence
                    }
                    
                    completed_scalps.append(completed_scalp)
                    self.scalp_history.append(completed_scalp)
                    del self.active_scalps[symbol]
                    
                    logger.info(f"Scalp completed: {symbol} {scalp.side} "
                              f"P&L: {pnl_pct:.2%} (${profit_usd:.2f}) - {exit_reason}")
                
            except Exception as e:
                logger.error(f"Error managing scalp for {symbol}: {e}")
        
        return completed_scalps

class GridTradingEngine:
    """Grid trading engine for ranging markets"""
    
    def __init__(self, exchange_client, risk_manager):
        self.exchange_client = exchange_client
        self.risk_manager = risk_manager
        self.active_grids = {}  # symbol -> List[GridLevel]
        self.grid_profits = deque(maxlen=1000)
        
        # Grid parameters
        self.grid_levels = 5
        self.grid_spacing_pct = 0.004  # 0.4% between levels
        self.profit_per_level = 0.003  # 0.3% profit per fill
        self.max_grid_exposure = 0.02  # 2% of account per grid
        
    async def setup_grid(self, symbol: str, market_data: Dict[str, Any]) -> List[GridLevel]:
        """Setup grid trading levels around current price"""
        try:
            if symbol in self.active_grids:
                return self.active_grids[symbol]  # Grid already active
            
            current_price = float(market_data['klines'][-1]['close'])
            
            # Calculate dynamic spacing based on volatility
            atr = self._calculate_atr(market_data['klines'][-20:])
            dynamic_spacing = max(self.grid_spacing_pct, atr * 0.5)
            
            # Position size per level
            total_risk = await self.risk_manager.calculate_optimal_position_size(
                symbol, 0.8, {}, market_data  # High confidence for grid
            )
            size_per_level = total_risk / (self.grid_levels * 2)  # Buy and sell levels
            
            grid_levels = []
            
            # Create buy levels below current price
            for i in range(1, self.grid_levels + 1):
                buy_price = current_price * (1 - dynamic_spacing * i)
                profit_target = buy_price * (1 + self.profit_per_level)
                
                grid_level = GridLevel(
                    symbol=symbol,
                    level_price=buy_price,
                    side='BUY',
                    order_size=size_per_level,
                    profit_target=profit_target
                )
                grid_levels.append(grid_level)
            
            # Create sell levels above current price
            for i in range(1, self.grid_levels + 1):
                sell_price = current_price * (1 + dynamic_spacing * i)
                profit_target = sell_price * (1 - self.profit_per_level)
                
                grid_level = GridLevel(
                    symbol=symbol,
                    level_price=sell_price,
                    side='SELL',
                    order_size=size_per_level,
                    profit_target=profit_target
                )
                grid_levels.append(grid_level)
            
            self.active_grids[symbol] = grid_levels
            
            logger.info(f"Setup grid for {symbol}: {len(grid_levels)} levels "
                       f"around ${current_price:.6f} with {dynamic_spacing:.2%} spacing")
            
            return grid_levels
            
        except Exception as e:
            logger.error(f"Error setting up grid for {symbol}: {e}")
            return []
    
    def _calculate_atr(self, klines: List[Dict]) -> float:
        """Calculate Average True Range for grid spacing"""
        try:
            if len(klines) < 2:
                return 0.02
            
            true_ranges = []
            for i in range(1, len(klines)):
                high = float(klines[i]['high'])
                low = float(klines[i]['low'])
                prev_close = float(klines[i-1]['close'])
                
                tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                true_ranges.append(tr / prev_close)
            
            return np.mean(true_ranges) if true_ranges else 0.02
            
        except Exception as e:
            logger.error(f"Error calculating ATR for grid: {e}")
            return 0.02
    
    async def manage_grid_fills(self, symbol: str, current_price: float) -> List[Dict]:
        """Check for grid level fills and manage profit targets"""
        if symbol not in self.active_grids:
            return []
        
        grid_profits = []
        grid_levels = self.active_grids[symbol]
        
        for level in grid_levels:
            try:
                # Check if level should be filled
                if not level.filled:
                    if level.side == 'BUY' and current_price <= level.level_price:
                        level.filled = True
                        level.fill_time = datetime.utcnow()
                        logger.info(f"Grid BUY filled: {symbol} at ${level.level_price:.6f}")
                    elif level.side == 'SELL' and current_price >= level.level_price:
                        level.filled = True
                        level.fill_time = datetime.utcnow()
                        logger.info(f"Grid SELL filled: {symbol} at ${level.level_price:.6f}")
                
                # Check profit targets for filled levels
                elif level.filled and level.profit_target:
                    profit_hit = False
                    
                    if level.side == 'BUY' and current_price >= level.profit_target:
                        profit_hit = True
                    elif level.side == 'SELL' and current_price <= level.profit_target:
                        profit_hit = True
                    
                    if profit_hit:
                        pnl_pct = abs(level.profit_target - level.level_price) / level.level_price
                        profit_usd = pnl_pct * level.order_size
                        
                        grid_profit = {
                            'symbol': symbol,
                            'side': level.side,
                            'entry_price': level.level_price,
                            'exit_price': level.profit_target,
                            'pnl_pct': pnl_pct,
                            'profit_usd': profit_usd,
                            'duration_minutes': (datetime.utcnow() - level.fill_time).total_seconds() / 60,
                            'level_type': 'grid'
                        }
                        
                        grid_profits.append(grid_profit)
                        self.grid_profits.append(grid_profit)
                        
                        # Reset level for next cycle
                        level.filled = False
                        level.fill_time = None
                        
                        logger.info(f"Grid profit: {symbol} {level.side} "
                                  f"${profit_usd:.2f} ({pnl_pct:.2%})")
                
            except Exception as e:
                logger.error(f"Error managing grid level for {symbol}: {e}")
        
        return grid_profits
    
    async def stop_grid(self, symbol: str, reason: str = "manual"):
        """Stop grid trading for a symbol"""
        if symbol in self.active_grids:
            del self.active_grids[symbol]
            logger.info(f"Stopped grid trading for {symbol}: {reason}")

class DynamicProfitScraper:
    """Main profit scraping orchestrator"""
    
    def __init__(self, exchange_client, base_risk_manager):
        self.exchange_client = exchange_client
        self.base_risk_manager = base_risk_manager
        
        # Initialize components
        self.regime_detector = MarketRegimeDetector()
        self.trend_scalper = TrendScalpingEngine(exchange_client, base_risk_manager)
        self.grid_trader = GridTradingEngine(exchange_client, base_risk_manager)
        self.advanced_risk_manager = AdvancedRiskManager(base_risk_manager)
        
        # State tracking
        self.active_symbols = set()
        self.symbol_strategies = {}  # symbol -> StrategyMode
        self.symbol_regimes = {}     # symbol -> MarketRegime
        self.performance_metrics = ProfitScrapingMetrics()
        
        # Configuration
        self.max_concurrent_symbols = 10
        self.regime_check_interval = 300  # 5 minutes
        self.last_regime_check = {}
        self.running = False
        
    async def start_profit_scraping(self, symbols: List[str]):
        """Start the dynamic profit scraping system"""
        self.running = True
        self.active_symbols = set(symbols[:self.max_concurrent_symbols])
        
        logger.info(f"🚀 Starting Dynamic Profit Scraping on {len(self.active_symbols)} symbols")
        
        # Initialize strategies for each symbol
        for symbol in self.active_symbols:
            self.symbol_strategies[symbol] = StrategyMode.STANDBY
            self.symbol_regimes[symbol] = MarketRegime.UNKNOWN
        
        # Start main loop
        asyncio.create_task(self._profit_scraping_loop())
    
    def stop_profit_scraping(self):
        """Stop the profit scraping system"""
        self.running = False
        logger.info("🛑 Stopping Dynamic Profit Scraping")
    
    async def _profit_scraping_loop(self):
        """Main profit scraping loop"""
        while self.running:
            try:
                # Get market data for all symbols
                market_data_dict = await self._get_market_data_batch(self.active_symbols)
                
                for symbol in self.active_symbols:
                    if symbol not in market_data_dict:
                        continue
                    
                    market_data = market_data_dict[symbol]
                    
                    # Check if regime detection is needed
                    now = datetime.utcnow()
                    last_check = self.last_regime_check.get(symbol, datetime.min)
                    
                    if (now - last_check).total_seconds() >= self.regime_check_interval:
                        await self._update_symbol_strategy(symbol, market_data)
                        self.last_regime_check[symbol] = now
                    
                    # Execute current strategy
                    await self._execute_symbol_strategy(symbol, market_data)
                
                # Manage all active positions
                await self._manage_active_positions(market_data_dict)
                
                # Update performance metrics
                self._update_performance_metrics()
                
                await asyncio.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                logger.error(f"Error in profit scraping loop: {e}")
                await asyncio.sleep(30)
    
    async def _get_market_data_batch(self, symbols: List[str]) -> Dict[str, Dict]:
        """Get market data for multiple symbols"""
        market_data_dict = {}
        
        for symbol in symbols:
            try:
                # Mock market data - replace with real exchange calls
                market_data_dict[symbol] = await self._generate_mock_market_data(symbol)
            except Exception as e:
                logger.error(f"Error getting market data for {symbol}: {e}")
        
        return market_data_dict
    
    async def _generate_mock_market_data(self, symbol: str) -> Dict[str, Any]:
        """Generate mock market data for testing"""
        import random
        import time
        
        # Generate realistic OHLCV data
        base_price = 50000.0 if 'BTC' in symbol else 3000.0
        current_time = int(time.time() * 1000)
        
        klines = []
        price = base_price
        
        # Generate 100 5-minute candles
        for i in range(100):
            timestamp = current_time - (100 - i) * 5 * 60 * 1000
            
            # Simulate price movement
            change_pct = random.uniform(-0.01, 0.01)  # ±1%
            new_price = price * (1 + change_pct)
            
            open_price = price
            close_price = new_price
            high_price = max(open_price, close_price) * (1 + random.uniform(0, 0.005))
            low_price = min(open_price, close_price) * (1 - random.uniform(0, 0.005))
            volume = random.uniform(1000, 10000)
            
            klines.append({
                'timestamp': timestamp,
                'open': str(open_price),
                'high': str(high_price),
                'low': str(low_price),
                'close': str(close_price),
                'volume': str(volume)
            })
            
            price = new_price
        
        return {
            'symbol': symbol,
            'klines': klines,
            'indicators': {
                'atr': price * 0.02,  # 2% ATR
                'volume_ratio': random.uniform(0.8, 1.5)
            }
        }
    
    async def _update_symbol_strategy(self, symbol: str, market_data: Dict[str, Any]):
        """Update strategy for a symbol based on regime detection"""
        try:
            # Detect current regime
            current_regime = self.regime_detector.detect_regime(symbol, market_data)
            previous_regime = self.symbol_regimes.get(symbol, MarketRegime.UNKNOWN)
            
            if current_regime != previous_regime:
                logger.info(f"Regime change for {symbol}: {previous_regime.value} -> {current_regime.value}")
                
                # Stop current strategy if switching
                await self._stop_current_strategy(symbol)
                
                # Determine new strategy mode
                if current_regime in [MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN]:
                    new_mode = StrategyMode.TREND_SCALPING
                elif current_regime == MarketRegime.RANGING:
                    new_mode = StrategyMode.GRID_TRADING
                elif current_regime == MarketRegime.VOLATILE:
                    new_mode = StrategyMode.HYBRID
                else:
                    new_mode = StrategyMode.STANDBY
                
                self.symbol_regimes[symbol] = current_regime
                self.symbol_strategies[symbol] = new_mode
                
                logger.info(f"Strategy for {symbol}: {new_mode.value}")
                
        except Exception as e:
            logger.error(f"Error updating strategy for {symbol}: {e}")
    
    async def _stop_current_strategy(self, symbol: str):
        """Stop current active strategy for a symbol"""
        try:
            current_mode = self.symbol_strategies.get(symbol, StrategyMode.STANDBY)
            
            if current_mode == StrategyMode.TREND_SCALPING:
                if symbol in self.trend_scalper.active_scalps:
                    del self.trend_scalper.active_scalps[symbol]
            
            elif current_mode == StrategyMode.GRID_TRADING:
                await self.grid_trader.stop_grid(symbol, "regime_change")
            
        except Exception as e:
            logger.error(f"Error stopping strategy for {symbol}: {e}")
    
    async def _execute_symbol_strategy(self, symbol: str, market_data: Dict[str, Any]):
        """Execute the active strategy for a symbol"""
        try:
            strategy_mode = self.symbol_strategies.get(symbol, StrategyMode.STANDBY)
            regime = self.symbol_regimes.get(symbol, MarketRegime.UNKNOWN)
            
            if strategy_mode == StrategyMode.TREND_SCALPING:
                # Check for new scalp opportunities
                scalp_opportunity = await self.trend_scalper.evaluate_scalp_opportunity(
                    symbol, market_data, regime
                )
                
                if scalp_opportunity:
                    await self.trend_scalper.execute_scalp(scalp_opportunity)
            
            elif strategy_mode == StrategyMode.GRID_TRADING:
                # Setup or maintain grid
                if symbol not in self.grid_trader.active_grids:
                    await self.grid_trader.setup_grid(symbol, market_data)
            
            elif strategy_mode == StrategyMode.HYBRID:
                # Use both strategies with reduced allocation
                # Could implement more sophisticated hybrid logic
                pass
            
        except Exception as e:
            logger.error(f"Error executing strategy for {symbol}: {e}")
    
    async def _manage_active_positions(self, market_data_dict: Dict[str, Dict]):
        """Manage all active positions across strategies"""
        try:
            # Manage scalp positions
            scalp_completions = await self.trend_scalper.manage_active_scalps(market_data_dict)
            
            # Manage grid positions
            for symbol, market_data in market_data_dict.items():
                current_price = float(market_data['klines'][-1]['close'])
                grid_profits = await self.grid_trader.manage_grid_fills(symbol, current_price)
                
                # Update metrics with grid profits
                for profit in grid_profits:
                    self.performance_metrics.total_trades += 1
                    self.performance_metrics.total_profit += profit['profit_usd']
                    if profit['profit_usd'] > 0:
                        self.performance_metrics.winning_trades += 1
                        self.performance_metrics.grid_wins += 1
            
            # Update metrics with scalp completions
            for completion in scalp_completions:
                self.performance_metrics.total_trades += 1
                self.performance_metrics.total_profit += completion['profit_usd']
                if completion['profit_usd'] > 0:
                    self.performance_metrics.winning_trades += 1
                    self.performance_metrics.scalp_wins += 1
            
        except Exception as e:
            logger.error(f"Error managing active positions: {e}")
    
    def _update_performance_metrics(self):
        """Update overall performance metrics"""
        try:
            if self.performance_metrics.total_trades > 0:
                self.performance_metrics.avg_profit_per_trade = (
                    self.performance_metrics.total_profit / self.performance_metrics.total_trades
                )
                
                win_rate = self.performance_metrics.winning_trades / self.performance_metrics.total_trades
                
                # Update daily scrapes count
                if self.performance_metrics.last_update.date() != datetime.utcnow().date():
                    self.performance_metrics.daily_scrapes = 0
                
                self.performance_metrics.daily_scrapes += 1
                self.performance_metrics.last_update = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Error updating performance metrics: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current profit scraping status"""
        return {
            'running': self.running,
            'active_symbols': len(self.active_symbols),
            'strategy_distribution': {
                mode.value: sum(1 for m in self.symbol_strategies.values() if m == mode)
                for mode in StrategyMode
            },
            'regime_distribution': {
                regime.value: sum(1 for r in self.symbol_regimes.values() if r == regime)
                for regime in MarketRegime
            },
            'active_scalps': len(self.trend_scalper.active_scalps),
            'active_grids': len(self.grid_trader.active_grids),
            'performance': {
                'total_trades': self.performance_metrics.total_trades,
                'winning_trades': self.performance_metrics.winning_trades,
                'win_rate': (self.performance_metrics.winning_trades / 
                           max(1, self.performance_metrics.total_trades)),
                'total_profit': self.performance_metrics.total_profit,
                'avg_profit_per_trade': self.performance_metrics.avg_profit_per_trade,
                'scalp_wins': self.performance_metrics.scalp_wins,
                'grid_wins': self.performance_metrics.grid_wins,
                'daily_scrapes': self.performance_metrics.daily_scrapes
            }
        }
    
    def get_symbol_details(self, symbol: str) -> Dict[str, Any]:
        """Get detailed status for a specific symbol"""
        return {
            'symbol': symbol,
            'regime': self.symbol_regimes.get(symbol, MarketRegime.UNKNOWN).value,
            'strategy': self.symbol_strategies.get(symbol, StrategyMode.STANDBY).value,
            'has_scalp': symbol in self.trend_scalper.active_scalps,
            'has_grid': symbol in self.grid_trader.active_grids,
            'scalp_details': self.trend_scalper.active_scalps.get(symbol).__dict__ if symbol in self.trend_scalper.active_scalps else None,
            'grid_levels': len(self.grid_trader.active_grids.get(symbol, [])),
            'last_regime_check': self.last_regime_check.get(symbol, datetime.min).isoformat()
        } 