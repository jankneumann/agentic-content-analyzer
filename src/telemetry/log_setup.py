"""OpenTelemetry Log Bridge — third OTel signal (traces + metrics + logs).

Bridges Python stdlib logging to the OTel Log Data Model.  Every log record
emitted within an active span is automatically enriched with TraceId and
SpanId (via LoggingInstrumentor), then exported to the same OTLP endpoint
as traces.

Two-phase initialization:
  1. setup_logging() configures the root logger with StreamHandler (console)
  2. setup_otel_log_bridge() adds a LoggingHandler (OTLP export) as a second handler

Only active when both settings.otel_enabled and settings.otel_logs_enabled are True.
"""

from __future__ import annotations

import logging
from typing import Any

from src.config import settings
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Module-level reference for shutdown (LoggerProvider or None)
_logger_provider: Any = None


def setup_otel_log_bridge(resource: object) -> Any:
    """Configure the OTel log bridge with OTLP export.

    Creates a LoggerProvider sharing the same Resource as the TracerProvider,
    attaches a BatchLogRecordProcessor with an OTLPLogExporter, instruments
    stdlib logging for trace context injection, and adds a LoggingHandler
    to the root logger for OTLP export.

    Args:
        resource: An opentelemetry.sdk.resources.Resource instance shared
                  with TracerProvider for correlation.

    Returns:
        The LoggerProvider instance, or None if the bridge is disabled.
    """
    global _logger_provider

    if not settings.otel_enabled:
        logger.debug("OTel log bridge disabled (OTEL_ENABLED=false)")
        return None

    if not settings.otel_logs_enabled:
        logger.debug("OTel log bridge disabled (OTEL_LOGS_ENABLED=false)")
        return None

    if not settings.otel_exporter_otlp_endpoint:
        logger.debug("OTel log bridge disabled (no OTLP endpoint)")
        return None

    try:
        from opentelemetry._logs import set_logger_provider
        from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
        from opentelemetry.instrumentation.logging import LoggingInstrumentor
        from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    except ImportError:
        logger.error(
            "OTel log bridge packages not installed. "
            "Install with: pip install opentelemetry-instrumentation-logging"
        )
        return None

    # Build the log pipeline: LoggerProvider → BatchProcessor → OTLPExporter
    from src.telemetry.otel_setup import _parse_headers

    headers = _parse_headers(settings.otel_exporter_otlp_headers)
    endpoint = settings.otel_exporter_otlp_endpoint
    if not endpoint.endswith("/v1/logs"):
        endpoint = f"{endpoint.rstrip('/')}/v1/logs"

    log_exporter = OTLPLogExporter(
        endpoint=endpoint,
        headers=headers,
    )

    _logger_provider = LoggerProvider(resource=resource)
    _logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
    set_logger_provider(_logger_provider)

    # Instrument stdlib logging for automatic trace context injection
    # (otelTraceID, otelSpanID, otelServiceName, otelTraceSampled)
    # set_logging_format=False: we manage our own formatters
    LoggingInstrumentor().instrument(set_logging_format=False)

    # Add LoggingHandler to root logger for OTLP export
    export_level = getattr(logging, settings.otel_logs_export_level.upper(), logging.WARNING)
    otel_handler = LoggingHandler(level=export_level, logger_provider=_logger_provider)
    logging.getLogger().addHandler(otel_handler)

    logger.info(
        f"OTel log bridge enabled (export_level={settings.otel_logs_export_level}, "
        f"endpoint={endpoint})"
    )

    return _logger_provider


def shutdown_otel_log_bridge() -> None:
    """Shut down the OTel log bridge, flushing buffered log records."""
    global _logger_provider

    if _logger_provider is not None:
        try:
            _logger_provider.shutdown()
            logger.debug("OTel log bridge shut down")
        except Exception as e:
            logger.debug(f"OTel log bridge shutdown error: {e}")
        finally:
            _logger_provider = None

    # Uninstrument logging
    try:
        from opentelemetry.instrumentation.logging import LoggingInstrumentor

        LoggingInstrumentor().uninstrument()
    except (ImportError, Exception):
        pass
