import json

import pytest


def test_websocket_connection_accepted_no_username(client):
    """Test that WebSocket connection is accepted without username (anonymous)."""
    with client.websocket_connect("/ws/testroom") as websocket:
        # Connection should be accepted as anonymous user
        assert websocket is not None


def test_websocket_connection_accepted_empty_username(client):
    """Test that WebSocket connection is accepted with empty username (anonymous)."""
    with client.websocket_connect("/ws/testroom?username=") as websocket:
        # Connection should be accepted as anonymous user
        assert websocket is not None


def test_websocket_connection_accepted_long_username(client):
    """Test that WebSocket connection is accepted with long username (truncated)."""
    long_username = "a" * 33  # 33 characters, limit is 32
    with client.websocket_connect(
        f"/ws/testroom?username={long_username}"
    ) as websocket:
        # Connection should be accepted (username will be truncated or handled)
        assert websocket is not None


def test_websocket_connection_accepted(client):
    """Test that WebSocket connection is accepted with valid username."""
    with client.websocket_connect("/ws/testroom?username=alice") as websocket:
        # Connection should be accepted
        assert websocket is not None


def test_websocket_message_sending(client):
    """Test sending a message through WebSocket."""
    with client.websocket_connect("/ws/testroom?username=alice") as websocket:
        # Send a message
        message = {"text": "Hello, world!"}
        websocket.send_text(json.dumps(message))

        # The message should be processed without error
        # Note: In a real test with Redis, we'd receive the message back
        # But with mocked Redis, we just verify no exceptions are raised


def test_websocket_plain_text_message(client):
    """Test sending plain text message through WebSocket."""
    with client.websocket_connect("/ws/testroom?username=alice") as websocket:
        # Send plain text (not JSON)
        websocket.send_text("Hello, world!")

        # The message should be processed without error
        # Plain text gets wrapped in a ChatIn object


def test_websocket_invalid_json_message(client):
    """Test sending invalid JSON through WebSocket."""
    with client.websocket_connect("/ws/testroom?username=alice") as websocket:
        # Send invalid JSON
        websocket.send_text('{"invalid": json}')

        # The message should be processed without error
        # Invalid JSON gets treated as plain text


def test_websocket_connection_with_invalid_token(client):
    """Test that WebSocket connection is rejected with invalid token."""
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/testroom?token=invalid_token"):
            pass  # This should raise an exception since token is invalid


def test_websocket_room_switching(client):
    """Test room switching functionality."""
    with client.websocket_connect("/ws/testroom1?username=alice") as websocket:
        # Send a room switch message
        switch_message = {"type": "switch", "room": "testroom2"}
        websocket.send_text(json.dumps(switch_message))

        # The message should be processed without error
        # In a real test, we'd verify the user switched rooms
