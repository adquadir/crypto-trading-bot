#!/usr/bin/env python3
"""
🔍 Signal Quality Checker

Check the current quality and reliability of signals before trading.
"""

import asyncio
import sys
import json
from datetime import datetime
from typing import Dict, List

# Add project root to path
sys.path.append('.')

from src.opportunity.opportunity_manager import OpportunityManager
from src.utils.config import load_config

class SignalQualityChecker:
    """Check signal quality before trading"""
    
    def __init__(self):
        self.quality_thresholds = {
            'min_confidence': 0.8,      # Require 80%+ confidence
            'min_risk_reward': 1.5,     # Require 1.5:1 R:R minimum
            'max_volatility': 0.06,     # Max 6% volatility
            'min_volume_ratio': 1.2,    # Volume must be 20%+ above average
            'max_spread': 0.002         # Max 0.2% spread
        }
    
    async def check_current_signals(self):
        """Check the quality of current signals"""
        
        print("🔍 Signal Quality Assessment")
        print("=" * 40)
        
        try:
            # Initialize opportunity manager
            config = load_config()
            om = OpportunityManager(config)
            await om.initialize()
            
            # Get current signals
            signals = om.get_opportunities()
            
            if not signals:
                print("❌ No signals found")
                return
            
            print(f"📊 Found {len(signals)} signals to analyze")
            
            # Analyze each signal
            high_quality = []
            medium_quality = []
            low_quality = []
            
            for signal in signals:
                quality_score, quality_level, issues = self._assess_signal_quality(signal)
                
                if quality_level == 'HIGH':
                    high_quality.append((signal, quality_score, issues))
                elif quality_level == 'MEDIUM':
                    medium_quality.append((signal, quality_score, issues))
                else:
                    low_quality.append((signal, quality_score, issues))
            
            # Report results
            self._print_quality_report(high_quality, medium_quality, low_quality)
            
            # Recommendations
            self._print_trading_recommendations(high_quality, medium_quality, low_quality)
            
        except Exception as e:
            print(f"❌ Quality check failed: {e}")
            import traceback
            traceback.print_exc()
    
    def _assess_signal_quality(self, signal: Dict) -> tuple:
        """Assess individual signal quality"""
        
        issues = []
        quality_points = 0
        max_points = 10
        
        # Check confidence
        confidence = signal.get('confidence', 0)
        if confidence >= self.quality_thresholds['min_confidence']:
            quality_points += 2
        elif confidence >= 0.7:
            quality_points += 1
            issues.append(f"Moderate confidence ({confidence:.1%})")
        else:
            issues.append(f"Low confidence ({confidence:.1%})")
        
        # Check risk/reward ratio
        entry = signal.get('entry_price', signal.get('entry', 0))
        tp = signal.get('take_profit', 0)
        sl = signal.get('stop_loss', 0)
        
        if entry and tp and sl:
            risk = abs(entry - sl)
            reward = abs(tp - entry)
            rr_ratio = reward / risk if risk > 0 else 0
            
            if rr_ratio >= self.quality_thresholds['min_risk_reward']:
                quality_points += 2
            elif rr_ratio >= 1.2:
                quality_points += 1
                issues.append(f"Low R:R ratio ({rr_ratio:.2f})")
            else:
                issues.append(f"Poor R:R ratio ({rr_ratio:.2f})")
        else:
            issues.append("Missing price levels")
        
        # Check volatility
        volatility = signal.get('volatility', 0)
        if volatility <= self.quality_thresholds['max_volatility']:
            quality_points += 2
        elif volatility <= 0.08:
            quality_points += 1
            issues.append(f"High volatility ({volatility:.1%})")
        else:
            issues.append(f"Very high volatility ({volatility:.1%})")
        
        # Check volume
        volume_ratio = signal.get('volume_ratio', 0)
        if volume_ratio >= self.quality_thresholds['min_volume_ratio']:
            quality_points += 2
        elif volume_ratio >= 1.0:
            quality_points += 1
            issues.append(f"Low volume surge ({volume_ratio:.2f}x)")
        else:
            issues.append(f"No volume surge ({volume_ratio:.2f}x)")
        
        # Check market conditions
        market_conditions = signal.get('market_conditions', {})
        if market_conditions.get('trend_strength', 0) > 0.6:
            quality_points += 1
        if market_conditions.get('momentum', 0) > 0.5:
            quality_points += 1
        
        # Determine quality level
        quality_score = (quality_points / max_points) * 100
        
        if quality_score >= 80:
            quality_level = 'HIGH'
        elif quality_score >= 60:
            quality_level = 'MEDIUM'
        else:
            quality_level = 'LOW'
        
        return quality_score, quality_level, issues
    
    def _print_quality_report(self, high_quality, medium_quality, low_quality):
        """Print quality assessment report"""
        
        total_signals = len(high_quality) + len(medium_quality) + len(low_quality)
        
        print(f"\n🎯 Quality Assessment Results:")
        print(f"   🟢 HIGH Quality: {len(high_quality)}/{total_signals} ({len(high_quality)/total_signals*100:.1f}%)")
        print(f"   🟡 MEDIUM Quality: {len(medium_quality)}/{total_signals} ({len(medium_quality)/total_signals*100:.1f}%)")
        print(f"   🔴 LOW Quality: {len(low_quality)}/{total_signals} ({len(low_quality)/total_signals*100:.1f}%)")
        
        # Show high quality signals
        if high_quality:
            print(f"\n🟢 HIGH QUALITY SIGNALS (Trade-ready):")
            for i, (signal, score, issues) in enumerate(high_quality[:5], 1):
                symbol = signal.get('symbol', 'Unknown')
                strategy = signal.get('strategy', 'Unknown')
                direction = signal.get('direction', 'Unknown')
                confidence = signal.get('confidence', 0)
                print(f"   {i}. {symbol} {direction} - {strategy} (Confidence: {confidence:.1%}, Score: {score:.1f})")
                if issues:
                    print(f"      Minor issues: {', '.join(issues)}")
        
        # Show medium quality signals
        if medium_quality:
            print(f"\n🟡 MEDIUM QUALITY SIGNALS (Proceed with caution):")
            for i, (signal, score, issues) in enumerate(medium_quality[:3], 1):
                symbol = signal.get('symbol', 'Unknown')
                strategy = signal.get('strategy', 'Unknown')
                direction = signal.get('direction', 'Unknown')
                confidence = signal.get('confidence', 0)
                print(f"   {i}. {symbol} {direction} - {strategy} (Confidence: {confidence:.1%}, Score: {score:.1f})")
                if issues:
                    print(f"      Issues: {', '.join(issues)}")
        
        # Show worst signals
        if low_quality:
            print(f"\n🔴 LOW QUALITY SIGNALS (Avoid for now):")
            for i, (signal, score, issues) in enumerate(low_quality[:3], 1):
                symbol = signal.get('symbol', 'Unknown')
                strategy = signal.get('strategy', 'Unknown')
                direction = signal.get('direction', 'Unknown')
                confidence = signal.get('confidence', 0)
                print(f"   {i}. {symbol} {direction} - {strategy} (Confidence: {confidence:.1%}, Score: {score:.1f})")
                if issues:
                    print(f"      Major issues: {', '.join(issues)}")
    
    def _print_trading_recommendations(self, high_quality, medium_quality, low_quality):
        """Print trading recommendations"""
        
        print(f"\n💡 TRADING RECOMMENDATIONS:")
        
        if len(high_quality) >= 3:
            print(f"✅ {len(high_quality)} high-quality signals available")
            print(f"   → Start with these signals using small position sizes")
            print(f"   → Risk 0.5% per trade ($50) for validation")
        elif len(high_quality) >= 1:
            print(f"⚠️ Only {len(high_quality)} high-quality signal(s) available")
            print(f"   → Consider waiting for more high-quality setups")
            print(f"   → Or test with very small amounts ($20-30 risk)")
        else:
            print(f"🚨 No high-quality signals found")
            print(f"   → Do NOT trade right now")
            print(f"   → Wait for better market conditions")
        
        total_signals = len(high_quality) + len(medium_quality) + len(low_quality)
        quality_ratio = len(high_quality) / total_signals * 100 if total_signals > 0 else 0
        
        print(f"\n📊 Overall Market Assessment:")
        if quality_ratio >= 30:
            print(f"🟢 Market conditions: GOOD ({quality_ratio:.1f}% high-quality)")
            print(f"   → Favorable for selective trading")
        elif quality_ratio >= 15:
            print(f"🟡 Market conditions: MODERATE ({quality_ratio:.1f}% high-quality)")
            print(f"   → Be very selective, reduce position sizes")
        else:
            print(f"🔴 Market conditions: POOR ({quality_ratio:.1f}% high-quality)")
            print(f"   → Consider waiting for better conditions")
        
        print(f"\n🎯 Next Steps:")
        print(f"1. Only trade HIGH quality signals for now")
        print(f"2. Start with 0.5% risk per trade ($50 max)")
        print(f"3. Track results for 1 week minimum")
        print(f"4. Increase position sizes only after proven success")
        print(f"5. Run this script daily to assess signal quality")

async def main():
    """Run signal quality check"""
    checker = SignalQualityChecker()
    await checker.check_current_signals()

if __name__ == "__main__":
    asyncio.run(main()) 