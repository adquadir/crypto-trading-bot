import pytest
import pytest_asyncio
from typing import AsyncGenerator, Dict, Any
from unittest.mock import patch, AsyncMock, MagicMock
from src.market_data.exchange_client import ExchangeClient

@pytest_asyncio.fixture
async def exchange_client() -> AsyncGenerator[ExchangeClient, None]:
    """Fixture that provides an ExchangeClient instance for testing."""
    config = {
        'api_key': 'test_api_key',
        'api_secret': 'test_api_secret',
        'base_url': 'https://testnet.binance.vision/api',
        'ws_url': 'wss://testnet.binance.vision/ws/stream',
        'testnet': True,
        'symbols': ['BTCUSDT'],
        'discovery_mode': False,
        'discovery_interval': 3600,
        'cache_ttl': 60
    }
    
    client = ExchangeClient(config=config)
    await client.initialize()
    
    try:
        yield client
    finally:
        await client.shutdown()