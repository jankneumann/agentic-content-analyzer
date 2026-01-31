"""Factory function for observability providers.

Follows the same pattern as src/storage/providers/factory.py for database providers
and src/services/file_storage.py for storage providers.
"""

from __future__ import annotations

from src.config import settings
from src.telemetry.providers.base import ObservabilityProvider
from src.telemetry.providers.noop import NoopProvider
from src.utils.logging import get_logger

logger = get_logger(__name__)


def get_observability_provider() -> ObservabilityProvider:
    """Get the configured observability provider.

    Provider selection is determined by settings.observability_provider:
    - "noop" (default): Zero overhead, disabled state
    - "opik": OTel-based with gen_ai.* semantic conventions
    - "braintrust": Native Braintrust SDK for rich LLM tracing
    - "otel": Generic OpenTelemetry OTLP export to any backend

    Returns:
        ObservabilityProvider implementation

    Raises:
        ValueError: If a provider requires configuration that is missing
    """
    provider_type = settings.observability_provider

    match provider_type:
        case "opik":
            from src.telemetry.providers.opik import OpikProvider

            return OpikProvider(
                endpoint=settings.otel_exporter_otlp_endpoint,
                headers=settings.otel_exporter_otlp_headers,
                api_key=settings.opik_api_key,
                workspace=settings.opik_workspace,
                project_name=settings.opik_project_name,
                service_name=settings.otel_service_name,
                log_prompts=settings.otel_log_prompts,
            )

        case "braintrust":
            from src.telemetry.providers.braintrust import BraintrustProvider

            return BraintrustProvider(
                api_key=settings.braintrust_api_key,
                project_name=settings.braintrust_project_name,
                api_url=settings.braintrust_api_url,
                log_prompts=settings.otel_log_prompts,
            )

        case "otel":
            from src.telemetry.providers.otel_provider import OTelProvider

            return OTelProvider(
                endpoint=settings.otel_exporter_otlp_endpoint,
                headers=settings.otel_exporter_otlp_headers,
                service_name=settings.otel_service_name,
                log_prompts=settings.otel_log_prompts,
            )

        case _:  # "noop" or any unrecognized value
            return NoopProvider()
