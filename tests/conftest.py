import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from src.market_data.exchange_client import ExchangeClient

@pytest.fixture(scope="function")
async def exchange_client():
    with patch("aiohttp.ClientSession") as mock_session_class:
        mock_session = MagicMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = AsyncMock()

        mock_response = MagicMock()
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value='pong')
        mock_session.get.return_value = mock_response
        mock_session.ws_connect.return_value = mock_response

        mock_session_class.return_value.__aenter__.return_value = mock_session
        mock_session_class.return_value.__aexit__.return_value = AsyncMock()
        mock_session_class.return_value.get.return_value = mock_response
        mock_session_class.return_value.ws_connect.return_value = mock_response

        client = ExchangeClient()

        client._test_proxy_connection = AsyncMock(return_value=True)
        client._check_proxy_health = AsyncMock()
        client._start_health_check_loop = AsyncMock()
        client._score_proxies = AsyncMock()
        client._rotate_proxy = AsyncMock()

        client.client = MagicMock()
        client.client.ping.return_value = True

        await client.initialize()
        yield client
        await client.shutdown()
