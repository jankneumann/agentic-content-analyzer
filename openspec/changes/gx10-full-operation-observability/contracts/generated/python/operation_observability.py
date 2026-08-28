"""Generated review stub for the proposed observability contract."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OperationStage(StrEnum):
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
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    SKIPPED_POLICY = "skipped_policy"
    SKIPPED_DUPLICATE = "skipped_duplicate"
    FILTERED = "filtered"
    RETRYABLE_FAILURE = "retryable_failure"
    PERMANENT_FAILURE = "permanent_failure"
    CANCELLED = "cancelled"


class TelemetryDeliveryState(StrEnum):
    PENDING = "pending"
    DELIVERED = "delivered"
    DEGRADED = "degraded"
    DROPPED = "dropped"
    DISABLED = "disabled"


class OperationContextEnvelope(StrictModel):
    schema_version: Literal[1]
    operation_id: str = Field(pattern=r"^[1-9][0-9]*$", max_length=19)
    root_operation_id: str = Field(pattern=r"^[1-9][0-9]*$", max_length=19)
    parent_operation_id: str | None = Field(pattern=r"^[1-9][0-9]*$", max_length=19)
    traceparent: str = Field(min_length=55, max_length=512)
    tracestate: str | None = Field(max_length=512)
    trace_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    span_id: str = Field(pattern=r"^[0-9a-f]{16}$")
    claim_generation: int = Field(ge=0, le=9_223_372_036_854_775_807)
    attempt_number: int | None = Field(ge=0, le=9_223_372_036_854_775_807)
    entrypoint: str = Field(min_length=1, max_length=160)
    service_name: str = Field(min_length=1, max_length=100)
    service_instance_id: str = Field(min_length=1, max_length=128)
    environment: str = Field(min_length=1, max_length=32)
    release_revision: str = Field(min_length=1, max_length=64)
    stage: OperationStage | None
    resource_kind: str | None = Field(max_length=64)
    resource_key: str | None = Field(max_length=128)


class OperationAttemptSummary(StrictModel):
    claim_generation: int = Field(ge=0)
    attempt_number: int = Field(ge=1)
    trace_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    root_span_id: str = Field(pattern=r"^[0-9a-f]{16}$")
    langfuse_observation_id: str | None = Field(None, max_length=64)
    service_name: str = Field(max_length=100)
    service_instance_id: str = Field(max_length=128)
    environment: str = Field(max_length=32)
    release_revision: str = Field(max_length=64)
    started_at: datetime
    completed_at: datetime | None = None
    terminal_stage: OperationStage | None = None
    outcome: OperationOutcome | None = None
    retryable: bool | None = None
    telemetry_delivery_state: TelemetryDeliveryState
    diagnostic_codes: list[str] = Field(max_length=20)
    diagnostics_omitted: int = Field(ge=0)


class OperationObservabilitySummary(StrictModel):
    root_operation_id: str = Field(pattern=r"^[1-9][0-9]*$", max_length=19)
    trace_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    attempt_count: int = Field(ge=0)
    latest_attempt: OperationAttemptSummary | None = None
    telemetry_delivery_state: TelemetryDeliveryState
    langfuse_url: str | None = Field(None, max_length=2048)


class OperationObservabilityExtension(BaseModel):
    model_config = ConfigDict(extra="allow")
    observability: OperationObservabilitySummary | None = None


class OperationAttemptPage(StrictModel):
    schema_version: Literal[1]
    operation_id: str = Field(pattern=r"^[1-9][0-9]*$", max_length=19)
    root_operation_id: str = Field(pattern=r"^[1-9][0-9]*$", max_length=19)
    attempts: list[OperationAttemptSummary] = Field(max_length=100)
    attempts_omitted: int = Field(ge=0)
    next_after_claim_generation: int | None = Field(ge=0)


class ProcessObservabilityHealth(StrictModel):
    schema_version: Literal[1]
    required: bool
    initialized: bool
    status: Literal["healthy", "degraded", "disabled", "stale"]
    service_name: str = Field(max_length=100)
    service_instance_id: str = Field(max_length=128)
    environment: str = Field(max_length=32)
    release_revision: str = Field(max_length=64)
    export_target: Literal["local_langfuse", "remote_langfuse", "other_otlp", "none"]
    last_heartbeat_at: datetime
    last_success_at: datetime | None
    last_success_age_seconds: int | None = Field(ge=0)
    last_error_at: datetime | None
    last_error_age_seconds: int | None = Field(ge=0)
    last_error_code: str | None = Field(None, max_length=100)
    buffered_count: int = Field(ge=0)
    buffer_capacity: int = Field(ge=1)
    dropped_count: int = Field(ge=0)
    last_flush_at: datetime | None = None
    last_flush_succeeded: bool | None = None


class ObservabilityHealthPage(StrictModel):
    schema_version: Literal[1]
    status: Literal["healthy", "degraded"]
    generated_at: datetime
    stale_after_seconds: int = Field(ge=1)
    processes: list[ProcessObservabilityHealth] = Field(max_length=1000)


class Problem(BaseModel):
    model_config = ConfigDict(extra="allow")
    title: str = Field(max_length=200)
    status: int = Field(ge=400, le=599)
    code: str | None = Field(None, max_length=100)
    detail: Any | None = None
