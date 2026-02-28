"""Unit tests for the Langfuse observability provider.

Tests the LangfuseProvider class in isolation (no Langfuse backend required).
Uses mocked OTel SDK components to verify behavior.
"""

from __future__ import annotations

import base64
from unittest.mock import MagicMock, patch

import pytest

from src.telemetry.providers.langfuse import (
    GEN_AI_COMPLETION,
    GEN_AI_PROMPT,
    GEN_AI_REQUEST_MAX_TOKENS,
    GEN_AI_REQUEST_MODEL,
    GEN_AI_SYSTEM,
    GEN_AI_USAGE_INPUT_TOKENS,
    GEN_AI_USAGE_OUTPUT_TOKENS,
    LANGFUSE_CLOUD_BASE_URL,
    LangfuseProvider,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_tracer() -> tuple[MagicMock, MagicMock]:
    """Create a mock tracer + span pair wired for context-manager usage."""
    mock_span = MagicMock()
    mock_tracer = MagicMock()
    mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
    mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
    return mock_tracer, mock_span


def _set_attributes_dict(mock_span: MagicMock) -> dict[str, object]:
    """Extract all set_attribute calls into a dict."""
    return {call[0][0]: call[0][1] for call in mock_span.set_attribute.call_args_list}


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestSemanticConventionConstants:
    """Tests for gen_ai.* constant values."""

    def test_gen_ai_system(self):
        assert GEN_AI_SYSTEM == "gen_ai.system"

    def test_gen_ai_request_model(self):
        assert GEN_AI_REQUEST_MODEL == "gen_ai.request.model"

    def test_gen_ai_request_max_tokens(self):
        assert GEN_AI_REQUEST_MAX_TOKENS == "gen_ai.request.max_tokens"

    def test_gen_ai_usage_input_tokens(self):
        assert GEN_AI_USAGE_INPUT_TOKENS == "gen_ai.usage.input_tokens"

    def test_gen_ai_usage_output_tokens(self):
        assert GEN_AI_USAGE_OUTPUT_TOKENS == "gen_ai.usage.output_tokens"

    def test_gen_ai_prompt(self):
        assert GEN_AI_PROMPT == "gen_ai.prompt"

    def test_gen_ai_completion(self):
        assert GEN_AI_COMPLETION == "gen_ai.completion"

    def test_cloud_base_url(self):
        assert LANGFUSE_CLOUD_BASE_URL == "https://cloud.langfuse.com"


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


class TestLangfuseProviderInit:
    """Tests for LangfuseProvider initialization."""

    def test_default_initialization(self):
        provider = LangfuseProvider()
        assert provider.name == "langfuse"
        assert provider._public_key is None
        assert provider._secret_key is None
        assert provider._base_url == "https://cloud.langfuse.com"
        assert provider._service_name == "newsletter-aggregator"
        assert provider._log_prompts is False
        assert provider._setup_complete is False

    def test_custom_initialization(self):
        provider = LangfuseProvider(
            public_key="pk-lf-test",
            secret_key="sk-lf-test",
            base_url="http://localhost:3100",
            service_name="test-service",
            log_prompts=True,
        )
        assert provider._public_key == "pk-lf-test"
        assert provider._secret_key == "sk-lf-test"
        assert provider._base_url == "http://localhost:3100"
        assert provider._service_name == "test-service"
        assert provider._log_prompts is True

    def test_name_property(self):
        provider = LangfuseProvider()
        assert provider.name == "langfuse"


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


class TestBuildAuthHeader:
    """Tests for _build_auth_header() method."""

    def test_both_keys_present(self):
        provider = LangfuseProvider(public_key="pk-lf-abc", secret_key="sk-lf-xyz")
        headers = provider._build_auth_header()
        expected = base64.b64encode(b"pk-lf-abc:sk-lf-xyz").decode()
        assert headers == {"Authorization": f"Basic {expected}"}

    def test_no_keys(self):
        provider = LangfuseProvider()
        assert provider._build_auth_header() == {}

    def test_only_public_key(self):
        provider = LangfuseProvider(public_key="pk-lf-abc")
        assert provider._build_auth_header() == {}

    def test_only_secret_key(self):
        provider = LangfuseProvider(secret_key="sk-lf-xyz")
        assert provider._build_auth_header() == {}

    def test_empty_string_keys(self):
        provider = LangfuseProvider(public_key="", secret_key="")
        assert provider._build_auth_header() == {}

    def test_special_characters_in_keys(self):
        provider = LangfuseProvider(public_key="pk-lf-abc+123/=", secret_key="sk-lf-xyz!@#")
        headers = provider._build_auth_header()
        expected = base64.b64encode(b"pk-lf-abc+123/=:sk-lf-xyz!@#").decode()
        assert headers == {"Authorization": f"Basic {expected}"}


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


class TestGetEndpoint:
    """Tests for _get_endpoint() method."""

    def test_default_cloud_endpoint(self):
        provider = LangfuseProvider()
        assert provider._get_endpoint() == "https://cloud.langfuse.com/api/public/otel"

    def test_self_hosted_endpoint(self):
        provider = LangfuseProvider(base_url="http://localhost:3100")
        assert provider._get_endpoint() == "http://localhost:3100/api/public/otel"

    def test_trailing_slash_stripped(self):
        provider = LangfuseProvider(base_url="http://localhost:3100/")
        assert provider._get_endpoint() == "http://localhost:3100/api/public/otel"

    def test_us_cloud_endpoint(self):
        provider = LangfuseProvider(base_url="https://us.cloud.langfuse.com")
        assert provider._get_endpoint() == "https://us.cloud.langfuse.com/api/public/otel"

    def test_eu_cloud_endpoint(self):
        provider = LangfuseProvider(base_url="https://eu.cloud.langfuse.com")
        assert provider._get_endpoint() == "https://eu.cloud.langfuse.com/api/public/otel"


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------


class TestSetup:
    """Tests for setup() method."""

    @staticmethod
    def _run_setup_with_mocked_otel(provider: LangfuseProvider):
        """Run setup() with mocked OTel imports.

        Returns tuple: (mock_resource, mock_tp_cls, mock_exporter_cls, mock_bsp)
        """
        mock_resource = MagicMock()
        mock_tp_cls = MagicMock()
        mock_exporter_cls = MagicMock()
        mock_bsp = MagicMock()

        with (
            patch("opentelemetry.sdk.resources.Resource", mock_resource),
            patch("opentelemetry.sdk.trace.TracerProvider", mock_tp_cls),
            patch(
                "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter",
                mock_exporter_cls,
            ),
            patch("opentelemetry.sdk.trace.export.BatchSpanProcessor", mock_bsp),
        ):
            provider.setup()

        return mock_resource, mock_tp_cls, mock_exporter_cls, mock_bsp

    def test_setup_with_full_auth(self):
        """Verify setup initializes OTel with auth headers."""
        provider = LangfuseProvider(
            public_key="pk-lf-test",
            secret_key="sk-lf-test",
            base_url="http://localhost:3100",
        )
        self._run_setup_with_mocked_otel(provider)

        assert provider._setup_complete is True
        assert provider._tracer_provider is not None

    def test_setup_does_not_set_global_tracer_provider(self):
        """Verify setup uses local TracerProvider, not the global one.

        This prevents overwriting infrastructure OTel (otel_setup.py).
        """
        provider = LangfuseProvider(
            public_key="pk-lf-test",
            secret_key="sk-lf-test",
            base_url="http://localhost:3100",
        )
        mock_tp_cls = MagicMock()
        mock_tp_instance = mock_tp_cls.return_value

        with (
            patch("opentelemetry.sdk.resources.Resource"),
            patch("opentelemetry.sdk.trace.TracerProvider", mock_tp_cls),
            patch("opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter"),
            patch("opentelemetry.sdk.trace.export.BatchSpanProcessor"),
        ):
            provider.setup()

        # Tracer obtained from local provider, not global trace.get_tracer()
        mock_tp_instance.get_tracer.assert_called_once()

    def test_setup_without_keys_warns_but_succeeds(self):
        """Verify setup works without keys (self-hosted)."""
        provider = LangfuseProvider(base_url="http://localhost:3100")
        self._run_setup_with_mocked_otel(provider)
        assert provider._setup_complete is True

    def test_setup_is_idempotent(self):
        """Verify calling setup() multiple times doesn't re-initialize."""
        provider = LangfuseProvider()
        provider._setup_complete = True
        provider.setup()
        assert provider._tracer_provider is None

    def test_setup_endpoint_includes_v1_traces(self):
        """Verify the exporter gets endpoint with /v1/traces suffix."""
        provider = LangfuseProvider(
            public_key="pk", secret_key="sk", base_url="http://localhost:3100"
        )
        _, _, mock_exporter_cls, _ = self._run_setup_with_mocked_otel(provider)
        call_kwargs = mock_exporter_cls.call_args
        endpoint = call_kwargs.kwargs.get("endpoint") or call_kwargs[1].get("endpoint")
        assert endpoint.endswith("/v1/traces")
        assert "/api/public/otel/" in endpoint


# ---------------------------------------------------------------------------
# Tracing
# ---------------------------------------------------------------------------


class TestTraceLlmCall:
    """Tests for trace_llm_call() method."""

    def test_trace_sets_gen_ai_attributes(self):
        mock_tracer, mock_span = _make_mock_tracer()
        provider = LangfuseProvider()
        provider._tracer = mock_tracer

        provider.trace_llm_call(
            model="claude-sonnet-4-5",
            provider="anthropic",
            system_prompt="You are helpful",
            user_prompt="Hello",
            response_text="Hi there",
            input_tokens=10,
            output_tokens=5,
            duration_ms=100.0,
            max_tokens=1024,
        )

        attrs = _set_attributes_dict(mock_span)
        assert attrs[GEN_AI_SYSTEM] == "anthropic"
        assert attrs[GEN_AI_REQUEST_MODEL] == "claude-sonnet-4-5"
        assert attrs[GEN_AI_USAGE_INPUT_TOKENS] == 10
        assert attrs[GEN_AI_USAGE_OUTPUT_TOKENS] == 5
        assert attrs[GEN_AI_REQUEST_MAX_TOKENS] == 1024

    def test_trace_without_max_tokens(self):
        mock_tracer, mock_span = _make_mock_tracer()
        provider = LangfuseProvider()
        provider._tracer = mock_tracer

        provider.trace_llm_call(
            model="test",
            provider="test",
            system_prompt="sys",
            user_prompt="user",
            response_text="resp",
            input_tokens=1,
            output_tokens=1,
            duration_ms=1.0,
        )

        attrs = _set_attributes_dict(mock_span)
        assert GEN_AI_REQUEST_MAX_TOKENS not in attrs

    def test_trace_respects_log_prompts_false(self):
        mock_tracer, mock_span = _make_mock_tracer()
        provider = LangfuseProvider(log_prompts=False)
        provider._tracer = mock_tracer

        provider.trace_llm_call(
            model="test",
            provider="test",
            system_prompt="sys",
            user_prompt="user",
            response_text="resp",
            input_tokens=1,
            output_tokens=1,
            duration_ms=1.0,
        )

        attrs = _set_attributes_dict(mock_span)
        assert GEN_AI_PROMPT not in attrs
        assert GEN_AI_COMPLETION not in attrs

    def test_trace_logs_prompts_when_enabled(self):
        mock_tracer, mock_span = _make_mock_tracer()
        provider = LangfuseProvider(log_prompts=True)
        provider._tracer = mock_tracer

        provider.trace_llm_call(
            model="test",
            provider="test",
            system_prompt="sys",
            user_prompt="user prompt text",
            response_text="response text",
            input_tokens=1,
            output_tokens=1,
            duration_ms=1.0,
        )

        attrs = _set_attributes_dict(mock_span)
        assert attrs[GEN_AI_PROMPT] == "user prompt text"
        assert attrs[GEN_AI_COMPLETION] == "response text"

    def test_trace_truncates_long_prompts(self):
        mock_tracer, mock_span = _make_mock_tracer()
        provider = LangfuseProvider(log_prompts=True)
        provider._tracer = mock_tracer

        long_text = "x" * 2000
        provider.trace_llm_call(
            model="test",
            provider="test",
            system_prompt="sys",
            user_prompt=long_text,
            response_text=long_text,
            input_tokens=1,
            output_tokens=1,
            duration_ms=1.0,
        )

        attrs = _set_attributes_dict(mock_span)
        assert len(attrs[GEN_AI_PROMPT]) == 1000
        assert len(attrs[GEN_AI_COMPLETION]) == 1000

    def test_trace_with_metadata(self):
        mock_tracer, mock_span = _make_mock_tracer()
        provider = LangfuseProvider()
        provider._tracer = mock_tracer

        provider.trace_llm_call(
            model="test",
            provider="test",
            system_prompt="sys",
            user_prompt="user",
            response_text="resp",
            input_tokens=1,
            output_tokens=1,
            duration_ms=1.0,
            metadata={"step": "summarize", "pipeline": "daily"},
        )

        attrs = _set_attributes_dict(mock_span)
        assert attrs["custom.step"] == "summarize"
        assert attrs["custom.pipeline"] == "daily"

    def test_trace_noop_without_tracer(self):
        provider = LangfuseProvider()
        # Should not raise
        provider.trace_llm_call(
            model="test",
            provider="test",
            system_prompt="sys",
            user_prompt="user",
            response_text="resp",
            input_tokens=1,
            output_tokens=1,
            duration_ms=1.0,
        )


# ---------------------------------------------------------------------------
# Span
# ---------------------------------------------------------------------------


class TestStartSpan:
    """Tests for start_span() context manager."""

    def test_span_with_attributes(self):
        mock_tracer, mock_span = _make_mock_tracer()
        provider = LangfuseProvider()
        provider._tracer = mock_tracer

        with provider.start_span("test.operation", {"key": "value"}):
            pass

        mock_tracer.start_as_current_span.assert_called_once_with("test.operation")
        mock_span.set_attribute.assert_called_once_with("key", "value")

    def test_span_without_attributes(self):
        mock_tracer, mock_span = _make_mock_tracer()
        provider = LangfuseProvider()
        provider._tracer = mock_tracer

        with provider.start_span("test.operation"):
            pass

        mock_tracer.start_as_current_span.assert_called_once_with("test.operation")
        mock_span.set_attribute.assert_not_called()

    def test_span_yields_none_without_setup(self):
        """When setup() hasn't been called, start_span yields None.

        Without _get_tracer() lazy fallback, self._tracer stays None,
        so start_span correctly yields None rather than accidentally
        creating a non-recording span from the global OTel provider.
        """
        provider = LangfuseProvider()
        with provider.start_span("test") as span:
            assert span is None


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


class TestLifecycle:
    """Tests for flush() and shutdown() methods."""

    def test_flush_calls_force_flush(self):
        provider = LangfuseProvider()
        provider._tracer_provider = MagicMock()
        provider.flush()
        provider._tracer_provider.force_flush.assert_called_once()

    def test_flush_handles_exception(self):
        provider = LangfuseProvider()
        provider._tracer_provider = MagicMock()
        provider._tracer_provider.force_flush.side_effect = Exception("flush error")
        provider.flush()  # Should not raise

    def test_flush_noop_without_provider(self):
        provider = LangfuseProvider()
        provider.flush()  # Should not raise

    def test_shutdown_resets_state(self):
        provider = LangfuseProvider()
        provider._tracer_provider = MagicMock()
        provider._tracer = MagicMock()
        provider._setup_complete = True

        provider.shutdown()

        assert provider._tracer_provider is None
        assert provider._tracer is None
        assert provider._setup_complete is False

    def test_shutdown_handles_exception(self):
        provider = LangfuseProvider()
        provider._tracer_provider = MagicMock()
        provider._tracer_provider.shutdown.side_effect = Exception("shutdown error")

        provider.shutdown()
        assert provider._tracer_provider is None


# ---------------------------------------------------------------------------
# Factory Dispatch
# ---------------------------------------------------------------------------


class TestFactoryDispatch:
    """Tests for factory creating LangfuseProvider."""

    def test_factory_creates_langfuse_provider(self, monkeypatch):
        from src.config.settings import Settings
        from src.telemetry.providers.factory import get_observability_provider

        settings = Settings(
            _env_file=None,
            anthropic_api_key="test-key",
            observability_provider="langfuse",
            langfuse_public_key="pk-lf-test",
            langfuse_secret_key="sk-lf-test",
            langfuse_base_url="http://localhost:3100",
        )

        monkeypatch.setattr("src.telemetry.providers.factory.settings", settings)

        provider = get_observability_provider()
        assert provider.name == "langfuse"

    def test_factory_creates_langfuse_without_keys(self, monkeypatch):
        from src.config.settings import Settings
        from src.telemetry.providers.factory import get_observability_provider

        settings = Settings(
            _env_file=None,
            anthropic_api_key="test-key",
            observability_provider="langfuse",
        )

        monkeypatch.setattr("src.telemetry.providers.factory.settings", settings)

        provider = get_observability_provider()
        assert provider.name == "langfuse"


# ---------------------------------------------------------------------------
# Settings Validation
# ---------------------------------------------------------------------------


class TestSettingsValidation:
    """Tests for Langfuse settings validation."""

    def test_settings_accepts_langfuse_provider(self):
        from src.config.settings import Settings

        settings = Settings(
            _env_file=None,
            anthropic_api_key="test-key",
            observability_provider="langfuse",
        )
        assert settings.observability_provider == "langfuse"

    def test_settings_langfuse_fields_default(self):
        from src.config.settings import Settings

        settings = Settings(_env_file=None, anthropic_api_key="test-key")
        assert settings.langfuse_public_key is None
        assert settings.langfuse_secret_key is None
        assert settings.langfuse_base_url == "https://cloud.langfuse.com"

    def test_settings_langfuse_with_keys(self):
        from src.config.settings import Settings

        settings = Settings(
            _env_file=None,
            anthropic_api_key="test-key",
            observability_provider="langfuse",
            langfuse_public_key="pk-lf-test",
            langfuse_secret_key="sk-lf-test",
            langfuse_base_url="http://localhost:3100",
        )
        assert settings.langfuse_public_key == "pk-lf-test"
        assert settings.langfuse_secret_key == "sk-lf-test"
        assert settings.langfuse_base_url == "http://localhost:3100"

    def test_settings_rejects_invalid_provider(self):
        from pydantic import ValidationError

        from src.config.settings import Settings

        with pytest.raises(ValidationError):
            Settings(
                _env_file=None,
                anthropic_api_key="test-key",
                observability_provider="invalid",
            )


# ---------------------------------------------------------------------------
# Protocol Compliance
# ---------------------------------------------------------------------------


class TestProtocolCompliance:
    """Tests verifying ObservabilityProvider protocol conformance."""

    def test_isinstance_check(self):
        from src.telemetry.providers.base import ObservabilityProvider

        provider = LangfuseProvider()
        assert isinstance(provider, ObservabilityProvider)

    def test_has_all_protocol_methods(self):
        provider = LangfuseProvider()
        assert hasattr(provider, "name")
        assert hasattr(provider, "setup")
        assert hasattr(provider, "trace_llm_call")
        assert hasattr(provider, "start_span")
        assert hasattr(provider, "flush")
        assert hasattr(provider, "shutdown")
