"""Tests for job queue API endpoints.

Integration tests for:
- GET /api/v1/jobs with pagination edge cases
- GET /api/v1/jobs/history with filters, time parsing, and empty results
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from starlette.testclient import TestClient

from src.api.app import app
from src.models.jobs import JobHistoryItem, JobListItem, JobStatus


class TestJobListPaginationEdgeCases:
    """Tests for pagination edge cases in GET /api/v1/jobs endpoint."""

    @pytest.fixture
    def mock_list_jobs(self):
        """Create a mock for list_jobs that returns sample data."""
        sample_jobs = [
            JobListItem(
                id=1,
                entrypoint="summarize_content",
                status=JobStatus.QUEUED,
                progress=0,
                error=None,
                created_at=datetime.now(UTC),
                updated_at=None,
            ),
            JobListItem(
                id=2,
                entrypoint="summarize_content",
                status=JobStatus.COMPLETED,
                progress=100,
                error=None,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            ),
        ]
        return sample_jobs

    def test_page_size_zero_returns_422(self):
        """Test that page_size=0 is rejected with HTTP 422.

        FastAPI Query validation: page_size: int = Query(20, ge=1, le=100)
        page_size=0 fails the ge=1 (greater than or equal to 1) constraint.
        """
        client = TestClient(app)
        response = client.get("/api/v1/jobs", params={"page_size": 0})

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        # FastAPI returns validation error details
        errors = data["detail"]
        assert any(
            "page_size" in str(error).lower() or "greater than or equal" in str(error).lower()
            for error in errors
        )

    def test_page_size_negative_returns_422(self):
        """Test that negative page_size is rejected with HTTP 422.

        FastAPI Query validation: page_size: int = Query(20, ge=1, le=100)
        Negative values fail the ge=1 constraint.
        """
        client = TestClient(app)
        response = client.get("/api/v1/jobs", params={"page_size": -1})

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        errors = data["detail"]
        assert any(
            "page_size" in str(error).lower() or "greater than or equal" in str(error).lower()
            for error in errors
        )

    def test_page_size_large_negative_returns_422(self):
        """Test that large negative page_size is rejected with HTTP 422."""
        client = TestClient(app)
        response = client.get("/api/v1/jobs", params={"page_size": -100})

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_page_size_exceeds_max_returns_422(self):
        """Test that page_size > 100 is rejected with HTTP 422.

        FastAPI Query validation: page_size: int = Query(20, ge=1, le=100)
        Values above 100 fail the le=100 (less than or equal to 100) constraint.
        """
        client = TestClient(app)
        response = client.get("/api/v1/jobs", params={"page_size": 101})

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        errors = data["detail"]
        assert any(
            "page_size" in str(error).lower() or "less than or equal" in str(error).lower()
            for error in errors
        )

    def test_page_size_way_exceeds_max_returns_422(self):
        """Test that very large page_size values are rejected."""
        client = TestClient(app)
        response = client.get("/api/v1/jobs", params={"page_size": 1000})

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_page_size_minimum_valid(self, mock_list_jobs):
        """Test that page_size=1 (minimum valid) works correctly."""
        with patch(
            "src.api.job_routes.list_jobs",
            new_callable=AsyncMock,
            return_value=(mock_list_jobs[:1], 2),
        ):
            client = TestClient(app)
            response = client.get("/api/v1/jobs", params={"page_size": 1})

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "pagination" in data
        assert data["pagination"]["page_size"] == 1
        assert len(data["data"]) == 1

    def test_page_size_maximum_valid(self, mock_list_jobs):
        """Test that page_size=100 (maximum valid) works correctly."""
        with patch(
            "src.api.job_routes.list_jobs",
            new_callable=AsyncMock,
            return_value=(mock_list_jobs, 2),
        ):
            client = TestClient(app)
            response = client.get("/api/v1/jobs", params={"page_size": 100})

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "pagination" in data
        assert data["pagination"]["page_size"] == 100

    def test_page_size_default(self, mock_list_jobs):
        """Test that default page_size=20 is used when not specified."""
        with patch(
            "src.api.job_routes.list_jobs",
            new_callable=AsyncMock,
            return_value=(mock_list_jobs, 2),
        ):
            client = TestClient(app)
            response = client.get("/api/v1/jobs")

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["page_size"] == 20

    def test_page_number_zero_returns_422(self):
        """Test that page=0 is rejected with HTTP 422.

        FastAPI Query validation: page: int = Query(1, ge=1)
        page=0 fails the ge=1 constraint.
        """
        client = TestClient(app)
        response = client.get("/api/v1/jobs", params={"page": 0})

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_page_number_negative_returns_422(self):
        """Test that negative page number is rejected with HTTP 422."""
        client = TestClient(app)
        response = client.get("/api/v1/jobs", params={"page": -1})

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data


class TestJobListFiltering:
    """Tests for filtering in GET /api/v1/jobs endpoint."""

    @pytest.fixture
    def mock_jobs_by_status(self):
        """Create sample jobs with different statuses."""
        return [
            JobListItem(
                id=1,
                entrypoint="summarize_content",
                status=JobStatus.QUEUED,
                progress=0,
                error=None,
                created_at=datetime.now(UTC),
                updated_at=None,
            ),
            JobListItem(
                id=2,
                entrypoint="summarize_content",
                status=JobStatus.IN_PROGRESS,
                progress=50,
                error=None,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            ),
            JobListItem(
                id=3,
                entrypoint="summarize_content",
                status=JobStatus.COMPLETED,
                progress=100,
                error=None,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            ),
            JobListItem(
                id=4,
                entrypoint="summarize_content",
                status=JobStatus.FAILED,
                progress=25,
                error="Connection timeout",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            ),
        ]

    def test_filter_by_status_queued(self, mock_jobs_by_status):
        """Test filtering jobs by queued status."""
        queued_jobs = [j for j in mock_jobs_by_status if j.status == JobStatus.QUEUED]

        with patch(
            "src.api.job_routes.list_jobs",
            new_callable=AsyncMock,
            return_value=(queued_jobs, 1),
        ):
            client = TestClient(app)
            response = client.get("/api/v1/jobs", params={"status": "queued"})

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1
        assert all(job["status"] == "queued" for job in data["data"])

    def test_filter_by_status_failed(self, mock_jobs_by_status):
        """Test filtering jobs by failed status."""
        failed_jobs = [j for j in mock_jobs_by_status if j.status == JobStatus.FAILED]

        with patch(
            "src.api.job_routes.list_jobs",
            new_callable=AsyncMock,
            return_value=(failed_jobs, 1),
        ):
            client = TestClient(app)
            response = client.get("/api/v1/jobs", params={"status": "failed"})

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1
        assert data["data"][0]["status"] == "failed"
        assert data["data"][0]["error"] == "Connection timeout"

    def test_filter_by_entrypoint(self, mock_jobs_by_status):
        """Test filtering jobs by entrypoint."""
        with patch(
            "src.api.job_routes.list_jobs",
            new_callable=AsyncMock,
            return_value=(mock_jobs_by_status[:2], 2),
        ):
            client = TestClient(app)
            response = client.get("/api/v1/jobs", params={"entrypoint": "summarize_content"})

        assert response.status_code == 200
        data = response.json()
        assert all(job["entrypoint"] == "summarize_content" for job in data["data"])

    def test_combined_filters(self, mock_jobs_by_status):
        """Test combining status and entrypoint filters."""
        filtered = [
            j
            for j in mock_jobs_by_status
            if j.status == JobStatus.QUEUED and j.entrypoint == "summarize_content"
        ]

        with patch(
            "src.api.job_routes.list_jobs",
            new_callable=AsyncMock,
            return_value=(filtered, 1),
        ):
            client = TestClient(app)
            response = client.get(
                "/api/v1/jobs",
                params={"status": "queued", "entrypoint": "summarize_content"},
            )

        assert response.status_code == 200


class TestJobListPaginationOffset:
    """Tests for pagination offset calculation."""

    @pytest.fixture
    def mock_many_jobs(self):
        """Create multiple jobs for pagination testing."""
        return [
            JobListItem(
                id=i,
                entrypoint="summarize_content",
                status=JobStatus.COMPLETED,
                progress=100,
                error=None,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            for i in range(1, 51)  # 50 jobs
        ]

    def test_page_2_with_default_page_size(self, mock_many_jobs):
        """Test that page 2 correctly calculates offset as 20."""
        # Page 2 with page_size=20 means offset=20
        page_2_jobs = mock_many_jobs[20:40]

        with patch(
            "src.api.job_routes.list_jobs",
            new_callable=AsyncMock,
            return_value=(page_2_jobs, 50),
        ) as mock_list:
            client = TestClient(app)
            response = client.get("/api/v1/jobs", params={"page": 2})

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["page"] == 2
        # Verify list_jobs was called with correct offset
        mock_list.assert_called_once()
        call_kwargs = mock_list.call_args.kwargs
        assert call_kwargs["offset"] == 20  # (page-1) * page_size = (2-1) * 20

    def test_page_3_with_custom_page_size(self, mock_many_jobs):
        """Test that page 3 with page_size=10 calculates offset as 20."""
        page_3_jobs = mock_many_jobs[20:30]

        with patch(
            "src.api.job_routes.list_jobs",
            new_callable=AsyncMock,
            return_value=(page_3_jobs, 50),
        ) as mock_list:
            client = TestClient(app)
            response = client.get("/api/v1/jobs", params={"page": 3, "page_size": 10})

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["page"] == 3
        assert data["pagination"]["page_size"] == 10
        # Verify list_jobs was called with correct offset
        mock_list.assert_called_once()
        call_kwargs = mock_list.call_args.kwargs
        assert call_kwargs["offset"] == 20  # (page-1) * page_size = (3-1) * 10

    def test_pagination_response_structure(self, mock_many_jobs):
        """Test that pagination response includes correct fields."""
        with patch(
            "src.api.job_routes.list_jobs",
            new_callable=AsyncMock,
            return_value=(mock_many_jobs[:20], 50),
        ):
            client = TestClient(app)
            response = client.get("/api/v1/jobs")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "data" in data
        assert "pagination" in data
        assert "page" in data["pagination"]
        assert "page_size" in data["pagination"]
        assert "total" in data["pagination"]

        # Verify pagination values
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["page_size"] == 20
        assert data["pagination"]["total"] == 50


class TestJobListEmptyResults:
    """Tests for empty result handling."""

    def test_empty_results_returns_empty_list(self):
        """Test that empty results return empty data array."""
        with patch(
            "src.api.job_routes.list_jobs",
            new_callable=AsyncMock,
            return_value=([], 0),
        ):
            client = TestClient(app)
            response = client.get("/api/v1/jobs")

        assert response.status_code == 200
        data = response.json()
        assert data["data"] == []
        assert data["pagination"]["total"] == 0

    def test_empty_results_with_filter(self):
        """Test that filtering with no matches returns empty array."""
        with patch(
            "src.api.job_routes.list_jobs",
            new_callable=AsyncMock,
            return_value=([], 0),
        ):
            client = TestClient(app)
            response = client.get("/api/v1/jobs", params={"status": "failed"})

        assert response.status_code == 200
        data = response.json()
        assert data["data"] == []
        assert data["pagination"]["total"] == 0


# ============================================================================
# Job History Endpoint Tests (GET /api/v1/jobs/history)
# ============================================================================


class TestJobHistoryEndpoint:
    """Tests for GET /api/v1/jobs/history."""

    @pytest.fixture
    def sample_history(self):
        """Create sample job history items."""
        return [
            JobHistoryItem(
                id=1,
                entrypoint="summarize_content",
                task_label="Summarize",
                status=JobStatus.COMPLETED,
                content_id=42,
                description="AI Weekly: GPT-5 Announced",
                error=None,
                created_at=datetime.now(UTC),
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
            ),
            JobHistoryItem(
                id=2,
                entrypoint="ingest_content",
                task_label="Ingest",
                status=JobStatus.COMPLETED,
                content_id=None,
                description="Gmail ingestion",
                error=None,
                created_at=datetime.now(UTC),
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
            ),
        ]

    def test_history_default(self, sample_history):
        """Test history endpoint returns enriched data."""
        with patch(
            "src.api.job_routes.list_job_history",
            new_callable=AsyncMock,
            return_value=(sample_history, 2),
        ):
            client = TestClient(app)
            response = client.get("/api/v1/jobs/history")

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "pagination" in data
        assert len(data["data"]) == 2
        assert data["data"][0]["task_label"] == "Summarize"
        assert data["data"][0]["description"] == "AI Weekly: GPT-5 Announced"
        assert data["data"][1]["content_id"] is None

    def test_history_with_since_shorthand(self, sample_history):
        """Test history with since=7d shorthand."""
        with patch(
            "src.api.job_routes.list_job_history",
            new_callable=AsyncMock,
            return_value=(sample_history, 2),
        ) as mock_fn:
            client = TestClient(app)
            response = client.get("/api/v1/jobs/history", params={"since": "7d"})

        assert response.status_code == 200
        # Verify since was parsed and passed
        mock_fn.assert_called_once()
        call_kwargs = mock_fn.call_args.kwargs
        assert call_kwargs["since"] is not None

    def test_history_with_since_iso(self, sample_history):
        """Test history with ISO datetime since parameter."""
        with patch(
            "src.api.job_routes.list_job_history",
            new_callable=AsyncMock,
            return_value=(sample_history, 2),
        ) as mock_fn:
            client = TestClient(app)
            response = client.get(
                "/api/v1/jobs/history",
                params={"since": "2025-01-15T00:00:00+00:00"},
            )

        assert response.status_code == 200
        mock_fn.assert_called_once()
        call_kwargs = mock_fn.call_args.kwargs
        assert call_kwargs["since"] is not None

    def test_history_invalid_since_returns_400(self):
        """Test that invalid since format returns 400."""
        client = TestClient(app)
        response = client.get("/api/v1/jobs/history", params={"since": "invalid"})

        assert response.status_code == 400
        data = response.json()
        assert "since" in data["detail"].lower()

    def test_history_with_filters(self, sample_history):
        """Test history with status and entrypoint filters."""
        filtered = [sample_history[0]]
        with patch(
            "src.api.job_routes.list_job_history",
            new_callable=AsyncMock,
            return_value=(filtered, 1),
        ) as mock_fn:
            client = TestClient(app)
            response = client.get(
                "/api/v1/jobs/history",
                params={"status": "completed", "entrypoint": "summarize_content"},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1
        mock_fn.assert_called_once()
        call_kwargs = mock_fn.call_args.kwargs
        assert call_kwargs["status"] == JobStatus.COMPLETED
        assert call_kwargs["entrypoint"] == "summarize_content"

    def test_history_empty_results(self):
        """Test history with no results."""
        with patch(
            "src.api.job_routes.list_job_history",
            new_callable=AsyncMock,
            return_value=([], 0),
        ):
            client = TestClient(app)
            response = client.get("/api/v1/jobs/history")

        assert response.status_code == 200
        data = response.json()
        assert data["data"] == []
        assert data["pagination"]["total"] == 0

    def test_history_pagination(self, sample_history):
        """Test history pagination parameters."""
        with patch(
            "src.api.job_routes.list_job_history",
            new_callable=AsyncMock,
            return_value=(sample_history[:1], 10),
        ) as mock_fn:
            client = TestClient(app)
            response = client.get(
                "/api/v1/jobs/history",
                params={"page": 2, "page_size": 1},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["page"] == 2
        assert data["pagination"]["page_size"] == 1
        assert data["pagination"]["total"] == 10
        # Verify offset calculation
        mock_fn.assert_called_once()
        call_kwargs = mock_fn.call_args.kwargs
        assert call_kwargs["offset"] == 1  # (2-1) * 1

    def test_history_default_page_size(self, sample_history):
        """Test history default page_size is 50."""
        with patch(
            "src.api.job_routes.list_job_history",
            new_callable=AsyncMock,
            return_value=(sample_history, 2),
        ):
            client = TestClient(app)
            response = client.get("/api/v1/jobs/history")

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["page_size"] == 50
