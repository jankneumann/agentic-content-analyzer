"""Tests for Content API security.

Verifies that content routes are protected by admin authentication
when running in production environment.
"""

from contextlib import contextmanager
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.config.settings import get_settings


@pytest.fixture
def raw_client(db_session, monkeypatch):
    """Create a raw TestClient without automatic auth header injection.

    Patches get_db to use the test database session.
    Disables worker to prevent DB connection attempts.
    """
    monkeypatch.setenv("WORKER_ENABLED", "false")
    get_settings.cache_clear()

    @contextmanager
    def mock_get_db():
        yield db_session

    # Patch get_db in content_routes
    with patch("src.api.content_routes.get_db", mock_get_db):
        with TestClient(app) as client:
            yield client


def test_content_routes_require_auth(raw_client, monkeypatch):
    """Verify content routes require admin key in production."""
    # Configure production environment
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ADMIN_API_KEY", "secret-key")
    monkeypatch.setenv("WORKER_ENABLED", "false")

    # Clear settings cache to pick up new env vars
    get_settings.cache_clear()

    # 1. Test missing header (401)
    response = raw_client.get("/api/v1/contents")
    assert response.status_code == 401
    assert "Missing authentication header" in response.json()["detail"]

    # 2. Test invalid key (403)
    response = raw_client.get(
        "/api/v1/contents",
        headers={"X-Admin-Key": "wrong-key"}
    )
    assert response.status_code == 403
    assert "Invalid admin API key" in response.json()["detail"]

    # 3. Test valid key (200)
    response = raw_client.get(
        "/api/v1/contents",
        headers={"X-Admin-Key": "secret-key"}
    )
    assert response.status_code == 200
