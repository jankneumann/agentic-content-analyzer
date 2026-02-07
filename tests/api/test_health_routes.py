"""Tests for health and readiness endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from starlette.testclient import TestClient

from src.api.app import app
from src.api.health_routes import _check_backup_recency


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
        mock_settings.database_provider = "local"
        mock_settings.railway_backup_enabled = False

        with patch(
            "src.storage.database.health_check",
            return_value=True,
        ):
            client = TestClient(app)
            response = client.get("/ready")

        data = response.json()
        # Queue check should be present (may be not_connected, not_configured, or ok)
        assert "queue" in data["checks"]

    @patch("src.api.health_routes.settings")
    def test_ready_includes_backup_check_for_railway(self, mock_settings):
        """Readiness should include backup status when using Railway provider."""
        mock_settings.health_check_timeout_seconds = 5
        mock_settings.database_provider = "railway"
        mock_settings.railway_backup_enabled = True

        with (
            patch("src.storage.database.health_check", return_value=True),
            patch(
                "src.api.health_routes._check_backup_recency",
                return_value="ok",
            ),
        ):
            client = TestClient(app)
            response = client.get("/ready")

        data = response.json()
        assert data["checks"]["backup"] == "ok"

    @patch("src.api.health_routes.settings")
    def test_ready_excludes_backup_check_for_non_railway(self, mock_settings):
        """Readiness should not include backup check for non-Railway providers."""
        mock_settings.health_check_timeout_seconds = 5
        mock_settings.database_provider = "local"
        mock_settings.railway_backup_enabled = True

        with patch("src.storage.database.health_check", return_value=True):
            client = TestClient(app)
            response = client.get("/ready")

        data = response.json()
        assert "backup" not in data["checks"]

    @patch("src.api.health_routes.settings")
    def test_ready_excludes_backup_when_disabled(self, mock_settings):
        """Readiness should not include backup check when backups are disabled."""
        mock_settings.health_check_timeout_seconds = 5
        mock_settings.database_provider = "railway"
        mock_settings.railway_backup_enabled = False

        with patch("src.storage.database.health_check", return_value=True):
            client = TestClient(app)
            response = client.get("/ready")

        data = response.json()
        assert "backup" not in data["checks"]

    @patch("src.api.health_routes.settings")
    def test_ready_backup_check_handles_failure(self, mock_settings):
        """Backup check failure should not affect overall readiness."""
        mock_settings.health_check_timeout_seconds = 5
        mock_settings.database_provider = "railway"
        mock_settings.railway_backup_enabled = True

        with (
            patch("src.storage.database.health_check", return_value=True),
            patch(
                "src.api.health_routes._check_backup_recency",
                side_effect=Exception("pg_cron not available"),
            ),
        ):
            client = TestClient(app)
            response = client.get("/ready")

        data = response.json()
        # Backup check failure should not cause 503 (it's informational)
        assert response.status_code == 200
        assert data["checks"]["backup"] == "unknown"


class TestCheckBackupRecency:
    """Tests for _check_backup_recency helper function."""

    @patch("src.storage.database.get_engine")
    def test_returns_not_configured_when_no_cron_schema(self, mock_get_engine):
        """Should return 'not_configured' when cron schema doesn't exist."""
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None  # No cron.job_run_details table
        mock_conn.execute.return_value = mock_result
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn
        mock_get_engine.return_value = mock_engine

        assert _check_backup_recency() == "not_configured"

    @patch("src.storage.database.get_engine")
    def test_returns_no_history_when_no_runs(self, mock_get_engine):
        """Should return 'no_history' when no backup runs exist."""
        mock_conn = MagicMock()

        # First call: cron schema exists
        schema_result = MagicMock()
        schema_result.fetchone.return_value = (1,)

        # Second call: no backup runs
        runs_result = MagicMock()
        runs_result.fetchone.return_value = None

        mock_conn.execute.side_effect = [schema_result, runs_result]
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn
        mock_get_engine.return_value = mock_engine

        assert _check_backup_recency() == "no_history"

    @patch("src.api.health_routes.settings")
    @patch("src.storage.database.get_engine")
    def test_returns_ok_for_recent_backup(self, mock_get_engine, mock_settings):
        """Should return 'ok' when last backup was within threshold."""
        mock_settings.railway_backup_staleness_hours = 48
        mock_conn = MagicMock()

        schema_result = MagicMock()
        schema_result.fetchone.return_value = (1,)

        # Last backup was 6 hours ago (well within 48h threshold)
        recent_time = datetime.now(UTC) - timedelta(hours=6)
        runs_result = MagicMock()
        runs_result.fetchone.return_value = (recent_time,)

        mock_conn.execute.side_effect = [schema_result, runs_result]
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn
        mock_get_engine.return_value = mock_engine

        assert _check_backup_recency() == "ok"

    @patch("src.api.health_routes.settings")
    @patch("src.storage.database.get_engine")
    def test_returns_stale_for_old_backup(self, mock_get_engine, mock_settings):
        """Should return 'stale' when last backup exceeds threshold."""
        mock_settings.railway_backup_staleness_hours = 48
        mock_conn = MagicMock()

        schema_result = MagicMock()
        schema_result.fetchone.return_value = (1,)

        # Last backup was 3 days ago (exceeds 48h threshold)
        old_time = datetime.now(UTC) - timedelta(days=3)
        runs_result = MagicMock()
        runs_result.fetchone.return_value = (old_time,)

        mock_conn.execute.side_effect = [schema_result, runs_result]
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn
        mock_get_engine.return_value = mock_engine

        assert _check_backup_recency() == "stale"

    @patch("src.storage.database.get_engine")
    def test_returns_not_configured_on_engine_error(self, mock_get_engine):
        """Should return 'not_configured' when engine creation fails."""
        mock_get_engine.side_effect = Exception("No database configured")

        assert _check_backup_recency() == "not_configured"
