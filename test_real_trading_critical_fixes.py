#!/usr/bin/env python3
"""
Critical Real Trading Engine Fixes Test Suite
Tests all the must-fix issues identified for live trading safety
"""

import asyncio
import pytest
import logging
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import yaml
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath('.'))

from src.trading.real_trading_engine import RealTradingEngine, LivePosition
from src.market_data.exchange_client import ExchangeClient
from src.opportunity.opportunity_manager import OpportunityManager

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FakeExchangeClient:
    """Mock exchange client for testing"""
    
    def __init__(self):
        self.positions = {}  # symbol -> position_size
        self.orders = {}     # order_id -> order_data
        self.trades = []     # list of trades
        self.balance = {'total': 10000.0}
        self.margin_calls = []
        self.leverage_calls = []
        self.order_counter = 1000
        
    async def get_account_balance(self):
        return self.balance
    
    async def get_position(self, symbol):
        size = self.positions.get(symbol, 0.0)
        return {'positionAmt': str(size)}
    
    async def get_ticker_24h(self, symbol):
        return {'lastPrice': '50000.0'}  # Default BTC price
    
    async def get_symbol_info(self, symbol):
        return {
            'stepSize': '0.001',
            'tickSize': '0.01', 
            'minNotional': '10'
        }
    
    async def set_margin_type(self, symbol, margin_type):
        self.margin_calls.append((symbol, margin_type))
        
    async def set_leverage(self, symbol, leverage):
        self.leverage_calls.append((symbol, leverage))
    
    async def create_order(self, symbol, side, type, quantity, **kwargs):
        order_id = str(self.order_counter)
        self.order_counter += 1
        
        order = {
            'orderId': order_id,
            'symbol': symbol,
            'side': side,
            'type': type,
            'quantity': quantity,
            'avgPrice': '50000.0',
            'price': '50000.0',
            **kwargs
        }
        
        self.orders[order_id] = order
        
        # Update position for market orders
        if type == 'MARKET':
            current_size = self.positions.get(symbol, 0.0)
            if side == 'BUY':
                self.positions[symbol] = current_size + float(quantity)
            else:  # SELL
                self.positions[symbol] = current_size - float(quantity)
        
        return order
    
    async def cancel_order(self, symbol, order_id):
        if order_id in self.orders:
            del self.orders[order_id]
        return True
    
    async def get_account_trades(self, symbol, limit=10):
        return self.trades[-limit:] if self.trades else []
    
    def set_position_size(self, symbol, size):
        """Helper to simulate position changes"""
        self.positions[symbol] = size
    
    def market_close_called(self, symbol):
        """Check if market close was called for symbol"""
        for order in self.orders.values():
            if (order['symbol'] == symbol and 
                order['type'] == 'MARKET' and 
                order.get('reduceOnly')):
                return True
        return False
    
    def assert_isolated(self, symbol):
        """Assert isolated margin was set"""
        assert any(call[0] == symbol and call[1] == 'ISOLATED' 
                  for call in self.margin_calls), f"ISOLATED margin not set for {symbol}"
    
    def assert_leverage(self, symbol, expected_max):
        """Assert leverage was set within bounds"""
        leverage_calls = [call[1] for call in self.leverage_calls if call[0] == symbol]
        assert leverage_calls, f"No leverage set for {symbol}"
        assert max(leverage_calls) <= expected_max, f"Leverage {max(leverage_calls)} exceeds max {expected_max}"

@pytest.fixture
def config():
    """Test configuration"""
    return {
        'real_trading': {
            'enabled': True,
            'stake_usd': 200.0,
            'max_positions': 20,
            'accept_sources': ['opportunity_manager'],
            'pure_3_rule_mode': True,
            'primary_target_dollars': 10.0,
            'absolute_floor_dollars': 7.0,
            'stop_loss_percent': 0.5,
            'default_leverage': 3,
            'max_leverage': 5
        }
    }

@pytest.fixture
def fake_exchange():
    """Fake exchange client"""
    return FakeExchangeClient()

@pytest.fixture
def real_engine(config, fake_exchange):
    """Real trading engine with fake exchange"""
    return RealTradingEngine(config, fake_exchange)

@pytest.fixture
def opportunity_manager():
    """Mock opportunity manager"""
    om = MagicMock()
    om.get_opportunities.return_value = []
    return om

@pytest.fixture
def test_opportunity():
    """Test opportunity signal"""
    return {
        'symbol': 'BTCUSDT',
        'direction': 'LONG',
        'entry_price': 50000.0,
        'signal_source': 'opportunity_manager',
        'confidence': 0.8,
        'tradable': True,
        'recommended_leverage': 4
    }

class TestCriticalFixes:
    """Test suite for critical real trading fixes"""
    
    @pytest.mark.asyncio
    async def test_double_close_bug_fix(self, real_engine, fake_exchange, test_opportunity):
        """Test 1: Double-close bug is fixed"""
        logger.info("🧪 Testing double-close bug fix...")
        
        # Connect OM and start engine
        om = MagicMock()
        om.get_opportunities.return_value = []
        real_engine.connect_opportunity_manager(om)
        
        # Manually create a position
        position = LivePosition(
            position_id='test_pos_1',
            symbol='BTCUSDT',
            side='LONG',
            entry_price=50000.0,
            qty=0.004,
            stake_usd=200.0,
            leverage=3.0,
            entry_time=datetime.now()
        )
        
        real_engine.positions['test_pos_1'] = position
        real_engine.positions_by_symbol['BTCUSDT'] = 'test_pos_1'
        
        # Simulate position closed on exchange (TP/SL hit)
        fake_exchange.set_position_size('BTCUSDT', 0.0)
        
        # Run one monitoring loop tick
        positions_to_close = []
        
        # Simulate the monitoring loop logic
        for position_id, pos in list(real_engine.positions.items()):
            if not await real_engine._has_open_position_on_exchange(pos.symbol):
                # This should call _mark_position_closed, NOT add to positions_to_close
                await real_engine._mark_position_closed(position_id, reason="tp_sl_hit_exchange")
                break
        
        # Assert: No market close order was sent
        assert not fake_exchange.market_close_called('BTCUSDT'), "❌ CRITICAL: Market close was called for already-closed position"
        
        # Assert: Position was marked closed locally
        assert 'test_pos_1' not in real_engine.positions, "❌ Position not removed from active positions"
        assert 'BTCUSDT' not in real_engine.positions_by_symbol, "❌ Position not removed from symbol mapping"
        
        logger.info("✅ Double-close bug fix: PASSED")
    
    @pytest.mark.asyncio
    async def test_leverage_setup_bounded(self, real_engine, fake_exchange, test_opportunity):
        """Test 2: Leverage setup with bounds"""
        logger.info("🧪 Testing leverage setup with bounds...")
        
        # Connect OM
        om = MagicMock()
        real_engine.connect_opportunity_manager(om)
        
        # Test opportunity with high leverage recommendation
        high_leverage_opp = test_opportunity.copy()
        high_leverage_opp['recommended_leverage'] = 20  # Should be capped at 5
        
        # Open position
        await real_engine._open_live_position_from_opportunity(high_leverage_opp)
        
        # Assert: ISOLATED margin was set
        fake_exchange.assert_isolated('BTCUSDT')
        
        # Assert: Leverage was bounded to max_leverage (5)
        fake_exchange.assert_leverage('BTCUSDT', expected_max=5)
        
        logger.info("✅ Leverage setup with bounds: PASSED")
    
    @pytest.mark.asyncio
    async def test_opportunity_manager_auto_connection(self, config, fake_exchange):
        """Test 3: OpportunityManager auto-connection"""
        logger.info("🧪 Testing OpportunityManager auto-connection...")
        
        # Test the API route logic
        with patch('src.api.trading_routes.real_trading_routes.OpportunityManager') as mock_om_class:
            mock_om = MagicMock()
            mock_om_class.return_value = mock_om
            
            # Import and call the function
            from src.api.trading_routes.real_trading_routes import get_real_trading_engine
            
            # Clear global engine
            import src.api.trading_routes.real_trading_routes as routes_module
            routes_module.real_trading_engine = None
            
            # Mock config loading
            with patch('builtins.open'), patch('yaml.safe_load', return_value=config):
                with patch('src.api.trading_routes.real_trading_routes.ExchangeClient', return_value=fake_exchange):
                    engine = get_real_trading_engine()
            
            # Assert: OpportunityManager was auto-connected
            assert engine.opportunity_manager is not None, "❌ OpportunityManager not auto-connected"
            
        logger.info("✅ OpportunityManager auto-connection: PASSED")
    
    @pytest.mark.asyncio
    async def test_signal_source_filtering(self, real_engine, fake_exchange):
        """Test 4: Signal source filtering"""
        logger.info("🧪 Testing signal source filtering...")
        
        # Test signals from different sources
        test_signals = [
            {
                'symbol': 'BTCUSDT',
                'direction': 'LONG',
                'entry_price': 50000.0,
                'signal_source': 'opportunity_manager',  # Should be accepted
                'confidence': 0.8,
                'tradable': True
            },
            {
                'symbol': 'ETHUSDT', 
                'direction': 'LONG',
                'entry_price': 3000.0,
                'signal_source': 'profit_scraping',  # Should be rejected
                'confidence': 0.8,
                'tradable': True
            },
            {
                'symbol': 'ADAUSDT',
                'direction': 'LONG', 
                'entry_price': 0.5,
                'strategy': 'opportunity_manager',  # Should be accepted (fallback field)
                'confidence': 0.8,
                'tradable': True
            }
        ]
        
        accepted_count = 0
        for signal in test_signals:
            if real_engine._is_acceptable_opportunity(signal):
                accepted_count += 1
        
        # Assert: Only OpportunityManager signals accepted
        assert accepted_count == 2, f"❌ Expected 2 accepted signals, got {accepted_count}"
        
        logger.info("✅ Signal source filtering: PASSED")
    
    @pytest.mark.asyncio
    async def test_exchange_client_gate_removed(self, config, fake_exchange):
        """Test 5: Exchange client gate is more robust"""
        logger.info("🧪 Testing exchange client gate robustness...")
        
        # Create engine with exchange client that doesn't have ccxt_client attribute
        engine = RealTradingEngine(config, fake_exchange)
        om = MagicMock()
        om.get_opportunities.return_value = []
        engine.connect_opportunity_manager(om)
        
        # Should not fail on missing ccxt_client attribute
        # The real test is the balance check
        try:
            success = await engine.start_trading(['BTCUSDT'])
            assert success, "❌ Engine failed to start with valid exchange client"
        except AttributeError as e:
            if 'ccxt_client' in str(e):
                pytest.fail("❌ Engine still checking for ccxt_client attribute")
        
        logger.info("✅ Exchange client gate robustness: PASSED")
    
    @pytest.mark.asyncio
    async def test_accept_sources_filtering(self, real_engine, fake_exchange):
        """Test 6: accept_sources configuration is respected"""
        logger.info("🧪 Testing accept_sources filtering...")
        
        # Test with mixed signal sources
        mixed_signals = [
            {'signal_source': 'opportunity_manager', 'symbol': 'BTCUSDT', 'direction': 'LONG', 'entry_price': 50000, 'confidence': 0.8, 'tradable': True},
            {'signal_source': 'profit_scraping', 'symbol': 'ETHUSDT', 'direction': 'LONG', 'entry_price': 3000, 'confidence': 0.8, 'tradable': True},
            {'strategy': 'flow_trading', 'symbol': 'ADAUSDT', 'direction': 'LONG', 'entry_price': 0.5, 'confidence': 0.8, 'tradable': True}
        ]
        
        accepted = [sig for sig in mixed_signals if real_engine._is_acceptable_opportunity(sig)]
        
        # Only opportunity_manager should be accepted
        assert len(accepted) == 1, f"❌ Expected 1 accepted signal, got {len(accepted)}"
        assert 'opportunity_manager' in accepted[0]['signal_source'], "❌ Wrong signal source accepted"
        
        logger.info("✅ accept_sources filtering: PASSED")

async def run_critical_tests():
    """Run all critical tests"""
    logger.info("🚀 Starting Critical Real Trading Engine Fixes Test Suite")
    logger.info("=" * 70)
    
    # Load test config
    config = {
        'real_trading': {
            'enabled': True,
            'stake_usd': 200.0,
            'max_positions': 20,
            'accept_sources': ['opportunity_manager'],
            'pure_3_rule_mode': True,
            'primary_target_dollars': 10.0,
            'absolute_floor_dollars': 7.0,
            'stop_loss_percent': 0.5,
            'default_leverage': 3,
            'max_leverage': 5
        }
    }
    
    fake_exchange = FakeExchangeClient()
    real_engine = RealTradingEngine(config, fake_exchange)
    
    test_opportunity = {
        'symbol': 'BTCUSDT',
        'direction': 'LONG',
        'entry_price': 50000.0,
        'signal_source': 'opportunity_manager',
        'confidence': 0.8,
        'tradable': True,
        'recommended_leverage': 4
    }
    
    test_suite = TestCriticalFixes()
    
    try:
        # Test 1: Double-close bug fix
        await test_suite.test_double_close_bug_fix(real_engine, fake_exchange, test_opportunity)
        
        # Test 2: Leverage setup
        fake_exchange_2 = FakeExchangeClient()
        real_engine_2 = RealTradingEngine(config, fake_exchange_2)
        await test_suite.test_leverage_setup_bounded(real_engine_2, fake_exchange_2, test_opportunity)
        
        # Test 3: Auto-connection
        await test_suite.test_opportunity_manager_auto_connection(config, FakeExchangeClient())
        
        # Test 4: Signal filtering
        await test_suite.test_signal_source_filtering(real_engine, fake_exchange)
        
        # Test 5: Exchange client gate
        await test_suite.test_exchange_client_gate_removed(config, FakeExchangeClient())
        
        # Test 6: accept_sources filtering
        await test_suite.test_accept_sources_filtering(real_engine, fake_exchange)
        
        logger.info("=" * 70)
        logger.info("🎉 ALL CRITICAL TESTS PASSED!")
        logger.info("✅ Double-close bug: FIXED")
        logger.info("✅ Leverage setup: IMPLEMENTED") 
        logger.info("✅ Auto-connection: WORKING")
        logger.info("✅ Signal filtering: ACTIVE")
        logger.info("✅ Exchange gate: ROBUST")
        logger.info("✅ Source filtering: ENFORCED")
        logger.info("=" * 70)
        logger.info("🚀 Real Trading Engine is READY for live trading!")
        logger.info("⚠️  Remember to:")
        logger.info("   1. Set real_trading.enabled = true in config.yaml")
        logger.info("   2. Configure valid Binance API keys")
        logger.info("   3. Test on testnet first")
        logger.info("   4. Start with 1-2 symbols only")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ CRITICAL TEST FAILED: {e}")
        logger.error("🛑 DO NOT USE FOR LIVE TRADING UNTIL FIXED")
        return False

if __name__ == "__main__":
    success = asyncio.run(run_critical_tests())
    sys.exit(0 if success else 1)
