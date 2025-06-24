"""
Dynamic Profit-Scraping Core System
Main orchestrator for adaptive profit scraping that flows with market conditions
"""

import numpy as np
import asyncio
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict, deque
from enum import Enum

logger = logging.getLogger(__name__)

class MarketRegime(Enum):
    """Market regime classification for strategy selection"""
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
class ProfitScrapResult:
    """Result of a profit scraping trade"""
    symbol: str
    strategy_type: str  # 'scalp' or 'grid'
    side: str  # 'LONG' or 'SHORT'
    entry_price: float
    exit_price: float
    pnl_pct: float
    profit_usd: float
    duration_minutes: float
    timestamp: datetime
    confidence: float = 0.0

class MarketRegimeDetector:
    """Detects market regime for adaptive strategy switching"""
    
    def __init__(self):
        self.regime_history = defaultdict(list)
        self.regime_buffer = 3  # Require consistent readings
        
    def detect_regime(self, symbol: str, market_data: Dict[str, Any]) -> MarketRegime:
        """Analyze market data to determine current regime"""
        try:
            if not market_data or 'klines' not in market_data:
                return MarketRegime.UNKNOWN
            
            klines = market_data['klines']
            if len(klines) < 30:
                return MarketRegime.UNKNOWN
            
            # Extract price data
            closes = np.array([float(k['close']) for k in klines[-30:]])
            highs = np.array([float(k['high']) for k in klines[-30:]])
            lows = np.array([float(k['low']) for k in klines[-30:]])
            
            current_price = closes[-1]
            
            # Calculate moving averages
            sma_10 = np.mean(closes[-10:])
            sma_20 = np.mean(closes[-20:])
            
            # Volatility calculation
            returns = np.diff(closes) / closes[:-1]
            volatility = np.std(returns[-20:])
            
            # Trend strength
            trend_slope = np.polyfit(range(len(closes[-20:])), closes[-20:], 1)[0]
            trend_strength = abs(trend_slope) / current_price
            
            # Classification thresholds
            volatility_high = 0.04  # 4%
            volatility_low = 0.01   # 1%
            trend_threshold = 0.0005  # 0.05%
            
            # Determine regime
            if volatility > volatility_high:
                regime = MarketRegime.VOLATILE
            elif trend_strength > trend_threshold:
                if trend_slope > 0 and current_price > sma_10 > sma_20:
                    regime = MarketRegime.TRENDING_UP
                elif trend_slope < 0 and current_price < sma_10 < sma_20:
                    regime = MarketRegime.TRENDING_DOWN
                else:
                    regime = MarketRegime.RANGING
            else:
                regime = MarketRegime.RANGING
            
            # Apply buffer for stability
            self.regime_history[symbol].append(regime)
            if len(self.regime_history[symbol]) > self.regime_buffer:
                self.regime_history[symbol].pop(0)
            
            # Return most common recent regime
            if len(self.regime_history[symbol]) >= self.regime_buffer:
                regime_counts = {}
                for r in self.regime_history[symbol]:
                    regime_counts[r] = regime_counts.get(r, 0) + 1
                return max(regime_counts, key=regime_counts.get)
            
            return regime
            
        except Exception as e:
            logger.error(f"Error detecting regime for {symbol}: {e}")
            return MarketRegime.UNKNOWN

class TrendScalpingStrategy:
    """Scalping strategy for trending markets"""
    
    def __init__(self):
        self.active_scalps = {}
        self.profit_target = 0.005  # 0.5%
        self.stop_loss = 0.003      # 0.3%
        self.min_confidence = 0.7
        
    async def evaluate_scalp_signal(self, symbol: str, market_data: Dict[str, Any], 
                                  regime: MarketRegime) -> Optional[Dict[str, Any]]:
        """Evaluate scalping opportunity in trending market"""
        try:
            if regime not in [MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN]:
                return None
            
            if symbol in self.active_scalps:
                return None  # Already have position
            
            klines = market_data['klines']
            if len(klines) < 10:
                return None
            
            closes = np.array([float(k['close']) for k in klines[-10:]])
            current_price = closes[-1]
            
            # Simple momentum signal
            sma_5 = np.mean(closes[-5:])
            price_above_sma = current_price > sma_5
            
            # RSI calculation
            deltas = np.diff(closes)
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)
            avg_gain = np.mean(gains[-5:]) if len(gains) >= 5 else 0
            avg_loss = np.mean(losses[-5:]) if len(losses) >= 5 else 0.001
            rsi = 100 - (100 / (1 + avg_gain / avg_loss))
            
            # Signal logic
            signal = None
            confidence = 0.5
            
            if regime == MarketRegime.TRENDING_UP:
                # Look for dips to buy in uptrend
                if rsi < 40 and price_above_sma:
                    signal = {
                        'side': 'LONG',
                        'entry_price': current_price,
                        'take_profit': current_price * (1 + self.profit_target),
                        'stop_loss': current_price * (1 - self.stop_loss),
                        'confidence': min(0.9, 0.6 + (40 - rsi) / 100)
                    }
            
            elif regime == MarketRegime.TRENDING_DOWN:
                # Look for bounces to sell in downtrend
                if rsi > 60 and not price_above_sma:
                    signal = {
                        'side': 'SHORT',
                        'entry_price': current_price,
                        'take_profit': current_price * (1 - self.profit_target),
                        'stop_loss': current_price * (1 + self.stop_loss),
                        'confidence': min(0.9, 0.6 + (rsi - 60) / 100)
                    }
            
            if signal and signal['confidence'] >= self.min_confidence:
                return signal
            
            return None
            
        except Exception as e:
            logger.error(f"Error evaluating scalp signal for {symbol}: {e}")
            return None
    
    async def manage_scalp_position(self, symbol: str, current_price: float) -> Optional[ProfitScrapResult]:
        """Manage active scalp position"""
        if symbol not in self.active_scalps:
            return None
        
        try:
            scalp = self.active_scalps[symbol]
            
            # Calculate P&L
            if scalp['side'] == 'LONG':
                pnl_pct = (current_price - scalp['entry_price']) / scalp['entry_price']
            else:
                pnl_pct = (scalp['entry_price'] - current_price) / scalp['entry_price']
            
            # Check exit conditions
            should_exit = False
            exit_reason = ""
            
            # Take profit
            if scalp['side'] == 'LONG' and current_price >= scalp['take_profit']:
                should_exit = True
                exit_reason = "take_profit"
            elif scalp['side'] == 'SHORT' and current_price <= scalp['take_profit']:
                should_exit = True
                exit_reason = "take_profit"
            
            # Stop loss
            elif scalp['side'] == 'LONG' and current_price <= scalp['stop_loss']:
                should_exit = True
                exit_reason = "stop_loss"
            elif scalp['side'] == 'SHORT' and current_price >= scalp['stop_loss']:
                should_exit = True
                exit_reason = "stop_loss"
            
            # Time limit (15 minutes max)
            elif (datetime.utcnow() - scalp['entry_time']).total_seconds() > 900:
                should_exit = True
                exit_reason = "time_limit"
            
            if should_exit:
                result = ProfitScrapResult(
                    symbol=symbol,
                    strategy_type='scalp',
                    side=scalp['side'],
                    entry_price=scalp['entry_price'],
                    exit_price=current_price,
                    pnl_pct=pnl_pct,
                    profit_usd=pnl_pct * 1000,  # Assuming $1000 position
                    duration_minutes=(datetime.utcnow() - scalp['entry_time']).total_seconds() / 60,
                    timestamp=datetime.utcnow(),
                    confidence=scalp['confidence']
                )
                
                del self.active_scalps[symbol]
                logger.info(f"Scalp completed: {symbol} {scalp['side']} P&L: {pnl_pct:.2%} - {exit_reason}")
                return result
            
            return None
            
        except Exception as e:
            logger.error(f"Error managing scalp position for {symbol}: {e}")
            return None
    
    def add_scalp_position(self, symbol: str, signal: Dict[str, Any]):
        """Add new scalp position"""
        self.active_scalps[symbol] = {
            **signal,
            'entry_time': datetime.utcnow(),
            'position_id': f"scalp_{symbol}_{int(datetime.utcnow().timestamp())}"
        }

class GridTradingStrategy:
    """Grid trading strategy for ranging markets"""
    
    def __init__(self):
        self.active_grids = {}
        self.grid_spacing = 0.004  # 0.4%
        self.grid_levels = 3
        self.profit_per_level = 0.002  # 0.2%
        
    async def setup_grid(self, symbol: str, market_data: Dict[str, Any]) -> bool:
        """Setup grid trading levels"""
        try:
            if symbol in self.active_grids:
                return True  # Already have grid
            
            current_price = float(market_data['klines'][-1]['close'])
            
            grid_levels = []
            
            # Create buy levels below current price
            for i in range(1, self.grid_levels + 1):
                buy_price = current_price * (1 - self.grid_spacing * i)
                profit_target = buy_price * (1 + self.profit_per_level)
                
                grid_levels.append({
                    'side': 'BUY',
                    'price': buy_price,
                    'profit_target': profit_target,
                    'filled': False,
                    'fill_time': None
                })
            
            # Create sell levels above current price
            for i in range(1, self.grid_levels + 1):
                sell_price = current_price * (1 + self.grid_spacing * i)
                profit_target = sell_price * (1 - self.profit_per_level)
                
                grid_levels.append({
                    'side': 'SELL',
                    'price': sell_price,
                    'profit_target': profit_target,
                    'filled': False,
                    'fill_time': None
                })
            
            self.active_grids[symbol] = {
                'levels': grid_levels,
                'center_price': current_price,
                'setup_time': datetime.utcnow()
            }
            
            logger.info(f"Grid setup for {symbol}: {len(grid_levels)} levels around ${current_price:.6f}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting up grid for {symbol}: {e}")
            return False
    
    async def manage_grid_levels(self, symbol: str, current_price: float) -> List[ProfitScrapResult]:
        """Manage grid level fills and profit targets"""
        if symbol not in self.active_grids:
            return []
        
        results = []
        
        try:
            grid = self.active_grids[symbol]
            
            for level in grid['levels']:
                # Check for fills
                if not level['filled']:
                    if level['side'] == 'BUY' and current_price <= level['price']:
                        level['filled'] = True
                        level['fill_time'] = datetime.utcnow()
                        logger.info(f"Grid BUY filled: {symbol} at ${level['price']:.6f}")
                    
                    elif level['side'] == 'SELL' and current_price >= level['price']:
                        level['filled'] = True
                        level['fill_time'] = datetime.utcnow()
                        logger.info(f"Grid SELL filled: {symbol} at ${level['price']:.6f}")
                
                # Check profit targets for filled levels
                elif level['filled']:
                    profit_hit = False
                    
                    if level['side'] == 'BUY' and current_price >= level['profit_target']:
                        profit_hit = True
                    elif level['side'] == 'SELL' and current_price <= level['profit_target']:
                        profit_hit = True
                    
                    if profit_hit:
                        pnl_pct = abs(level['profit_target'] - level['price']) / level['price']
                        
                        result = ProfitScrapResult(
                            symbol=symbol,
                            strategy_type='grid',
                            side=level['side'],
                            entry_price=level['price'],
                            exit_price=level['profit_target'],
                            pnl_pct=pnl_pct,
                            profit_usd=pnl_pct * 500,  # Assuming $500 per level
                            duration_minutes=(datetime.utcnow() - level['fill_time']).total_seconds() / 60,
                            timestamp=datetime.utcnow(),
                            confidence=0.8
                        )
                        
                        results.append(result)
                        
                        # Reset level for next cycle
                        level['filled'] = False
                        level['fill_time'] = None
                        
                        logger.info(f"Grid profit: {symbol} {level['side']} "
                                  f"${result.profit_usd:.2f} ({pnl_pct:.2%})")
            
            return results
            
        except Exception as e:
            logger.error(f"Error managing grid levels for {symbol}: {e}")
            return []
    
    def stop_grid(self, symbol: str):
        """Stop grid trading for symbol"""
        if symbol in self.active_grids:
            del self.active_grids[symbol]
            logger.info(f"Grid stopped for {symbol}")

class DynamicProfitScraper:
    """Main profit scraping orchestrator"""
    
    def __init__(self, exchange_client=None):
        self.exchange_client = exchange_client
        
        # Initialize components
        self.regime_detector = MarketRegimeDetector()
        self.trend_scalper = TrendScalpingStrategy()
        self.grid_trader = GridTradingStrategy()
        
        # State
        self.active_symbols = set()
        self.symbol_strategies = {}  # symbol -> StrategyMode
        self.symbol_regimes = {}     # symbol -> MarketRegime
        self.profit_history = deque(maxlen=1000)
        
        # Performance tracking
        self.total_profits = 0.0
        self.total_trades = 0
        self.winning_trades = 0
        self.running = False
        
    async def start_scraping(self, symbols: List[str]):
        """Start dynamic profit scraping"""
        self.running = True
        self.active_symbols = set(symbols[:10])  # Limit to 10 symbols
        
        logger.info(f"🚀 Starting Dynamic Profit Scraping on {len(self.active_symbols)} symbols")
        
        # Initialize strategies
        for symbol in self.active_symbols:
            self.symbol_strategies[symbol] = StrategyMode.STANDBY
            self.symbol_regimes[symbol] = MarketRegime.UNKNOWN
        
        # Start main loop
        asyncio.create_task(self._scraping_loop())
    
    def stop_scraping(self):
        """Stop profit scraping"""
        self.running = False
        logger.info("🛑 Stopping Dynamic Profit Scraping")
    
    async def _scraping_loop(self):
        """Main profit scraping loop"""
        while self.running:
            try:
                # Get market data for all symbols
                market_data_dict = await self._get_market_data_batch(list(self.active_symbols))
                
                for symbol in self.active_symbols:
                    if symbol not in market_data_dict:
                        continue
                    
                    market_data = market_data_dict[symbol]
                    
                    # Detect regime and update strategy
                    await self._update_symbol_strategy(symbol, market_data)
                    
                    # Execute current strategy
                    await self._execute_strategy(symbol, market_data)
                    
                    # Manage active positions
                    await self._manage_positions(symbol, market_data)
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in scraping loop: {e}")
                await asyncio.sleep(60)
    
    async def _get_market_data_batch(self, symbols: List[str]) -> Dict[str, Dict]:
        """Get market data for symbols"""
        market_data = {}
        
        for symbol in symbols:
            # Mock data for testing
            market_data[symbol] = await self._generate_mock_data(symbol)
        
        return market_data
    
    async def _generate_mock_data(self, symbol: str) -> Dict[str, Any]:
        """Generate mock market data"""
        import random
        import time
        
        base_price = 50000.0 if 'BTC' in symbol else 3000.0
        current_time = int(time.time() * 1000)
        
        klines = []
        price = base_price
        
        for i in range(50):
            timestamp = current_time - (50 - i) * 5 * 60 * 1000
            change = random.uniform(-0.005, 0.005)  # ±0.5%
            price *= (1 + change)
            
            klines.append({
                'timestamp': timestamp,
                'open': str(price),
                'high': str(price * (1 + abs(change) * 0.5)),
                'low': str(price * (1 - abs(change) * 0.5)),
                'close': str(price),
                'volume': str(random.uniform(1000, 5000))
            })
        
        return {'symbol': symbol, 'klines': klines}
    
    async def _update_symbol_strategy(self, symbol: str, market_data: Dict[str, Any]):
        """Update strategy based on regime"""
        try:
            current_regime = self.regime_detector.detect_regime(symbol, market_data)
            previous_regime = self.symbol_regimes.get(symbol, MarketRegime.UNKNOWN)
            
            if current_regime != previous_regime:
                logger.info(f"Regime change {symbol}: {previous_regime.value} -> {current_regime.value}")
                
                # Stop current strategy
                await self._stop_current_strategy(symbol)
                
                # Set new strategy
                if current_regime in [MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN]:
                    self.symbol_strategies[symbol] = StrategyMode.TREND_SCALPING
                elif current_regime == MarketRegime.RANGING:
                    self.symbol_strategies[symbol] = StrategyMode.GRID_TRADING
                else:
                    self.symbol_strategies[symbol] = StrategyMode.STANDBY
                
                self.symbol_regimes[symbol] = current_regime
                
        except Exception as e:
            logger.error(f"Error updating strategy for {symbol}: {e}")
    
    async def _stop_current_strategy(self, symbol: str):
        """Stop current strategy for symbol"""
        current_mode = self.symbol_strategies.get(symbol, StrategyMode.STANDBY)
        
        if current_mode == StrategyMode.TREND_SCALPING:
            if symbol in self.trend_scalper.active_scalps:
                del self.trend_scalper.active_scalps[symbol]
        
        elif current_mode == StrategyMode.GRID_TRADING:
            self.grid_trader.stop_grid(symbol)
    
    async def _execute_strategy(self, symbol: str, market_data: Dict[str, Any]):
        """Execute active strategy for symbol"""
        strategy_mode = self.symbol_strategies.get(symbol, StrategyMode.STANDBY)
        regime = self.symbol_regimes.get(symbol, MarketRegime.UNKNOWN)
        
        try:
            if strategy_mode == StrategyMode.TREND_SCALPING:
                # Check for scalp opportunity
                signal = await self.trend_scalper.evaluate_scalp_signal(symbol, market_data, regime)
                if signal:
                    self.trend_scalper.add_scalp_position(symbol, signal)
                    logger.info(f"New scalp: {symbol} {signal['side']} at ${signal['entry_price']:.6f}")
            
            elif strategy_mode == StrategyMode.GRID_TRADING:
                # Setup grid if needed
                await self.grid_trader.setup_grid(symbol, market_data)
            
        except Exception as e:
            logger.error(f"Error executing strategy for {symbol}: {e}")
    
    async def _manage_positions(self, symbol: str, market_data: Dict[str, Any]):
        """Manage active positions for symbol"""
        try:
            current_price = float(market_data['klines'][-1]['close'])
            
            # Manage scalp positions
            scalp_result = await self.trend_scalper.manage_scalp_position(symbol, current_price)
            if scalp_result:
                self._record_profit(scalp_result)
            
            # Manage grid positions
            grid_results = await self.grid_trader.manage_grid_levels(symbol, current_price)
            for result in grid_results:
                self._record_profit(result)
            
        except Exception as e:
            logger.error(f"Error managing positions for {symbol}: {e}")
    
    def _record_profit(self, result: ProfitScrapResult):
        """Record profit result"""
        self.profit_history.append(result)
        self.total_trades += 1
        self.total_profits += result.profit_usd
        
        if result.profit_usd > 0:
            self.winning_trades += 1
        
        logger.info(f"💰 Profit scraped: {result.symbol} {result.strategy_type} "
                   f"${result.profit_usd:.2f} ({result.pnl_pct:.2%})")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current scraping status"""
        win_rate = self.winning_trades / max(1, self.total_trades)
        
        return {
            'running': self.running,
            'active_symbols': len(self.active_symbols),
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'win_rate': win_rate,
            'total_profits': self.total_profits,
            'avg_profit_per_trade': self.total_profits / max(1, self.total_trades),
            'active_scalps': len(self.trend_scalper.active_scalps),
            'active_grids': len(self.grid_trader.active_grids),
            'strategy_distribution': {
                mode.value: sum(1 for m in self.symbol_strategies.values() if m == mode)
                for mode in StrategyMode
            },
            'regime_distribution': {
                regime.value: sum(1 for r in self.symbol_regimes.values() if r == regime)
                for regime in MarketRegime
            }
        } 