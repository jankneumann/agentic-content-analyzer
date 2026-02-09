"""Tests for POST /api/v1/settings/prompts/{key}/test endpoint.

Tests the prompt testing feature which renders templates with variables
and returns the rendered result.
"""


class TestPromptTestEndpoint:
    """Tests for the prompt test endpoint."""

    def test_test_prompt_renders_template(self, client):
        """Test rendering a prompt template with variables."""
        response = client.post(
            "/api/v1/settings/prompts/pipeline.podcast_script.length_brief/test",
            json={"variables": {"period": "daily"}},
        )

        assert response.status_code == 200
        data = response.json()

        assert "rendered_prompt" in data
        assert "variable_names" in data
        # The variable should have been substituted
        assert "daily" in data["rendered_prompt"]
        # {period} should no longer appear as a placeholder
        assert "{period}" not in data["rendered_prompt"]

    def test_test_prompt_returns_variable_names(self, client):
        """Test that variable names are extracted from the template."""
        response = client.post(
            "/api/v1/settings/prompts/pipeline.podcast_script.length_brief/test",
            json={},
        )

        assert response.status_code == 200
        data = response.json()

        assert "variable_names" in data
        assert isinstance(data["variable_names"], list)
        # length_brief template should have a 'period' variable
        assert "period" in data["variable_names"]

    def test_test_prompt_with_draft_value(self, client):
        """Test rendering with a draft value instead of saved template."""
        response = client.post(
            "/api/v1/settings/prompts/pipeline.summarization.system/test",
            json={
                "draft_value": "Summarize this {title} by {author}.",
                "variables": {"title": "AI Newsletter", "author": "OpenAI"},
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["rendered_prompt"] == "Summarize this AI Newsletter by OpenAI."
        assert "title" in data["variable_names"]
        assert "author" in data["variable_names"]

    def test_test_prompt_leaves_unset_variables(self, client):
        """Test that unset variables remain as {placeholder}."""
        response = client.post(
            "/api/v1/settings/prompts/pipeline.summarization.system/test",
            json={
                "draft_value": "Title: {title}, Author: {author}",
                "variables": {"title": "My Title"},
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert "My Title" in data["rendered_prompt"]
        assert "{author}" in data["rendered_prompt"]

    def test_test_prompt_invalid_key(self, client):
        """Test with an invalid key format."""
        response = client.post(
            "/api/v1/settings/prompts/invalid/test",
            json={},
        )

        assert response.status_code == 400

    def test_test_prompt_not_found(self, client):
        """Test with a non-existent prompt key."""
        response = client.post(
            "/api/v1/settings/prompts/pipeline.nonexistent.system/test",
            json={},
        )

        assert response.status_code == 404

    def test_test_prompt_empty_variables(self, client):
        """Test rendering with no variables provided."""
        response = client.post(
            "/api/v1/settings/prompts/pipeline.podcast_script.length_brief/test",
            json={"variables": {}},
        )

        assert response.status_code == 200
        data = response.json()

        # Template should still be returned (with unresolved variables)
        assert len(data["rendered_prompt"]) > 0

    def test_test_prompt_with_override_active(self, client, db_session):
        """Test that test endpoint uses the override when no draft_value given."""
        # Set an override
        client.put(
            "/api/v1/settings/prompts/chat.summary.system",
            json={"value": "Custom: {topic} summary"},
        )

        # Test without draft_value — should use override
        response = client.post(
            "/api/v1/settings/prompts/chat.summary.system/test",
            json={"variables": {"topic": "AI"}},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["rendered_prompt"] == "Custom: AI summary"
        assert "topic" in data["variable_names"]


class TestListPromptsUpdated:
    """Tests for the updated list prompts endpoint."""

    def test_list_prompts_includes_all_variants(self, client):
        """Test that list now includes non-system prompt variants."""
        response = client.get("/api/v1/settings/prompts")

        assert response.status_code == 200
        data = response.json()

        keys = {p["key"] for p in data["prompts"]}

        # Should include template variants, not just .system keys
        assert "pipeline.podcast_script.system" in keys
        assert "pipeline.podcast_script.length_brief" in keys
        assert "pipeline.podcast_script.length_standard" in keys
        assert "pipeline.summarization.user_template" in keys

    def test_list_prompts_includes_version_and_description(self, client, db_session):
        """Test that version and description fields are returned."""
        # Set an override with description
        client.put(
            "/api/v1/settings/prompts/chat.summary.system",
            json={"value": "Custom prompt", "description": "Test change"},
        )

        response = client.get("/api/v1/settings/prompts")
        data = response.json()

        summary_prompt = next(p for p in data["prompts"] if p["key"] == "chat.summary.system")
        assert summary_prompt["has_override"] is True
        assert summary_prompt["version"] == 1
        assert summary_prompt["description"] == "Test change"

    def test_get_prompt_includes_version(self, client, db_session):
        """Test that get prompt returns version info."""
        # Set override
        client.put(
            "/api/v1/settings/prompts/chat.summary.system",
            json={"value": "v1"},
        )
        # Update to bump version
        client.put(
            "/api/v1/settings/prompts/chat.summary.system",
            json={"value": "v2"},
        )

        response = client.get("/api/v1/settings/prompts/chat.summary.system")
        data = response.json()

        assert data["version"] == 2

    def test_update_prompt_returns_version(self, client, db_session):
        """Test that update returns the new version."""
        response = client.put(
            "/api/v1/settings/prompts/chat.summary.system",
            json={"value": "Test prompt"},
        )

        data = response.json()
        assert data["version"] == 1

        # Update again
        response = client.put(
            "/api/v1/settings/prompts/chat.summary.system",
            json={"value": "Updated prompt"},
        )

        data = response.json()
        assert data["version"] == 2
