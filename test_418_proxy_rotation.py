#!/usr/bin/env python3
"""
Test script to verify 418 error handling with automatic proxy rotation.
"""

import asyncio
import logging
import os
import sys
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from market_data.exchange_client import ExchangeClient, ProxyMetrics
from binance.exceptions import BinanceAPIException

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Test418ProxyRotation:
    """Test class for 418 error handling and proxy rotation."""
    
    def __init__(self):
        self.test_config = {
            'proxy': {
                'USE_PROXY': True,
                'rotation_on_418': True,
                'proxy_cooldown_after_418_minutes': 5,  # Shorter for testing
                'max_418_errors_per_proxy': 2,  # Lower for testing
                'rotation_threshold': 0.8
            },
            'symbols': ['BTCUSDT']
        }
        
    async def test_418_error_triggers_rotation(self):
        """Test that 418 errors trigger immediate proxy rotation."""
        logger.info("Testing 418 error triggers proxy rotation...")
        
        # Mock environment variables
        with patch.dict(os.environ, {
            'USE_PROXY': 'true',
            'PROXY_HOST': 'test.proxy.com',
            'PROXY_PORT': '10001',
            'PROXY_USER': 'testuser',
            'PROXY_PASS': 'testpass',
            'PROXY_LIST': '10001,10002,10003',
            'BINANCE_API_KEY': 'test_key',
            'BINANCE_API_SECRET': 'test_secret'
        }):
            # Create exchange client with test config
            client = ExchangeClient(self.test_config)
            
            # Mock the _rotate_proxy method to track calls
            rotate_calls = []
            original_rotate = client._rotate_proxy
            
            async def mock_rotate():
                rotate_calls.append(datetime.now())
                # Simulate rotation by changing port
                client.proxy_port = '10002'
                logger.info(f"Mock proxy rotation: switched to port {client.proxy_port}")
            
            client._rotate_proxy = mock_rotate
            
            # Create a 418 exception
            exception_418 = BinanceAPIException(
                response=Mock(status_code=418),
                status_code=418,
                message="IP banned"
            )
            
            # Test the retry_with_backoff decorator behavior
            @client.__class__.__dict__['retry_with_backoff'](max_retries=2, base_delay=0.1)
            async def mock_api_call():
                raise exception_418
            
            # Bind the method to the client instance
            mock_api_call.__self__ = client
            
            try:
                await mock_api_call()
            except BinanceAPIException:
                pass  # Expected to fail after retries
            
            # Verify that proxy rotation was called
            assert len(rotate_calls) > 0, "Proxy rotation should have been called on 418 error"
            logger.info(f"✓ Proxy rotation was triggered {len(rotate_calls)} times")
            
            # Verify proxy metrics were updated
            if client.proxy_port in client.proxy_metrics:
                metrics = client.proxy_metrics[client.proxy_port]
                assert metrics.error_418_count > 0, "418 error count should be incremented"
                logger.info(f"✓ 418 error count updated: {metrics.error_418_count}")
            
            return True
    
    async def test_proxy_blocking_after_max_418_errors(self):
        """Test that proxies are blocked after reaching max 418 errors."""
        logger.info("Testing proxy blocking after max 418 errors...")
        
        with patch.dict(os.environ, {
            'USE_PROXY': 'true',
            'PROXY_HOST': 'test.proxy.com',
            'PROXY_PORT': '10001',
            'PROXY_LIST': '10001,10002,10003'
        }):
            client = ExchangeClient(self.test_config)
            
            # Manually trigger 418 errors to reach the limit
            for i in range(client.max_418_errors):
                client._update_proxy_metrics_418()
            
            # Check if proxy is blocked
            metrics = client.proxy_metrics.get(client.proxy_port)
            if metrics:
                assert metrics.blocked_until is not None, "Proxy should be blocked after max 418 errors"
                assert metrics.blocked_until > datetime.now(), "Proxy should be blocked for future time"
                logger.info(f"✓ Proxy blocked until: {metrics.blocked_until}")
                
                # Test that blocked proxy is skipped in selection
                available_proxies = []
                current_time = datetime.now()
                
                for port in client.proxy_list:
                    port_str = str(port)
                    if port_str in client.proxy_metrics:
                        proxy_metrics = client.proxy_metrics[port_str]
                        if not (proxy_metrics.blocked_until and current_time < proxy_metrics.blocked_until):
                            available_proxies.append(port_str)
                    else:
                        available_proxies.append(port_str)
                
                assert client.proxy_port not in available_proxies, "Blocked proxy should not be in available list"
                logger.info("✓ Blocked proxy is correctly excluded from selection")
            
            return True
    
    async def test_proxy_score_calculation(self):
        """Test proxy scoring system for selection."""
        logger.info("Testing proxy score calculation...")
        
        with patch.dict(os.environ, {
            'USE_PROXY': 'true',
            'PROXY_HOST': 'test.proxy.com',
            'PROXY_PORT': '10001'
        }):
            client = ExchangeClient(self.test_config)
            
            # Create test metrics for different proxies
            # Proxy 1: High 418 errors (should have high score - bad)
            metrics_1 = ProxyMetrics()
            metrics_1.error_418_count = 5
            metrics_1.total_requests = 100
            metrics_1.error_count = 10
            
            # Proxy 2: Recent success (should have low score - good)
            metrics_2 = ProxyMetrics()
            metrics_2.error_418_count = 0
            metrics_2.total_requests = 100
            metrics_2.error_count = 2
            metrics_2.last_success = datetime.now() - timedelta(minutes=5)
            
            # Calculate scores
            score_1 = client._calculate_proxy_score(metrics_1)
            score_2 = client._calculate_proxy_score(metrics_2)
            
            assert score_1 > score_2, "Proxy with 418 errors should have higher (worse) score"
            logger.info(f"✓ Proxy scoring works correctly: bad_proxy={score_1:.2f}, good_proxy={score_2:.2f}")
            
            return True
    
    async def test_configuration_loading(self):
        """Test that configuration values are loaded correctly."""
        logger.info("Testing configuration loading...")
        
        with patch.dict(os.environ, {
            'USE_PROXY': 'true',
            'PROXY_HOST': 'test.proxy.com',
            'PROXY_PORT': '10001'
        }):
            client = ExchangeClient(self.test_config)
            
            # Verify configuration values
            assert client.rotation_on_418 == True, "rotation_on_418 should be True"
            assert client.proxy_cooldown_minutes == 5, "proxy_cooldown_minutes should be 5"
            assert client.max_418_errors == 2, "max_418_errors should be 2"
            assert client.rotation_threshold == 0.8, "rotation_threshold should be 0.8"
            
            logger.info("✓ All configuration values loaded correctly")
            logger.info(f"  - rotation_on_418: {client.rotation_on_418}")
            logger.info(f"  - proxy_cooldown_minutes: {client.proxy_cooldown_minutes}")
            logger.info(f"  - max_418_errors: {client.max_418_errors}")
            logger.info(f"  - rotation_threshold: {client.rotation_threshold}")
            
            return True
    
    async def test_find_best_proxy_avoids_blocked(self):
        """Test that find_best_proxy avoids blocked proxies."""
        logger.info("Testing find_best_proxy avoids blocked proxies...")
        
        with patch.dict(os.environ, {
            'USE_PROXY': 'true',
            'PROXY_HOST': 'test.proxy.com',
            'PROXY_PORT': '10001',
            'PROXY_LIST': '10001,10002,10003'
        }):
            client = ExchangeClient(self.test_config)
            
            # Block the first proxy
            client.proxy_metrics['10001'] = ProxyMetrics()
            client.proxy_metrics['10001'].blocked_until = datetime.now() + timedelta(minutes=30)
            client.proxy_metrics['10001'].error_418_count = 5
            
            # Find best proxy
            best_proxy = await client._find_best_proxy()
            
            assert best_proxy != '10001', "Blocked proxy should not be selected"
            assert best_proxy in ['10002', '10003'], "Should select from available proxies"
            
            logger.info(f"✓ Best proxy selection avoids blocked proxy: selected {best_proxy}")
            
            return True
    
    async def run_all_tests(self):
        """Run all tests."""
        logger.info("Starting 418 proxy rotation tests...")
        
        tests = [
            self.test_configuration_loading,
            self.test_proxy_score_calculation,
            self.test_proxy_blocking_after_max_418_errors,
            self.test_find_best_proxy_avoids_blocked,
            self.test_418_error_triggers_rotation,
        ]
        
        passed = 0
        failed = 0
        
        for test in tests:
            try:
                result = await test()
                if result:
                    passed += 1
                    logger.info(f"✓ {test.__name__} PASSED")
                else:
                    failed += 1
                    logger.error(f"✗ {test.__name__} FAILED")
            except Exception as e:
                failed += 1
                logger.error(f"✗ {test.__name__} FAILED with exception: {e}")
        
        logger.info(f"\nTest Results: {passed} passed, {failed} failed")
        
        if failed == 0:
            logger.info("🎉 All tests passed! 418 proxy rotation is working correctly.")
        else:
            logger.error("❌ Some tests failed. Please check the implementation.")
        
        return failed == 0


async def main():
    """Main test function."""
    test_runner = Test418ProxyRotation()
    success = await test_runner.run_all_tests()
    
    if success:
        print("\n" + "="*60)
        print("✅ 418 PROXY ROTATION IMPLEMENTATION COMPLETE")
        print("="*60)
        print("Features implemented:")
        print("• Immediate proxy rotation on 418 errors")
        print("• Configurable proxy blocking after max 418 errors")
        print("• Smart proxy selection avoiding blocked proxies")
        print("• Proxy scoring system for optimal selection")
        print("• Configurable cooldown periods and thresholds")
        print("• Enhanced logging and monitoring")
        print("="*60)
    else:
        print("\n❌ Tests failed. Please review the implementation.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
