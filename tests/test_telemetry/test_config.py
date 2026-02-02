"""Tests for observability configuration in settings."""

from __future__ import annotations

import pytest

from src.config.settings import Settings


class TestObservabilityProviderDefaults:
    """Tests for default observability settings."""

    def test_default_provider_is_noop(self):
        """Default observability provider should be noop."""
        s = Settings(
            _env_file=None, database_url="postgresql://localhost/test", anthropic_api_key="test-key"
        )
        assert s.observability_provider == "noop"

    def test_default_otel_disabled(self):
        """OTel auto-instrumentation should be disabled by default."""
        s = Settings(
            _env_file=None, database_url="postgresql://localhost/test", anthropic_api_key="test-key"
        )
        assert s.otel_enabled is False

    def test_default_service_name(self):
        """Default OTel service name should be newsletter-aggregator."""
        s = Settings(
            _env_file=None, database_url="postgresql://localhost/test", anthropic_api_key="test-key"
        )
        assert s.otel_service_name == "newsletter-aggregator"

    def test_default_log_prompts_disabled(self):
        """Prompt logging should be disabled by default (PII risk)."""
        s = Settings(
            _env_file=None, database_url="postgresql://localhost/test", anthropic_api_key="test-key"
        )
        assert s.otel_log_prompts is False

    def test_default_sampler_config(self):
        """Default sampler should be parentbased_traceidratio at 100%."""
        s = Settings(
            _env_file=None, database_url="postgresql://localhost/test", anthropic_api_key="test-key"
        )
        assert s.otel_traces_sampler == "parentbased_traceidratio"
        assert s.otel_traces_sampler_arg == 1.0

    def test_default_opik_project_name(self):
        """Default Opik project name should be newsletter-aggregator."""
        s = Settings(
            _env_file=None, database_url="postgresql://localhost/test", anthropic_api_key="test-key"
        )
        assert s.opik_project_name == "newsletter-aggregator"

    def test_default_braintrust_config(self):
        """Default Braintrust config should have project name and API URL."""
        s = Settings(
            _env_file=None, database_url="postgresql://localhost/test", anthropic_api_key="test-key"
        )
        assert s.braintrust_project_name == "newsletter-aggregator"
        assert s.braintrust_api_url == "https://api.braintrust.dev"

    def test_default_health_check_timeout(self):
        """Default health check timeout should be 5 seconds."""
        s = Settings(
            _env_file=None, database_url="postgresql://localhost/test", anthropic_api_key="test-key"
        )
        assert s.health_check_timeout_seconds == 5


class TestObservabilityProviderValidation:
    """Tests for observability provider configuration validation."""

    def test_noop_provider_no_validation_needed(self):
        """Noop provider should work without any additional config."""
        s = Settings(
            _env_file=None,
            database_url="postgresql://localhost/test",
            anthropic_api_key="test-key",
            observability_provider="noop",
        )
        assert s.observability_provider == "noop"

    def test_opik_provider_works_without_api_key(self):
        """Opik provider should work without API key (self-hosted mode)."""
        s = Settings(
            _env_file=None,
            database_url="postgresql://localhost/test",
            anthropic_api_key="test-key",
            observability_provider="opik",
        )
        assert s.observability_provider == "opik"

    def test_opik_provider_with_api_key(self):
        """Opik provider should accept API key for Comet Cloud."""
        s = Settings(
            _env_file=None,
            database_url="postgresql://localhost/test",
            anthropic_api_key="test-key",
            observability_provider="opik",
            opik_api_key="test-key",
            opik_workspace="test-workspace",
        )
        assert s.opik_api_key == "test-key"
        assert s.opik_workspace == "test-workspace"

    def test_braintrust_provider_requires_api_key(self):
        """Braintrust provider should require API key."""
        with pytest.raises(ValueError, match="BRAINTRUST_API_KEY"):
            Settings(
                _env_file=None,
                database_url="postgresql://localhost/test",
                anthropic_api_key="test-key",
                observability_provider="braintrust",
            )

    def test_braintrust_provider_with_api_key(self):
        """Braintrust provider should work with API key."""
        s = Settings(
            _env_file=None,
            database_url="postgresql://localhost/test",
            anthropic_api_key="test-key",
            observability_provider="braintrust",
            braintrust_api_key="test-braintrust-key",
        )
        assert s.observability_provider == "braintrust"
        assert s.braintrust_api_key == "test-braintrust-key"

    def test_otel_provider_requires_endpoint(self):
        """Generic OTel provider should require OTLP endpoint."""
        with pytest.raises(ValueError, match="OTEL_EXPORTER_OTLP_ENDPOINT"):
            Settings(
                _env_file=None,
                database_url="postgresql://localhost/test",
                anthropic_api_key="test-key",
                observability_provider="otel",
            )

    def test_otel_provider_with_endpoint(self):
        """Generic OTel provider should work with endpoint."""
        s = Settings(
            _env_file=None,
            database_url="postgresql://localhost/test",
            anthropic_api_key="test-key",
            observability_provider="otel",
            otel_exporter_otlp_endpoint="http://localhost:4318",
        )
        assert s.observability_provider == "otel"
        assert s.otel_exporter_otlp_endpoint == "http://localhost:4318"


class TestObservabilityProviderType:
    """Tests for the observability provider type literal."""

    def test_valid_provider_types(self):
        """All valid provider types should be accepted."""
        for provider_type in ["noop", "opik"]:
            s = Settings(
                _env_file=None,
                database_url="postgresql://localhost/test",
                anthropic_api_key="test-key",
                observability_provider=provider_type,
            )
            assert s.observability_provider == provider_type

    def test_braintrust_with_key(self):
        """Braintrust provider type with required key should work."""
        s = Settings(
            _env_file=None,
            database_url="postgresql://localhost/test",
            anthropic_api_key="test-key",
            observability_provider="braintrust",
            braintrust_api_key="test-key",
        )
        assert s.observability_provider == "braintrust"

    def test_otel_with_endpoint(self):
        """OTel provider type with required endpoint should work."""
        s = Settings(
            _env_file=None,
            database_url="postgresql://localhost/test",
            anthropic_api_key="test-key",
            observability_provider="otel",
            otel_exporter_otlp_endpoint="http://localhost:4318",
        )
        assert s.observability_provider == "otel"


class TestOtelLogBridgeSettings:
    """Tests for OTel log bridge settings and validation."""

    def test_default_logs_enabled(self):
        """OTel log bridge should be enabled by default."""
        s = Settings(
            _env_file=None, database_url="postgresql://localhost/test", anthropic_api_key="test-key"
        )
        assert s.otel_logs_enabled is True

    def test_default_export_level(self):
        """Default export level should be WARNING (uppercase)."""
        s = Settings(
            _env_file=None, database_url="postgresql://localhost/test", anthropic_api_key="test-key"
        )
        assert s.otel_logs_export_level == "WARNING"

    def test_default_log_format(self):
        """Default log format should be json."""
        s = Settings(
            _env_file=None, database_url="postgresql://localhost/test", anthropic_api_key="test-key"
        )
        assert s.log_format == "json"

    def test_export_level_normalized_to_uppercase(self):
        """Export level should be normalized to uppercase."""
        s = Settings(
            _env_file=None,
            database_url="postgresql://localhost/test",
            anthropic_api_key="test-key",
            otel_logs_export_level="error",
        )
        assert s.otel_logs_export_level == "ERROR"

    def test_valid_export_levels_accepted(self):
        """All standard Python logging levels should be accepted."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            s = Settings(
                _env_file=None,
                database_url="postgresql://localhost/test",
                anthropic_api_key="test-key",
                otel_logs_export_level=level,
            )
            assert s.otel_logs_export_level == level

    def test_invalid_export_level_rejected(self):
        """Invalid export level should raise ValueError."""
        with pytest.raises(ValueError, match="OTEL_LOGS_EXPORT_LEVEL"):
            Settings(
                _env_file=None,
                database_url="postgresql://localhost/test",
                anthropic_api_key="test-key",
                otel_logs_export_level="WARNNG",
            )

    def test_log_format_text_accepted(self):
        """text log format should be accepted."""
        s = Settings(
            _env_file=None,
            database_url="postgresql://localhost/test",
            anthropic_api_key="test-key",
            log_format="text",
        )
        assert s.log_format == "text"
