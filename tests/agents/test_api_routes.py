"""Tests for the agent API routes.

Uses FastAPI TestClient for request/response validation.
All endpoints currently return stub responses; these tests verify
routing, input validation, and response shape.
"""

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


# ============================================================================
# Task endpoints
# ============================================================================


class TestTaskEndpoints:
    """Test task submission and retrieval endpoints."""

    def test_submit_task(self, client: TestClient):
        resp = client.post(
            "/api/v1/agent/task",
            json={"prompt": "What are the trends in AI agents?"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "task_id" in data
        assert data["status"] == "received"

    def test_submit_task_with_options(self, client: TestClient):
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
        assert resp.status_code == 404

    def test_list_tasks_empty(self, client: TestClient):
        resp = client.get("/api/v1/agent/tasks")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_tasks_with_filters(self, client: TestClient):
        resp = client.get("/api/v1/agent/tasks?status=completed&persona=leadership&limit=10&offset=0")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_cancel_task_not_found(self, client: TestClient):
        resp = client.delete("/api/v1/agent/task/nonexistent-id")
        assert resp.status_code == 404


# ============================================================================
# Insight endpoints
# ============================================================================


class TestInsightEndpoints:
    """Test insight listing and retrieval endpoints."""

    def test_list_insights_empty(self, client: TestClient):
        resp = client.get("/api/v1/agent/insights")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_insights_with_type_filter(self, client: TestClient):
        resp = client.get("/api/v1/agent/insights?insight_type=trend")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_insights_with_since_filter(self, client: TestClient):
        resp = client.get("/api/v1/agent/insights?since=2025-01-01T00:00:00")
        assert resp.status_code == 200

    def test_list_insights_invalid_since(self, client: TestClient):
        resp = client.get("/api/v1/agent/insights?since=not-a-date")
        assert resp.status_code == 422

    def test_get_insight_not_found(self, client: TestClient):
        resp = client.get("/api/v1/agent/insights/nonexistent-id")
        assert resp.status_code == 404


# ============================================================================
# Approval endpoints
# ============================================================================


class TestApprovalEndpoints:
    """Test approval handling endpoints."""

    def test_approve_not_found(self, client: TestClient):
        resp = client.post(
            "/api/v1/agent/approval/nonexistent-id",
            json={"approved": True},
        )
        assert resp.status_code == 404

    def test_deny_not_found(self, client: TestClient):
        resp = client.post(
            "/api/v1/agent/approval/nonexistent-id",
            json={"approved": False, "reason": "Too risky"},
        )
        assert resp.status_code == 404

    def test_approval_missing_body(self, client: TestClient):
        resp = client.post("/api/v1/agent/approval/some-id", json={})
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

    def test_enable_schedule(self, client: TestClient):
        resp = client.post("/api/v1/agent/schedules/some-id/enable")
        assert resp.status_code == 200
        assert resp.json()["enabled"] is True

    def test_disable_schedule(self, client: TestClient):
        resp = client.post("/api/v1/agent/schedules/some-id/disable")
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False


# ============================================================================
# Persona endpoints
# ============================================================================


class TestPersonaEndpoints:
    """Test persona listing endpoint."""

    def test_list_personas(self, client: TestClient):
        resp = client.get("/api/v1/agent/personas")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
