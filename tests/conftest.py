import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def client():
    """Create a test client"""
    return TestClient(app)

@pytest.fixture
def auth_headers(client):
    """Get authentication headers"""
    response = client.post("/login", json={"username": "test", "password": "password"})
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"} 