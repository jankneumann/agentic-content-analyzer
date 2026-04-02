"""Agent API Routes.

Endpoints for submitting and monitoring agentic analysis tasks,
browsing generated insights, handling approval requests, and
managing proactive schedules and personas.
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.dependencies import verify_admin_key
from src.models.agent_task import AgentTaskStatus
from src.models.approval_request import ApprovalStatus
from src.queue.setup import enqueue_queue_job
from src.services.agent_service import AgentInsightService, AgentTaskService, ApprovalService
from src.storage.database import get_db
from src.utils.logging import get_logger

logger = get_logger(__name__)


def _parse_uuid(value: str, name: str = "ID") -> uuid.UUID:
    """Parse a string to UUID, raising 422 on invalid format."""
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid {name}: {value}")


def _task_to_response(task) -> "TaskResponse":
    """Convert an AgentTask ORM instance to a TaskResponse."""
    return TaskResponse(
        id=str(task.id),
        status=task.status,
        task_type=task.task_type,
        prompt=task.prompt,
        persona_name=task.persona_name,
        result=task.result,
        error_message=task.error_message,
        created_at=task.created_at.isoformat() if task.created_at else None,
    )


def _insight_to_response(insight) -> "InsightResponse":
    """Convert an AgentInsight ORM instance to an InsightResponse."""
    return InsightResponse(
        id=str(insight.id),
        insight_type=insight.insight_type,
        title=insight.title,
        content=insight.content,
        confidence=insight.confidence,
        tags=insight.tags or [],
        task_id=str(insight.task_id) if insight.task_id else None,
        created_at=insight.created_at.isoformat() if insight.created_at else None,
    )


# ============================================================================
# Request / Response Models
# ============================================================================


class TaskSubmission(BaseModel):
    """Request body for submitting a new agent task."""

    prompt: str = Field(..., min_length=1, description="The task prompt or question")
    task_type: Literal["research", "analysis", "synthesis", "ingestion", "maintenance"] = Field(
        default="research",
        description="Task type: research, analysis, synthesis, ingestion, maintenance",
    )
    persona: str = Field(default="default", description="Persona to use for this task")
    output: str | None = Field(default=None, description="Output format override")
    sources: list[str] | None = Field(default=None, description="Restrict to specific source types")
    params: dict[str, Any] = Field(default_factory=dict, description="Additional task parameters")


class TaskResponse(BaseModel):
    """Response model for a single agent task."""

    id: str
    status: str
    task_type: str
    prompt: str
    persona_name: str
    result: dict | None = None
    error_message: str | None = None
    created_at: str | None = None


class InsightResponse(BaseModel):
    """Response model for a single agent insight."""

    id: str
    insight_type: str
    title: str
    content: str
    confidence: float
    tags: list[str] = Field(default_factory=list)
    task_id: str | None = None
    created_at: str | None = None


class ApprovalDecision(BaseModel):
    """Request body for approving or denying an approval request."""

    approved: bool
    reason: str | None = None


class ScheduleResponse(BaseModel):
    """Response model for a schedule entry."""

    id: str
    cron: str
    task_type: str
    persona: str = "default"
    output: str | None = None
    sources: list[str] | None = None
    description: str = ""
    priority: str = "medium"
    enabled: bool = True


class PersonaResponse(BaseModel):
    """Response model for a persona summary."""

    name: str
    description: str = ""
    domain_focus: list[str] = Field(default_factory=list)


# ============================================================================
# Router
# ============================================================================

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])


# ─── Tasks ─────────────────────────────────────────────────────


@router.post("/task", dependencies=[Depends(verify_admin_key)])
async def submit_task(submission: TaskSubmission) -> dict:
    """Submit a new agent task.

    Creates an agent_task record and enqueues it for processing
    by the conductor agent.
    """
    with get_db() as db:
        task = AgentTaskService(db).create_task(
            prompt=submission.prompt,
            task_type=submission.task_type,
            persona=submission.persona,
            source="user",
            params=submission.params,
        )
        db.commit()
        task_id = str(task.id)
        task_type = task.task_type
        persona_name = task.persona_name

    # Enqueue for async processing (DB work is committed above)
    job_id, created = await enqueue_queue_job(
        "execute_agent_task",
        {
            "task_id": task_id,
            "prompt": submission.prompt,
            "task_type": task_type,
            "persona": persona_name,
        },
    )
    logger.info(
        "Agent task submitted: %s (type=%s, persona=%s, job=%d, new=%s)",
        task_id,
        task_type,
        persona_name,
        job_id,
        created,
    )
    return {"task_id": task_id, "status": "received"}


@router.get("/task/{task_id}", dependencies=[Depends(verify_admin_key)])
async def get_task(task_id: str) -> TaskResponse:
    """Get the status and result of an agent task."""
    task_uuid = _parse_uuid(task_id, "task ID")
    with get_db() as db:
        task = AgentTaskService(db).get_task(task_uuid)
        if task is None:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        return _task_to_response(task)


@router.get("/tasks", dependencies=[Depends(verify_admin_key)])
async def list_tasks(
    status: str | None = Query(default=None, description="Filter by status"),
    persona: str | None = Query(default=None, description="Filter by persona"),
    limit: int = Query(default=50, ge=1, le=200, description="Max results"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
) -> list[TaskResponse]:
    """List agent tasks with optional filters."""
    with get_db() as db:
        tasks, _total = AgentTaskService(db).list_tasks(
            status=status, persona=persona, limit=limit, offset=offset
        )
        return [_task_to_response(t) for t in tasks]


@router.delete("/task/{task_id}", dependencies=[Depends(verify_admin_key)])
async def cancel_task(task_id: str) -> dict:
    """Cancel a pending or in-progress agent task."""
    task_uuid = _parse_uuid(task_id, "task ID")
    with get_db() as db:
        task = AgentTaskService(db).cancel_task(task_uuid)
        if task is None:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        db.commit()
        return {"task_id": str(task.id), "status": task.status}


# ─── Insights ──────────────────────────────────────────────────


@router.get("/insights", dependencies=[Depends(verify_admin_key)])
async def list_insights(
    insight_type: str | None = Query(default=None, description="Filter by insight type"),
    since: str | None = Query(
        default=None, description="ISO datetime — only insights after this time"
    ),
    persona: str | None = Query(
        default=None, description="Filter by persona that generated the insight"
    ),
    limit: int = Query(default=50, ge=1, le=200, description="Max results"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
) -> list[InsightResponse]:
    """List generated agent insights with optional filters."""
    since_dt: datetime | None = None
    if since is not None:
        try:
            since_dt = datetime.fromisoformat(since)
        except ValueError:
            raise HTTPException(
                status_code=422, detail="Invalid 'since' datetime format. Use ISO 8601."
            )
    with get_db() as db:
        insights, _total = AgentInsightService(db).list_insights(
            insight_type=insight_type, since=since_dt, persona=persona, limit=limit, offset=offset
        )
        return [_insight_to_response(i) for i in insights]


@router.get("/insights/{insight_id}", dependencies=[Depends(verify_admin_key)])
async def get_insight(insight_id: str) -> InsightResponse:
    """Get a single agent insight by ID."""
    insight_uuid = _parse_uuid(insight_id, "insight ID")
    with get_db() as db:
        insight = AgentInsightService(db).get_insight(insight_uuid)
        if insight is None:
            raise HTTPException(status_code=404, detail=f"Insight {insight_id} not found")
        return _insight_to_response(insight)


# ─── Approvals ─────────────────────────────────────────────────


@router.post("/approval/{request_id}", dependencies=[Depends(verify_admin_key)])
async def handle_approval(request_id: str, decision: ApprovalDecision) -> dict:
    """Approve or deny a pending approval request.

    When approved, the blocked task resumes execution.
    When denied, the denial reason is passed to the conductor for re-planning.
    """
    req_uuid = _parse_uuid(request_id, "approval request ID")
    task_id_str: str | None = None
    task_was_blocked = False

    with get_db() as db:
        result = ApprovalService(db).decide_request(req_uuid, decision.approved, decision.reason)
        if result is None:
            raise HTTPException(status_code=404, detail=f"Approval request {request_id} not found")
        # Check if we should re-enqueue the associated task
        if result.status == ApprovalStatus.APPROVED and result.task_id:
            task = AgentTaskService(db).get_task(result.task_id)
            if task and task.status == AgentTaskStatus.BLOCKED:
                task_id_str = str(task.id)
                task_was_blocked = True
        db.commit()

    # Re-enqueue the blocked task outside the DB session
    if task_was_blocked and task_id_str:
        await enqueue_queue_job(
            "execute_agent_task",
            {"task_id": task_id_str},
        )
        logger.info("Re-enqueued blocked task %s after approval", task_id_str)

    return {
        "request_id": str(result.id),
        "status": result.status,
        "decided_at": result.decided_at.isoformat() if result.decided_at else None,
    }


# ─── Schedules ─────────────────────────────────────────────────


def _get_scheduler():
    """Lazy-init a module-level scheduler to share state across requests."""
    global _scheduler
    if _scheduler is None:
        from src.agents.scheduler.scheduler import AgentScheduler

        _scheduler = AgentScheduler()
        _scheduler.load_schedules()
    return _scheduler


_scheduler = None


@router.get("/schedules", dependencies=[Depends(verify_admin_key)])
async def list_schedules() -> list[ScheduleResponse]:
    """List all proactive schedule entries."""
    try:
        scheduler = _get_scheduler()
        return [
            ScheduleResponse(
                id=s.id,
                cron=s.cron,
                task_type=s.task_type,
                persona=s.persona,
                output=s.output,
                sources=s.sources,
                description=s.description,
                priority=s.priority,
                enabled=s.enabled,
            )
            for s in scheduler.list_schedules()
        ]
    except Exception:
        logger.exception("Failed to load schedules")
        return []


@router.post("/schedules/{schedule_id}/enable", dependencies=[Depends(verify_admin_key)])
async def enable_schedule(schedule_id: str) -> dict:
    """Enable a proactive schedule entry."""
    scheduler = _get_scheduler()
    if scheduler.enable_schedule(schedule_id):
        return {"schedule_id": schedule_id, "enabled": True}
    raise HTTPException(status_code=404, detail=f"Schedule not found: {schedule_id}")


@router.post("/schedules/{schedule_id}/disable", dependencies=[Depends(verify_admin_key)])
async def disable_schedule(schedule_id: str) -> dict:
    """Disable a proactive schedule entry."""
    scheduler = _get_scheduler()
    if scheduler.disable_schedule(schedule_id):
        return {"schedule_id": schedule_id, "enabled": False}
    raise HTTPException(status_code=404, detail=f"Schedule not found: {schedule_id}")


# ─── Personas ──────────────────────────────────────────────────


@router.get("/personas", dependencies=[Depends(verify_admin_key)])
async def list_personas() -> list[PersonaResponse]:
    """List available agent personas."""
    try:
        from src.agents.persona.loader import PersonaLoader

        loader = PersonaLoader()
        names = loader.list_personas()
        results: list[PersonaResponse] = []

        for name in names:
            try:
                config = loader.load(name)
                results.append(
                    PersonaResponse(
                        name=name,
                        description=config.role,
                        domain_focus=config.domain_focus.primary,
                    )
                )
            except Exception:
                logger.warning("Failed to load persona: %s", name)

        return results
    except Exception:
        logger.exception("Failed to list personas")
        return []


@router.get("/task/{task_id}/stream", dependencies=[Depends(verify_admin_key)])
async def stream_task_progress(task_id: str):
    """Stream task progress via Server-Sent Events."""
    from starlette.responses import StreamingResponse

    task_uuid = _parse_uuid(task_id, "task ID")
    terminal_statuses = {AgentTaskStatus.COMPLETED, AgentTaskStatus.FAILED}

    async def event_generator():
        """Poll task status from DB and yield SSE events.

        Polls every 1 second, breaks on terminal states (completed, failed).
        Max 300 polls = 5 minutes.
        """
        max_polls = 300  # 5 minutes at 1s intervals
        for _ in range(max_polls):
            with get_db() as db:
                task = AgentTaskService(db).get_task(task_uuid)
            if task is None:
                yield f"data: {json.dumps({'status': 'not_found', 'task_id': task_id})}\n\n"
                return
            event_data = {
                "task_id": task_id,
                "status": task.status,
                "error_message": task.error_message,
            }
            if task.result:
                event_data["result"] = task.result
            yield f"data: {json.dumps(event_data)}\n\n"
            if task.status in terminal_statuses:
                return
            await asyncio.sleep(1)
        yield f"data: {json.dumps({'status': 'timeout', 'task_id': task_id})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
