"""Tests for theme analysis API endpoints."""

from unittest.mock import AsyncMock, patch

import pytest


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
        """Test getting latest when no analyses exist."""
        # Clear any existing analyses by making a fresh request
        response = client.get("/api/v1/themes/latest")

        assert response.status_code == 200
        # Either returns a result or a message saying none found
        data = response.json()
        assert "message" in data or "themes" in data


class TestListAnalyses:
    """Tests for GET /api/v1/themes endpoint."""

    def test_list_analyses_empty(self, client):
        """Test listing analyses returns list."""
        response = client.get("/api/v1/themes")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

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


class TestThemeAnalysisIntegration:
    """Integration tests for theme analysis with mocked LLM."""

    @pytest.mark.asyncio
    async def test_full_analysis_flow_mocked(self, client, sample_summaries):
        """Test full analysis flow with mocked theme analyzer."""
        from datetime import datetime

        from src.models.theme import ThemeAnalysisResult

        # Mock the theme analyzer to return a result
        mock_result = ThemeAnalysisResult(
            analysis_date=datetime.utcnow(),
            start_date=datetime(2025, 1, 1),
            end_date=datetime(2025, 1, 7),
            newsletter_count=2,
            newsletter_ids=[1, 2],
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
