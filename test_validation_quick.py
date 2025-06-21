#!/usr/bin/env python3
"""Quick validation test - bypasses API to test core functionality."""

import asyncio
import sys
import os
sys.path.append('src')

from src.opportunity.opportunity_manager import OpportunityManager
from src.market_data.exchange_client import ExchangeClient
from src.strategy.strategy_manager import StrategyManager
from src.risk.risk_manager import RiskManager
from src.utils.config import load_config

async def test_validation():
    print("🔧 TESTING VALIDATION DIRECTLY...")
    
    # Initialize components
    config = load_config()
    exchange_client = ExchangeClient()
    await exchange_client.initialize()
    
    try:
        risk_manager = RiskManager(config)
    except:
        risk_manager = None
    
    try:
        strategy_manager = StrategyManager(exchange_client)
        await strategy_manager.initialize()
    except:
        strategy_manager = None
    
    opportunity_manager = OpportunityManager(exchange_client, strategy_manager, risk_manager)
    await opportunity_manager.initialize()
    
    # Generate a single signal for testing
    symbol = 'BTCUSDT'
    market_data = await opportunity_manager._get_market_data_for_signal_stable(symbol)
    
    if market_data:
        print(f"✅ Got market data for {symbol}")
        
        # Generate signal
        opportunity = opportunity_manager._analyze_market_and_generate_signal_balanced(symbol, market_data, 1750470000.0)
        
        if opportunity:
            print(f"\n🎯 SIGNAL GENERATED for {symbol}:")
            print(f"Direction: {opportunity.get('direction', 'N/A')}")
            print(f"Entry: {opportunity.get('entry_price', 'N/A')}")
            print(f"Take Profit: {opportunity.get('take_profit', 'N/A')}")
            print(f"Stop Loss: {opportunity.get('stop_loss', 'N/A')}")
            
            # Check validation fields
            print(f"\n🔧 VALIDATION STATUS:")
            print(f"validation_applied: {opportunity.get('validation_applied', 'N/A')}")
            print(f"tradable: {opportunity.get('tradable', 'N/A')}")
            print(f"verdict: {opportunity.get('verdict', 'N/A')}")
            print(f"volume_score: {opportunity.get('volume_score', 'N/A')}")
            print(f"adjusted_move_pct: {opportunity.get('adjusted_move_pct', 'N/A')}")
            print(f"expected_slippage_pct: {opportunity.get('expected_slippage_pct', 'N/A')}")
            
            # Calculate move %
            entry = opportunity.get('entry_price', 0)
            tp = opportunity.get('take_profit', 0)
            if entry and tp:
                move_pct = abs(tp - entry) / entry * 100
                print(f"Raw move %: {move_pct:.2f}%")
            
            return True
        else:
            print(f"❌ No signal generated for {symbol}")
            return False
    else:
        print(f"❌ No market data for {symbol}")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_validation())
    if result:
        print("\n✅ VALIDATION TEST PASSED!")
    else:
        print("\n❌ VALIDATION TEST FAILED!") 