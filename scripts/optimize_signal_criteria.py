#!/usr/bin/env python3
"""
🎯 Signal Criteria Optimizer

This script analyzes signal performance and suggests criteria adjustments
to improve hit rates and golden signal generation.

Usage:
    python scripts/optimize_signal_criteria.py
    python scripts/optimize_signal_criteria.py --strategy trend_following_stable
    python scripts/optimize_signal_criteria.py --days 30 --auto-apply
"""

import asyncio
import argparse
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.signals.enhanced_signal_tracker import enhanced_signal_tracker

class CriteriaOptimizer:
    """Optimize signal criteria based on performance analysis"""
    
    def __init__(self):
        self.current_criteria = {
            'min_confidence': 0.6,
            'min_risk_reward': 1.2,
            'max_volatility': 0.08,
            'min_volume_ratio': 1.05,
            'min_market_move': 0.0015,  # 0.15%
            'max_market_move': 0.02     # 2.0%
        }
    
    async def analyze_performance(self, days_back: int = 7, strategy: str = None) -> Dict[str, Any]:
        """Analyze signal performance and suggest optimizations"""
        
        print(f"🔍 Analyzing signal performance for last {days_back} days...")
        if strategy:
            print(f"📊 Focusing on strategy: {strategy}")
        
        # Get performance data
        performance = await enhanced_signal_tracker.get_performance_summary(days_back)
        
        if not performance or not performance.get('overall'):
            print("❌ No performance data available")
            return {}
        
        overall = performance['overall']
        strategies = performance.get('by_strategy', [])
        
        # Overall analysis
        total_signals = overall['total_signals']
        if total_signals == 0:
            print("❌ No signals found in the specified period")
            return {}
        
        hit_rate_3pct = (overall['signals_3pct'] / total_signals) * 100
        hit_rate_5pct = (overall['signals_5pct'] / total_signals) * 100
        stop_rate = (overall['signals_stopped'] / total_signals) * 100
        golden_rate = (overall['golden_signals'] / total_signals) * 100
        
        print(f"\n📈 Overall Performance ({total_signals} signals):")
        print(f"   3% Hit Rate: {hit_rate_3pct:.1f}%")
        print(f"   5% Hit Rate: {hit_rate_5pct:.1f}%")
        print(f"   Stop Loss Rate: {stop_rate:.1f}%")
        print(f"   Golden Signal Rate: {golden_rate:.1f}%")
        print(f"   Avg Time to 3%: {overall['avg_time_to_3pct']:.1f} minutes")
        
        # Strategy-specific analysis
        if strategy:
            strategy_data = next((s for s in strategies if s['strategy'] == strategy), None)
            if strategy_data:
                self._analyze_strategy_performance(strategy_data)
            else:
                print(f"⚠️ No data found for strategy: {strategy}")
        else:
            print(f"\n🎯 Strategy Performance:")
            for strat in sorted(strategies, key=lambda x: x['golden'], reverse=True)[:5]:
                hit_rate = (strat['hit_3pct'] / max(strat['total'], 1)) * 100
                golden_pct = (strat['golden'] / max(strat['total'], 1)) * 100
                print(f"   {strat['strategy']}: {hit_rate:.1f}% hit rate, {golden_pct:.1f}% golden ({strat['total']} signals)")
        
        # Generate optimization suggestions
        suggestions = self._generate_suggestions(overall, strategies, strategy)
        
        return {
            'performance': performance,
            'suggestions': suggestions,
            'current_criteria': self.current_criteria
        }
    
    def _analyze_strategy_performance(self, strategy_data: Dict):
        """Detailed analysis of a specific strategy"""
        total = strategy_data['total']
        hit_3pct = strategy_data['hit_3pct']
        golden = strategy_data['golden']
        
        hit_rate = (hit_3pct / max(total, 1)) * 100
        golden_rate = (golden / max(total, 1)) * 100
        avg_time = strategy_data.get('avg_time_to_3pct', 0)
        
        print(f"\n🎯 {strategy_data['strategy']} Performance:")
        print(f"   Total Signals: {total}")
        print(f"   3% Hit Rate: {hit_rate:.1f}%")
        print(f"   Golden Signals: {golden} ({golden_rate:.1f}%)")
        print(f"   Avg Time to 3%: {avg_time:.1f} minutes")
        
        # Performance assessment
        if hit_rate > 70:
            print("   ✅ Excellent hit rate - consider tightening criteria for quality")
        elif hit_rate > 50:
            print("   👍 Good hit rate - minor adjustments may help")
        elif hit_rate > 30:
            print("   ⚠️ Moderate hit rate - consider loosening criteria")
        else:
            print("   🚨 Low hit rate - significant criteria adjustment needed")
        
        if golden_rate > 15:
            print("   🌟 Excellent golden signal rate")
        elif golden_rate > 10:
            print("   ✅ Good golden signal rate")
        elif golden_rate > 5:
            print("   👍 Moderate golden signal rate - room for improvement")
        else:
            print("   🚨 Low golden signal rate - review entry timing")
    
    def _generate_suggestions(self, overall: Dict, strategies: List[Dict], target_strategy: str = None) -> List[Dict]:
        """Generate optimization suggestions based on performance"""
        suggestions = []
        
        total_signals = overall['total_signals']
        hit_rate_3pct = (overall['signals_3pct'] / max(total_signals, 1)) * 100
        golden_rate = (overall['golden_signals'] / max(total_signals, 1)) * 100
        
        # Overall suggestions
        if hit_rate_3pct < 25:
            suggestions.append({
                'type': 'loosen_criteria',
                'priority': 'high',
                'reason': f'Very low 3% hit rate ({hit_rate_3pct:.1f}%)',
                'actions': [
                    'Lower min_confidence from 0.6 to 0.5',
                    'Increase max_volatility from 8% to 10%',
                    'Lower min_volume_ratio from 1.05 to 1.03',
                    'Widen market move range: 0.1% - 2.5%'
                ],
                'expected_impact': 'Increase signal quantity, may slightly reduce quality'
            })
        elif hit_rate_3pct < 40:
            suggestions.append({
                'type': 'moderate_loosen',
                'priority': 'medium',
                'reason': f'Low 3% hit rate ({hit_rate_3pct:.1f}%)',
                'actions': [
                    'Lower min_confidence from 0.6 to 0.55',
                    'Increase max_volatility from 8% to 9%',
                    'Adjust market move range: 0.12% - 2.2%'
                ],
                'expected_impact': 'Moderate increase in signal quantity'
            })
        elif hit_rate_3pct > 70:
            suggestions.append({
                'type': 'tighten_criteria',
                'priority': 'medium',
                'reason': f'Very high 3% hit rate ({hit_rate_3pct:.1f}%)',
                'actions': [
                    'Raise min_confidence from 0.6 to 0.7',
                    'Increase min_risk_reward from 1.2 to 1.4',
                    'Tighten max_volatility from 8% to 6%'
                ],
                'expected_impact': 'Focus on highest quality signals'
            })
        
        # Golden signal optimization
        if golden_rate < 5:
            suggestions.append({
                'type': 'optimize_golden',
                'priority': 'high',
                'reason': f'Very low golden signal rate ({golden_rate:.1f}%)',
                'actions': [
                    'Review entry timing - consider earlier entries',
                    'Optimize risk/reward ratios for faster moves',
                    'Focus on higher momentum setups',
                    'Consider tighter stop losses for higher position sizes'
                ],
                'expected_impact': 'Increase quick 3% gainers'
            })
        elif golden_rate < 10:
            suggestions.append({
                'type': 'improve_golden',
                'priority': 'medium',
                'reason': f'Low golden signal rate ({golden_rate:.1f}%)',
                'actions': [
                    'Fine-tune entry timing',
                    'Consider momentum indicators for entry',
                    'Review best performing symbols for patterns'
                ],
                'expected_impact': 'Moderate improvement in golden signals'
            })
        
        # Strategy-specific suggestions
        if target_strategy and strategies:
            strategy_data = next((s for s in strategies if s['strategy'] == target_strategy), None)
            if strategy_data:
                suggestions.extend(self._get_strategy_specific_suggestions(strategy_data))
        
        return suggestions
    
    def _get_strategy_specific_suggestions(self, strategy_data: Dict) -> List[Dict]:
        """Get suggestions specific to a strategy"""
        suggestions = []
        
        total = strategy_data['total']
        hit_rate = (strategy_data['hit_3pct'] / max(total, 1)) * 100
        golden_rate = (strategy_data['golden'] / max(total, 1)) * 100
        
        strategy_name = strategy_data['strategy']
        
        if 'trend_following' in strategy_name.lower():
            if hit_rate < 30:
                suggestions.append({
                    'type': 'trend_following_optimization',
                    'priority': 'high',
                    'reason': f'Trend following strategy underperforming ({hit_rate:.1f}%)',
                    'actions': [
                        'Consider longer timeframe for trend confirmation',
                        'Add momentum filters',
                        'Reduce noise with higher confidence threshold for trend signals'
                    ],
                    'expected_impact': 'Better trend signal quality'
                })
        
        elif 'mean_reversion' in strategy_name.lower():
            if golden_rate < 8:
                suggestions.append({
                    'type': 'mean_reversion_optimization',
                    'priority': 'medium',
                    'reason': f'Mean reversion not generating quick gains ({golden_rate:.1f}%)',
                    'actions': [
                        'Tighten reversal criteria for faster bounces',
                        'Add volume spike confirmation',
                        'Consider oversold/overbought levels'
                    ],
                    'expected_impact': 'Faster mean reversion signals'
                })
        
        elif 'breakout' in strategy_name.lower():
            if hit_rate < 35:
                suggestions.append({
                    'type': 'breakout_optimization',
                    'priority': 'high',
                    'reason': f'Breakout strategy false signals ({hit_rate:.1f}%)',
                    'actions': [
                        'Add volume confirmation for breakouts',
                        'Require higher timeframe alignment',
                        'Filter out low volatility breakouts'
                    ],
                    'expected_impact': 'Reduce false breakout signals'
                })
        
        return suggestions
    
    async def apply_suggestions(self, suggestions: List[Dict], auto_apply: bool = False):
        """Apply optimization suggestions"""
        
        if not suggestions:
            print("✅ No optimization suggestions needed")
            return
        
        print(f"\n🎯 Optimization Suggestions:")
        print("=" * 50)
        
        for i, suggestion in enumerate(suggestions, 1):
            priority_emoji = "🚨" if suggestion['priority'] == 'high' else "⚠️" if suggestion['priority'] == 'medium' else "💡"
            print(f"\n{priority_emoji} Suggestion {i}: {suggestion['type'].title()}")
            print(f"   Reason: {suggestion['reason']}")
            print(f"   Expected Impact: {suggestion['expected_impact']}")
            print(f"   Actions:")
            for action in suggestion['actions']:
                print(f"     • {action}")
        
        if auto_apply:
            print(f"\n🔧 Auto-applying high priority suggestions...")
            high_priority = [s for s in suggestions if s['priority'] == 'high']
            for suggestion in high_priority:
                print(f"   Applying: {suggestion['type']}")
                # Here you would integrate with your signal generation config
                # For now, just show what would be applied
        else:
            print(f"\n💡 To apply these suggestions:")
            print(f"   1. Review the recommendations above")
            print(f"   2. Manually adjust your signal generation criteria")
            print(f"   3. Run this script again in a few days to measure impact")
            print(f"   4. Use --auto-apply flag for automatic high-priority adjustments")
    
    async def run_optimization(self, days_back: int = 7, strategy: str = None, auto_apply: bool = False):
        """Run the complete optimization process"""
        
        print("🎯 Signal Criteria Optimizer")
        print("=" * 40)
        
        try:
            # Initialize tracker
            await enhanced_signal_tracker.initialize()
            
            # Analyze performance
            analysis = await self.analyze_performance(days_back, strategy)
            
            if not analysis:
                return
            
            # Apply suggestions
            await self.apply_suggestions(analysis['suggestions'], auto_apply)
            
            print(f"\n✅ Optimization analysis complete!")
            print(f"📊 Run the signals for a few days, then re-run this script to measure improvement")
            
        except Exception as e:
            print(f"❌ Optimization failed: {e}")
        finally:
            await enhanced_signal_tracker.close()

async def main():
    parser = argparse.ArgumentParser(description='Optimize signal criteria based on performance')
    parser.add_argument('--days', type=int, default=7, help='Days of history to analyze (default: 7)')
    parser.add_argument('--strategy', type=str, help='Focus on specific strategy')
    parser.add_argument('--auto-apply', action='store_true', help='Auto-apply high priority suggestions')
    
    args = parser.parse_args()
    
    optimizer = CriteriaOptimizer()
    await optimizer.run_optimization(args.days, args.strategy, args.auto_apply)

if __name__ == "__main__":
    asyncio.run(main()) 