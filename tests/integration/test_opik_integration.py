"""Integration tests for Opik observability provider.

Tests the full round-trip of sending traces via the OpikProvider
and verifying they appear in the Opik backend.

Requires:
- Opik stack running (make opik-up)
- Network connectivity to localhost:5174 (Opik UI) and localhost:8080 (Opik API)

Run with:
    pytest tests/integration/test_opik_integration.py -v

Or with the make target:
    make test-opik
"""

from __future__ import annotations

from tests.integration.fixtures.opik import (
    OPIK_OTLP_ENDPOINT,
    opik_available,
    opik_provider,
    opik_test_helpers,
    requires_opik,
    unique_project_name,
)

# Re-export fixtures for pytest discovery
__all__ = [
    "opik_available",
    "opik_provider",
    "opik_test_helpers",
    "requires_opik",
    "unique_project_name",
]


@requires_opik
class TestOpikProviderIntegration:
    """Integration tests for OpikProvider with real Opik backend."""

    def test_trace_llm_call_round_trip(self, opik_provider, opik_test_helpers):
        """Verify trace_llm_call sends traces that appear in Opik.

        This is the core integration test: send a trace and verify
        it can be retrieved from the Opik API.
        """
        # 1. Setup provider
        opik_provider.setup()

        # 2. Send a test LLM call trace
        opik_provider.trace_llm_call(
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

        # 3. Flush to ensure trace is exported
        opik_provider.flush()

        # 4. Wait for trace to appear in Opik
        traces = opik_test_helpers.wait_for_traces(expected_count=1, timeout=10.0)

        # 5. Verify trace was received
        assert len(traces) >= 1, "Expected at least one trace in Opik"

        # Find our trace (should have llm.completion span)
        trace = traces[0]
        assert trace is not None

    def test_multiple_traces_are_captured(self, opik_provider, opik_test_helpers):
        """Verify multiple sequential traces are all captured."""
        opik_provider.setup()

        # Send 3 different traces
        models = ["claude-haiku-4-5-20250514", "claude-sonnet-4-5-20250514", "gpt-4o"]
        for i, model in enumerate(models):
            opik_provider.trace_llm_call(
                model=model,
                provider="anthropic" if "claude" in model else "openai",
                system_prompt=f"System prompt {i}",
                user_prompt=f"User prompt {i}",
                response_text=f"Response {i}",
                input_tokens=10 + i,
                output_tokens=5 + i,
                duration_ms=100.0 + i * 10,
            )

        opik_provider.flush()

        # Wait for all 3 traces
        traces = opik_test_helpers.wait_for_traces(expected_count=3, timeout=15.0)
        assert len(traces) >= 3, f"Expected 3 traces, got {len(traces)}"

    def test_start_span_creates_trace(self, opik_provider, opik_test_helpers):
        """Verify start_span context manager creates traces."""
        opik_provider.setup()

        # Create a custom span
        with opik_provider.start_span(
            "test.custom_operation",
            attributes={
                "operation.type": "test",
                "operation.name": "custom_span_test",
            },
        ):
            # Simulate some work
            pass

        opik_provider.flush()

        # Verify trace appears
        traces = opik_test_helpers.wait_for_traces(expected_count=1, timeout=10.0)
        assert len(traces) >= 1

    def test_provider_setup_is_idempotent(self, opik_provider, opik_test_helpers):
        """Verify calling setup() multiple times doesn't cause issues."""
        # Call setup multiple times
        opik_provider.setup()
        opik_provider.setup()
        opik_provider.setup()

        # Should still work normally
        opik_provider.trace_llm_call(
            model="claude-sonnet-4-5-20250514",
            provider="anthropic",
            system_prompt="Test",
            user_prompt="Test",
            response_text="Test",
            input_tokens=5,
            output_tokens=5,
            duration_ms=50.0,
        )

        opik_provider.flush()
        traces = opik_test_helpers.wait_for_traces(expected_count=1, timeout=10.0)
        assert len(traces) >= 1


@requires_opik
class TestOpikProviderConfiguration:
    """Tests for OpikProvider configuration and error handling."""

    def test_provider_requires_endpoint_for_self_hosted(self):
        """Verify self-hosted Opik requires explicit endpoint configuration."""
        from src.telemetry.providers.opik import OpikProvider

        # Create provider without endpoint or API key
        provider = OpikProvider(
            endpoint=None,
            api_key=None,
            project_name="test-no-endpoint",
        )

        # Setup should fail gracefully (log error, not raise)
        provider.setup()

        # Provider should not be set up
        assert not provider._setup_complete

    def test_provider_with_explicit_endpoint_works(self, unique_project_name):
        """Verify provider works when endpoint is explicitly configured."""
        from src.telemetry.providers.opik import OpikProvider

        provider = OpikProvider(
            endpoint=OPIK_OTLP_ENDPOINT,
            project_name=unique_project_name,
        )

        provider.setup()
        assert provider._setup_complete

        # Cleanup
        provider.shutdown()

    def test_provider_name_property(self):
        """Verify provider name is 'opik'."""
        from src.telemetry.providers.opik import OpikProvider

        provider = OpikProvider()
        assert provider.name == "opik"


@requires_opik
class TestOpikFactoryIntegration:
    """Tests for observability provider factory with Opik."""

    def test_factory_creates_opik_provider_with_profile(self, monkeypatch):
        """Verify factory creates OpikProvider when configured via profile settings."""
        from src.config.settings import Settings
        from src.telemetry.providers.factory import get_observability_provider

        # Create settings with Opik configuration
        settings = Settings(
            _env_file=None,
            anthropic_api_key="test-key",
            observability_provider="opik",
            otel_exporter_otlp_endpoint=OPIK_OTLP_ENDPOINT,
            otel_enabled=True,
        )

        # Patch the global settings
        monkeypatch.setattr("src.telemetry.providers.factory.settings", settings)

        provider = get_observability_provider()
        assert provider.name == "opik"

    def test_factory_creates_noop_by_default(self, monkeypatch):
        """Verify factory creates NoopProvider when observability is disabled."""
        from src.config.settings import Settings
        from src.telemetry.providers.factory import get_observability_provider

        settings = Settings(
            _env_file=None,
            anthropic_api_key="test-key",
            observability_provider="noop",
        )

        monkeypatch.setattr("src.telemetry.providers.factory.settings", settings)

        provider = get_observability_provider()
        assert provider.name == "noop"
