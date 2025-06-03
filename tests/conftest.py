import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from src.market_data.exchange_client import ExchangeClient

@pytest_asyncio.fixture
async def exchange_client():
    with patch("aiohttp.ClientSession") as MockSession:
        # Mock session.get
        mock_response = MagicMock()
        mock_response.__aenter__.return_value.status = 200
        mock_response.__aexit__.return_value = None

        mock_session_instance = MagicMock()
        mock_session_instance.get.return_value = mock_response
        MockSession.return_value.__aenter__.return_value = mock_session_instance

        # Patch aiohttp.ClientSession.ws_connect
        mock_ws_context = AsyncMock()
        mock_ws = AsyncMock()
        mock_ws.__aenter__.return_value = mock_ws_context
        mock_ws.__aexit__.return_value = None

        with patch("aiohttp.ClientSession.ws_connect", return_value=mock_ws):
            with patch("src.market_data.exchange_client.Client") as mock_binance:
                mock_binance.return_value.ping.return_value = {}
                mock_binance.return_value.get_order_book.return_value = {'bids': [], 'asks': []}

                client = ExchangeClient(
                    api_key='test_api_key',
                    api_secret='test_api_secret',
                    symbol_set={"BTCUSDT"},
                    proxy_list=["10001", "10002"],
                    failover_ports=["10001", "10002", "10003"],
                    testnet=True,
                    proxy_config={
                        "host": "test.proxy.com",
                        "port": "10001",
                        "user": "test_user",
                        "pass": "test_pass"
                    }
)

                await client.initialize()
                yield client
                await client.close()
