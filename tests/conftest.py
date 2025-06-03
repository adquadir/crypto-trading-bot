import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from src.market_data.exchange_client import ExchangeClient

@pytest_asyncio.fixture
async def exchange_client():
    with patch("aiohttp.ClientSession") as MockSession:
        mock_session_instance = AsyncMock()
        mock_session_instance.get.return_value.__aenter__.return_value.status = 200
        MockSession.return_value = mock_session_instance

        with patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock) as mock_ws_connect:
            mock_ws_connect.return_value.__aenter__.return_value = AsyncMock()

            with patch("src.market_data.exchange_client.Client") as mock_binance:
                mock_binance.return_value.ping.return_value = {}
                mock_binance.return_value.get_order_book.return_value = {'bids': [], 'asks': []}
                mock_binance.return_value.get_klines.return_value = []
                mock_binance.return_value.get_ticker.return_value = {'price': '100.0'}

                client = ExchangeClient(
                    api_key='test_api_key',
                    api_secret='test_api_secret',
                    symbol_set={"BTCUSDT"},
                    testnet=True,
                    proxy_list=["10001", "10002"],
                    failover_ports=["10001", "10002", "10003"],
                    proxy_config={
                        "host": "test.proxy.com",
                        "port": "10001",
                        "user": "test_user",
                        "pass": "test_pass"
                    }
                )

                await client.setup()
                yield client
                client.session = None  # Prevent MagicMock await error
                await client.close()
