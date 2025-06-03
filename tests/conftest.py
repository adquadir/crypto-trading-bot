import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from src.market_data.exchange_client import ExchangeClient


@pytest_asyncio.fixture
async def exchange_client():
    with patch("aiohttp.ClientSession") as mock_session_class:
        # Create the mock session
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text.return_value = "pong"

        # Setup return values for get and ws_connect
        mock_session.get.return_value.__aenter__.return_value = mock_response
        mock_session.ws_connect.return_value.__aenter__.return_value = mock_response
        mock_session_class.return_value.__aenter__.return_value = mock_session

        # Patch Binance Client
        with patch('src.market_data.exchange_client.Client') as mock_binance_client_class:
            mock_binance = MagicMock()
            mock_binance.ping.return_value = {}
            mock_binance_client_class.return_value = mock_binance

            # Create the exchange client
            client = ExchangeClient(
                api_key='test_api_key',
                api_secret='test_api_secret',
                symbol_set={'BTCUSDT'},
                testnet=True
            )

            await client.initialize()
            yield client
            await client.close()
