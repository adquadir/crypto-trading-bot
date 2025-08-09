"""
Price Level Analyzer
Identifies historically reactive support/resistance levels from price data
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from scipy.signal import argrelextrema
from sklearn.cluster import DBSCAN

logger = logging.getLogger(__name__)

@dataclass
class PriceLevel:
    """Represents an identified price level"""
    price: float
    level_type: str  # 'support', 'resistance', 'magnet'
    strength_score: int  # 0-100 reliability score
    touch_count: int
    bounce_count: int
    avg_bounce_distance: float
    max_bounce_distance: float
    last_tested: datetime
    first_identified: datetime
    volume_confirmation: float  # Average volume at this level
    
    def to_dict(self) -> Dict:
        return {
            'price': self.price,
            'level_type': self.level_type,
            'strength_score': self.strength_score,
            'touch_count': self.touch_count,
            'bounce_count': self.bounce_count,
            'avg_bounce_distance': self.avg_bounce_distance,
            'max_bounce_distance': self.max_bounce_distance,
            'last_tested': self.last_tested.isoformat(),
            'first_identified': self.first_identified.isoformat(),
            'volume_confirmation': self.volume_confirmation
        }

class PriceLevelAnalyzer:
    """Analyzes historical price data to identify reactive levels"""
    
    def __init__(self, min_touches: int = 3, min_strength: int = 60):
        self.min_touches = min_touches
        self.min_strength = min_strength
        self.lookback_days = 30
        self.price_tolerance = 0.002  # 0.2% tolerance for level clustering
        
    async def analyze_symbol(self, symbol: str, exchange_client) -> List[PriceLevel]:
        """Analyze a symbol and return identified price levels"""
        try:
            logger.info(f"🔍 Analyzing price levels for {symbol}")
            
            # Get historical data
            historical_data = await self._get_historical_data(symbol, exchange_client)
            if historical_data is None or len(historical_data) < 100:
                logger.warning(f"Insufficient data for {symbol}")
                return []
            
            # Find pivot points
            pivot_highs, pivot_lows = self._find_pivot_points(historical_data)
            
            # Cluster similar price levels
            support_levels = self._cluster_price_levels(pivot_lows, historical_data, 'support')
            resistance_levels = self._cluster_price_levels(pivot_highs, historical_data, 'resistance')
            
            # Combine and validate levels
            all_levels = support_levels + resistance_levels
            validated_levels = self._validate_levels(all_levels, historical_data)
            
            # Filter by minimum requirements
            strong_levels = [level for level in validated_levels 
                           if level.strength_score >= self.min_strength 
                           and level.touch_count >= self.min_touches]
            
            logger.info(f"✅ Found {len(strong_levels)} strong levels for {symbol}")
            return strong_levels
            
        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}")
            return []
    
    async def _get_historical_data(self, symbol: str, exchange_client, days: int = 30) -> Optional[pd.DataFrame]:
        """Get historical OHLCV data - REAL DATA ONLY"""
        try:
            if not exchange_client:
                logger.error(f"❌ CRITICAL: No exchange client provided for {symbol} - CANNOT PROCEED WITHOUT REAL DATA")
                raise ValueError("Exchange client is required - mock data is not allowed")
            
            logger.info(f"🔗 Using REAL Binance data for {symbol}")
            
            # Calculate limit based on days requested (24 hours per day)
            limit = min(days * 24, 1500)  # Binance API limit is 1500
            
            # Use real exchange client with proper method
            klines = await exchange_client.get_klines(
                symbol=symbol,
                interval='1h',
                limit=limit
            )
            
            if not klines:
                logger.error(f"❌ CRITICAL: No real data received for {symbol} from Binance API")
                raise ValueError(f"Failed to get real market data for {symbol}")
            
            # Convert Binance klines format to DataFrame
            df_data = []
            for kline in klines:
                df_data.append({
                    'timestamp': pd.to_datetime(int(kline[0]), unit='ms'),
                    'open': float(kline[1]),
                    'high': float(kline[2]),
                    'low': float(kline[3]),
                    'close': float(kline[4]),
                    'volume': float(kline[5])
                })
            
            df = pd.DataFrame(df_data)
            logger.info(f"✅ REAL DATA: {symbol} - {len(df)} candles, price range ${df['low'].min():.2f} - ${df['high'].max():.2f}")
            return df
                
        except Exception as e:
            logger.error(f"❌ CRITICAL ERROR getting real data for {symbol}: {e}")
            logger.error("🚫 MOCK DATA IS NOT ALLOWED - SYSTEM WILL NOT PROCEED")
            raise
    
    def _generate_mock_data(self, symbol: str) -> pd.DataFrame:
        """Generate realistic mock price data with BALANCED support/resistance levels"""
        # Use symbol-specific seed for variety but consistency
        seed = hash(symbol) % 1000
        np.random.seed(seed)
        
        # Base price
        base_price = 50000 if 'BTC' in symbol else 3000
        
        # Generate 720 hours (30 days) of data
        timestamps = pd.date_range(
            start=datetime.now() - timedelta(days=30),
            periods=720,
            freq='H'
        )
        
        # Generate realistic price movement with MULTIPLE support/resistance levels
        prices = []
        current_price = base_price
        
        # Define MULTIPLE key levels that will act as support/resistance
        # This ensures we get both types of levels near current price
        key_levels = [
            base_price * 0.92,  # Strong support (far)
            base_price * 0.95,  # Strong support (medium)
            base_price * 0.98,  # Weak support (close)
            base_price * 0.995, # Very close support
            base_price * 1.005, # Very close resistance
            base_price * 1.02,  # Weak resistance (close)
            base_price * 1.05,  # Strong resistance (medium)
            base_price * 1.08   # Strong resistance (far)
        ]
        
        # Create a trending pattern that will test both support and resistance
        trend_phases = [
            ('down', 180),    # First 7.5 days: downtrend (tests support)
            ('sideways', 180), # Next 7.5 days: sideways (tests both)
            ('up', 180),      # Next 7.5 days: uptrend (tests resistance)
            ('sideways', 180)  # Last 7.5 days: sideways (tests both)
        ]
        
        phase_index = 0
        phase_counter = 0
        current_trend, phase_length = trend_phases[phase_index]
        
        for i in range(720):
            # Switch trend phases
            if phase_counter >= phase_length and phase_index < len(trend_phases) - 1:
                phase_index += 1
                phase_counter = 0
                current_trend, phase_length = trend_phases[phase_index]
                logger.info(f"Mock data: Switching to {current_trend} trend for {symbol}")
            
            # Base random change
            change = np.random.normal(0, 0.008)  # 0.8% base volatility
            
            # Add trend bias
            if current_trend == 'down':
                change -= 0.002  # Downward bias
            elif current_trend == 'up':
                change += 0.002  # Upward bias
            # sideways has no bias
            
            # Add attraction/repulsion to key levels
            for level in key_levels:
                distance = abs(current_price - level) / level
                if distance < 0.015:  # Within 1.5% of level
                    level_strength = 0.008  # Strong level effect
                    
                    if current_price > level:
                        # Above level - level acts as support
                        if current_price < level * 1.01:  # Very close
                            change += level_strength  # Bounce up from support
                    else:
                        # Below level - level acts as resistance
                        if current_price > level * 0.99:  # Very close
                            change -= level_strength  # Bounce down from resistance
            
            # Apply change
            current_price *= (1 + change)
            
            # Ensure price stays within reasonable bounds
            current_price = max(current_price, base_price * 0.85)
            current_price = min(current_price, base_price * 1.15)
            
            # Generate OHLC from current price with realistic wicks
            wick_size = abs(np.random.normal(0, 0.003))  # 0.3% average wick
            high = current_price * (1 + wick_size)
            low = current_price * (1 - wick_size)
            
            # Ensure OHLC relationships are valid
            open_price = current_price * (1 + np.random.normal(0, 0.001))
            close = current_price
            
            # Make sure high is highest and low is lowest
            high = max(high, open_price, close)
            low = min(low, open_price, close)
            
            volume = np.random.uniform(800, 6000)
            
            prices.append({
                'timestamp': timestamps[i],
                'open': open_price,
                'high': high,
                'low': low,
                'close': close,
                'volume': volume
            })
            
            phase_counter += 1
        
        df = pd.DataFrame(prices)
        logger.info(f"Generated mock data for {symbol}: Price range ${df['low'].min():.2f} - ${df['high'].max():.2f}")
        return df
    
    def _find_pivot_points(self, df: pd.DataFrame) -> Tuple[List[float], List[float]]:
        """Find pivot highs and lows in price data"""
        try:
            highs = df['high'].values
            lows = df['low'].values
            
            # Find local maxima and minima
            # Use order=5 for 5-period lookback/forward
            high_indices = argrelextrema(highs, np.greater, order=5)[0]
            low_indices = argrelextrema(lows, np.less, order=5)[0]
            
            pivot_highs = highs[high_indices].tolist()
            pivot_lows = lows[low_indices].tolist()
            
            logger.info(f"Found {len(pivot_highs)} pivot highs, {len(pivot_lows)} pivot lows")
            return pivot_highs, pivot_lows
            
        except Exception as e:
            logger.error(f"Error finding pivot points: {e}")
            return [], []
    
    def _cluster_price_levels(self, prices: List[float], df: pd.DataFrame, level_type: str) -> List[PriceLevel]:
        """Cluster similar price levels using DBSCAN"""
        try:
            if len(prices) < 3:
                return []
            
            # Prepare data for clustering
            price_array = np.array(prices).reshape(-1, 1)
            
            # Use DBSCAN to cluster similar prices
            # eps is the maximum distance between points (as percentage of price)
            avg_price = np.mean(prices)
            eps = avg_price * self.price_tolerance  # 0.2% tolerance
            
            clustering = DBSCAN(eps=eps, min_samples=2).fit(price_array)
            
            levels = []
            unique_labels = set(clustering.labels_)
            
            for label in unique_labels:
                if label == -1:  # Noise points
                    continue
                
                # Get all prices in this cluster
                cluster_prices = [prices[i] for i in range(len(prices)) 
                                if clustering.labels_[i] == label]
                
                if len(cluster_prices) < self.min_touches:
                    continue
                
                # Calculate cluster statistics
                cluster_price = np.mean(cluster_prices)
                touch_count = len(cluster_prices)
                
                # Analyze bounces from this level
                bounce_stats = self._analyze_bounces(cluster_price, df, level_type)
                
                # Calculate strength score
                strength_score = self._calculate_strength_score(
                    touch_count, bounce_stats['bounce_count'], 
                    bounce_stats['avg_bounce_distance']
                )
                
                level = PriceLevel(
                    price=cluster_price,
                    level_type=level_type,
                    strength_score=strength_score,
                    touch_count=touch_count,
                    bounce_count=bounce_stats['bounce_count'],
                    avg_bounce_distance=bounce_stats['avg_bounce_distance'],
                    max_bounce_distance=bounce_stats['max_bounce_distance'],
                    last_tested=bounce_stats['last_tested'],
                    first_identified=bounce_stats['first_identified'],
                    volume_confirmation=bounce_stats['avg_volume']
                )
                
                levels.append(level)
            
            return levels
            
        except Exception as e:
            logger.error(f"Error clustering price levels: {e}")
            return []
    
    def _analyze_bounces(self, level_price: float, df: pd.DataFrame, level_type: str) -> Dict:
        """Analyze bounce behavior at a specific price level"""
        try:
            bounces = []
            touches = []
            volumes = []
            
            tolerance = level_price * self.price_tolerance
            
            for i, row in df.iterrows():
                # Check if price touched this level
                if level_type == 'support':
                    if row['low'] <= level_price + tolerance and row['low'] >= level_price - tolerance:
                        touches.append(i)
                        volumes.append(row['volume'])
                        
                        # Check for bounce (price moved up after touching)
                        if i < len(df) - 5:  # Need future data to confirm bounce
                            future_prices = df.iloc[i+1:i+6]['close'].values
                            if any(price > level_price * 1.005 for price in future_prices):  # 0.5% bounce
                                bounce_distance = max(future_prices) - row['low']
                                bounces.append(bounce_distance / level_price)  # Percentage bounce
                
                elif level_type == 'resistance':
                    if row['high'] >= level_price - tolerance and row['high'] <= level_price + tolerance:
                        touches.append(i)
                        volumes.append(row['volume'])
                        
                        # Check for bounce (price moved down after touching)
                        if i < len(df) - 5:
                            future_prices = df.iloc[i+1:i+6]['close'].values
                            if any(price < level_price * 0.995 for price in future_prices):  # 0.5% bounce
                                bounce_distance = row['high'] - min(future_prices)
                                bounces.append(bounce_distance / level_price)  # Percentage bounce
            
            # Calculate statistics
            bounce_count = len(bounces)
            avg_bounce_distance = np.mean(bounces) if bounces else 0
            max_bounce_distance = max(bounces) if bounces else 0
            avg_volume = np.mean(volumes) if volumes else 0
            
            # Get timestamps
            last_tested = df.iloc[touches[-1]]['timestamp'] if touches else datetime.now()
            first_identified = df.iloc[touches[0]]['timestamp'] if touches else datetime.now()
            
            return {
                'bounce_count': bounce_count,
                'avg_bounce_distance': avg_bounce_distance,
                'max_bounce_distance': max_bounce_distance,
                'avg_volume': avg_volume,
                'last_tested': last_tested,
                'first_identified': first_identified
            }
            
        except Exception as e:
            logger.error(f"Error analyzing bounces: {e}")
            return {
                'bounce_count': 0,
                'avg_bounce_distance': 0,
                'max_bounce_distance': 0,
                'avg_volume': 0,
                'last_tested': datetime.now(),
                'first_identified': datetime.now()
            }
    
    def _calculate_strength_score(self, touch_count: int, bounce_count: int, avg_bounce_distance: float) -> int:
        """Calculate strength score (0-100) for a price level"""
        try:
            # Base score from touch count (max 40 points)
            touch_score = min(touch_count * 8, 40)
            
            # Bounce reliability score (max 30 points)
            bounce_reliability = (bounce_count / max(touch_count, 1)) * 30
            
            # Bounce strength score (max 30 points)
            bounce_strength = min(avg_bounce_distance * 1000, 30)  # Scale up percentage
            
            total_score = int(touch_score + bounce_reliability + bounce_strength)
            return min(max(total_score, 0), 100)
            
        except Exception as e:
            logger.error(f"Error calculating strength score: {e}")
            return 0
    
    def _validate_levels(self, levels: List[PriceLevel], df: pd.DataFrame) -> List[PriceLevel]:
        """Validate and filter price levels"""
        try:
            validated = []
            current_price = df['close'].iloc[-1]
            
            for level in levels:
                # Skip levels too far from current price (more than 10%)
                distance = abs(level.price - current_price) / current_price
                if distance > 0.10:
                    continue
                
                # Skip levels that haven't been tested recently
                days_since_test = (datetime.now() - level.last_tested).days
                if days_since_test > 14:  # Not tested in 2 weeks
                    continue
                
                # Skip levels with very low bounce rate
                bounce_rate = level.bounce_count / max(level.touch_count, 1)
                if bounce_rate < 0.3:  # Less than 30% bounce rate
                    continue
                
                validated.append(level)
            
            return validated
            
        except Exception as e:
            logger.error(f"Error validating levels: {e}")
            return levels
    
    def get_levels_near_price(self, levels: List[PriceLevel], current_price: float, 
                             max_distance: float = 0.02) -> List[PriceLevel]:
        """Get levels within specified distance of current price"""
        try:
            nearby_levels = []
            
            for level in levels:
                distance = abs(level.price - current_price) / current_price
                if distance <= max_distance:
                    nearby_levels.append(level)
            
            # Sort by distance from current price
            nearby_levels.sort(key=lambda x: abs(x.price - current_price))
            return nearby_levels
            
        except Exception as e:
            logger.error(f"Error getting nearby levels: {e}")
            return []
