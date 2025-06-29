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
    
    async def _get_historical_data(self, symbol: str, exchange_client) -> Optional[pd.DataFrame]:
        """Get historical OHLCV data"""
        try:
            # Get 30 days of 1-hour data
            end_time = datetime.now()
            start_time = end_time - timedelta(days=self.lookback_days)
            
            if exchange_client:
                # Use real exchange client
                klines = await exchange_client.get_klines(
                    symbol=symbol,
                    interval='1h',
                    start_time=int(start_time.timestamp() * 1000),
                    end_time=int(end_time.timestamp() * 1000),
                    limit=1000
                )
                
                if not klines:
                    return None
                
                df = pd.DataFrame(klines, columns=[
                    'timestamp', 'open', 'high', 'low', 'close', 'volume',
                    'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                    'taker_buy_quote', 'ignore'
                ])
                
                # Convert to proper types
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = pd.to_numeric(df[col])
                
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            
            else:
                # Generate mock data for testing
                return self._generate_mock_data(symbol)
                
        except Exception as e:
            logger.error(f"Error getting historical data for {symbol}: {e}")
            return None
    
    def _generate_mock_data(self, symbol: str) -> pd.DataFrame:
        """Generate realistic mock price data for testing"""
        np.random.seed(42)  # Consistent data
        
        # Base price
        base_price = 50000 if 'BTC' in symbol else 3000
        
        # Generate 720 hours (30 days) of data
        timestamps = pd.date_range(
            start=datetime.now() - timedelta(days=30),
            periods=720,
            freq='H'
        )
        
        # Generate realistic price movement with support/resistance
        prices = []
        current_price = base_price
        
        # Define some key levels that will act as support/resistance
        key_levels = [
            base_price * 0.95,  # Strong support
            base_price * 0.98,  # Weak support
            base_price * 1.02,  # Weak resistance
            base_price * 1.05   # Strong resistance
        ]
        
        for i in range(720):
            # Random walk with mean reversion to key levels
            change = np.random.normal(0, 0.01)  # 1% volatility
            
            # Add attraction to key levels
            for level in key_levels:
                distance = abs(current_price - level) / level
                if distance < 0.02:  # Within 2% of level
                    # Add bounce effect
                    if current_price > level:
                        change -= 0.005  # Pull down
                    else:
                        change += 0.005  # Pull up
            
            current_price *= (1 + change)
            
            # Generate OHLC from current price
            high = current_price * (1 + abs(np.random.normal(0, 0.005)))
            low = current_price * (1 - abs(np.random.normal(0, 0.005)))
            open_price = current_price * (1 + np.random.normal(0, 0.002))
            close = current_price
            volume = np.random.uniform(1000, 5000)
            
            prices.append({
                'timestamp': timestamps[i],
                'open': open_price,
                'high': high,
                'low': low,
                'close': close,
                'volume': volume
            })
        
        return pd.DataFrame(prices)
    
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
