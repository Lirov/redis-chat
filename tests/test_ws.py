import json

import pytest


def test_websocket_connection_rejected_no_username(client):
    """Test that WebSocket connection is rejected without username."""
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/testroom"):
            pass  # This should raise an exception since no username is provided


def test_websocket_connection_rejected_invalid_username(client):
    """Test that WebSocket connection is rejected with invalid username."""
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/testroom?username="):
            pass  # This should raise an exception since username is empty


def test_websocket_connection_rejected_long_username(client):
    """Test that WebSocket connection is rejected with username too long."""
    long_username = "a" * 33  # 33 characters, limit is 32
    with pytest.raises(Exception):
        with client.websocket_connect(f"/ws/testroom?username={long_username}"):
            pass  # This should raise an exception since username is too long


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
