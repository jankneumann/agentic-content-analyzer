"""Agent API Routes.

Endpoints for submitting and monitoring agentic analysis tasks,
browsing generated insights, handling approval requests, and
managing proactive schedules and personas.
"""

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.dependencies import verify_admin_key
from src.utils.logging import get_logger

logger = get_logger(__name__)


# ============================================================================
# Request / Response Models
# ============================================================================


class TaskSubmission(BaseModel):
    """Request body for submitting a new agent task."""

    prompt: str = Field(..., min_length=1, description="The task prompt or question")
    task_type: Literal["research", "analysis", "synthesis", "ingestion", "maintenance"] = Field(
        default="research", description="Task type: research, analysis, synthesis, ingestion, maintenance"
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
    # Stub: return a placeholder task ID
    import uuid

    task_id = str(uuid.uuid4())
    logger.info("Agent task submitted: %s (type=%s, persona=%s)", task_id, submission.task_type, submission.persona)
    return {"task_id": task_id, "status": "received"}


@router.get("/task/{task_id}", dependencies=[Depends(verify_admin_key)])
async def get_task(task_id: str) -> TaskResponse:
    """Get the status and result of an agent task."""
    # Stub: return a not-found response until DB integration
    raise HTTPException(status_code=404, detail=f"Task {task_id} not found")


@router.get("/tasks", dependencies=[Depends(verify_admin_key)])
async def list_tasks(
    status: str | None = Query(default=None, description="Filter by status"),
    persona: str | None = Query(default=None, description="Filter by persona"),
    limit: int = Query(default=50, ge=1, le=200, description="Max results"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
) -> list[TaskResponse]:
    """List agent tasks with optional filters."""
    # Stub: return empty list until DB integration
    return []


@router.delete("/task/{task_id}", dependencies=[Depends(verify_admin_key)])
async def cancel_task(task_id: str) -> dict:
    """Cancel a pending or in-progress agent task."""
    # Stub: return not-found until DB integration
    raise HTTPException(status_code=404, detail=f"Task {task_id} not found")


# ─── Insights ──────────────────────────────────────────────────


@router.get("/insights", dependencies=[Depends(verify_admin_key)])
async def list_insights(
    insight_type: str | None = Query(default=None, description="Filter by insight type"),
    since: str | None = Query(default=None, description="ISO datetime — only insights after this time"),
    persona: str | None = Query(default=None, description="Filter by persona that generated the insight"),
    limit: int = Query(default=50, ge=1, le=200, description="Max results"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
) -> list[InsightResponse]:
    """List generated agent insights with optional filters."""
    # Validate since parameter if provided
    if since is not None:
        try:
            datetime.fromisoformat(since)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid 'since' datetime format. Use ISO 8601.")
    # Stub: return empty list until DB integration
    return []


@router.get("/insights/{insight_id}", dependencies=[Depends(verify_admin_key)])
async def get_insight(insight_id: str) -> InsightResponse:
    """Get a single agent insight by ID."""
    raise HTTPException(status_code=404, detail=f"Insight {insight_id} not found")


# ─── Approvals ─────────────────────────────────────────────────


@router.post("/approval/{request_id}", dependencies=[Depends(verify_admin_key)])
async def handle_approval(request_id: str, decision: ApprovalDecision) -> dict:
    """Approve or deny a pending approval request.

    When approved, the blocked task resumes execution.
    When denied, the denial reason is passed to the conductor for re-planning.
    """
    # Stub: return not-found until DB integration
    raise HTTPException(status_code=404, detail=f"Approval request {request_id} not found")


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
        from pathlib import Path

        import yaml

        personas_dir = Path("settings/personas")
        results: list[PersonaResponse] = []

        if not personas_dir.exists():
            return results

        for yaml_file in sorted(personas_dir.glob("*.yaml")):
            try:
                with open(yaml_file) as f:
                    data = yaml.safe_load(f) or {}
                name = yaml_file.stem
                description = data.get("description", "")
                domain = data.get("domain_focus", {})
                primary = domain.get("primary", []) if isinstance(domain, dict) else []
                results.append(
                    PersonaResponse(
                        name=name,
                        description=description,
                        domain_focus=primary,
                    )
                )
            except Exception:
                logger.warning("Failed to parse persona file: %s", yaml_file)

        return results
    except Exception:
        logger.exception("Failed to list personas")
        return []
