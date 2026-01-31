"""Generic OpenTelemetry observability provider.

Pure OTel implementation with gen_ai.* semantic conventions. Works with
any OTLP-compatible backend (Jaeger, Grafana Tempo, Datadog, etc.).
Use this provider when you don't have a dedicated provider for your
observability backend.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Generator

    from fastapi import FastAPI

from src.utils.logging import get_logger

logger = get_logger(__name__)

# gen_ai semantic convention attribute names (shared with OpikProvider)
GEN_AI_SYSTEM = "gen_ai.system"
GEN_AI_REQUEST_MODEL = "gen_ai.request.model"
GEN_AI_REQUEST_MAX_TOKENS = "gen_ai.request.max_tokens"
GEN_AI_USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
GEN_AI_USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"
GEN_AI_PROMPT = "gen_ai.prompt"
GEN_AI_COMPLETION = "gen_ai.completion"


class OTelProvider:
    """Generic OpenTelemetry provider for any OTLP-compatible backend.

    Exports traces via OTLP HTTP with gen_ai.* semantic conventions
    for LLM calls. This is the fallback provider for backends that
    don't have a dedicated implementation.
    """

    def __init__(
        self,
        *,
        endpoint: str | None = None,
        headers: str | None = None,
        service_name: str = "newsletter-aggregator",
        log_prompts: bool = False,
    ) -> None:
        self._endpoint = endpoint
        self._headers = headers
        self._service_name = service_name
        self._log_prompts = log_prompts
        self._tracer: Any = None
        self._tracer_provider: Any = None
        self._setup_complete = False

    @property
    def name(self) -> str:
        return "otel"

    def _parse_headers(self) -> dict[str, str]:
        """Parse header string into dict.

        Format: "key1=value1,key2=value2"
        """
        if not self._headers:
            return {}

        headers: dict[str, str] = {}
        for pair in self._headers.split(","):
            pair = pair.strip()
            if "=" in pair:
                key, value = pair.split("=", 1)
                headers[key.strip()] = value.strip()
        return headers

    def setup(self, app: FastAPI | None = None) -> None:
        """Initialize OTel SDK with OTLP HTTP exporter."""
        if self._setup_complete:
            return

        if not self._endpoint:
            logger.warning(
                "OTEL_EXPORTER_OTLP_ENDPOINT not configured. OTel traces will not be exported."
            )
            self._setup_complete = True
            return

        try:
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            resource = Resource.create({"service.name": self._service_name})
            self._tracer_provider = TracerProvider(resource=resource)

            # Ensure endpoint includes /v1/traces path
            endpoint = self._endpoint
            if not endpoint.endswith("/v1/traces"):
                endpoint = f"{endpoint.rstrip('/')}/v1/traces"

            exporter = OTLPSpanExporter(
                endpoint=endpoint,
                headers=self._parse_headers(),
            )
            self._tracer_provider.add_span_processor(BatchSpanProcessor(exporter))
            trace.set_tracer_provider(self._tracer_provider)

            self._tracer = trace.get_tracer(__name__)
            self._setup_complete = True

            logger.info(f"OTel provider initialized (endpoint: {self._endpoint})")
        except ImportError:
            logger.error(
                "OpenTelemetry packages not installed. "
                "Install with: pip install opentelemetry-api opentelemetry-sdk "
                "opentelemetry-exporter-otlp-proto-http"
            )
            self._setup_complete = True

    def _get_tracer(self) -> Any:
        """Get the OTel tracer."""
        if self._tracer is None:
            try:
                from opentelemetry import trace

                self._tracer = trace.get_tracer(__name__)
            except ImportError:
                return None
        return self._tracer

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
        tracer = self._get_tracer()
        if tracer is None:
            return

        with tracer.start_as_current_span("llm.completion") as span:
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
        tracer = self._get_tracer()
        if tracer is None:
            yield None
            return

        with tracer.start_as_current_span(name) as span:
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
                logger.debug(f"Error flushing OTel provider: {e}")

    def shutdown(self) -> None:
        """Shut down the OTel tracer provider."""
        if self._tracer_provider is not None:
            try:
                self._tracer_provider.shutdown()
            except Exception as e:
                logger.debug(f"Error shutting down OTel provider: {e}")
        self._tracer_provider = None
        self._tracer = None
        self._setup_complete = False
