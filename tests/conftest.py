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
    # Create mock response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value="OK")
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    
    # Create mock session
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=mock_response)
    mock_session.ws_connect = AsyncMock(return_value=mock_response)
    mock_session.close = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    
    # Create mock ClientSession class
    mock_client_session = AsyncMock()
    mock_client_session.return_value = mock_session
    
    monkeypatch.setattr("aiohttp.ClientSession", mock_client_session)
    return mock_session

@pytest.fixture
async def exchange_client(mock_env_vars, mock_aiohttp_session):
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