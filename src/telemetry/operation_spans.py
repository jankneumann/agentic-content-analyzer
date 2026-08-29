"""Backend-neutral helpers for operation stage spans and LLM generations."""

from __future__ import annotations

from collections.abc import Generator, Mapping
from contextlib import contextmanager
from typing import Any, Protocol

from src.contracts.operation_context import OperationContext, OperationStage
from src.telemetry.safety import TelemetryMasker, safe_span_attributes


class SpanProvider(Protocol):
    def start_span(self, name: str, attributes: dict[str, Any] | None = None) -> Any: ...


@contextmanager
def operation_span(
    provider: SpanProvider,
    name: str,
    *,
    context: OperationContext,
    stage: OperationStage | str | None = None,
    attributes: Mapping[str, Any] | None = None,
    masker: TelemetryMasker | None = None,
) -> Generator[Any, None, None]:
    """Start a masked stage span carrying the stable attempt correlation metadata."""
    effective_masker = masker or TelemetryMasker.from_environment()
    selected_stage = stage or context.stage
    base: dict[str, Any] = {
        "operation.id": context.operation_id,
        "operation.root_id": context.root_operation_id,
        "operation.parent_id": context.parent_operation_id,
        "operation.claim_generation": context.claim_generation,
        "operation.attempt_number": context.attempt_number,
        "operation.stage": str(selected_stage) if selected_stage is not None else None,
        "service.name": context.service_name,
        "service.instance.id": context.service_instance_id,
        "deployment.environment": context.environment,
        "service.version": context.release_revision,
        "resource.kind": context.resource_kind,
        "resource.key": context.resource_key,
    }
    if attributes:
        base.update(attributes)
    safe_attributes = safe_span_attributes(base, masker=effective_masker)
    with provider.start_span(name, safe_attributes) as span:
        yield span


def generation_metadata(
    *,
    model: str,
    provider: str,
    input_tokens: int,
    output_tokens: int,
    duration_ms: float,
    cost_usd: float | None = None,
    max_tokens: int | None = None,
    extra: Mapping[str, Any] | None = None,
    masker: TelemetryMasker | None = None,
) -> dict[str, Any]:
    """Build the controlled metadata shared by Langfuse and OTel generations."""
    metadata: dict[str, Any] = {
        "model": model,
        "provider": provider,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "duration_ms": duration_ms,
    }
    if cost_usd is not None:
        metadata["cost_usd"] = cost_usd
    if max_tokens is not None:
        metadata["max_tokens"] = max_tokens
    if extra:
        metadata.update(extra)
    return safe_span_attributes(
        metadata,
        masker=masker or TelemetryMasker.from_environment(),
    )


__all__ = ["generation_metadata", "operation_span"]
