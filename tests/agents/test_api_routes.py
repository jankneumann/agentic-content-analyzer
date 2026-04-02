"""Tests for the agent API routes.

Uses FastAPI TestClient for request/response validation.
DB service calls are mocked to avoid requiring a live database.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.agent_routes import router


@pytest.fixture
def app() -> FastAPI:
    """Create a test FastAPI app with the agent router."""
    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Create a test client (no auth middleware for unit tests)."""
    return TestClient(app)


def _mock_task(**overrides):
    """Create a mock AgentTask."""
    task = MagicMock()
    task.id = overrides.get("id", uuid.uuid4())
    task.task_type = overrides.get("task_type", "research")
    task.status = overrides.get("status", "received")
    task.persona_name = overrides.get("persona_name", "default")
    task.prompt = overrides.get("prompt", "Test prompt")
    task.result = overrides.get("result")
    task.error_message = overrides.get("error_message")
    task.created_at = overrides.get("created_at", datetime.now(UTC))
    task.started_at = None
    task.completed_at = None
    task.cost_total = None
    task.tokens_total = None
    return task


# ============================================================================
# Task endpoints
# ============================================================================


class TestTaskEndpoints:
    """Test task submission and retrieval endpoints."""

    @patch("src.api.agent_routes.enqueue_queue_job")
    @patch("src.api.agent_routes.get_db")
    def test_submit_task(self, mock_get_db, mock_enqueue, client: TestClient):
        fake_task = _mock_task()
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.api.agent_routes.AgentTaskService") as mock_svc:
            mock_svc.return_value.create_task.return_value = fake_task
            mock_enqueue.return_value = (1, True)
            resp = client.post(
                "/api/v1/agent/task",
                json={"prompt": "What are the trends in AI agents?"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "task_id" in data
        assert data["status"] == "received"

    @patch("src.api.agent_routes.enqueue_queue_job")
    @patch("src.api.agent_routes.get_db")
    def test_submit_task_with_options(self, mock_get_db, mock_enqueue, client: TestClient):
        fake_task = _mock_task(task_type="analysis", persona_name="leadership")
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.api.agent_routes.AgentTaskService") as mock_svc:
            mock_svc.return_value.create_task.return_value = fake_task
            mock_enqueue.return_value = (1, True)
            resp = client.post(
                "/api/v1/agent/task",
                json={
                    "prompt": "Analyze enterprise AI adoption",
                    "task_type": "analysis",
                    "persona": "leadership",
                    "output": "executive_briefing",
                    "sources": ["arxiv", "scholar"],
                    "params": {"lookback_days": 7},
                },
            )

        assert resp.status_code == 200
        assert "task_id" in resp.json()

    def test_submit_task_empty_prompt(self, client: TestClient):
        resp = client.post(
            "/api/v1/agent/task",
            json={"prompt": ""},
        )
        assert resp.status_code == 422  # Validation error

    def test_submit_task_missing_prompt(self, client: TestClient):
        resp = client.post(
            "/api/v1/agent/task",
            json={},
        )
        assert resp.status_code == 422

    def test_get_task_not_found(self, client: TestClient):
        resp = client.get("/api/v1/agent/task/nonexistent-id")
        assert resp.status_code == 422  # Invalid UUID

    @patch("src.api.agent_routes.get_db")
    def test_get_task_valid_uuid_not_found(self, mock_get_db, client: TestClient):
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.api.agent_routes.AgentTaskService") as mock_svc:
            mock_svc.return_value.get_task.return_value = None
            resp = client.get(f"/api/v1/agent/task/{uuid.uuid4()}")

        assert resp.status_code == 404

    @patch("src.api.agent_routes.get_db")
    def test_list_tasks_empty(self, mock_get_db, client: TestClient):
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.api.agent_routes.AgentTaskService") as mock_svc:
            mock_svc.return_value.list_tasks.return_value = ([], 0)
            resp = client.get("/api/v1/agent/tasks")

        assert resp.status_code == 200

    @patch("src.api.agent_routes.get_db")
    def test_list_tasks_with_filters(self, mock_get_db, client: TestClient):
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.api.agent_routes.AgentTaskService") as mock_svc:
            mock_svc.return_value.list_tasks.return_value = ([], 0)
            resp = client.get(
                "/api/v1/agent/tasks?status=completed&persona=leadership&limit=10&offset=0"
            )

        assert resp.status_code == 200

    def test_cancel_task_invalid_uuid(self, client: TestClient):
        resp = client.delete("/api/v1/agent/task/nonexistent-id")
        assert resp.status_code == 422


# ============================================================================
# Insight endpoints
# ============================================================================


class TestInsightEndpoints:
    """Test insight listing and retrieval endpoints."""

    @patch("src.api.agent_routes.get_db")
    def test_list_insights_empty(self, mock_get_db, client: TestClient):
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.api.agent_routes.AgentInsightService") as mock_svc:
            mock_svc.return_value.list_insights.return_value = ([], 0)
            resp = client.get("/api/v1/agent/insights")

        assert resp.status_code == 200

    @patch("src.api.agent_routes.get_db")
    def test_list_insights_with_type_filter(self, mock_get_db, client: TestClient):
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.api.agent_routes.AgentInsightService") as mock_svc:
            mock_svc.return_value.list_insights.return_value = ([], 0)
            resp = client.get("/api/v1/agent/insights?insight_type=trend")

        assert resp.status_code == 200

    @patch("src.api.agent_routes.get_db")
    def test_list_insights_with_since_filter(self, mock_get_db, client: TestClient):
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.api.agent_routes.AgentInsightService") as mock_svc:
            mock_svc.return_value.list_insights.return_value = ([], 0)
            resp = client.get("/api/v1/agent/insights?since=2025-01-01T00:00:00")

        assert resp.status_code == 200

    def test_list_insights_invalid_since(self, client: TestClient):
        resp = client.get("/api/v1/agent/insights?since=not-a-date")
        assert resp.status_code == 422

    def test_get_insight_invalid_uuid(self, client: TestClient):
        resp = client.get("/api/v1/agent/insights/nonexistent-id")
        assert resp.status_code == 422


# ============================================================================
# Approval endpoints
# ============================================================================


class TestApprovalEndpoints:
    """Test approval handling endpoints."""

    @patch("src.api.agent_routes.get_db")
    def test_approve_not_found(self, mock_get_db, client: TestClient):
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.api.agent_routes.ApprovalService") as mock_svc:
            mock_svc.return_value.decide_request.return_value = None
            resp = client.post(
                f"/api/v1/agent/approval/{uuid.uuid4()}",
                json={"approved": True},
            )

        assert resp.status_code == 404

    @patch("src.api.agent_routes.get_db")
    def test_deny_not_found(self, mock_get_db, client: TestClient):
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.api.agent_routes.ApprovalService") as mock_svc:
            mock_svc.return_value.decide_request.return_value = None
            resp = client.post(
                f"/api/v1/agent/approval/{uuid.uuid4()}",
                json={"approved": False, "reason": "Too risky"},
            )

        assert resp.status_code == 404

    def test_approval_missing_body(self, client: TestClient):
        resp = client.post(f"/api/v1/agent/approval/{uuid.uuid4()}", json={})
        assert resp.status_code == 422


# ============================================================================
# Schedule endpoints
# ============================================================================


class TestScheduleEndpoints:
    """Test schedule listing endpoints."""

    def test_list_schedules(self, client: TestClient):
        resp = client.get("/api/v1/agent/schedules")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_enable_nonexistent_schedule(self, client: TestClient):
        resp = client.post("/api/v1/agent/schedules/nonexistent/enable")
        assert resp.status_code == 404

    def test_disable_nonexistent_schedule(self, client: TestClient):
        resp = client.post("/api/v1/agent/schedules/nonexistent/disable")
        assert resp.status_code == 404


# ============================================================================
# Persona endpoints
# ============================================================================


class TestPersonaEndpoints:
    """Test persona listing endpoint."""

    def test_list_personas(self, client: TestClient):
        resp = client.get("/api/v1/agent/personas")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
