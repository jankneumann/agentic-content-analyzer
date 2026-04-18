"""Unit tests for the Langfuse observability provider (SDK v4).

Tests the LangfuseProvider class in isolation (no Langfuse backend required).
Uses mocked Langfuse SDK to verify behavior.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.telemetry.providers.langfuse import LangfuseProvider, _sanitize_metadata

# ---------------------------------------------------------------------------
# Metadata Sanitization
# ---------------------------------------------------------------------------


class TestSanitizeMetadata:
    """Tests for _sanitize_metadata helper."""

    def test_none_returns_empty_dict(self):
        assert _sanitize_metadata(None) == {}

    def test_empty_dict_returns_empty_dict(self):
        assert _sanitize_metadata({}) == {}

    def test_string_values_pass_through(self):
        result = _sanitize_metadata({"key": "value"})
        assert result == {"key": "value"}

    def test_non_string_values_coerced(self):
        result = _sanitize_metadata({"count": 42, "flag": True, "rate": 0.5})
        assert result == {"count": "42", "flag": "True", "rate": "0.5"}

    def test_long_values_truncated_to_200(self):
        long_value = "x" * 300
        result = _sanitize_metadata({"key": long_value})
        assert len(result["key"]) == 200
        assert result["key"].endswith("...")

    def test_exactly_200_not_truncated(self):
        value = "x" * 200
        result = _sanitize_metadata({"key": value})
        assert result["key"] == value

    def test_non_string_keys_coerced(self):
        result = _sanitize_metadata({42: "value"})
        assert result == {"42": "value"}


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
        assert provider._sample_rate == 1.0
        assert provider._debug is False
        assert provider._environment is None
        assert provider._setup_complete is False

    def test_custom_initialization(self):
        provider = LangfuseProvider(
            public_key="pk-lf-test",
            secret_key="sk-lf-test",
            base_url="http://localhost:3100",
            service_name="test-service",
            log_prompts=True,
            sample_rate=0.5,
            debug=True,
            environment="staging",
        )
        assert provider._public_key == "pk-lf-test"
        assert provider._secret_key == "sk-lf-test"
        assert provider._base_url == "http://localhost:3100"
        assert provider._service_name == "test-service"
        assert provider._log_prompts is True
        assert provider._sample_rate == 0.5
        assert provider._debug is True
        assert provider._environment == "staging"

    def test_name_property(self):
        provider = LangfuseProvider()
        assert provider.name == "langfuse"


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------


class TestSetup:
    """Tests for setup() method."""

    def test_setup_creates_langfuse_client(self):
        mock_langfuse_cls = MagicMock()
        mock_client = MagicMock()
        mock_langfuse_cls.return_value = mock_client

        provider = LangfuseProvider(
            public_key="pk-lf-test",
            secret_key="sk-lf-test",
            base_url="http://localhost:3100",
            sample_rate=0.8,
            debug=True,
            environment="staging",
        )

        with patch.dict("sys.modules", {"langfuse": MagicMock(Langfuse=mock_langfuse_cls)}):
            with patch.object(provider, "_setup_anthropic_instrumentor"):
                provider.setup()

        assert provider._setup_complete is True
        assert provider._client is mock_client
        mock_langfuse_cls.assert_called_once_with(
            host="http://localhost:3100",
            sample_rate=0.8,
            debug=True,
            public_key="pk-lf-test",
            secret_key="sk-lf-test",
            environment="staging",
        )

    def test_setup_without_keys_warns_but_succeeds(self):
        mock_langfuse_cls = MagicMock()

        provider = LangfuseProvider(base_url="http://localhost:3100")

        with patch.dict("sys.modules", {"langfuse": MagicMock(Langfuse=mock_langfuse_cls)}):
            with patch.object(provider, "_setup_anthropic_instrumentor"):
                provider.setup()

        assert provider._setup_complete is True
        # Keys not passed when None
        call_kwargs = mock_langfuse_cls.call_args.kwargs
        assert "public_key" not in call_kwargs
        assert "secret_key" not in call_kwargs

    def test_setup_is_idempotent(self):
        provider = LangfuseProvider()
        provider._setup_complete = True
        provider.setup()
        assert provider._client is None  # Not re-initialized

    def test_setup_handles_import_error(self):
        provider = LangfuseProvider()

        with patch("builtins.__import__", side_effect=ImportError("No langfuse")):
            provider.setup()

        assert provider._setup_complete is True
        assert provider._client is None


# ---------------------------------------------------------------------------
# AnthropicInstrumentor
# ---------------------------------------------------------------------------


class TestAnthropicInstrumentor:
    """Tests for _setup_anthropic_instrumentor()."""

    def test_instrumentor_activated_when_available(self):
        mock_instrumentor_cls = MagicMock()
        provider = LangfuseProvider()

        with patch.dict(
            "sys.modules",
            {
                "opentelemetry.instrumentation.anthropic": MagicMock(
                    AnthropicInstrumentor=mock_instrumentor_cls
                )
            },
        ):
            provider._setup_anthropic_instrumentor()

        assert provider._instrumentor_active is True
        mock_instrumentor_cls.return_value.instrument.assert_called_once()

    def test_instrumentor_handles_import_error(self):
        provider = LangfuseProvider()

        with patch(
            "builtins.__import__",
            side_effect=ImportError("No anthropic instrumentor"),
        ):
            provider._setup_anthropic_instrumentor()

        assert provider._instrumentor_active is False


# ---------------------------------------------------------------------------
# Tracing
# ---------------------------------------------------------------------------


class TestTraceLlmCall:
    """Tests for trace_llm_call() method."""

    def test_trace_creates_generation_observation(self):
        mock_client = MagicMock()
        mock_obs = MagicMock()
        mock_client.start_as_current_observation.return_value.__enter__ = MagicMock(
            return_value=mock_obs
        )
        mock_client.start_as_current_observation.return_value.__exit__ = MagicMock(
            return_value=False
        )

        provider = LangfuseProvider()
        provider._client = mock_client

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

        call_kwargs = mock_client.start_as_current_observation.call_args.kwargs
        assert call_kwargs["as_type"] == "generation"
        assert call_kwargs["model"] == "claude-sonnet-4-5"
        assert call_kwargs["usage"] == {"input": 10, "output": 5}
        assert call_kwargs["metadata"]["provider"] == "anthropic"
        assert call_kwargs["metadata"]["max_tokens"] == "1024"

    def test_trace_includes_prompts_when_enabled(self):
        mock_client = MagicMock()
        mock_client.start_as_current_observation.return_value.__enter__ = MagicMock()
        mock_client.start_as_current_observation.return_value.__exit__ = MagicMock(
            return_value=False
        )

        provider = LangfuseProvider(log_prompts=True)
        provider._client = mock_client

        provider.trace_llm_call(
            model="test",
            provider="test",
            system_prompt="sys",
            user_prompt="user prompt",
            response_text="response text",
            input_tokens=1,
            output_tokens=1,
            duration_ms=1.0,
        )

        call_kwargs = mock_client.start_as_current_observation.call_args.kwargs
        assert call_kwargs["input"] == "user prompt"
        assert call_kwargs["output"] == "response text"

    def test_trace_excludes_prompts_when_disabled(self):
        mock_client = MagicMock()
        mock_client.start_as_current_observation.return_value.__enter__ = MagicMock()
        mock_client.start_as_current_observation.return_value.__exit__ = MagicMock(
            return_value=False
        )

        provider = LangfuseProvider(log_prompts=False)
        provider._client = mock_client

        provider.trace_llm_call(
            model="test",
            provider="test",
            system_prompt="sys",
            user_prompt="user prompt",
            response_text="response text",
            input_tokens=1,
            output_tokens=1,
            duration_ms=1.0,
        )

        call_kwargs = mock_client.start_as_current_observation.call_args.kwargs
        assert "input" not in call_kwargs
        assert "output" not in call_kwargs

    def test_trace_noop_without_client(self):
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

    def test_trace_sanitizes_metadata(self):
        mock_client = MagicMock()
        mock_client.start_as_current_observation.return_value.__enter__ = MagicMock()
        mock_client.start_as_current_observation.return_value.__exit__ = MagicMock(
            return_value=False
        )

        provider = LangfuseProvider()
        provider._client = mock_client

        provider.trace_llm_call(
            model="test",
            provider="test",
            system_prompt="sys",
            user_prompt="user",
            response_text="resp",
            input_tokens=1,
            output_tokens=1,
            duration_ms=1.0,
            metadata={"count": 42, "long": "x" * 300},
        )

        call_kwargs = mock_client.start_as_current_observation.call_args.kwargs
        assert call_kwargs["metadata"]["count"] == "42"
        assert len(call_kwargs["metadata"]["long"]) == 200


# ---------------------------------------------------------------------------
# Span
# ---------------------------------------------------------------------------


class TestStartSpan:
    """Tests for start_span() context manager."""

    def test_span_creates_observation(self):
        mock_client = MagicMock()
        mock_obs = MagicMock()
        mock_client.start_as_current_observation.return_value.__enter__ = MagicMock(
            return_value=mock_obs
        )
        mock_client.start_as_current_observation.return_value.__exit__ = MagicMock(
            return_value=False
        )

        provider = LangfuseProvider()
        provider._client = mock_client

        with provider.start_span("test.operation", {"key": "value"}):
            pass

        call_kwargs = mock_client.start_as_current_observation.call_args.kwargs
        assert call_kwargs["name"] == "test.operation"
        assert call_kwargs["as_type"] == "span"
        assert call_kwargs["metadata"] == {"key": "value"}

    def test_span_yields_none_without_client(self):
        provider = LangfuseProvider()
        with provider.start_span("test") as span:
            assert span is None


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


class TestLifecycle:
    """Tests for flush() and shutdown() methods."""

    def test_flush_calls_client_flush(self):
        provider = LangfuseProvider()
        provider._client = MagicMock()
        provider.flush()
        provider._client.flush.assert_called_once()

    def test_flush_handles_exception(self):
        provider = LangfuseProvider()
        provider._client = MagicMock()
        provider._client.flush.side_effect = Exception("flush error")
        provider.flush()  # Should not raise

    def test_flush_noop_without_client(self):
        provider = LangfuseProvider()
        provider.flush()  # Should not raise

    def test_shutdown_resets_state(self):
        provider = LangfuseProvider()
        provider._client = MagicMock()
        provider._setup_complete = True
        provider._instrumentor_active = True

        provider.shutdown()

        assert provider._client is None
        assert provider._setup_complete is False
        assert provider._instrumentor_active is False

    def test_shutdown_handles_exception(self):
        provider = LangfuseProvider()
        provider._client = MagicMock()
        provider._client.flush.side_effect = Exception("shutdown error")

        provider.shutdown()
        assert provider._client is None


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

    def test_factory_passes_new_v4_settings(self, monkeypatch):
        from src.config.settings import Settings
        from src.telemetry.providers.factory import get_observability_provider

        settings = Settings(
            _env_file=None,
            anthropic_api_key="test-key",
            observability_provider="langfuse",
            langfuse_sample_rate=0.5,
            langfuse_debug=True,
            langfuse_environment="staging",
        )

        monkeypatch.setattr("src.telemetry.providers.factory.settings", settings)

        provider = get_observability_provider()
        assert provider._sample_rate == 0.5
        assert provider._debug is True
        assert provider._environment == "staging"

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

    def test_settings_langfuse_v4_fields_default(self):
        from src.config.settings import Settings

        settings = Settings(_env_file=None, anthropic_api_key="test-key")
        assert settings.langfuse_sample_rate == 1.0
        assert settings.langfuse_debug is False
        assert settings.langfuse_environment is None

    def test_settings_sample_rate_clamped_high(self):
        from src.config.settings import Settings

        settings = Settings(
            _env_file=None,
            anthropic_api_key="test-key",
            langfuse_sample_rate=2.0,
        )
        assert settings.langfuse_sample_rate == 1.0

    def test_settings_sample_rate_clamped_low(self):
        from src.config.settings import Settings

        settings = Settings(
            _env_file=None,
            anthropic_api_key="test-key",
            langfuse_sample_rate=-0.5,
        )
        assert settings.langfuse_sample_rate == 0.0

    def test_settings_sample_rate_valid_passes(self):
        from src.config.settings import Settings

        settings = Settings(
            _env_file=None,
            anthropic_api_key="test-key",
            langfuse_sample_rate=0.5,
        )
        assert settings.langfuse_sample_rate == 0.5


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
