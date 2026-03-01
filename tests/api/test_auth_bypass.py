from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.api import save_routes
from src.api.app import app


@pytest.fixture
def mock_db_session():
    """Mock the database session."""
    mock_session = MagicMock()
    return mock_session


@pytest.fixture
def client(monkeypatch, mock_db_session):
    """Test client with mocked DB context manager."""

    @contextmanager
    def mock_get_db():
        yield mock_db_session

    # Monkeypatch get_db in the route module that uses it
    monkeypatch.setattr(save_routes, "get_db", mock_get_db)

    return TestClient(app)


def test_auth_enforced_in_development_when_keys_set(monkeypatch, client, mock_db_session):
    """
    Security Fix Verification: In development mode, authentication MUST be enforced if keys are set.
    """
    # Force dev mode and set a secret key
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("APP_SECRET_KEY", "super-secret-key")

    # Mock the DB query to return None (Content not found)
    mock_db_session.query.return_value.filter.return_value.first.return_value = None

    # Try to access a protected endpoint
    response = client.get("/api/v1/content/123/status")

    # Expectation: 401 Unauthorized because we didn't provide credentials
    assert response.status_code == 401, f"Expected 401 Unauthorized, got {response.status_code}"


def test_auth_enforced_in_production(monkeypatch, client):
    """
    Verify that in production, auth is enforced.
    """
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("APP_SECRET_KEY", "super-secret-key")
    monkeypatch.setenv("ADMIN_API_KEY", "admin-key")

    response = client.get("/api/v1/content/123/status")
    assert response.status_code == 401
