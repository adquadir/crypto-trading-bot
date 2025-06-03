import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timedelta
import aiohttp
import statistics
from src.market_data.exchange_client import ExchangeClient, ProxyMetrics

@pytest.fixture
def mock_binance_client():
    """Mock Binance client."""
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
    """Test proxy initialization."""
    async for client in exchange_client:
        assert client.proxy_host == 'test.proxy.com'
        assert client.proxy_port == '10001'
        assert client.proxy_user == 'test_user'
        assert client.proxy_pass == 'test_pass'
        assert isinstance(client.proxy_auth, aiohttp.BasicAuth)
        assert isinstance(client.proxy_metrics, dict)
        assert isinstance(client.ws_connections, dict)

@pytest.mark.asyncio
async def test_proxy_connection_test(exchange_client, mock_binance_client):
    """Test proxy connection testing."""
    async for client in exchange_client:
        success = await client._test_proxy_connection()
        assert success is True
        
        # Verify proxy configuration using the mock session
        mock_session = client.session
        mock_session.get.assert_called_once()
        call_args = mock_session.get.call_args[1]
        assert call_args['proxy'] == 'http://test.proxy.com:10001'
        assert isinstance(call_args['proxy_auth'], aiohttp.BasicAuth)

@pytest.mark.asyncio
async def test_proxy_rotation(exchange_client, mock_binance_client):
    """Test proxy rotation logic."""
    async for client in exchange_client:
        # Force rotation by setting minimum requests to 1
        client.min_requests_before_rotation = 1
        
        # Simulate poor performance for current proxy
        metrics = client.proxy_metrics['10001']
        metrics.error_count = 8
        metrics.total_requests = 10
        metrics.response_times.extend([1.5] * 10)  # Slow response times
        
        # Simulate better performance for alternative proxy
        alt_metrics = client.proxy_metrics['10002']
        alt_metrics.error_count = 1
        alt_metrics.total_requests = 10
        alt_metrics.response_times.extend([0.1] * 10)  # Fast response times
        
        with patch.object(client, '_reinitialize_websockets') as mock_reinit:
            await client._rotate_proxy()
            assert client.proxy_port == '10002'
            mock_reinit.assert_called_once()

@pytest.mark.asyncio
async def test_health_check_loop(exchange_client, mock_binance_client):
    """Test health check loop functionality."""
    async for client in exchange_client:
        with patch.object(client, '_check_proxy_health') as mock_check:
            # Start health check loop
            task = asyncio.create_task(client._health_check_loop())
            
            # Wait for a few iterations
            await asyncio.sleep(0.1)
            
            # Cancel the task
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
                
            assert mock_check.call_count > 0

@pytest.mark.asyncio
async def test_proxy_metrics(exchange_client, mock_binance_client):
    """Test proxy metrics collection and analysis."""
    async for client in exchange_client:
        metrics = client.proxy_metrics['10001']
        
        # Clear existing metrics before test
        metrics.response_times.clear()
        
        # Simulate some requests
        metrics.response_times.extend([0.1, 0.2, 0.3])
        metrics.error_count = 1
        metrics.total_requests = 4
        metrics.successful_requests = 3
        metrics.last_success = datetime.now()
        
        # Test metrics calculations
        assert metrics.total_requests == 4
        assert metrics.successful_requests == 3
        assert len(metrics.response_times) == 3
        assert statistics.mean(metrics.response_times) == 0.2

@pytest.mark.asyncio
async def test_websocket_reinitialization(exchange_client, mock_binance_client):
    """Test WebSocket reinitialization after proxy rotation."""
    async for client in exchange_client:
        # Mock WebSocket connections
        mock_ws = AsyncMock()
        client.ws_connections['BTCUSDT'] = mock_ws
        
        # Test reinitialization
        with patch.object(client, '_setup_symbol_websocket') as mock_setup:
            await client._reinitialize_websockets()
            
            # Verify old connection was closed
            mock_ws.close.assert_called_once()
            
            # Verify new connection was established
            mock_setup.assert_called_once_with('BTCUSDT')

@pytest.mark.asyncio
async def test_proxy_failover(exchange_client, mock_binance_client):
    """Test proxy failover mechanism."""
    async for client in exchange_client:
        # Setup multiple proxies
        client.proxy_list = ['10001', '10002', '10003']
        client.proxy_metrics['10002'] = ProxyMetrics()
        client.proxy_metrics['10003'] = ProxyMetrics()
        
        # Simulate connection failure
        with patch.object(client, '_test_proxy_connection', return_value=False):
            with patch.object(client, '_init_client') as mock_init:
                await client._handle_connection_error()
                
                # Verify client was reinitialized with new proxy
                assert mock_init.call_count > 0
                assert client.proxy_port != '10001'

@pytest.mark.asyncio
async def test_proxy_performance_scoring(exchange_client, mock_binance_client):
    """Test proxy performance scoring."""
    async for client in exchange_client:
        # Set up test metrics
        metrics = client.proxy_metrics['10001']
        metrics.response_times.extend([0.1, 0.2, 0.3])
        metrics.error_count = 1
        metrics.total_requests = 10
        
        # Test performance scoring
        best_port = client._find_best_proxy()
        assert best_port in client.failover_ports

@pytest.mark.asyncio
async def test_proxy_health_check(exchange_client, mock_binance_client):
    """Test proxy health check functionality."""
    async for client in exchange_client:
        with patch.object(client, '_test_proxy_connection', return_value=True):
            await client._check_proxy_health()
            
            # Verify metrics were updated
            metrics = client.proxy_metrics[client.proxy_port]
            assert metrics.total_requests > 0
            assert metrics.successful_requests > 0
            assert metrics.last_success is not None

@pytest.mark.asyncio
async def test_proxy_connection_failure(exchange_client, mock_binance_client):
    """Test handling of proxy connection failures."""
    async for client in exchange_client:
        with patch.object(client, '_test_proxy_connection', return_value=False):
            await client._check_proxy_health()
            
            # Verify error metrics were updated
            metrics = client.proxy_metrics[client.proxy_port]
            assert metrics.error_count > 0
            assert metrics.last_error is not None

if __name__ == '__main__':
    pytest.main(['-v', 'test_exchange_client.py']) 