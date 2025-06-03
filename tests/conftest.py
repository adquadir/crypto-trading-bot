import os
import pytest
import pytest_asyncio
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
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
    # Mock HTTP response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text.return_value = "OK"

    # Mock WebSocket
    mock_ws = AsyncMock()
    mock_ws.__aiter__.return_value = iter([])

    # Mock session methods
    mock_session = AsyncMock()
    mock_session.get.return_value = AsyncMock()
    mock_session.get.return_value.__aenter__.return_value = mock_response
    mock_session.get.return_value.__aexit__.return_value = None

    mock_session.ws_connect.return_value = AsyncMock()
    mock_session.ws_connect.return_value.__aenter__.return_value = mock_ws
    mock_session.ws_connect.return_value.__aexit__.return_value = None

    mock_session.close = AsyncMock()

    # Patch aiohttp.ClientSession to return the mocked session
    mock_client_session = MagicMock()
    mock_client_session.return_value.__aenter__.return_value = mock_session
    mock_client_session.return_value.__aexit__.return_value = None

    monkeypatch.setattr("aiohttp.ClientSession", mock_client_session)

@pytest_asyncio.fixture
async def exchange_client():
    """Create an ExchangeClient instance for testing."""
    # ✅ Patch the Binance Client to prevent real network calls
    with patch('src.market_data.exchange_client.Client') as mock_client_class:
        mock_client_instance = MagicMock()
        mock_client_instance.ping.return_value = {}
        mock_client_instance.get_order_book.return_value = {'bids': [], 'asks': []}
        mock_client_class.return_value = mock_client_instance

        client = ExchangeClient(
            api_key='test_api_key',
            api_secret='test_api_secret',
            symbol_set={'BTCUSDT'},
            testnet=True
        )

        await client.initialize()
        yield client
        await client.close() 