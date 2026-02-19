"""API tests for settings override endpoints.

Tests cover:
- Auth (401 without admin key in production mode)
- CRUD operations (create, read, update, delete)
- Prefix filtering
- Key format validation (400)
- Not found (404)
"""

from contextlib import contextmanager
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import app


class TestSettingsOverrideAuth:
    """Test admin key authentication in production mode."""

    @pytest.fixture
    def production_client(self, db_session, monkeypatch):
        """Client without auth header, in production mode to enforce auth."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        from src.config.settings import get_settings

        get_settings.cache_clear()

        @contextmanager
        def mock_get_db():
            yield db_session

        with (
            patch("src.api.settings_override_routes.get_db", mock_get_db),
            patch("src.api.settings_routes.get_db", mock_get_db),
        ):
            with TestClient(app) as c:
                yield c

        monkeypatch.setenv("ENVIRONMENT", "development")
        get_settings.cache_clear()

    def test_list_requires_auth(self, production_client):
        """GET /overrides returns 401 without auth in production."""
        resp = production_client.get("/api/v1/settings/overrides")
        assert resp.status_code == 401

    def test_get_requires_auth(self, production_client):
        """GET /overrides/{key} returns 401 without auth in production."""
        resp = production_client.get("/api/v1/settings/overrides/model.summarization")
        assert resp.status_code == 401

    def test_put_requires_auth(self, production_client):
        """PUT /overrides/{key} returns 401 without auth in production."""
        resp = production_client.put(
            "/api/v1/settings/overrides/model.summarization",
            json={"value": "claude-haiku-4-5"},
        )
        assert resp.status_code == 401

    def test_delete_requires_auth(self, production_client):
        """DELETE /overrides/{key} returns 401 without auth in production."""
        resp = production_client.delete("/api/v1/settings/overrides/model.summarization")
        assert resp.status_code == 401

    def test_invalid_key_returns_403(self, production_client):
        """Wrong API key returns 403."""
        resp = production_client.get(
            "/api/v1/settings/overrides",
            headers={"X-Admin-Key": "wrong-key"},
        )
        assert resp.status_code == 403


class TestSettingsOverrideList:
    """Test listing overrides."""

    def test_list_empty(self, client):
        resp = client.get("/api/v1/settings/overrides")
        assert resp.status_code == 200
        data = resp.json()
        assert data["overrides"] == []

    def test_list_with_data(self, client):
        # Create overrides
        client.put(
            "/api/v1/settings/overrides/model.summarization",
            json={"value": "claude-haiku-4-5"},
        )
        client.put(
            "/api/v1/settings/overrides/voice.provider",
            json={"value": "openai"},
        )

        resp = client.get("/api/v1/settings/overrides")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["overrides"]) == 2

    def test_list_with_prefix_filter(self, client):
        # Create overrides in different namespaces
        client.put(
            "/api/v1/settings/overrides/model.summarization",
            json={"value": "claude-haiku-4-5"},
        )
        client.put(
            "/api/v1/settings/overrides/model.theme_analysis",
            json={"value": "claude-sonnet-4-5"},
        )
        client.put(
            "/api/v1/settings/overrides/voice.provider",
            json={"value": "openai"},
        )

        resp = client.get("/api/v1/settings/overrides?prefix=model")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["overrides"]) == 2
        assert all(o["key"].startswith("model.") for o in data["overrides"])

    def test_list_with_nonexistent_prefix(self, client):
        resp = client.get("/api/v1/settings/overrides?prefix=nonexistent")
        assert resp.status_code == 200
        assert resp.json()["overrides"] == []


class TestSettingsOverrideGet:
    """Test getting a single override."""

    def test_get_existing(self, client):
        client.put(
            "/api/v1/settings/overrides/model.summarization",
            json={"value": "claude-haiku-4-5", "description": "Cost savings"},
        )

        resp = client.get("/api/v1/settings/overrides/model.summarization")
        assert resp.status_code == 200
        data = resp.json()
        assert data["key"] == "model.summarization"
        assert data["value"] == "claude-haiku-4-5"
        assert data["version"] == 1
        assert data["description"] == "Cost savings"

    def test_get_not_found(self, client):
        resp = client.get("/api/v1/settings/overrides/model.nonexistent")
        assert resp.status_code == 404

    def test_get_invalid_key_format(self, client):
        resp = client.get("/api/v1/settings/overrides/invalid")
        assert resp.status_code == 400
        assert "Invalid settings key format" in resp.json()["detail"]


class TestSettingsOverridePut:
    """Test creating and updating overrides."""

    def test_create_new(self, client):
        resp = client.put(
            "/api/v1/settings/overrides/model.summarization",
            json={"value": "claude-haiku-4-5"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["key"] == "model.summarization"
        assert data["value"] == "claude-haiku-4-5"
        assert data["version"] == 1

    def test_update_increments_version(self, client):
        client.put(
            "/api/v1/settings/overrides/model.summarization",
            json={"value": "claude-haiku-4-5"},
        )
        resp = client.put(
            "/api/v1/settings/overrides/model.summarization",
            json={"value": "claude-sonnet-4-5"},
        )
        assert resp.status_code == 200
        assert resp.json()["version"] == 2

    def test_put_with_description(self, client):
        resp = client.put(
            "/api/v1/settings/overrides/model.summarization",
            json={"value": "claude-haiku-4-5", "description": "Cost reduction"},
        )
        assert resp.status_code == 200

        # Verify description persisted
        get_resp = client.get("/api/v1/settings/overrides/model.summarization")
        assert get_resp.json()["description"] == "Cost reduction"

    def test_put_invalid_key_format(self, client):
        resp = client.put(
            "/api/v1/settings/overrides/INVALID",
            json={"value": "some-value"},
        )
        assert resp.status_code == 400

    def test_put_empty_value_rejected(self, client):
        resp = client.put(
            "/api/v1/settings/overrides/model.summarization",
            json={"value": ""},
        )
        assert resp.status_code == 422  # Pydantic min_length validation


class TestSettingsOverrideDelete:
    """Test deleting overrides."""

    def test_delete_existing(self, client):
        client.put(
            "/api/v1/settings/overrides/model.summarization",
            json={"value": "claude-haiku-4-5"},
        )
        resp = client.delete("/api/v1/settings/overrides/model.summarization")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

        # Verify it's gone
        get_resp = client.get("/api/v1/settings/overrides/model.summarization")
        assert get_resp.status_code == 404

    def test_delete_not_found(self, client):
        resp = client.delete("/api/v1/settings/overrides/model.nonexistent")
        assert resp.status_code == 404

    def test_delete_invalid_key_format(self, client):
        resp = client.delete("/api/v1/settings/overrides/INVALID")
        assert resp.status_code == 400
