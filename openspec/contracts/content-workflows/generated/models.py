"""Generated from contracts/openapi/v1.yaml; do not edit."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import (
    AfterValidator,
    AnyUrl,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

CONTRACT_SHA256 = "cf0dbd992a3617bd4887ea21e305e9cee0b7eb360f7f3f060fea4ce85a401c55"

TRACEPARENT_PATTERN = re.compile(r"^00-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$")
TRACESTATE_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_*/-]{0,255}$")


def _reject_zero_identifier(value: str) -> str:
    if not value.strip("0"):
        raise ValueError("W3C trace and span identifiers must be non-zero")
    return value


def _validate_schema_version_one(value: Any) -> int:
    if isinstance(value, bool) or type(value) not in (int, float) or value != 1:
        raise ValueError("schema_version must be the JSON number 1")
    return 1


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


OperationStatus = Literal["queued", "in_progress", "completed", "failed", "cancelled"]
OperationType = Literal[
    "ingestion.execute",
    "summarization.run",
    "theme_analysis.create",
    "digest.create",
    "pipeline.run",
    "podcast_script.create",
    "podcast_audio.create",
    "audio_digest.create",
]
IngestionOutcome = Literal["success", "zero_items", "partial", "failed", "cancelled", "unknown"]
IngestionStatus = Literal["ok", "partial", "error"]
TerminalOperationStatus = Literal["completed", "failed", "cancelled"]
ContentReconciliationMode = Literal["dry_run", "apply"]
ContentReconciliationProjection = Literal["proposed", "observed"]
ContentReconciliationContentStatus = Literal[
    "pending", "parsing", "parsed", "processing", "completed", "failed", "filtered_out"
]
ContentReconciliationOperationStatus = Literal[
    "queued", "in_progress", "completed", "failed", "cancelled"
]
ContentReconciliationPhase = Literal["parsing", "processing"]
ContentReconciliationAction = Literal[
    "none",
    "retry_operation",
    "project_completed",
    "project_parsed",
    "restore_parsed",
    "restore_pending",
    "cancel_restore_parsed",
    "cancel_restore_pending",
]
ContentReconciliationReason = Literal[
    "summary_exists",
    "extraction_completed",
    "completed_output_missing",
    "output_owner_mismatch",
    "active_operation",
    "cancellation_pending",
    "execution_locked",
    "cancellation_requested",
    "stale_operation",
    "failed_operation",
    "retry_budget_exhausted",
    "forced_reprocessing",
    "summarization_cancelled",
    "extraction_cancelled",
    "missing_operation",
    "ownership_conflict",
    "incompatible_worker",
    "revalidation_conflict",
    "apply_failed",
]
TraceId = Annotated[str, Field(pattern=r"^[0-9a-f]{32}$"), AfterValidator(_reject_zero_identifier)]
SpanId = Annotated[str, Field(pattern=r"^[0-9a-f]{16}$"), AfterValidator(_reject_zero_identifier)]
OperationId = Annotated[
    str,
    Field(
        max_length=19,
        pattern="^([1-9][0-9]{0,17}|[1-8][0-9]{18}|9[01][0-9]{17}|92[01][0-9]{16}|922[0-2][0-9]{15}|9223[0-2][0-9]{14}|92233[0-6][0-9]{13}|922337[0-1][0-9]{12}|92233720[0-2][0-9]{10}|922337203[0-5][0-9]{9}|9223372036[0-7][0-9]{8}|92233720368[0-4][0-9]{7}|922337203685[0-3][0-9]{6}|9223372036854[0-6][0-9]{5}|92233720368547[0-6][0-9]{4}|922337203685477[0-4][0-9]{3}|9223372036854775[0-7][0-9]{2}|922337203685477580[0-7])$",
    ),
]
Int64NonNegativeString = Annotated[
    str,
    Field(
        max_length=19,
        pattern="^(0|[1-9][0-9]{0,17}|[1-8][0-9]{18}|9[01][0-9]{17}|92[01][0-9]{16}|922[0-2][0-9]{15}|9223[0-2][0-9]{14}|92233[0-6][0-9]{13}|922337[0-1][0-9]{12}|92233720[0-2][0-9]{10}|922337203[0-5][0-9]{9}|9223372036[0-7][0-9]{8}|92233720368[0-4][0-9]{7}|922337203685[0-3][0-9]{6}|9223372036854[0-6][0-9]{5}|92233720368547[0-6][0-9]{4}|922337203685477[0-4][0-9]{3}|9223372036854775[0-7][0-9]{2}|922337203685477580[0-7])$",
    ),
]
ClaimGenerationString = Annotated[
    str,
    Field(
        max_length=19,
        pattern="^(0|[1-9][0-9]{0,17}|[1-8][0-9]{18}|9[01][0-9]{17}|92[01][0-9]{16}|922[0-2][0-9]{15}|9223[0-2][0-9]{14}|92233[0-6][0-9]{13}|922337[0-1][0-9]{12}|92233720[0-2][0-9]{10}|922337203[0-5][0-9]{9}|9223372036[0-7][0-9]{8}|92233720368[0-4][0-9]{7}|922337203685[0-3][0-9]{6}|9223372036854[0-6][0-9]{5}|92233720368547[0-6][0-9]{4}|922337203685477[0-4][0-9]{3}|9223372036854775[0-7][0-9]{2}|922337203685477580[0-6])$",
    ),
]
Int64PositiveString = Annotated[
    str,
    Field(
        max_length=19,
        pattern="^([1-9][0-9]{0,17}|[1-8][0-9]{18}|9[01][0-9]{17}|92[01][0-9]{16}|922[0-2][0-9]{15}|9223[0-2][0-9]{14}|92233[0-6][0-9]{13}|922337[0-1][0-9]{12}|92233720[0-2][0-9]{10}|922337203[0-5][0-9]{9}|9223372036[0-7][0-9]{8}|92233720368[0-4][0-9]{7}|922337203685[0-3][0-9]{6}|9223372036854[0-6][0-9]{5}|92233720368547[0-6][0-9]{4}|922337203685477[0-4][0-9]{3}|9223372036854775[0-7][0-9]{2}|922337203685477580[0-7])$",
    ),
]
OperationStage = Literal[
    "submit",
    "queue_wait",
    "claim",
    "fetch",
    "discover",
    "metadata",
    "transcript",
    "extract",
    "parse",
    "filter",
    "deduplicate",
    "model",
    "fallback",
    "persist",
    "index",
    "graph",
    "deliver",
    "backup",
    "restore",
    "alert",
    "cleanup",
    "flush",
]
OperationOutcome = Literal[
    "succeeded",
    "partial",
    "skipped_policy",
    "skipped_duplicate",
    "filtered",
    "retryable_failure",
    "permanent_failure",
    "cancelled",
]
TelemetryDeliveryState = Literal["pending", "delivered", "degraded", "dropped", "disabled"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExtensibleModel(BaseModel):
    model_config = ConfigDict(extra="allow")


COMMAND_FIELD_SCHEMAS: dict[str, dict[str, Any]] = {
    "gmail": {
        "properties": {
            "max_items": {"type": "integer", "minimum": 1},
            "days_back": {"type": "integer", "minimum": 0},
            "after_date": {"type": "string", "format": "date-time"},
            "force_reprocess": {"type": "boolean", "default": False},
            "kind": {"type": "string", "const": "gmail"},
            "query": {"type": "string"},
        },
        "required": ["kind"],
    },
    "rss": {
        "properties": {
            "kind": {"type": "string", "const": "rss"},
            "max_items": {"type": "integer", "minimum": 1},
            "days_back": {"type": "integer", "minimum": 0},
            "after_date": {"type": "string", "format": "date-time"},
            "force_reprocess": {"type": "boolean", "default": False},
        },
        "required": ["kind"],
    },
    "blog": {
        "properties": {
            "kind": {"type": "string", "const": "blog"},
            "max_items": {"type": "integer", "minimum": 1},
            "days_back": {"type": "integer", "minimum": 0},
            "after_date": {"type": "string", "format": "date-time"},
            "force_reprocess": {"type": "boolean", "default": False},
        },
        "required": ["kind"],
    },
    "substack": {
        "properties": {
            "kind": {"type": "string", "const": "substack"},
            "max_items": {"type": "integer", "minimum": 1},
            "days_back": {"type": "integer", "minimum": 0},
            "after_date": {"type": "string", "format": "date-time"},
            "force_reprocess": {"type": "boolean", "default": False},
        },
        "required": ["kind"],
    },
    "youtube_playlist": {
        "properties": {
            "kind": {"type": "string", "const": "youtube_playlist"},
            "max_items": {"type": "integer", "minimum": 1},
            "days_back": {"type": "integer", "minimum": 0},
            "after_date": {"type": "string", "format": "date-time"},
            "force_reprocess": {"type": "boolean", "default": False},
            "public_only": {"type": "boolean", "default": False},
        },
        "required": ["kind"],
    },
    "youtube_rss": {
        "properties": {
            "kind": {"type": "string", "const": "youtube_rss"},
            "max_items": {"type": "integer", "minimum": 1},
            "days_back": {"type": "integer", "minimum": 0},
            "after_date": {"type": "string", "format": "date-time"},
            "force_reprocess": {"type": "boolean", "default": False},
        },
        "required": ["kind"],
    },
    "podcast": {
        "properties": {
            "kind": {"type": "string", "const": "podcast"},
            "max_items": {"type": "integer", "minimum": 1},
            "days_back": {"type": "integer", "minimum": 0},
            "after_date": {"type": "string", "format": "date-time"},
            "force_reprocess": {"type": "boolean", "default": False},
            "transcribe": {"type": "boolean", "default": True},
        },
        "required": ["kind"],
    },
    "x_search": {
        "properties": {
            "kind": {"type": "string", "const": "x_search"},
            "prompt": {"type": "string"},
            "max_threads": {"type": "integer", "minimum": 1},
            "force_reprocess": {"type": "boolean", "default": False},
        },
        "required": ["kind"],
    },
    "perplexity_search": {
        "properties": {
            "kind": {"type": "string", "const": "perplexity_search"},
            "prompt": {"type": "string"},
            "max_items": {"type": "integer", "minimum": 1},
            "recency": {"type": "string", "enum": ["hour", "day", "week", "month"]},
            "context_size": {"type": "string", "enum": ["low", "medium", "high"]},
            "force_reprocess": {"type": "boolean", "default": False},
        },
        "required": ["kind"],
    },
    "files": {
        "properties": {
            "kind": {"type": "string", "const": "files"},
            "upload_ids": {"type": "array", "minItems": 1, "items": {"type": "string"}},
            "force_reprocess": {"type": "boolean", "default": False},
        },
        "required": ["kind", "upload_ids"],
    },
    "url": {
        "properties": {
            "kind": {"type": "string", "const": "url"},
            "url": {"type": "string", "format": "uri"},
            "title": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "notes": {"type": "string"},
            "routing_mode": {"type": "string", "enum": ["auto", "webpage"], "default": "auto"},
            "force_reprocess": {"type": "boolean", "default": False},
        },
        "required": ["kind", "url"],
    },
    "scholar_search": {
        "properties": {
            "kind": {"type": "string", "const": "scholar_search"},
            "max_items": {"type": "integer", "minimum": 1, "default": 20},
        },
        "required": ["kind"],
    },
    "scholar_paper": {
        "properties": {
            "kind": {"type": "string", "const": "scholar_paper"},
            "identifier": {"type": "string", "minLength": 1},
            "with_references": {"type": "boolean", "default": False},
        },
        "required": ["kind", "identifier"],
    },
    "scholar_references": {
        "properties": {
            "kind": {"type": "string", "const": "scholar_references"},
            "after": {"type": "string", "format": "date-time"},
            "before": {"type": "string", "format": "date-time"},
            "source_types": {"type": "array", "items": {"type": "string"}},
            "dry_run": {"type": "boolean", "default": False},
            "limit": {"type": "integer", "minimum": 1},
        },
        "required": ["kind"],
    },
    "arxiv_search": {
        "properties": {
            "kind": {"type": "string", "const": "arxiv_search"},
            "max_items": {"type": "integer", "minimum": 1, "default": 20},
            "days_back": {"type": "integer", "minimum": 0},
            "after_date": {"type": "string", "format": "date-time"},
            "force_reprocess": {"type": "boolean", "default": False},
            "extract_pdf": {"type": "boolean", "default": True},
        },
        "required": ["kind"],
    },
    "arxiv_paper": {
        "properties": {
            "kind": {"type": "string", "const": "arxiv_paper"},
            "identifier": {"type": "string", "minLength": 1},
            "extract_pdf": {"type": "boolean", "default": True},
            "force_reprocess": {"type": "boolean", "default": False},
        },
        "required": ["kind", "identifier"],
    },
    "huggingface_papers": {
        "properties": {
            "kind": {"type": "string", "const": "huggingface_papers"},
            "max_items": {"type": "integer", "minimum": 1, "default": 30},
            "days_back": {"type": "integer", "minimum": 0},
            "after_date": {"type": "string", "format": "date-time"},
            "force_reprocess": {"type": "boolean", "default": False},
        },
        "required": ["kind"],
    },
    "readwise": {
        "properties": {
            "kind": {"type": "string", "const": "readwise"},
            "updated_after": {"type": "string", "format": "date-time"},
            "source_types": {"type": "array", "items": {"type": "string"}},
            "include_deleted": {"type": "boolean", "default": False},
            "max_books": {"type": "integer", "minimum": 1},
            "force_reprocess": {"type": "boolean", "default": False},
        },
        "required": ["kind"],
    },
    "obsidian_vault": {
        "properties": {
            "kind": {"type": "string", "const": "obsidian_vault"},
            "source_key": {"type": "string", "pattern": "^src_[a-f0-9]{20}$"},
            "max_items": {"type": "integer", "minimum": 1, "maximum": 10000},
            "force_reprocess": {"type": "boolean", "default": False},
        },
        "required": ["kind", "source_key"],
    },
}


class Problem(StrictModel):
    type: AnyUrl
    title: str
    status: Annotated[int, Field(ge=400, le=599)]
    detail: str
    instance: str | None = None
    code: str | None = None
    errors: list[dict[str, Any]] | None = None


class ResourceReference(StrictModel):
    type: Literal[
        "content",
        "ingestion_run",
        "summary_batch",
        "theme_analysis",
        "digest",
        "pipeline_run",
        "podcast_script",
        "podcast",
        "audio_digest",
    ]
    id: str
    url: str


class BoundedDiagnostic(StrictModel):
    code: Annotated[str, Field(min_length=1, max_length=100)]
    message: Annotated[str, Field(min_length=1, max_length=500)]
    redirected_source_key: str | None = Field(None, pattern="^src_[a-f0-9]{20}$")


class ConfiguredSourceOutcome(StrictModel):
    source_key: Annotated[str, Field(pattern="^src_[a-f0-9]{20}$")]
    status: IngestionStatus
    items_ingested: Annotated[int, Field(ge=0)]
    items_failed: Annotated[int, Field(ge=0)]
    errors: Annotated[list[BoundedDiagnostic], Field(max_length=20)]
    warnings: Annotated[list[BoundedDiagnostic], Field(max_length=20)]
    errors_omitted: Annotated[int, Field(ge=0)]
    warnings_omitted: Annotated[int, Field(ge=0)]


class IngestionResultV1(StrictModel):
    schema_version: Literal[1] = 1
    command_key: str
    resolved_route: str
    emitted_sources: Annotated[list[str], Field(min_length=1)]
    items_ingested: Annotated[int, Field(ge=0)]
    content_ids: list[int]
    warnings: list[str] | None = None
    details: dict[str, Any] | None = None


class IngestionResultV2(StrictModel):
    schema_version: Literal[2] = 2
    command_key: Annotated[str, Field(min_length=1, max_length=100)]
    resolved_route: Annotated[str, Field(min_length=1, max_length=100)]
    emitted_sources: Annotated[list[str], Field(min_length=1)]
    status: IngestionStatus
    outcome: IngestionOutcome
    items_ingested: Annotated[int, Field(ge=0)]
    items_skipped: Annotated[int, Field(ge=0)]
    items_failed: Annotated[int, Field(ge=0)]
    content_ids: list[int]
    errors: Annotated[list[BoundedDiagnostic], Field(max_length=20)]
    warnings: Annotated[list[BoundedDiagnostic], Field(max_length=20)]
    errors_omitted: Annotated[int, Field(ge=0)]
    warnings_omitted: Annotated[int, Field(ge=0)]
    source_outcomes: Annotated[list[ConfiguredSourceOutcome], Field(max_length=100)]
    source_outcomes_omitted: Annotated[int, Field(ge=0)]
    details: SafeIngestionDetails
    details_omitted: Annotated[int, Field(ge=0)]


class SafeIngestionDetails(StrictModel):
    dry_run: bool | None = None
    duplicate: bool | None = None
    version_updated: bool | None = None
    papers_ingested: int | None = Field(None, ge=0)
    refs_ingested: int | None = Field(None, ge=0)
    content_scanned: int | None = Field(None, ge=0)
    references_found: int | None = Field(None, ge=0)
    references_resolved: int | None = Field(None, ge=0)
    references_unresolved: int | None = Field(None, ge=0)
    queries_made: int | None = Field(None, ge=0)
    citations_found: int | None = Field(None, ge=0)
    tool_calls_made: int | None = Field(None, ge=0)
    threads_found: int | None = Field(None, ge=0)


class PipelineSourceIngestionSummary(StrictModel):
    operation_id: Annotated[str, Field(max_length=19, pattern="^[1-9][0-9]*$")]
    command_key: Annotated[str, Field(min_length=1, max_length=100)]
    operation_status: TerminalOperationStatus
    outcome: IngestionOutcome
    items_ingested: Annotated[int | None, Field(ge=0)]
    items_skipped: Annotated[int | None, Field(ge=0)]
    items_failed: Annotated[int | None, Field(ge=0)]


class PipelineIngestionSummary(StrictModel):
    outcome: IngestionOutcome
    sources: Annotated[list[PipelineSourceIngestionSummary], Field(max_length=100)]
    sources_omitted: Annotated[int, Field(ge=0)]


class PipelineResultV2(ExtensibleModel):
    schema_version: Literal[2] = 2
    ingestion_summary: PipelineIngestionSummary


class ConfiguredSourceHistoryOutcome(StrictModel):
    source_key: Annotated[str, Field(pattern="^src_[a-f0-9]{20}$")]
    status: IngestionStatus
    outcome: IngestionOutcome
    items_ingested: Annotated[int | None, Field(ge=0)]
    items_failed: Annotated[int | None, Field(ge=0)]
    error_codes: list[str] | None = Field(None, max_length=20)
    warning_codes: list[str] | None = Field(None, max_length=20)


class IngestionHistoryItem(StrictModel):
    operation_id: Annotated[str, Field(max_length=19, pattern="^[1-9][0-9]*$")]
    parent_operation_id: str | None = Field(None, max_length=19, pattern="^[1-9][0-9]*$")
    command_key: Annotated[str, Field(min_length=1, max_length=100)]
    operation_status: TerminalOperationStatus
    outcome: IngestionOutcome
    items_ingested: Annotated[int | None, Field(ge=0)]
    items_skipped: Annotated[int | None, Field(ge=0)]
    items_failed: Annotated[int | None, Field(ge=0)]
    source_outcomes: Annotated[list[ConfiguredSourceHistoryOutcome], Field(max_length=100)]
    retry_count: Annotated[int, Field(ge=0)]
    problem_code: str | None = Field(None, max_length=100)
    status_url: Annotated[str, Field(pattern="^/api/v1/operations/[1-9][0-9]*$")]
    created_at: datetime
    completed_at: datetime | None = None


class IngestionHistoryPage(StrictModel):
    data: Annotated[list[IngestionHistoryItem], Field(max_length=100)]
    next_cursor: str | None = Field(None, max_length=2048)


class OperationSummary(StrictModel):
    schema_version: Literal[2] = 2
    operation_id: Annotated[str, Field(max_length=19, pattern="^[1-9][0-9]*$")]
    operation_type: OperationType
    status: OperationStatus
    progress: Annotated[int, Field(ge=0, le=100)]
    message: Annotated[str, Field(max_length=500)]
    cancellable: bool
    retry_count: Annotated[int, Field(ge=0)]
    status_url: Annotated[str, Field(pattern="^/api/v1/operations/[1-9][0-9]*$")]
    events_url: Annotated[str, Field(pattern="^/api/v1/operations/[1-9][0-9]*/events$")]
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class OperationHandle(StrictModel):
    schema_version: Literal[2] = 2
    operation_id: str
    operation_type: OperationType
    status: OperationStatus
    progress: Annotated[int, Field(ge=0, le=100)]
    message: str
    cancellable: bool
    retry_count: Annotated[int, Field(ge=0)]
    status_url: str
    events_url: str
    resource: ResourceReference | None = None
    result: dict[str, Any] | None = None
    problem: Problem | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    observability: OperationObservabilitySummary | None = None


class OperationPage(StrictModel):
    data: Annotated[list[OperationSummary], Field(max_length=100)]
    next_cursor: str | None = Field(None, max_length=2048)


class WorkflowAlertVerificationContext(StrictModel):
    schema_version: Literal[1] = 1
    environment_class: Literal["staging"] = "staging"
    revision: Annotated[str, Field(min_length=40, max_length=40, pattern="^[a-f0-9]{40}$")]
    revision_source: Literal["railway_commit_sha"] = "railway_commit_sha"

    @field_validator("schema_version", mode="before")
    @classmethod
    def validate_workflowalertverificationcontext_schema_version(cls, value: Any) -> int:
        return _validate_schema_version_one(value)


class WorkflowTerminalDeliveryCounts(StrictModel):
    pending: Annotated[int, Field(ge=0, le=9223372036854775807)]
    leased: Annotated[int, Field(ge=0, le=9223372036854775807)]
    delivered: Annotated[int, Field(ge=0, le=9223372036854775807)]
    permanent_failure: Annotated[int, Field(ge=0, le=9223372036854775807)]
    exhausted: Annotated[int, Field(ge=0, le=9223372036854775807)]


class WorkflowTerminalEventDiagnostic(StrictModel):
    schema_version: Literal[1] = 1
    event_id: UUID
    event_key: Annotated[str, Field(min_length=1, max_length=160, pattern="^[a-z0-9:_-]+$")]
    source_kind: Literal[
        "operation", "reconciliation_action", "reconciliation_failure", "system_check"
    ]
    operation_id: Annotated[str | None, Field(max_length=19, pattern="^[1-9][0-9]*$")]
    claim_generation: Annotated[int | None, Field(ge=0, le=2147483647)]
    terminal_status: Literal["completed", "failed", "cancelled", None]
    classification_status: Literal["pending", "ready", "telemetry_only", "rejected"]
    release_revision: Annotated[
        str | None, Field(max_length=40, pattern="^(?:[a-f0-9]{40}|development|unavailable)$")
    ]
    release_revision_source: Literal["railway_commit_sha", "local_development", "unavailable", None]
    occurred_at: datetime
    telemetry_emitted_at: datetime | None
    delivery_counts: WorkflowTerminalDeliveryCounts

    @field_validator("schema_version", mode="before")
    @classmethod
    def validate_workflowterminaleventdiagnostic_schema_version(cls, value: Any) -> int:
        return _validate_schema_version_one(value)


class ContentReconciliationRequest(StrictModel):
    apply: bool = False
    limit: int | None = Field(None, ge=1, le=100)
    after_content_id: int | None = Field(None, ge=1, le=2147483647)


class ContentReconciliationCounts(StrictModel):
    applied: Annotated[int, Field(ge=0, le=100)]
    retried: Annotated[int, Field(ge=0, le=100)]
    projected: Annotated[int, Field(ge=0, le=100)]
    restored: Annotated[int, Field(ge=0, le=100)]
    active: Annotated[int, Field(ge=0, le=100)]
    locked: Annotated[int, Field(ge=0, le=100)]
    missing: Annotated[int, Field(ge=0, le=100)]
    conflicted: Annotated[int, Field(ge=0, le=100)]
    cancelled: Annotated[int, Field(ge=0, le=100)]
    forced: Annotated[int, Field(ge=0, le=100)]
    exhausted: Annotated[int, Field(ge=0, le=100)]
    incompatible: Annotated[int, Field(ge=0, le=100)]
    failed: Annotated[int, Field(ge=0, le=100)]


class ContentReconciliationItem(StrictModel):
    content_id: Annotated[int, Field(ge=1, le=2147483647)]
    projection: ContentReconciliationProjection
    content_status_before: ContentReconciliationContentStatus
    content_status_after: ContentReconciliationContentStatus
    operation_id: Annotated[str | None, Field(max_length=19, pattern="^[1-9][0-9]{0,18}$")]
    claim_generation: Annotated[int | None, Field(ge=1, le=9223372036854775807)]
    claim_protocol_version: Annotated[int | None, Field(ge=1, le=32767)]
    operation_status_before: ContentReconciliationOperationStatus | None
    operation_status_after: ContentReconciliationOperationStatus | None
    retry_count_before: Annotated[int | None, Field(ge=0, le=2147483647)]
    retry_count_after: Annotated[int | None, Field(ge=0, le=2147483647)]
    phase: ContentReconciliationPhase | None
    action: ContentReconciliationAction
    reason: ContentReconciliationReason
    operation_heartbeat_at: datetime | None = None
    operation_completed_at: datetime | None = None
    applied: bool


class ContentReconciliationReport(StrictModel):
    run_id: UUID
    mode: ContentReconciliationMode
    scanned: Annotated[int, Field(ge=0, le=100)]
    reported: Annotated[int, Field(ge=0, le=100)]
    next_after_content_id: int | None = Field(None, ge=1, le=2147483647)
    counts: ContentReconciliationCounts
    items: Annotated[list[ContentReconciliationItem], Field(max_length=100)]


class OperationEvent(StrictModel):
    schema_version: Literal[2] = 2
    event_id: str
    operation_id: str
    operation_type: OperationType
    status: OperationStatus
    progress: Annotated[int, Field(ge=0, le=100)]
    message: str
    resource: ResourceReference | None = None
    problem: Problem | None = None
    occurred_at: datetime


class UploadReference(StrictModel):
    id: str
    filename: str
    media_type: str
    size_bytes: Annotated[int, Field(ge=0)]
    title: str | None = None
    publication: str | None = None


class CapabilityField(StrictModel):
    name: str
    type: str
    required: bool
    description: str | None = None
    format: str | None = None
    enum: list[str] | None = None
    default: Any | None = None
    constraints: dict[str, Any] = {}


class SourceCapability(StrictModel):
    key: str
    display_name: str
    emitted_sources: Annotated[list[str], Field(min_length=1)]
    scheduled: bool
    supports_force: bool
    supports_date_range: bool
    supports_preview: bool
    requires_identifier: bool
    transports: list[Literal["cli", "http", "mcp", "frontend"]]
    fields: list[CapabilityField]


class CapabilityDocument(StrictModel):
    contract_version: str
    source_commands: list[SourceCapability]
    operation_types: list[str]
    resource_types: list[str]
    next_cursor: str | None = None


class ConfiguredSource(StrictModel):
    key: str
    command_key: str
    source_type: str
    name: str | None = None
    enabled: bool
    origin: Literal["yaml", "db"]
    configuration: dict[str, Any]
    ready: bool
    readiness_code: str | None


class ConfiguredSourcePage(StrictModel):
    data: list[ConfiguredSource]
    next_cursor: str | None = None


class ContentQuery(StrictModel):
    source_types: (
        list[
            Literal[
                "gmail",
                "rss",
                "file_upload",
                "youtube",
                "podcast",
                "substack",
                "manual",
                "webpage",
                "xsearch",
                "perplexity",
                "blog",
                "scholar",
                "arxiv",
                "huggingface_papers",
                "readwise",
                "obsidian",
                "other",
            ]
        ]
        | None
    ) = None
    statuses: (
        list[
            Literal[
                "pending", "parsing", "parsed", "processing", "completed", "failed", "filtered_out"
            ]
        ]
        | None
    ) = None
    publications: list[str] | None = None
    publication_search: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    date_basis: Literal["published_date", "ingested_at"] = "published_date"
    search: str | None = None
    limit: int | None = Field(None, ge=1)
    sort_by: Literal[
        "id", "title", "source_type", "publication", "status", "published_date", "ingested_at"
    ] = "published_date"
    sort_order: Literal["asc", "desc"] = "desc"
    canonical_only: bool = True
    require_summary: bool = True


class ConfiguredSourceCommandBase(StrictModel):
    configured_sources: list[dict[str, Any]] | None = None
    max_items: int | None = Field(None, ge=1)
    days_back: int | None = Field(None, ge=0)
    after_date: datetime | None = None
    force_reprocess: bool = False


class GmailIngestCommand(ConfiguredSourceCommandBase):
    kind: Literal["gmail"] = "gmail"
    configured_sources: list[dict[str, Any]] | None = None
    query: str | None = None
    max_items: int | None = Field(None, ge=1)
    days_back: int | None = Field(None, ge=0)
    after_date: datetime | None = None
    force_reprocess: bool = False


class RssIngestCommand(StrictModel):
    kind: Literal["rss"] = "rss"
    configured_sources: list[dict[str, Any]] | None = None
    max_items: int | None = Field(None, ge=1)
    days_back: int | None = Field(None, ge=0)
    after_date: datetime | None = None
    force_reprocess: bool = False


class BlogIngestCommand(StrictModel):
    kind: Literal["blog"] = "blog"
    configured_sources: list[dict[str, Any]] | None = None
    max_items: int | None = Field(None, ge=1)
    days_back: int | None = Field(None, ge=0)
    after_date: datetime | None = None
    force_reprocess: bool = False


class SubstackIngestCommand(StrictModel):
    kind: Literal["substack"] = "substack"
    configured_sources: list[dict[str, Any]] | None = None
    max_items: int | None = Field(None, ge=1)
    days_back: int | None = Field(None, ge=0)
    after_date: datetime | None = None
    force_reprocess: bool = False


class YouTubePlaylistIngestCommand(StrictModel):
    kind: Literal["youtube_playlist"] = "youtube_playlist"
    configured_sources: list[dict[str, Any]] | None = None
    max_items: int | None = Field(None, ge=1)
    days_back: int | None = Field(None, ge=0)
    after_date: datetime | None = None
    force_reprocess: bool = False
    public_only: bool = False


class YouTubeRssIngestCommand(StrictModel):
    kind: Literal["youtube_rss"] = "youtube_rss"
    configured_sources: list[dict[str, Any]] | None = None
    max_items: int | None = Field(None, ge=1)
    days_back: int | None = Field(None, ge=0)
    after_date: datetime | None = None
    force_reprocess: bool = False


class PodcastIngestCommand(StrictModel):
    kind: Literal["podcast"] = "podcast"
    configured_sources: list[dict[str, Any]] | None = None
    max_items: int | None = Field(None, ge=1)
    days_back: int | None = Field(None, ge=0)
    after_date: datetime | None = None
    force_reprocess: bool = False
    transcribe: bool = True


class XSearchIngestCommand(StrictModel):
    kind: Literal["x_search"] = "x_search"
    configured_sources: list[dict[str, Any]] | None = None
    prompt: str | None = None
    max_threads: int | None = Field(None, ge=1)
    force_reprocess: bool = False


class PerplexitySearchIngestCommand(StrictModel):
    kind: Literal["perplexity_search"] = "perplexity_search"
    configured_sources: list[dict[str, Any]] | None = None
    prompt: str | None = None
    max_items: int | None = Field(None, ge=1)
    recency: Literal["hour", "day", "week", "month"] | None = None
    context_size: Literal["low", "medium", "high"] | None = None
    force_reprocess: bool = False


class FilesIngestCommand(StrictModel):
    kind: Literal["files"] = "files"
    upload_ids: Annotated[list[str], Field(min_length=1)]
    force_reprocess: bool = False


class UrlIngestCommand(StrictModel):
    kind: Literal["url"] = "url"
    url: AnyUrl
    title: str | None = None
    tags: list[str] | None = None
    notes: str | None = None
    routing_mode: Literal["auto", "webpage"] = "auto"
    force_reprocess: bool = False


class ScholarSearchIngestCommand(StrictModel):
    kind: Literal["scholar_search"] = "scholar_search"
    configured_sources: list[dict[str, Any]] | None = None
    max_items: int = Field(20, ge=1)


class ScholarPaperIngestCommand(StrictModel):
    kind: Literal["scholar_paper"] = "scholar_paper"
    identifier: Annotated[str, Field(min_length=1)]
    with_references: bool = False


class ScholarReferencesIngestCommand(StrictModel):
    kind: Literal["scholar_references"] = "scholar_references"
    after: datetime | None = None
    before: datetime | None = None
    source_types: list[str] | None = None
    dry_run: bool = False
    limit: int | None = Field(None, ge=1)


class ArxivSearchIngestCommand(StrictModel):
    kind: Literal["arxiv_search"] = "arxiv_search"
    configured_sources: list[dict[str, Any]] | None = None
    max_items: int = Field(20, ge=1)
    days_back: int | None = Field(None, ge=0)
    after_date: datetime | None = None
    force_reprocess: bool = False
    extract_pdf: bool = True


class ArxivPaperIngestCommand(StrictModel):
    kind: Literal["arxiv_paper"] = "arxiv_paper"
    identifier: Annotated[str, Field(min_length=1)]
    extract_pdf: bool = True
    force_reprocess: bool = False


class HuggingFacePapersIngestCommand(StrictModel):
    kind: Literal["huggingface_papers"] = "huggingface_papers"
    configured_sources: list[dict[str, Any]] | None = None
    max_items: int = Field(30, ge=1)
    days_back: int | None = Field(None, ge=0)
    after_date: datetime | None = None
    force_reprocess: bool = False


class ReadwiseIngestCommand(StrictModel):
    kind: Literal["readwise"] = "readwise"
    configured_sources: list[dict[str, Any]] | None = None
    updated_after: datetime | None = None
    source_types: list[str] | None = None
    include_deleted: bool = False
    max_books: int | None = Field(None, ge=1)
    force_reprocess: bool = False


class ObsidianVaultIngestCommand(StrictModel):
    kind: Literal["obsidian_vault"] = "obsidian_vault"
    source_key: Annotated[str, Field(pattern="^src_[a-f0-9]{20}$")]
    configured_source_version: str | None = Field(None, pattern="^[a-f0-9]{64}$")
    max_items: int | None = Field(None, ge=1, le=10000)
    force_reprocess: bool = False


class SummarizationRequest(StrictModel):
    content_ids: list[int] | None = Field(None, min_length=1)
    query: ContentQuery | None = None
    force_reprocess: bool = False


class ThemeAnalysisRequest(StrictModel):
    query: ContentQuery
    max_themes: int = Field(10, ge=1, le=50)


class DigestCreateRequest(StrictModel):
    digest_type: Literal["daily", "weekly"]
    period_start: datetime
    period_end: datetime
    query: ContentQuery | None = None
    include_historical_context: bool = True


class PipelineRequest(StrictModel):
    period: Literal["daily", "weekly"]
    period_start: datetime
    period_end: datetime
    sources: list[str] | None = None
    continue_on_source_error: bool = True


class PodcastScriptRequest(StrictModel):
    digest_id: Annotated[int, Field(ge=1)]
    length: Literal["brief", "standard", "extended"] = "standard"
    enable_web_search: bool = True
    custom_focus_topics: list[str] | None = None
    custom_instructions: str | None = None


class PodcastAudioRequest(StrictModel):
    script_id: Annotated[int, Field(ge=1)]
    voice_provider: Literal["elevenlabs", "google_tts", "aws_polly", "openai_tts"] = "openai_tts"
    alex_voice: Literal["alex_male", "alex_female"] = "alex_male"
    sam_voice: Literal["sam_male", "sam_female"] = "sam_female"


class AudioDigestRequest(StrictModel):
    digest_id: Annotated[int, Field(ge=1)]
    provider: str = "openai"
    voice: str = "nova"
    speed: float = Field(1.0, ge=0.5, le=2.0)


class OperationContextEnvelope(StrictModel):
    schema_version: Literal[1] = 1
    operation_id: OperationId
    root_operation_id: OperationId
    parent_operation_id: OperationId | None
    traceparent: Annotated[
        str,
        Field(min_length=55, max_length=55, pattern="^00-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$"),
    ]
    tracestate: Annotated[
        str | None,
        Field(
            max_length=512,
            pattern="^[a-z0-9][a-z0-9_*/-]{0,255}=(?:[!-+\\--<>-~]|[!-+\\--<>-~][ -+\\--<>-~]{0,254}[!-+\\--<>-~])(,[a-z0-9][a-z0-9_*/-]{0,255}=(?:[!-+\\--<>-~]|[!-+\\--<>-~][ -+\\--<>-~]{0,254}[!-+\\--<>-~])){0,31}$",
        ),
    ]
    trace_id: TraceId
    span_id: SpanId
    claim_generation: ClaimGenerationString
    attempt_number: Int64PositiveString | None
    entrypoint: Annotated[str, Field(min_length=1, max_length=160)]
    service_name: Annotated[str, Field(min_length=1, max_length=100)]
    service_instance_id: Annotated[str, Field(min_length=1, max_length=128)]
    environment: Annotated[str, Field(min_length=1, max_length=32)]
    release_revision: Annotated[str, Field(min_length=1, max_length=64)]
    authority_fingerprint: Annotated[str | None, Field(max_length=64, pattern="^[0-9a-f]{64}$")]
    ownership_epoch: Int64NonNegativeString | None
    stage: OperationStage | None
    resource_kind: Annotated[str | None, Field(max_length=64)]
    resource_key: Annotated[str | None, Field(max_length=128)]

    @field_validator("schema_version", mode="before")
    @classmethod
    def validate_operationcontextenvelope_schema_version(cls, value: Any) -> int:
        return _validate_schema_version_one(value)

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
    attempt_number: Int64PositiveString
    trace_id: TraceId
    root_span_id: SpanId | None
    langfuse_observation_id: Annotated[str | None, Field(max_length=64)]
    service_name: Annotated[str, Field(max_length=100)]
    service_instance_id: Annotated[str, Field(max_length=128)]
    environment: Annotated[str, Field(max_length=32)]
    release_revision: Annotated[str, Field(max_length=64)]
    started_at: datetime
    completed_at: datetime | None
    terminal_stage: OperationStage | None
    outcome: OperationOutcome | None
    retryable: bool | None
    telemetry_delivery_state: TelemetryDeliveryState
    diagnostic_codes: Annotated[list[str], Field(max_length=20)]
    diagnostics_omitted: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def validate_attempt_number(self) -> OperationAttemptSummary:
        if int(self.attempt_number) != int(self.claim_generation) + 1:
            raise ValueError("attempt_number must equal claim_generation + 1")
        return self


class OperationObservabilitySummary(StrictModel):
    root_operation_id: OperationId
    trace_id: TraceId
    attempt_count: Annotated[int, Field(ge=0)]
    latest_attempt: OperationAttemptSummary | None
    telemetry_delivery_state: TelemetryDeliveryState
    langfuse_url: Annotated[AnyUrl | None, Field(max_length=2048)]


class OperationAttemptPage(StrictModel):
    schema_version: Literal[1] = 1
    operation_id: OperationId
    root_operation_id: OperationId
    attempts: Annotated[list[OperationAttemptSummary], Field(max_length=100)]
    attempts_omitted: Annotated[int, Field(ge=0)]
    next_after_claim_generation: ClaimGenerationString | None

    @field_validator("schema_version", mode="before")
    @classmethod
    def validate_operationattemptpage_schema_version(cls, value: Any) -> int:
        return _validate_schema_version_one(value)


class ProcessObservabilityHealth(StrictModel):
    schema_version: Literal[1] = 1
    required: bool
    initialized: bool
    status: Literal["healthy", "degraded", "disabled", "stale"]
    service_name: Annotated[str, Field(max_length=100)]
    service_instance_id: Annotated[str, Field(max_length=128)]
    environment: Annotated[str, Field(max_length=32)]
    release_revision: Annotated[str, Field(max_length=64)]
    lifecycle_kind: Literal["long_running", "short_lived"]
    expires_at: datetime
    export_target: Literal["local_langfuse", "remote_langfuse", "other_otlp", "none"]
    last_heartbeat_at: datetime
    last_success_at: datetime | None
    last_success_age_seconds: Annotated[int | None, Field(ge=0)]
    last_error_at: datetime | None
    last_error_age_seconds: Annotated[int | None, Field(ge=0)]
    last_error_code: Annotated[str | None, Field(max_length=100)]
    buffered_count: Annotated[int, Field(ge=0)]
    buffer_capacity: Annotated[int, Field(ge=1)]
    dropped_count: Annotated[int, Field(ge=0)]
    last_flush_at: datetime | None
    last_flush_succeeded: bool | None

    @field_validator("schema_version", mode="before")
    @classmethod
    def validate_processobservabilityhealth_schema_version(cls, value: Any) -> int:
        return _validate_schema_version_one(value)


class ObservabilityHealthPage(StrictModel):
    schema_version: Literal[1] = 1
    status: Literal["healthy", "degraded"]
    generated_at: datetime
    stale_after_seconds: Annotated[int, Field(ge=1)]
    processes_omitted: Annotated[int, Field(ge=0)]
    processes: Annotated[list[ProcessObservabilityHealth], Field(max_length=1000)]

    @field_validator("schema_version", mode="before")
    @classmethod
    def validate_observabilityhealthpage_schema_version(cls, value: Any) -> int:
        return _validate_schema_version_one(value)


class EnvironmentOwnershipStatus(StrictModel):
    schema_version: Literal[1] = 1
    configured_environment: Annotated[str, Field(min_length=1, max_length=32)]
    active_environment: Annotated[str, Field(min_length=1, max_length=32)]
    mode: Literal["active", "passive", "conflict"]
    authority_matches: bool
    authority_fingerprint_prefix: Annotated[str, Field(pattern="^[0-9a-f]{12}$")]
    epoch: Int64NonNegativeString
    passive_reasons: Annotated[list[str], Field(max_length=20)]
    dry_run: OwnershipDryRun | None

    @field_validator("schema_version", mode="before")
    @classmethod
    def validate_environmentownershipstatus_schema_version(cls, value: Any) -> int:
        return _validate_schema_version_one(value)


class OwnershipDryRun(StrictModel):
    target_environment: Annotated[str, Field(min_length=1, max_length=32)]
    allowed: bool
    next_epoch: Int64NonNegativeString | None
    checks: Annotated[list[str], Field(max_length=20)]


IngestionResult = IngestionResultV1 | IngestionResultV2


IngestCommand = Annotated[
    GmailIngestCommand
    | RssIngestCommand
    | BlogIngestCommand
    | SubstackIngestCommand
    | YouTubePlaylistIngestCommand
    | YouTubeRssIngestCommand
    | PodcastIngestCommand
    | XSearchIngestCommand
    | PerplexitySearchIngestCommand
    | FilesIngestCommand
    | UrlIngestCommand
    | ScholarSearchIngestCommand
    | ScholarPaperIngestCommand
    | ScholarReferencesIngestCommand
    | ArxivSearchIngestCommand
    | ArxivPaperIngestCommand
    | HuggingFacePapersIngestCommand
    | ReadwiseIngestCommand
    | ObsidianVaultIngestCommand,
    Field(discriminator="kind"),
]


def parse_operation_context_envelope(value: Any) -> OperationContextEnvelope:
    """Validate structure and all cross-field operation-context invariants."""
    return OperationContextEnvelope.model_validate(value)
