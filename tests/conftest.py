import os
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from src.market_data.exchange_client import ExchangeClient

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """Mock environment variables."""
    monkeypatch.setenv('BINANCE_API_KEY', 'test_api_key')
    monkeypatch.setenv('BINANCE_API_SECRET', 'test_api_secret')
    monkeypatch.setenv('PROXY_HOST', 'test.proxy.com')
    monkeypatch.setenv('PROXY_PORT', '10001')
    monkeypatch.setenv('PROXY_USER', 'test_user')
    monkeypatch.setenv('PROXY_PASS', 'test_pass')
    monkeypatch.setenv('USE_TESTNET', 'True')

@pytest.fixture(autouse=True)
def mock_aiohttp_session(monkeypatch):
    """Mock aiohttp.ClientSession with async context manager support."""
    # Mock response for `session.get(...)`
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text.return_value = "OK"

    # Mock WebSocket returned by ws_connect
    mock_ws = AsyncMock()
    mock_ws.__aiter__.return_value = iter([])  # simulate empty WS stream

    # Mock aiohttp.ClientSession
    mock_session = AsyncMock()
    mock_session.get.return_value.__aenter__.return_value = mock_response
    mock_session.ws_connect.return_value.__aenter__.return_value = mock_ws
    mock_session.close.return_value = AsyncMock()

    # 🔥 Critical fix: Properly mock ClientSession as async context manager
    mock_client_session_constructor = MagicMock()
    mock_client_session_constructor.return_value.__aenter__.return_value = mock_session
    mock_client_session_constructor.return_value.__aexit__.return_value = None

    monkeypatch.setattr("aiohttp.ClientSession", mock_client_session_constructor)

@pytest.fixture
async def exchange_client():
    """Create an ExchangeClient instance for testing."""
    client = ExchangeClient(
        api_key='test_api_key',
        api_secret='test_api_secret',
        symbol_set={'BTCUSDT'},
        testnet=True
    )

    await client.initialize()
    yield client
    await client.close() 