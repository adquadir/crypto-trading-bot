"""
Magnet Level Detector
Identifies psychological and liquidity magnet levels that attract price
"""

import numpy as np
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime
import logging
import math

from .price_level_analyzer import PriceLevel

logger = logging.getLogger(__name__)

@dataclass
class MagnetLevel:
    """Represents a psychological/liquidity magnet level"""
    price: float
    magnet_type: str  # 'round_number', 'fibonacci', 'previous_high', 'previous_low', 'psychological'
    strength: int  # 0-100 magnet strength
    attraction_radius: float  # Price range where magnet effect is strong
    historical_reactions: int  # Number of times price reacted to this level
    last_reaction: Optional[datetime]
    
    def to_dict(self) -> Dict:
        return {
            'price': self.price,
            'magnet_type': self.magnet_type,
            'strength': self.strength,
            'attraction_radius': self.attraction_radius,
            'historical_reactions': self.historical_reactions,
            'last_reaction': self.last_reaction.isoformat() if self.last_reaction else None
        }

class MagnetLevelDetector:
    """Detects psychological and liquidity magnet levels"""
    
    def __init__(self):
        self.round_number_weights = {
            1000: 100,   # Major round numbers (1000, 2000, etc.)
            500: 80,     # Half-thousands
            100: 60,     # Hundreds
            50: 40,      # Half-hundreds
            10: 20       # Tens
        }
        
    def detect_magnet_levels(self, symbol: str, current_price: float, 
                           price_levels: List[PriceLevel], 
                           historical_data=None) -> List[MagnetLevel]:
        """Detect all types of magnet levels for a symbol"""
        try:
            logger.info(f"🧲 Detecting magnet levels for {symbol} at ${current_price:.2f}")
            
            magnet_levels = []
            
            # Detect round number magnets
            round_magnets = self._detect_round_number_magnets(current_price)
            magnet_levels.extend(round_magnets)
            
            # Detect Fibonacci magnets
            fib_magnets = self._detect_fibonacci_magnets(current_price, historical_data)
            magnet_levels.extend(fib_magnets)
            
            # Detect previous high/low magnets
            if historical_data is not None:
                hl_magnets = self._detect_high_low_magnets(historical_data)
                magnet_levels.extend(hl_magnets)
            
            # Detect psychological level magnets
            psych_magnets = self._detect_psychological_magnets(current_price)
            magnet_levels.extend(psych_magnets)
            
            # Enhance with historical reaction data
            enhanced_magnets = self._enhance_with_historical_data(magnet_levels, price_levels)
            
            # Filter and rank by strength
            strong_magnets = [m for m in enhanced_magnets if m.strength >= 40]
            strong_magnets.sort(key=lambda x: x.strength, reverse=True)
            
            logger.info(f"✅ Found {len(strong_magnets)} strong magnet levels for {symbol}")
            return strong_magnets
            
        except Exception as e:
            logger.error(f"Error detecting magnet levels for {symbol}: {e}")
            return []
    
    def _detect_round_number_magnets(self, current_price: float) -> List[MagnetLevel]:
        """Detect round number magnet levels"""
        try:
            magnets = []
            price_range = current_price * 0.15  # Look within 15% of current price
            
            # Determine appropriate round number intervals based on price
            if current_price >= 10000:
                intervals = [1000, 500, 100]
            elif current_price >= 1000:
                intervals = [100, 50, 10]
            elif current_price >= 100:
                intervals = [10, 5, 1]
            else:
                intervals = [1, 0.5, 0.1]
            
            for interval in intervals:
                # Find round numbers above and below current price
                lower_bound = current_price - price_range
                upper_bound = current_price + price_range
                
                # Calculate round numbers in range
                start_multiple = math.floor(lower_bound / interval)
                end_multiple = math.ceil(upper_bound / interval)
                
                for multiple in range(start_multiple, end_multiple + 1):
                    round_price = multiple * interval
                    
                    if lower_bound <= round_price <= upper_bound and round_price > 0:
                        # Calculate strength based on interval significance
                        base_strength = self.round_number_weights.get(interval, 10)
                        
                        # Boost strength for "prettier" numbers
                        if multiple % 10 == 0:  # Multiples of 10 intervals
                            base_strength += 20
                        elif multiple % 5 == 0:  # Multiples of 5 intervals
                            base_strength += 10
                        
                        # Reduce strength based on distance from current price
                        distance_factor = 1 - (abs(round_price - current_price) / price_range)
                        strength = int(base_strength * distance_factor)
                        
                        magnet = MagnetLevel(
                            price=round_price,
                            magnet_type='round_number',
                            strength=min(strength, 100),
                            attraction_radius=round_price * 0.005,  # 0.5% radius
                            historical_reactions=0,
                            last_reaction=None
                        )
                        magnets.append(magnet)
            
            return magnets
            
        except Exception as e:
            logger.error(f"Error detecting round number magnets: {e}")
            return []
    
    def _detect_fibonacci_magnets(self, current_price: float, historical_data) -> List[MagnetLevel]:
        """Detect Fibonacci retracement/extension magnet levels"""
        try:
            magnets = []
            
            if historical_data is None or len(historical_data) < 50:
                return magnets
            
            # Find recent significant high and low
            recent_data = historical_data.tail(100)  # Last 100 periods
            recent_high = recent_data['high'].max()
            recent_low = recent_data['low'].min()
            
            # Calculate Fibonacci levels
            fib_ratios = [0.236, 0.382, 0.5, 0.618, 0.786, 1.0, 1.272, 1.618]
            price_range = recent_high - recent_low
            
            for ratio in fib_ratios:
                # Retracement levels (from high)
                fib_price_ret = recent_high - (price_range * ratio)
                
                # Extension levels (from low)
                fib_price_ext = recent_low + (price_range * ratio)
                
                # Check if levels are near current price (within 10%)
                for fib_price in [fib_price_ret, fib_price_ext]:
                    if fib_price > 0:
                        distance = abs(fib_price - current_price) / current_price
                        if distance <= 0.10:  # Within 10%
                            # Calculate strength based on Fibonacci ratio importance
                            if ratio in [0.382, 0.618]:  # Golden ratio levels
                                base_strength = 80
                            elif ratio in [0.5, 1.0]:  # 50% and 100% levels
                                base_strength = 70
                            elif ratio in [0.236, 0.786]:  # Other important levels
                                base_strength = 60
                            else:
                                base_strength = 50
                            
                            # Adjust for distance
                            distance_factor = 1 - (distance / 0.10)
                            strength = int(base_strength * distance_factor)
                            
                            magnet = MagnetLevel(
                                price=fib_price,
                                magnet_type='fibonacci',
                                strength=strength,
                                attraction_radius=fib_price * 0.008,  # 0.8% radius
                                historical_reactions=0,
                                last_reaction=None
                            )
                            magnets.append(magnet)
            
            return magnets
            
        except Exception as e:
            logger.error(f"Error detecting Fibonacci magnets: {e}")
            return []
    
    def _detect_high_low_magnets(self, historical_data) -> List[MagnetLevel]:
        """Detect previous significant high/low magnet levels"""
        try:
            magnets = []
            
            if historical_data is None or len(historical_data) < 20:
                return magnets
            
            # Find significant highs and lows from different timeframes
            timeframes = [
                ('daily_high', 24),    # Daily high (last 24 hours)
                ('weekly_high', 168),  # Weekly high (last 7 days)
                ('monthly_high', 720), # Monthly high (last 30 days)
            ]
            
            current_price = historical_data['close'].iloc[-1]
            
            for tf_name, periods in timeframes:
                if len(historical_data) >= periods:
                    tf_data = historical_data.tail(periods)
                    
                    # Find highest high and lowest low
                    period_high = tf_data['high'].max()
                    period_low = tf_data['low'].min()
                    
                    # Check if these levels are significant (not current price)
                    for level_price, level_type in [(period_high, 'previous_high'), (period_low, 'previous_low')]:
                        distance = abs(level_price - current_price) / current_price
                        
                        if 0.01 <= distance <= 0.08:  # Between 1% and 8% away
                            # Calculate strength based on timeframe and distance
                            if periods >= 720:  # Monthly
                                base_strength = 85
                            elif periods >= 168:  # Weekly
                                base_strength = 70
                            else:  # Daily
                                base_strength = 55
                            
                            # Adjust for distance (closer = stronger)
                            distance_factor = 1 - (distance / 0.08)
                            strength = int(base_strength * distance_factor)
                            
                            magnet = MagnetLevel(
                                price=level_price,
                                magnet_type=level_type,
                                strength=strength,
                                attraction_radius=level_price * 0.006,  # 0.6% radius
                                historical_reactions=0,
                                last_reaction=None
                            )
                            magnets.append(magnet)
            
            return magnets
            
        except Exception as e:
            logger.error(f"Error detecting high/low magnets: {e}")
            return []
    
    def _detect_psychological_magnets(self, current_price: float) -> List[MagnetLevel]:
        """Detect psychological magnet levels"""
        try:
            magnets = []
            
            # Detect "even" price levels that traders psychologically focus on
            # These are prices that end in multiple zeros or are "clean" numbers
            
            price_range = current_price * 0.10  # Look within 10%
            
            # Generate psychological levels based on price magnitude
            if current_price >= 10000:
                # For high prices, focus on 250, 500, 750 intervals
                base_intervals = [250, 500, 750]
            elif current_price >= 1000:
                # For medium prices, focus on 25, 50, 75 intervals
                base_intervals = [25, 50, 75]
            else:
                # For lower prices, focus on smaller intervals
                base_intervals = [2.5, 5, 7.5]
            
            for interval in base_intervals:
                lower_bound = current_price - price_range
                upper_bound = current_price + price_range
                
                start_multiple = math.floor(lower_bound / interval)
                end_multiple = math.ceil(upper_bound / interval)
                
                for multiple in range(start_multiple, end_multiple + 1):
                    psych_price = multiple * interval
                    
                    if lower_bound <= psych_price <= upper_bound and psych_price > 0:
                        # Calculate strength based on "cleanliness" of number
                        strength = 40  # Base psychological strength
                        
                        # Boost for quarter/half/three-quarter levels
                        if multiple % 4 == 0:  # Quarter levels
                            strength += 20
                        elif multiple % 2 == 0:  # Half levels
                            strength += 15
                        
                        # Reduce strength based on distance
                        distance = abs(psych_price - current_price) / current_price
                        distance_factor = 1 - (distance / 0.10)
                        final_strength = int(strength * distance_factor)
                        
                        if final_strength >= 30:  # Only include meaningful levels
                            magnet = MagnetLevel(
                                price=psych_price,
                                magnet_type='psychological',
                                strength=final_strength,
                                attraction_radius=psych_price * 0.004,  # 0.4% radius
                                historical_reactions=0,
                                last_reaction=None
                            )
                            magnets.append(magnet)
            
            return magnets
            
        except Exception as e:
            logger.error(f"Error detecting psychological magnets: {e}")
            return []
    
    def _enhance_with_historical_data(self, magnet_levels: List[MagnetLevel], 
                                    price_levels: List[PriceLevel]) -> List[MagnetLevel]:
        """Enhance magnet levels with historical reaction data"""
        try:
            enhanced_magnets = []
            
            for magnet in magnet_levels:
                # Find nearby price levels that confirm this magnet
                nearby_levels = []
                for price_level in price_levels:
                    distance = abs(price_level.price - magnet.price) / magnet.price
                    if distance <= 0.01:  # Within 1%
                        nearby_levels.append(price_level)
                
                # Enhance magnet with historical data
                if nearby_levels:
                    # Use the strongest nearby level for enhancement
                    strongest_level = max(nearby_levels, key=lambda x: x.strength_score)
                    
                    # Boost magnet strength based on historical confirmation
                    historical_boost = min(strongest_level.strength_score // 2, 30)
                    magnet.strength = min(magnet.strength + historical_boost, 100)
                    magnet.historical_reactions = strongest_level.touch_count
                    magnet.last_reaction = strongest_level.last_tested
                
                enhanced_magnets.append(magnet)
            
            return enhanced_magnets
            
        except Exception as e:
            logger.error(f"Error enhancing magnet levels: {e}")
            return magnet_levels
    
    def get_nearest_magnet(self, magnet_levels: List[MagnetLevel], 
                          current_price: float) -> Optional[MagnetLevel]:
        """Get the nearest strong magnet level to current price"""
        try:
            if not magnet_levels:
                return None
            
            # Filter for strong magnets only
            strong_magnets = [m for m in magnet_levels if m.strength >= 60]
            
            if not strong_magnets:
                return None
            
            # Find nearest magnet
            nearest = min(strong_magnets, key=lambda x: abs(x.price - current_price))
            
            # Only return if within reasonable distance (5%)
            distance = abs(nearest.price - current_price) / current_price
            if distance <= 0.05:
                return nearest
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting nearest magnet: {e}")
            return None
    
    def is_price_near_magnet(self, current_price: float, magnet: MagnetLevel) -> bool:
        """Check if current price is within magnet's attraction radius"""
        try:
            distance = abs(current_price - magnet.price)
            return distance <= magnet.attraction_radius
            
        except Exception as e:
            logger.error(f"Error checking magnet proximity: {e}")
            return False
