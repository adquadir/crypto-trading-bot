import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from src.market_data.exchange_client import ExchangeClient

@pytest_asyncio.fixture
async def exchange_client():
    with patch("aiohttp.ClientSession") as MockSession:
        # Patch session.get to work with async context manager
        mock_response = MagicMock()
        mock_response.__aenter__.return_value.status = 200
        mock_response.__aexit__.return_value = None

        mock_session_instance = MagicMock()
        mock_session_instance.get.return_value = mock_response
        MockSession.return_value.__aenter__.return_value = mock_session_instance

        # Patch websocket connection
        with patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock) as mock_ws:
            mock_ws.return_value.__aenter__.return_value = AsyncMock()
            mock_ws.return_value.__aexit__.return_value = None

            # Patch Binance client
            with patch("src.market_data.exchange_client.Client") as mock_binance:
                mock_binance.return_value.ping.return_value = {}
                mock_binance.return_value.get_order_book.return_value = {'bids': [], 'asks': []}

                client = ExchangeClient(
                    symbol="BTCUSDT",
                    proxy_host="test.proxy.com",
                    proxy_port="10001",
                    proxy_user="test_user",
                    proxy_pass="test_pass",
                    proxy_list=["10001", "10002"],
                    failover_ports=["10001", "10002", "10003"]
                )
                await client.initialize()
                yield client
                await client.close()
