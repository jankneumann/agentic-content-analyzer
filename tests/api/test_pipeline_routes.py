"""Tests for pipeline API routes.

Covers POST /api/v1/pipeline/run endpoint for triggering pipeline jobs.
SSE status endpoint is excluded (streaming responses are hard to unit test).

Note: The autouse ``api_test_env`` fixture in tests/api/conftest.py sets
ADMIN_API_KEY="test-admin-key" and clears the settings cache, so the auth
middleware enforces authentication.  All requests must include the
X-Admin-Key header.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from starlette.testclient import TestClient

from src.api.app import app

# Must match the value set by the autouse api_test_env fixture in conftest.py
_AUTH_HEADERS = {"X-Admin-Key": "test-admin-key"}


class TestTriggerPipelineRun:
    """Tests for POST /api/v1/pipeline/run."""

    @patch("src.queue.setup.enqueue_queue_job", new_callable=AsyncMock)
    def test_trigger_daily_pipeline(self, mock_enqueue: AsyncMock):
        """POST /run with daily returns job_id, message, and pipeline_type."""
        mock_enqueue.return_value = (42, True)
        client = TestClient(app)

        resp = client.post(
            "/api/v1/pipeline/run",
            json={"pipeline_type": "daily"},
            headers=_AUTH_HEADERS,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["job_id"] == 42
        assert data["pipeline_type"] == "daily"
        assert "daily" in data["message"]

        # Verify enqueue was called with correct entrypoint and payload
        mock_enqueue.assert_awaited_once()
        call_args = mock_enqueue.call_args
        assert call_args[0][0] == "run_pipeline"
        assert call_args[0][1]["pipeline_type"] == "daily"

    @patch("src.queue.setup.enqueue_queue_job", new_callable=AsyncMock)
    def test_trigger_weekly_pipeline(self, mock_enqueue: AsyncMock):
        """POST /run with weekly returns correct pipeline_type."""
        mock_enqueue.return_value = (99, True)
        client = TestClient(app)

        resp = client.post(
            "/api/v1/pipeline/run",
            json={"pipeline_type": "weekly"},
            headers=_AUTH_HEADERS,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["job_id"] == 99
        assert data["pipeline_type"] == "weekly"
        assert "weekly" in data["message"]

    @patch("src.queue.setup.enqueue_queue_job", new_callable=AsyncMock)
    def test_trigger_invalid_pipeline_type_returns_422(self, mock_enqueue: AsyncMock):
        """POST /run with invalid pipeline_type returns 422."""
        client = TestClient(app)

        resp = client.post(
            "/api/v1/pipeline/run",
            json={"pipeline_type": "monthly"},
            headers=_AUTH_HEADERS,
        )

        assert resp.status_code == 422
        data = resp.json()
        assert "detail" in data
        mock_enqueue.assert_not_awaited()

    @patch("src.queue.setup.enqueue_queue_job", new_callable=AsyncMock)
    def test_trigger_pipeline_defaults_to_daily(self, mock_enqueue: AsyncMock):
        """POST /run with empty body defaults pipeline_type to daily."""
        mock_enqueue.return_value = (1, True)
        client = TestClient(app)

        resp = client.post(
            "/api/v1/pipeline/run",
            json={},
            headers=_AUTH_HEADERS,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["pipeline_type"] == "daily"

        call_args = mock_enqueue.call_args
        assert call_args[0][1]["pipeline_type"] == "daily"
