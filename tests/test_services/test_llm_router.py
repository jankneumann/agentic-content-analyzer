"""Tests for LLMRouter generate_sync() method.

Verifies provider routing, SDK client selection, and LLMResponse construction
for synchronous generation across all three provider families.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.config.models import ModelConfig, Provider
from src.services.llm_router import LLMResponse, LLMRouter


@pytest.fixture
def router():
    """Create an LLMRouter with default config."""
    config = ModelConfig()
    return LLMRouter(config)


class TestGenerateSyncAnthropicProvider:
    """Tests for generate_sync() with Anthropic-family providers."""

    def test_routes_to_anthropic_for_claude_model(self, router):
        """Should route Claude models to _generate_anthropic_sync."""
        mock_response = LLMResponse(
            text="Summary text",
            input_tokens=100,
            output_tokens=50,
            provider=Provider.ANTHROPIC,
            model_version="claude-haiku-4-5-20250414",
        )

        with patch.object(
            router, "_generate_anthropic_sync", return_value=mock_response
        ) as mock_gen:
            result = router.generate_sync(
                model="claude-haiku-4-5",
                system_prompt="Summarize this.",
                user_prompt="Some content to summarize.",
            )

            mock_gen.assert_called_once()
            assert result.text == "Summary text"
            assert result.provider == Provider.ANTHROPIC
            assert result.input_tokens == 100
            assert result.output_tokens == 50

    def test_anthropic_sync_creates_client_and_calls_api(self, router):
        """Should create Anthropic client and call messages.create()."""
        mock_message_response = MagicMock()
        mock_message_response.content = [MagicMock(text="Generated text")]
        mock_message_response.usage.input_tokens = 200
        mock_message_response.usage.output_tokens = 100

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message_response

        with patch.object(router, "_get_anthropic_client", return_value=mock_client):
            result = router._generate_anthropic_sync(
                model="claude-haiku-4-5",
                provider=Provider.ANTHROPIC,
                system_prompt="System",
                user_prompt="User",
                max_tokens=4096,
                temperature=0.0,
            )

            mock_client.messages.create.assert_called_once()
            call_kwargs = mock_client.messages.create.call_args
            assert call_kwargs.kwargs["system"] == "System"
            assert call_kwargs.kwargs["max_tokens"] == 4096
            assert call_kwargs.kwargs["temperature"] == 0.0
            assert result.text == "Generated text"
            assert result.input_tokens == 200
            assert result.output_tokens == 100


class TestGenerateSyncGeminiProvider:
    """Tests for generate_sync() with Google AI provider."""

    def test_routes_to_gemini_for_gemini_model(self, router):
        """Should route Gemini models to _generate_gemini_sync."""
        mock_response = LLMResponse(
            text="Gemini summary",
            input_tokens=150,
            output_tokens=75,
            provider=Provider.GOOGLE_AI,
        )

        with patch.object(router, "_generate_gemini_sync", return_value=mock_response) as mock_gen:
            result = router.generate_sync(
                model="gemini-2.5-flash-lite",
                system_prompt="Summarize.",
                user_prompt="Content here.",
            )

            mock_gen.assert_called_once()
            assert result.text == "Gemini summary"
            assert result.provider == Provider.GOOGLE_AI

    def test_gemini_sync_creates_client_and_calls_api(self, router):
        """Should create Gemini client and call generate_content()."""
        mock_response = MagicMock()
        mock_part = MagicMock()
        mock_part.text = "Gemini output"
        mock_response.candidates = [MagicMock()]
        mock_response.candidates[0].content.parts = [mock_part]
        mock_response.usage_metadata = MagicMock(
            prompt_token_count=300,
            candidates_token_count=150,
        )

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        mock_genai_module = MagicMock()
        mock_genai_module.Client.return_value = mock_client

        import sys

        with patch("src.services.llm_router.os.environ.get", return_value="fake-api-key"):
            with patch.dict(
                sys.modules, {"google.genai": mock_genai_module, "google.genai.types": MagicMock()}
            ):
                result = router._generate_gemini_sync(
                    model="gemini-2.5-flash-lite",
                    provider=Provider.GOOGLE_AI,
                    system_prompt="System",
                    user_prompt="User",
                    max_tokens=4096,
                    temperature=0.0,
                )

                mock_client.models.generate_content.assert_called_once()
                assert result.text == "Gemini output"
                assert result.input_tokens == 300
                assert result.output_tokens == 150


class TestGenerateSyncOpenAIProvider:
    """Tests for generate_sync() with OpenAI provider."""

    def test_routes_to_openai_for_gpt_model(self, router):
        """Should route GPT models to _generate_openai_sync."""
        mock_response = LLMResponse(
            text="GPT summary",
            input_tokens=120,
            output_tokens=60,
            provider=Provider.OPENAI,
        )

        with patch.object(router, "_generate_openai_sync", return_value=mock_response) as mock_gen:
            result = router.generate_sync(
                model="gpt-5-mini",
                system_prompt="Summarize.",
                user_prompt="Content here.",
            )

            mock_gen.assert_called_once()
            assert result.text == "GPT summary"
            assert result.provider == Provider.OPENAI

    def test_openai_sync_creates_sync_client(self, router):
        """Should use sync OpenAI client (not AsyncOpenAI)."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "OpenAI output"
        mock_response.usage = MagicMock(prompt_tokens=250, completion_tokens=125)

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch.object(router, "_get_openai_sync_client", return_value=mock_client):
            result = router._generate_openai_sync(
                model="gpt-5-mini",
                provider=Provider.OPENAI,
                system_prompt="System",
                user_prompt="User",
                max_tokens=4096,
                temperature=0.7,
            )

            mock_client.chat.completions.create.assert_called_once()
            assert result.text == "OpenAI output"
            assert result.input_tokens == 250
            assert result.output_tokens == 125

    def test_get_openai_sync_client_creates_sync_openai(self, router):
        """Should create sync OpenAI (not AsyncOpenAI)."""
        with patch("src.services.llm_router.os.environ.get", return_value="fake-key"):
            with patch("openai.OpenAI") as mock_openai_cls:
                router._get_openai_sync_client(Provider.OPENAI)
                mock_openai_cls.assert_called_once_with(api_key="fake-key")

    def test_get_openai_sync_client_creates_azure_openai(self, router):
        """Should create sync AzureOpenAI for Azure provider."""

        def mock_getenv(key, default=None):
            env = {
                "AZURE_OPENAI_API_KEY": "azure-key",
                "AZURE_OPENAI_ENDPOINT": "https://myendpoint.openai.azure.com",
                "AZURE_OPENAI_API_VERSION": "2024-02-15-preview",
            }
            return env.get(key, default)

        with patch("src.services.llm_router.os.environ.get", side_effect=mock_getenv):
            with patch("openai.AzureOpenAI") as mock_azure_cls:
                router._get_openai_sync_client(Provider.MICROSOFT_AZURE)
                mock_azure_cls.assert_called_once()


class TestGenerateSyncTelemetry:
    """Tests for telemetry integration in generate_sync()."""

    def test_traces_llm_call_on_success(self, router):
        """Should call _trace_llm_call after successful generation."""
        mock_response = LLMResponse(
            text="Result",
            input_tokens=50,
            output_tokens=25,
            provider=Provider.ANTHROPIC,
        )

        with (
            patch.object(router, "_generate_anthropic_sync", return_value=mock_response),
            patch.object(router, "_trace_llm_call") as mock_trace,
        ):
            router.generate_sync(
                model="claude-haiku-4-5",
                system_prompt="Test",
                user_prompt="Test",
            )

            mock_trace.assert_called_once()
            trace_kwargs = mock_trace.call_args.kwargs
            assert trace_kwargs["model"] == "claude-haiku-4-5"
            assert trace_kwargs["provider"] == "anthropic"

    def test_explicit_provider_override(self, router):
        """Should pass explicit provider through to sync helper."""
        mock_response = LLMResponse(
            text="Bedrock result",
            input_tokens=50,
            output_tokens=25,
            provider=Provider.AWS_BEDROCK,
        )

        with patch.object(
            router, "_generate_anthropic_sync", return_value=mock_response
        ) as mock_gen:
            router.generate_sync(
                model="claude-sonnet-4-5",
                system_prompt="Test",
                user_prompt="Test",
                provider=Provider.AWS_BEDROCK,
            )

            call_args = mock_gen.call_args
            assert call_args[0][1] == Provider.AWS_BEDROCK  # provider arg


class TestGenerateSyncErrorHandling:
    """Tests for error handling in generate_sync()."""

    def test_unsupported_provider_raises_value_error(self, router):
        """Should raise ValueError for unsupported provider."""
        # Create a mock provider enum value that doesn't match any known branch
        mock_provider = MagicMock()
        mock_provider.value = "unsupported_provider"

        with patch.object(router, "resolve_provider", return_value=mock_provider):
            with pytest.raises(ValueError, match="Unsupported provider"):
                router.generate_sync(
                    model="claude-haiku-4-5",
                    system_prompt="Test",
                    user_prompt="Test",
                )

    def test_missing_api_key_raises_runtime_error(self, router):
        """Should propagate RuntimeError when API key is missing."""
        with patch("src.services.llm_router.os.environ.get", return_value=None):
            with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
                router._generate_anthropic_sync(
                    model="claude-haiku-4-5",
                    provider=Provider.ANTHROPIC,
                    system_prompt="Test",
                    user_prompt="Test",
                    max_tokens=4096,
                    temperature=0.0,
                )
