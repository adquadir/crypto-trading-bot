import pytest
import asyncio
from unittest.mock import patch
from src.market_data.exchange_client import ExchangeClient

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def mock_env_vars():
    """Mock environment variables."""
    with patch.dict('os.environ', {
        'BINANCE_API_KEY': 'test_api_key',
        'BINANCE_API_SECRET': 'test_api_secret',
        'PROXY_HOST': 'test.proxy.com',
        'PROXY_PORT': '10001',
        'PROXY_USER': 'test_user',
        'PROXY_PASS': 'test_pass'
    }):
        yield

@pytest.fixture
async def exchange_client(mock_env_vars):
    """Create an ExchangeClient instance for testing."""
    client = ExchangeClient(
        api_key='test_api_key',
        api_secret='test_api_secret',
        symbol_set={'BTCUSDT'},
        testnet=True
    )
    
    try:
        await client.initialize()
        return client  # Return instead of yield
    finally:
        await client.close() 