import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.market_data.exchange_client import ProxyMetrics

@pytest.mark.asyncio
async def test_proxy_initialization(exchange_client):
    assert exchange_client.proxy_config["host"] == "test.proxy.com"
    assert exchange_client.proxy_config["port"] == "10001"
    assert exchange_client.proxy_config["user"] == "test_user"

@pytest.mark.asyncio
async def test_proxy_connection_test(exchange_client):
    with patch("aiohttp.ClientSession.get", new_callable=AsyncMock) as mock_get:
        mock_response = MagicMock()
        mock_response.status = 200
        mock_get.return_value.__aenter__.return_value = mock_response
        result = await exchange_client._test_proxy_connection("10001")
        assert result is True

@pytest.mark.asyncio
async def test_proxy_rotation(exchange_client):
    exchange_client.min_requests_before_rotation = 1
    exchange_client.proxy_metrics['10001'] = ProxyMetrics()
    exchange_client.proxy_metrics['10001'].error_count = 8
    exchange_client.proxy_metrics['10001'].total_requests = 10
    exchange_client.proxy_metrics['10001'].response_times.extend([1.5] * 10)

    exchange_client.proxy_metrics['10002'] = ProxyMetrics()
    exchange_client.proxy_metrics['10002'].error_count = 1
    exchange_client.proxy_metrics['10002'].total_requests = 10
    exchange_client.proxy_metrics['10002'].response_times.extend([0.1] * 10)

    with patch.object(exchange_client, '_reinitialize_websockets', new_callable=AsyncMock):
        await exchange_client.rotate_proxy()
        assert exchange_client.proxy_port == '10002'

@pytest.mark.asyncio
async def test_health_check_loop(exchange_client):
    assert exchange_client.health_check_task is not None

@pytest.mark.asyncio
async def test_proxy_metrics(exchange_client):
    exchange_client.proxy_metrics['10001'].total_requests += 1
    assert exchange_client.proxy_metrics['10001'].total_requests == 1

@pytest.mark.asyncio
async def test_websocket_reinitialization(exchange_client):
    exchange_client.ws_connections["BTCUSDT"] = AsyncMock()
    with patch.object(exchange_client, '_setup_symbol_websocket', new_callable=AsyncMock):
        await exchange_client._reinitialize_websockets()

@pytest.mark.asyncio
async def test_proxy_failover(exchange_client):
    exchange_client.proxy_list = ['10001', '10002', '10003']
    exchange_client.proxy_metrics['10002'] = ProxyMetrics()
    exchange_client.proxy_metrics['10003'] = ProxyMetrics()
    with patch.object(exchange_client, '_test_proxy_connection', return_value=False):
        with patch.object(exchange_client, '_init_client', new_callable=AsyncMock):
            await exchange_client._handle_connection_error()

@pytest.mark.asyncio
async def test_proxy_performance_scoring(exchange_client):
    exchange_client.proxy_metrics['10001'].response_times.extend([0.2, 0.4, 0.6])
    score = exchange_client._calculate_performance_score('10001')
    assert score > 0

@pytest.mark.asyncio
async def test_proxy_health_check(exchange_client):
    await exchange_client._check_proxy_health()

@pytest.mark.asyncio
async def test_proxy_connection_failure(exchange_client):
    with patch.object(exchange_client, '_test_proxy_connection', return_value=False):
        success = await exchange_client._test_proxy_connection("9999")
        assert not success
