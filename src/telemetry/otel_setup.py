"""OpenTelemetry infrastructure auto-instrumentation setup.

Configures auto-instrumentation for FastAPI, SQLAlchemy, and httpx.
This is the infrastructure layer (Layer 1) that runs regardless of
which LLM observability provider is selected.

Only active when settings.otel_enabled is True.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI
    from opentelemetry.sdk.resources import Resource

from src.config import settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


def _parse_headers(headers_str: str | None) -> dict[str, str]:
    """Parse comma-separated key=value header string into dict."""
    if not headers_str:
        return {}
    result: dict[str, str] = {}
    for pair in headers_str.split(","):
        pair = pair.strip()
        if "=" in pair:
            key, value = pair.split("=", 1)
            result[key.strip()] = value.strip()
    return result


def _build_exporter_config(path_suffix: str) -> tuple[str, dict[str, str]]:
    """Build (endpoint, headers) for an OTLP exporter.

    Appends the path_suffix (e.g. "/v1/traces", "/v1/logs") to the base
    endpoint if not already present, and parses the OTLP headers string.

    Args:
        path_suffix: OTLP path to append (e.g. "/v1/traces", "/v1/logs")

    Returns:
        Tuple of (endpoint_url, headers_dict)
    """
    headers = _parse_headers(settings.otel_exporter_otlp_headers)
    endpoint = settings.otel_exporter_otlp_endpoint or ""
    if not endpoint.endswith(path_suffix):
        endpoint = f"{endpoint.rstrip('/')}{path_suffix}"
    return endpoint, headers


def _create_resource() -> Resource:
    """Create a shared OTel Resource for all signal providers.

    Returns the same Resource identity for TracerProvider, LoggerProvider,
    and MeterProvider so that traces, logs, and metrics are correlated by
    service.name and deployment.environment.

    Returns:
        An opentelemetry.sdk.resources.Resource instance
    """
    from opentelemetry.sdk.resources import Resource as _Resource

    return _Resource.create(
        {
            "service.name": settings.otel_service_name,
            "telemetry.sdk.name": "opentelemetry",
            "deployment.environment": settings.environment,
        }
    )


def setup_otel_infrastructure(app: FastAPI | None = None) -> None:
    """Configure OTel auto-instrumentation for infrastructure.

    Sets up:
    - TracerProvider with OTLP HTTP exporter
    - FastAPI auto-instrumentation (HTTP requests, latency)
    - SQLAlchemy auto-instrumentation (database queries)
    - httpx auto-instrumentation (outbound HTTP calls)

    Only runs when settings.otel_enabled is True and an OTLP endpoint
    is configured.

    Args:
        app: FastAPI application instance (required for FastAPI instrumentation)
    """
    if not settings.otel_enabled:
        logger.debug("OTel infrastructure instrumentation is disabled (OTEL_ENABLED=false)")
        return

    if not settings.otel_exporter_otlp_endpoint:
        logger.warning(
            "OTel enabled but OTEL_EXPORTER_OTLP_ENDPOINT not set. "
            "Skipping infrastructure instrumentation."
        )
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        logger.error(
            "OpenTelemetry packages not installed. "
            "Install with: pip install opentelemetry-sdk opentelemetry-exporter-otlp-proto-http"
        )
        return

    # Shared resource for all OTel signal providers (traces, logs, metrics)
    resource = _create_resource()

    # Configure trace exporter
    endpoint, headers = _build_exporter_config("/v1/traces")
    exporter = OTLPSpanExporter(
        endpoint=endpoint,
        headers=headers,
    )

    # Only set global tracer provider if not already set by an LLM provider
    # (Opik and OTel providers set their own TracerProvider in setup())
    current_provider = trace.get_tracer_provider()
    is_default = type(current_provider).__name__ == "ProxyTracerProvider"

    if is_default:
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        logger.info("OTel TracerProvider configured for infrastructure")
    else:
        logger.info("OTel TracerProvider already set by LLM provider, skipping")

    # Auto-instrumentation: FastAPI
    if app is not None:
        try:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

            FastAPIInstrumentor.instrument_app(app)
            logger.info("FastAPI auto-instrumentation enabled")
        except ImportError:
            logger.debug("opentelemetry-instrumentation-fastapi not installed, skipping")

    # Auto-instrumentation: SQLAlchemy
    _instrument_sqlalchemy()

    # Auto-instrumentation: httpx
    _instrument_httpx()

    # OTel log bridge: attach LoggingHandler to export logs via OTLP
    from src.telemetry.log_setup import setup_otel_log_bridge

    setup_otel_log_bridge(resource)

    logger.info(
        f"OTel infrastructure instrumentation initialized "
        f"(endpoint: {settings.otel_exporter_otlp_endpoint})"
    )


def _instrument_sqlalchemy() -> None:
    """Instrument SQLAlchemy for database query tracing."""
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        SQLAlchemyInstrumentor().instrument()
        logger.info("SQLAlchemy auto-instrumentation enabled")
    except ImportError:
        logger.debug("opentelemetry-instrumentation-sqlalchemy not installed, skipping")
    except Exception as e:
        logger.debug(f"SQLAlchemy instrumentation failed: {e}")


def _instrument_httpx() -> None:
    """Instrument httpx for outbound HTTP call tracing."""
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()
        logger.info("httpx auto-instrumentation enabled")
    except ImportError:
        logger.debug("opentelemetry-instrumentation-httpx not installed, skipping")
    except Exception as e:
        logger.debug(f"httpx instrumentation failed: {e}")
