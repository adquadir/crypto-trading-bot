#!/usr/bin/env python3
"""Test validation function directly."""

import asyncio
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.opportunity.opportunity_manager import OpportunityManager
from src.market_data.exchange_client import ExchangeClient
from src.strategy.strategy_manager import StrategyManager
from src.risk.risk_manager import RiskManager

async def test_validation():
    print('🔧 Testing validation function directly...')
    
    # Create opportunity manager
    exchange_client = ExchangeClient()
    await exchange_client.initialize()
    
    try:
        risk_manager = RiskManager({})
    except:
        risk_manager = None
    
    try:
        strategy_manager = StrategyManager(exchange_client)
        await strategy_manager.initialize()
    except:
        strategy_manager = None
    
    opportunity_manager = OpportunityManager(exchange_client, strategy_manager, risk_manager)
    await opportunity_manager.initialize()
    
    # Create test opportunity
    test_opportunity = {
        'symbol': 'BTCUSDT',
        'direction': 'LONG',
        'entry_price': 100000.0,
        'take_profit': 103000.0,
        'stop_loss': 98000.0,
        'confidence': 0.75,
        'volatility': 2.0,
        'volume_ratio': 1.2
    }
    
    try:
        print('🎯 Calling validation function...')
        result = opportunity_manager._validate_signal_for_real_trading(test_opportunity)
        print('✅ Validation result:')
        for key in ['validation_applied', 'tradable', 'verdict', 'volume_score']:
            print(f'  {key}: {result.get(key)}')
        return True
    except Exception as e:
        print(f'❌ VALIDATION ERROR: {e}')
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(test_validation()) 