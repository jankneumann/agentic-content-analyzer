"""Tests for LLM Router telemetry integration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.services.llm_router import LLMResponse, LLMRouter


class TestLLMRouterTelemetry:
    """Tests for telemetry instrumentation in LLMRouter."""

    def test_trace_llm_call_invokes_provider(self):
        """_trace_llm_call should invoke the telemetry provider."""
        from src.config.models import ModelConfig

        router = LLMRouter(ModelConfig())

        mock_provider = MagicMock()

        response = LLMResponse(
            text="test response",
            input_tokens=100,
            output_tokens=50,
        )

        with patch("src.telemetry.get_provider", return_value=mock_provider):
            router._trace_llm_call(
                model="test-model",
                provider="anthropic",
                system_prompt="test system",
                user_prompt="test user",
                response=response,
                duration_ms=500.0,
                max_tokens=4096,
            )

        mock_provider.trace_llm_call.assert_called_once_with(
            model="test-model",
            provider="anthropic",
            system_prompt="test system",
            user_prompt="test user",
            response_text="test response",
            input_tokens=100,
            output_tokens=50,
            duration_ms=500.0,
            max_tokens=4096,
            metadata=None,
        )

    def test_trace_llm_call_with_metadata(self):
        """_trace_llm_call should pass metadata to provider."""
        from src.config.models import ModelConfig

        router = LLMRouter(ModelConfig())

        mock_provider = MagicMock()

        response = LLMResponse(
            text="test response",
            input_tokens=200,
            output_tokens=100,
        )

        with patch("src.telemetry.get_provider", return_value=mock_provider):
            router._trace_llm_call(
                model="test-model",
                provider="openai",
                system_prompt="sys",
                user_prompt="usr",
                response=response,
                duration_ms=1000.0,
                metadata={"tool_count": 3, "max_iterations": 20},
            )

        call_kwargs = mock_provider.trace_llm_call.call_args[1]
        assert call_kwargs["metadata"] == {"tool_count": 3, "max_iterations": 20}

    def test_trace_llm_call_handles_errors_gracefully(self):
        """_trace_llm_call should never raise exceptions."""
        from src.config.models import ModelConfig

        router = LLMRouter(ModelConfig())

        response = LLMResponse(
            text="test response",
            input_tokens=100,
            output_tokens=50,
        )

        with patch(
            "src.telemetry.get_provider",
            side_effect=RuntimeError("telemetry broken"),
        ):
            # Should not raise — telemetry failures are silently logged
            router._trace_llm_call(
                model="test-model",
                provider="anthropic",
                system_prompt="sys",
                user_prompt="usr",
                response=response,
                duration_ms=500.0,
            )

    def test_trace_llm_call_handles_provider_error(self):
        """_trace_llm_call should catch errors from the provider itself."""
        from src.config.models import ModelConfig

        router = LLMRouter(ModelConfig())

        mock_provider = MagicMock()
        mock_provider.trace_llm_call.side_effect = Exception("Braintrust down")

        response = LLMResponse(
            text="test response",
            input_tokens=100,
            output_tokens=50,
        )

        with patch("src.telemetry.get_provider", return_value=mock_provider):
            # Should not raise
            router._trace_llm_call(
                model="test-model",
                provider="braintrust",
                system_prompt="sys",
                user_prompt="usr",
                response=response,
                duration_ms=500.0,
            )


class TestNoopProviderIntegration:
    """Tests that noop provider adds zero overhead to LLM calls."""

    def test_noop_trace_is_zero_overhead(self):
        """Noop provider trace should complete instantly with no side effects."""
        from src.config.models import ModelConfig
        from src.telemetry.providers.noop import NoopProvider

        router = LLMRouter(ModelConfig())

        response = LLMResponse(
            text="test response",
            input_tokens=100,
            output_tokens=50,
        )

        with patch("src.telemetry.get_provider", return_value=NoopProvider()):
            # Should complete without any network calls or side effects
            router._trace_llm_call(
                model="test-model",
                provider="anthropic",
                system_prompt="sys",
                user_prompt="usr",
                response=response,
                duration_ms=500.0,
            )
