"""API tests for notification preferences endpoints.

Tests cover:
- GET /api/v1/settings/notifications/ - List all preferences with source badges
- PUT /api/v1/settings/notifications/{event_type} - Update a preference
- DELETE /api/v1/settings/notifications/{event_type} - Reset preference to default

Preference resolution order: env var > DB override > default (all enabled).
"""

import pytest

from src.config.settings import get_settings
from src.models.notification import NotificationEventType

# All 7 event types for completeness checks
ALL_EVENT_TYPES = [e.value for e in NotificationEventType]
EXPECTED_EVENT_COUNT = 7


class TestGetPreferences:
    """Test GET /api/v1/settings/notifications/."""

    def test_get_preferences_all_default(self, client):
        """Returns all 7 event types with source='default' and enabled=True."""
        resp = client.get("/api/v1/settings/notifications")
        assert resp.status_code == 200

        data = resp.json()
        assert "preferences" in data
        prefs = data["preferences"]
        assert len(prefs) == EXPECTED_EVENT_COUNT

        returned_types = set()
        for pref in prefs:
            assert pref["enabled"] is True
            assert pref["source"] == "default"
            assert pref["description"] != ""
            returned_types.add(pref["event_type"])

        # Every NotificationEventType must be represented
        assert returned_types == set(ALL_EVENT_TYPES)

    def test_get_preferences_with_db_override(self, client):
        """After PUT, the affected preference shows source='db'."""
        # Create a DB override
        client.put(
            "/api/v1/settings/notifications/batch_summary",
            json={"enabled": False},
        )

        resp = client.get("/api/v1/settings/notifications")
        assert resp.status_code == 200

        prefs = {p["event_type"]: p for p in resp.json()["preferences"]}

        # The overridden preference should be db-sourced and disabled
        batch = prefs["batch_summary"]
        assert batch["enabled"] is False
        assert batch["source"] == "db"

        # All other preferences remain default
        for event_type in ALL_EVENT_TYPES:
            if event_type != "batch_summary":
                assert prefs[event_type]["source"] == "default"
                assert prefs[event_type]["enabled"] is True

    def test_get_preferences_with_env_override(self, client, monkeypatch):
        """When env var is set, shows source='env' with correct value."""
        monkeypatch.setenv("NOTIFICATION_DIGEST_CREATION", "false")
        get_settings.cache_clear()

        resp = client.get("/api/v1/settings/notifications")
        assert resp.status_code == 200

        prefs = {p["event_type"]: p for p in resp.json()["preferences"]}

        digest = prefs["digest_creation"]
        assert digest["enabled"] is False
        assert digest["source"] == "env"

    def test_get_preferences_env_true(self, client, monkeypatch):
        """Env var set to 'true' is correctly resolved."""
        monkeypatch.setenv("NOTIFICATION_JOB_FAILURE", "true")
        get_settings.cache_clear()

        resp = client.get("/api/v1/settings/notifications")
        assert resp.status_code == 200

        prefs = {p["event_type"]: p for p in resp.json()["preferences"]}

        job_failure = prefs["job_failure"]
        assert job_failure["enabled"] is True
        assert job_failure["source"] == "env"

    def test_get_preferences_env_overrides_db(self, client, monkeypatch):
        """Env var takes precedence over DB override."""
        # Set DB override to enabled
        client.put(
            "/api/v1/settings/notifications/theme_analysis",
            json={"enabled": True},
        )

        # Set env var to disabled (higher precedence)
        monkeypatch.setenv("NOTIFICATION_THEME_ANALYSIS", "false")
        get_settings.cache_clear()

        resp = client.get("/api/v1/settings/notifications")
        assert resp.status_code == 200

        prefs = {p["event_type"]: p for p in resp.json()["preferences"]}

        theme = prefs["theme_analysis"]
        assert theme["enabled"] is False
        assert theme["source"] == "env"


class TestUpdatePreference:
    """Test PUT /api/v1/settings/notifications/{event_type}."""

    def test_update_preference_disable(self, client):
        """PUT sets preference and returns source='db'."""
        resp = client.put(
            "/api/v1/settings/notifications/batch_summary",
            json={"enabled": False},
        )
        assert resp.status_code == 200

        data = resp.json()
        assert data["event_type"] == "batch_summary"
        assert data["enabled"] is False
        assert data["source"] == "db"

    def test_update_preference_enable(self, client):
        """PUT with enabled=True stores the preference."""
        # First disable
        client.put(
            "/api/v1/settings/notifications/pipeline_completion",
            json={"enabled": False},
        )

        # Then re-enable
        resp = client.put(
            "/api/v1/settings/notifications/pipeline_completion",
            json={"enabled": True},
        )
        assert resp.status_code == 200

        data = resp.json()
        assert data["event_type"] == "pipeline_completion"
        assert data["enabled"] is True
        assert data["source"] == "db"

    def test_update_preference_invalid_type(self, client):
        """PUT with invalid event type returns 400."""
        resp = client.put(
            "/api/v1/settings/notifications/nonexistent_type",
            json={"enabled": False},
        )
        assert resp.status_code == 400
        assert "Invalid event type" in resp.json()["detail"]

    def test_update_preference_env_controlled(self, client, monkeypatch):
        """PUT returns 409 when env var controls the preference."""
        monkeypatch.setenv("NOTIFICATION_BATCH_SUMMARY", "true")
        get_settings.cache_clear()

        resp = client.put(
            "/api/v1/settings/notifications/batch_summary",
            json={"enabled": False},
        )
        assert resp.status_code == 409
        assert "environment variable" in resp.json()["detail"]
        assert "NOTIFICATION_BATCH_SUMMARY" in resp.json()["detail"]

    def test_update_preference_persists_in_get(self, client):
        """PUT change is visible in subsequent GET."""
        client.put(
            "/api/v1/settings/notifications/audio_generation",
            json={"enabled": False},
        )

        resp = client.get("/api/v1/settings/notifications")
        assert resp.status_code == 200

        prefs = {p["event_type"]: p for p in resp.json()["preferences"]}
        assert prefs["audio_generation"]["enabled"] is False
        assert prefs["audio_generation"]["source"] == "db"

    @pytest.mark.parametrize("event_type", ALL_EVENT_TYPES)
    def test_update_all_valid_event_types(self, client, event_type):
        """Every valid event type can be updated without error."""
        resp = client.put(
            f"/api/v1/settings/notifications/{event_type}",
            json={"enabled": False},
        )
        assert resp.status_code == 200
        assert resp.json()["event_type"] == event_type


class TestResetPreference:
    """Test DELETE /api/v1/settings/notifications/{event_type}."""

    def test_reset_preference(self, client):
        """DELETE resets preference to default (enabled=True, source='default')."""
        # First create a DB override
        client.put(
            "/api/v1/settings/notifications/script_generation",
            json={"enabled": False},
        )

        # Then reset it
        resp = client.delete("/api/v1/settings/notifications/script_generation")
        assert resp.status_code == 200

        data = resp.json()
        assert data["event_type"] == "script_generation"
        assert data["enabled"] is True
        assert data["source"] == "default"

    def test_reset_preference_reflects_in_get(self, client):
        """After DELETE, GET shows default source."""
        # Override then reset
        client.put(
            "/api/v1/settings/notifications/job_failure",
            json={"enabled": False},
        )
        client.delete("/api/v1/settings/notifications/job_failure")

        resp = client.get("/api/v1/settings/notifications")
        assert resp.status_code == 200

        prefs = {p["event_type"]: p for p in resp.json()["preferences"]}
        assert prefs["job_failure"]["enabled"] is True
        assert prefs["job_failure"]["source"] == "default"

    def test_reset_preference_invalid_type(self, client):
        """DELETE with invalid event type returns 400."""
        resp = client.delete("/api/v1/settings/notifications/not_a_real_type")
        assert resp.status_code == 400
        assert "Invalid event type" in resp.json()["detail"]

    def test_reset_preference_no_override_exists(self, client):
        """DELETE on a preference with no DB override succeeds silently."""
        resp = client.delete("/api/v1/settings/notifications/batch_summary")
        assert resp.status_code == 200

        data = resp.json()
        assert data["event_type"] == "batch_summary"
        assert data["enabled"] is True
        assert data["source"] == "default"
