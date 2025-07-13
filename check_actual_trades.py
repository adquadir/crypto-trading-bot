#!/usr/bin/env python3
"""
Check Actual Completed Trades
Direct API call to verify what exit reasons are being used
"""

import requests
import json

def check_actual_trades():
    """Check actual completed trades via API"""
    
    print("🔍 CHECKING ACTUAL COMPLETED TRADES")
    print("=" * 60)
    
    try:
        # Get completed trades
        print("📡 Fetching completed trades from API...")
        response = requests.get('http://localhost:8000/api/v1/paper-trading/trades', timeout=10)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ API Error: {response.status_code}")
            print(f"Response: {response.text}")
            return
        
        data = response.json()
        
        if 'trades' not in data or not data['trades']:
            print("❌ NO COMPLETED TRADES FOUND")
            print("Response structure:", json.dumps(data, indent=2))
            return
        
        trades = data['trades']
        print(f"✅ Found {len(trades)} completed trades")
        print()
        
        # Analyze exit reasons
        exit_reason_counts = {}
        rule_1_exits = 0  # $10 target
        rule_2_exits = 0  # $7 floor  
        rule_3_exits = 0  # 0.5% stop loss
        other_exits = 0
        
        profitable_trades = 0
        total_pnl = 0
        
        print("📊 TRADE ANALYSIS:")
        print("-" * 80)
        print(f"{'#':>2} {'Symbol':>8} {'PnL':>8} {'Exit Reason':>25} {'Duration':>8} {'Rule'}")
        print("-" * 80)
        
        for i, trade in enumerate(trades[:20]):  # Show first 20 trades
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
                rule_indicator = "RULE 1"
            elif exit_reason == 'absolute_floor_7_dollars':
                rule_2_exits += 1
                rule_indicator = "RULE 2"
            elif exit_reason in ['stop_loss_0_5_percent', 'stop_loss']:
                rule_3_exits += 1
                rule_indicator = "RULE 3"
            else:
                other_exits += 1
                rule_indicator = "OTHER"
            
            print(f"{i+1:>2} {symbol:>8} ${pnl:>6.2f} {exit_reason:>25} {duration:>6}min {rule_indicator}")
        
        print("-" * 80)
        print()
        
        # Exit reason summary
        print("🔍 EXIT REASON BREAKDOWN:")
        for reason, count in sorted(exit_reason_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / len(trades)) * 100
            print(f"   {reason:30s}: {count:3d} trades ({percentage:5.1f}%)")
        print()
        
        # 3-Rule compliance analysis
        total_rule_exits = rule_1_exits + rule_2_exits + rule_3_exits
        rule_compliance = (total_rule_exits / len(trades)) * 100
        
        print("🎯 3-RULE MODE COMPLIANCE:")
        print(f"   Rule 1 ($10 Target):     {rule_1_exits:3d} trades ({rule_1_exits/len(trades)*100:5.1f}%)")
        print(f"   Rule 2 ($7 Floor):       {rule_2_exits:3d} trades ({rule_2_exits/len(trades)*100:5.1f}%)")
        print(f"   Rule 3 (0.5% Stop Loss): {rule_3_exits:3d} trades ({rule_3_exits/len(trades)*100:5.1f}%)")
        print(f"   Other Exits:             {other_exits:3d} trades ({other_exits/len(trades)*100:5.1f}%)")
        print()
        print(f"   TOTAL 3-RULE COMPLIANCE: {rule_compliance:.1f}% ({total_rule_exits}/{len(trades)} trades)")
        print()
        
        # Performance summary
        win_rate = (profitable_trades / len(trades)) * 100
        print("💰 PERFORMANCE SUMMARY:")
        print(f"   Total Trades: {len(trades)}")
        print(f"   Profitable:   {profitable_trades} ({win_rate:.1f}%)")
        print(f"   Total P&L:    ${total_pnl:.2f}")
        print(f"   Avg P&L:      ${total_pnl/len(trades):.2f}")
        print()
        
        # Verification verdict
        print("🎯 VERIFICATION VERDICT:")
        print("=" * 40)
        
        if rule_compliance >= 95:
            print("✅ EXCELLENT: 3-Rule Mode is working correctly")
        elif rule_compliance >= 80:
            print("⚠️  GOOD: 3-Rule Mode is mostly working")
        elif rule_compliance >= 50:
            print("❌ POOR: 3-Rule Mode has significant issues")
        else:
            print("❌ FAILED: 3-Rule Mode is not working")
        
        print(f"   Compliance Rate: {rule_compliance:.1f}%")
        
        if other_exits > 0:
            print()
            print("⚠️  NON-RULE EXITS DETECTED:")
            non_rule_reasons = [reason for reason in exit_reason_counts.keys() 
                              if reason not in ['primary_target_10_dollars', 'absolute_floor_7_dollars', 'stop_loss_0_5_percent', 'stop_loss']]
            for reason in non_rule_reasons:
                count = exit_reason_counts[reason]
                print(f"   - {reason}: {count} trades")
            
            if len(non_rule_reasons) > 0:
                print("   ⚠️  These exits should be investigated if Pure 3-Rule Mode is enabled")
        
    except requests.exceptions.Timeout:
        print("❌ API Timeout - server may be overloaded")
    except requests.exceptions.ConnectionError:
        print("❌ Connection Error - server may not be running")
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_actual_trades()
