"""Tests for theme analysis API endpoints.

Tests cover DB-persisted theme analysis routes: POST /analyze, GET /analysis/{id},
GET /latest, and GET /themes (list). The client fixture provides a DB session
via patched get_db, so all records are written to the test database with
transaction rollback after each test.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from src.models.theme import AnalysisStatus, ThemeAnalysis, ThemeAnalysisResult


class TestAnalyzeThemes:
    """Tests for POST /api/v1/themes/analyze endpoint."""

    def test_analyze_themes_returns_queued(self, client):
        """Test triggering theme analysis returns queued status."""
        response = client.post(
            "/api/v1/themes/analyze",
            json={"max_themes": 10, "min_newsletters": 2},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "queued"
        assert data["analysis_id"] is not None
        assert "started" in data["message"].lower()

    def test_analyze_themes_with_date_range(self, client):
        """Test triggering theme analysis with custom date range."""
        response = client.post(
            "/api/v1/themes/analyze",
            json={
                "start_date": "2025-01-01T00:00:00",
                "end_date": "2025-01-07T23:59:59",
                "max_themes": 5,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "queued"
        assert "2025-01-01" in data["message"]
        assert "2025-01-07" in data["message"]

    def test_analyze_themes_invalid_date_range(self, client):
        """Test invalid date range (start > end) returns 400."""
        response = client.post(
            "/api/v1/themes/analyze",
            json={
                "start_date": "2025-01-15T00:00:00",
                "end_date": "2025-01-01T00:00:00",
            },
        )

        assert response.status_code == 400
        assert "start_date must be before end_date" in response.json()["detail"]

    def test_analyze_themes_with_all_parameters(self, client):
        """Test triggering theme analysis with all parameters."""
        response = client.post(
            "/api/v1/themes/analyze",
            json={
                "max_themes": 20,
                "min_newsletters": 3,
                "relevance_threshold": 0.5,
                "include_historical_context": False,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "queued"

    def test_analyze_themes_validates_max_themes(self, client):
        """Test max_themes validation (1-50)."""
        # Too high
        response = client.post(
            "/api/v1/themes/analyze",
            json={"max_themes": 100},
        )
        assert response.status_code == 422  # Validation error

        # Too low
        response = client.post(
            "/api/v1/themes/analyze",
            json={"max_themes": 0},
        )
        assert response.status_code == 422

    def test_analysis_creates_db_record(self, client, db_session):
        """After POST, verify a ThemeAnalysis record exists in DB.

        Note: Background tasks run synchronously in TestClient, so by the time
        we query the record its status may have advanced beyond QUEUED.
        """
        response = client.post(
            "/api/v1/themes/analyze",
            json={"max_themes": 10},
        )

        assert response.status_code == 200
        analysis_id = response.json()["analysis_id"]

        # Query the DB directly to verify the record was persisted
        record = db_session.query(ThemeAnalysis).filter(ThemeAnalysis.id == analysis_id).first()
        assert record is not None
        # Background tasks run synchronously in TestClient, so status may
        # have advanced from QUEUED to RUNNING, COMPLETED, or FAILED.
        assert record.status in (
            AnalysisStatus.QUEUED,
            AnalysisStatus.RUNNING,
            AnalysisStatus.COMPLETED,
            AnalysisStatus.FAILED,
        )
        assert record.start_date is not None
        assert record.end_date is not None
        assert record.created_at is not None


class TestGetAnalysisStatus:
    """Tests for GET /api/v1/themes/analysis/{id} endpoint."""

    def test_get_analysis_not_found(self, client):
        """Test getting non-existent analysis returns 404."""
        response = client.get("/api/v1/themes/analysis/99999")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_analysis_status_queued(self, client):
        """Test getting status of queued analysis."""
        # First trigger an analysis
        create_response = client.post(
            "/api/v1/themes/analyze",
            json={"max_themes": 5},
        )
        analysis_id = create_response.json()["analysis_id"]

        # Check status immediately (should be queued or running)
        response = client.get(f"/api/v1/themes/analysis/{analysis_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["queued", "running", "completed"]


class TestGetLatestAnalysis:
    """Tests for GET /api/v1/themes/latest endpoint."""

    def test_get_latest_no_analyses(self, client):
        """Test getting latest when no completed analyses exist."""
        response = client.get("/api/v1/themes/latest")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "No completed analyses found"


class TestListAnalyses:
    """Tests for GET /api/v1/themes endpoint."""

    def test_list_analyses_empty(self, client):
        """Test listing analyses returns empty list when none exist."""
        response = client.get("/api/v1/themes")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_list_analyses_with_limit(self, client):
        """Test listing analyses with limit parameter."""
        response = client.get("/api/v1/themes?limit=5")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) <= 5

    def test_list_analyses_after_triggering(self, client):
        """Test listing analyses shows triggered analysis."""
        # Trigger an analysis
        create_response = client.post(
            "/api/v1/themes/analyze",
            json={"max_themes": 5},
        )
        analysis_id = create_response.json()["analysis_id"]

        # List should include the new analysis
        response = client.get("/api/v1/themes")

        assert response.status_code == 200
        data = response.json()
        analysis_ids = [a["id"] for a in data]
        assert analysis_id in analysis_ids

    def test_list_supports_offset(self, client, db_session):
        """Test listing analyses with offset skips records."""
        now = datetime.now(UTC)
        # Create 3 analyses directly in DB
        for i in range(3):
            record = ThemeAnalysis(
                status=AnalysisStatus.QUEUED,
                analysis_date=now - timedelta(hours=i),
                start_date=now - timedelta(days=7),
                end_date=now,
                created_at=now - timedelta(hours=i),
            )
            db_session.add(record)
        db_session.commit()

        # Get all
        all_response = client.get("/api/v1/themes?limit=10")
        all_data = all_response.json()
        assert len(all_data) == 3

        # Get with offset=1 — should skip the first (most recent) record
        offset_response = client.get("/api/v1/themes?limit=10&offset=1")
        offset_data = offset_response.json()
        assert len(offset_data) == 2

        # The offset result should not contain the first record from the full list
        all_ids = [a["id"] for a in all_data]
        offset_ids = [a["id"] for a in offset_data]
        assert all_ids[0] not in offset_ids
        assert offset_ids == all_ids[1:]


class TestResponseFieldNames:
    """Tests verifying response uses content_count/content_ids, not legacy newsletter_* names."""

    def test_response_uses_content_field_names(self, client, db_session):
        """Insert a completed ThemeAnalysis, GET /latest, verify content_count and content_ids."""
        now = datetime.now(UTC)
        record = ThemeAnalysis(
            status=AnalysisStatus.COMPLETED,
            analysis_date=now,
            start_date=now - timedelta(days=7),
            end_date=now,
            content_count=5,
            content_ids=[10, 20, 30, 40, 50],
            themes=[],
            total_themes=0,
            emerging_themes_count=0,
            agent_framework="claude",
            model_used="claude-sonnet-4-5",
            processing_time_seconds=2.5,
            token_usage=500,
            cross_theme_insights=["insight1"],
            created_at=now,
        )
        db_session.add(record)
        db_session.commit()

        response = client.get("/api/v1/themes/latest")

        assert response.status_code == 200
        data = response.json()

        # Verify new field names are present
        assert "content_count" in data
        assert "content_ids" in data
        assert data["content_count"] == 5
        assert data["content_ids"] == [10, 20, 30, 40, 50]

        # Verify legacy field names are NOT present
        assert "newsletter_count" not in data
        assert "newsletter_ids" not in data

    def test_latest_returns_most_recent_completed(self, client, db_session):
        """Insert multiple records with different statuses and dates, verify latest returns most recent completed."""
        now = datetime.now(UTC)

        # Older completed analysis
        older = ThemeAnalysis(
            status=AnalysisStatus.COMPLETED,
            analysis_date=now - timedelta(days=3),
            start_date=now - timedelta(days=10),
            end_date=now - timedelta(days=3),
            content_count=2,
            content_ids=[1, 2],
            themes=[],
            total_themes=1,
            emerging_themes_count=0,
            top_theme="Older Theme",
            agent_framework="claude",
            model_used="claude-sonnet-4-5",
            created_at=now - timedelta(days=3),
        )

        # Newer completed analysis
        newer = ThemeAnalysis(
            status=AnalysisStatus.COMPLETED,
            analysis_date=now - timedelta(days=1),
            start_date=now - timedelta(days=8),
            end_date=now - timedelta(days=1),
            content_count=4,
            content_ids=[1, 2, 3, 4],
            themes=[],
            total_themes=3,
            emerging_themes_count=1,
            top_theme="Newer Theme",
            agent_framework="claude",
            model_used="claude-sonnet-4-5",
            created_at=now - timedelta(days=1),
        )

        # A queued analysis (most recent but not completed — should be skipped)
        queued = ThemeAnalysis(
            status=AnalysisStatus.QUEUED,
            analysis_date=now,
            start_date=now - timedelta(days=7),
            end_date=now,
            created_at=now,
        )

        # A failed analysis (also should be skipped)
        failed = ThemeAnalysis(
            status=AnalysisStatus.FAILED,
            analysis_date=now - timedelta(hours=6),
            start_date=now - timedelta(days=7),
            end_date=now,
            error_message="Something went wrong",
            created_at=now - timedelta(hours=6),
        )

        db_session.add_all([older, newer, queued, failed])
        db_session.commit()

        response = client.get("/api/v1/themes/latest")

        assert response.status_code == 200
        data = response.json()

        # Should return the newer completed analysis (not older, not queued, not failed)
        assert data["top_theme"] == "Newer Theme"
        assert data["content_count"] == 4
        assert data["total_themes"] == 3


class TestThemeAnalysisIntegration:
    """Integration tests for theme analysis with mocked LLM."""

    @pytest.mark.asyncio
    async def test_full_analysis_flow_mocked(self, client, sample_summaries):
        """Test full analysis flow with mocked theme analyzer."""
        # Mock the theme analyzer to return a result
        mock_result = ThemeAnalysisResult(
            analysis_date=datetime.now(UTC),
            start_date=datetime(2025, 1, 1, tzinfo=UTC),
            end_date=datetime(2025, 1, 7, tzinfo=UTC),
            content_count=2,
            content_ids=[1, 2],
            themes=[],
            total_themes=0,
            emerging_themes_count=0,
            top_theme=None,
            processing_time_seconds=1.0,
            token_usage=100,
            model_used="claude-sonnet-4-5",
            model_version=None,
            agent_framework="claude",
            cross_theme_insights=[],
        )

        with patch(
            "src.processors.theme_analyzer.ThemeAnalyzer.analyze_themes",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            # Trigger analysis
            response = client.post(
                "/api/v1/themes/analyze",
                json={"max_themes": 10},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "queued"
