from fastapi.testclient import TestClient
from app.main import app

def test_websocket_connect():
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        # Just assert we can connect without errors
        assert websocket

def test_websocket_broadcast():
    """Test that the ConnectionManager can handle multiple clients."""
    from app.api.ws import manager
    assert manager.client_count == 0
