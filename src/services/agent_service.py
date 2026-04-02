"""Service layer for agent task, insight, and approval CRUD.

Follows the ContentService pattern: each service takes a SQLAlchemy
Session in __init__ and performs synchronous DB operations. Routes
and CLI commands use ``with get_db() as db:`` to obtain sessions.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import desc
from sqlalchemy.orm import Session

from src.models.agent_insight import AgentInsight
from src.models.agent_task import AgentTask, AgentTaskStatus
from src.models.approval_request import ApprovalRequest, ApprovalStatus
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Terminal states — tasks in these states cannot be cancelled or restarted.
_TERMINAL_STATUSES = {AgentTaskStatus.COMPLETED, AgentTaskStatus.FAILED}


class AgentTaskService:
    """CRUD operations for agent tasks."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_task(
        self,
        prompt: str,
        task_type: str = "research",
        persona: str = "default",
        source: str = "user",
        params: dict | None = None,
    ) -> AgentTask:
        """Create a new agent task in RECEIVED status."""
        task = AgentTask(
            prompt=prompt,
            task_type=task_type,
            persona_name=persona,
            source=source,
            status=AgentTaskStatus.RECEIVED,
            result=params or {},
        )
        self.db.add(task)
        self.db.flush()
        self.db.refresh(task)
        logger.info("Created agent task %s (type=%s, persona=%s)", task.id, task_type, persona)
        return task

    def get_task(self, task_id: uuid.UUID) -> AgentTask | None:
        """Get a single task by ID."""
        return self.db.get(AgentTask, task_id)

    def list_tasks(
        self,
        status: str | None = None,
        persona: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AgentTask], int]:
        """List tasks with optional filters. Returns (tasks, total_count)."""
        query = self.db.query(AgentTask)
        if status:
            query = query.filter(AgentTask.status == status)
        if persona:
            query = query.filter(AgentTask.persona_name == persona)
        total = query.count()
        tasks = query.order_by(desc(AgentTask.created_at)).offset(offset).limit(limit).all()
        return tasks, total

    def cancel_task(self, task_id: uuid.UUID) -> AgentTask | None:
        """Cancel a task if not already terminal. Returns None if not found."""
        task = self.get_task(task_id)
        if task is None:
            return None
        if task.status in _TERMINAL_STATUSES:
            logger.warning("Cannot cancel task %s in terminal status %s", task_id, task.status)
            return task
        task.status = AgentTaskStatus.FAILED
        task.error_message = "Cancelled by user"
        task.completed_at = datetime.now(UTC)
        self.db.flush()
        logger.info("Cancelled task %s", task_id)
        return task

    def update_task_status(
        self,
        task_id: uuid.UUID | str,
        status: str,
        *,
        result: dict | None = None,
        error: str | None = None,
        cost: float | None = None,
        tokens: int | None = None,
        plan: list | None = None,
        persona_config: dict | None = None,
    ) -> AgentTask | None:
        """Update task status and associated fields.

        Automatically sets ``started_at`` on first non-RECEIVED status
        and ``completed_at`` on terminal statuses.
        """
        if isinstance(task_id, str):
            task_id = uuid.UUID(task_id)
        task = self.get_task(task_id)
        if task is None:
            return None

        task.status = status

        if result is not None:
            task.result = result
        if error is not None:
            task.error_message = error
        if cost is not None:
            task.cost_total = cost
        if tokens is not None:
            task.tokens_total = tokens
        if plan is not None:
            task.plan = plan
        if persona_config is not None:
            task.persona_config = persona_config

        # Lifecycle timestamps
        if status != AgentTaskStatus.RECEIVED and task.started_at is None:
            task.started_at = datetime.now(UTC)
        if status in _TERMINAL_STATUSES:
            task.completed_at = datetime.now(UTC)

        self.db.flush()
        return task


class AgentInsightService:
    """CRUD operations for agent insights."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_insight(
        self,
        task_id: uuid.UUID | str,
        insight_type: str,
        title: str,
        content: str,
        confidence: float,
        tags: list[str] | None = None,
        related_content_ids: list[int] | None = None,
        related_theme_ids: list[int] | None = None,
        metadata: dict | None = None,
    ) -> AgentInsight:
        """Store a generated insight."""
        if isinstance(task_id, str):
            task_id = uuid.UUID(task_id)
        insight = AgentInsight(
            task_id=task_id,
            insight_type=insight_type,
            title=title,
            content=content,
            confidence=confidence,
            tags=tags or [],
            related_content_ids=related_content_ids or [],
            related_theme_ids=related_theme_ids or [],
            metadata_=metadata or {},
        )
        self.db.add(insight)
        self.db.flush()
        self.db.refresh(insight)
        return insight

    def get_insight(self, insight_id: uuid.UUID) -> AgentInsight | None:
        """Get a single insight by ID."""
        return self.db.get(AgentInsight, insight_id)

    def list_insights(
        self,
        insight_type: str | None = None,
        since: datetime | None = None,
        persona: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AgentInsight], int]:
        """List insights with optional filters. Returns (insights, total_count).

        Filtering by persona requires a JOIN to agent_tasks.
        """
        query = self.db.query(AgentInsight)
        if persona:
            query = query.join(AgentTask, AgentInsight.task_id == AgentTask.id).filter(
                AgentTask.persona_name == persona
            )
        if insight_type:
            query = query.filter(AgentInsight.insight_type == insight_type)
        if since:
            query = query.filter(AgentInsight.created_at >= since)

        total = query.count()
        insights = query.order_by(desc(AgentInsight.created_at)).offset(offset).limit(limit).all()
        return insights, total


class ApprovalService:
    """CRUD operations for approval requests."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_request(self, request_id: uuid.UUID) -> ApprovalRequest | None:
        """Get a single approval request by ID."""
        return self.db.get(ApprovalRequest, request_id)

    def decide_request(
        self,
        request_id: uuid.UUID | str,
        approved: bool,
        reason: str | None = None,
    ) -> ApprovalRequest | None:
        """Approve or deny a pending request. Returns None if not found.

        Only PENDING requests can be decided.
        """
        if isinstance(request_id, str):
            request_id = uuid.UUID(request_id)
        request = self.get_request(request_id)
        if request is None:
            return None
        if request.status != ApprovalStatus.PENDING:
            logger.warning(
                "Cannot decide approval %s — already in status %s",
                request_id,
                request.status,
            )
            return request

        request.status = ApprovalStatus.APPROVED if approved else ApprovalStatus.DENIED
        request.decision_reason = reason
        request.decided_at = datetime.now(UTC)
        self.db.flush()
        logger.info(
            "Approval %s %s (reason: %s)",
            request_id,
            "approved" if approved else "denied",
            reason or "—",
        )
        return request

    def list_pending(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ApprovalRequest], int]:
        """List pending approval requests."""
        query = self.db.query(ApprovalRequest).filter(
            ApprovalRequest.status == ApprovalStatus.PENDING
        )
        total = query.count()
        requests = (
            query.order_by(desc(ApprovalRequest.created_at)).offset(offset).limit(limit).all()
        )
        return requests, total
