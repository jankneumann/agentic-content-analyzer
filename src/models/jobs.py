"""Job status models for the parallel job queue system.

These Pydantic models represent job state from the pgqueuer_jobs table,
providing type-safe interfaces for job tracking, progress updates, and
status queries.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class JobStatus(StrEnum):
    """Job lifecycle states in the queue.

    State machine:
        queued → in_progress → completed
                           ↘ failed

    Jobs can also be retried: failed → queued
    """

    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


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
        return self.status in (JobStatus.COMPLETED, JobStatus.FAILED)


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
}

TYPE_ALIASES: dict[str, str] = {
    "summarize": "summarize_content",
    "batch": "summarize_batch",
    "extract": "extract_url_content",
    "process": "process_content",
    "ingest": "ingest_content",
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
