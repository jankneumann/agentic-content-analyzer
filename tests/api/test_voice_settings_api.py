"""API tests for voice settings endpoints."""

import os
from unittest.mock import patch


class TestGetVoiceSettings:
    """Test GET /api/v1/settings/voice."""

    def test_get_defaults(self, client):
        resp = client.get("/api/v1/settings/voice")
        assert resp.status_code == 200
        data = resp.json()
        assert data["provider"]["value"] == "openai"
        assert data["provider"]["source"] == "default"
        assert data["default_voice"]["value"] == "nova"
        assert data["speed"]["value"] == "1.0"
        assert len(data["presets"]) == 4  # professional, warm, energetic, calm
        assert data["valid_providers"] == ["openai", "elevenlabs"]

    def test_db_override_reflected(self, client):
        # Set override via settings override API
        client.put(
            "/api/v1/settings/overrides/voice.provider",
            json={"value": "elevenlabs"},
        )

        resp = client.get("/api/v1/settings/voice")
        data = resp.json()
        assert data["provider"]["value"] == "elevenlabs"
        assert data["provider"]["source"] == "db"


class TestUpdateVoiceSetting:
    """Test PUT /api/v1/settings/voice/{field}."""

    def test_set_provider(self, client):
        resp = client.put(
            "/api/v1/settings/voice/provider",
            json={"value": "elevenlabs"},
        )
        assert resp.status_code == 200
        assert resp.json()["source"] == "db"

    def test_set_invalid_provider(self, client):
        resp = client.put(
            "/api/v1/settings/voice/provider",
            json={"value": "invalid_provider"},
        )
        assert resp.status_code == 400
        assert "Invalid provider" in resp.json()["detail"]

    def test_set_speed(self, client):
        resp = client.put(
            "/api/v1/settings/voice/speed",
            json={"value": "1.5"},
        )
        assert resp.status_code == 200

    def test_set_speed_too_low(self, client):
        resp = client.put(
            "/api/v1/settings/voice/speed",
            json={"value": "0.1"},
        )
        assert resp.status_code == 400
        assert "Invalid speed" in resp.json()["detail"]

    def test_set_speed_too_high(self, client):
        resp = client.put(
            "/api/v1/settings/voice/speed",
            json={"value": "3.0"},
        )
        assert resp.status_code == 400

    def test_set_speed_non_numeric(self, client):
        resp = client.put(
            "/api/v1/settings/voice/speed",
            json={"value": "fast"},
        )
        assert resp.status_code == 400

    def test_set_voice(self, client):
        resp = client.put(
            "/api/v1/settings/voice/default_voice",
            json={"value": "onyx"},
        )
        assert resp.status_code == 200

    def test_set_invalid_field(self, client):
        resp = client.put(
            "/api/v1/settings/voice/invalid_field",
            json={"value": "something"},
        )
        assert resp.status_code == 400

    def test_env_var_blocks_override(self, client):
        with patch.dict(os.environ, {"AUDIO_DIGEST_PROVIDER": "openai"}):
            resp = client.put(
                "/api/v1/settings/voice/provider",
                json={"value": "elevenlabs"},
            )
            assert resp.status_code == 409
            assert "environment variable" in resp.json()["detail"]


class TestResetVoiceSetting:
    """Test DELETE /api/v1/settings/voice/{field}."""

    def test_reset_to_default(self, client):
        # Set then reset
        client.put(
            "/api/v1/settings/voice/provider",
            json={"value": "elevenlabs"},
        )
        resp = client.delete("/api/v1/settings/voice/provider")
        assert resp.status_code == 200
        assert resp.json()["source"] == "default"
        assert resp.json()["value"] == "openai"

    def test_reset_invalid_field(self, client):
        resp = client.delete("/api/v1/settings/voice/invalid_field")
        assert resp.status_code == 400
