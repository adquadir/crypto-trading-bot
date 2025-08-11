"""
Statistical Calculator
Calculates optimal profit targets and stop losses based on historical data
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import logging
from scipy import stats

from .price_level_analyzer import PriceLevel
from .magnet_level_detector import MagnetLevel

logger = logging.getLogger(__name__)

@dataclass
class TradingTargets:
    """Represents calculated trading targets for a level"""
    entry_price: float
    profit_target: float
    stop_loss: float
    profit_probability: float  # 0-1 probability of hitting profit target
    risk_reward_ratio: float
    expected_duration_minutes: int
    confidence_score: int  # 0-100 overall confidence
    # Net-dollar targets (after fees)
    take_profit_net_usd: float = 0.0  # Net USD take profit target
    stop_loss_net_usd: float = 0.0    # Net USD stop loss target
    floor_net_usd: float = 0.0        # Net USD floor target
    
    def to_dict(self) -> Dict:
        return {
            'entry_price': self.entry_price,
            'profit_target': self.profit_target,
            'stop_loss': self.stop_loss,
            'profit_probability': self.profit_probability,
            'risk_reward_ratio': self.risk_reward_ratio,
            'expected_duration_minutes': self.expected_duration_minutes,
            'confidence_score': self.confidence_score,
            'take_profit_net_usd': self.take_profit_net_usd,
            'stop_loss_net_usd': self.stop_loss_net_usd,
            'floor_net_usd': self.floor_net_usd
        }

class StatisticalCalculator:
    """Calculates statistically optimal trading targets"""
    
    def __init__(self):
        self.min_profit_probability = 0.75  # Minimum 75% success probability
        self.min_risk_reward = 1.5  # Minimum 1.5:1 risk/reward
        self.max_trade_duration = 60  # Maximum 60 minutes per trade
        
    def calculate_targets(self, level: PriceLevel, current_price: float, 
                         historical_data: pd.DataFrame, 
                         magnet_level: Optional[MagnetLevel] = None,
                         adaptive_tolerance: float = 0.003) -> Optional[TradingTargets]:
        """Calculate optimal trading targets for a price level"""
        try:
            logger.info(f"📊 Calculating targets for {level.level_type} level at ${level.price:.2f}")
            
            # Analyze historical bounces from this level with adaptive tolerance
            bounce_analysis = self._analyze_historical_bounces(level, historical_data, adaptive_tolerance)
            
            if not bounce_analysis or bounce_analysis['sample_size'] < 5:
                logger.warning(f"Insufficient bounce data for level ${level.price:.2f}")
                return None
            
            # Calculate optimal profit target
            profit_target = self._calculate_profit_target(level, bounce_analysis, current_price)
            
            # Calculate stop loss
            stop_loss = self._calculate_stop_loss(level, current_price, bounce_analysis)
            
            # Calculate probabilities and metrics
            profit_probability = self._calculate_profit_probability(bounce_analysis, profit_target, level.price)
            risk_reward = abs(profit_target - level.price) / abs(level.price - stop_loss)
            expected_duration = self._estimate_trade_duration(bounce_analysis)
            
            # Calculate overall confidence score
            confidence_score = self._calculate_confidence_score(
                level, bounce_analysis, profit_probability, risk_reward, magnet_level
            )
            
            # Validate targets meet minimum requirements
            if (profit_probability < self.min_profit_probability or 
                risk_reward < self.min_risk_reward or
                expected_duration > self.max_trade_duration):
                logger.info(f"Targets don't meet requirements: prob={profit_probability:.2f}, rr={risk_reward:.2f}")
                return None
            
            targets = TradingTargets(
                entry_price=level.price,
                profit_target=profit_target,
                stop_loss=stop_loss,
                profit_probability=profit_probability,
                risk_reward_ratio=risk_reward,
                expected_duration_minutes=expected_duration,
                confidence_score=confidence_score
            )
            
            logger.info(f"✅ Targets calculated: PT=${profit_target:.2f}, SL=${stop_loss:.2f}, "
                       f"Prob={profit_probability:.1%}, RR={risk_reward:.1f}")
            
            return targets
            
        except Exception as e:
            logger.error(f"Error calculating targets: {e}")
            return None
    
    def _analyze_historical_bounces(self, level: PriceLevel, 
                                  historical_data: pd.DataFrame,
                                  adaptive_tolerance: float = 0.003) -> Optional[Dict]:
        """Analyze historical bounce behavior at this level"""
        try:
            bounces = []
            failed_bounces = []
            durations = []
            volumes = []
            
            tolerance = level.price * adaptive_tolerance  # Use adaptive tolerance
            
            for i in range(len(historical_data) - 10):  # Need future data
                row = historical_data.iloc[i]
                
                # Check if price touched this level
                touched = False
                if level.level_type == 'support':
                    touched = row['low'] <= level.price + tolerance and row['low'] >= level.price - tolerance
                elif level.level_type == 'resistance':
                    touched = row['high'] >= level.price - tolerance and row['high'] <= level.price + tolerance
                
                if touched:
                    volumes.append(row['volume'])
                    
                    # Analyze what happened after the touch
                    future_data = historical_data.iloc[i+1:i+11]  # Next 10 periods
                    
                    if level.level_type == 'support':
                        # Look for upward bounce
                        max_bounce = future_data['high'].max()
                        bounce_distance = max_bounce - row['low']
                        bounce_pct = bounce_distance / level.price
                        
                        # Find when max bounce occurred
                        bounce_idx = future_data['high'].idxmax()
                        duration = (bounce_idx - i) * 60  # Assuming hourly data
                        
                        if bounce_pct >= 0.005:  # At least 0.5% bounce
                            bounces.append({
                                'distance': bounce_distance,
                                'percentage': bounce_pct,
                                'duration_minutes': duration,
                                'volume': row['volume']
                            })
                        else:
                            failed_bounces.append({
                                'distance': bounce_distance,
                                'percentage': bounce_pct
                            })
                    
                    elif level.level_type == 'resistance':
                        # Look for downward bounce
                        min_bounce = future_data['low'].min()
                        bounce_distance = row['high'] - min_bounce
                        bounce_pct = bounce_distance / level.price
                        
                        # Find when min bounce occurred
                        bounce_idx = future_data['low'].idxmin()
                        duration = (bounce_idx - i) * 60
                        
                        if bounce_pct >= 0.005:  # At least 0.5% bounce
                            bounces.append({
                                'distance': bounce_distance,
                                'percentage': bounce_pct,
                                'duration_minutes': duration,
                                'volume': row['volume']
                            })
                        else:
                            failed_bounces.append({
                                'distance': bounce_distance,
                                'percentage': bounce_pct
                            })
            
            if len(bounces) < 3:  # Need at least 3 successful bounces
                return None
            
            # Calculate statistics
            bounce_distances = [b['distance'] for b in bounces]
            bounce_percentages = [b['percentage'] for b in bounces]
            bounce_durations = [b['duration_minutes'] for b in bounces]
            
            analysis = {
                'sample_size': len(bounces),
                'success_rate': len(bounces) / (len(bounces) + len(failed_bounces)),
                'avg_bounce_distance': np.mean(bounce_distances),
                'median_bounce_distance': np.median(bounce_distances),
                'std_bounce_distance': np.std(bounce_distances),
                'avg_bounce_percentage': np.mean(bounce_percentages),
                'median_bounce_percentage': np.median(bounce_percentages),
                'percentile_25': np.percentile(bounce_percentages, 25),
                'percentile_50': np.percentile(bounce_percentages, 50),
                'percentile_75': np.percentile(bounce_percentages, 75),
                'percentile_85': np.percentile(bounce_percentages, 85),
                'percentile_95': np.percentile(bounce_percentages, 95),
                'avg_duration': np.mean(bounce_durations),
                'median_duration': np.median(bounce_durations),
                'avg_volume': np.mean(volumes) if volumes else 0,
                'bounce_data': bounces
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing historical bounces: {e}")
            return None
    
    def _calculate_profit_target(self, level: PriceLevel, bounce_analysis: Dict, 
                               current_price: float) -> float:
        """Calculate profit target - FIXED $10 PROFIT TARGET (0.5% with 10x leverage)"""
        try:
            # FIXED PROFIT TARGET: $10 per position
            # With $200 capital at risk and 10x leverage: $10 profit = 0.5% price movement
            fixed_tp_pct = 0.005  # 0.5% fixed target for $10 profit
            
            if level.level_type == 'support':
                # For support, target is above the level
                profit_target = level.price * (1 + fixed_tp_pct)
            else:  # resistance
                # For resistance, target is below the level
                profit_target = level.price * (1 - fixed_tp_pct)
            
            logger.info(f"💰 FIXED $10 TP: {level.level_type} @ {level.price:.4f} → TP @ {profit_target:.4f} ({fixed_tp_pct:.3%}) [Target: $10 profit]")
            return profit_target
            
        except Exception as e:
            logger.error(f"Error calculating fixed profit target: {e}")
            # Fallback to 0.5% target for $10 profit
            fixed_tp_pct = 0.005
            if level.level_type == 'support':
                return level.price * (1 + fixed_tp_pct)
            else:
                return level.price * (1 - fixed_tp_pct)
    
    def _calculate_stop_loss(self, level: PriceLevel, current_price: float, 
                           bounce_analysis: Dict) -> float:
        """Calculate stop loss based on level strength and volatility"""
        try:
            # Base stop loss on level strength and historical failures
            base_stop_percentage = 0.003  # 0.3% base stop
            
            # Adjust based on level strength (stronger levels = tighter stops)
            strength_factor = (100 - level.strength_score) / 100
            adjusted_stop = base_stop_percentage * (1 + strength_factor)
            
            # Adjust based on success rate (lower success = wider stops)
            success_rate = bounce_analysis.get('success_rate', 0.8)
            success_factor = (1 - success_rate) * 0.5  # Max 50% adjustment
            final_stop_percentage = adjusted_stop * (1 + success_factor)
            
            # Ensure stop is between 0.2% and 1%
            final_stop_percentage = max(min(final_stop_percentage, 0.01), 0.002)
            
            if level.level_type == 'support':
                # For support, stop loss is below the level
                stop_loss = level.price * (1 - final_stop_percentage)
            else:  # resistance
                # For resistance, stop loss is above the level
                stop_loss = level.price * (1 + final_stop_percentage)
            
            return stop_loss
            
        except Exception as e:
            logger.error(f"Error calculating stop loss: {e}")
            # Fallback to 0.5% stop
            if level.level_type == 'support':
                return level.price * 0.995
            else:
                return level.price * 1.005
    
    def _calculate_profit_probability(self, bounce_analysis: Dict, 
                                    profit_target: float, entry_price: float) -> float:
        """Calculate probability of hitting profit target"""
        try:
            # Calculate target percentage
            target_pct = abs(profit_target - entry_price) / entry_price
            
            # Count how many historical bounces reached this target
            bounce_data = bounce_analysis.get('bounce_data', [])
            successful_targets = sum(1 for bounce in bounce_data 
                                   if bounce['percentage'] >= target_pct)
            
            # Calculate probability
            probability = successful_targets / len(bounce_data) if bounce_data else 0
            
            # Apply confidence adjustments
            sample_size = len(bounce_data)
            if sample_size < 10:
                # Reduce confidence for small sample sizes
                confidence_penalty = (10 - sample_size) * 0.05
                probability = max(0, probability - confidence_penalty)
            
            return min(probability, 0.95)  # Cap at 95%
            
        except Exception as e:
            logger.error(f"Error calculating profit probability: {e}")
            return 0.5  # Conservative fallback
    
    def _estimate_trade_duration(self, bounce_analysis: Dict) -> int:
        """Estimate expected trade duration in minutes"""
        try:
            # Use median duration from historical data
            median_duration = bounce_analysis.get('median_duration', 30)
            
            # Cap at maximum allowed duration
            return min(int(median_duration), self.max_trade_duration)
            
        except Exception as e:
            logger.error(f"Error estimating trade duration: {e}")
            return 30  # 30 minute fallback
    
    def _calculate_confidence_score(self, level: PriceLevel, bounce_analysis: Dict,
                                  profit_probability: float, risk_reward: float,
                                  magnet_level: Optional[MagnetLevel] = None) -> int:
        """Calculate overall confidence score for the trade setup"""
        try:
            # Base score from level strength
            base_score = level.strength_score * 0.3
            
            # Score from bounce analysis
            sample_size = bounce_analysis.get('sample_size', 0)
            success_rate = bounce_analysis.get('success_rate', 0)
            
            sample_score = min(sample_size * 2, 20)  # Max 20 points for sample size
            success_score = success_rate * 25  # Max 25 points for success rate
            
            # Score from profit probability
            probability_score = profit_probability * 20  # Max 20 points
            
            # Score from risk/reward ratio
            rr_score = min(risk_reward * 5, 15)  # Max 15 points
            
            # Bonus for magnet level confirmation
            magnet_bonus = 0
            if magnet_level and magnet_level.strength >= 60:
                magnet_bonus = 10
            
            total_score = (base_score + sample_score + success_score + 
                          probability_score + rr_score + magnet_bonus)
            
            return min(int(total_score), 100)
            
        except Exception as e:
            logger.error(f"Error calculating confidence score: {e}")
            return 50  # Neutral fallback
    
    def validate_targets(self, targets: TradingTargets, current_price: float) -> bool:
        """Validate that targets meet all requirements"""
        try:
            # Check profit probability
            if targets.profit_probability < self.min_profit_probability:
                return False
            
            # Check risk/reward ratio
            if targets.risk_reward_ratio < self.min_risk_reward:
                return False
            
            # Check trade duration
            if targets.expected_duration_minutes > self.max_trade_duration:
                return False
            
            # Check that entry price is reasonable distance from current price
            distance = abs(targets.entry_price - current_price) / current_price
            if distance > 0.05:  # More than 5% away
                return False
            
            # Check that profit target is reasonable
            profit_distance = abs(targets.profit_target - targets.entry_price) / targets.entry_price
            if profit_distance < 0.003 or profit_distance > 0.025:  # Between 0.3% and 2.5%
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating targets: {e}")
            return False
    
    def get_optimal_position_size(self, targets: TradingTargets, account_balance: float,
                                max_risk_per_trade: float = 0.02) -> float:
        """Calculate optimal position size based on risk management"""
        try:
            # Calculate risk per trade (distance to stop loss)
            risk_per_unit = abs(targets.entry_price - targets.stop_loss)
            
            # Calculate maximum position size based on risk limit
            max_risk_amount = account_balance * max_risk_per_trade
            max_position_size = max_risk_amount / risk_per_unit
            
            # Adjust based on confidence (higher confidence = larger position)
            confidence_factor = targets.confidence_score / 100
            optimal_size = max_position_size * confidence_factor
            
            return optimal_size
            
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return 0.0
