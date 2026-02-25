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
        assert data["input_language"]["value"] == "en-US"
        assert data["input_language"]["source"] == "default"
        assert data["input_continuous"]["value"] == "false"
        assert data["input_auto_submit"]["value"] == "false"
        assert len(data["presets"]) == 4  # professional, warm, energetic, calm
        assert data["valid_providers"] == ["openai", "elevenlabs"]
        assert "en-US" in data["valid_input_languages"]

    def test_get_cloud_stt_defaults(self, client):
        """Cloud STT: response should include cloud STT settings."""
        resp = client.get("/api/v1/settings/voice")
        data = resp.json()
        assert data["cloud_stt_language"]["value"] == "auto"
        assert data["cloud_stt_language"]["source"] == "default"
        assert data["engine_preference_order"]["value"] == "cloud,native,browser,on-device"
        assert data["engine_preference_order"]["source"] == "default"
        assert "cloud_stt_model" in data
        assert "valid_cloud_stt_languages" in data
        assert "auto" in data["valid_cloud_stt_languages"]
        assert "en-US" in data["valid_cloud_stt_languages"]
        assert "valid_engine_names" in data
        assert "cloud" in data["valid_engine_names"]
        assert "browser" in data["valid_engine_names"]

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

    def test_set_input_language(self, client):
        resp = client.put(
            "/api/v1/settings/voice/input_language",
            json={"value": "fr-FR"},
        )
        assert resp.status_code == 200
        assert resp.json()["value"] == "fr-FR"

    def test_set_invalid_input_language(self, client):
        resp = client.put(
            "/api/v1/settings/voice/input_language",
            json={"value": "xx-XX"},
        )
        assert resp.status_code == 400
        assert "Invalid language" in resp.json()["detail"]

    def test_set_input_continuous(self, client):
        resp = client.put(
            "/api/v1/settings/voice/input_continuous",
            json={"value": "true"},
        )
        assert resp.status_code == 200

    def test_set_invalid_input_continuous(self, client):
        resp = client.put(
            "/api/v1/settings/voice/input_continuous",
            json={"value": "yes"},
        )
        assert resp.status_code == 400
        assert "Must be 'true' or 'false'" in resp.json()["detail"]

    def test_set_input_auto_submit(self, client):
        resp = client.put(
            "/api/v1/settings/voice/input_auto_submit",
            json={"value": "true"},
        )
        assert resp.status_code == 200

    def test_set_invalid_input_auto_submit(self, client):
        resp = client.put(
            "/api/v1/settings/voice/input_auto_submit",
            json={"value": "maybe"},
        )
        assert resp.status_code == 400

    def test_set_cloud_stt_language(self, client):
        resp = client.put(
            "/api/v1/settings/voice/cloud_stt_language",
            json={"value": "en-US"},
        )
        assert resp.status_code == 200
        assert resp.json()["value"] == "en-US"

    def test_set_cloud_stt_language_auto(self, client):
        resp = client.put(
            "/api/v1/settings/voice/cloud_stt_language",
            json={"value": "auto"},
        )
        assert resp.status_code == 200
        assert resp.json()["value"] == "auto"

    def test_set_invalid_cloud_stt_language(self, client):
        resp = client.put(
            "/api/v1/settings/voice/cloud_stt_language",
            json={"value": "klingon"},
        )
        assert resp.status_code == 400
        assert "Invalid cloud STT language" in resp.json()["detail"]

    def test_set_engine_preference_order(self, client):
        resp = client.put(
            "/api/v1/settings/voice/engine_preference_order",
            json={"value": "browser,cloud"},
        )
        assert resp.status_code == 200
        assert resp.json()["value"] == "browser,cloud"

    def test_set_invalid_engine_preference_order(self, client):
        resp = client.put(
            "/api/v1/settings/voice/engine_preference_order",
            json={"value": "cloud,invalid_engine"},
        )
        assert resp.status_code == 400
        assert "Invalid engine" in resp.json()["detail"]

    def test_set_empty_engine_preference_order(self, client):
        resp = client.put(
            "/api/v1/settings/voice/engine_preference_order",
            json={"value": ""},
        )
        # Empty string may be caught by route handler (400) or Pydantic (422)
        assert resp.status_code in (400, 422)

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
