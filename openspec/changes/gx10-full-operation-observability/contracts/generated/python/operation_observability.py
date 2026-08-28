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
    operation_id: str = Field(pattern=r"^([1-9][0-9]{0,17}|[1-8][0-9]{18}|9[01][0-9]{17}|92[01][0-9]{16}|922[0-2][0-9]{15}|9223[0-2][0-9]{14}|92233[0-6][0-9]{13}|922337[0-1][0-9]{12}|92233720[0-2][0-9]{10}|922337203[0-5][0-9]{9}|9223372036[0-7][0-9]{8}|92233720368[0-4][0-9]{7}|922337203685[0-3][0-9]{6}|9223372036854[0-6][0-9]{5}|92233720368547[0-6][0-9]{4}|922337203685477[0-4][0-9]{3}|9223372036854775[0-7][0-9]{2}|922337203685477580[0-7])$", max_length=19)
    root_operation_id: str = Field(pattern=r"^([1-9][0-9]{0,17}|[1-8][0-9]{18}|9[01][0-9]{17}|92[01][0-9]{16}|922[0-2][0-9]{15}|9223[0-2][0-9]{14}|92233[0-6][0-9]{13}|922337[0-1][0-9]{12}|92233720[0-2][0-9]{10}|922337203[0-5][0-9]{9}|9223372036[0-7][0-9]{8}|92233720368[0-4][0-9]{7}|922337203685[0-3][0-9]{6}|9223372036854[0-6][0-9]{5}|92233720368547[0-6][0-9]{4}|922337203685477[0-4][0-9]{3}|9223372036854775[0-7][0-9]{2}|922337203685477580[0-7])$", max_length=19)
    parent_operation_id: str | None = Field(pattern=r"^([1-9][0-9]{0,17}|[1-8][0-9]{18}|9[01][0-9]{17}|92[01][0-9]{16}|922[0-2][0-9]{15}|9223[0-2][0-9]{14}|92233[0-6][0-9]{13}|922337[0-1][0-9]{12}|92233720[0-2][0-9]{10}|922337203[0-5][0-9]{9}|9223372036[0-7][0-9]{8}|92233720368[0-4][0-9]{7}|922337203685[0-3][0-9]{6}|9223372036854[0-6][0-9]{5}|92233720368547[0-6][0-9]{4}|922337203685477[0-4][0-9]{3}|9223372036854775[0-7][0-9]{2}|922337203685477580[0-7])$", max_length=19)
    traceparent: str = Field(min_length=55, max_length=512)
    tracestate: str | None = Field(max_length=512)
    trace_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    span_id: str = Field(pattern=r"^[0-9a-f]{16}$")
    claim_generation: str = Field(pattern=r"^(0|[1-9][0-9]{0,17}|[1-8][0-9]{18}|9[01][0-9]{17}|92[01][0-9]{16}|922[0-2][0-9]{15}|9223[0-2][0-9]{14}|92233[0-6][0-9]{13}|922337[0-1][0-9]{12}|92233720[0-2][0-9]{10}|922337203[0-5][0-9]{9}|9223372036[0-7][0-9]{8}|92233720368[0-4][0-9]{7}|922337203685[0-3][0-9]{6}|9223372036854[0-6][0-9]{5}|92233720368547[0-6][0-9]{4}|922337203685477[0-4][0-9]{3}|9223372036854775[0-7][0-9]{2}|922337203685477580[0-6])$", max_length=19)
    attempt_number: str | None = Field(pattern=r"^([1-9][0-9]{0,17}|[1-8][0-9]{18}|9[01][0-9]{17}|92[01][0-9]{16}|922[0-2][0-9]{15}|9223[0-2][0-9]{14}|92233[0-6][0-9]{13}|922337[0-1][0-9]{12}|92233720[0-2][0-9]{10}|922337203[0-5][0-9]{9}|9223372036[0-7][0-9]{8}|92233720368[0-4][0-9]{7}|922337203685[0-3][0-9]{6}|9223372036854[0-6][0-9]{5}|92233720368547[0-6][0-9]{4}|922337203685477[0-4][0-9]{3}|9223372036854775[0-7][0-9]{2}|922337203685477580[0-7])$", max_length=19)
    entrypoint: str = Field(min_length=1, max_length=160)
    service_name: str = Field(min_length=1, max_length=100)
    service_instance_id: str = Field(min_length=1, max_length=128)
    environment: str = Field(min_length=1, max_length=32)
    release_revision: str = Field(min_length=1, max_length=64)
    stage: OperationStage | None
    resource_kind: str | None = Field(max_length=64)
    resource_key: str | None = Field(max_length=128)


class OperationAttemptSummary(StrictModel):
    claim_generation: str = Field(pattern=r"^(0|[1-9][0-9]{0,17}|[1-8][0-9]{18}|9[01][0-9]{17}|92[01][0-9]{16}|922[0-2][0-9]{15}|9223[0-2][0-9]{14}|92233[0-6][0-9]{13}|922337[0-1][0-9]{12}|92233720[0-2][0-9]{10}|922337203[0-5][0-9]{9}|9223372036[0-7][0-9]{8}|92233720368[0-4][0-9]{7}|922337203685[0-3][0-9]{6}|9223372036854[0-6][0-9]{5}|92233720368547[0-6][0-9]{4}|922337203685477[0-4][0-9]{3}|9223372036854775[0-7][0-9]{2}|922337203685477580[0-6])$", max_length=19)
    attempt_number: str = Field(pattern=r"^([1-9][0-9]{0,17}|[1-8][0-9]{18}|9[01][0-9]{17}|92[01][0-9]{16}|922[0-2][0-9]{15}|9223[0-2][0-9]{14}|92233[0-6][0-9]{13}|922337[0-1][0-9]{12}|92233720[0-2][0-9]{10}|922337203[0-5][0-9]{9}|9223372036[0-7][0-9]{8}|92233720368[0-4][0-9]{7}|922337203685[0-3][0-9]{6}|9223372036854[0-6][0-9]{5}|92233720368547[0-6][0-9]{4}|922337203685477[0-4][0-9]{3}|9223372036854775[0-7][0-9]{2}|922337203685477580[0-7])$", max_length=19)
    trace_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    root_span_id: str | None = Field(pattern=r"^[0-9a-f]{16}$")
    langfuse_observation_id: str | None = Field(max_length=64)
    service_name: str = Field(max_length=100)
    service_instance_id: str = Field(max_length=128)
    environment: str = Field(max_length=32)
    release_revision: str = Field(max_length=64)
    started_at: datetime
    completed_at: datetime | None
    terminal_stage: OperationStage | None
    outcome: OperationOutcome | None
    retryable: bool | None
    telemetry_delivery_state: TelemetryDeliveryState
    diagnostic_codes: list[str] = Field(max_length=20)
    diagnostics_omitted: int = Field(ge=0)


class OperationObservabilitySummary(StrictModel):
    root_operation_id: str = Field(pattern=r"^([1-9][0-9]{0,17}|[1-8][0-9]{18}|9[01][0-9]{17}|92[01][0-9]{16}|922[0-2][0-9]{15}|9223[0-2][0-9]{14}|92233[0-6][0-9]{13}|922337[0-1][0-9]{12}|92233720[0-2][0-9]{10}|922337203[0-5][0-9]{9}|9223372036[0-7][0-9]{8}|92233720368[0-4][0-9]{7}|922337203685[0-3][0-9]{6}|9223372036854[0-6][0-9]{5}|92233720368547[0-6][0-9]{4}|922337203685477[0-4][0-9]{3}|9223372036854775[0-7][0-9]{2}|922337203685477580[0-7])$", max_length=19)
    trace_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    attempt_count: int = Field(ge=0)
    latest_attempt: OperationAttemptSummary | None
    telemetry_delivery_state: TelemetryDeliveryState
    langfuse_url: str | None = Field(max_length=2048)


class OperationObservabilityExtension(BaseModel):
    model_config = ConfigDict(extra="allow")
    observability: OperationObservabilitySummary | None = None


class OperationAttemptPage(StrictModel):
    schema_version: Literal[1]
    operation_id: str = Field(pattern=r"^([1-9][0-9]{0,17}|[1-8][0-9]{18}|9[01][0-9]{17}|92[01][0-9]{16}|922[0-2][0-9]{15}|9223[0-2][0-9]{14}|92233[0-6][0-9]{13}|922337[0-1][0-9]{12}|92233720[0-2][0-9]{10}|922337203[0-5][0-9]{9}|9223372036[0-7][0-9]{8}|92233720368[0-4][0-9]{7}|922337203685[0-3][0-9]{6}|9223372036854[0-6][0-9]{5}|92233720368547[0-6][0-9]{4}|922337203685477[0-4][0-9]{3}|9223372036854775[0-7][0-9]{2}|922337203685477580[0-7])$", max_length=19)
    root_operation_id: str = Field(pattern=r"^[1-9][0-9]*$", max_length=19)
    attempts: list[OperationAttemptSummary] = Field(max_length=100)
    attempts_omitted: int = Field(ge=0)
    next_after_claim_generation: str | None = Field(pattern=r"^(0|[1-9][0-9]{0,18})$", max_length=19)


class ProcessObservabilityHealth(StrictModel):
    schema_version: Literal[1]
    required: bool
    initialized: bool
    status: Literal["healthy", "degraded", "disabled", "stale"]
    service_name: str = Field(max_length=100)
    service_instance_id: str = Field(max_length=128)
    environment: str = Field(max_length=32)
    release_revision: str = Field(max_length=64)
    lifecycle_kind: Literal["long_running", "short_lived"]
    expires_at: datetime
    export_target: Literal["local_langfuse", "remote_langfuse", "other_otlp", "none"]
    last_heartbeat_at: datetime
    last_success_at: datetime | None
    last_success_age_seconds: int | None = Field(ge=0)
    last_error_at: datetime | None
    last_error_age_seconds: int | None = Field(ge=0)
    last_error_code: str | None = Field(max_length=100)
    buffered_count: int = Field(ge=0)
    buffer_capacity: int = Field(ge=1)
    dropped_count: int = Field(ge=0)
    last_flush_at: datetime | None
    last_flush_succeeded: bool | None


class ObservabilityHealthPage(StrictModel):
    schema_version: Literal[1]
    status: Literal["healthy", "degraded"]
    generated_at: datetime
    stale_after_seconds: int = Field(ge=1)
    processes: list[ProcessObservabilityHealth] = Field(max_length=1000)
    processes_omitted: int = Field(ge=0)


class Problem(BaseModel):
    model_config = ConfigDict(extra="allow")
    title: str = Field(max_length=200)
    status: int = Field(ge=400, le=599)
    code: str | None = Field(None, max_length=100)
    detail: Any | None = None

class OwnershipDryRun(StrictModel):
    target_environment: str = Field(min_length=1, max_length=32)
    allowed: bool
    next_epoch: str | None = Field(pattern=r"^(0|[1-9][0-9]{0,18})$", max_length=19)
    checks: list[str] = Field(max_length=20)


class EnvironmentOwnershipStatus(StrictModel):
    schema_version: Literal[1]
    configured_environment: str = Field(min_length=1, max_length=32)
    active_environment: str = Field(min_length=1, max_length=32)
    mode: Literal["active", "passive", "conflict"]
    authority_matches: bool
    authority_fingerprint_prefix: str = Field(pattern=r"^[0-9a-f]{12}$")
    epoch: str = Field(pattern=r"^(0|[1-9][0-9]{0,18})$", max_length=19)
    passive_reasons: list[str] = Field(max_length=20)
    dry_run: OwnershipDryRun | None
