"""API tests for model settings endpoints."""

import os
from unittest.mock import patch


class TestGetModelSettings:
    """Test GET /api/v1/settings/models."""

    def test_list_all_steps(self, client):
        resp = client.get("/api/v1/settings/models")
        assert resp.status_code == 200
        data = resp.json()
        assert "steps" in data
        assert "available_models" in data
        # Should have 11 steps (all ModelStep values)
        assert len(data["steps"]) == 12

    def test_steps_have_required_fields(self, client):
        resp = client.get("/api/v1/settings/models")
        data = resp.json()
        for step in data["steps"]:
            assert "step" in step
            assert "current_model" in step
            assert "source" in step
            assert "env_var" in step
            assert "default_model" in step

    def test_default_source_when_no_overrides(self, client):
        resp = client.get("/api/v1/settings/models")
        data = resp.json()
        # Without any DB overrides or env vars, all should be "default"
        for step in data["steps"]:
            if not os.environ.get(step["env_var"]):
                assert step["source"] == "default"

    def test_available_models_include_cost(self, client):
        """User request: models should show cost."""
        resp = client.get("/api/v1/settings/models")
        data = resp.json()
        for model in data["available_models"]:
            assert "cost_per_mtok_input" in model
            assert "cost_per_mtok_output" in model
            assert "providers" in model
            assert "family" in model

    def test_db_override_reflected_in_source(self, client):
        # Set a model override via the settings override API
        client.put(
            "/api/v1/settings/overrides/model.summarization",
            json={"value": "claude-sonnet-4-5"},
        )

        resp = client.get("/api/v1/settings/models")
        data = resp.json()
        summarization = next(s for s in data["steps"] if s["step"] == "summarization")
        assert summarization["current_model"] == "claude-sonnet-4-5"
        assert summarization["source"] == "db"


class TestSetModelForStep:
    """Test PUT /api/v1/settings/models/{step}."""

    def test_set_valid_model(self, client):
        resp = client.put(
            "/api/v1/settings/models/summarization",
            json={"model_id": "claude-sonnet-4-5"},
        )
        assert resp.status_code == 200
        assert resp.json()["source"] == "db"

    def test_set_invalid_step(self, client):
        resp = client.put(
            "/api/v1/settings/models/invalid_step",
            json={"model_id": "claude-sonnet-4-5"},
        )
        assert resp.status_code == 400
        assert "Invalid step" in resp.json()["detail"]

    def test_set_invalid_model(self, client):
        resp = client.put(
            "/api/v1/settings/models/summarization",
            json={"model_id": "nonexistent-model"},
        )
        assert resp.status_code == 400
        assert "Unknown model" in resp.json()["detail"]

    def test_env_var_blocks_override(self, client):
        with patch.dict(os.environ, {"MODEL_SUMMARIZATION": "claude-haiku-4-5"}):
            resp = client.put(
                "/api/v1/settings/models/summarization",
                json={"model_id": "claude-sonnet-4-5"},
            )
            assert resp.status_code == 409
            assert "environment variable" in resp.json()["detail"]


class TestResetModelForStep:
    """Test DELETE /api/v1/settings/models/{step}."""

    def test_reset_to_default(self, client):
        # First set an override
        client.put(
            "/api/v1/settings/models/summarization",
            json={"model_id": "claude-sonnet-4-5"},
        )
        # Then reset
        resp = client.delete("/api/v1/settings/models/summarization")
        assert resp.status_code == 200
        assert resp.json()["source"] == "default"

    def test_reset_invalid_step(self, client):
        resp = client.delete("/api/v1/settings/models/invalid_step")
        assert resp.status_code == 400
