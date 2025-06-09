import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime
import aiohttp
import statistics
from src.market_data.exchange_client import ExchangeClient, ProxyMetrics
from src.market_data.websocket import MarketDataWebSocket

@pytest.fixture
def mock_binance_client():
    with patch('src.market_data.exchange_client.Client') as mock_client:
        mock_instance = MagicMock()
        mock_instance.ping.return_value = {}
        mock_instance.get_klines.return_value = []
        mock_instance.get_order_book.return_value = {'bids': [], 'asks': []}
        mock_instance.get_ticker.return_value = {'price': '100.0'}
        mock_client.return_value = mock_instance
        yield mock_instance

@pytest.mark.asyncio
async def test_proxy_initialization(exchange_client, mock_binance_client):
    assert exchange_client.proxy_host == 'test.proxy.com'
    assert exchange_client.proxy_port == '10001'
    assert exchange_client.proxy_user == 'test_user'
    assert exchange_client.proxy_pass == 'test_pass'
    assert isinstance(exchange_client.proxy_auth, aiohttp.BasicAuth)
    assert isinstance(exchange_client.proxy_metrics, dict)
    assert isinstance(exchange_client.ws_clients, dict)

@pytest.mark.asyncio
async def test_proxy_connection_test(exchange_client, mock_binance_client):
    # Mock aiohttp.ClientSession directly where it's used
    with patch('src.market_data.exchange_client.aiohttp.ClientSession') as mock_session_class:
        # Create mock session and response
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        
        # Set up the session as an async context manager
        mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_class.return_value.__aexit__ = AsyncMock(return_value=None)
        
        # Set up the get method to return a response context manager
        mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)
        
        success = await exchange_client._test_proxy_connection()
        assert success is True
        
        # Verify the session was created and used correctly
        mock_session_class.assert_called_once()
        mock_session.get.assert_called_once_with(
            "https://api.binance.com/api/v3/ping",
            proxy=f"http://{exchange_client.proxy_host}:{exchange_client.proxy_port}",
            proxy_auth=exchange_client.proxy_auth
        )

@pytest.mark.asyncio
async def test_proxy_rotation(exchange_client, mock_binance_client):
    exchange_client.proxy_metrics['10001'].error_count = 8
    exchange_client.proxy_metrics['10001'].total_requests = 10
    exchange_client.proxy_metrics['10001'].response_times.extend([1.5] * 10)
    
    exchange_client.proxy_metrics['10002'] = ProxyMetrics()
    exchange_client.proxy_metrics['10002'].error_count = 1
    exchange_client.proxy_metrics['10002'].total_requests = 10
    exchange_client.proxy_metrics['10002'].response_times.extend([0.1] * 10)
    
    with patch.object(exchange_client, '_reinitialize_websockets') as mock_reinit:
        await exchange_client._rotate_proxy()
        assert exchange_client.proxy_port == '10002'
        mock_reinit.assert_called_once()

@pytest.mark.asyncio
async def test_health_check_loop(exchange_client, mock_binance_client):
    with patch.object(exchange_client, '_check_proxy_health', new_callable=AsyncMock) as mock_check:
        async def stop_loop():
            await asyncio.sleep(0.1)
            exchange_client._shutdown_event.set()
        
        await asyncio.gather(
            exchange_client._health_check_loop(),
            stop_loop()
        )
        
        mock_check.assert_awaited_once()

@pytest.mark.asyncio
async def test_proxy_metrics(exchange_client, mock_binance_client):
    metrics = exchange_client.proxy_metrics['10001']
    metrics.response_times.clear()
    metrics.response_times.extend([0.1, 0.2, 0.3])
    metrics.error_count = 1
    metrics.total_requests = 4
    metrics.successful_requests = 3
    metrics.last_success = datetime.now()
    assert metrics.total_requests == 4
    assert metrics.successful_requests == 3
    assert len(metrics.response_times) == 3
    assert statistics.mean(metrics.response_times) == 0.2

@pytest.mark.asyncio
async def test_initialize_websocket():
    """Test WebSocket initialization."""
    client = ExchangeClient()
    await client.initialize()
    
    # Check that WebSocket clients were created
    assert len(client.ws_clients) > 0
    for symbol in client.symbols:
        assert symbol in client.ws_clients
        assert isinstance(client.ws_clients[symbol], MarketDataWebSocket)

@pytest.mark.asyncio
async def test_reinitialize_websockets():
    """Test WebSocket reinitialization."""
    client = ExchangeClient()
    await client.initialize()
    
    # Store original clients
    original_clients = client.ws_clients.copy()
    
    # Reinitialize WebSockets
    await client._reinitialize_websockets()
    
    # Check that new clients were created
    assert len(client.ws_clients) == len(original_clients)
    for symbol in client.symbols:
        assert symbol in client.ws_clients
        assert client.ws_clients[symbol] is not original_clients[symbol]

@pytest.mark.asyncio
async def test_websocket_connection():
    """Test WebSocket connection and message handling."""
    client = ExchangeClient()
    await client.initialize()
    
    # Check that WebSocket clients are connected
    for symbol, ws_client in client.ws_clients.items():
        assert ws_client.connection is not None
        assert ws_client.running is True

@pytest.mark.asyncio
async def test_proxy_failover(exchange_client, mock_binance_client):
    exchange_client.proxy_list = ['10001', '10002', '10003']
    exchange_client.proxy_metrics['10002'] = ProxyMetrics()
    exchange_client.proxy_metrics['10003'] = ProxyMetrics()
    
    with patch.object(exchange_client, '_test_proxy_connection', return_value=False):
        with patch.object(exchange_client, '_rotate_proxy', new_callable=AsyncMock) as mock_rotate:
            await exchange_client._handle_connection_error()
            mock_rotate.assert_awaited_once()

@pytest.mark.asyncio
async def test_proxy_performance_scoring(exchange_client, mock_binance_client):
    metrics = exchange_client.proxy_metrics['10001']
    metrics.response_times.extend([0.1, 0.2, 0.3])
    metrics.error_count = 1
    metrics.total_requests = 10
    best_port = exchange_client._find_best_proxy()
    assert best_port in exchange_client.failover_ports

@pytest.mark.asyncio
async def test_proxy_health_check(exchange_client, mock_binance_client):
    with patch.object(exchange_client, '_test_proxy_connection', return_value=True):
        await exchange_client._check_proxy_health()
        metrics = exchange_client.proxy_metrics[exchange_client.proxy_port]
        assert metrics.total_requests > 0
        assert metrics.successful_requests > 0
        assert metrics.last_success is not None

@pytest.mark.asyncio
async def test_proxy_connection_failure(exchange_client, mock_binance_client):
    with patch.object(exchange_client, '_test_proxy_connection', return_value=False):
        await exchange_client._check_proxy_health()
        metrics = exchange_client.proxy_metrics[exchange_client.proxy_port]
        assert metrics.error_count > 0
        assert metrics.last_error is not None