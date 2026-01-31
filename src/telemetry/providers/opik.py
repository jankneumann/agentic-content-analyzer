"""Opik observability provider.

Uses OpenTelemetry with gen_ai.* semantic conventions to export traces
to Opik (Comet Cloud or self-hosted). Opik provides LLM-specific
visualization, evaluation, and hallucination detection.

Comet Cloud: https://www.comet.com/opik/api/v1/private/otel
Self-hosted: Configurable OTLP HTTP endpoint
"""

from __future__ import annotations

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

# Default Comet Cloud OTLP endpoint
COMET_CLOUD_OTLP_ENDPOINT = "https://www.comet.com/opik/api/v1/private/otel"


class OpikProvider:
    """Opik observability provider using OTel with gen_ai.* attributes.

    Supports both Comet Cloud and self-hosted Opik deployments.
    All LLM calls are traced with gen_ai semantic conventions that
    Opik recognizes for LLM-specific visualization.
    """

    def __init__(
        self,
        *,
        endpoint: str | None = None,
        headers: str | None = None,
        api_key: str | None = None,
        workspace: str | None = None,
        project_name: str = "newsletter-aggregator",
        service_name: str = "newsletter-aggregator",
        log_prompts: bool = False,
    ) -> None:
        self._endpoint = endpoint
        self._headers = headers
        self._api_key = api_key
        self._workspace = workspace
        self._project_name = project_name
        self._service_name = service_name
        self._log_prompts = log_prompts
        self._tracer: Any = None
        self._tracer_provider: Any = None
        self._setup_complete = False

    @property
    def name(self) -> str:
        return "opik"

    def _build_headers(self) -> dict[str, str]:
        """Build OTLP headers for Opik.

        For Comet Cloud, constructs Authorization + project headers.
        For self-hosted, parses user-provided header string.
        """
        headers: dict[str, str] = {}

        # If explicit headers are provided, parse them
        if self._headers:
            for pair in self._headers.split(","):
                pair = pair.strip()
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    headers[key.strip()] = value.strip()
            return headers

        # Construct Comet Cloud headers from individual settings
        if self._api_key:
            headers["Authorization"] = self._api_key
        if self._project_name:
            headers["projectName"] = self._project_name
        if self._workspace:
            headers["Comet-Workspace"] = self._workspace

        return headers

    def _get_endpoint(self) -> str:
        """Get the OTLP endpoint URL.

        Defaults to Comet Cloud if API key is set and no explicit endpoint.
        """
        if self._endpoint:
            return self._endpoint
        if self._api_key:
            return COMET_CLOUD_OTLP_ENDPOINT
        return "http://localhost:5173/api"

    def setup(self, app: FastAPI | None = None) -> None:
        """Initialize OTel SDK with OTLP exporter pointing to Opik."""
        if self._setup_complete:
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

            exporter = OTLPSpanExporter(
                endpoint=f"{self._get_endpoint()}/v1/traces",
                headers=self._build_headers(),
            )
            self._tracer_provider.add_span_processor(BatchSpanProcessor(exporter))
            trace.set_tracer_provider(self._tracer_provider)

            self._tracer = trace.get_tracer(__name__)
            self._setup_complete = True

            logger.info(f"Opik provider initialized (endpoint: {self._get_endpoint()})")
        except ImportError:
            logger.error(
                "OpenTelemetry packages not installed. "
                "Install with: pip install opentelemetry-api opentelemetry-sdk "
                "opentelemetry-exporter-otlp-proto-http"
            )

    def _get_tracer(self) -> Any:
        """Get the OTel tracer, initializing if needed."""
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
                logger.debug(f"Error flushing Opik provider: {e}")

    def shutdown(self) -> None:
        """Shut down the OTel tracer provider."""
        if self._tracer_provider is not None:
            try:
                self._tracer_provider.shutdown()
            except Exception as e:
                logger.debug(f"Error shutting down Opik provider: {e}")
        self._tracer_provider = None
        self._tracer = None
        self._setup_complete = False
