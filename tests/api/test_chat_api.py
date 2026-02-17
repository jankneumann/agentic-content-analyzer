"""Tests for chat API endpoints.

Tests the multi-provider chat service integration including:
- Chat configuration endpoint
- Model listing from registry
- Message streaming (mocked LLM responses)
- Conversation management
"""

import pytest

from src.config.models import MODEL_REGISTRY


class TestChatConfig:
    """Tests for GET /api/v1/chat/config endpoint."""

    def test_get_chat_config_returns_models(self, client):
        """Test that chat config returns available models from registry."""
        response = client.get("/api/v1/chat/config")

        assert response.status_code == 200
        data = response.json()

        # Should have available_models list
        assert "available_models" in data
        assert isinstance(data["available_models"], list)
        assert len(data["available_models"]) > 0

        # Each model should have required fields
        for model in data["available_models"]:
            assert "id" in model
            assert "name" in model
            assert "provider" in model

    def test_get_chat_config_models_match_registry(self, client):
        """Test that returned models match the model registry."""
        response = client.get("/api/v1/chat/config")

        assert response.status_code == 200
        data = response.json()

        # Get model IDs from response
        returned_model_ids = {m["id"] for m in data["available_models"]}

        # All registry models should be in response
        for model_id in MODEL_REGISTRY.keys():
            assert model_id in returned_model_ids, f"Model {model_id} not in response"

    def test_get_chat_config_has_default_model(self, client):
        """Test that chat config includes a default model."""
        response = client.get("/api/v1/chat/config")

        assert response.status_code == 200
        data = response.json()

        assert "default_model" in data
        assert isinstance(data["default_model"], str)
        assert len(data["default_model"]) > 0

    def test_get_chat_config_default_model_is_valid(self, client):
        """Test that the default model is in the available models list."""
        response = client.get("/api/v1/chat/config")

        assert response.status_code == 200
        data = response.json()

        default_model = data["default_model"]
        available_ids = [m["id"] for m in data["available_models"]]

        assert default_model in available_ids, (
            f"Default model '{default_model}' not in available models"
        )

    def test_get_chat_config_has_feature_flags(self, client):
        """Test that chat config includes feature flags."""
        response = client.get("/api/v1/chat/config")

        assert response.status_code == 200
        data = response.json()

        # Should have web_search_enabled flag
        assert "web_search_enabled" in data
        assert isinstance(data["web_search_enabled"], bool)

    def test_get_chat_config_has_limits(self, client):
        """Test that chat config includes message limits."""
        response = client.get("/api/v1/chat/config")

        assert response.status_code == 200
        data = response.json()

        # Should have max_message_length
        assert "max_message_length" in data
        assert isinstance(data["max_message_length"], int)
        assert data["max_message_length"] > 0

        # Should have max_history_length
        assert "max_history_length" in data
        assert isinstance(data["max_history_length"], int)
        assert data["max_history_length"] > 0


class TestChatModelProviders:
    """Tests for model provider detection and grouping."""

    def test_claude_models_have_correct_provider(self, client):
        """Test that Claude models are labeled with 'claude' provider."""
        response = client.get("/api/v1/chat/config")

        assert response.status_code == 200
        data = response.json()

        for model in data["available_models"]:
            if model["id"].startswith("claude-"):
                assert model["provider"] == "claude", (
                    f"Model {model['id']} should have provider 'claude'"
                )

    def test_gemini_models_have_correct_provider(self, client):
        """Test that Gemini models are labeled with 'gemini' provider."""
        response = client.get("/api/v1/chat/config")

        assert response.status_code == 200
        data = response.json()

        for model in data["available_models"]:
            if model["id"].startswith("gemini-"):
                assert model["provider"] == "gemini", (
                    f"Model {model['id']} should have provider 'gemini'"
                )

    def test_gpt_models_have_correct_provider(self, client):
        """Test that GPT models are labeled with 'gpt' provider."""
        response = client.get("/api/v1/chat/config")

        assert response.status_code == 200
        data = response.json()

        for model in data["available_models"]:
            if model["id"].startswith("gpt-"):
                assert model["provider"] == "gpt", f"Model {model['id']} should have provider 'gpt'"


class TestConversationCreation:
    """Tests for POST /api/v1/chat/conversations endpoint."""

    def test_create_conversation_success(self, client, sample_summary):
        """Test creating a new chat conversation."""
        response = client.post(
            "/api/v1/chat/conversations",
            json={
                "artifact_type": "summary",
                "artifact_id": str(sample_summary.id),
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert "id" in data
        assert data["artifactType"] == "summary"  # camelCase in response
        assert data["artifactId"] == str(sample_summary.id)
        assert data["messages"] == []

    def test_create_conversation_with_digest(self, client, sample_digest):
        """Test creating a conversation for a digest."""
        response = client.post(
            "/api/v1/chat/conversations",
            json={
                "artifact_type": "digest",
                "artifact_id": str(sample_digest.id),
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["artifactType"] == "digest"  # camelCase in response
        assert data["artifactId"] == str(sample_digest.id)

    def test_create_conversation_with_script(self, client, sample_script):
        """Test creating a conversation for a script."""
        response = client.post(
            "/api/v1/chat/conversations",
            json={
                "artifact_type": "script",
                "artifact_id": str(sample_script.id),
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["artifactType"] == "script"  # camelCase in response
        assert data["artifactId"] == str(sample_script.id)

    def test_create_conversation_invalid_artifact_type(self, client):
        """Test that invalid artifact types are rejected."""
        response = client.post(
            "/api/v1/chat/conversations",
            json={
                "artifact_type": "invalid_type",
                "artifact_id": 1,
            },
        )

        assert response.status_code == 422  # Validation error


class TestConversationRetrieval:
    """Tests for GET /api/v1/chat/conversations/{id} endpoint."""

    def test_get_conversation_success(self, client, sample_summary):
        """Test retrieving an existing conversation."""
        # First create a conversation
        create_response = client.post(
            "/api/v1/chat/conversations",
            json={
                "artifact_type": "summary",
                "artifact_id": str(sample_summary.id),
            },
        )
        conversation_id = create_response.json()["id"]

        # Now retrieve it
        response = client.get(f"/api/v1/chat/conversations/{conversation_id}")

        assert response.status_code == 200
        data = response.json()

        assert data["id"] == conversation_id
        assert data["artifactType"] == "summary"  # camelCase
        assert data["artifactId"] == str(sample_summary.id)

    def test_get_conversation_not_found(self, client):
        """Test retrieving a non-existent conversation."""
        response = client.get("/api/v1/chat/conversations/nonexistent-id")

        assert response.status_code == 404


class TestSendMessage:
    """Tests for POST /api/v1/chat/conversations/{id}/messages endpoint."""

    def test_send_message_creates_user_message(self, client, sample_summary):
        """Test sending a message adds it to the conversation."""
        # Create conversation
        create_response = client.post(
            "/api/v1/chat/conversations",
            json={
                "artifact_type": "summary",
                "artifact_id": str(sample_summary.id),
            },
        )
        conversation_id = create_response.json()["id"]

        # Send a message (this is SSE endpoint, so we get streaming response)
        # For testing, we just verify it accepts the request
        with client.stream(
            "POST",
            f"/api/v1/chat/conversations/{conversation_id}/messages",
            json={"content": "What is the main topic?"},
        ) as response:
            assert response.status_code == 200
            # Just consume some of the stream
            for _ in response.iter_lines():
                break

    def test_send_message_with_model_selection(self, client, sample_summary):
        """Test sending a message with a specific model selected."""
        # Create conversation
        create_response = client.post(
            "/api/v1/chat/conversations",
            json={
                "artifact_type": "summary",
                "artifact_id": str(sample_summary.id),
            },
        )
        conversation_id = create_response.json()["id"]

        # Send message with model selection
        with client.stream(
            "POST",
            f"/api/v1/chat/conversations/{conversation_id}/messages",
            json={
                "content": "What is the main topic?",
                "model": "claude-haiku-4-5",
            },
        ) as response:
            assert response.status_code == 200

    def test_send_message_to_nonexistent_conversation(self, client):
        """Test sending a message to a non-existent conversation.

        SSE endpoints return 200 but include error type in the stream.
        """
        # Use valid UUID format that doesn't exist
        with client.stream(
            "POST",
            "/api/v1/chat/conversations/00000000-0000-0000-0000-000000000000/messages",
            json={"content": "Hello"},
        ) as response:
            assert response.status_code == 200  # SSE always returns 200
            # Check for error in stream
            content = response.read().decode()
            assert "error" in content.lower() or "not found" in content.lower()


class TestChatServiceIntegration:
    """Tests for ChatService integration with different providers."""

    @pytest.fixture
    def mock_anthropic_response(self):
        """Mock Anthropic streaming response."""

        async def mock_stream(*args, **kwargs):
            yield "Hello, ", None
            yield "I can help ", None
            yield "you with that.", None
            yield (
                "",
                {
                    "model": "claude-sonnet-4-5",
                    "provider": "anthropic",
                    "input_tokens": 100,
                    "output_tokens": 50,
                },
            )

        return mock_stream

    def test_chat_service_uses_correct_provider_for_claude(self, client, sample_summary):
        """Test that Claude models use Anthropic provider."""
        from src.config.models import Provider
        from src.services.chat_service import ChatService

        service = ChatService(None)  # We don't need model_config for this test

        provider = service._get_provider_for_model("claude-sonnet-4-5")
        assert provider == Provider.ANTHROPIC

    def test_chat_service_uses_correct_provider_for_gemini(self, client):
        """Test that Gemini models use Google provider."""
        from src.config.models import Provider
        from src.services.chat_service import ChatService

        service = ChatService(None)

        provider = service._get_provider_for_model("gemini-2.0-flash")
        assert provider == Provider.GOOGLE_AI

    def test_chat_service_uses_correct_provider_for_gpt(self, client):
        """Test that GPT models use OpenAI provider."""
        from src.config.models import Provider
        from src.services.chat_service import ChatService

        service = ChatService(None)

        provider = service._get_provider_for_model("gpt-5.2")
        assert provider == Provider.OPENAI

    def test_chat_service_unknown_model_raises_error(self, client):
        """Test that unknown models raise an error."""
        from src.services.chat_service import ChatService

        service = ChatService(None)

        with pytest.raises(ValueError, match="Unknown model"):
            service._get_provider_for_model("unknown-model-xyz")


class TestMessageHistory:
    """Tests for conversation message history."""

    def test_conversation_preserves_message_history(self, client, sample_summary):
        """Test that messages are preserved in conversation history."""
        # Create conversation
        create_response = client.post(
            "/api/v1/chat/conversations",
            json={
                "artifact_type": "summary",
                "artifact_id": str(sample_summary.id),
            },
        )
        conversation_id = create_response.json()["id"]

        # Send a message
        with client.stream(
            "POST",
            f"/api/v1/chat/conversations/{conversation_id}/messages",
            json={"content": "First question"},
        ) as response:
            # Consume stream
            for _ in response.iter_lines():
                pass

        # Retrieve conversation and check history
        get_response = client.get(f"/api/v1/chat/conversations/{conversation_id}")

        assert get_response.status_code == 200
        data = get_response.json()

        # Should have at least the user message
        assert len(data["messages"]) >= 1
        assert data["messages"][0]["role"] == "user"
        assert data["messages"][0]["content"] == "First question"


class TestChatErrors:
    """Tests for chat error handling."""

    def test_missing_content_rejected(self, client, sample_summary):
        """Test that missing content field is rejected."""
        # Create conversation
        create_response = client.post(
            "/api/v1/chat/conversations",
            json={
                "artifact_type": "summary",
                "artifact_id": str(sample_summary.id),
            },
        )
        conversation_id = create_response.json()["id"]

        # Try to send message without content field
        response = client.post(
            f"/api/v1/chat/conversations/{conversation_id}/messages",
            json={},  # Missing content field
        )

        assert response.status_code == 422  # Validation error

    def test_conversation_not_found_error_in_stream(self, client):
        """Test that non-existent conversation returns error in SSE stream.

        SSE endpoints return HTTP 200 but communicate errors within the stream.
        """
        # Use a valid UUID format that doesn't exist
        with client.stream(
            "POST",
            "/api/v1/chat/conversations/00000000-0000-0000-0000-000000000000/messages",
            json={"content": "Hello"},
        ) as response:
            assert response.status_code == 200  # SSE always returns 200
            # Check for error message in stream
            content = response.read().decode()
            assert "Conversation not found" in content
