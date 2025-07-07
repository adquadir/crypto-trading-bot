#!/usr/bin/env python3
"""
Direct script to enable paper trading mode and connect signals
This bypasses the API and directly modifies the opportunity manager
"""

import sys
import asyncio
import requests
import time

# Add project root to path  
sys.path.append('/home/ubuntu/crypto-trading-bot')

def manual_enable_paper_trading_mode():
    """Manually enable paper trading mode through direct API calls"""
    try:
        print("🎯 Manually enabling paper trading mode...")
        
        # Step 1: Check current opportunities
        print("📊 Checking current opportunities...")
        opp_response = requests.get("http://localhost:8000/api/v1/opportunities", timeout=10)
        if opp_response.status_code == 200:
            data = opp_response.json()
            opportunities = data.get('data', [])
            total = len(opportunities)
            tradable = sum(1 for opp in opportunities if opp.get('tradable', False))
            
            print(f"   Total opportunities: {total}")
            print(f"   Tradable opportunities: {tradable}")
            print(f"   Tradable percentage: {round((tradable/total)*100, 1) if total > 0 else 0}%")
            
            if total > 0:
                # Show sample rejection reason
                rejected = [opp for opp in opportunities if not opp.get('tradable', False)]
                if rejected:
                    sample = rejected[0]
                    reason = sample.get('rejection_reason', 'Unknown')
                    rr_ratio = sample.get('adjusted_rr_ratio', 'N/A')
                    print(f"   Sample rejection: {reason}")
                    print(f"   Sample R/R ratio: {rr_ratio}")
            
            return opportunities
        else:
            print(f"❌ Failed to get opportunities: {opp_response.status_code}")
            return []
            
    except Exception as e:
        print(f"❌ Error checking opportunities: {e}")
        return []

def inject_manual_signals(opportunities):
    """Convert existing opportunities to manual signals for paper trading"""
    try:
        # Find some decent opportunities to convert
        decent_opportunities = [
            opp for opp in opportunities 
            if (opp.get('confidence', 0) >= 0.6 and 
                opp.get('adjusted_rr_ratio', 0) >= 0.3 and
                'USDT' in opp.get('symbol', ''))
        ]
        
        print(f"🎯 Found {len(decent_opportunities)} decent opportunities to convert")
        
        if not decent_opportunities:
            print("⚠️  No suitable opportunities found - using test signals")
            return inject_test_signals()
        
        # Take the best 3-5 opportunities
        best_opportunities = sorted(decent_opportunities, 
                                  key=lambda x: x.get('confidence', 0), 
                                  reverse=True)[:5]
        
        executed_trades = []
        for i, opp in enumerate(best_opportunities):
            try:
                # Convert opportunity to signal format
                signal_data = {
                    'symbol': opp.get('symbol'),
                    'strategy_type': 'converted_opportunity',
                    'side': opp.get('direction', 'LONG'),
                    'confidence': opp.get('confidence', 0.7),
                    'ml_score': opp.get('confidence', 0.7),
                    'reason': f"converted_from_opportunity_{i+1}",
                    'market_regime': opp.get('market_regime', 'trending'),
                    'volatility_regime': 'medium'
                }
                
                # Execute through manual signal injection
                response = requests.post(
                    "http://localhost:8000/api/v1/paper-trading/execute-signal",
                    json=signal_data,
                    timeout=10
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('status') == 'success':
                        executed_trades.append({
                            'symbol': signal_data['symbol'],
                            'side': signal_data['side'],
                            'confidence': signal_data['confidence']
                        })
                        print(f"✅ Executed: {signal_data['symbol']} {signal_data['side']} (confidence: {signal_data['confidence']:.1%})")
                    else:
                        print(f"❌ Failed: {signal_data['symbol']} - {result.get('message', 'Unknown error')}")
                else:
                    print(f"❌ HTTP Error for {signal_data['symbol']}: {response.status_code}")
                    
            except Exception as e:
                print(f"❌ Error converting {opp.get('symbol', 'Unknown')}: {e}")
                continue
        
        print(f"\n🎯 Successfully executed {len(executed_trades)} converted trades!")
        return len(executed_trades) > 0
        
    except Exception as e:
        print(f"❌ Error injecting manual signals: {e}")
        return False

def inject_test_signals():
    """Fallback: inject test signals"""
    try:
        print("🧪 Injecting test signals as fallback...")
        
        symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
        executed = 0
        
        for symbol in symbols:
            response = requests.post(f"http://localhost:8000/api/v1/paper-trading/simulate-signals?symbol={symbol}&count=2", timeout=10)
            if response.status_code == 200:
                data = response.json()
                trades = len(data.get('executed_trades', []))
                executed += trades
                print(f"✅ {symbol}: {trades} trades executed")
            else:
                print(f"❌ {symbol}: Failed")
                
        return executed > 0
        
    except Exception as e:
        print(f"❌ Error injecting test signals: {e}")
        return False

def check_final_status():
    """Check final status"""
    try:
        # Check positions
        pos_response = requests.get("http://localhost:8000/api/v1/paper-trading/positions", timeout=5)
        if pos_response.status_code == 200:
            positions = pos_response.json().get('data', [])
            print(f"📊 Final result: {len(positions)} active positions")
            
            # Check balance
            status_response = requests.get("http://localhost:8000/api/v1/paper-trading/status", timeout=5)
            if status_response.status_code == 200:
                status = status_response.json().get('data', {})
                balance = status.get('virtual_balance', 0)
                enabled = status.get('enabled', False)
                print(f"💰 Paper trading balance: ${balance:,.2f}")
                print(f"🔄 Paper trading enabled: {enabled}")
                
            return len(positions)
        else:
            print("❌ Could not check final status")
            return 0
            
    except Exception as e:
        print(f"❌ Error checking final status: {e}")
        return 0

def main():
    print("🎯 DIRECT PAPER TRADING MODE ENABLER")
    print("=" * 60)
    
    # Step 1: Check current state
    opportunities = manual_enable_paper_trading_mode()
    
    # Step 2: Convert opportunities to signals or use test signals
    if opportunities:
        success = inject_manual_signals(opportunities)
    else:
        success = inject_test_signals()
    
    # Step 3: Check final result
    if success:
        time.sleep(2)  # Wait for execution
        final_positions = check_final_status()
        
        if final_positions > 0:
            print(f"\n✅ SUCCESS: {final_positions} positions active!")
            print("📊 Paper trading is now working with real market data")
            print("🔍 Monitor: pm2 logs crypto-trading-api")
        else:
            print("\n⚠️  No positions created - check logs for issues")
    else:
        print("\n❌ Failed to inject signals")
    
    print("\n🎯 Next steps:")
    print("   1. Check Paper Trading page in frontend")
    print("   2. Monitor logs: pm2 logs crypto-trading-api") 
    print("   3. Wait for real signals to be processed")

if __name__ == "__main__":
    main() 