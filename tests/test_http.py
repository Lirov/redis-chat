

def test_get_rooms(client):
    """Test getting list of rooms."""
    response = client.get("/rooms")
    assert response.status_code == 200
    data = response.json()
    assert "rooms" in data
    assert isinstance(data["rooms"], list)


def test_get_history_empty(client):
    """Test getting history for a room with no messages."""
    response = client.get("/history/testroom?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


def test_get_history_with_data(client, sample_history):
    """Test getting history for a room with messages."""
    # Mock the redis lrange to return sample history
    client.app.dependency_overrides = {}
    
    # We need to patch the redis mock to return our sample data
    from app.main import redis
    redis.lrange.return_value = sample_history
    
    response = client.get("/history/testroom?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["username"] == "alice"
    assert data[0]["text"] == "hello"
    assert data[1]["username"] == "bob"
    assert data[1]["text"] == "hi there"


def test_get_history_limit_validation(client):
    """Test history endpoint limit validation."""
    # Test limit too high
    response = client.get("/history/testroom?limit=300")
    assert response.status_code == 422  # Validation error
    
    # Test limit too low
    response = client.get("/history/testroom?limit=0")
    assert response.status_code == 422  # Validation error
    
    # Test valid limit
    response = client.get("/history/testroom?limit=10")
    assert response.status_code == 200
