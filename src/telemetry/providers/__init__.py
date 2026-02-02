"""Observability providers for the Newsletter Aggregator.

Supports multiple backends via provider factory pattern:
- noop: Zero overhead (default)
- opik: OTel-based with gen_ai.* semantic conventions
- braintrust: Native Braintrust SDK
- otel: Generic OTLP export
"""

from src.telemetry.providers.base import ObservabilityProvider
from src.telemetry.providers.factory import get_observability_provider
from src.telemetry.providers.noop import NoopProvider

__all__ = [
    "ObservabilityProvider",
    "NoopProvider",
    "get_observability_provider",
]
