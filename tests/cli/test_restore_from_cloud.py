"""Tests for `aca manage restore-from-cloud` CLI command.

Per design D5, this command is a thin subprocess orchestrator that wraps
`mc` (MinIO client) and `pg_restore`. Tests mock `subprocess.run` and the
Settings object; no real MinIO / Postgres interaction occurs.
"""

from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.cli.app import app

runner = CliRunner()


def _make_completed(
    returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess:
    """Build a stub `CompletedProcess` to return from `subprocess.run`."""
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


@pytest.fixture
def fake_settings():
    """Settings stub populated with MinIO + DB credentials."""
    s = MagicMock()
    s.railway_minio_endpoint = "https://minio.railway.internal"
    s.railway_backup_bucket = "backups"
    s.minio_root_user = "test-user"
    s.minio_root_password = "test-pass"
    s.database_url = "postgresql://localhost:5432/newsletters_sync"
    s.railway_database_url = None
    return s


class TestRestoreFromCloudCLI:
    """Unit tests for argument parsing, subprocess orchestration, exit codes."""

    @patch("src.cli.restore_commands.get_settings")
    @patch("src.cli.restore_commands.subprocess.run")
    def test_specific_backup_date_resolves_filename(self, mock_run, mock_settings, fake_settings):
        """--backup-date 2026-04-20 selects matching dump from `mc ls` listing."""
        mock_settings.return_value = fake_settings
        # Sequence: mc alias set, mc ls (returns dumps), mc cp, pg_restore, mc rm (local)
        mock_run.side_effect = [
            _make_completed(0),  # mc alias set
            _make_completed(
                0,
                stdout=(
                    "[2026-04-19 03:00:00 UTC]  50MiB railway-2026-04-19-0300.dump\n"
                    "[2026-04-20 03:00:00 UTC]  50MiB railway-2026-04-20-0300.dump\n"
                    "[2026-04-21 03:00:00 UTC]  50MiB railway-2026-04-21-0300.dump\n"
                ),
            ),  # mc ls
            _make_completed(0),  # mc cp
            _make_completed(0),  # pg_restore
        ]

        result = runner.invoke(
            app,
            ["manage", "restore-from-cloud", "--backup-date", "2026-04-20", "--yes"],
        )

        assert result.exit_code == 0, result.output
        # Verify mc cp was called with the filename matching the date
        cp_call = mock_run.call_args_list[2]
        cp_args = cp_call[0][0]  # positional args list
        assert any("railway-2026-04-20" in str(a) for a in cp_args), (
            f"Expected railway-2026-04-20 in cp args, got: {cp_args}"
        )

    @patch("src.cli.restore_commands.get_settings")
    @patch("src.cli.restore_commands.subprocess.run")
    def test_latest_backup_picked_when_no_date(self, mock_run, mock_settings, fake_settings):
        """No --backup-date picks the most recent dump from the listing."""
        mock_settings.return_value = fake_settings
        mock_run.side_effect = [
            _make_completed(0),
            _make_completed(
                0,
                stdout=(
                    "[2026-04-19 03:00:00 UTC]  50MiB railway-2026-04-19-0300.dump\n"
                    "[2026-04-20 03:00:00 UTC]  50MiB railway-2026-04-20-0300.dump\n"
                    "[2026-04-21 03:00:00 UTC]  50MiB railway-2026-04-21-0300.dump\n"
                ),
            ),
            _make_completed(0),
            _make_completed(0),
        ]

        result = runner.invoke(app, ["manage", "restore-from-cloud", "--yes"])

        assert result.exit_code == 0, result.output
        cp_call = mock_run.call_args_list[2]
        cp_args = cp_call[0][0]
        # The latest date in the listing is 2026-04-21
        assert any("railway-2026-04-21" in str(a) for a in cp_args), (
            f"Expected latest (2026-04-21) dump, got: {cp_args}"
        )

    @patch("src.cli.restore_commands.get_settings")
    @patch("src.cli.restore_commands.subprocess.run")
    def test_mc_alias_failure_surfaces_nonzero_exit(self, mock_run, mock_settings, fake_settings):
        """`mc` subprocess nonzero exit propagates to CLI exit code."""
        mock_settings.return_value = fake_settings
        mock_run.side_effect = [
            _make_completed(1, stderr="mc: authentication failed"),
        ]

        result = runner.invoke(app, ["manage", "restore-from-cloud", "--yes"])

        assert result.exit_code != 0
        assert "mc" in result.output.lower() or "error" in result.output.lower()

    @patch("src.cli.restore_commands.get_settings")
    @patch("src.cli.restore_commands.subprocess.run")
    def test_mc_ls_empty_listing_errors(self, mock_run, mock_settings, fake_settings):
        """If `mc ls` returns no dumps, CLI exits non-zero with clear message."""
        mock_settings.return_value = fake_settings
        mock_run.side_effect = [
            _make_completed(0),  # mc alias set
            _make_completed(0, stdout=""),  # mc ls returns empty
        ]

        result = runner.invoke(app, ["manage", "restore-from-cloud", "--yes"])

        assert result.exit_code != 0
        assert "no backup" in result.output.lower() or "not found" in result.output.lower()

    @patch("src.cli.restore_commands.get_settings")
    @patch("src.cli.restore_commands.subprocess.run")
    def test_backup_date_not_found_errors(self, mock_run, mock_settings, fake_settings):
        """--backup-date that doesn't match any dump → non-zero exit with message."""
        mock_settings.return_value = fake_settings
        mock_run.side_effect = [
            _make_completed(0),
            _make_completed(
                0,
                stdout="[2026-04-19 03:00:00 UTC]  50MiB railway-2026-04-19-0300.dump\n",
            ),
        ]

        result = runner.invoke(
            app,
            ["manage", "restore-from-cloud", "--backup-date", "2099-01-01", "--yes"],
        )

        assert result.exit_code != 0
        assert "2099-01-01" in result.output or "not found" in result.output.lower()

    @patch("src.cli.restore_commands.get_settings")
    @patch("src.cli.restore_commands.subprocess.run")
    def test_pg_restore_nonzero_exit_surfaces(self, mock_run, mock_settings, fake_settings):
        """`pg_restore` nonzero exit → CLI nonzero exit."""
        mock_settings.return_value = fake_settings
        mock_run.side_effect = [
            _make_completed(0),  # mc alias
            _make_completed(
                0, stdout="[2026-04-20 03:00:00 UTC]  50MiB railway-2026-04-20-0300.dump\n"
            ),  # mc ls
            _make_completed(0),  # mc cp
            _make_completed(1, stderr="pg_restore: could not connect"),  # pg_restore fails
        ]

        result = runner.invoke(app, ["manage", "restore-from-cloud", "--yes"])

        assert result.exit_code != 0
        assert "pg_restore" in result.output.lower() or "restore" in result.output.lower()

    @patch("src.cli.restore_commands.get_settings")
    @patch("src.cli.restore_commands.subprocess.run")
    def test_happy_path_exit_zero_with_summary(self, mock_run, mock_settings, fake_settings):
        """All subprocesses succeed → exit 0 with human-readable summary."""
        mock_settings.return_value = fake_settings
        mock_run.side_effect = [
            _make_completed(0),
            _make_completed(
                0, stdout="[2026-04-20 03:00:00 UTC]  50MiB railway-2026-04-20-0300.dump\n"
            ),
            _make_completed(0),
            _make_completed(0),
        ]

        result = runner.invoke(app, ["manage", "restore-from-cloud", "--yes"])

        assert result.exit_code == 0, result.output
        assert "railway-2026-04-20" in result.output or "restore" in result.output.lower()

    @patch("src.cli.restore_commands.get_settings")
    @patch("src.cli.restore_commands.subprocess.run")
    def test_json_mode_emits_only_json(self, mock_run, mock_settings, fake_settings):
        """--json mode: stdout parses as JSON; no human text."""
        mock_settings.return_value = fake_settings
        mock_run.side_effect = [
            _make_completed(0),
            _make_completed(
                0, stdout="[2026-04-20 03:00:00 UTC]  50MiB railway-2026-04-20-0300.dump\n"
            ),
            _make_completed(0),
            _make_completed(0),
        ]

        result = runner.invoke(
            app,
            ["--json", "manage", "restore-from-cloud", "--yes"],
        )

        assert result.exit_code == 0, result.output
        # Strip any trailing whitespace and parse
        payload = json.loads(result.stdout.strip())
        assert payload["success"] is True
        assert "dump_file" in payload
        assert "railway-2026-04-20" in payload["dump_file"]
        assert payload["target_db"].startswith("postgresql://")

    @patch("src.cli.restore_commands.get_settings")
    def test_missing_minio_credentials_errors(self, mock_settings):
        """If MinIO endpoint/creds are not configured, CLI errors clearly."""
        s = MagicMock()
        s.railway_minio_endpoint = None
        s.minio_root_user = None
        s.minio_root_password = None
        s.railway_backup_bucket = "backups"
        s.database_url = "postgresql://localhost/newsletters"
        s.railway_database_url = None
        mock_settings.return_value = s

        result = runner.invoke(app, ["manage", "restore-from-cloud", "--yes"])

        assert result.exit_code != 0
        assert "minio" in result.output.lower() or "credentials" in result.output.lower()

    # ---- Safety guards against restoring over Railway production DB (IR-002) ----

    @patch("src.cli.restore_commands.get_settings")
    def test_refuses_to_fallback_to_railway_database_url(self, mock_settings, fake_settings):
        """IMPL_REVIEW IR-002: restore-from-cloud must NOT default to RAILWAY_DATABASE_URL.

        Without --target-db and without local DATABASE_URL, the command must refuse
        rather than silently target the Railway production DB.
        """
        fake_settings.database_url = None
        fake_settings.railway_database_url = "postgresql://railway-prod:5432/main"
        mock_settings.return_value = fake_settings

        result = runner.invoke(app, ["manage", "restore-from-cloud", "--yes"])

        assert result.exit_code != 0
        assert (
            "RAILWAY_DATABASE_URL" in result.output
            or "refused" in result.output.lower()
            or "production" in result.output.lower()
        ), f"Expected refusal message, got: {result.output!r}"

    @patch("src.cli.restore_commands.get_settings")
    def test_refuses_explicit_target_db_matching_railway_url(self, mock_settings, fake_settings):
        """IR-002: even an explicit --target-db that matches RAILWAY_DATABASE_URL is refused."""
        railway = "postgresql://railway-prod:5432/main"
        fake_settings.database_url = "postgresql://localhost:5432/newsletters_sync"
        fake_settings.railway_database_url = railway
        mock_settings.return_value = fake_settings

        result = runner.invoke(
            app,
            ["manage", "restore-from-cloud", "--target-db", railway, "--yes"],
        )

        assert result.exit_code != 0
        assert "--allow-remote-target" in result.output or "refused" in result.output.lower()

    @patch("src.cli.restore_commands.get_settings")
    @patch("src.cli.restore_commands.subprocess.run")
    def test_allow_remote_target_opts_into_railway_url(
        self, mock_run, mock_settings, fake_settings
    ):
        """IR-002: explicit --allow-remote-target lets the operator use RAILWAY_DATABASE_URL."""
        railway = "postgresql://railway-prod:5432/main"
        fake_settings.database_url = None
        fake_settings.railway_database_url = railway
        mock_settings.return_value = fake_settings
        mock_run.side_effect = [
            _make_completed(0),
            _make_completed(
                0, stdout="[2026-04-20 03:00:00 UTC]  50MiB railway-2026-04-20-0300.dump\n"
            ),
            _make_completed(0),
            _make_completed(0),
        ]

        result = runner.invoke(
            app,
            ["manage", "restore-from-cloud", "--yes", "--allow-remote-target"],
        )

        assert result.exit_code == 0, result.output
        pg_call = mock_run.call_args_list[3]
        pg_args = pg_call[0][0]
        assert any(railway in str(a) for a in pg_args)

    @patch("src.cli.restore_commands.get_settings")
    @patch("src.cli.restore_commands.subprocess.run")
    def test_target_db_override_used(self, mock_run, mock_settings, fake_settings):
        """--target-db overrides DATABASE_URL for pg_restore."""
        mock_settings.return_value = fake_settings
        mock_run.side_effect = [
            _make_completed(0),
            _make_completed(
                0, stdout="[2026-04-20 03:00:00 UTC]  50MiB railway-2026-04-20-0300.dump\n"
            ),
            _make_completed(0),
            _make_completed(0),
        ]

        result = runner.invoke(
            app,
            [
                "manage",
                "restore-from-cloud",
                "--target-db",
                "postgresql://localhost/my_local",
                "--yes",
            ],
        )

        assert result.exit_code == 0, result.output
        pg_call = mock_run.call_args_list[3]
        pg_args = pg_call[0][0]
        # pg_restore should get the overridden target
        assert any("postgresql://localhost/my_local" in str(a) for a in pg_args), (
            f"Expected override DB in pg_restore args, got: {pg_args}"
        )


# -------------------- integration test (best-effort / skipped) --------------------


@pytest.mark.slow
@pytest.mark.skip(
    reason="requires MinIO + seeded backup fixture (not yet provisioned in docker-compose)"
)
def test_restore_integration_round_trip():  # pragma: no cover
    """Integration: restore a known dump from a local MinIO to a scratch DB.

    Blocked pending a `docker-compose.yml` MinIO service + seeded dump file.
    See docs/SYNC_DOWN.md "Integration test" section for the intended flow.
    """
    pytest.skip("MinIO fixture not yet available")
