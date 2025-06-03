import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from src.market_data.exchange_client import ExchangeClient


@pytest_asyncio.fixture
async def exchange_client():
    """Async fixture to return a fully mocked ExchangeClient."""

    # Patch aiohttp.ClientSession globally
    with patch("aiohttp.ClientSession") as mock_client_session_class:
        # Create a mock session object with context manager support
        mock_session_instance = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="pong")

        # Support for `async with session.get(...)`
        mock_session_instance.get.return_value.__aenter__.return_value = mock_response
        mock_session_instance.get.return_value.__aexit__.return_value = None
        mock_session_instance.ws_connect.return_value.__aenter__.return_value = mock_response
        mock_session_instance.ws_connect.return_value.__aexit__.return_value = None

        # Mock context manager for aiohttp.ClientSession()
        mock_client_session_class.return_value.__aenter__.return_value = mock_session_instance
        mock_client_session_class.return_value.__aexit__.return_value = None

        # Patch Binance Client
        with patch('src.market_data.exchange_client.Client') as mock_binance_client_class:
            mock_binance = MagicMock()
            mock_binance.ping.return_value = {}
            mock_binance.get_order_book.return_value = {'bids': [], 'asks': []}
            mock_binance_client_class.return_value = mock_binance

            # Create and initialize ExchangeClient
            client = ExchangeClient(
                api_key='test_api_key',
                api_secret='test_api_secret',
                symbol_set={'BTCUSDT'},
                testnet=True
            )

            await client.initialize()
            yield client
            await client.close()
