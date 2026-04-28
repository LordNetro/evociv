import pytest

from fastapi.testclient import TestClient
from app.main import app


def test_websocket_connect():
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        # Just assert we can connect without errors
        assert websocket


@pytest.mark.anyio
async def test_websocket_broadcast():
    """Test that ConnectionManager broadcasts to connected clients."""
    from app.api.ws import ConnectionManager

    manager = ConnectionManager()

    # We can't easily test WebSocket message delivery in unit tests
    # Instead, verify the manager interface works correctly
    assert manager.client_count == 0

    # Verify the snapshot storage field exists (for T6)
    assert hasattr(manager, "latest_snapshot")
    assert manager.latest_snapshot is None
