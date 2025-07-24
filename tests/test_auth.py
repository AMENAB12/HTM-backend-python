import pytest
from fastapi.testclient import TestClient

def test_login_success(client):
    """Test successful login"""
    response = client.post("/login", json={"username": "test", "password": "password"})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_login_invalid_credentials(client):
    """Test login with invalid credentials"""
    response = client.post("/login", json={"username": "test", "password": "wrong"})
    assert response.status_code == 401

def test_login_missing_credentials(client):
    """Test login with missing credentials"""
    response = client.post("/login", json={"username": "test"})
    assert response.status_code == 400 