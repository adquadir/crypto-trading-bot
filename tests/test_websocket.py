import pytest
from fastapi.testclient import TestClient
from src.api.main import app
import os

client = TestClient(app)

def test_websocket_invalid_api_key():
    """Test that WebSocket connection is rejected with invalid API key."""
    with client.websocket_connect("/ws?api_key=invalid_key") as websocket:
        response = websocket.receive_text()
        assert "Invalid API key" in response

def test_websocket_missing_api_key():
    """Test that WebSocket connection is rejected without API key."""
    with pytest.raises(Exception):
        with client.websocket_connect("/ws") as websocket:
            pass

def test_websocket_valid_api_key():
    """Test that WebSocket connection is accepted with valid API key."""
    valid_key = os.getenv("API_KEY")
    if not valid_key:
        pytest.skip("API_KEY environment variable not set")
    
    with client.websocket_connect(f"/ws?api_key={valid_key}") as websocket:
        # Connection should be established
        assert websocket.client.connected

def test_websocket_signals_endpoint():
    """Test that /ws/signals endpoint works the same as /ws."""
    valid_key = os.getenv("API_KEY")
    if not valid_key:
        pytest.skip("API_KEY environment variable not set")
    
    with client.websocket_connect(f"/ws/signals?api_key={valid_key}") as websocket:
        # Connection should be established
        assert websocket.client.connected 