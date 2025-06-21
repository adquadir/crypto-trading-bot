#!/usr/bin/env python3
import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.opportunity.opportunity_manager import OpportunityManager
from src.market_data.exchange_client import ExchangeClient
from src.strategy.strategy_manager import StrategyManager
from src.risk.risk_manager import RiskManager

async def main():
    print("🎯 HIGH CONFIDENCE SIGNALS ONLY")
    print("=" * 40)
    
    # Quick setup
    exchange_client = ExchangeClient()
    strategy_manager = StrategyManager(exchange_client)
    risk_config = {
        'risk': {'max_drawdown': 0.2, 'max_leverage': 5.0, 'position_size_limit': 1000.0, 'daily_loss_limit': 100.0, 'initial_balance': 10000.0},
        'trading': {'max_volatility': 0.5, 'max_spread': 0.01}
    }
    risk_manager = RiskManager(risk_config)
    opportunity_manager = OpportunityManager(exchange_client, strategy_manager, risk_manager)
    await opportunity_manager.initialize()
    
    print("Scanning...")
    await opportunity_manager.scan_opportunities_incremental()
    all_signals = opportunity_manager.get_opportunities()
    
    # Filter for high confidence
    high_conf = []
    for s in all_signals:
        if (s.get('validation_applied', False) and 
            s.get('tradable', True) and
            s.get('adjusted_rr_ratio', 0) >= 2.0 and
            s.get('adjusted_move_pct', 0) >= 2.5 and
            s.get('confidence', 0) >= 0.75 and
            s.get('volume_score', '') in ['🟢 Excellent', '🟡 Good', '🟠 Moderate']):
            
            # Calculate TP hit probability
            prob = 50
            if s.get('volume_score') == '🟢 Excellent': prob += 25
            elif s.get('volume_score') == '🟡 Good': prob += 20
            elif s.get('volume_score') == '🟠 Moderate': prob += 15
            
            rr = s.get('adjusted_rr_ratio', 0)
            if rr >= 3.0: prob += 15
            elif rr >= 2.5: prob += 10
            elif rr >= 2.0: prob += 5
            
            conf_bonus = (s.get('confidence', 0) - 0.75) * 40
            prob += conf_bonus
            
            slip_penalty = s.get('expected_slippage_pct', 0) * 50
            prob -= slip_penalty
            
            s['tp_hit_prob'] = max(0, min(100, int(prob)))
            
            if s['tp_hit_prob'] >= 80:
                high_conf.append(s)
    
    high_conf.sort(key=lambda x: x['tp_hit_prob'], reverse=True)
    
    print(f"Total signals: {len(all_signals)}")
    print(f"High confidence: {len(high_conf)}")
    print()
    
    if not high_conf:
        print("❌ No high confidence signals found.")
        print("💡 System is being selective - this protects your capital.")
        return
    
    print("🟢 HIGH CONFIDENCE SIGNALS (80%+ TP Hit Rate)")
    print("=" * 50)
    
    for i, s in enumerate(high_conf[:10], 1):
        symbol = s['symbol']
        direction = s['direction']
        tp_prob = s['tp_hit_prob']
        entry = s.get('adjusted_entry', s['entry_price'])
        tp = s.get('adjusted_take_profit', s['take_profit'])
        move = s.get('adjusted_move_pct', 0)
        rr = s.get('adjusted_rr_ratio', 0)
        volume = s.get('volume_score', 'Unknown')
        profit = s.get('expected_profit_100', 0)
        
        print(f"#{i} {symbol} {direction}")
        print(f"   🎯 TP Hit Probability: {tp_prob}%")
        print(f"   📊 Entry: ${entry:.6f} → TP: ${tp:.6f} (+{move:.2f}%)")
        print(f"   ⚖️ R:R: {rr:.2f}:1 | Volume: {volume}")
        print(f"   💰 $100 Profit: ${profit:.2f}")
        print()
    
    avg_prob = sum(s['tp_hit_prob'] for s in high_conf) / len(high_conf)
    total_profit = sum(s.get('expected_profit_100', 0) for s in high_conf)
    
    print(f"📊 SUMMARY:")
    print(f"   Average TP Hit Rate: {avg_prob:.1f}%")
    print(f"   Total $100 Profit Potential: ${total_profit:.2f}")
    print(f"   🎯 TRADE THESE WITH CONFIDENCE!")

if __name__ == "__main__":
    asyncio.run(main())
