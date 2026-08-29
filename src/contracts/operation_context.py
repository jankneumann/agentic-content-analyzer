"""Immutable, validated operation context and W3C propagation helpers.

The generated workflow model remains the canonical composite ingress validator.
This module adds the runtime concerns that do not belong in generated code:
immutability, process-local binding, and defensive W3C carrier handling.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pydantic import ConfigDict

from src.contracts.workflow_models import (
    OperationContextEnvelope,
    parse_operation_context_envelope,
)

_TRACEPARENT = re.compile(
    r"^00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$"
)
_TRACESTATE_KEY = re.compile(r"^[a-z0-9][a-z0-9_*/-]{0,255}$")


class OperationStage(StrEnum):
    """Frozen stage vocabulary from the operation observability contract."""

    SUBMIT = "submit"
    QUEUE_WAIT = "queue_wait"
    CLAIM = "claim"
    FETCH = "fetch"
    DISCOVER = "discover"
    METADATA = "metadata"
    TRANSCRIPT = "transcript"
    EXTRACT = "extract"
    PARSE = "parse"
    FILTER = "filter"
    DEDUPLICATE = "deduplicate"
    MODEL = "model"
    FALLBACK = "fallback"
    PERSIST = "persist"
    INDEX = "index"
    GRAPH = "graph"
    DELIVER = "deliver"
    BACKUP = "backup"
    RESTORE = "restore"
    ALERT = "alert"
    CLEANUP = "cleanup"
    FLUSH = "flush"


class OperationOutcome(StrEnum):
    """Frozen terminal/stage outcome vocabulary from the contract."""

    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    SKIPPED_POLICY = "skipped_policy"
    SKIPPED_DUPLICATE = "skipped_duplicate"
    FILTERED = "filtered"
    RETRYABLE_FAILURE = "retryable_failure"
    PERMANENT_FAILURE = "permanent_failure"
    CANCELLED = "cancelled"


class OperationContext(OperationContextEnvelope):
    """Immutable runtime form of the generated operation-context envelope."""

    model_config = ConfigDict(extra="forbid", frozen=True)


@dataclass(frozen=True, slots=True)
class W3CContext:
    """Validated fields extracted from an untrusted W3C carrier."""

    trace_id: str
    parent_span_id: str
    trace_flags: str
    tracestate: str | None

    @property
    def traceparent(self) -> str:
        return f"00-{self.trace_id}-{self.parent_span_id}-{self.trace_flags}"


_current_operation_context: ContextVar[OperationContext | None] = ContextVar(
    "operation_context",
    default=None,
)


def parse_operation_context(value: Any) -> OperationContext:
    """Run the mandatory generated semantic validator, then freeze the result."""
    if isinstance(value, OperationContext):
        return value
    generated = parse_operation_context_envelope(value)
    return OperationContext.model_validate(generated.model_dump(mode="python"))


def get_current_operation_context() -> OperationContext | None:
    """Return the operation context bound to this async/thread context, if any."""
    return _current_operation_context.get()


@contextmanager
def bind_operation_context(value: OperationContext | Mapping[str, Any]) -> Iterator[OperationContext]:
    """Bind a validated context and reliably restore an outer nested binding."""
    context = parse_operation_context(value)
    token = _current_operation_context.set(context)
    try:
        yield context
    finally:
        _current_operation_context.reset(token)


def inject_w3c_context(
    context: OperationContext,
    carrier: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return a copy of *carrier* containing the validated W3C propagation fields."""
    result = dict(carrier or {})
    result["traceparent"] = context.traceparent
    if context.tracestate is None:
        result.pop("tracestate", None)
    else:
        result["tracestate"] = context.tracestate
    return result


def extract_w3c_context(carrier: Mapping[str, Any]) -> W3CContext | None:
    """Defensively extract a supported W3C context, discarding malformed input.

    External carrier values are never reflected in errors or diagnostics.  Header
    names are matched case-insensitively because HTTP field names are case-insensitive.
    """
    lowered = {str(key).lower(): value for key, value in carrier.items()}
    traceparent = lowered.get("traceparent")
    if not isinstance(traceparent, str) or len(traceparent) != 55:
        return None
    match = _TRACEPARENT.fullmatch(traceparent)
    if match is None:
        return None
    trace_id, parent_span_id, trace_flags = match.groups()
    if trace_id == "0" * 32 or parent_span_id == "0" * 16:
        return None

    tracestate_value = lowered.get("tracestate")
    if tracestate_value is not None:
        if not isinstance(tracestate_value, str) or not _is_valid_tracestate(tracestate_value):
            return None

    return W3CContext(
        trace_id=trace_id,
        parent_span_id=parent_span_id,
        trace_flags=trace_flags,
        tracestate=tracestate_value,
    )


def _is_valid_tracestate(value: str) -> bool:
    """Validate the frozen, bounded W3C simple-key tracestate subset."""
    if not 1 <= len(value) <= 512:
        return False
    members = value.split(",")
    if not 1 <= len(members) <= 32:
        return False

    keys: set[str] = set()
    for member in members:
        if "=" not in member:
            return False
        key, member_value = member.split("=", 1)
        if _TRACESTATE_KEY.fullmatch(key) is None or key in keys:
            return False
        if not 1 <= len(member_value) <= 256:
            return False
        if any(not 0x21 <= ord(char) <= 0x7E or char in ",=" for char in member_value):
            return False
        keys.add(key)
    return True


__all__ = [
    "OperationContext",
    "OperationOutcome",
    "OperationStage",
    "W3CContext",
    "bind_operation_context",
    "extract_w3c_context",
    "get_current_operation_context",
    "inject_w3c_context",
    "parse_operation_context",
]
