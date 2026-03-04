"""Integration tests for Langfuse observability provider.

Tests the full round-trip of sending traces via the LangfuseProvider
and verifying they appear in the Langfuse backend.

Requires:
- Langfuse stack running (make langfuse-up)
- API keys configured (from Langfuse Settings → API Keys)

Run with:
    pytest tests/integration/test_langfuse_integration.py -v

Or with the make target:
    make test-langfuse
"""

from __future__ import annotations

from tests.integration.fixtures.langfuse import (
    langfuse_available,
    langfuse_provider,
    langfuse_test_helpers,
    requires_langfuse,
    unique_langfuse_project_name,
)

# Re-export fixtures for pytest discovery
__all__ = [
    "langfuse_available",
    "langfuse_provider",
    "langfuse_test_helpers",
    "requires_langfuse",
    "unique_langfuse_project_name",
]


@requires_langfuse
class TestLangfuseProviderIntegration:
    """Integration tests for LangfuseProvider with real Langfuse backend."""

    def test_trace_llm_call_round_trip(self, langfuse_provider, langfuse_test_helpers):
        """Verify trace_llm_call sends traces that appear in Langfuse."""
        langfuse_provider.setup()
        langfuse_provider.trace_llm_call(
            model="claude-sonnet-4-5-20250514",
            provider="anthropic",
            system_prompt="You are a helpful assistant.",
            user_prompt="What is the capital of France?",
            response_text="The capital of France is Paris.",
            input_tokens=25,
            output_tokens=10,
            duration_ms=150.0,
            max_tokens=1024,
            metadata={"test": "integration", "step": "verification"},
        )
        langfuse_provider.flush()
        traces = langfuse_test_helpers.wait_for_traces(expected_count=1, timeout=15.0)
        assert len(traces) >= 1, "Expected at least one trace in Langfuse"

    def test_multiple_traces_are_captured(self, langfuse_provider, langfuse_test_helpers):
        """Verify multiple sequential traces are all captured."""
        langfuse_provider.setup()
        models = ["claude-haiku-4-5-20250514", "claude-sonnet-4-5-20250514", "gpt-4o"]
        for i, model in enumerate(models):
            langfuse_provider.trace_llm_call(
                model=model,
                provider="anthropic" if "claude" in model else "openai",
                system_prompt=f"System prompt {i}",
                user_prompt=f"User prompt {i}",
                response_text=f"Response {i}",
                input_tokens=10 + i,
                output_tokens=5 + i,
                duration_ms=100.0 + i * 10,
            )
        langfuse_provider.flush()
        traces = langfuse_test_helpers.wait_for_traces(expected_count=3, timeout=20.0)
        assert len(traces) >= 3, f"Expected 3 traces, got {len(traces)}"

    def test_start_span_creates_trace(self, langfuse_provider, langfuse_test_helpers):
        """Verify start_span context manager creates traces."""
        langfuse_provider.setup()
        with langfuse_provider.start_span(
            "test.custom_operation",
            attributes={"operation.type": "test", "operation.name": "custom_span_test"},
        ):
            pass
        langfuse_provider.flush()
        traces = langfuse_test_helpers.wait_for_traces(expected_count=1, timeout=15.0)
        assert len(traces) >= 1

    def test_provider_setup_is_idempotent(self, langfuse_provider, langfuse_test_helpers):
        """Verify calling setup() multiple times doesn't cause issues."""
        langfuse_provider.setup()
        langfuse_provider.setup()
        langfuse_provider.setup()
        langfuse_provider.trace_llm_call(
            model="claude-sonnet-4-5-20250514",
            provider="anthropic",
            system_prompt="Test",
            user_prompt="Test",
            response_text="Test",
            input_tokens=5,
            output_tokens=5,
            duration_ms=50.0,
        )
        langfuse_provider.flush()
        traces = langfuse_test_helpers.wait_for_traces(expected_count=1, timeout=15.0)
        assert len(traces) >= 1


@requires_langfuse
class TestLangfuseProviderConfiguration:
    """Tests for LangfuseProvider configuration and error handling."""

    def test_provider_works_without_auth(self):
        """Verify provider initializes without auth keys (self-hosted)."""
        from src.telemetry.providers.langfuse import LangfuseProvider
        from tests.integration.fixtures.langfuse import (
            LANGFUSE_BASE_URL,
            _reset_otel_tracer_provider,
        )

        _reset_otel_tracer_provider()
        provider = LangfuseProvider(base_url=LANGFUSE_BASE_URL)
        provider.setup()
        assert provider._setup_complete is True
        provider.shutdown()

    def test_provider_with_explicit_config(self):
        """Verify provider works with explicit configuration."""
        from src.telemetry.providers.langfuse import LangfuseProvider
        from tests.integration.fixtures.langfuse import (
            LANGFUSE_BASE_URL,
            _reset_otel_tracer_provider,
            _settings,
        )

        _reset_otel_tracer_provider()
        provider = LangfuseProvider(
            public_key=_settings.langfuse_public_key,
            secret_key=_settings.langfuse_secret_key,
            base_url=LANGFUSE_BASE_URL,
        )
        provider.setup()
        assert provider._setup_complete is True
        provider.shutdown()

    def test_provider_name_property(self):
        """Verify provider name is 'langfuse'."""
        from src.telemetry.providers.langfuse import LangfuseProvider

        provider = LangfuseProvider()
        assert provider.name == "langfuse"


@requires_langfuse
class TestLangfuseFactoryIntegration:
    """Tests for observability provider factory with Langfuse."""

    def test_factory_creates_langfuse_provider_with_profile(self, monkeypatch):
        """Verify factory creates LangfuseProvider when configured via settings."""
        from src.config.settings import Settings
        from src.telemetry.providers.factory import get_observability_provider
        from tests.integration.fixtures.langfuse import LANGFUSE_BASE_URL

        settings = Settings(
            _env_file=None,
            anthropic_api_key="test-key",
            observability_provider="langfuse",
            langfuse_base_url=LANGFUSE_BASE_URL,
            otel_enabled=True,
        )
        monkeypatch.setattr("src.telemetry.providers.factory.settings", settings)
        provider = get_observability_provider()
        assert provider.name == "langfuse"
