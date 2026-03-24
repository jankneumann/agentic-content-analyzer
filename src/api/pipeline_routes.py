"""Pipeline API routes.

Provides endpoints for triggering and monitoring pipeline runs:
- POST /api/v1/pipeline/run — enqueue a pipeline job
- GET /api/v1/pipeline/status/{job_id} — SSE progress stream
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.api.dependencies import verify_admin_key
from src.models.jobs import JobStatus
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/v1/pipeline",
    tags=["pipeline"],
    dependencies=[Depends(verify_admin_key)],
)


class PipelineRunRequest(BaseModel):
    """Request body for pipeline execution."""

    pipeline_type: str = Field(default="daily", description="Pipeline type: 'daily' or 'weekly'")
    date: str | None = Field(default=None, description="Target date YYYY-MM-DD (default: today)")
    sources: list[str] | None = Field(
        default=None, description="Source filter (default: all sources)"
    )


class PipelineRunResponse(BaseModel):
    """Response from pipeline trigger."""

    job_id: int
    message: str
    pipeline_type: str


@router.post("/run", response_model=PipelineRunResponse)
async def trigger_pipeline_run(request: PipelineRunRequest) -> PipelineRunResponse:
    """Trigger a pipeline run as a background job.

    Enqueues a run_pipeline job and returns the job ID for status tracking.
    """
    if request.pipeline_type not in ("daily", "weekly"):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid pipeline_type: '{request.pipeline_type}'. Must be 'daily' or 'weekly'.",
        )

    from src.queue.setup import enqueue_queue_job

    job_id, _created = await enqueue_queue_job(
        "run_pipeline",
        {
            "pipeline_type": request.pipeline_type,
            "date": request.date,
            "sources": request.sources,
        },
    )

    return PipelineRunResponse(
        job_id=job_id,
        message=f"Pipeline '{request.pipeline_type}' enqueued",
        pipeline_type=request.pipeline_type,
    )


@router.get("/status/{job_id}")
async def get_pipeline_status(job_id: int) -> StreamingResponse:
    """Stream pipeline job progress via Server-Sent Events.

    Polls the job record and yields SSE events until the job reaches
    a terminal state (completed or failed).
    """
    from src.queue.setup import DEFAULT_STATUS_POLL_SECONDS, get_job_status

    job = await get_job_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        import json

        from src.queue.setup import _open_queue_connection

        conn = await _open_queue_connection()
        try:
            while True:
                job = await get_job_status(job_id, conn=conn)
                if not job:
                    yield f"data: {json.dumps({'status': 'error', 'message': 'Job not found'})}\n\n"
                    break

                payload = job.payload or {}
                status_str = {
                    JobStatus.QUEUED: "queued",
                    JobStatus.IN_PROGRESS: "processing",
                    JobStatus.COMPLETED: "completed",
                    JobStatus.FAILED: "error",
                }.get(job.status, "unknown")

                event_data = {
                    "status": status_str,
                    "progress": payload.get("progress", 0),
                    "message": payload.get("message", ""),
                    "stage": payload.get("stage", ""),
                    "pipeline_type": payload.get("pipeline_type", ""),
                    "started_at": job.started_at.isoformat() if job.started_at else None,
                }
                if job.error:
                    event_data["message"] = job.error

                yield f"data: {json.dumps(event_data)}\n\n"

                if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                    break

                await asyncio.sleep(DEFAULT_STATUS_POLL_SECONDS)
        finally:
            await conn.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
