import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
import aiohttp
from src.market_data.exchange_client import ExchangeClient, ProxyMetrics

@pytest.fixture
def mock_env_vars():
    """Mock environment variables."""
    with patch.dict('os.environ', {
        'BINANCE_API_KEY': 'test_api_key',
        'BINANCE_API_SECRET': 'test_api_secret',
        'PROXY_HOST': 'test.proxy.com',
        'PROXY_PORT': '10001',
        'PROXY_USER': 'test_user',
        'PROXY_PASS': 'test_pass'
    }):
        yield

@pytest.fixture
async def exchange_client(mock_env_vars):
    """Create an ExchangeClient instance for testing."""
    client = ExchangeClient(
        api_key='test_api_key',
        api_secret='test_api_secret',
        testnet=True
    )
    yield client
    await client.close()

@pytest.mark.asyncio
async def test_proxy_initialization(exchange_client):
    """Test proxy initialization."""
    assert exchange_client.proxy_host == 'test.proxy.com'
    assert exchange_client.proxy_port == '10001'
    assert exchange_client.proxy_user == 'test_user'
    assert exchange_client.proxy_pass == 'test_pass'
    assert isinstance(exchange_client.proxy_auth, aiohttp.BasicAuth)

@pytest.mark.asyncio
async def test_proxy_connection_test(exchange_client):
    """Test proxy connection testing."""
    with patch('aiohttp.ClientSession.get') as mock_get:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_get.return_value.__aenter__.return_value = mock_response
        
        success = await exchange_client._test_proxy_connection()
        assert success is True
        
        # Verify proxy configuration
        mock_get.assert_called_once()
        call_args = mock_get.call_args[1]
        assert call_args['proxy'] == 'http://test.proxy.com:10001'
        assert isinstance(call_args['proxy_auth'], aiohttp.BasicAuth)

@pytest.mark.asyncio
async def test_proxy_rotation(exchange_client):
    """Test proxy rotation logic."""
    # Simulate poor performance for current proxy
    metrics = exchange_client.proxy_metrics['10001']
    metrics.error_count = 8
    metrics.total_requests = 10
    metrics.response_times.extend([1.5] * 10)  # Slow response times
    
    # Simulate better performance for alternative proxy
    alt_metrics = exchange_client.proxy_metrics['10002']
    alt_metrics.error_count = 1
    alt_metrics.total_requests = 10
    alt_metrics.response_times.extend([0.1] * 10)  # Fast response times
    
    with patch.object(exchange_client, '_reinitialize_websockets') as mock_reinit:
        await exchange_client._rotate_proxy()
        assert exchange_client.proxy_port == '10002'
        mock_reinit.assert_called_once()

@pytest.mark.asyncio
async def test_health_check_loop(exchange_client):
    """Test health check loop functionality."""
    with patch.object(exchange_client, '_check_proxy_health') as mock_check:
        # Start health check loop
        task = asyncio.create_task(exchange_client._health_check_loop())
        
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
async def test_proxy_metrics(exchange_client):
    """Test proxy metrics collection and analysis."""
    metrics = exchange_client.proxy_metrics['10001']
    
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
async def test_websocket_reinitialization(exchange_client):
    """Test WebSocket reinitialization after proxy rotation."""
    # Mock WebSocket connections
    mock_ws = AsyncMock()
    exchange_client.ws_connections['BTCUSDT'] = mock_ws
    
    # Test reinitialization
    with patch.object(exchange_client, '_setup_symbol_websocket') as mock_setup:
        await exchange_client._reinitialize_websockets()
        
        # Verify old connection was closed
        mock_ws.close.assert_called_once()
        
        # Verify new connection was established
        mock_setup.assert_called_once_with('BTCUSDT')

@pytest.mark.asyncio
async def test_proxy_failover(exchange_client):
    """Test proxy failover mechanism."""
    # Simulate connection failure
    with patch.object(exchange_client, '_test_proxy_connection', return_value=False):
        with patch.object(exchange_client, '_init_client') as mock_init:
            await exchange_client._handle_connection_error()
            
            # Verify client was reinitialized with new proxy
            assert mock_init.call_count > 0
            assert exchange_client.proxy_port in ['10002', '10003']

@pytest.mark.asyncio
async def test_proxy_performance_scoring(exchange_client):
    """Test proxy performance scoring."""
    # Set up test metrics
    metrics = exchange_client.proxy_metrics['10001']
    metrics.response_times.extend([0.1, 0.2, 0.3])
    metrics.error_count = 1
    metrics.total_requests = 10
    
    # Test performance scoring
    best_port = exchange_client._find_best_proxy()
    assert best_port in exchange_client.failover_ports

if __name__ == '__main__':
    pytest.main(['-v', 'test_exchange_client.py']) 