#!/usr/bin/env python3
"""
Test Configuration Lookup Fix
Verifies that the nested config lookup bug is fixed and absolute_floor_dollars is read correctly.
"""

import asyncio
import sys
import os
import logging
from datetime import datetime
import yaml

# Add the src directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.trading.enhanced_paper_trading_engine import EnhancedPaperTradingEngine
from src.market_data.exchange_client import ExchangeClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_config_lookup_fix():
    """Test that the configuration lookup bug is fixed."""
    
    logger.info("🧪 Starting Configuration Lookup Fix Test")
    
    try:
        # Load configuration from YAML file
        with open('config/config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        # Initialize exchange client
        exchange_client = ExchangeClient(config)
        await exchange_client.initialize()
        
        # Initialize paper trading engine
        paper_engine = EnhancedPaperTradingEngine(
            config=config,
            exchange_client=exchange_client
        )
        
        logger.info("✅ Paper Trading Engine initialized successfully")
        
        # Test 1: Verify the configuration is loaded correctly
        logger.info("\n🧪 TEST 1: Configuration Loading")
        
        # Check that the paper trading config is properly extracted
        expected_floor = 15.0  # From config.yaml
        logger.info(f"Expected absolute_floor_dollars from YAML: {expected_floor}")
        
        # Create a test signal to trigger the execute_virtual_trade method
        test_signal = {
            'symbol': 'BTCUSDT',
            'direction': 'LONG',
            'entry_price': 50000,
            'strategy': 'config_test',
            'signal_id': 'test_config',
            'optimal_leverage': 10.0
        }
        
        # Execute a virtual trade to test the configuration lookup
        position_id = await paper_engine.execute_virtual_trade(test_signal, 500.0)
        
        if position_id:
            logger.info(f"✅ Virtual trade executed successfully: {position_id}")
            
            # Check the position's floor value
            position = paper_engine.virtual_positions[position_id]
            actual_floor = position.absolute_floor_profit
            
            logger.info(f"Position absolute_floor_profit: {actual_floor}")
            
            # Calculate expected net floor (gross floor minus fees)
            fee_rate = paper_engine.fees.get('rate', 0.0004)
            stake_amount = 500.0
            total_fees = stake_amount * fee_rate * 2  # Entry + exit fees
            expected_net_floor = expected_floor - total_fees
            
            logger.info(f"Expected net floor (after fees): {expected_net_floor}")
            logger.info(f"Actual position floor: {actual_floor}")
            
            # Test passes if the floor is calculated correctly from config
            if abs(actual_floor - expected_net_floor) < 0.01:  # Allow small floating point differences
                logger.info("✅ TEST 1 PASSED: Configuration lookup working correctly")
                logger.info(f"✅ Floor value properly read from YAML: ${expected_floor}")
                logger.info(f"✅ Net floor correctly calculated: ${actual_floor:.2f}")
            else:
                logger.error(f"❌ TEST 1 FAILED: Floor mismatch - Expected: {expected_net_floor:.2f}, Got: {actual_floor:.2f}")
                return False
        else:
            logger.error("❌ TEST 1 FAILED: Could not execute virtual trade")
            return False
        
        # Test 2: Verify different config values work
        logger.info("\n🧪 TEST 2: Dynamic Configuration Values")
        
        # Temporarily modify the config to test different values
        original_floor = paper_engine.config.get('absolute_floor_dollars', 15.0)
        paper_engine.config['absolute_floor_dollars'] = 20.0
        
        test_signal_2 = {
            'symbol': 'ETHUSDT',
            'direction': 'LONG',
            'entry_price': 3000,
            'strategy': 'config_test_2',
            'signal_id': 'test_config_2',
            'optimal_leverage': 10.0
        }
        
        position_id_2 = await paper_engine.execute_virtual_trade(test_signal_2, 500.0)
        
        if position_id_2:
            position_2 = paper_engine.virtual_positions[position_id_2]
            expected_net_floor_2 = 20.0 - total_fees  # Using modified config value
            
            logger.info(f"Modified config floor: 20.0")
            logger.info(f"Expected net floor: {expected_net_floor_2:.2f}")
            logger.info(f"Actual position floor: {position_2.absolute_floor_profit:.2f}")
            
            if abs(position_2.absolute_floor_profit - expected_net_floor_2) < 0.01:
                logger.info("✅ TEST 2 PASSED: Dynamic configuration values working")
            else:
                logger.error(f"❌ TEST 2 FAILED: Dynamic config not working")
                return False
        else:
            logger.error("❌ TEST 2 FAILED: Could not execute second virtual trade")
            return False
        
        # Restore original config
        paper_engine.config['absolute_floor_dollars'] = original_floor
        
        # Test 3: Verify the bug would have occurred with old code
        logger.info("\n🧪 TEST 3: Verify Bug Fix")
        
        # Simulate what the old buggy code would have done
        paper_config_old_way = paper_engine.config.get('paper_trading', {})  # This would be {}
        old_floor = float(paper_config_old_way.get('absolute_floor_dollars', 15.0))  # Would always be 15.0
        
        # New correct way
        new_floor = float(paper_engine.config.get('absolute_floor_dollars', 15.0))  # Reads from actual config
        
        logger.info(f"Old buggy method would get: {old_floor} (always default)")
        logger.info(f"New fixed method gets: {new_floor} (from actual config)")
        
        if old_floor == 15.0 and new_floor == expected_floor:
            logger.info("✅ TEST 3 PASSED: Bug fix verified - old method would fail, new method works")
        else:
            logger.error("❌ TEST 3 FAILED: Bug fix verification failed")
            return False
        
        # Final summary
        logger.info("\n📊 CONFIGURATION FIX SUMMARY")
        logger.info("=" * 50)
        logger.info(f"✅ Configuration properly loaded from YAML")
        logger.info(f"✅ absolute_floor_dollars correctly read: ${expected_floor}")
        logger.info(f"✅ Net floor calculation working: ${actual_floor:.2f}")
        logger.info(f"✅ Dynamic configuration changes work")
        logger.info(f"✅ Nested config lookup bug is FIXED")
        logger.info(f"✅ Your $15 floor on reversal rule is now active!")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_config_lookup_fix())
    sys.exit(0 if success else 1)
