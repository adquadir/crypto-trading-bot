#!/usr/bin/env python3
"""
Live 3-Rule Mode Verification
Check actual completed trades to verify the three rules are being applied
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.trading.enhanced_paper_trading_engine import EnhancedPaperTradingEngine
from src.database.database import Database
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_live_3_rule_verification():
    """Check actual completed trades to verify 3-rule implementation"""
    
    print("🔍 LIVE 3-RULE MODE VERIFICATION")
    print("=" * 80)
    
    try:
        # Initialize database connection
        db = Database()
        
        # Check if paper trading engine is running and get its state
        config = {
            'paper_trading': {
                'initial_balance': 10000.0,
                'pure_3_rule_mode': True,
                'primary_target_dollars': 10.0,
                'absolute_floor_dollars': 7.0
            }
        }
        
        engine = EnhancedPaperTradingEngine(config)
        
        # Get current account status
        status = engine.get_account_status()
        
        print(f"📊 CURRENT STATUS:")
        print(f"   Running: {status['is_running']}")
        print(f"   Total Trades: {status['account']['total_trades']}")
        print(f"   Active Positions: {len(status['positions'])}")
        print(f"   Recent Trades: {len(status['recent_trades'])}")
        print()
        
        # Analyze completed trades
        completed_trades = status['recent_trades']
        
        if not completed_trades:
            print("❌ NO COMPLETED TRADES FOUND")
            print("   Cannot verify if 3-rule mode is working without trade data")
            return
        
        print(f"📈 ANALYZING {len(completed_trades)} COMPLETED TRADES:")
        print("-" * 60)
        
        # Count exit reasons
        exit_reason_counts = {}
        rule_1_exits = 0  # $10 target
        rule_2_exits = 0  # $7 floor
        rule_3_exits = 0  # 0.5% stop loss
        other_exits = 0
        
        profitable_trades = 0
        total_pnl = 0
        
        for i, trade in enumerate(completed_trades):
            symbol = trade.get('symbol', 'UNKNOWN')
            pnl = trade.get('pnl', 0)
            exit_reason = trade.get('exit_reason', 'unknown')
            duration = trade.get('duration_minutes', 0)
            
            total_pnl += pnl
            if pnl > 0:
                profitable_trades += 1
            
            # Count exit reasons
            exit_reason_counts[exit_reason] = exit_reason_counts.get(exit_reason, 0) + 1
            
            # Categorize by 3-rule system
            if exit_reason == 'primary_target_10_dollars':
                rule_1_exits += 1
                rule_indicator = "✅ RULE 1"
            elif exit_reason == 'absolute_floor_7_dollars':
                rule_2_exits += 1
                rule_indicator = "✅ RULE 2"
            elif exit_reason in ['stop_loss_0_5_percent', 'stop_loss']:
                rule_3_exits += 1
                rule_indicator = "✅ RULE 3"
            else:
                other_exits += 1
                rule_indicator = "❌ OTHER"
            
            print(f"{i+1:2d}. {symbol:8s} | ${pnl:6.2f} | {exit_reason:20s} | {duration:3d}min | {rule_indicator}")
        
        print("-" * 60)
        print(f"📊 EXIT REASON ANALYSIS:")
        print()
        
        # Show all exit reasons found
        print("🔍 All Exit Reasons Found:")
        for reason, count in sorted(exit_reason_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / len(completed_trades)) * 100
            print(f"   {reason:25s}: {count:3d} trades ({percentage:5.1f}%)")
        print()
        
        # 3-Rule Analysis
        print("🎯 3-RULE MODE ANALYSIS:")
        total_rule_exits = rule_1_exits + rule_2_exits + rule_3_exits
        rule_compliance = (total_rule_exits / len(completed_trades)) * 100
        
        print(f"   Rule 1 ($10 Target):     {rule_1_exits:3d} trades ({rule_1_exits/len(completed_trades)*100:5.1f}%)")
        print(f"   Rule 2 ($7 Floor):       {rule_2_exits:3d} trades ({rule_2_exits/len(completed_trades)*100:5.1f}%)")
        print(f"   Rule 3 (0.5% Stop Loss): {rule_3_exits:3d} trades ({rule_3_exits/len(completed_trades)*100:5.1f}%)")
        print(f"   Other Exits:             {other_exits:3d} trades ({other_exits/len(completed_trades)*100:5.1f}%)")
        print()
        print(f"   3-RULE COMPLIANCE: {rule_compliance:.1f}% ({total_rule_exits}/{len(completed_trades)} trades)")
        print()
        
        # Performance Analysis
        win_rate = (profitable_trades / len(completed_trades)) * 100
        print(f"💰 PERFORMANCE SUMMARY:")
        print(f"   Total P&L: ${total_pnl:.2f}")
        print(f"   Win Rate:  {win_rate:.1f}% ({profitable_trades}/{len(completed_trades)})")
        print(f"   Avg P&L:   ${total_pnl/len(completed_trades):.2f}")
        print()
        
        # Verification Results
        print("🎯 VERIFICATION RESULTS:")
        print("=" * 40)
        
        if rule_compliance >= 95:
            print("✅ EXCELLENT: 3-Rule Mode is working correctly")
            print(f"   {rule_compliance:.1f}% of trades follow the 3-rule system")
        elif rule_compliance >= 80:
            print("⚠️  GOOD: 3-Rule Mode is mostly working")
            print(f"   {rule_compliance:.1f}% compliance, some other exits present")
        elif rule_compliance >= 50:
            print("❌ POOR: 3-Rule Mode has issues")
            print(f"   Only {rule_compliance:.1f}% compliance, many other exits")
        else:
            print("❌ FAILED: 3-Rule Mode is not working")
            print(f"   Only {rule_compliance:.1f}% compliance, system not following rules")
        
        if other_exits > 0:
            print()
            print("⚠️  NON-RULE EXITS DETECTED:")
            non_rule_reasons = [reason for reason in exit_reason_counts.keys() 
                              if reason not in ['primary_target_10_dollars', 'absolute_floor_7_dollars', 'stop_loss_0_5_percent', 'stop_loss']]
            for reason in non_rule_reasons:
                count = exit_reason_counts[reason]
                print(f"   - {reason}: {count} trades")
            print("   These should be investigated if Pure 3-Rule Mode is enabled")
        
        print()
        
        # Check current positions
        if status['positions']:
            print("🔄 ACTIVE POSITIONS:")
            for pos_id, pos in status['positions'].items():
                symbol = pos.get('symbol', 'UNKNOWN')
                pnl = pos.get('unrealized_pnl', 0)
                floor_active = pos.get('profit_floor_activated', False)
                highest_profit = pos.get('highest_profit_ever', 0)
                
                print(f"   {symbol}: ${pnl:.2f} PnL | Floor: {'✅' if floor_active else '❌'} | Peak: ${highest_profit:.2f}")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_live_3_rule_verification())
