"""
Multi-timeframe analysis for improved signal accuracy.
Requires confirmation across multiple timeframes before generating signals.
"""

import logging
from typing import Dict, List, Optional, Tuple
import numpy as np
from datetime import datetime, timedelta
import asyncio

logger = logging.getLogger(__name__)

class MultiTimeframeAnalyzer:
    """Analyzes signals across multiple timeframes for confirmation."""
    
    def __init__(self, exchange_client):
        self.exchange_client = exchange_client
        self.timeframes = ['5m', '15m', '1h']  # Primary timeframes
        self.confirmation_threshold = 0.7  # 70% of timeframes must agree
        self.cache = {}  # Cache for historical data
        self.cache_expiry = 300  # 5 minutes
        
    async def analyze_multi_timeframe_signal(
        self, 
        symbol: str, 
        primary_signal: Dict,
        signal_generator
    ) -> Dict:
        """
        Analyze signal across multiple timeframes for confirmation.
        
        Args:
            symbol: Trading symbol
            primary_signal: Signal from primary timeframe
            signal_generator: Signal generator instance
            
        Returns:
            Enhanced signal with MTF confirmation data
        """
        try:
            if not primary_signal or primary_signal.get('signal_type') == 'NEUTRAL':
                return primary_signal
                
            logger.info(f"Analyzing MTF signal for {symbol}")
            
            # Get data for all timeframes
            mtf_data = await self._get_multi_timeframe_data(symbol)
            
            if not mtf_data:
                logger.warning(f"No MTF data available for {symbol}")
                return primary_signal
                
            # Analyze each timeframe
            timeframe_signals = {}
            timeframe_scores = {}
            
            for timeframe, data in mtf_data.items():
                if not data:
                    continue
                    
                try:
                    # Generate signal for this timeframe
                    tf_signal = await asyncio.to_thread(
                        signal_generator.generate_signal, data
                    )
                    
                    if tf_signal:
                        timeframe_signals[timeframe] = tf_signal
                        timeframe_scores[timeframe] = self._calculate_timeframe_score(
                            tf_signal, primary_signal
                        )
                        
                except Exception as e:
                    logger.debug(f"Error analyzing {timeframe} for {symbol}: {e}")
                    continue
                    
            # Calculate MTF confirmation
            mtf_confirmation = self._calculate_mtf_confirmation(
                primary_signal, timeframe_signals, timeframe_scores
            )
            
            # Enhance primary signal with MTF data
            enhanced_signal = primary_signal.copy()
            enhanced_signal.update({
                'mtf_confirmation': mtf_confirmation,
                'timeframe_signals': timeframe_signals,
                'mtf_score': mtf_confirmation.get('score', 0),
                'mtf_strength': mtf_confirmation.get('strength', 0),
                'confirmed_timeframes': mtf_confirmation.get('confirmed_timeframes', [])
            })
            
            # Adjust confidence based on MTF confirmation
            original_confidence = enhanced_signal.get('confidence', 0.5)
            mtf_boost = mtf_confirmation.get('score', 0) * 0.3  # Up to 30% boost
            enhanced_signal['confidence'] = min(1.0, original_confidence + mtf_boost)
            
            logger.info(f"MTF analysis complete for {symbol}: "
                       f"Score {mtf_confirmation.get('score', 0):.2f}, "
                       f"Confirmed TFs: {len(mtf_confirmation.get('confirmed_timeframes', []))}")
            
            return enhanced_signal
            
        except Exception as e:
            logger.error(f"Error in MTF analysis for {symbol}: {e}")
            return primary_signal
            
    async def _get_multi_timeframe_data(self, symbol: str) -> Dict:
        """Get market data for all timeframes."""
        mtf_data = {}
        
        for timeframe in self.timeframes:
            try:
                # Check cache first
                cache_key = f"{symbol}_{timeframe}"
                if self._is_cache_valid(cache_key):
                    mtf_data[timeframe] = self.cache[cache_key]['data']
                    continue
                    
                # Get historical data for this timeframe
                historical_data = await self.exchange_client.get_historical_data(
                    symbol=symbol,
                    interval=timeframe,
                    limit=100
                )
                
                if historical_data:
                    # Format data for signal generator
                    market_data = {
                        'symbol': symbol,
                        'klines': historical_data,
                        'current_price': float(historical_data[-1]['close']),
                        'volume_24h': sum(float(k['volume']) for k in historical_data[-24:]),
                        'timestamp': historical_data[-1]['openTime'],
                        'timeframe': timeframe
                    }
                    
                    mtf_data[timeframe] = market_data
                    
                    # Cache the data
                    self.cache[cache_key] = {
                        'data': market_data,
                        'timestamp': datetime.now()
                    }
                    
            except Exception as e:
                logger.debug(f"Error getting {timeframe} data for {symbol}: {e}")
                continue
                
        return mtf_data
        
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached data is still valid."""
        if cache_key not in self.cache:
            return False
            
        cache_time = self.cache[cache_key]['timestamp']
        return (datetime.now() - cache_time).seconds < self.cache_expiry
        
    def _calculate_timeframe_score(
        self, 
        tf_signal: Dict, 
        primary_signal: Dict
    ) -> float:
        """Calculate how well a timeframe signal aligns with primary signal."""
        try:
            # Check direction alignment
            tf_direction = tf_signal.get('direction', 'NEUTRAL')
            primary_direction = primary_signal.get('direction', 'NEUTRAL')
            
            if tf_direction == 'NEUTRAL' or primary_direction == 'NEUTRAL':
                return 0.0
                
            if tf_direction != primary_direction:
                return 0.0  # Opposite direction = no confirmation
                
            # Base score for same direction
            score = 0.5
            
            # Add score based on signal strength
            tf_confidence = tf_signal.get('confidence', 0)
            primary_confidence = primary_signal.get('confidence', 0)
            
            # Higher confidence in confirming timeframe = higher score
            score += tf_confidence * 0.3
            
            # Similar confidence levels = better alignment
            confidence_similarity = 1 - abs(tf_confidence - primary_confidence)
            score += confidence_similarity * 0.2
            
            return min(1.0, score)
            
        except Exception as e:
            logger.debug(f"Error calculating timeframe score: {e}")
            return 0.0
            
    def _calculate_mtf_confirmation(
        self, 
        primary_signal: Dict, 
        timeframe_signals: Dict, 
        timeframe_scores: Dict
    ) -> Dict:
        """Calculate overall multi-timeframe confirmation."""
        try:
            if not timeframe_signals:
                return {
                    'score': 0.0,
                    'strength': 0.0,
                    'confirmed_timeframes': [],
                    'conflicting_timeframes': [],
                    'neutral_timeframes': []
                }
                
            primary_direction = primary_signal.get('direction', 'NEUTRAL')
            
            confirmed_timeframes = []
            conflicting_timeframes = []
            neutral_timeframes = []
            
            total_score = 0.0
            max_possible_score = 0.0
            
            for timeframe, tf_signal in timeframe_signals.items():
                tf_direction = tf_signal.get('direction', 'NEUTRAL')
                tf_score = timeframe_scores.get(timeframe, 0)
                
                # Weight timeframes differently (longer timeframes = more weight)
                timeframe_weight = self._get_timeframe_weight(timeframe)
                max_possible_score += timeframe_weight
                
                if tf_direction == primary_direction:
                    confirmed_timeframes.append(timeframe)
                    total_score += tf_score * timeframe_weight
                elif tf_direction == 'NEUTRAL':
                    neutral_timeframes.append(timeframe)
                    # Neutral doesn't add or subtract, but reduces max possible
                else:
                    conflicting_timeframes.append(timeframe)
                    # Conflicting timeframes subtract from score
                    total_score -= 0.2 * timeframe_weight
                    
            # Calculate final scores
            overall_score = total_score / max_possible_score if max_possible_score > 0 else 0
            overall_score = max(0.0, min(1.0, overall_score))  # Clamp to [0,1]
            
            # Calculate strength (percentage of timeframes confirming)
            total_timeframes = len(timeframe_signals)
            confirmed_ratio = len(confirmed_timeframes) / total_timeframes if total_timeframes > 0 else 0
            
            # Strength considers both confirmation ratio and signal quality
            strength = (confirmed_ratio * 0.7) + (overall_score * 0.3)
            
            return {
                'score': overall_score,
                'strength': strength,
                'confirmed_timeframes': confirmed_timeframes,
                'conflicting_timeframes': conflicting_timeframes,
                'neutral_timeframes': neutral_timeframes,
                'confirmation_ratio': confirmed_ratio,
                'total_timeframes_analyzed': total_timeframes
            }
            
        except Exception as e:
            logger.error(f"Error calculating MTF confirmation: {e}")
            return {
                'score': 0.0,
                'strength': 0.0,
                'confirmed_timeframes': [],
                'conflicting_timeframes': [],
                'neutral_timeframes': []
            }
            
    def _get_timeframe_weight(self, timeframe: str) -> float:
        """Get weight for different timeframes (longer = more important)."""
        weights = {
            '1m': 0.5,
            '3m': 0.6,
            '5m': 0.7,
            '15m': 1.0,  # Base weight
            '30m': 1.2,
            '1h': 1.5,
            '2h': 1.7,
            '4h': 2.0,
            '1d': 2.5
        }
        return weights.get(timeframe, 1.0)
        
    def should_trade_signal(self, enhanced_signal: Dict) -> bool:
        """Determine if signal has sufficient MTF confirmation to trade."""
        try:
            mtf_confirmation = enhanced_signal.get('mtf_confirmation', {})
            
            # Require minimum confirmation score
            min_score = 0.6
            if mtf_confirmation.get('score', 0) < min_score:
                return False
                
            # Require minimum confirmation ratio
            min_ratio = 0.5  # At least 50% of timeframes must confirm
            if mtf_confirmation.get('confirmation_ratio', 0) < min_ratio:
                return False
                
            # Check for too many conflicting signals
            conflicting = len(mtf_confirmation.get('conflicting_timeframes', []))
            total = mtf_confirmation.get('total_timeframes_analyzed', 1)
            
            if conflicting / total > 0.3:  # More than 30% conflicting
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error checking trade signal: {e}")
            return False
            
    def get_mtf_summary(self, enhanced_signal: Dict) -> str:
        """Get human-readable summary of MTF analysis."""
        try:
            mtf_confirmation = enhanced_signal.get('mtf_confirmation', {})
            
            if not mtf_confirmation:
                return "No MTF analysis available"
                
            confirmed = mtf_confirmation.get('confirmed_timeframes', [])
            conflicting = mtf_confirmation.get('conflicting_timeframes', [])
            neutral = mtf_confirmation.get('neutral_timeframes', [])
            score = mtf_confirmation.get('score', 0)
            strength = mtf_confirmation.get('strength', 0)
            
            summary_parts = [
                f"MTF Score: {score:.2f}",
                f"Strength: {strength:.2f}",
                f"Confirmed: {', '.join(confirmed) if confirmed else 'None'}",
            ]
            
            if conflicting:
                summary_parts.append(f"Conflicting: {', '.join(conflicting)}")
                
            if neutral:
                summary_parts.append(f"Neutral: {', '.join(neutral)}")
                
            return " | ".join(summary_parts)
            
        except Exception as e:
            logger.error(f"Error creating MTF summary: {e}")
            return "MTF analysis error" 