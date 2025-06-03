import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
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

@pytest.fixture(autouse=True)
def mock_aiohttp_session(monkeypatch):
    """Mock aiohttp.ClientSession with proper async context manager behavior."""
    mock_session = MagicMock()
    
    # Mock the response object returned by session.get(...)
    mock_response = AsyncMock()
    mock_response.__aenter__.return_value = mock_response
    mock_response.__aexit__.return_value = None
    mock_response.status = 200
    mock_response.text.return_value = "OK"
    
    # Mock session.get(...) to return a context manager
    mock_session.get.return_value = mock_response
    
    # Mock WebSocket
    mock_ws = AsyncMock()
    mock_ws.__aenter__.return_value = mock_ws
    mock_ws.__aexit__.return_value = None
    mock_session.ws_connect.return_value = mock_ws
    
    # Patch aiohttp.ClientSession to return mock_session
    mock_client_session = MagicMock()
    mock_client_session.return_value.__aenter__.return_value = mock_session
    mock_client_session.return_value.__aexit__.return_value = None
    
    monkeypatch.setattr("aiohttp.ClientSession", mock_client_session)

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
        yield client
    finally:
        await client.close() 