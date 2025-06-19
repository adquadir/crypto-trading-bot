"""Institutional-grade trade analysis for real-world trading constraints."""

import math
import logging
from typing import Dict, List, Optional, Tuple, Any
import statistics
import numpy as np

logger = logging.getLogger(__name__)

class InstitutionalTradeAnalyzer:
    """
    Analyze market data for institutional-grade trading opportunities.
    
    Focus on:
    - Real market structure (support/resistance levels that matter)
    - Liquidity analysis (can trades actually be filled?)
    - Dynamic position sizing based on confidence and market conditions
    - Risk-adjusted returns with realistic TP/SL levels
    - Order book depth and slippage considerations
    """
    
    def __init__(self):
        self.min_confidence_threshold = 0.6  # Lower threshold for more opportunities
        self.max_leverage = 10.0  # Conservative leverage cap
        self.min_risk_reward = 1.2  # Lower minimum RR ratio
        
    def analyze_trade_opportunity(self, symbol: str, market_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Perform comprehensive institutional-grade trade analysis.
        
        Returns high-confidence trade setup or None if no quality opportunity exists.
        """
        try:
            klines = market_data.get('klines', [])
            if len(klines) < 50:  # Need sufficient data
                return None
                
            # Extract comprehensive price data
            prices = self._extract_price_data(klines)
            if not prices:
                return None
                
            # 1. Market Structure Analysis
            structure = self._analyze_market_structure(prices)
            if not structure['is_tradeable']:
                return None
                
            # 2. Liquidity & Volume Analysis
            liquidity = self._analyze_liquidity(klines, market_data)
            if liquidity['confidence'] < 0.6:
                return None
                
            # 3. Support/Resistance Level Identification
            levels = self._identify_key_levels(prices)
            if not levels['high_confidence_levels']:
                return None
                
            # 4. Trade Setup Identification
            trade_setup = self._identify_trade_setup(prices, structure, levels, liquidity)
            if not trade_setup or trade_setup['confidence'] < self.min_confidence_threshold:
                return None
                
            # 5. Position Sizing & Risk Management
            position_info = self._calculate_position_sizing(
                trade_setup, structure, liquidity, market_data
            )
            
            # 6. Final Trade Validation
            final_trade = self._validate_and_finalize_trade(
                symbol, trade_setup, position_info, structure, levels, market_data
            )
            
            return final_trade
            
        except Exception as e:
            logger.error(f"Error in institutional trade analysis for {symbol}: {e}")
            return None
    
    def _extract_price_data(self, klines: List[Dict]) -> Optional[Dict[str, List[float]]]:
        """Extract and validate price data."""
        try:
            return {
                'opens': [float(k['open']) for k in klines],
                'highs': [float(k['high']) for k in klines],
                'lows': [float(k['low']) for k in klines],
                'closes': [float(k['close']) for k in klines],
                'volumes': [float(k['volume']) for k in klines],
                'timestamps': [int(k['openTime']) for k in klines]
            }
        except (ValueError, KeyError) as e:
            logger.error(f"Invalid price data: {e}")
            return None
    
    def _analyze_market_structure(self, prices: Dict[str, List[float]]) -> Dict[str, Any]:
        """
        Analyze market structure to determine if market is tradeable.
        
        Focus on:
        - Trend strength and consistency
        - Market regime (trending/ranging/transitional)
        - Volatility patterns
        - Price action quality
        """
        closes = prices['closes']
        highs = prices['highs']
        lows = prices['lows']
        volumes = prices['volumes']
        
        current_price = closes[-1]
        
        # Calculate multiple timeframe trends
        short_trend = self._calculate_trend_strength(closes[-10:])  # Last 10 periods
        medium_trend = self._calculate_trend_strength(closes[-20:])  # Last 20 periods
        long_trend = self._calculate_trend_strength(closes[-50:])  # Last 50 periods
        
        # Volatility analysis
        volatility = self._calculate_adaptive_volatility(closes)
        
        # Market regime detection
        regime = self._detect_market_regime(closes, highs, lows, volumes)
        
        # Trend alignment score
        trend_alignment = self._calculate_trend_alignment(short_trend, medium_trend, long_trend)
        
        # Price action quality
        price_action_quality = self._assess_price_action_quality(prices)
        
        # Overall tradeability assessment (more liberal)
        is_tradeable = (
            trend_alignment > 0.4 and
            price_action_quality > 0.3 and
            regime['confidence'] > 0.4 and
            volatility['is_normal']
        )
        
        return {
            'is_tradeable': is_tradeable,
            'regime': regime,
            'trend_alignment': trend_alignment,
            'volatility': volatility,
            'price_action_quality': price_action_quality,
            'short_trend': short_trend,
            'medium_trend': medium_trend,
            'long_trend': long_trend,
            'current_price': current_price
        }
    
    def _calculate_trend_strength(self, prices: List[float]) -> Dict[str, float]:
        """Calculate trend strength and direction using linear regression."""
        if len(prices) < 3:
            return {'direction': 0, 'strength': 0, 'consistency': 0}
        
        # Simple linear regression
        n = len(prices)
        x_mean = (n - 1) / 2
        y_mean = sum(prices) / n
        
        numerator = sum((i - x_mean) * (prices[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        
        slope = numerator / denominator if denominator != 0 else 0
        
        # Normalize slope by price
        direction = slope / prices[-1] if prices[-1] != 0 else 0
        
        # Calculate R-squared for consistency
        y_pred = [slope * i + (y_mean - slope * x_mean) for i in range(n)]
        ss_res = sum((prices[i] - y_pred[i]) ** 2 for i in range(n))
        ss_tot = sum((prices[i] - y_mean) ** 2 for i in range(n))
        consistency = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
        
        # Trend strength (combination of direction and consistency)
        strength = abs(direction) * consistency
        
        return {
            'direction': direction,
            'strength': strength,
            'consistency': max(0, consistency)
        }
    
    def _calculate_adaptive_volatility(self, closes: List[float]) -> Dict[str, Any]:
        """Calculate adaptive volatility metrics."""
        if len(closes) < 20:
            return {'value': 0, 'is_normal': False, 'percentile': 0, 'regime': 'unknown'}
        
        # Calculate returns
        returns = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, len(closes))]
        
        # Current volatility (20-period)
        current_vol = statistics.stdev(returns[-20:]) if len(returns) >= 20 else statistics.stdev(returns)
        
        # Historical volatility percentile
        historical_vols = []
        for i in range(20, len(returns)):
            period_vol = statistics.stdev(returns[i-20:i])
            historical_vols.append(period_vol)
        
        if historical_vols:
            vol_percentile = sum(1 for v in historical_vols if v < current_vol) / len(historical_vols)
        else:
            vol_percentile = 0.5
        
        # Determine if volatility is normal (not extreme)
        is_normal = 0.2 <= vol_percentile <= 0.8
        
        return {
            'value': current_vol,
            'percentile': vol_percentile,
            'is_normal': is_normal,
            'regime': 'low' if vol_percentile < 0.3 else 'high' if vol_percentile > 0.7 else 'normal'
        }
    
    def _detect_market_regime(self, closes: List[float], highs: List[float], 
                            lows: List[float], volumes: List[float]) -> Dict[str, Any]:
        """Detect current market regime with confidence."""
        
        # Trend detection
        trend_score = self._calculate_trend_strength(closes[-20:])['strength']
        
        # Range detection (consolidation)
        recent_range = max(highs[-20:]) - min(lows[-20:])
        avg_range = statistics.mean([highs[i] - lows[i] for i in range(-20, 0)])
        range_compression = avg_range / recent_range if recent_range > 0 else 0
        
        # Volume pattern analysis
        volume_trend = self._calculate_trend_strength(volumes[-10:])['strength']
        
        # Regime classification
        if trend_score > 0.3 and range_compression < 0.7:
            regime = 'trending'
            confidence = min(0.9, trend_score + 0.3)
        elif range_compression > 0.8 and trend_score < 0.2:
            regime = 'ranging'
            confidence = min(0.9, range_compression)
        else:
            regime = 'transitional'
            confidence = 0.4
        
        return {
            'type': regime,
            'confidence': confidence,
            'trend_score': trend_score,
            'range_compression': range_compression,
            'volume_trend': volume_trend
        }
    
    def _calculate_trend_alignment(self, short: Dict, medium: Dict, long: Dict) -> float:
        """Calculate alignment between different timeframe trends."""
        
        # Direction alignment
        directions = [short['direction'], medium['direction'], long['direction']]
        
        # Check if all trends point in same direction
        all_positive = all(d > 0.001 for d in directions)
        all_negative = all(d < -0.001 for d in directions)
        
        if all_positive or all_negative:
            # Strong alignment - weight by consistency
            alignment = statistics.mean([short['consistency'], medium['consistency'], long['consistency']])
        else:
            # Mixed signals - lower alignment
            alignment = 0.3
        
        return max(0, min(1, alignment))
    
    def _assess_price_action_quality(self, prices: Dict[str, List[float]]) -> float:
        """Assess the quality of price action for trading."""
        
        closes = prices['closes']
        highs = prices['highs']
        lows = prices['lows']
        
        # Body-to-wick ratio (strong moves vs indecision)
        body_ratios = []
        for i in range(-20, 0):
            if i == 0 or len(closes) + i <= 0:
                continue
                
            high = highs[i]
            low = lows[i]
            close = closes[i]
            open_price = closes[i-1] if i > -len(closes) else closes[i]
            
            total_range = high - low
            body_size = abs(close - open_price)
            
            if total_range > 0:
                body_ratio = body_size / total_range
                body_ratios.append(body_ratio)
        
        avg_body_ratio = statistics.mean(body_ratios) if body_ratios else 0
        
        # Consecutive closes in same direction (momentum)
        consecutive_score = self._calculate_consecutive_momentum(closes[-10:])
        
        # Overall quality score
        quality = (avg_body_ratio * 0.6) + (consecutive_score * 0.4)
        
        return max(0, min(1, quality))
    
    def _calculate_consecutive_momentum(self, closes: List[float]) -> float:
        """Calculate momentum based on consecutive price moves."""
        if len(closes) < 3:
            return 0
        
        consecutive_up = 0
        consecutive_down = 0
        max_consecutive = 0
        
        for i in range(1, len(closes)):
            if closes[i] > closes[i-1]:
                consecutive_up += 1
                consecutive_down = 0
            elif closes[i] < closes[i-1]:
                consecutive_down += 1
                consecutive_up = 0
            else:
                consecutive_up = 0
                consecutive_down = 0
            
            max_consecutive = max(max_consecutive, consecutive_up, consecutive_down)
        
        # Normalize to 0-1 scale
        return min(1.0, max_consecutive / 5.0)
    
    def _analyze_liquidity(self, klines: List[Dict], market_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze market liquidity and trading conditions."""
        
        # Volume analysis
        volumes = [float(k['volume']) for k in klines[-20:]]
        avg_volume = statistics.mean(volumes)
        recent_volume = statistics.mean(volumes[-5:])
        
        volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1
        
        # Volume consistency
        volume_cv = statistics.stdev(volumes) / avg_volume if avg_volume > 0 else 1
        
        # Liquidity score
        liquidity_score = min(1.0, volume_ratio * (1 - min(0.8, volume_cv)))
        
        # Market depth estimation (from futures data if available)
        open_interest = market_data.get('open_interest')
        if open_interest:
            oi_score = min(1.0, float(open_interest) / 1000000)  # Normalize large OI
        else:
            oi_score = 0.5  # Default assumption
        
        # Overall confidence
        confidence = (liquidity_score * 0.7) + (oi_score * 0.3)
        
        return {
            'confidence': confidence,
            'volume_ratio': volume_ratio,
            'volume_consistency': 1 - volume_cv,
            'avg_volume': avg_volume,
            'open_interest_score': oi_score
        }
    
    def _identify_key_levels(self, prices: Dict[str, List[float]]) -> Dict[str, Any]:
        """Identify key support and resistance levels that actually matter."""
        
        highs = prices['highs']
        lows = prices['lows']
        closes = prices['closes']
        current_price = closes[-1]
        
        # Find significant highs and lows (pivot points)
        resistance_levels = self._find_resistance_levels(highs, closes)
        support_levels = self._find_support_levels(lows, closes)
        
        # Filter for high-confidence levels near current price
        relevant_resistance = [r for r in resistance_levels 
                             if abs(r['price'] - current_price) / current_price < 0.05 
                             and r['confidence'] > 0.6]
        
        relevant_support = [s for s in support_levels 
                          if abs(s['price'] - current_price) / current_price < 0.05 
                          and s['confidence'] > 0.6]
        
        # Determine if we're near key levels
        near_resistance = any(r['price'] > current_price for r in relevant_resistance)
        near_support = any(s['price'] < current_price for s in relevant_support)
        
        high_confidence_levels = len(relevant_resistance) + len(relevant_support) > 0
        
        return {
            'resistance_levels': relevant_resistance,
            'support_levels': relevant_support,
            'near_resistance': near_resistance,
            'near_support': near_support,
            'high_confidence_levels': high_confidence_levels,
            'current_price': current_price
        }
    
    def _find_resistance_levels(self, highs: List[float], closes: List[float]) -> List[Dict[str, Any]]:
        """Find significant resistance levels."""
        levels = []
        
        # Look for pivot highs
        for i in range(2, len(highs) - 2):
            if (highs[i] > highs[i-1] and highs[i] > highs[i-2] and 
                highs[i] > highs[i+1] and highs[i] > highs[i+2]):
                
                # Count how many times price tested this level
                tests = sum(1 for h in highs[i+1:] if abs(h - highs[i]) / highs[i] < 0.005)
                
                # Calculate confidence based on tests and time
                confidence = min(0.9, 0.3 + (tests * 0.2))
                
                levels.append({
                    'price': highs[i],
                    'confidence': confidence,
                    'tests': tests,
                    'type': 'resistance'
                })
        
        return sorted(levels, key=lambda x: x['confidence'], reverse=True)[:5]
    
    def _find_support_levels(self, lows: List[float], closes: List[float]) -> List[Dict[str, Any]]:
        """Find significant support levels."""
        levels = []
        
        # Look for pivot lows
        for i in range(2, len(lows) - 2):
            if (lows[i] < lows[i-1] and lows[i] < lows[i-2] and 
                lows[i] < lows[i+1] and lows[i] < lows[i+2]):
                
                # Count how many times price tested this level
                tests = sum(1 for l in lows[i+1:] if abs(l - lows[i]) / lows[i] < 0.005)
                
                # Calculate confidence based on tests and time
                confidence = min(0.9, 0.3 + (tests * 0.2))
                
                levels.append({
                    'price': lows[i],
                    'confidence': confidence,
                    'tests': tests,
                    'type': 'support'
                })
        
        return sorted(levels, key=lambda x: x['confidence'], reverse=True)[:5]
    
    def _identify_trade_setup(self, prices: Dict[str, List[float]], structure: Dict[str, Any],
                            levels: Dict[str, Any], liquidity: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Identify specific trade setup with entry, TP, and SL."""
        
        current_price = structure['current_price']
        
        # Only trade high-probability setups (more liberal)
        if structure['trend_alignment'] < 0.4:
            return None
        
        # Determine trade direction based on structure
        if structure['short_trend']['direction'] > 0.002:  # Strong uptrend
            direction = 'LONG'
            entry_price = current_price
            
            # Find nearest resistance for TP
            resistance_levels = [r for r in levels['resistance_levels'] if r['price'] > current_price]
            if resistance_levels:
                take_profit = resistance_levels[0]['price'] * 0.995  # Slightly before resistance
            else:
                take_profit = current_price * (1 + structure['volatility']['value'] * 3)
            
            # Find support for SL or use volatility-based
            support_levels = [s for s in levels['support_levels'] if s['price'] < current_price]
            if support_levels:
                stop_loss = support_levels[0]['price'] * 1.005  # Slightly below support
            else:
                stop_loss = current_price * (1 - structure['volatility']['value'] * 2)
                
        elif structure['short_trend']['direction'] < -0.002:  # Strong downtrend
            direction = 'SHORT'
            entry_price = current_price
            
            # Find nearest support for TP
            support_levels = [s for s in levels['support_levels'] if s['price'] < current_price]
            if support_levels:
                take_profit = support_levels[0]['price'] * 1.005  # Slightly above support
            else:
                take_profit = current_price * (1 - structure['volatility']['value'] * 3)
            
            # Find resistance for SL or use volatility-based
            resistance_levels = [r for r in levels['resistance_levels'] if r['price'] > current_price]
            if resistance_levels:
                stop_loss = resistance_levels[0]['price'] * 0.995  # Slightly above resistance
            else:
                stop_loss = current_price * (1 + structure['volatility']['value'] * 2)
        else:
            return None  # No clear direction
        
        # Calculate risk/reward
        risk = abs(entry_price - stop_loss)
        reward = abs(take_profit - entry_price)
        risk_reward = reward / risk if risk > 0 else 0
        
        # Only proceed if RR is acceptable
        if risk_reward < self.min_risk_reward:
            return None
        
        # Calculate confidence
        confidence = (
            structure['trend_alignment'] * 0.4 +
            structure['price_action_quality'] * 0.3 +
            liquidity['confidence'] * 0.2 +
            min(1.0, risk_reward / 3.0) * 0.1
        )
        
        return {
            'direction': direction,
            'entry_price': entry_price,
            'take_profit': take_profit,
            'stop_loss': stop_loss,
            'risk_reward': risk_reward,
            'confidence': confidence,
            'setup_type': f"{structure['regime']['type']}_trend"
        }
    
    def _calculate_position_sizing(self, trade_setup: Dict[str, Any], structure: Dict[str, Any],
                                 liquidity: Dict[str, Any], market_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate optimal position size and leverage."""
        
        # Base risk per trade (1-3% of account based on confidence)
        base_risk_percent = 0.01 + (trade_setup['confidence'] * 0.02)  # 1-3%
        
        # Adjust for volatility
        vol_adjustment = 1.0 / (1.0 + structure['volatility']['value'] * 10)
        
        # Adjust for liquidity
        liquidity_adjustment = liquidity['confidence']
        
        # Final risk percentage
        risk_percent = base_risk_percent * vol_adjustment * liquidity_adjustment
        
        # Calculate leverage based on risk and confidence
        base_leverage = min(self.max_leverage, trade_setup['confidence'] * 5)
        
        # Reduce leverage in high volatility
        volatility_factor = max(0.3, 1.0 - structure['volatility']['percentile'])
        recommended_leverage = base_leverage * volatility_factor
        
        # Position size calculation (for $10,000 account)
        account_size = 10000  # Example account
        risk_amount = account_size * risk_percent
        
        price_distance = abs(trade_setup['entry_price'] - trade_setup['stop_loss'])
        position_size = risk_amount / price_distance if price_distance > 0 else 0
        
        # Convert to notional value
        notional_value = position_size * trade_setup['entry_price']
        
        return {
            'risk_percent': risk_percent,
            'recommended_leverage': recommended_leverage,
            'position_size': position_size,
            'notional_value': notional_value,
            'risk_amount': risk_amount,
            'account_size': account_size
        }
    
    def _validate_and_finalize_trade(self, symbol: str, trade_setup: Dict[str, Any],
                                   position_info: Dict[str, Any], structure: Dict[str, Any],
                                   levels: Dict[str, Any], market_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Final validation and trade package creation."""
        
        # Final confidence check
        if trade_setup['confidence'] < self.min_confidence_threshold:
            return None
        
        # Final RR check
        if trade_setup['risk_reward'] < self.min_risk_reward:
            return None
        
        # Calculate expected profit
        expected_profit = position_info['risk_amount'] * trade_setup['risk_reward']
        expected_return = expected_profit / position_info['account_size']
        
        # Create comprehensive trade package
        return {
            'symbol': symbol,
            'direction': trade_setup['direction'],
            'entry_price': trade_setup['entry_price'],
            'take_profit': trade_setup['take_profit'],
            'stop_loss': trade_setup['stop_loss'],
            'confidence': trade_setup['confidence'],
            'risk_reward': trade_setup['risk_reward'],
            
            # Position sizing
            'recommended_leverage': position_info['recommended_leverage'],
            'position_size': position_info['position_size'],
            'notional_value': position_info['notional_value'],
            'risk_percent': position_info['risk_percent'],
            'expected_profit': expected_profit,
            'expected_return': expected_return,
            
            # Market analysis
            'market_regime': structure['regime']['type'],
            'trend_alignment': structure['trend_alignment'],
            'volatility_regime': structure['volatility']['regime'],
            'liquidity_score': liquidity['confidence'],
            'setup_type': trade_setup['setup_type'],
            
            # Key levels
            'key_resistance': [r['price'] for r in levels['resistance_levels'][:3]],
            'key_support': [s['price'] for s in levels['support_levels'][:3]],
            
            # Reasoning
            'reasoning': [
                f"High-confidence {trade_setup['direction']} setup",
                f"Trend alignment: {structure['trend_alignment']:.1%}",
                f"Risk/Reward: {trade_setup['risk_reward']:.1f}:1",
                f"Expected return: {expected_return:.1%}",
                f"Market regime: {structure['regime']['type']}",
                f"Volatility: {structure['volatility']['regime']}"
            ],
            
            # Metadata
            'analysis_type': 'institutional_grade',
            'timestamp': market_data.get('timestamp', 0),
            'is_futures_data': market_data.get('is_futures_data', False),
            'funding_rate': market_data.get('funding_rate'),
            'open_interest': market_data.get('open_interest')
        } 