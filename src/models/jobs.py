"""Job status models for the parallel job queue system.

These Pydantic models represent job state from the pgqueuer_jobs table,
providing type-safe interfaces for job tracking, progress updates, and
status queries.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class JobStatus(StrEnum):
    """Job lifecycle states in the queue.

    State machine:
        queued → in_progress → completed
                           ↘ failed
                           ↘ cancelled

    Jobs can also be retried: failed → queued
    """

    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


OperationStatus = JobStatus


class OperationType(StrEnum):
    """Stable operation names shared by every external interface."""

    INGESTION_EXECUTE = "ingestion.execute"
    SUMMARIZATION_RUN = "summarization.run"
    THEME_ANALYSIS_CREATE = "theme_analysis.create"
    DIGEST_CREATE = "digest.create"
    PIPELINE_RUN = "pipeline.run"
    PODCAST_SCRIPT_CREATE = "podcast_script.create"
    PODCAST_AUDIO_CREATE = "podcast_audio.create"
    AUDIO_DIGEST_CREATE = "audio_digest.create"


LEGACY_OPERATION_TYPES: dict[str, OperationType] = {
    "ingest_content": OperationType.INGESTION_EXECUTE,
    "extract_url_content": OperationType.INGESTION_EXECUTE,
    "summarize_content": OperationType.SUMMARIZATION_RUN,
    "summarize_batch": OperationType.SUMMARIZATION_RUN,
    "analyze_themes": OperationType.THEME_ANALYSIS_CREATE,
    "create_theme_analysis": OperationType.THEME_ANALYSIS_CREATE,
    "create_digest": OperationType.DIGEST_CREATE,
    "run_pipeline": OperationType.PIPELINE_RUN,
    "create_podcast_script": OperationType.PODCAST_SCRIPT_CREATE,
    "generate_podcast_script": OperationType.PODCAST_SCRIPT_CREATE,
    "create_podcast_audio": OperationType.PODCAST_AUDIO_CREATE,
    "generate_podcast_audio": OperationType.PODCAST_AUDIO_CREATE,
    "create_audio_digest": OperationType.AUDIO_DIGEST_CREATE,
    "generate_audio_digest": OperationType.AUDIO_DIGEST_CREATE,
}


ResourceType = Literal[
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


class ResourceReference(BaseModel):
    """Reference to a durable resource produced by an operation."""

    model_config = ConfigDict(extra="forbid")

    type: ResourceType
    id: str
    url: str


class OperationProblem(BaseModel):
    """RFC 7807-compatible problem projected for a failed operation."""

    model_config = ConfigDict(extra="forbid")

    type: str = "about:blank"
    title: str
    status: int = Field(ge=400, le=599)
    detail: str
    instance: str | None = None
    code: str | None = None
    errors: list[dict[str, Any]] | None = None


class OperationPayloadV2(BaseModel):
    """Versioned application contract stored in ``pgqueuer_jobs.payload``."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[2] = 2
    operation_type: OperationType
    input: dict[str, Any] = Field(default_factory=dict)
    progress: int = Field(default=0, ge=0, le=100)
    message: str = "Queued"
    cancel_requested: bool = False
    cancellable: bool = True
    resource: ResourceReference | None = None
    result: dict[str, Any] | None = None
    problem: OperationProblem | None = None


_PAYLOAD_CONTROL_FIELDS = frozenset(
    {
        "schema_version",
        "operation_type",
        "progress",
        "message",
        "cancel_requested",
        "cancellable",
        "resource",
        "result",
        "problem",
    }
)


def normalize_operation_payload(
    entrypoint: str,
    payload: dict[str, Any],
) -> OperationPayloadV2:
    """Read schema-v2 payloads and project supported legacy payloads.

    Version-1 queue handlers expect workflow arguments at the payload root, so
    this parser does not mutate stored data. It only lifts those fields into
    ``input`` for the canonical status projection.
    """

    raw = dict(payload)
    raw_schema_version = raw.get("schema_version", 1)
    try:
        schema_version = int(raw_schema_version)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid job payload schema version: {raw_schema_version}") from exc
    if schema_version == 2:
        raw["schema_version"] = 2
        return OperationPayloadV2.model_validate(raw)
    if schema_version != 1:
        raise ValueError(f"Unsupported job payload schema version: {schema_version}")

    operation_type = LEGACY_OPERATION_TYPES.get(entrypoint)
    if operation_type is None:
        try:
            operation_type = OperationType(entrypoint)
        except ValueError as exc:
            raise ValueError(
                f"Cannot project legacy entrypoint '{entrypoint}' as a canonical operation"
            ) from exc

    normalized_input = {
        key: value for key, value in raw.items() if key not in _PAYLOAD_CONTROL_FIELDS
    }
    return OperationPayloadV2(
        operation_type=operation_type,
        input=normalized_input,
        progress=raw.get("progress", 0),
        message=raw.get("message", "Queued"),
        cancel_requested=raw.get("cancel_requested", False),
        cancellable=raw.get("cancellable", True),
        resource=raw.get("resource"),
        result=raw.get("result"),
        problem=raw.get("problem"),
    )


class OperationHandle(BaseModel):
    """Transport-neutral projection of a durable queue record."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[2] = 2
    operation_id: str
    operation_type: OperationType
    status: OperationStatus
    progress: int = Field(ge=0, le=100)
    message: str
    cancellable: bool
    retry_count: int = Field(ge=0)
    status_url: str
    events_url: str
    resource: ResourceReference | None = None
    result: dict[str, Any] | None = None
    problem: OperationProblem | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @property
    def is_terminal(self) -> bool:
        return self.status in {
            OperationStatus.COMPLETED,
            OperationStatus.FAILED,
            OperationStatus.CANCELLED,
        }


class OperationEvent(BaseModel):
    """Current operation snapshot encoded as a resumable progress event."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[2] = 2
    event_id: str
    operation_id: str
    operation_type: OperationType
    status: OperationStatus
    progress: int = Field(ge=0, le=100)
    message: str
    resource: ResourceReference | None = None
    problem: OperationProblem | None = None
    occurred_at: datetime


class OperationPage(BaseModel):
    """Cursor page used by agent-facing operation listings."""

    model_config = ConfigDict(extra="forbid")

    data: list[OperationHandle]
    next_cursor: str | None = None


class JobPayload(BaseModel):
    """Structured job payload with progress tracking.

    The payload is stored as JSONB in pgqueuer_jobs.payload.
    This model provides type-safe access to common fields.
    """

    model_config = ConfigDict(extra="allow")

    # Common payload fields
    content_id: int | None = Field(default=None, description="ID of content being processed")

    # Progress tracking (0-100)
    progress: int = Field(default=0, ge=0, le=100, description="Job progress percentage")
    message: str = Field(default="", description="Current status message")


class JobRecord(BaseModel):
    """Complete job record from pgqueuer_jobs table.

    Represents a single job with all metadata, used for:
    - API responses (GET /api/v1/jobs/{id})
    - CLI output (aca jobs show {id})
    - SSE progress events
    """

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Unique job identifier")
    entrypoint: str = Field(description="Task handler name (e.g., 'summarize_content')")
    status: JobStatus = Field(description="Current job state")
    payload: dict[str, Any] = Field(default_factory=dict, description="Job parameters and progress")
    priority: int = Field(default=0, description="Job priority (higher = sooner)")
    error: str | None = Field(default=None, description="Error message if failed")
    retry_count: int = Field(default=0, description="Number of retry attempts")
    parent_job_id: int | None = Field(default=None, description="Parent batch job ID")
    heartbeat_at: datetime | None = Field(default=None, description="Last liveness heartbeat")
    created_at: datetime = Field(description="When the job was enqueued")
    started_at: datetime | None = Field(default=None, description="When processing began")
    completed_at: datetime | None = Field(default=None, description="When processing finished")

    @property
    def progress(self) -> int:
        """Extract progress from payload (convenience accessor)."""
        return self.payload.get("progress", 0)

    @property
    def progress_message(self) -> str:
        """Extract progress message from payload (convenience accessor)."""
        return self.payload.get("message", "")

    @property
    def is_terminal(self) -> bool:
        """Check if job has reached a terminal state."""
        return self.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED)


class JobListItem(BaseModel):
    """Compact job representation for list views.

    Used in paginated API responses and CLI table output.
    Excludes large payload data for efficiency.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    entrypoint: str
    status: JobStatus
    progress: int = Field(default=0)
    error: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class JobListResponse(BaseModel):
    """Paginated job list API response."""

    data: list[JobListItem]
    pagination: dict[str, int] = Field(description="Pagination info: page, page_size, total")


class JobRetryResponse(BaseModel):
    """Response from job retry operation."""

    id: int
    status: JobStatus
    retry_count: int
    message: str = "Job re-enqueued for processing"


# ============================================================================
# Task History (Audit Log)
# ============================================================================

ENTRYPOINT_LABELS: dict[str, str] = {
    "summarize_content": "Summarize",
    "summarize_batch": "Summarize (Batch)",
    "extract_url_content": "URL Extraction",
    "process_content": "Process Content",
    "ingest_content": "Ingest",
    "run_pipeline": "Pipeline",
}

TYPE_ALIASES: dict[str, str] = {
    "summarize": "summarize_content",
    "batch": "summarize_batch",
    "extract": "extract_url_content",
    "process": "process_content",
    "ingest": "ingest_content",
    "pipeline": "run_pipeline",
}


class JobHistoryItem(BaseModel):
    """Enriched job record for the Task History audit view.

    Extends the raw job data with human-readable labels and
    context-aware descriptions built from payload + content table.
    """

    id: int
    entrypoint: str
    task_label: str
    status: JobStatus
    content_id: int | None = None
    description: str | None = None
    error: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class JobHistoryResponse(BaseModel):
    """Paginated job history API response."""

    data: list[JobHistoryItem]
    pagination: dict[str, int] = Field(description="Pagination info: page, page_size, total")
