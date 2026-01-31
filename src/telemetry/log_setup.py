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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from opentelemetry.sdk._logs import LoggerProvider
    from opentelemetry.sdk.resources import Resource

from src.config import settings
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Module-level references for shutdown
_logger_provider: LoggerProvider | None = None
_otel_handler: logging.Handler | None = None


def setup_otel_log_bridge(resource: Resource) -> LoggerProvider | None:
    """Configure the OTel log bridge with OTLP export.

    Creates a LoggerProvider sharing the same Resource as the TracerProvider,
    attaches a BatchLogRecordProcessor with an OTLPLogExporter, instruments
    stdlib logging for trace context injection, and adds a LoggingHandler
    to the root logger for OTLP export.

    Idempotent: returns the existing LoggerProvider if already initialized.

    Args:
        resource: An opentelemetry.sdk.resources.Resource instance shared
                  with TracerProvider for correlation.

    Returns:
        The LoggerProvider instance, or None if the bridge is disabled.
    """
    global _logger_provider, _otel_handler

    # Idempotency guard — prevent duplicate handlers on double-init
    if _logger_provider is not None:
        logger.debug("OTel log bridge already initialized, skipping")
        return _logger_provider

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
        from opentelemetry.sdk._logs import LoggerProvider as _LoggerProvider, LoggingHandler
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    except ImportError:
        logger.error(
            "OTel log bridge packages not installed. "
            "Install with: pip install opentelemetry-instrumentation-logging"
        )
        return None

    # Build the log pipeline: LoggerProvider → BatchProcessor → OTLPExporter
    from src.telemetry.otel_setup import _build_exporter_config

    endpoint, headers = _build_exporter_config("/v1/logs")

    log_exporter = OTLPLogExporter(
        endpoint=endpoint,
        headers=headers,
    )

    _logger_provider = _LoggerProvider(resource=resource)
    _logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
    set_logger_provider(_logger_provider)

    # Instrument stdlib logging for automatic trace context injection
    # (otelTraceID, otelSpanID, otelServiceName, otelTraceSampled)
    # set_logging_format=False: we manage our own formatters
    LoggingInstrumentor().instrument(set_logging_format=False)

    # Add LoggingHandler to root logger for OTLP export.
    # Log the setup message *before* attaching the handler so the bootstrap
    # message itself is not the first record exported to the backend.
    export_level = getattr(logging, settings.otel_logs_export_level.upper(), logging.WARNING)
    logger.info(
        f"OTel log bridge enabled (export_level={settings.otel_logs_export_level}, "
        f"endpoint={endpoint})"
    )

    handler = LoggingHandler(level=export_level, logger_provider=_logger_provider)
    logging.getLogger().addHandler(handler)
    _otel_handler = handler

    return _logger_provider


def shutdown_otel_log_bridge() -> None:
    """Shut down the OTel log bridge, flushing buffered log records.

    Removes the LoggingHandler from the root logger, shuts down the
    LoggerProvider, and uninstruments stdlib logging.
    """
    global _logger_provider, _otel_handler

    # Remove handler from root logger first (stop feeding records)
    if _otel_handler is not None:
        logging.getLogger().removeHandler(_otel_handler)
        _otel_handler = None

    # Shut down the LoggerProvider (flushes buffered records)
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
