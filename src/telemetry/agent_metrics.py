"""OpenTelemetry metrics and tracing for the agentic analysis system.

Provides:
- Metrics: agent task counts, durations, token usage, specialist invocations
- Tracing: spans for conductor lifecycle, specialist execution, memory operations

Follows the same lazy-init + safe no-op pattern as src/telemetry/metrics.py.
When OTel is disabled, all functions are safe no-ops.

Covers OpenSpec task 8.3.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from src.utils.logging import get_logger

logger = get_logger(__name__)

# Module-level meter instruments (lazy-initialized)
_meter: Any = None
_agent_task_counter: Any = None
_agent_task_duration: Any = None
_agent_token_counter: Any = None
_agent_cost_counter: Any = None
_specialist_invocation_counter: Any = None
_specialist_duration: Any = None
_memory_operation_counter: Any = None
_approval_check_counter: Any = None

# Module-level tracer (lazy-initialized)
_tracer: Any = None


def _ensure_meter() -> bool:
    """Initialize the OTel meter for agent metrics if not already done."""
    global _meter, _agent_task_counter, _agent_task_duration
    global _agent_token_counter, _agent_cost_counter
    global _specialist_invocation_counter, _specialist_duration
    global _memory_operation_counter, _approval_check_counter

    if _meter is not None:
        return True

    try:
        from src.config import settings

        if not settings.otel_enabled:
            return False

        from opentelemetry import metrics

        _meter = metrics.get_meter("newsletter-aggregator.agents")

        _agent_task_counter = _meter.create_counter(
            name="agent.tasks",
            description="Total agent tasks by status and type",
            unit="1",
        )

        _agent_task_duration = _meter.create_histogram(
            name="agent.task.duration",
            description="Agent task execution duration",
            unit="ms",
        )

        _agent_token_counter = _meter.create_counter(
            name="agent.tokens",
            description="Total tokens consumed by agent tasks",
            unit="tokens",
        )

        _agent_cost_counter = _meter.create_counter(
            name="agent.cost",
            description="Estimated cost of agent task execution",
            unit="USD",
        )

        _specialist_invocation_counter = _meter.create_counter(
            name="agent.specialist.invocations",
            description="Specialist invocations by name and outcome",
            unit="1",
        )

        _specialist_duration = _meter.create_histogram(
            name="agent.specialist.duration",
            description="Specialist execution duration",
            unit="ms",
        )

        _memory_operation_counter = _meter.create_counter(
            name="agent.memory.operations",
            description="Memory operations by type (store, recall, forget)",
            unit="1",
        )

        _approval_check_counter = _meter.create_counter(
            name="agent.approval.checks",
            description="Approval gate checks by action and result",
            unit="1",
        )

        logger.info("Agent OTel metrics instruments initialized")
        return True
    except ImportError:
        logger.debug("OTel metrics not available (opentelemetry not installed)")
        return False
    except Exception as e:
        logger.debug("Agent OTel metrics initialization failed: %s", e)
        return False


def _ensure_tracer() -> bool:
    """Initialize the OTel tracer for agent spans."""
    global _tracer

    if _tracer is not None:
        return True

    try:
        from src.config import settings

        if not settings.otel_enabled:
            return False

        from opentelemetry import trace

        _tracer = trace.get_tracer("newsletter-aggregator.agents")
        return True
    except ImportError:
        return False
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Metrics recording functions
# ---------------------------------------------------------------------------


def record_agent_task(
    *,
    task_type: str,
    status: str,
    persona: str,
    source: str,
    duration_ms: float,
    tokens: int = 0,
    cost: float = 0.0,
) -> None:
    """Record an agent task completion with all relevant dimensions."""
    if not _ensure_meter():
        return

    attributes = {
        "task_type": task_type,
        "status": status,
        "persona": persona,
        "source": source,
    }

    _agent_task_counter.add(1, attributes)
    _agent_task_duration.record(duration_ms, attributes)

    if tokens > 0:
        _agent_token_counter.add(tokens, {"persona": persona, "task_type": task_type})

    if cost > 0:
        _agent_cost_counter.add(cost, {"persona": persona, "task_type": task_type})


def record_specialist_invocation(
    *,
    specialist: str,
    success: bool,
    duration_ms: float,
    retries: int = 0,
) -> None:
    """Record a specialist agent invocation."""
    if not _ensure_meter():
        return

    attributes = {
        "specialist": specialist,
        "success": str(success),
        "retries": str(retries),
    }

    _specialist_invocation_counter.add(1, attributes)
    _specialist_duration.record(duration_ms, attributes)


def record_memory_operation(*, operation: str, strategy: str = "", success: bool = True) -> None:
    """Record a memory store/recall/forget operation."""
    if not _ensure_meter():
        return

    _memory_operation_counter.add(
        1,
        {"operation": operation, "strategy": strategy, "success": str(success)},
    )


def record_approval_check(*, action: str, risk_level: str, approved: bool) -> None:
    """Record an approval gate check."""
    if not _ensure_meter():
        return

    _approval_check_counter.add(
        1,
        {"action": action, "risk_level": risk_level, "approved": str(approved)},
    )


# ---------------------------------------------------------------------------
# Tracing context managers
# ---------------------------------------------------------------------------


@contextmanager
def trace_agent_task(
    task_id: str, task_type: str, persona: str, source: str
) -> Generator[Any, None, None]:
    """Create a span for the full agent task lifecycle.

    Usage::

        with trace_agent_task(task_id, task_type, persona, source) as span:
            result = await conductor.execute_task(...)
            span.set_attribute("agent.task.status", result.status)
    """
    if not _ensure_tracer():
        yield _NoopSpan()
        return

    with _tracer.start_as_current_span(
        "agent.task",
        attributes={
            "agent.task.id": task_id,
            "agent.task.type": task_type,
            "agent.task.persona": persona,
            "agent.task.source": source,
        },
    ) as span:
        yield span


@contextmanager
def trace_specialist(specialist_name: str, task_id: str) -> Generator[Any, None, None]:
    """Create a span for a specialist invocation."""
    if not _ensure_tracer():
        yield _NoopSpan()
        return

    with _tracer.start_as_current_span(
        f"agent.specialist.{specialist_name}",
        attributes={
            "agent.specialist.name": specialist_name,
            "agent.task.id": task_id,
        },
    ) as span:
        yield span


@contextmanager
def trace_memory_operation(operation: str) -> Generator[Any, None, None]:
    """Create a span for a memory operation (recall, store, forget)."""
    if not _ensure_tracer():
        yield _NoopSpan()
        return

    with _tracer.start_as_current_span(
        f"agent.memory.{operation}",
        attributes={"agent.memory.operation": operation},
    ) as span:
        yield span


@contextmanager
def trace_approval_check(action: str) -> Generator[Any, None, None]:
    """Create a span for an approval gate check."""
    if not _ensure_tracer():
        yield _NoopSpan()
        return

    with _tracer.start_as_current_span(
        "agent.approval.check",
        attributes={"agent.approval.action": action},
    ) as span:
        yield span


class _NoopSpan:
    """No-op span for when OTel is disabled."""

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def set_status(self, *args: Any, **kwargs: Any) -> None:
        pass

    def record_exception(self, exception: Exception) -> None:
        pass


# ---------------------------------------------------------------------------
# Reset for testing
# ---------------------------------------------------------------------------


def reset_agent_metrics() -> None:
    """Reset agent metrics state for testing."""
    global _meter, _agent_task_counter, _agent_task_duration
    global _agent_token_counter, _agent_cost_counter
    global _specialist_invocation_counter, _specialist_duration
    global _memory_operation_counter, _approval_check_counter
    global _tracer
    _meter = None
    _agent_task_counter = None
    _agent_task_duration = None
    _agent_token_counter = None
    _agent_cost_counter = None
    _specialist_invocation_counter = None
    _specialist_duration = None
    _memory_operation_counter = None
    _approval_check_counter = None
    _tracer = None
