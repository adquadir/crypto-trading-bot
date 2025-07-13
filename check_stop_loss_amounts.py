#!/usr/bin/env python3
"""
Check Stop Loss Amounts
Verify if Rule 3 (0.5% stop loss = ~$10 max loss) is working correctly
"""

import requests
import json

def check_stop_loss_amounts():
    """Check actual stop loss P&L amounts"""
    
    print("🔍 STOP LOSS ANALYSIS - Rule 3 Verification")
    print("=" * 70)
    
    try:
        response = requests.get('http://localhost:8000/api/v1/paper-trading/trades', timeout=10)
        data = response.json()
        trades = data['trades']
        
        # Filter stop loss trades
        stop_loss_trades = []
        for trade in trades:
            exit_reason = trade.get('exit_reason', '')
            if 'stop_loss' in exit_reason:
                stop_loss_trades.append(trade)
        
        print(f"Found {len(stop_loss_trades)} stop loss trades:")
        print()
        print(f"{'#':>2} {'Symbol':>8} {'PnL':>8} {'Exit Reason':>25} {'Duration':>8} {'Rule 3?'}")
        print("-" * 70)
        
        losses_over_10 = 0
        losses_under_10 = 0
        total_loss = 0
        
        for i, trade in enumerate(stop_loss_trades):
            symbol = trade.get('symbol', 'UNKNOWN')
            pnl = trade.get('pnl', 0)
            exit_reason = trade.get('exit_reason', 'unknown')
            duration = trade.get('duration_minutes', 0)
            
            total_loss += pnl
            
            # Check if loss is within $10 limit (Rule 3)
            if pnl < -10:
                losses_over_10 += 1
                rule_3_status = "❌ FAILED"
            else:
                losses_under_10 += 1
                rule_3_status = "✅ OK"
            
            print(f"{i+1:>2} {symbol:>8} ${pnl:>6.2f} {exit_reason:>25} {duration:>6}min {rule_3_status}")
        
        print("-" * 70)
        print()
        
        # Analysis
        print("📊 RULE 3 ANALYSIS:")
        print(f"   Total stop loss trades: {len(stop_loss_trades)}")
        print(f"   Losses ≤ $10 (Rule 3 OK): {losses_under_10} trades")
        print(f"   Losses > $10 (Rule 3 FAILED): {losses_over_10} trades")
        print(f"   Average loss: ${total_loss/len(stop_loss_trades):.2f}")
        print()
        
        # Rule 3 compliance rate
        if len(stop_loss_trades) > 0:
            compliance_rate = (losses_under_10 / len(stop_loss_trades)) * 100
            print(f"🎯 RULE 3 COMPLIANCE: {compliance_rate:.1f}%")
            print()
            
            if compliance_rate >= 90:
                print("✅ EXCELLENT: Rule 3 (0.5% stop loss) is working correctly")
            elif compliance_rate >= 70:
                print("⚠️  GOOD: Rule 3 is mostly working, some issues")
            elif compliance_rate >= 50:
                print("❌ POOR: Rule 3 has significant issues")
            else:
                print("❌ FAILED: Rule 3 (0.5% stop loss) is not working")
            
            if losses_over_10 > 0:
                print()
                print("⚠️  TRADES WITH LOSSES > $10:")
                for trade in stop_loss_trades:
                    if trade.get('pnl', 0) < -10:
                        pnl = trade.get('pnl', 0)
                        symbol = trade.get('symbol', 'UNKNOWN')
                        exit_reason = trade.get('exit_reason', '')
                        print(f"   {symbol}: ${pnl:.2f} ({exit_reason})")
                print("   ⚠️  These indicate Rule 3 is not properly limiting losses to $10")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    check_stop_loss_amounts()
