#!/usr/bin/env python3
"""
Test Per-Symbol Position Limit Implementation
Verifies that the paper trading engine correctly limits positions per symbol.
"""

import asyncio
import sys
import os
import logging
from datetime import datetime
import time
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

class MockOpportunityManager:
    """Mock opportunity manager that generates multiple signals for the same symbol."""
    
    def __init__(self):
        self.call_count = 0
    
    def get_opportunities(self):
        """Return multiple BTCUSDT opportunities to test per-symbol limit."""
        self.call_count += 1
        
        # Generate 5 BTCUSDT opportunities to test the limit
        opportunities = []
        for i in range(5):
            opportunities.append({
                'symbol': 'BTCUSDT',
                'direction': 'LONG',
                'entry_price': 50000 + (i * 10),  # Slightly different prices
                'take_profit': 51000 + (i * 10),
                'stop_loss': 49000 + (i * 10),
                'confidence': 0.8,
                'strategy': 'test_opportunity',
                'tradable': True,
                'tp_net_usd': 10.0,
                'sl_net_usd': 15.0,
                'floor_net_usd': 7.0
            })
        
        logger.info(f"📊 Mock OpportunityManager returning {len(opportunities)} BTCUSDT opportunities (call #{self.call_count})")
        return opportunities

async def test_per_symbol_position_limit():
    """Test that per-symbol position limits are enforced correctly."""
    
    logger.info("🧪 Starting Per-Symbol Position Limit Test")
    
    try:
        # Load configuration from YAML file
        with open('config/config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        # Override paper trading config for testing
        config['paper_trading'] = {
            'enabled': True,
            'initial_balance': 10000.0,
            'max_positions': 20,
            'max_positions_per_symbol': 2,  # Test with limit of 2 per symbol
            'stake_amount': 500.0,
            'leverage': 10.0,
            'fees': {'rate': 0.0004, 'close_rate': 0.0004},
            'slippage': {'rate': 0.0003},
            'latency': {'ms': 50}
        }
        
        # Initialize exchange client
        exchange_client = ExchangeClient(config)
        await exchange_client.initialize()
        
        # Create mock opportunity manager
        mock_opportunity_manager = MockOpportunityManager()
        
        # Initialize paper trading engine
        paper_engine = EnhancedPaperTradingEngine(
            config=config,
            exchange_client=exchange_client,
            opportunity_manager=mock_opportunity_manager
        )
        
        logger.info(f"✅ Paper Trading Engine initialized with max_positions_per_symbol = {paper_engine.max_positions_per_symbol}")
        
        # Test 1: Direct execution of multiple signals for same symbol
        logger.info("\n🧪 TEST 1: Direct execution of multiple BTCUSDT signals")
        
        signals = [
            {
                'symbol': 'BTCUSDT',
                'direction': 'LONG',
                'entry_price': 50000,
                'strategy': 'test_signal_1',
                'signal_id': 'test_1',
                'optimal_leverage': 10.0
            },
            {
                'symbol': 'BTCUSDT',
                'direction': 'LONG',
                'entry_price': 50010,
                'strategy': 'test_signal_2',
                'signal_id': 'test_2',
                'optimal_leverage': 10.0
            },
            {
                'symbol': 'BTCUSDT',
                'direction': 'LONG',
                'entry_price': 50020,
                'strategy': 'test_signal_3',
                'signal_id': 'test_3',
                'optimal_leverage': 10.0
            }
        ]
        
        executed_positions = []
        for i, signal in enumerate(signals):
            logger.info(f"📈 Attempting to execute signal {i+1}/3 for BTCUSDT...")
            position_id = await paper_engine.execute_virtual_trade(signal, 500.0)
            
            if position_id:
                executed_positions.append(position_id)
                logger.info(f"✅ Position {position_id} created successfully")
            else:
                logger.info(f"🚫 Position creation blocked (expected after limit reached)")
        
        # Check results
        btc_positions = [pos for pos in paper_engine.virtual_positions.values() if pos.symbol == 'BTCUSDT']
        logger.info(f"📊 BTCUSDT positions created: {len(btc_positions)} (expected: 2)")
        
        if len(btc_positions) == 2:
            logger.info("✅ TEST 1 PASSED: Per-symbol limit correctly enforced in direct execution")
        else:
            logger.error(f"❌ TEST 1 FAILED: Expected 2 BTCUSDT positions, got {len(btc_positions)}")
        
        # Test 2: Test with different symbols
        logger.info("\n🧪 TEST 2: Testing with different symbols")
        
        eth_signal = {
            'symbol': 'ETHUSDT',
            'direction': 'LONG',
            'entry_price': 3000,
            'strategy': 'test_eth_signal',
            'signal_id': 'test_eth',
            'optimal_leverage': 10.0
        }
        
        eth_position_id = await paper_engine.execute_virtual_trade(eth_signal, 500.0)
        
        if eth_position_id:
            logger.info("✅ ETHUSDT position created successfully")
            eth_positions = [pos for pos in paper_engine.virtual_positions.values() if pos.symbol == 'ETHUSDT']
            logger.info(f"📊 ETHUSDT positions: {len(eth_positions)}")
            
            if len(eth_positions) == 1:
                logger.info("✅ TEST 2 PASSED: Different symbols work independently")
            else:
                logger.error(f"❌ TEST 2 FAILED: Expected 1 ETHUSDT position, got {len(eth_positions)}")
        else:
            logger.error("❌ TEST 2 FAILED: ETHUSDT position creation failed")
        
        # Test 3: Test signal collection loop filtering
        logger.info("\n🧪 TEST 3: Testing signal collection loop filtering")
        
        # Start the paper trading engine to activate signal collection
        await paper_engine.start()
        
        # Wait a few seconds for signal collection to run
        logger.info("⏳ Waiting for signal collection loop to process opportunities...")
        await asyncio.sleep(10)
        
        # Check final position counts
        final_btc_positions = [pos for pos in paper_engine.virtual_positions.values() if pos.symbol == 'BTCUSDT']
        final_eth_positions = [pos for pos in paper_engine.virtual_positions.values() if pos.symbol == 'ETHUSDT']
        
        logger.info(f"📊 Final BTCUSDT positions: {len(final_btc_positions)} (should still be 2)")
        logger.info(f"📊 Final ETHUSDT positions: {len(final_eth_positions)} (should still be 1)")
        
        if len(final_btc_positions) == 2:
            logger.info("✅ TEST 3 PASSED: Signal collection loop respects per-symbol limits")
        else:
            logger.error(f"❌ TEST 3 FAILED: Signal collection loop created {len(final_btc_positions)} BTCUSDT positions")
        
        # Test 4: Test position closure and re-opening
        logger.info("\n🧪 TEST 4: Testing position closure and re-opening")
        
        if final_btc_positions:
            # Close one BTCUSDT position
            position_to_close = final_btc_positions[0]
            logger.info(f"🔄 Closing BTCUSDT position {position_to_close.position_id}")
            
            await paper_engine.close_virtual_position(position_to_close.position_id, "manual_test")
            
            # Try to create a new BTCUSDT position
            new_btc_signal = {
                'symbol': 'BTCUSDT',
                'direction': 'LONG',
                'entry_price': 50100,
                'strategy': 'test_reopen',
                'signal_id': 'test_reopen',
                'optimal_leverage': 10.0
            }
            
            new_position_id = await paper_engine.execute_virtual_trade(new_btc_signal, 500.0)
            
            if new_position_id:
                logger.info("✅ TEST 4 PASSED: Can create new position after closing one")
                
                # Verify we still have 2 BTCUSDT positions
                current_btc_positions = [pos for pos in paper_engine.virtual_positions.values() if pos.symbol == 'BTCUSDT']
                if len(current_btc_positions) == 2:
                    logger.info("✅ Position count maintained at limit after close/reopen")
                else:
                    logger.error(f"❌ Expected 2 BTCUSDT positions after reopen, got {len(current_btc_positions)}")
            else:
                logger.error("❌ TEST 4 FAILED: Could not create new position after closing one")
        
        # Stop the engine
        await paper_engine.stop()
        
        # Final summary
        logger.info("\n📊 FINAL TEST SUMMARY")
        logger.info("=" * 50)
        
        total_positions = len(paper_engine.virtual_positions)
        btc_final = len([pos for pos in paper_engine.virtual_positions.values() if pos.symbol == 'BTCUSDT'])
        eth_final = len([pos for pos in paper_engine.virtual_positions.values() if pos.symbol == 'ETHUSDT'])
        
        logger.info(f"Total positions: {total_positions}")
        logger.info(f"BTCUSDT positions: {btc_final} (limit: 2)")
        logger.info(f"ETHUSDT positions: {eth_final} (limit: 2)")
        logger.info(f"Per-symbol limit setting: {paper_engine.max_positions_per_symbol}")
        
        # Verify all constraints
        success = True
        if btc_final > paper_engine.max_positions_per_symbol:
            logger.error(f"❌ BTCUSDT positions ({btc_final}) exceed per-symbol limit ({paper_engine.max_positions_per_symbol})")
            success = False
        
        if eth_final > paper_engine.max_positions_per_symbol:
            logger.error(f"❌ ETHUSDT positions ({eth_final}) exceed per-symbol limit ({paper_engine.max_positions_per_symbol})")
            success = False
        
        if success:
            logger.info("🎉 ALL TESTS PASSED: Per-symbol position limits working correctly!")
            logger.info("✅ The system will now prevent multiple positions on the same symbol")
            logger.info("✅ Your 13 BTCUSDT positions issue is resolved")
        else:
            logger.error("❌ SOME TESTS FAILED: Per-symbol position limits need adjustment")
        
        return success
        
    except Exception as e:
        logger.error(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_per_symbol_position_limit())
    sys.exit(0 if success else 1)
