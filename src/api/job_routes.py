"""Job Queue API Routes.

Provides endpoints for listing, viewing, and retrying jobs in the parallel
job queue system (PGQueuer). Used by the frontend and CLI to monitor
background processing tasks.
"""

import re
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Path, Query

from src.models.jobs import (
    JobHistoryResponse,
    JobListResponse,
    JobRecord,
    JobRetryResponse,
    JobStatus,
)
from src.queue.setup import get_job_status, list_job_history, list_jobs, retry_failed_job
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])

_SINCE_SHORTHAND = re.compile(r"^(\d+)d$")


@router.get("", response_model=JobListResponse)
async def list_all_jobs(
    status: JobStatus | None = Query(None, description="Filter by job status"),
    entrypoint: str | None = Query(None, description="Filter by task entrypoint"),
    page: int = Query(1, ge=1, le=10000, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> JobListResponse:
    """
    List jobs with optional filters and pagination.

    Returns a paginated list of jobs, ordered by creation time (newest first).

    Filters:
    - status: Filter by job status (queued, in_progress, completed, failed)
    - entrypoint: Filter by task type (e.g., 'summarize_content')

    Pagination:
    - page: Page number (1-indexed)
    - page_size: Items per page (1-100, default 20)
    """
    offset = (page - 1) * page_size

    jobs, total = await list_jobs(
        status=status,
        entrypoint=entrypoint,
        limit=page_size,
        offset=offset,
    )

    return JobListResponse(
        data=jobs,
        pagination={
            "page": page,
            "page_size": page_size,
            "total": total,
        },
    )


@router.get("/history", response_model=JobHistoryResponse)
async def get_job_history(
    since: str | None = Query(
        None, description="Time filter: ISO datetime or shorthand (1d, 7d, 30d)"
    ),
    status: JobStatus | None = Query(None, description="Filter by job status"),
    entrypoint: str | None = Query(None, description="Filter by task entrypoint"),
    page: int = Query(1, ge=1, le=10000, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> JobHistoryResponse:
    """
    Get enriched job history for the audit view.

    Returns jobs with human-readable task labels and context-aware
    descriptions (built from content titles, source names, etc.).

    Time filter examples:
    - since=1d (last 24 hours)
    - since=7d (last 7 days)
    - since=2025-01-15T00:00:00Z (ISO datetime)
    """
    since_dt: datetime | None = None
    if since:
        match = _SINCE_SHORTHAND.match(since.strip().lower())
        if match:
            days = int(match.group(1))
            since_dt = datetime.now(UTC) - timedelta(days=days)
        else:
            try:
                since_dt = datetime.fromisoformat(since)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid 'since' format: '{since}'. Use ISO datetime or shorthand (1d, 7d, 30d).",
                )

    offset = (page - 1) * page_size

    items, total = await list_job_history(
        since=since_dt,
        status=status,
        entrypoint=entrypoint,
        limit=page_size,
        offset=offset,
    )

    return JobHistoryResponse(
        data=items,
        pagination={
            "page": page,
            "page_size": page_size,
            "total": total,
        },
    )


@router.get("/{job_id}", response_model=JobRecord)
async def get_job(job_id: int = Path(ge=1, le=9223372036854775807)) -> JobRecord:
    """
    Get job details by ID.

    Returns full job information including:
    - Status and progress
    - Payload data (content_id, progress message)
    - Timing information (created, started, completed)
    - Error message (if failed)
    - Retry count
    """
    job = await get_job_status(job_id)

    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return job


@router.post("/{job_id}/retry", response_model=JobRetryResponse)
async def retry_job(job_id: int = Path(ge=1, le=9223372036854775807)) -> JobRetryResponse:
    """
    Retry a failed job.

    Re-enqueues the job for processing. Only works for jobs
    in the 'failed' status.

    Returns:
    - id: Job ID
    - status: New status (should be 'queued')
    - retry_count: Number of retry attempts
    - message: Confirmation message
    """
    # First check if job exists
    existing = await get_job_status(job_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Job not found")

    # Check if job is in failed status
    if existing.status != JobStatus.FAILED:
        raise HTTPException(
            status_code=400,
            detail=f"Only failed jobs can be retried. Current status: {existing.status.value}",
        )

    # Retry the job
    updated = await retry_failed_job(job_id)

    if updated is None:
        raise HTTPException(
            status_code=500,
            detail="Failed to retry job",
        )

    return JobRetryResponse(
        id=updated.id,
        status=updated.status,
        retry_count=updated.retry_count,
        message="Job re-enqueued for processing",
    )
