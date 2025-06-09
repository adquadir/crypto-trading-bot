import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from src.market_data.exchange_client import ExchangeClient

@pytest.fixture
async def exchange_client():
    """Create an exchange client for testing."""
    config = {
        'api_key': 'test_api_key',
        'api_secret': 'test_api_secret',
        'base_url': 'https://testnet.binance.vision/api',
        'ws_url': 'wss://testnet.binance.vision/ws/stream',
        'testnet': True,
        'symbols': ['BTCUSDT', 'ETHUSDT'],
        'scalping_mode': False
    }
    client = ExchangeClient(config=config)
    await client.initialize()
    yield client
    await client.shutdown()