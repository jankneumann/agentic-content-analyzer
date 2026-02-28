"""Langfuse observability provider.

Uses OpenTelemetry with gen_ai.* semantic conventions to export traces
to Langfuse (Cloud or self-hosted). Langfuse provides LLM-specific
tracing, prompt management, and evaluation.

Cloud: https://cloud.langfuse.com/api/public/otel
Self-hosted: {base_url}/api/public/otel
"""

from __future__ import annotations

import base64
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Generator

    from fastapi import FastAPI

from src.utils.logging import get_logger

logger = get_logger(__name__)

# gen_ai semantic convention attribute names (EXPERIMENTAL — may change)
# Pinned as constants for single-point-of-update if conventions evolve
GEN_AI_SYSTEM = "gen_ai.system"
GEN_AI_REQUEST_MODEL = "gen_ai.request.model"
GEN_AI_REQUEST_MAX_TOKENS = "gen_ai.request.max_tokens"
GEN_AI_USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
GEN_AI_USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"
GEN_AI_PROMPT = "gen_ai.prompt"
GEN_AI_COMPLETION = "gen_ai.completion"

# Default Langfuse Cloud base URL
LANGFUSE_CLOUD_BASE_URL = "https://cloud.langfuse.com"


class LangfuseProvider:
    """Langfuse observability provider using OTel with gen_ai.* attributes.

    Supports both Langfuse Cloud and self-hosted deployments.
    Authentication uses HTTP Basic Auth with public_key:secret_key.
    All LLM calls are traced with gen_ai semantic conventions that
    Langfuse recognizes for LLM-specific visualization.
    """

    def __init__(
        self,
        *,
        public_key: str | None = None,
        secret_key: str | None = None,
        base_url: str = LANGFUSE_CLOUD_BASE_URL,
        service_name: str = "newsletter-aggregator",
        log_prompts: bool = False,
    ) -> None:
        self._public_key = public_key
        self._secret_key = secret_key
        self._base_url = base_url
        self._service_name = service_name
        self._log_prompts = log_prompts
        self._tracer: Any = None
        self._tracer_provider: Any = None
        self._setup_complete = False

    @property
    def name(self) -> str:
        return "langfuse"

    def _build_auth_header(self) -> dict[str, str]:
        """Build HTTP Basic Auth header for Langfuse.

        Constructs Authorization: Basic base64(public_key:secret_key).
        Returns empty dict if either key is missing.
        """
        if not self._public_key or not self._secret_key:
            return {}

        credentials = f"{self._public_key}:{self._secret_key}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return {"Authorization": f"Basic {encoded}"}

    def _get_endpoint(self) -> str:
        """Get the OTLP endpoint URL.

        Always constructs from base_url + /api/public/otel.
        Never returns None since base_url has a default.
        """
        return f"{self._base_url.rstrip('/')}/api/public/otel"

    def setup(self, app: FastAPI | None = None) -> None:
        """Initialize OTel SDK with OTLP exporter pointing to Langfuse."""
        if self._setup_complete:
            return

        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

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

            resource = Resource.create({"service.name": self._service_name})
            self._tracer_provider = TracerProvider(resource=resource)

            endpoint = self._get_endpoint()

            # Ensure endpoint includes /v1/traces path
            if not endpoint.endswith("/v1/traces"):
                endpoint = f"{endpoint.rstrip('/')}/v1/traces"

            exporter = OTLPSpanExporter(
                endpoint=endpoint,
                headers=self._build_auth_header(),
            )
            self._tracer_provider.add_span_processor(BatchSpanProcessor(exporter))

            # Get tracer from our own provider — don't overwrite the global
            # OTel tracer provider, which may be used by infrastructure
            # auto-instrumentation (otel_setup.py).
            self._tracer = self._tracer_provider.get_tracer(__name__)
            self._setup_complete = True

            logger.info(f"Langfuse provider initialized (endpoint: {endpoint})")
        except ImportError:
            logger.error(
                "OpenTelemetry packages not installed. "
                "Install with: pip install opentelemetry-api opentelemetry-sdk "
                "opentelemetry-exporter-otlp-proto-http"
            )

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
        """Record an LLM call with gen_ai.* semantic conventions."""
        if self._tracer is None:
            return

        with self._tracer.start_as_current_span("llm.completion") as span:
            span.set_attribute(GEN_AI_SYSTEM, provider)
            span.set_attribute(GEN_AI_REQUEST_MODEL, model)
            span.set_attribute(GEN_AI_USAGE_INPUT_TOKENS, input_tokens)
            span.set_attribute(GEN_AI_USAGE_OUTPUT_TOKENS, output_tokens)

            if max_tokens is not None:
                span.set_attribute(GEN_AI_REQUEST_MAX_TOKENS, max_tokens)

            if self._log_prompts:
                span.set_attribute(GEN_AI_PROMPT, user_prompt[:1000])
                span.set_attribute(GEN_AI_COMPLETION, response_text[:1000])

            if metadata:
                for key, value in metadata.items():
                    span.set_attribute(f"custom.{key}", str(value))

    @contextmanager
    def start_span(
        self, name: str, attributes: dict[str, Any] | None = None
    ) -> Generator[Any, None, None]:
        """Start a named OTel span."""
        if self._tracer is None:
            yield None
            return

        with self._tracer.start_as_current_span(name) as span:
            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, str(value))
            yield span

    def flush(self) -> None:
        """Flush the OTel span processor."""
        if self._tracer_provider is not None:
            try:
                self._tracer_provider.force_flush()
            except Exception as e:
                logger.debug(f"Error flushing Langfuse provider: {e}")

    def shutdown(self) -> None:
        """Shut down the OTel tracer provider."""
        if self._tracer_provider is not None:
            try:
                self._tracer_provider.shutdown()
            except Exception as e:
                logger.debug(f"Error shutting down Langfuse provider: {e}")
        self._tracer_provider = None
        self._tracer = None
        self._setup_complete = False
