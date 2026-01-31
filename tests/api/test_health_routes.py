"""Tests for health and readiness endpoints."""

from __future__ import annotations

from unittest.mock import patch

from starlette.testclient import TestClient

from src.api.app import app


class TestHealthEndpoint:
    """Tests for GET /health."""

    def test_health_returns_200(self):
        """Health endpoint should always return 200."""
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "newsletter-aggregator"


class TestReadinessEndpoint:
    """Tests for GET /ready."""

    @patch("src.api.health_routes.settings")
    def test_ready_returns_200_when_all_checks_pass(self, mock_settings):
        """Readiness should return 200 when DB is reachable."""
        mock_settings.health_check_timeout_seconds = 5

        with patch(
            "src.storage.database.health_check",
            return_value=True,
        ):
            client = TestClient(app)
            response = client.get("/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["checks"]["database"] == "ok"

    @patch("src.api.health_routes.settings")
    def test_ready_returns_503_when_db_unavailable(self, mock_settings):
        """Readiness should return 503 when DB is unreachable."""
        mock_settings.health_check_timeout_seconds = 5

        with patch(
            "src.storage.database.health_check",
            side_effect=Exception("Connection refused"),
        ):
            client = TestClient(app)
            response = client.get("/ready")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["checks"]["database"] == "unavailable"

    @patch("src.api.health_routes.settings")
    def test_ready_returns_503_when_db_degraded(self, mock_settings):
        """Readiness should return 503 when DB returns False."""
        mock_settings.health_check_timeout_seconds = 5

        with patch(
            "src.storage.database.health_check",
            return_value=False,
        ):
            client = TestClient(app)
            response = client.get("/ready")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["checks"]["database"] == "degraded"

    @patch("src.api.health_routes.settings")
    def test_ready_includes_queue_check(self, mock_settings):
        """Readiness should include queue connectivity status."""
        mock_settings.health_check_timeout_seconds = 5

        with patch(
            "src.storage.database.health_check",
            return_value=True,
        ):
            client = TestClient(app)
            response = client.get("/ready")

        data = response.json()
        # Queue check should be present (may be not_connected, not_configured, or ok)
        assert "queue" in data["checks"]
