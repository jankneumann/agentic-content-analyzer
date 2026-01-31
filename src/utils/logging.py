"""Logging configuration with structured JSON and trace context support."""

import json
import logging
import sys
from datetime import UTC, datetime

from src.config import settings

# Attributes that are part of LogRecord internals or OTel injection —
# excluded from the "extra" section of JSON output.  Module-level frozenset
# avoids per-call allocation on every log line.
_INTERNAL_LOG_ATTRS = frozenset(
    {
        "name",
        "msg",
        "args",
        "created",
        "relativeCreated",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "pathname",
        "filename",
        "module",
        "levelno",
        "levelname",
        "msecs",
        "process",
        "processName",
        "thread",
        "threadName",
        "taskName",
        "message",
        "otelTraceID",
        "otelSpanID",
        "otelServiceName",
        "otelTraceSampled",
        # Framework-injected attrs that duplicate existing fields
        "color_message",  # uvicorn: ANSI-colored duplicate of message
    }
)


class JsonFormatter(logging.Formatter):
    """JSON Lines formatter for structured log output.

    Each log record is a single JSON object with timestamp, level, logger,
    message, trace context (when available), and any extra attributes.
    """

    def format(self, record: logging.LogRecord) -> str:
        # Defensive getMessage: if args don't match the format string, fall back
        # to the raw message rather than crashing the entire logging pipeline.
        try:
            message = record.getMessage()
        except Exception:
            message = str(record.msg)

        log_entry: dict = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": message,
        }

        # Add trace context if injected by LoggingInstrumentor
        trace_id = getattr(record, "otelTraceID", "0")
        span_id = getattr(record, "otelSpanID", "0")
        if trace_id and trace_id != "0":
            log_entry["trace_id"] = trace_id
        if span_id and span_id != "0":
            log_entry["span_id"] = span_id

        # Add exception info if present
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add stack info if present (e.g. logger.info("msg", stack_info=True))
        if record.stack_info:
            log_entry["stack_info"] = self.formatStack(record.stack_info)

        # Add extra attributes (skip internal logging attrs).
        # Non-serializable values are handled by default=str in json.dumps below.
        for key, value in record.__dict__.items():
            if key not in _INTERNAL_LOG_ATTRS and not key.startswith("_"):
                log_entry[key] = value

        return json.dumps(log_entry, default=str)


class TraceContextFormatter(logging.Formatter):
    """Text formatter that appends trace context when available.

    Extends the standard text format with [trace_id=... span_id=...] suffix
    when an active OTel span is present.
    """

    def __init__(self) -> None:
        super().__init__(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt=None,
        )

    def format(self, record: logging.LogRecord) -> str:
        result = super().format(record)

        trace_id = getattr(record, "otelTraceID", "0")
        span_id = getattr(record, "otelSpanID", "0")
        if trace_id and trace_id != "0":
            result += f" [trace_id={trace_id} span_id={span_id}]"

        return result


def setup_logging() -> None:
    """Configure application logging with format selection.

    Selects formatter based on settings.log_format:
    - "json" (default): JSON Lines for structured log aggregation
    - "text": Human-readable with optional trace context suffix
    """
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Select formatter based on settings
    if settings.log_format == "json":
        formatter: logging.Formatter = JsonFormatter()
    else:
        formatter = TraceContextFormatter()

    # Configure root logger with selected formatter
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    logging.basicConfig(
        level=log_level,
        handlers=[handler],
    )

    # Set specific log levels for noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("opentelemetry").setLevel(logging.WARNING)

    # Suppress verbose output from AI/ML libraries
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)
    logging.getLogger("graphiti_core").setLevel(logging.WARNING)

    # Suppress Neo4j driver verbose output
    logging.getLogger("neo4j").setLevel(logging.WARNING)
    logging.getLogger("neo4j.notifications").setLevel(
        logging.ERROR
    )  # Suppress index creation notifications


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(name)
