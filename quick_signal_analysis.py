#!/usr/bin/env python3
"""
Quick Signal Profitability Analysis
Estimates win rates and profitability based on current signal characteristics.
"""

import requests
import json
import statistics
import random

def analyze_current_signals():
    """Analyze current signals for profitability estimation."""
    try:
        print("🎯 CRYPTO TRADING BOT - SIGNAL ACCURACY ANALYSIS")
        print("=" * 55)
        
        # Get current signals
        response = requests.get('http://localhost:8000/api/v1/trading/opportunities')
        data = response.json()
        signals = data.get('data', [])
        
        if not signals:
            print("❌ No signals available for analysis")
            return
        
        print(f"📊 Analyzing {len(signals)} active trading signals...")
        
        # Analyze signal characteristics
        confidences = [s.get('confidence', 0) for s in signals]
        risk_rewards = [s.get('risk_reward', 0) for s in signals]
        strategies = [s.get('strategy', 'unknown') for s in signals]
        directions = [s.get('direction', 'unknown') for s in signals]
        
        # Calculate statistics
        avg_confidence = statistics.mean(confidences)
        avg_risk_reward = statistics.mean(risk_rewards)
        high_confidence_count = len([c for c in confidences if c > 0.7])
        
        # Strategy distribution
        strategy_counts = {}
        for strategy in strategies:
            strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
        
        # Direction distribution
        long_signals = len([d for d in directions if d == 'LONG'])
        short_signals = len([d for d in directions if d == 'SHORT'])
        
        print(f"\n📈 SIGNAL QUALITY METRICS:")
        print(f"   Total Signals:          {len(signals)}")
        print(f"   Average Confidence:     {avg_confidence:.1%}")
        print(f"   Average Risk/Reward:    {avg_risk_reward:.2f}:1")
        print(f"   High Confidence (>70%): {high_confidence_count} ({high_confidence_count/len(signals)*100:.1f}%)")
        print(f"   LONG Signals:           {long_signals} ({long_signals/len(signals)*100:.1f}%)")
        print(f"   SHORT Signals:          {short_signals} ({short_signals/len(signals)*100:.1f}%)")
        
        print(f"\n🔧 STRATEGY DISTRIBUTION:")
        for strategy, count in strategy_counts.items():
            percentage = (count / len(signals)) * 100
            print(f"   {strategy:20s}: {count:3d} signals ({percentage:5.1f}%)")
        
        # Estimate profitability based on signal characteristics
        estimated_win_rate = estimate_win_rate(avg_confidence, avg_risk_reward, strategy_counts, len(signals))
        estimated_profit_factor = estimate_profit_factor(avg_risk_reward, estimated_win_rate)
        estimated_monthly_return = estimate_monthly_return(estimated_win_rate, avg_risk_reward, len(signals))
        
        print(f"\n💰 PROFITABILITY ESTIMATES:")
        print(f"   Estimated Win Rate:     {estimated_win_rate:.1f}%")
        print(f"   Estimated Profit Factor: {estimated_profit_factor:.2f}")
        print(f"   Est. Monthly Return:    {estimated_monthly_return:+.1f}%")
        
        # Risk assessment
        print(f"\n⚠️  RISK ASSESSMENT:")
        assess_risk_level(avg_confidence, avg_risk_reward, estimated_win_rate)
        
        # Recommendations
        print(f"\n💡 TRADING RECOMMENDATIONS:")
        provide_recommendations(avg_confidence, avg_risk_reward, estimated_win_rate, high_confidence_count, len(signals))
        
        # Sample high-quality signals
        print(f"\n🌟 TOP QUALITY SIGNALS (Confidence > 75%):")
        top_signals = [s for s in signals if s.get('confidence', 0) > 0.75][:5]
        
        for i, signal in enumerate(top_signals, 1):
            symbol = signal.get('symbol', 'N/A')
            direction = signal.get('direction', 'N/A')
            confidence = signal.get('confidence', 0)
            risk_reward = signal.get('risk_reward', 0)
            entry = signal.get('entry_price', 0)
            
            print(f"   [{i}] {symbol:10s} {direction:5s} | Conf: {confidence:.1%} | R:R: {risk_reward:.2f} | Entry: ${entry:,.2f}")
        
        if not top_signals:
            print("   No signals with >75% confidence currently available")
        
    except Exception as e:
        print(f"❌ Analysis failed: {e}")

def estimate_win_rate(avg_confidence, avg_risk_reward, strategy_counts, total_signals):
    """Estimate win rate based on signal characteristics."""
    
    # Base win rate from confidence (30-70% range)
    base_win_rate = 30 + (avg_confidence * 40)
    
    # Strategy adjustments
    strategy_adjustments = {
        'trend_following_stable': 5,   # +5% for trend following
        'mean_reversion_stable': -2,   # -2% for mean reversion
        'breakout_stable': 3,          # +3% for breakouts
        'stable_fallback': -5          # -5% for fallback signals
    }
    
    # Calculate weighted strategy adjustment
    strategy_adjustment = 0
    for strategy, count in strategy_counts.items():
        weight = count / total_signals
        adjustment = strategy_adjustments.get(strategy, 0)
        strategy_adjustment += weight * adjustment
    
    # Risk/reward adjustment (better R:R slightly improves win rate)
    rr_adjustment = min(3, (avg_risk_reward - 1) * 2)
    
    # Final win rate
    estimated_win_rate = base_win_rate + strategy_adjustment + rr_adjustment
    
    # Clamp between realistic bounds
    return max(35, min(75, estimated_win_rate))

def estimate_profit_factor(avg_risk_reward, win_rate):
    """Estimate profit factor based on win rate and risk/reward."""
    
    # Profit factor = (Win Rate * Avg Win) / ((1 - Win Rate) * Avg Loss)
    # Assuming avg win = risk/reward ratio, avg loss = 1
    
    win_rate_decimal = win_rate / 100
    avg_win = avg_risk_reward
    avg_loss = 1.0
    
    if win_rate_decimal == 1.0:
        return float('inf')
    
    profit_factor = (win_rate_decimal * avg_win) / ((1 - win_rate_decimal) * avg_loss)
    return profit_factor

def estimate_monthly_return(win_rate, avg_risk_reward, signal_count):
    """Estimate monthly return based on signal characteristics."""
    
    # Assume 2-3 trades per day on average (conservative)
    trades_per_month = 60
    
    # Risk per trade (2% of capital)
    risk_per_trade = 2.0
    
    win_rate_decimal = win_rate / 100
    avg_win_pct = risk_per_trade * avg_risk_reward
    avg_loss_pct = risk_per_trade
    
    # Expected return per trade
    expected_return_per_trade = (win_rate_decimal * avg_win_pct) - ((1 - win_rate_decimal) * avg_loss_pct)
    
    # Monthly return
    monthly_return = expected_return_per_trade * trades_per_month
    
    return monthly_return

def assess_risk_level(avg_confidence, avg_risk_reward, estimated_win_rate):
    """Assess overall risk level of the trading system."""
    
    risk_factors = []
    
    if avg_confidence < 0.6:
        risk_factors.append("Low average confidence (<60%)")
    
    if avg_risk_reward < 1.5:
        risk_factors.append("Low risk/reward ratio (<1.5)")
    
    if estimated_win_rate < 45:
        risk_factors.append("Low estimated win rate (<45%)")
    
    if not risk_factors:
        print("   ✅ LOW RISK: Strong signal quality across all metrics")
    elif len(risk_factors) == 1:
        print("   ⚠️  MEDIUM RISK: Some areas for improvement")
        for factor in risk_factors:
            print(f"      • {factor}")
    else:
        print("   ❌ HIGH RISK: Multiple quality concerns")
        for factor in risk_factors:
            print(f"      • {factor}")

def provide_recommendations(avg_confidence, avg_risk_reward, estimated_win_rate, high_conf_count, total_signals):
    """Provide trading recommendations based on analysis."""
    
    recommendations = []
    
    if estimated_win_rate >= 55:
        recommendations.append("✅ System shows good profit potential")
    elif estimated_win_rate >= 45:
        recommendations.append("⚠️  System shows moderate profit potential")
    else:
        recommendations.append("❌ System needs improvement before live trading")
    
    if high_conf_count / total_signals < 0.3:
        recommendations.append("• Focus on high-confidence signals (>70%)")
    
    if avg_risk_reward < 1.8:
        recommendations.append("• Consider improving risk/reward ratios")
    
    if avg_confidence < 0.65:
        recommendations.append("• Tighten signal filters to improve quality")
    
    recommendations.extend([
        "• Start with paper trading to validate performance",
        "• Use small position sizes initially (0.5-1% risk per trade)",
        "• Monitor performance closely and adjust as needed",
        "• Consider focusing on your best-performing strategies"
    ])
    
    for rec in recommendations:
        print(f"   {rec}")

if __name__ == "__main__":
    analyze_current_signals() 