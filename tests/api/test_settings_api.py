"""Tests for settings API endpoints.

Tests the prompt management API including:
- Listing all prompts with override status
- Getting individual prompts
- Setting prompt overrides
- Clearing prompt overrides (reset to default)
"""

from src.models.settings import PromptOverride


class TestListPrompts:
    """Tests for GET /api/v1/settings/prompts endpoint."""

    def test_list_prompts_returns_all_prompts(self, client):
        """Test that listing prompts returns chat and pipeline prompts."""
        response = client.get("/api/v1/settings/prompts")

        assert response.status_code == 200
        data = response.json()

        assert "prompts" in data
        assert isinstance(data["prompts"], list)
        assert len(data["prompts"]) > 0

    def test_list_prompts_includes_chat_prompts(self, client):
        """Test that chat prompts for all artifact types are included."""
        response = client.get("/api/v1/settings/prompts")

        assert response.status_code == 200
        data = response.json()

        # Find chat prompts
        chat_prompts = [p for p in data["prompts"] if p["category"] == "chat"]

        # Should have prompts for summary, digest, and script
        artifact_types = {p["key"].split(".")[1] for p in chat_prompts}
        assert "summary" in artifact_types
        assert "digest" in artifact_types
        assert "script" in artifact_types

    def test_list_prompts_includes_pipeline_prompts(self, client):
        """Test that pipeline step prompts are included."""
        response = client.get("/api/v1/settings/prompts")

        assert response.status_code == 200
        data = response.json()

        # Find pipeline prompts
        pipeline_prompts = [p for p in data["prompts"] if p["category"] == "pipeline"]

        # Should have prompts for pipeline steps
        step_names = {p["key"].split(".")[1] for p in pipeline_prompts}
        assert "summarization" in step_names
        assert "theme_analysis" in step_names
        assert "digest_creation" in step_names

    def test_list_prompts_has_required_fields(self, client):
        """Test that each prompt has all required fields."""
        response = client.get("/api/v1/settings/prompts")

        assert response.status_code == 200
        data = response.json()

        for prompt in data["prompts"]:
            assert "key" in prompt
            assert "category" in prompt
            assert "name" in prompt
            assert "default_value" in prompt
            assert "current_value" in prompt
            assert "has_override" in prompt

            # Key should follow pattern: category.name.type
            parts = prompt["key"].split(".")
            assert len(parts) >= 3

            # has_override should be boolean
            assert isinstance(prompt["has_override"], bool)

    def test_list_prompts_default_no_overrides(self, client):
        """Test that prompts have no overrides by default."""
        response = client.get("/api/v1/settings/prompts")

        assert response.status_code == 200
        data = response.json()

        # All prompts should have has_override=False initially
        for prompt in data["prompts"]:
            assert prompt["has_override"] is False
            assert prompt["current_value"] == prompt["default_value"]


class TestGetPrompt:
    """Tests for GET /api/v1/settings/prompts/{key} endpoint."""

    def test_get_chat_prompt(self, client):
        """Test getting a specific chat prompt."""
        response = client.get("/api/v1/settings/prompts/chat.summary.system")

        assert response.status_code == 200
        data = response.json()

        assert data["key"] == "chat.summary.system"
        assert data["category"] == "chat"
        assert "Summary" in data["name"]
        assert len(data["default_value"]) > 0
        assert data["has_override"] is False

    def test_get_pipeline_prompt(self, client):
        """Test getting a specific pipeline prompt."""
        response = client.get("/api/v1/settings/prompts/pipeline.summarization.system")

        assert response.status_code == 200
        data = response.json()

        assert data["key"] == "pipeline.summarization.system"
        assert data["category"] == "pipeline"
        assert len(data["default_value"]) > 0

    def test_get_prompt_invalid_key_format(self, client):
        """Test that invalid key format returns 400 error."""
        response = client.get("/api/v1/settings/prompts/invalid")

        assert response.status_code == 400
        assert "Invalid prompt key format" in response.json()["detail"]

    def test_get_prompt_not_found(self, client):
        """Test that non-existent prompt returns 404 error."""
        response = client.get("/api/v1/settings/prompts/chat.nonexistent.system")

        assert response.status_code == 404


class TestUpdatePrompt:
    """Tests for PUT /api/v1/settings/prompts/{key} endpoint."""

    def test_set_prompt_override(self, client, db_session):
        """Test setting a prompt override."""
        new_value = "This is a custom prompt for testing."

        response = client.put(
            "/api/v1/settings/prompts/chat.summary.system",
            json={"value": new_value},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["key"] == "chat.summary.system"
        assert data["current_value"] == new_value
        assert data["has_override"] is True

    def test_override_persists_in_database(self, client, db_session):
        """Test that override is persisted in database."""
        new_value = "Persisted custom prompt."

        # Set override
        client.put(
            "/api/v1/settings/prompts/chat.summary.system",
            json={"value": new_value},
        )

        # Verify in database
        override = db_session.query(PromptOverride).filter_by(key="chat.summary.system").first()

        assert override is not None
        assert override.value == new_value

    def test_override_appears_in_list(self, client, db_session):
        """Test that override shows up in prompt listing."""
        new_value = "Override that appears in list."

        # Set override
        client.put(
            "/api/v1/settings/prompts/chat.summary.system",
            json={"value": new_value},
        )

        # List prompts
        response = client.get("/api/v1/settings/prompts")
        data = response.json()

        # Find the overridden prompt
        summary_prompt = next(p for p in data["prompts"] if p["key"] == "chat.summary.system")

        assert summary_prompt["has_override"] is True
        assert summary_prompt["current_value"] == new_value
        # Default should still be available
        assert summary_prompt["default_value"] != new_value

    def test_update_override_value(self, client, db_session):
        """Test updating an existing override."""
        # Set initial override
        client.put(
            "/api/v1/settings/prompts/chat.summary.system",
            json={"value": "First value"},
        )

        # Update override
        response = client.put(
            "/api/v1/settings/prompts/chat.summary.system",
            json={"value": "Second value"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["current_value"] == "Second value"
        assert data["has_override"] is True

        # Verify only one override exists
        count = db_session.query(PromptOverride).filter_by(key="chat.summary.system").count()
        assert count == 1

    def test_clear_override_with_null(self, client, db_session):
        """Test clearing an override by setting value to null."""
        # Set override
        client.put(
            "/api/v1/settings/prompts/chat.summary.system",
            json={"value": "Temporary override"},
        )

        # Clear override
        response = client.put(
            "/api/v1/settings/prompts/chat.summary.system",
            json={"value": None},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["has_override"] is False
        # Current value should be back to default
        assert data["current_value"] != "Temporary override"

    def test_update_invalid_key_format(self, client):
        """Test updating with invalid key format."""
        response = client.put(
            "/api/v1/settings/prompts/invalid",
            json={"value": "test"},
        )

        assert response.status_code == 400

    def test_update_nonexistent_prompt(self, client):
        """Test updating a non-existent prompt returns 404."""
        response = client.put(
            "/api/v1/settings/prompts/chat.nonexistent.system",
            json={"value": "test"},
        )

        assert response.status_code == 404


class TestResetPrompt:
    """Tests for DELETE /api/v1/settings/prompts/{key} endpoint."""

    def test_reset_override(self, client, db_session):
        """Test resetting a prompt override to default."""
        # Set override
        client.put(
            "/api/v1/settings/prompts/chat.summary.system",
            json={"value": "Override to be reset"},
        )

        # Reset override
        response = client.delete("/api/v1/settings/prompts/chat.summary.system")

        assert response.status_code == 200
        data = response.json()

        assert data["has_override"] is False
        assert data["current_value"] != "Override to be reset"

    def test_reset_removes_from_database(self, client, db_session):
        """Test that reset removes override from database."""
        # Set override
        client.put(
            "/api/v1/settings/prompts/chat.summary.system",
            json={"value": "To be deleted"},
        )

        # Verify it exists
        count = db_session.query(PromptOverride).filter_by(key="chat.summary.system").count()
        assert count == 1

        # Reset
        client.delete("/api/v1/settings/prompts/chat.summary.system")

        # Verify it's gone
        count = db_session.query(PromptOverride).filter_by(key="chat.summary.system").count()
        assert count == 0

    def test_reset_nonexistent_override_succeeds(self, client):
        """Test that resetting a non-existent override succeeds gracefully."""
        # This should not fail even if no override exists
        response = client.delete("/api/v1/settings/prompts/chat.summary.system")

        assert response.status_code == 200
        data = response.json()
        assert data["has_override"] is False

    def test_reset_invalid_key_format(self, client):
        """Test resetting with invalid key format."""
        response = client.delete("/api/v1/settings/prompts/invalid")

        assert response.status_code == 400


class TestPromptServiceIntegration:
    """Tests for PromptService integration."""

    def test_prompt_service_loads_defaults(self, client):
        """Test that PromptService loads default prompts from YAML."""
        from src.services.prompt_service import PromptService

        service = PromptService()

        # Get a chat prompt
        prompt = service.get_chat_prompt("summary")

        assert prompt is not None
        assert len(prompt) > 0
        assert "assistant" in prompt.lower() or "ai" in prompt.lower()

    def test_prompt_service_returns_override_when_set(self, client, db_session):
        """Test that PromptService returns override when available."""
        from src.services.prompt_service import PromptService

        # Set an override
        override_value = "Custom override prompt for test."
        client.put(
            "/api/v1/settings/prompts/chat.summary.system",
            json={"value": override_value},
        )

        # Check via service
        service = PromptService(db_session)
        prompt = service.get_chat_prompt("summary")

        assert prompt == override_value

    def test_prompt_service_returns_default_when_no_override(self, client, db_session):
        """Test that PromptService returns default when no override exists."""
        from src.services.prompt_service import PromptService

        service = PromptService(db_session)

        # Get prompt without any override
        prompt = service.get_chat_prompt("summary")
        default = service._defaults.get("chat", {}).get("summary", {}).get("system", "")

        assert prompt == default

    def test_prompt_service_get_pipeline_prompt(self, client, db_session):
        """Test getting pipeline prompts through service."""
        from src.services.prompt_service import PromptService

        service = PromptService(db_session)

        prompt = service.get_pipeline_prompt("summarization")

        assert prompt is not None
        assert len(prompt) > 0


class TestMultipleOverrides:
    """Tests for managing multiple prompt overrides."""

    def test_multiple_overrides_independent(self, client, db_session):
        """Test that multiple overrides are independent."""
        # Set two different overrides
        client.put(
            "/api/v1/settings/prompts/chat.summary.system",
            json={"value": "Summary override"},
        )
        client.put(
            "/api/v1/settings/prompts/chat.digest.system",
            json={"value": "Digest override"},
        )

        # List prompts
        response = client.get("/api/v1/settings/prompts")
        data = response.json()

        # Find both prompts
        summary = next(p for p in data["prompts"] if p["key"] == "chat.summary.system")
        digest = next(p for p in data["prompts"] if p["key"] == "chat.digest.system")
        script = next(p for p in data["prompts"] if p["key"] == "chat.script.system")

        # Summary and digest should have overrides
        assert summary["has_override"] is True
        assert summary["current_value"] == "Summary override"

        assert digest["has_override"] is True
        assert digest["current_value"] == "Digest override"

        # Script should not have override
        assert script["has_override"] is False

    def test_reset_one_keeps_others(self, client, db_session):
        """Test that resetting one override doesn't affect others."""
        # Set two overrides
        client.put(
            "/api/v1/settings/prompts/chat.summary.system",
            json={"value": "Summary override"},
        )
        client.put(
            "/api/v1/settings/prompts/chat.digest.system",
            json={"value": "Digest override"},
        )

        # Reset summary
        client.delete("/api/v1/settings/prompts/chat.summary.system")

        # Check digest is still overridden
        response = client.get("/api/v1/settings/prompts/chat.digest.system")
        data = response.json()

        assert data["has_override"] is True
        assert data["current_value"] == "Digest override"


class TestPromptContent:
    """Tests for prompt content integrity."""

    def test_default_prompts_have_content(self, client):
        """Test that all default prompts have meaningful content."""
        response = client.get("/api/v1/settings/prompts")
        data = response.json()

        for prompt in data["prompts"]:
            # Default value should not be empty
            assert len(prompt["default_value"]) > 50, (
                f"Prompt {prompt['key']} has suspiciously short default value"
            )

    def test_prompt_preserves_formatting(self, client, db_session):
        """Test that prompts preserve newlines and formatting."""
        multiline_prompt = """Line 1
Line 2
Line 3

With blank line above."""

        # Set override
        client.put(
            "/api/v1/settings/prompts/chat.summary.system",
            json={"value": multiline_prompt},
        )

        # Retrieve and verify
        response = client.get("/api/v1/settings/prompts/chat.summary.system")
        data = response.json()

        assert data["current_value"] == multiline_prompt
        assert "\n" in data["current_value"]
