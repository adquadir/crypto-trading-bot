"""
Adaptive Flow Manager - Switches between scalping and grid trading strategies
"""

import asyncio
import logging
import time
from typing import Dict, Optional, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class MarketRegime(Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_volatility"
    UNKNOWN = "unknown"

class StrategyType(Enum):
    SCALPING = "scalping"
    GRID_TRADING = "grid_trading"
    DISABLED = "disabled"

@dataclass
class StrategyState:
    """Current strategy state for a symbol"""
    symbol: str
    current_strategy: StrategyType
    regime: MarketRegime
    last_switch: float
    switch_count: int = 0
    performance_score: float = 0.0
    
class AdaptiveFlowManager:
    """Manages strategy switching between scalping and grid trading"""
    
    def __init__(self, grid_engine, scalping_manager, exchange_client, risk_manager):
        self.grid_engine = grid_engine
        self.scalping_manager = scalping_manager
        self.exchange_client = exchange_client
        self.risk_manager = risk_manager
        
        self.symbol_strategies = {}  # symbol -> StrategyState
        self.config = {
            'switch_cooldown_minutes': 15,  # Prevent strategy flapping
            'trend_threshold_adx': 25,      # ADX > 25 = trending
            'ranging_threshold_bb_width': 0.02,  # BB width < 2% = ranging
            'volatility_threshold_atr_pct': 3.0,  # ATR > 3% = high vol
            'min_performance_score': -5.0,  # Switch if performance drops
            'strategy_timeout_hours': 4     # Force re-evaluation
        }
        
        self.running = False
        
    async def analyze_and_switch_strategy(self, symbol: str, market_data: Dict) -> bool:
        """Determine and switch to optimal strategy based on market regime"""
        try:
            # Get current strategy state
            current_state = self.symbol_strategies.get(symbol)
            
            # Detect market regime
            regime = await self._detect_market_regime(symbol, market_data)
            
            # Determine optimal strategy
            optimal_strategy = self._get_optimal_strategy(regime, market_data)
            
            # Check if switch is needed
            if current_state is None:
                # First time setup
                switch_needed = True
                reason = "initial_setup"
            elif current_state.current_strategy != optimal_strategy:
                # Strategy change needed
                switch_needed = self._should_switch_strategy(current_state, optimal_strategy)
                reason = f"regime_change_{regime.value}"
            else:
                # Same strategy, just update regime
                current_state.regime = regime
                switch_needed = False
                reason = "no_change"
                
            if switch_needed:
                success = await self._execute_strategy_switch(
                    symbol, optimal_strategy, regime, reason, market_data
                )
                if success:
                    logger.info(f"✅ Strategy switched for {symbol}: {optimal_strategy.value} ({reason})")
                    return True
                else:
                    logger.error(f"❌ Failed to switch strategy for {symbol}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error analyzing strategy for {symbol}: {e}")
            return False
            
    async def _detect_market_regime(self, symbol: str, market_data: Dict) -> MarketRegime:
        """Detect current market regime using technical indicators"""
        try:
            indicators = market_data.get('indicators', {})
            klines = market_data.get('klines', [])
            
            if not klines or len(klines) < 20:
                return MarketRegime.UNKNOWN
                
            # Get current price info
            current_price = float(klines[-1]['close'])
            
            # ADX for trend strength
            adx = indicators.get('adx', 0)
            adx_plus = indicators.get('adx_plus', 0)
            adx_minus = indicators.get('adx_minus', 0)
            
            # Bollinger Bands for ranging detection
            bb_upper = indicators.get('bb_upper', current_price * 1.02)
            bb_lower = indicators.get('bb_lower', current_price * 0.98)
            bb_width = (bb_upper - bb_lower) / current_price
            
            # ATR for volatility
            atr = indicators.get('atr', current_price * 0.01)
            atr_pct = atr / current_price * 100
            
            # High volatility check first
            if atr_pct > self.config['volatility_threshold_atr_pct']:
                return MarketRegime.HIGH_VOLATILITY
                
            # Strong trend detection
            if adx > self.config['trend_threshold_adx']:
                if adx_plus > adx_minus:
                    return MarketRegime.TRENDING_UP
                else:
                    return MarketRegime.TRENDING_DOWN
                    
            # Ranging market detection
            if bb_width < self.config['ranging_threshold_bb_width']:
                return MarketRegime.RANGING
                
            # Default to unknown if unclear
            return MarketRegime.UNKNOWN
            
        except Exception as e:
            logger.error(f"Error detecting market regime: {e}")
            return MarketRegime.UNKNOWN
            
    def _get_optimal_strategy(self, regime: MarketRegime, market_data: Dict) -> StrategyType:
        """Determine optimal strategy based on market regime"""
        
        # Grid trading for ranging markets
        if regime == MarketRegime.RANGING:
            return StrategyType.GRID_TRADING
            
        # Scalping for trending markets
        elif regime in [MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN]:
            return StrategyType.SCALPING
            
        # High volatility - prefer scalping with tighter stops
        elif regime == MarketRegime.HIGH_VOLATILITY:
            return StrategyType.SCALPING
            
        # Unknown regime - default to scalping (more conservative)
        else:
            return StrategyType.SCALPING
            
    def _should_switch_strategy(self, current_state: StrategyState, new_strategy: StrategyType) -> bool:
        """Check if strategy switch should be executed"""
        
        # Cooldown period to prevent flapping
        time_since_switch = time.time() - current_state.last_switch
        if time_since_switch < self.config['switch_cooldown_minutes'] * 60:
            return False
            
        # Force switch if performance is poor
        if current_state.performance_score < self.config['min_performance_score']:
            return True
            
        # Force switch if strategy has been running too long
        if time_since_switch > self.config['strategy_timeout_hours'] * 3600:
            return True
            
        return True
        
    async def _execute_strategy_switch(self, symbol: str, new_strategy: StrategyType, 
                                     regime: MarketRegime, reason: str, market_data: Dict) -> bool:
        """Execute the actual strategy switch"""
        try:
            current_state = self.symbol_strategies.get(symbol)
            
            # Stop current strategy
            if current_state and current_state.current_strategy != StrategyType.DISABLED:
                await self._stop_current_strategy(symbol, current_state.current_strategy)
                
            # Start new strategy
            success = await self._start_new_strategy(symbol, new_strategy, market_data)
            
            if success:
                # Update strategy state
                new_state = StrategyState(
                    symbol=symbol,
                    current_strategy=new_strategy,
                    regime=regime,
                    last_switch=time.time(),
                    switch_count=(current_state.switch_count + 1) if current_state else 1
                )
                self.symbol_strategies[symbol] = new_state
                
                # Log strategy switch (for database)
                await self._log_strategy_switch(symbol, current_state, new_state, reason)
                
                return True
            else:
                logger.error(f"Failed to start {new_strategy.value} for {symbol}")
                return False
                
        except Exception as e:
            logger.error(f"Error executing strategy switch: {e}")
            return False
            
    async def _stop_current_strategy(self, symbol: str, strategy: StrategyType):
        """Stop the currently running strategy"""
        try:
            if strategy == StrategyType.GRID_TRADING:
                await self.grid_engine.stop_grid(symbol, "strategy_switch")
            elif strategy == StrategyType.SCALPING:
                # Stop scalping for this symbol (implementation depends on scalping manager)
                if hasattr(self.scalping_manager, 'stop_scalping'):
                    await self.scalping_manager.stop_scalping(symbol)
                    
        except Exception as e:
            logger.error(f"Error stopping {strategy.value} for {symbol}: {e}")
            
    async def _start_new_strategy(self, symbol: str, strategy: StrategyType, market_data: Dict) -> bool:
        """Start the new strategy"""
        try:
            if strategy == StrategyType.GRID_TRADING:
                return await self.grid_engine.start_grid(symbol, market_data)
            elif strategy == StrategyType.SCALPING:
                # Start scalping for this symbol
                if hasattr(self.scalping_manager, 'start_scalping'):
                    return await self.scalping_manager.start_scalping(symbol, market_data)
                else:
                    # Scalping is handled by signal generation, just return True
                    return True
            else:
                return True  # DISABLED strategy
                
        except Exception as e:
            logger.error(f"Error starting {strategy.value} for {symbol}: {e}")
            return False
            
    async def _log_strategy_switch(self, symbol: str, old_state: Optional[StrategyState], 
                                 new_state: StrategyState, reason: str):
        """Log strategy switch to database"""
        try:
            # This would integrate with database logging
            switch_data = {
                'symbol': symbol,
                'from_strategy': old_state.current_strategy.value if old_state else 'none',
                'to_strategy': new_state.current_strategy.value,
                'reason': reason,
                'market_regime': new_state.regime.value,
                'timestamp': time.time()
            }
            
            logger.info(f"Strategy switch logged: {switch_data}")
            # TODO: Add database integration
            
        except Exception as e:
            logger.error(f"Error logging strategy switch: {e}")
            
    async def manage_strategy_transitions(self):
        """Continuous monitoring and strategy management"""
        while self.running:
            try:
                # Get active symbols
                active_symbols = list(self.symbol_strategies.keys())
                
                for symbol in active_symbols:
                    try:
                        # Get fresh market data
                        market_data = await self._get_market_data(symbol)
                        if market_data:
                            await self.analyze_and_switch_strategy(symbol, market_data)
                            
                    except Exception as e:
                        logger.error(f"Error managing strategy for {symbol}: {e}")
                        
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error in strategy transition management: {e}")
                await asyncio.sleep(60)
                
    async def _get_market_data(self, symbol: str) -> Optional[Dict]:
        """Get current market data for analysis"""
        try:
            # This would integrate with existing market data sources
            # For now, return mock data structure
            return {
                'symbol': symbol,
                'klines': [],  # Would be populated with real data
                'indicators': {}  # Would be populated with indicators
            }
            
        except Exception as e:
            logger.error(f"Error getting market data for {symbol}: {e}")
            return None
            
    def get_strategy_status(self, symbol: str) -> Optional[Dict]:
        """Get current strategy status for a symbol"""
        state = self.symbol_strategies.get(symbol)
        if not state:
            return None
            
        return {
            'symbol': symbol,
            'current_strategy': state.current_strategy.value,
            'market_regime': state.regime.value,
            'last_switch': state.last_switch,
            'switch_count': state.switch_count,
            'performance_score': state.performance_score,
            'uptime_minutes': (time.time() - state.last_switch) / 60
        }
        
    def get_all_strategies_status(self) -> List[Dict]:
        """Get status of all managed strategies"""
        return [self.get_strategy_status(symbol) for symbol in self.symbol_strategies.keys()]
        
    async def start_management(self):
        """Start strategy management"""
        self.running = True
        await self.manage_strategy_transitions()
        
    def stop_management(self):
        """Stop strategy management"""
        self.running = False
        
    async def add_symbol(self, symbol: str, market_data: Dict):
        """Add a new symbol to flow trading management"""
        await self.analyze_and_switch_strategy(symbol, market_data)
        
    async def remove_symbol(self, symbol: str):
        """Remove a symbol from flow trading management"""
        if symbol in self.symbol_strategies:
            state = self.symbol_strategies[symbol]
            await self._stop_current_strategy(symbol, state.current_strategy)
            del self.symbol_strategies[symbol]
            logger.info(f"Removed {symbol} from flow trading management") 