import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set test environment variables
os.environ["REDIS_URL"] = "redis://localhost:6379/1"  # Use different DB for tests
os.environ["APP_HOST"] = "127.0.0.1"
os.environ["APP_PORT"] = "8001"  # Different port for tests

# Import after setting up environment
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_redis():
    """Mock Redis connection for testing."""
    mock_redis = AsyncMock()

    # Mock common Redis operations
    mock_redis.lrange.return_value = []
    mock_redis.smembers.return_value = set()
    mock_redis.sadd.return_value = 1
    mock_redis.srem.return_value = 1
    mock_redis.scard.return_value = 0
    mock_redis.delete.return_value = 1
    mock_redis.lpush.return_value = 1
    mock_redis.ltrim.return_value = True
    mock_redis.publish.return_value = 1

    # Mock pubsub
    mock_pubsub = AsyncMock()
    mock_pubsub.subscribe.return_value = None
    mock_pubsub.unsubscribe.return_value = None
    mock_pubsub.close.return_value = None
    mock_pubsub.listen.return_value = []
    mock_redis.pubsub.return_value = mock_pubsub

    return mock_redis


@pytest.fixture
def client(mock_redis, monkeypatch):
    """Create a test client with mocked Redis."""
    # Patch the redis import in the main module
    monkeypatch.setattr("app.main.redis", mock_redis)

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
async def async_client(mock_redis, monkeypatch):
    """Create an async test client with mocked Redis."""
    # Patch the redis import in the main module
    monkeypatch.setattr("app.main.redis", mock_redis)

    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def sample_history():
    """Sample chat history for testing."""
    return [
        '{"type": "message", "room": "test", "username": "alice", "text": "hello", "ts": 1234567890}',
        '{"type": "message", "room": "test", "username": "bob", "text": "hi there", "ts": 1234567891}',
    ]
