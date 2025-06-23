"""
🧠 Automated Learning Manager - The Missing Learning Loop

This implements the critical missing piece: automated feedback from performance data
to signal generation criteria, making the system actually learn and improve.
"""

import asyncio
import logging
import json
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

@dataclass
class LearningCriteria:
    """Current learning-adjusted criteria"""
    min_confidence: float = 0.6
    min_risk_reward: float = 1.2
    max_volatility: float = 0.08
    stop_loss_tightness: float = 0.02  # 2%
    take_profit_distance: float = 0.03  # 3%
    min_volume_ratio: float = 1.05
    disabled_strategies: List[str] = None
    
    def __post_init__(self):
        if self.disabled_strategies is None:
            self.disabled_strategies = []

@dataclass
class LearningAction:
    """Track learning actions taken"""
    timestamp: datetime
    action_type: str
    reason: str
    old_value: Any
    new_value: Any
    performance_trigger: Dict[str, Any]

class AutomatedLearningManager:
    """Automated learning system that actually learns from performance data"""
    
    def __init__(self, enhanced_signal_tracker, opportunity_manager):
        self.signal_tracker = enhanced_signal_tracker
        self.opportunity_manager = opportunity_manager
        
        # Current adaptive criteria
        self.criteria = LearningCriteria()
        
        # Learning state
        self.learning_iterations = 0
        self.last_optimization = None
        self.learning_actions: List[LearningAction] = []
        
        # Emergency thresholds
        self.emergency_failure_threshold = 100  # Stop strategy after 100 failures
        self.catastrophic_failure_threshold = 500  # Complete reset after 500 failures
        
        # Learning task
        self.learning_task = None
        self.enabled = True
        
        # Ensure data directory exists
        os.makedirs('data', exist_ok=True)
        
    async def start_learning_loop(self):
        """Start the automated learning background task"""
        if self.learning_task:
            return
            
        logger.info("🧠 Starting automated learning loop...")
        await self.load_criteria_from_file()
        self.learning_task = asyncio.create_task(self._continuous_learning_loop())
        
    async def stop_learning_loop(self):
        """Stop the learning loop"""
        if self.learning_task:
            self.learning_task.cancel()
            try:
                await self.learning_task
            except asyncio.CancelledError:
                pass
            self.learning_task = None
            logger.info("🛑 Stopped automated learning loop")
    
    async def _continuous_learning_loop(self):
        """Main learning loop - checks performance and adjusts criteria every hour"""
        logger.info("🔄 Automated learning loop started - checking performance every hour")
        
        while self.enabled:
            try:
                await self._perform_learning_iteration()
                
                # Check every hour (3600 seconds)
                await asyncio.sleep(3600)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Learning loop error: {e}")
                await asyncio.sleep(300)  # 5 minutes on error
                
        logger.info("🛑 Learning loop stopped")
    
    async def _perform_learning_iteration(self):
        """Perform one learning iteration - THE CORE LEARNING LOGIC"""
        
        # Get recent performance data (last 24 hours)
        performance = await self.signal_tracker.get_performance_summary(days_back=1)
        
        if not performance or not performance.get('overall'):
            logger.debug("🔍 No performance data for learning iteration")
            return
            
        overall = performance['overall']
        strategies = performance.get('by_strategy', [])
        
        total_signals = overall.get('total_signals', 0)
        hit_rate_3pct = overall.get('signals_3pct', 0) / max(total_signals, 1) * 100
        stop_rate = overall.get('signals_stopped', 0) / max(total_signals, 1) * 100
        
        logger.info(f"🔍 Learning check: {total_signals} signals, {hit_rate_3pct:.1f}% hit rate, {stop_rate:.1f}% stop rate")
        
        # CRITICAL: Automatic adjustments based on performance
        adjustments_made = []
        
        # 1. EMERGENCY STRATEGY DISABLING - Disable strategies with 100+ failures
        emergency_actions = await self._check_emergency_strategy_disabling(strategies)
        adjustments_made.extend(emergency_actions)
        
        # 2. CRITERIA ADJUSTMENT BASED ON HIT RATE - Loosen if hit rate is terrible
        criteria_actions = await self._adjust_criteria_based_on_hit_rate(hit_rate_3pct, total_signals)
        adjustments_made.extend(criteria_actions)
        
        # 3. STOP LOSS ADJUSTMENT - Widen stops if too many signals getting stopped
        stop_loss_actions = await self._adjust_stop_losses_based_on_stop_rate(stop_rate, total_signals)
        adjustments_made.extend(stop_loss_actions)
        
        # 4. CONFIDENCE RECALIBRATION - Adjust confidence if it's overestimating
        confidence_actions = await self._recalibrate_confidence(hit_rate_3pct, total_signals)
        adjustments_made.extend(confidence_actions)
        
        # 5. CATASTROPHIC FAILURE CHECK - Emergency reset if too many total failures
        if await self._check_catastrophic_failure():
            await self.force_emergency_recalibration()
            adjustments_made.append("🚨 CATASTROPHIC FAILURE - EMERGENCY SYSTEM RESET")
        
        # Apply all adjustments to live system
        if adjustments_made:
            await self._apply_criteria_to_live_system()
            self.learning_iterations += 1
            
            logger.info(f"🧠 LEARNING ITERATION {self.learning_iterations} COMPLETED:")
            for action in adjustments_made:
                logger.info(f"   • {action}")
                
            # Record the learning action
            learning_action = LearningAction(
                timestamp=datetime.now(),
                action_type="automated_adjustment",
                reason=f"Performance: {hit_rate_3pct:.1f}% hit rate, {total_signals} signals",
                old_value="previous_criteria",
                new_value=asdict(self.criteria),
                performance_trigger=overall
            )
            self.learning_actions.append(learning_action)
            
            # Keep only last 100 actions to prevent memory bloat
            if len(self.learning_actions) > 100:
                self.learning_actions = self.learning_actions[-100:]
        else:
            logger.debug("🔍 No adjustments needed this iteration")
    
    async def _check_emergency_strategy_disabling(self, strategies: List[Dict]) -> List[str]:
        """Emergency disabling of consistently failing strategies"""
        actions = []
        
        for strategy_data in strategies:
            strategy_name = strategy_data['strategy']
            total = strategy_data['total']
            hit_3pct = strategy_data['hit_3pct']
            
            # Skip if already disabled
            if strategy_name in self.criteria.disabled_strategies:
                continue
                
            # EMERGENCY: Disable strategy after 100+ signals with 0% hit rate
            if total >= self.emergency_failure_threshold and hit_3pct == 0:
                self.criteria.disabled_strategies.append(strategy_name)
                actions.append(f"🚨 EMERGENCY DISABLED strategy '{strategy_name}' - 0% hit rate over {total} signals")
                logger.error(f"🚨 EMERGENCY: Disabling strategy '{strategy_name}' due to {total} consecutive failures")
                
        return actions
    
    async def _adjust_criteria_based_on_hit_rate(self, hit_rate_3pct: float, total_signals: int) -> List[str]:
        """Adjust criteria based on hit rate performance"""
        actions = []
        
        # Only adjust if we have enough data
        if total_signals < 10:
            return actions
            
        # CRITICAL: If hit rate is terrible (like the current 0%), loosen criteria
        if hit_rate_3pct < 5:  # Less than 5% hit rate is terrible
            old_confidence = self.criteria.min_confidence
            old_volatility = self.criteria.max_volatility
            
            # Significantly loosen confidence requirement
            self.criteria.min_confidence = max(0.3, self.criteria.min_confidence - 0.05)
            
            # Allow much higher volatility
            self.criteria.max_volatility = min(0.15, self.criteria.max_volatility + 0.01)
            
            # Loosen risk/reward requirement
            old_rr = self.criteria.min_risk_reward
            self.criteria.min_risk_reward = max(1.0, self.criteria.min_risk_reward - 0.1)
            
            actions.append(f"LOOSENED criteria due to {hit_rate_3pct:.1f}% hit rate: confidence {old_confidence:.2f}→{self.criteria.min_confidence:.2f}, volatility {old_volatility:.2f}→{self.criteria.max_volatility:.2f}, R:R {old_rr:.1f}→{self.criteria.min_risk_reward:.1f}")
            
        # If hit rate is good but very few signals, tighten criteria slightly
        elif hit_rate_3pct > 50 and total_signals < 5:
            old_confidence = self.criteria.min_confidence
            self.criteria.min_confidence = min(0.9, self.criteria.min_confidence + 0.02)
            actions.append(f"TIGHTENED confidence due to good hit rate with few signals: {old_confidence:.2f}→{self.criteria.min_confidence:.2f}")
            
        return actions
    
    async def _adjust_stop_losses_based_on_stop_rate(self, stop_rate: float, total_signals: int) -> List[str]:
        """Adjust stop loss tightness based on how many signals hit stop loss"""
        actions = []
        
        if total_signals < 10:
            return actions
            
        # If too many signals hitting stop loss, widen the stops
        if stop_rate > 70:  # More than 70% hit stop loss
            old_sl = self.criteria.stop_loss_tightness
            self.criteria.stop_loss_tightness = min(0.05, self.criteria.stop_loss_tightness + 0.005)
            actions.append(f"WIDENED stop losses due to {stop_rate:.1f}% stop rate: {old_sl:.3f}→{self.criteria.stop_loss_tightness:.3f}")
            
        # If very few signals hitting stop loss, can tighten stops slightly
        elif stop_rate < 20 and stop_rate > 0:
            old_sl = self.criteria.stop_loss_tightness
            self.criteria.stop_loss_tightness = max(0.015, self.criteria.stop_loss_tightness - 0.002)
            actions.append(f"TIGHTENED stop losses due to low {stop_rate:.1f}% stop rate: {old_sl:.3f}→{self.criteria.stop_loss_tightness:.3f}")
            
        return actions
    
    async def _recalibrate_confidence(self, hit_rate_3pct: float, total_signals: int) -> List[str]:
        """Recalibrate confidence scoring based on actual performance"""
        actions = []
        
        if total_signals < 50:
            return actions
            
        # If actual hit rate is much lower than what confidence scores suggest
        if hit_rate_3pct < 30:  # Confidence scores are clearly overestimating
            actions.append(f"FLAGGED confidence overestimation - actual hit rate {hit_rate_3pct:.1f}% suggests confidence scores are too high")
            
            # This would integrate with confidence calibrator to adjust scoring
            # For now, just flag the issue
            
        return actions
    
    async def _check_catastrophic_failure(self) -> bool:
        """Check if we have catastrophic failure requiring emergency reset"""
        
        # Get longer-term performance (7 days)
        performance = await self.signal_tracker.get_performance_summary(days_back=7)
        
        if not performance or not performance.get('overall'):
            return False
            
        overall = performance['overall']
        total_signals = overall.get('total_signals', 0)
        hit_rate_3pct = overall.get('signals_3pct', 0) / max(total_signals, 1) * 100
        
        # Catastrophic failure: 500+ signals with less than 5% hit rate
        if total_signals >= self.catastrophic_failure_threshold and hit_rate_3pct < 5:
            logger.error(f"🚨 CATASTROPHIC FAILURE DETECTED: {total_signals} signals with {hit_rate_3pct:.1f}% hit rate")
            return True
            
        return False
    
    async def _apply_criteria_to_live_system(self):
        """Apply learned criteria to live signal generation system"""
        
        try:
            # Try to update opportunity manager with new criteria
            if hasattr(self.opportunity_manager, 'update_learning_criteria'):
                await self.opportunity_manager.update_learning_criteria(self.criteria)
                logger.info("✅ Applied learning criteria to opportunity manager")
            else:
                logger.warning("⚠️ OpportunityManager doesn't support learning criteria updates yet")
                
            # Save criteria to file for persistence
            await self._save_criteria_to_file()
            
        except Exception as e:
            logger.error(f"❌ Failed to apply criteria to live system: {e}")
    
    async def _save_criteria_to_file(self):
        """Save current criteria to file for persistence across restarts"""
        try:
            criteria_file = "data/learning_criteria.json"
            criteria_dict = asdict(self.criteria)
            criteria_dict['last_updated'] = datetime.now().isoformat()
            criteria_dict['learning_iterations'] = self.learning_iterations
            criteria_dict['total_actions'] = len(self.learning_actions)
            
            with open(criteria_file, 'w') as f:
                json.dump(criteria_dict, f, indent=2)
                
            logger.debug("💾 Saved learning criteria to file")
                
        except Exception as e:
            logger.error(f"❌ Failed to save criteria: {e}")
    
    async def load_criteria_from_file(self):
        """Load previously saved criteria"""
        try:
            criteria_file = "data/learning_criteria.json"
            if not os.path.exists(criteria_file):
                logger.info("📄 No saved learning criteria found, using defaults")
                return
                
            with open(criteria_file, 'r') as f:
                data = json.load(f)
                
            # Restore criteria
            self.criteria.min_confidence = data.get('min_confidence', 0.6)
            self.criteria.min_risk_reward = data.get('min_risk_reward', 1.2)
            self.criteria.max_volatility = data.get('max_volatility', 0.08)
            self.criteria.stop_loss_tightness = data.get('stop_loss_tightness', 0.02)
            self.criteria.take_profit_distance = data.get('take_profit_distance', 0.03)
            self.criteria.min_volume_ratio = data.get('min_volume_ratio', 1.05)
            self.criteria.disabled_strategies = data.get('disabled_strategies', [])
            
            self.learning_iterations = data.get('learning_iterations', 0)
            
            logger.info(f"✅ Loaded learning criteria from file (iteration {self.learning_iterations})")
            if self.criteria.disabled_strategies:
                logger.info(f"📋 Disabled strategies: {self.criteria.disabled_strategies}")
            
        except Exception as e:
            logger.error(f"❌ Failed to load criteria: {e}")
    
    def get_learning_status(self) -> Dict[str, Any]:
        """Get current learning status for API/debugging"""
        return {
            "enabled": self.enabled,
            "learning_iterations": self.learning_iterations,
            "current_criteria": asdict(self.criteria),
            "recent_actions": [
                {
                    "timestamp": action.timestamp.isoformat(),
                    "action_type": action.action_type,
                    "reason": action.reason,
                    "new_value": action.new_value
                } 
                for action in self.learning_actions[-10:]  # Last 10 actions
            ],
            "disabled_strategies_count": len(self.criteria.disabled_strategies),
            "disabled_strategies": self.criteria.disabled_strategies,
            "last_optimization": self.last_optimization.isoformat() if self.last_optimization else None,
            "task_running": self.learning_task is not None and not self.learning_task.done()
        }
    
    async def force_emergency_recalibration(self):
        """Force emergency recalibration due to catastrophic performance"""
        logger.error("🚨 CATASTROPHIC PERFORMANCE DETECTED - FORCING EMERGENCY RECALIBRATION")
        
        # Store old criteria for logging
        old_criteria = asdict(self.criteria)
        
        # Reset criteria to much more liberal values
        self.criteria.min_confidence = 0.4          # Very low confidence requirement
        self.criteria.max_volatility = 0.12         # Allow high volatility
        self.criteria.stop_loss_tightness = 0.04    # Much wider stops
        self.criteria.min_risk_reward = 1.0         # Lower R:R requirement
        self.criteria.min_volume_ratio = 0.8        # Lower volume requirement
        
        # Clear disabled strategies (give them another chance with new criteria)
        disabled_count = len(self.criteria.disabled_strategies)
        self.criteria.disabled_strategies = []
        
        # Apply immediately
        await self._apply_criteria_to_live_system()
        
        logger.error(f"🔄 EMERGENCY RESET COMPLETE:")
        logger.error(f"   • Loosened all criteria dramatically")
        logger.error(f"   • Re-enabled {disabled_count} previously disabled strategies")
        logger.error(f"   • System will restart learning with liberal criteria")
        
        # Record emergency action
        emergency_action = LearningAction(
            timestamp=datetime.now(),
            action_type="emergency_recalibration",
            reason="Catastrophic performance triggered emergency reset",
            old_value=old_criteria,
            new_value=asdict(self.criteria),
            performance_trigger={"type": "catastrophic_failure"}
        )
        self.learning_actions.append(emergency_action)
        
        # Reset iteration counter
        self.learning_iterations = 0
        self.last_optimization = datetime.now()
    
    async def manual_force_learning_iteration(self):
        """Manually trigger a learning iteration for testing"""
        logger.info("🔧 Manual learning iteration triggered")
        await self._perform_learning_iteration()
        return self.get_learning_status() 