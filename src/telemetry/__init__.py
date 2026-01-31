"""Telemetry and observability for the Newsletter Aggregator.

Provides a provider-abstracted observability layer supporting multiple backends:
- noop (default): Zero overhead, disabled state
- opik: OTel + gen_ai.* attributes (Comet Cloud or self-hosted)
- braintrust: Native Braintrust SDK for rich LLM tracing
- otel: Generic OpenTelemetry OTLP export to any backend
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

from src.telemetry.providers import ObservabilityProvider, get_observability_provider
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Module-level provider instance (lazy singleton)
_provider = None


def get_provider() -> ObservabilityProvider:
    """Get the current observability provider (lazy singleton).

    Returns:
        The configured ObservabilityProvider instance
    """
    global _provider
    if _provider is None:
        _provider = get_observability_provider()
    return _provider


def setup_telemetry(app: FastAPI | None = None) -> None:
    """Initialize telemetry at application startup.

    Two-layer initialization:
    1. LLM observability provider (Opik, Braintrust, OTel, or noop)
    2. OTel infrastructure auto-instrumentation (FastAPI, SQLAlchemy, httpx)

    Args:
        app: FastAPI application instance (for middleware/instrumentation)
    """
    # Layer 1: LLM observability provider
    provider = get_provider()
    provider.setup(app=app)
    logger.info(f"Telemetry initialized with provider: {provider.name}")

    # Layer 2: OTel infrastructure auto-instrumentation
    from src.telemetry.otel_setup import setup_otel_infrastructure

    setup_otel_infrastructure(app=app)


def shutdown_telemetry() -> None:
    """Shut down telemetry at application shutdown.

    Flushes buffered data and releases resources.
    """
    global _provider
    if _provider is not None:
        _provider.flush()
        _provider.shutdown()
        logger.info(f"Telemetry shut down (provider: {_provider.name})")
        _provider = None


def reset_telemetry() -> None:
    """Reset telemetry state (for testing)."""
    global _provider
    if _provider is not None:
        _provider.shutdown()
    _provider = None
