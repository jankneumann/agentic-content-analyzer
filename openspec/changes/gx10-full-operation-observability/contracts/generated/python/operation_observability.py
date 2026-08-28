"""Generated contract stub. Do not import from production code until regenerated."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

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
    schema_version: Literal[1] = 1
    operation_id: str = Field(pattern=r"^[1-9][0-9]*$", max_length=19)
    root_operation_id: str = Field(pattern=r"^[1-9][0-9]*$", max_length=19)
    parent_operation_id: str | None = Field(None, pattern=r"^[1-9][0-9]*$", max_length=19)
    traceparent: str = Field(min_length=55, max_length=512)
    tracestate: str | None = Field(None, max_length=512)
    trace_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    span_id: str = Field(pattern=r"^[0-9a-f]{16}$")
    claim_generation: int = Field(ge=0, le=2147483647)
    attempt_number: int = Field(ge=0, le=2147483647)
    entrypoint: str = Field(min_length=1, max_length=160)
    service_name: str = Field(min_length=1, max_length=100)
    service_instance_id: str = Field(min_length=1, max_length=128)
    environment: str = Field(min_length=1, max_length=32)
    release_revision: str = Field(min_length=1, max_length=64)
    stage: OperationStage | None = None
    resource_kind: str | None = Field(None, max_length=64)
    resource_key: str | None = Field(None, max_length=128)


class OperationAttemptSummary(StrictModel):
    claim_generation: int = Field(ge=0)
    attempt_number: int = Field(ge=0)
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
