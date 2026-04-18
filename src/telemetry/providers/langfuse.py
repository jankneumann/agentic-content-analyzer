"""Langfuse observability provider using native Langfuse Python SDK v4.

Uses the Langfuse SDK for generation-typed observations, automatic cost
tracking, session grouping, and @observe() decorator support. The SDK
is built on OpenTelemetry internally, so it coexists with our existing
OTel infrastructure auto-instrumentation (otel_setup.py).

Cloud: https://cloud.langfuse.com
Self-hosted: configurable via base_url
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Generator

    from fastapi import FastAPI

from src.utils.logging import get_logger

logger = get_logger(__name__)


def _sanitize_metadata(metadata: dict[str, Any] | None) -> dict[str, str]:
    """Sanitize metadata to dict[str, str] with 200-char value limit.

    Langfuse SDK v4 requires metadata values to be strings with a
    maximum length of 200 characters. Non-string values are coerced;
    oversized values are truncated.
    """
    if not metadata:
        return {}
    result: dict[str, str] = {}
    for key, value in metadata.items():
        str_value = str(value)
        if len(str_value) > 200:
            str_value = str_value[:197] + "..."
        result[str(key)] = str_value
    return result


class LangfuseProvider:
    """Langfuse observability provider using native SDK v4.

    Provides generation-typed observations for LLM calls, automatic cost
    tracking via Langfuse's model pricing database, and compatibility with
    @observe() decorators on pipeline functions.

    Supports both Langfuse Cloud and self-hosted deployments.
    """

    def __init__(
        self,
        *,
        public_key: str | None = None,
        secret_key: str | None = None,
        base_url: str = "https://cloud.langfuse.com",
        service_name: str = "newsletter-aggregator",
        log_prompts: bool = False,
        sample_rate: float = 1.0,
        debug: bool = False,
        environment: str | None = None,
    ) -> None:
        self._public_key = public_key
        self._secret_key = secret_key
        self._base_url = base_url
        self._service_name = service_name
        self._log_prompts = log_prompts
        self._sample_rate = sample_rate
        self._debug = debug
        self._environment = environment
        self._client: Any = None
        self._setup_complete = False
        self._instrumentor_active = False

    @property
    def name(self) -> str:
        return "langfuse"

    def setup(self, app: FastAPI | None = None) -> None:
        """Initialize Langfuse SDK and optionally enable AnthropicInstrumentor."""
        if self._setup_complete:
            return

        # Warn about partial or missing auth configuration
        has_public = bool(self._public_key)
        has_secret = bool(self._secret_key)

        if has_public != has_secret:
            logger.warning(
                "Langfuse provider has partial auth configuration: "
                f"public_key={'set' if has_public else 'missing'}, "
                f"secret_key={'set' if has_secret else 'missing'}. "
                "Both are required for authentication."
            )
        elif not has_public and not has_secret:
            logger.warning(
                "Langfuse provider initialized without authentication keys. "
                "This is acceptable for self-hosted instances without auth, "
                "but Langfuse Cloud requires public_key and secret_key."
            )

        try:
            from langfuse import Langfuse

            # Build constructor kwargs — only pass keys if provided
            kwargs: dict[str, Any] = {
                "host": self._base_url,
                "sample_rate": self._sample_rate,
                "debug": self._debug,
            }
            if self._public_key:
                kwargs["public_key"] = self._public_key
            if self._secret_key:
                kwargs["secret_key"] = self._secret_key
            if self._environment:
                kwargs["environment"] = self._environment

            self._client = Langfuse(**kwargs)
            self._setup_complete = True

            logger.info(
                f"Langfuse provider initialized "
                f"(host: {self._base_url}, "
                f"sample_rate: {self._sample_rate}, "
                f"environment: {self._environment or 'default'})"
            )

        except ImportError:
            logger.error(
                "Langfuse package not installed. Install with: pip install langfuse>=4.3.0"
            )
            self._setup_complete = True
            return

        # Enable AnthropicInstrumentor for automatic Claude call tracing
        self._setup_anthropic_instrumentor()

    def _setup_anthropic_instrumentor(self) -> None:
        """Enable AnthropicInstrumentor if available."""
        try:
            from opentelemetry.instrumentation.anthropic import AnthropicInstrumentor

            AnthropicInstrumentor().instrument()
            self._instrumentor_active = True
            logger.info("AnthropicInstrumentor enabled for automatic Claude call tracing")
        except ImportError:
            logger.warning(
                "opentelemetry-instrumentation-anthropic not installed. "
                "Automatic Claude call tracing disabled. "
                "Install with: pip install opentelemetry-instrumentation-anthropic"
            )
        except Exception as e:
            logger.warning(f"Failed to enable AnthropicInstrumentor: {e}")

    def trace_llm_call(
        self,
        *,
        model: str,
        provider: str,
        system_prompt: str,
        user_prompt: str,
        response_text: str,
        input_tokens: int,
        output_tokens: int,
        duration_ms: float,
        max_tokens: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record an LLM call as a Langfuse generation observation."""
        if self._client is None:
            return

        try:
            # Build generation kwargs
            gen_kwargs: dict[str, Any] = {
                "name": "llm.completion",
                "as_type": "generation",
                "model": model,
                "usage": {
                    "input": input_tokens,
                    "output": output_tokens,
                },
                "metadata": {
                    "provider": provider,
                    **_sanitize_metadata(metadata),
                },
            }

            if self._log_prompts:
                gen_kwargs["input"] = user_prompt[:1000]
                gen_kwargs["output"] = response_text[:1000]

            if max_tokens is not None:
                gen_kwargs["metadata"]["max_tokens"] = str(max_tokens)

            with self._client.start_as_current_observation(**gen_kwargs):
                pass  # Observation is created and closed immediately

        except Exception as e:
            # Never let telemetry failures break LLM calls
            logger.debug(f"Langfuse trace_llm_call failed: {e}")

    @contextmanager
    def start_span(
        self, name: str, attributes: dict[str, Any] | None = None
    ) -> Generator[Any, None, None]:
        """Start a named Langfuse span observation."""
        if self._client is None:
            yield None
            return

        try:
            with self._client.start_as_current_observation(
                name=name,
                as_type="span",
                metadata=_sanitize_metadata(attributes),
            ) as observation:
                yield observation
        except Exception as e:
            logger.debug(f"Langfuse start_span failed: {e}")
            yield None

    def flush(self) -> None:
        """Flush buffered Langfuse data."""
        if self._client is not None:
            try:
                self._client.flush()
            except Exception as e:
                logger.debug(f"Error flushing Langfuse provider: {e}")

    def shutdown(self) -> None:
        """Shut down the Langfuse provider."""
        if self._client is not None:
            try:
                self._client.flush()
            except Exception as e:
                logger.debug(f"Error shutting down Langfuse provider: {e}")
        self._client = None
        self._setup_complete = False
        self._instrumentor_active = False
