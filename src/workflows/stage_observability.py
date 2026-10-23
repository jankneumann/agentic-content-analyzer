"""Bounded, provider-neutral stage evidence for domain operation coverage."""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from src.contracts.operation_context import (
    OperationOutcome,
    OperationStage,
    get_current_operation_context,
)
from src.telemetry import get_provider
from src.telemetry.operation_spans import operation_span
from src.telemetry.safety import (
    AttemptObservationBudget,
    TelemetryMasker,
    masked_exception_stack,
    safe_span_attributes,
)

_MAX_ERROR_CODE_LENGTH = 100
_budget_state: ContextVar[tuple[tuple[str, str, str], AttemptObservationBudget] | None] = (
    ContextVar("domain_attempt_observation_budget", default=None)
)


@dataclass(slots=True)
class StageError(Exception):
    """A classified failure crossing a nested domain-stage boundary."""

    stage: OperationStage
    error_code: str
    retryable: bool
    cause: BaseException

    def __post_init__(self) -> None:
        if not self.error_code or len(self.error_code) > _MAX_ERROR_CODE_LENGTH:
            raise ValueError("error_code must contain 1-100 characters")

    def __str__(self) -> str:
        return self.error_code


@dataclass(slots=True)
class StageObservation:
    """Mutable handle used to complete one already-started domain stage."""

    stage: OperationStage
    span: Any
    budget: AttemptObservationBudget | None
    masker: TelemetryMasker
    finished: bool = False

    def finish(
        self,
        outcome: OperationOutcome,
        *,
        error_code: str | None = None,
        retryable: bool | None = None,
        error: BaseException | None = None,
        attributes: Mapping[str, Any] | None = None,
    ) -> None:
        """Emit one bounded outcome event; failures use reserved attempt capacity."""
        if self.finished:
            return
        self.finished = True
        if error_code is not None and (not error_code or len(error_code) > _MAX_ERROR_CODE_LENGTH):
            raise ValueError("error_code must contain 1-100 characters")
        payload: dict[str, Any] = {
            "operation.stage": self.stage.value,
            "operation.outcome": outcome.value,
            "operation.error_code": error_code,
            "operation.retryable": retryable,
        }
        if attributes:
            payload.update(attributes)
        if error is not None:
            payload["exception.stacktrace"] = masked_exception_stack(
                error,
                masker=self.masker,
            )
        safe = safe_span_attributes(payload, masker=self.masker)
        payload_bytes = len(json.dumps(safe, ensure_ascii=False, default=str).encode("utf-8"))
        failure = outcome in {
            OperationOutcome.RETRYABLE_FAILURE,
            OperationOutcome.PERMANENT_FAILURE,
            OperationOutcome.PARTIAL,
            OperationOutcome.CANCELLED,
        }
        accepted = True
        if self.budget is not None:
            if failure:
                accepted = self.budget.record_reserved(
                    payload_bytes=payload_bytes,
                    kind="failure",
                )
            else:
                accepted = self.budget.record_success(
                    topology_bytes=min(payload_bytes, 512),
                    metadata_bytes=max(0, payload_bytes - 512),
                ).accepted
        if accepted:
            _annotate_span(self.span, safe)

    def fail(
        self,
        error: BaseException,
        *,
        error_code: str,
        retryable: bool,
    ) -> None:
        self.finish(
            OperationOutcome.RETRYABLE_FAILURE if retryable else OperationOutcome.PERMANENT_FAILURE,
            error_code=error_code,
            retryable=retryable,
            error=error,
        )


@contextmanager
def operation_stage(
    name: str,
    stage: OperationStage,
    *,
    attributes: Mapping[str, Any] | None = None,
) -> Iterator[StageObservation]:
    """Create a child stage when an attempt context is active, otherwise no-op safely."""
    context = get_current_operation_context()
    masker = TelemetryMasker.from_environment()
    if context is None:
        observation = StageObservation(stage, None, None, masker)
        try:
            yield observation
        except StageError as failure:
            observation.fail(
                failure.cause,
                error_code=failure.error_code,
                retryable=failure.retryable,
            )
            raise
        except Exception as error:
            observation.fail(
                error,
                error_code=f"{stage.value}_failed",
                retryable=True,
            )
            raise
        else:
            if not observation.finished:
                observation.finish(OperationOutcome.SUCCEEDED)
        return

    budget = _attempt_budget(context.trace_id, context.claim_generation, context.service_name)
    span_attributes: dict[str, Any] = {
        "operation.trace_id": context.trace_id,
        "operation.parent_span_id": context.span_id,
    }
    if attributes:
        span_attributes.update(attributes)
    with operation_span(
        get_provider(),
        name,
        context=context,
        stage=stage,
        attributes=span_attributes,
        masker=masker,
    ) as span:
        observation = StageObservation(stage, span, budget, masker)
        try:
            yield observation
        except StageError as failure:
            observation.fail(
                failure.cause,
                error_code=failure.error_code,
                retryable=failure.retryable,
            )
            raise
        except Exception as error:
            observation.fail(
                error,
                error_code=f"{stage.value}_failed",
                retryable=True,
            )
            raise
        else:
            if not observation.finished:
                observation.finish(OperationOutcome.SUCCEEDED)


def _attempt_budget(
    trace_id: str,
    claim_generation: str,
    service_name: str,
) -> AttemptObservationBudget:
    key = (trace_id, claim_generation, service_name)
    state = _budget_state.get()
    if state is None or state[0] != key:
        budget = AttemptObservationBudget()
        _budget_state.set((key, budget))
        return budget
    return state[1]


def _annotate_span(span: Any, attributes: Mapping[str, Any]) -> None:
    if span is None:
        return
    add_event = getattr(span, "add_event", None)
    if callable(add_event):
        add_event("operation.stage.outcome", attributes=dict(attributes))
        return
    update = getattr(span, "update", None)
    if callable(update):
        update(metadata=dict(attributes))
        return
    log = getattr(span, "log", None)
    if callable(log):
        log(metadata=dict(attributes))


__all__ = ["StageError", "StageObservation", "operation_stage"]
