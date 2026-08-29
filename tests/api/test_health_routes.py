"""Tests for health and readiness endpoints."""

from __future__ import annotations

from unittest.mock import patch

from starlette.testclient import TestClient

from src.api.app import app
from src.api.health_routes import _check_backup_recency, _release_identity

SHA = "a" * 40


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
        assert {"revision", "revision_source"} <= data.keys()

    @patch("src.api.health_routes._release_identity")
    def test_health_exposes_observed_release_identity(self, release_identity):
        release_identity.return_value = (SHA, "railway_commit_sha")

        response = TestClient(app).get("/health")

        assert response.json()["revision"] == SHA
        assert response.json()["revision_source"] == "railway_commit_sha"


class TestReleaseIdentity:
    def test_railway_commit_sha_is_authoritative(self):
        assert _release_identity(
            {
                "RAILWAY_GIT_COMMIT_SHA": SHA,
                "GITHUB_SHA": "b" * 40,
            }
        ) == (SHA, "railway_commit_sha")

    def test_github_sha_is_used_when_railway_metadata_is_absent(self):
        assert _release_identity({"GITHUB_SHA": SHA, "GITHUB_ACTIONS": "true"}) == (
            "unavailable",
            "unavailable",
        )

    def test_runtime_github_sha_without_actions_context_is_untrusted(self) -> None:
        assert _release_identity({"GITHUB_SHA": SHA}) == (
            "unavailable",
            "unavailable",
        )

    def test_malformed_platform_revision_fails_closed(self):
        assert _release_identity(
            {
                "RAILWAY_GIT_COMMIT_SHA": "not-a-sha",
                "GITHUB_SHA": SHA,
            }
        ) == ("unavailable", "unavailable")

    def test_runtime_override_cannot_claim_a_release_revision(self):
        assert _release_identity({"ACA_RELEASE_REVISION": SHA}) == (
            "development",
            "local_development",
        )


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
    def test_ready_includes_backup_status_regardless_of_database_provider(self, mock_settings):
        """The old check was gated on `database_provider == "railway"`, so it never
        ran anywhere else — including on the self-hosted host this project is
        migrating to, where there is no managed PITR to fall back on and the check
        matters most. Backup freshness has nothing to do with the database
        provider."""
        mock_settings.health_check_timeout_seconds = 5
        mock_settings.database_provider = "local"
        mock_settings.backup_monitoring_enabled = True
        mock_settings.backup_staleness_hours = 48

        with (
            patch("src.storage.database.health_check", return_value=True),
            patch("src.api.health_routes._check_backup_recency", return_value="ok"),
        ):
            response = TestClient(app).get("/ready")

        assert response.json()["checks"]["backup"] == "ok"

    @patch("src.api.health_routes.settings")
    def test_ready_excludes_backup_when_monitoring_is_disabled(self, mock_settings):
        """The disable decision comes from the provider-neutral setting."""
        mock_settings.health_check_timeout_seconds = 5
        mock_settings.database_provider = "railway"
        mock_settings.backup_monitoring_enabled = False

        with patch("src.storage.database.health_check", return_value=True):
            response = TestClient(app).get("/ready")

        assert "backup" not in response.json()["checks"]

    @patch("src.api.health_routes.settings")
    def test_ready_backup_check_handles_failure(self, mock_settings):
        """Backup check failure must not affect overall readiness."""
        mock_settings.health_check_timeout_seconds = 5
        mock_settings.database_provider = "local"
        mock_settings.backup_monitoring_enabled = True
        mock_settings.backup_staleness_hours = 48

        with (
            patch("src.storage.database.health_check", return_value=True),
            patch(
                "src.api.health_routes._check_backup_recency",
                side_effect=Exception("backup target unreachable"),
            ),
        ):
            response = TestClient(app).get("/ready")

        assert response.status_code == 200
        assert response.json()["checks"]["backup"] == "unknown"

    @patch("src.api.health_routes.settings")
    def test_stale_backup_does_not_make_the_service_not_ready(self, mock_settings):
        """Pulling an instance out of the load balancer over a stale backup turns a
        backup problem into a serving outage. The durable alert is what makes it
        actionable; readiness is not."""
        mock_settings.health_check_timeout_seconds = 5
        mock_settings.database_provider = "local"
        mock_settings.backup_monitoring_enabled = True
        mock_settings.backup_staleness_hours = 48

        with (
            patch("src.storage.database.health_check", return_value=True),
            patch("src.api.health_routes._check_backup_recency", return_value="stale"),
        ):
            response = TestClient(app).get("/ready")

        assert response.status_code == 200
        assert response.json()["status"] == "ready"
        assert response.json()["checks"]["backup"] == "stale"

    @patch("src.api.health_routes.settings")
    def test_backup_check_survives_a_broken_database_layer(self, mock_settings):
        """`loop` was bound at the top of the database try block and used by the
        backup check far below. If the import there raised, `loop` was unbound and
        the backup check raised NameError — swallowed by its own except into
        "unknown". The backup monitor went dark at exactly the moment something was
        already wrong."""
        mock_settings.health_check_timeout_seconds = 5
        mock_settings.database_provider = "local"
        mock_settings.backup_monitoring_enabled = True
        mock_settings.backup_staleness_hours = 48

        with (
            patch(
                "src.storage.database.health_check",
                side_effect=RuntimeError("database layer is broken"),
            ),
            patch("src.api.health_routes._check_backup_recency", return_value="stale") as check,
        ):
            response = TestClient(app).get("/ready")

        assert check.called, "the backup check did not run when the database check raised"
        assert response.json()["checks"]["backup"] == "stale"
        assert response.json()["checks"]["database"] == "unavailable"

    @patch("src.api.health_routes.settings")
    def test_the_staleness_warning_names_the_setting_that_controls_it(self, mock_settings, caplog):
        """The old text claimed "2x schedule interval". The real threshold is
        `backup_staleness_hours`, independent of any schedule — so the message sent
        operators to the wrong setting."""
        import logging

        mock_settings.health_check_timeout_seconds = 5
        mock_settings.database_provider = "local"
        mock_settings.backup_monitoring_enabled = True
        mock_settings.backup_staleness_hours = 12

        with (
            caplog.at_level(logging.WARNING),
            patch("src.storage.database.health_check", return_value=True),
            patch("src.api.health_routes._check_backup_recency", return_value="stale"),
        ):
            TestClient(app).get("/ready")

        messages = " ".join(record.getMessage() for record in caplog.records)
        assert "backup_staleness_hours" in messages
        assert "12" in messages
        assert "2x schedule" not in messages


class TestCheckBackupRecency:
    """The freshness helper now reads the manifest, not `cron.job_run_details`.

    The pg_cron original was unfixable rather than merely wrong: it queried for a
    job that had never once succeeded, on a platform where the GUC mechanism that
    job depended on is restricted. The honest answer to "when did the backup last
    run?" was never available from inside the database.
    """

    @staticmethod
    def _with_status(status):
        from src.services.backup.manifest_reader import BackupFreshness

        return patch(
            "src.services.backup.manifest_reader.read_freshness",
            return_value=BackupFreshness(status=status),
        )

    def test_derives_status_from_the_manifest(self):
        from src.services.backup.manifest_reader import BackupFreshnessStatus

        with self._with_status(BackupFreshnessStatus.OK):
            assert _check_backup_recency() == "ok"

    def test_reports_stale(self):
        from src.services.backup.manifest_reader import BackupFreshnessStatus

        with self._with_status(BackupFreshnessStatus.STALE):
            assert _check_backup_recency() == "stale"

    def test_absent_manifest_is_no_history(self):
        from src.services.backup.manifest_reader import BackupFreshnessStatus

        with self._with_status(BackupFreshnessStatus.NO_HISTORY):
            assert _check_backup_recency() == "no_history"

    def test_unreachable_target_is_unknown(self):
        from src.services.backup.manifest_reader import BackupFreshnessStatus

        with self._with_status(BackupFreshnessStatus.UNKNOWN):
            assert _check_backup_recency() == "unknown"

    def test_it_does_not_query_the_database_scheduler(self):
        """`cron.job_run_details` records whether a job RAN. The manifest records
        whether a backup EXISTS. Only one of those is the question."""
        import inspect

        from src.api import health_routes

        # The docstring names the old mechanism to explain why it was replaced, so
        # the assertion is against the executable body only.
        body = inspect.getsource(health_routes._check_backup_recency).split('"""')[-1]
        assert "cron.job_run_details" not in body
        assert "railway-backup" not in body
        assert "railway_backup" not in body


class TestNoRailwaySettingNamesRemainOnTheseePaths:
    """Guard for the provider-neutral rename (task 3.3e).

    This cannot live in the settings package: `health_routes` read
    `railway_backup_enabled` until the gate was removed here, so the assertion is
    only true once this package has landed.
    """

    def test_no_freshness_alerting_or_readiness_module_reads_a_railway_backup_setting(self):
        import inspect

        from src.api import health_routes
        from src.services import backup_freshness_alert
        from src.services.backup import manifest_reader

        for module in (health_routes, manifest_reader, backup_freshness_alert):
            source = inspect.getsource(module)
            code = "\n".join(
                line for line in source.splitlines() if not line.strip().startswith("#")
            )
            assert "settings.railway_backup" not in code
            assert "railway_backup_enabled" not in code
            assert "railway_backup_staleness_hours" not in code
