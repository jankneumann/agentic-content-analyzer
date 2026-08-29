"""Generated review stub for the proposed observability contract."""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator, model_validator

TRACEPARENT_PATTERN = re.compile(r"^00-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$")
TRACESTATE_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_*/-]{0,255}$")


def _is_valid_tracestate(value: str) -> bool:
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
        if TRACESTATE_KEY_PATTERN.fullmatch(key) is None or key in keys:
            return False
        if not 1 <= len(member_value) <= 256:
            return False
        if any(not 0x21 <= ord(char) <= 0x7E or char in ",=" for char in member_value):
            return False
        keys.add(key)
    return True


def _reject_zero_identifier(value: str) -> str:
    if not value.strip("0"):
        raise ValueError("W3C trace and span identifiers must be non-zero")
    return value


OperationIdString = Annotated[
    str,
    Field(
        pattern=r"^([1-9][0-9]{0,17}|[1-8][0-9]{18}|9[01][0-9]{17}|92[01][0-9]{16}|922[0-2][0-9]{15}|9223[0-2][0-9]{14}|92233[0-6][0-9]{13}|922337[0-1][0-9]{12}|92233720[0-2][0-9]{10}|922337203[0-5][0-9]{9}|9223372036[0-7][0-9]{8}|92233720368[0-4][0-9]{7}|922337203685[0-3][0-9]{6}|9223372036854[0-6][0-9]{5}|92233720368547[0-6][0-9]{4}|922337203685477[0-4][0-9]{3}|9223372036854775[0-7][0-9]{2}|922337203685477580[0-7])$",
        max_length=19,
    ),
]
PositiveInt64String = OperationIdString
ClaimGenerationString = Annotated[
    str,
    Field(
        pattern=r"^(0|[1-9][0-9]{0,17}|[1-8][0-9]{18}|9[01][0-9]{17}|92[01][0-9]{16}|922[0-2][0-9]{15}|9223[0-2][0-9]{14}|92233[0-6][0-9]{13}|922337[0-1][0-9]{12}|92233720[0-2][0-9]{10}|922337203[0-5][0-9]{9}|9223372036[0-7][0-9]{8}|92233720368[0-4][0-9]{7}|922337203685[0-3][0-9]{6}|9223372036854[0-6][0-9]{5}|92233720368547[0-6][0-9]{4}|922337203685477[0-4][0-9]{3}|9223372036854775[0-7][0-9]{2}|922337203685477580[0-6])$",
        max_length=19,
    ),
]
NonNegativeInt64String = Annotated[
    str,
    Field(
        pattern=r"^(0|[1-9][0-9]{0,17}|[1-8][0-9]{18}|9[01][0-9]{17}|92[01][0-9]{16}|922[0-2][0-9]{15}|9223[0-2][0-9]{14}|92233[0-6][0-9]{13}|922337[0-1][0-9]{12}|92233720[0-2][0-9]{10}|922337203[0-5][0-9]{9}|9223372036[0-7][0-9]{8}|92233720368[0-4][0-9]{7}|922337203685[0-3][0-9]{6}|9223372036854[0-6][0-9]{5}|92233720368547[0-6][0-9]{4}|922337203685477[0-4][0-9]{3}|9223372036854775[0-7][0-9]{2}|922337203685477580[0-7])$",
        max_length=19,
    ),
]
TraceIdString = Annotated[
    str, Field(pattern=r"^[0-9a-f]{32}$"), AfterValidator(_reject_zero_identifier)
]
SpanIdString = Annotated[
    str, Field(pattern=r"^[0-9a-f]{16}$"), AfterValidator(_reject_zero_identifier)
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("schema_version", mode="before", check_fields=False)
    @classmethod
    def validate_exact_schema_version(cls, value: Any) -> Any:
        # JSON Schema numeric semantics treat lexical 1 and 1.0 as the same
        # integer value; bool and string aliases remain invalid.
        if isinstance(value, bool) or type(value) not in (int, float) or value != 1:
            raise ValueError("schema_version must be the JSON number 1")
        return 1


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
    operation_id: OperationIdString
    root_operation_id: OperationIdString
    parent_operation_id: OperationIdString | None
    traceparent: str = Field(
        pattern=r"^00-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$", min_length=55, max_length=55
    )
    tracestate: str | None = Field(max_length=512)
    trace_id: TraceIdString
    span_id: SpanIdString
    claim_generation: ClaimGenerationString
    attempt_number: PositiveInt64String | None
    entrypoint: str = Field(min_length=1, max_length=160)
    service_name: str = Field(min_length=1, max_length=100)
    service_instance_id: str = Field(min_length=1, max_length=128)
    environment: str = Field(min_length=1, max_length=32)
    release_revision: str = Field(min_length=1, max_length=64)
    authority_fingerprint: Annotated[str | None, Field(pattern=r"^[0-9a-f]{64}$", max_length=64)]
    ownership_epoch: NonNegativeInt64String | None
    stage: OperationStage | None
    resource_kind: str | None = Field(max_length=64)
    resource_key: str | None = Field(max_length=128)

    @model_validator(mode="after")
    def validate_semantic_context(self) -> OperationContextEnvelope:
        match = TRACEPARENT_PATTERN.fullmatch(self.traceparent)
        if match is None:
            raise ValueError("traceparent must be canonical W3C version 00")
        _, carrier_trace_id, carrier_parent_id, _ = self.traceparent.split("-")
        if carrier_trace_id != self.trace_id or carrier_parent_id != self.span_id:
            raise ValueError("traceparent identifiers must match trace_id and span_id")
        if self.tracestate is not None and not _is_valid_tracestate(self.tracestate):
            raise ValueError("tracestate must use the bounded W3C simple-key subset")
        if (
            self.attempt_number is not None
            and int(self.attempt_number) != int(self.claim_generation) + 1
        ):
            raise ValueError("attempt_number must equal claim_generation + 1")
        return self


class OperationAttemptSummary(StrictModel):
    claim_generation: ClaimGenerationString
    attempt_number: PositiveInt64String
    trace_id: TraceIdString
    root_span_id: SpanIdString | None
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

    @model_validator(mode="after")
    def validate_attempt_number(self) -> OperationAttemptSummary:
        if int(self.attempt_number) != int(self.claim_generation) + 1:
            raise ValueError("attempt_number must equal claim_generation + 1")
        return self


class OperationObservabilitySummary(StrictModel):
    root_operation_id: OperationIdString
    trace_id: TraceIdString
    attempt_count: int = Field(ge=0)
    latest_attempt: OperationAttemptSummary | None
    telemetry_delivery_state: TelemetryDeliveryState
    langfuse_url: str | None = Field(max_length=2048)


class OperationObservabilityExtension(BaseModel):
    model_config = ConfigDict(extra="allow")
    observability: OperationObservabilitySummary | None = None


class OperationAttemptPage(StrictModel):
    schema_version: Literal[1]
    operation_id: OperationIdString
    root_operation_id: OperationIdString
    attempts: list[OperationAttemptSummary] = Field(max_length=100)
    attempts_omitted: int = Field(ge=0)
    next_after_claim_generation: ClaimGenerationString | None


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
    next_epoch: NonNegativeInt64String | None
    checks: list[str] = Field(max_length=20)


class EnvironmentOwnershipStatus(StrictModel):
    schema_version: Literal[1]
    configured_environment: str = Field(min_length=1, max_length=32)
    active_environment: str = Field(min_length=1, max_length=32)
    mode: Literal["active", "passive", "conflict"]
    authority_matches: bool
    authority_fingerprint_prefix: str = Field(pattern=r"^[0-9a-f]{12}$")
    epoch: NonNegativeInt64String
    passive_reasons: list[str] = Field(max_length=20)
    dry_run: OwnershipDryRun | None
