"""Tests for the observability provider factory."""

from __future__ import annotations

from unittest.mock import patch

from src.telemetry.providers.factory import get_observability_provider
from src.telemetry.providers.noop import NoopProvider


class TestGetObservabilityProvider:
    """Tests for provider factory function."""

    @patch("src.telemetry.providers.factory.settings")
    def test_noop_is_default(self, mock_settings):
        """Factory should return NoopProvider when provider is noop."""
        mock_settings.observability_provider = "noop"

        provider = get_observability_provider()

        assert isinstance(provider, NoopProvider)
        assert provider.name == "noop"

    @patch("src.telemetry.providers.factory.settings")
    def test_opik_provider_created(self, mock_settings):
        """Factory should create OpikProvider for opik setting."""
        mock_settings.observability_provider = "opik"
        mock_settings.otel_exporter_otlp_endpoint = "http://localhost:4318"
        mock_settings.otel_exporter_otlp_headers = None
        mock_settings.opik_api_key = "test-key"
        mock_settings.opik_workspace = "test-ws"
        mock_settings.opik_project_name = "test-project"
        mock_settings.otel_service_name = "test-service"
        mock_settings.otel_log_prompts = False

        provider = get_observability_provider()

        from src.telemetry.providers.opik import OpikProvider

        assert isinstance(provider, OpikProvider)
        assert provider.name == "opik"

    @patch("src.telemetry.providers.factory.settings")
    def test_braintrust_provider_created(self, mock_settings):
        """Factory should create BraintrustProvider for braintrust setting."""
        mock_settings.observability_provider = "braintrust"
        mock_settings.braintrust_api_key = "test-bt-key"
        mock_settings.braintrust_project_name = "test-project"
        mock_settings.braintrust_api_url = "https://api.braintrust.dev"
        mock_settings.otel_log_prompts = False

        provider = get_observability_provider()

        from src.telemetry.providers.braintrust import BraintrustProvider

        assert isinstance(provider, BraintrustProvider)
        assert provider.name == "braintrust"

    @patch("src.telemetry.providers.factory.settings")
    def test_otel_provider_created(self, mock_settings):
        """Factory should create OTelProvider for otel setting."""
        mock_settings.observability_provider = "otel"
        mock_settings.otel_exporter_otlp_endpoint = "http://localhost:4318"
        mock_settings.otel_exporter_otlp_headers = None
        mock_settings.otel_service_name = "test-service"
        mock_settings.otel_log_prompts = False

        provider = get_observability_provider()

        from src.telemetry.providers.otel_provider import OTelProvider

        assert isinstance(provider, OTelProvider)
        assert provider.name == "otel"

    @patch("src.telemetry.providers.factory.settings")
    def test_unknown_provider_returns_noop(self, mock_settings):
        """Factory should return NoopProvider for unknown provider type."""
        mock_settings.observability_provider = "unknown"

        provider = get_observability_provider()

        assert isinstance(provider, NoopProvider)


class TestProviderProtocolCompliance:
    """Tests that all providers satisfy the ObservabilityProvider protocol."""

    def test_noop_is_observable_provider(self):
        """NoopProvider should satisfy the ObservabilityProvider protocol."""
        from src.telemetry.providers.base import ObservabilityProvider

        provider = NoopProvider()
        assert isinstance(provider, ObservabilityProvider)

    def test_opik_is_observable_provider(self):
        """OpikProvider should satisfy the ObservabilityProvider protocol."""
        from src.telemetry.providers.base import ObservabilityProvider
        from src.telemetry.providers.opik import OpikProvider

        provider = OpikProvider()
        assert isinstance(provider, ObservabilityProvider)

    def test_braintrust_is_observable_provider(self):
        """BraintrustProvider should satisfy the ObservabilityProvider protocol."""
        from src.telemetry.providers.base import ObservabilityProvider
        from src.telemetry.providers.braintrust import BraintrustProvider

        provider = BraintrustProvider()
        assert isinstance(provider, ObservabilityProvider)

    def test_otel_is_observable_provider(self):
        """OTelProvider should satisfy the ObservabilityProvider protocol."""
        from src.telemetry.providers.base import ObservabilityProvider
        from src.telemetry.providers.otel_provider import OTelProvider

        provider = OTelProvider()
        assert isinstance(provider, ObservabilityProvider)


class TestNoopProviderBehavior:
    """Tests for NoopProvider behavior (zero overhead)."""

    def test_noop_setup_does_nothing(self):
        """NoopProvider.setup() should complete without error."""
        provider = NoopProvider()
        provider.setup(app=None)

    def test_noop_trace_llm_call_does_nothing(self):
        """NoopProvider.trace_llm_call() should complete without error."""
        provider = NoopProvider()
        provider.trace_llm_call(
            model="test-model",
            provider="test-provider",
            system_prompt="test system prompt",
            user_prompt="test user prompt",
            response_text="test response",
            input_tokens=100,
            output_tokens=50,
            duration_ms=500.0,
        )

    def test_noop_start_span_yields_none(self):
        """NoopProvider.start_span() should yield None."""
        provider = NoopProvider()
        with provider.start_span("test-span") as span:
            assert span is None

    def test_noop_start_span_with_attributes(self):
        """NoopProvider.start_span() should accept attributes without error."""
        provider = NoopProvider()
        with provider.start_span("test-span", attributes={"key": "value"}):
            pass

    def test_noop_flush_does_nothing(self):
        """NoopProvider.flush() should complete without error."""
        provider = NoopProvider()
        provider.flush()

    def test_noop_shutdown_does_nothing(self):
        """NoopProvider.shutdown() should complete without error."""
        provider = NoopProvider()
        provider.shutdown()


class TestTelemetryModule:
    """Tests for the top-level telemetry module functions."""

    def test_get_provider_returns_singleton(self):
        """get_provider() should return the same instance each time."""
        from src.telemetry import get_provider, reset_telemetry

        reset_telemetry()

        with patch("src.telemetry.get_observability_provider") as mock_factory:
            mock_factory.return_value = NoopProvider()

            provider1 = get_provider()
            provider2 = get_provider()

            assert provider1 is provider2
            mock_factory.assert_called_once()

        reset_telemetry()

    def test_setup_telemetry_initializes_provider(self):
        """setup_telemetry() should initialize the provider."""
        from src.telemetry import reset_telemetry, setup_telemetry

        reset_telemetry()

        with patch("src.telemetry.get_observability_provider") as mock_factory:
            mock_provider = NoopProvider()
            mock_factory.return_value = mock_provider

            setup_telemetry(app=None)

        reset_telemetry()

    def test_shutdown_telemetry_clears_provider(self):
        """shutdown_telemetry() should clear the provider singleton."""
        from src.telemetry import get_provider, reset_telemetry, shutdown_telemetry

        reset_telemetry()

        with patch("src.telemetry.get_observability_provider") as mock_factory:
            mock_factory.return_value = NoopProvider()

            # Initialize provider
            provider = get_provider()
            assert provider is not None

            # Shutdown should clear it
            shutdown_telemetry()

        reset_telemetry()

    def test_reset_telemetry_clears_state(self):
        """reset_telemetry() should clear the provider singleton for testing."""
        from src.telemetry import get_provider, reset_telemetry

        with patch("src.telemetry.get_observability_provider") as mock_factory:
            mock_factory.return_value = NoopProvider()

            get_provider()  # Initialize

        reset_telemetry()

        # After reset, module-level _provider should be None
        import src.telemetry

        assert src.telemetry._provider is None
