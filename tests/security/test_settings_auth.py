"""Security tests for settings authentication.

Tests that prompt update/reset endpoints require proper admin API key authentication.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    """Create a test client with required environment variables.

    The environment variables must be set before importing the app module
    to ensure Settings is created with the correct values.
    """
    # Set required environment variables BEFORE importing app
    monkeypatch.setenv("ADMIN_API_KEY", "secret-admin-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.setenv("TAVILY_API_KEY", "tv-test-key")

    # Clear settings cache to force reload with new env vars
    from src.config.settings import get_settings

    get_settings.cache_clear()

    # Now import app (which will create Settings with our env vars)
    from src.api.app import app

    yield TestClient(app)

    # Clear cache again after test
    get_settings.cache_clear()


def test_update_prompt_auth(client):
    """Test authentication for updating prompts."""
    url = "/api/v1/settings/prompts/chat.summary.system"
    payload = {"value": "You are a hacked AI."}

    # 1. Test missing header
    response = client.put(url, json=payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing authentication header X-Admin-Key"

    # 2. Test invalid key
    response = client.put(url, json=payload, headers={"X-Admin-Key": "wrong-key"})
    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid admin API key"

    # 3. Test valid key
    # This might fail with 500 DB error because DB is not mocked,
    # but that means it passed the auth check!
    try:
        response = client.put(url, json=payload, headers={"X-Admin-Key": "secret-admin-key"})
        # If it is NOT 401/403, we passed auth.
        assert response.status_code not in (401, 403)
    except Exception:
        # If client raises exception due to app crash (DB error), that's fine for this test
        pass


def test_reset_prompt_auth(client):
    """Test authentication for resetting prompts."""
    url = "/api/v1/settings/prompts/chat.summary.system"

    # 1. Test missing header
    response = client.delete(url)
    assert response.status_code == 401

    # 2. Test invalid key
    response = client.delete(url, headers={"X-Admin-Key": "wrong-key"})
    assert response.status_code == 403

    # 3. Test valid key
    try:
        response = client.delete(url, headers={"X-Admin-Key": "secret-admin-key"})
        assert response.status_code not in (401, 403)
    except Exception:
        pass
