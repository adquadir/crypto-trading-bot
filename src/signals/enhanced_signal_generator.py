"""
Enhanced signal generator with multi-timeframe confirmation,
market regime filtering, and optimized parameters.
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import asyncio

from .signal_generator import SignalGenerator
from .multi_timeframe import MultiTimeframeAnalyzer
from ..strategy.dynamic_config import StrategyConfig

logger = logging.getLogger(__name__)

class EnhancedSignalGenerator(SignalGenerator):
    """Enhanced signal generator with improved accuracy features."""
    
    def __init__(self, strategy_config: StrategyConfig, exchange_client):
        super().__init__(strategy_config)
        self.exchange_client = exchange_client
        self.mtf_analyzer = MultiTimeframeAnalyzer(exchange_client)
        
        # Enhanced parameters
        self.min_mtf_score = 0.6  # Minimum MTF confirmation score
        self.min_volume_ratio = 1.5  # Minimum volume vs average
        self.max_spread_pct = 0.5  # Maximum spread percentage
        
        # Market regime filters
        self.regime_filters = {
            'trending': {
                'min_adx': 25,
                'strategies': ['macd', 'momentum']
            },
            'ranging': {
                'max_adx': 20,
                'strategies': ['bollinger', 'rsi', 'candle_cluster']
            },
            'volatile': {
                'min_atr_pct': 3.0,
                'strategies': ['bollinger', 'momentum']
            }
        }
        
        # Performance tracking
        self.signal_performance = {}
        self.regime_performance = {}
        
    async def generate_enhanced_signal(self, market_data: Dict) -> Optional[Dict]:
        """Generate enhanced signal with MTF confirmation and regime filtering."""
        try:
            symbol = market_data.get('symbol', 'UNKNOWN')
            logger.debug(f"Generating enhanced signal for {symbol}")
            
            # Step 1: Generate base signal
            base_signal = await asyncio.to_thread(
                super().generate_signal, market_data
            )
            
            if not base_signal or base_signal.get('signal_type') == 'NEUTRAL':
                return base_signal
                
            logger.debug(f"Base signal generated for {symbol}: {base_signal.get('direction')}")
            
            # Step 2: Market regime analysis
            regime_data = self._enhanced_regime_analysis(market_data)
            current_regime = regime_data.get('regime', 'unknown')
            
            # Step 3: Check if strategy is suitable for current regime
            if not self._is_strategy_suitable_for_regime(base_signal, current_regime):
                logger.debug(f"Strategy not suitable for {current_regime} regime")
                return None
                
            # Step 4: Enhanced market condition checks
            if not self._check_enhanced_market_conditions(market_data, base_signal):
                logger.debug(f"Enhanced market conditions not met for {symbol}")
                return None
                
            # Step 5: Multi-timeframe confirmation
            enhanced_signal = await self.mtf_analyzer.analyze_multi_timeframe_signal(
                symbol, base_signal, self
            )
            
            # Step 6: Check MTF confirmation threshold
            if not self.mtf_analyzer.should_trade_signal(enhanced_signal):
                logger.debug(f"Insufficient MTF confirmation for {symbol}")
                return None
                
            # Step 7: Add regime and enhancement data
            enhanced_signal.update({
                'regime': current_regime,
                'regime_data': regime_data,
                'enhancement_version': '2.0',
                'mtf_summary': self.mtf_analyzer.get_mtf_summary(enhanced_signal)
            })
            
            # Step 8: Final confidence adjustment
            enhanced_signal = self._adjust_final_confidence(enhanced_signal, regime_data)
            
            logger.info(f"Enhanced signal generated for {symbol}: "
                       f"{enhanced_signal.get('direction')} "
                       f"(Confidence: {enhanced_signal.get('confidence', 0):.2f}, "
                       f"MTF Score: {enhanced_signal.get('mtf_score', 0):.2f})")
            
            return enhanced_signal
            
        except Exception as e:
            logger.error(f"Error generating enhanced signal: {e}")
            return base_signal if 'base_signal' in locals() else None
            
    def _enhanced_regime_analysis(self, market_data: Dict) -> Dict:
        """Enhanced market regime analysis with more indicators."""
        try:
            indicators = self._calculate_indicators(market_data)
            
            # Get base regime
            base_regime_data = self._determine_market_regime(market_data)
            
            # Enhanced regime scoring
            regime_scores = {
                'trending': 0.0,
                'ranging': 0.0,
                'volatile': 0.0
            }
            
            # ADX analysis (trend strength)
            adx = indicators.get('adx', 0)
            if adx > 30:
                regime_scores['trending'] += 0.4
            elif adx > 20:
                regime_scores['trending'] += 0.2
            elif adx < 15:
                regime_scores['ranging'] += 0.3
                
            # Bollinger Band width (volatility)
            bb_width_pct = self._calculate_bb_width_percent(indicators)
            if bb_width_pct > 4.0:
                regime_scores['volatile'] += 0.4
            elif bb_width_pct < 1.5:
                regime_scores['ranging'] += 0.3
                
            # ATR analysis (volatility)
            atr_pct = self._calculate_atr_percent(market_data, indicators)
            if atr_pct > 3.0:
                regime_scores['volatile'] += 0.3
            elif atr_pct < 1.0:
                regime_scores['ranging'] += 0.2
                
            # Volume analysis
            volume_ratio = self._calculate_volume_ratio(market_data)
            if volume_ratio > 2.0:
                regime_scores['volatile'] += 0.2
                regime_scores['trending'] += 0.1
            elif volume_ratio < 0.7:
                regime_scores['ranging'] += 0.2
                
            # Price momentum
            momentum_score = self._calculate_momentum_score(indicators)
            if abs(momentum_score) > 0.7:
                regime_scores['trending'] += 0.3
            elif abs(momentum_score) < 0.3:
                regime_scores['ranging'] += 0.2
                
            # Determine dominant regime
            dominant_regime = max(regime_scores.items(), key=lambda x: x[1])
            
            return {
                'regime': dominant_regime[0],
                'regime_score': dominant_regime[1],
                'regime_scores': regime_scores,
                'adx': adx,
                'bb_width_pct': bb_width_pct,
                'atr_pct': atr_pct,
                'volume_ratio': volume_ratio,
                'momentum_score': momentum_score,
                'confidence': dominant_regime[1]
            }
            
        except Exception as e:
            logger.error(f"Error in enhanced regime analysis: {e}")
            return {'regime': 'unknown', 'confidence': 0.0}
            
    def _calculate_bb_width_percent(self, indicators: Dict) -> float:
        """Calculate Bollinger Band width as percentage of price."""
        try:
            bb_upper = indicators.get('bb_upper', 0)
            bb_lower = indicators.get('bb_lower', 0)
            bb_middle = indicators.get('bb_middle', 1)
            
            if bb_middle > 0:
                return ((bb_upper - bb_lower) / bb_middle) * 100
            return 0.0
            
        except Exception:
            return 0.0
            
    def _calculate_atr_percent(self, market_data: Dict, indicators: Dict) -> float:
        """Calculate ATR as percentage of current price."""
        try:
            atr = indicators.get('atr', 0)
            current_price = market_data.get('current_price', 1)
            
            return (atr / current_price) * 100 if current_price > 0 else 0.0
            
        except Exception:
            return 0.0
            
    def _calculate_volume_ratio(self, market_data: Dict) -> float:
        """Calculate current volume ratio vs average."""
        try:
            klines = market_data.get('klines', [])
            if len(klines) < 20:
                return 1.0
                
            # Current volume
            current_volume = float(klines[-1].get('volume', 0))
            
            # Average volume (last 20 periods)
            volumes = [float(k.get('volume', 0)) for k in klines[-20:]]
            avg_volume = np.mean(volumes) if volumes else 1
            
            return current_volume / avg_volume if avg_volume > 0 else 1.0
            
        except Exception:
            return 1.0
            
    def _calculate_momentum_score(self, indicators: Dict) -> float:
        """Calculate overall momentum score."""
        try:
            # RSI momentum
            rsi = indicators.get('rsi', 50)
            rsi_momentum = (rsi - 50) / 50  # Normalize to [-1, 1]
            
            # MACD momentum
            macd = indicators.get('macd', 0)
            macd_signal = indicators.get('macd_signal', 0)
            macd_momentum = np.tanh((macd - macd_signal) * 10)  # Normalize
            
            # Combine momentums
            momentum_score = (rsi_momentum * 0.6) + (macd_momentum * 0.4)
            
            return np.clip(momentum_score, -1, 1)
            
        except Exception:
            return 0.0
            
    def _is_strategy_suitable_for_regime(self, signal: Dict, regime: str) -> bool:
        """Check if strategy is suitable for current market regime."""
        try:
            strategy_type = signal.get('strategy_type', 'unknown')
            
            if regime not in self.regime_filters:
                return True  # Allow if regime unknown
                
            suitable_strategies = self.regime_filters[regime].get('strategies', [])
            
            # Map signal types to strategy names
            strategy_mapping = {
                'MACD': 'macd',
                'RSI': 'rsi',
                'BOLLINGER': 'bollinger',
                'MOMENTUM': 'momentum',
                'CANDLE_CLUSTER': 'candle_cluster'
            }
            
            mapped_strategy = strategy_mapping.get(strategy_type, strategy_type.lower())
            
            return mapped_strategy in suitable_strategies
            
        except Exception as e:
            logger.debug(f"Error checking strategy suitability: {e}")
            return True
            
    def _check_enhanced_market_conditions(self, market_data: Dict, signal: Dict) -> bool:
        """Enhanced market condition checks."""
        try:
            # Volume check
            volume_ratio = self._calculate_volume_ratio(market_data)
            if volume_ratio < self.min_volume_ratio:
                logger.debug(f"Volume too low: {volume_ratio:.2f} < {self.min_volume_ratio}")
                return False
                
            # Spread check (if available)
            spread_pct = market_data.get('spread_pct', 0)
            if spread_pct > self.max_spread_pct:
                logger.debug(f"Spread too high: {spread_pct:.2f}% > {self.max_spread_pct}%")
                return False
                
            # Liquidity check
            if not self._check_liquidity(market_data):
                logger.debug("Insufficient liquidity")
                return False
                
            # Time-based filters
            if not self._check_time_filters():
                logger.debug("Time filters not met")
                return False
                
            return True
            
        except Exception as e:
            logger.debug(f"Error in enhanced market condition checks: {e}")
            return True
            
    def _check_liquidity(self, market_data: Dict) -> bool:
        """Check market liquidity conditions."""
        try:
            # Check 24h volume
            volume_24h = market_data.get('volume_24h', 0)
            min_volume_24h = 1000000  # $1M minimum
            
            if volume_24h < min_volume_24h:
                return False
                
            # Check recent volume consistency
            klines = market_data.get('klines', [])
            if len(klines) < 10:
                return True  # Not enough data to check
                
            recent_volumes = [float(k.get('volume', 0)) for k in klines[-10:]]
            volume_std = np.std(recent_volumes)
            volume_mean = np.mean(recent_volumes)
            
            # Check for volume consistency (CV < 2.0)
            if volume_mean > 0:
                cv = volume_std / volume_mean
                return cv < 2.0
                
            return True
            
        except Exception:
            return True
            
    def _check_time_filters(self) -> bool:
        """Check time-based trading filters."""
        try:
            now = datetime.now()
            hour = now.hour
            
            # Avoid low-liquidity hours (typically 2-6 AM UTC)
            if 2 <= hour <= 6:
                return False
                
            # Avoid weekends for some assets
            weekday = now.weekday()
            if weekday >= 5:  # Saturday = 5, Sunday = 6
                return False
                
            return True
            
        except Exception:
            return True
            
    def _adjust_final_confidence(self, signal: Dict, regime_data: Dict) -> Dict:
        """Adjust final confidence based on all factors."""
        try:
            base_confidence = signal.get('confidence', 0.5)
            
            # MTF boost (already applied)
            mtf_score = signal.get('mtf_score', 0)
            
            # Regime confidence boost
            regime_confidence = regime_data.get('confidence', 0)
            regime_boost = regime_confidence * 0.15  # Up to 15% boost
            
            # Volume boost
            volume_ratio = regime_data.get('volume_ratio', 1.0)
            volume_boost = min(0.1, (volume_ratio - 1.0) * 0.05)  # Up to 10% boost
            
            # ADX boost for trending signals
            adx = regime_data.get('adx', 0)
            adx_boost = 0
            if signal.get('direction') in ['LONG', 'SHORT'] and adx > 25:
                adx_boost = min(0.1, (adx - 25) * 0.002)  # Up to 10% boost
                
            # Calculate final confidence
            final_confidence = base_confidence + regime_boost + volume_boost + adx_boost
            final_confidence = min(1.0, max(0.0, final_confidence))
            
            signal['confidence'] = final_confidence
            signal['confidence_breakdown'] = {
                'base': base_confidence,
                'mtf_boost': signal.get('confidence', base_confidence) - base_confidence,
                'regime_boost': regime_boost,
                'volume_boost': volume_boost,
                'adx_boost': adx_boost,
                'final': final_confidence
            }
            
            return signal
            
        except Exception as e:
            logger.error(f"Error adjusting final confidence: {e}")
            return signal
            
    def update_signal_performance(self, signal: Dict, outcome: Dict):
        """Update signal performance tracking."""
        try:
            strategy_type = signal.get('strategy_type', 'unknown')
            regime = signal.get('regime', 'unknown')
            mtf_score = signal.get('mtf_score', 0)
            
            # Update strategy performance
            if strategy_type not in self.signal_performance:
                self.signal_performance[strategy_type] = {
                    'total': 0, 'wins': 0, 'losses': 0,
                    'total_pnl': 0.0, 'win_rate': 0.0
                }
                
            perf = self.signal_performance[strategy_type]
            perf['total'] += 1
            perf['total_pnl'] += outcome.get('pnl', 0)
            
            if outcome.get('outcome') == 'win':
                perf['wins'] += 1
            else:
                perf['losses'] += 1
                
            perf['win_rate'] = perf['wins'] / perf['total']
            
            # Update regime performance
            if regime not in self.regime_performance:
                self.regime_performance[regime] = {
                    'total': 0, 'wins': 0, 'win_rate': 0.0
                }
                
            regime_perf = self.regime_performance[regime]
            regime_perf['total'] += 1
            if outcome.get('outcome') == 'win':
                regime_perf['wins'] += 1
            regime_perf['win_rate'] = regime_perf['wins'] / regime_perf['total']
            
            logger.info(f"Updated performance - {strategy_type}: {perf['win_rate']:.2%}, "
                       f"{regime}: {regime_perf['win_rate']:.2%}")
            
        except Exception as e:
            logger.error(f"Error updating signal performance: {e}")
            
    def get_performance_summary(self) -> Dict:
        """Get performance summary for all strategies and regimes."""
        return {
            'strategy_performance': self.signal_performance,
            'regime_performance': self.regime_performance,
            'total_signals': sum(p['total'] for p in self.signal_performance.values()),
            'overall_win_rate': (
                sum(p['wins'] for p in self.signal_performance.values()) /
                max(1, sum(p['total'] for p in self.signal_performance.values()))
            )
        } 