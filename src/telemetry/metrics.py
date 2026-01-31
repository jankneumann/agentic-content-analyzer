"""OpenTelemetry metrics for LLM and API monitoring.

Provides OTel meter instruments for tracking:
- LLM request counts and token usage
- API request duration
- Ingestion totals by source

Metrics are only active when settings.otel_enabled is True.
When disabled, the record functions are safe no-ops.
"""

from __future__ import annotations

from typing import Any

from src.utils.logging import get_logger

logger = get_logger(__name__)

# Module-level meter instruments (lazy-initialized)
_meter: Any = None
_llm_request_counter: Any = None
_llm_token_counter: Any = None
_llm_duration_histogram: Any = None
_ingestion_counter: Any = None


def _ensure_meter() -> bool:
    """Initialize the OTel meter if not already done.

    Returns True if meter is available, False otherwise.
    """
    global _meter, _llm_request_counter, _llm_token_counter
    global _llm_duration_histogram, _ingestion_counter

    if _meter is not None:
        return True

    try:
        from src.config import settings

        if not settings.otel_enabled:
            return False

        from opentelemetry import metrics

        _meter = metrics.get_meter("newsletter-aggregator")

        _llm_request_counter = _meter.create_counter(
            name="llm.requests",
            description="Total LLM API requests",
            unit="1",
        )

        _llm_token_counter = _meter.create_counter(
            name="llm.tokens",
            description="Total LLM tokens consumed",
            unit="tokens",
        )

        _llm_duration_histogram = _meter.create_histogram(
            name="llm.request.duration",
            description="LLM request duration",
            unit="ms",
        )

        _ingestion_counter = _meter.create_counter(
            name="ingestion.total",
            description="Total items ingested by source",
            unit="1",
        )

        logger.info("OTel metrics instruments initialized")
        return True
    except ImportError:
        logger.debug("OTel metrics not available (opentelemetry not installed)")
        return False
    except Exception as e:
        logger.debug(f"OTel metrics initialization failed: {e}")
        return False


def record_llm_request(
    *,
    model: str,
    provider: str,
    input_tokens: int,
    output_tokens: int,
    duration_ms: float,
) -> None:
    """Record an LLM request with token counts and duration.

    Safe no-op when OTel is disabled.
    """
    if not _ensure_meter():
        return

    attributes = {"model": model, "provider": provider}

    _llm_request_counter.add(1, attributes)
    _llm_token_counter.add(input_tokens, {**attributes, "direction": "input"})
    _llm_token_counter.add(output_tokens, {**attributes, "direction": "output"})
    _llm_duration_histogram.record(duration_ms, attributes)


def record_ingestion(*, source_type: str, count: int = 1) -> None:
    """Record content ingestion from a source.

    Safe no-op when OTel is disabled.
    """
    if not _ensure_meter():
        return

    _ingestion_counter.add(count, {"source_type": source_type})


def reset_metrics() -> None:
    """Reset metrics state for testing."""
    global _meter, _llm_request_counter, _llm_token_counter
    global _llm_duration_histogram, _ingestion_counter
    _meter = None
    _llm_request_counter = None
    _llm_token_counter = None
    _llm_duration_histogram = None
    _ingestion_counter = None
