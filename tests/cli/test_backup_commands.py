"""`aca backup run | verify | list` — command surface and output contract.

No subprocess runs and no store is contacted: the engine is stubbed at the CLI
boundary, which is the right seam for testing what the *command* does. Engine
behavior itself is covered in tests/test_services/test_backup_engine.py.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from src.cli.app import app
from src.services.backup.engine import VerifyResult
from src.services.backup.models import (
    BackupRunResult,
    RetentionTier,
    StoreName,
    StoreResult,
)
from src.services.backup.preflight import PreflightReport

runner = CliRunner()

DIGEST = "b" * 64


def make_result(*, failed: bool = False) -> BackupRunResult:
    stores = [
        StoreResult.succeeded(
            StoreName.POSTGRES,
            artifact_key="aca/daily/2026-08-21T030000Z/postgres.dump.age",
            size=4096,
            checksum_sha256=DIGEST,
        ),
        StoreResult.skipped(StoreName.OPENBAO, "not_configured"),
    ]
    if failed:
        stores = [StoreResult.failed(StoreName.POSTGRES, "pipeline_stage_exit_nonzero")]
    return BackupRunResult(
        environment="production",
        started_at=datetime(2026, 8, 21, 3, 0, tzinfo=UTC),
        completed_at=datetime(2026, 8, 21, 3, 4, tzinfo=UTC),
        retention_tier=RetentionTier.DAILY,
        prefix="aca",
        stores=tuple(stores),
    )


class StubEngine:
    def __init__(self, **behaviour: Any) -> None:
        self._behaviour = behaviour

    def run(self) -> Any:
        value = self._behaviour.get("run", make_result())
        if isinstance(value, Exception):
            raise value
        return value

    def verify(self) -> Any:
        return self._behaviour.get("verify", VerifyResult(preflight=PreflightReport()))

    def list_backups(self) -> Any:
        return self._behaviour.get("list", [])


def invoke(args: list[str], **behaviour: Any) -> Any:
    with patch("src.cli.backup_commands._engine", lambda now=None: StubEngine(**behaviour)):
        return runner.invoke(app, args)


class TestCommandGroupIsDiscoverable:
    def test_help_lists_the_three_subcommands(self) -> None:
        result = runner.invoke(app, ["backup", "--help"])
        assert result.exit_code == 0
        for subcommand in ("run", "verify", "list"):
            assert subcommand in result.stdout


class TestJsonOutputContract:
    def test_run_emits_exactly_one_json_document_on_stdout(self) -> None:
        result = invoke(["--json", "backup", "run"])
        assert result.exit_code == 0
        payload = json.loads(result.stdout)  # a second document would raise here
        assert payload["success"] is True
        assert payload["environment"] == "production"

    def test_verify_emits_exactly_one_json_document(self) -> None:
        result = invoke(["--json", "backup", "verify"], verify=_verified())
        assert result.exit_code == 0
        assert json.loads(result.stdout)["success"] is True

    def test_list_emits_exactly_one_json_document(self) -> None:
        entries = [
            {
                "key": "aca/daily/2026-08-21T030000Z/postgres.dump.age",
                "size": 4096,
                "modified_at": "2026-08-21T03:04:00Z",
            }
        ]
        result = invoke(["--json", "backup", "list"], list=entries)
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["count"] == 1

    def test_a_failed_run_still_emits_one_document(self) -> None:
        result = invoke(["--json", "backup", "run"], run=make_result(failed=True))
        assert result.exit_code != 0
        assert json.loads(result.stdout)["success"] is False


class TestOutputCarriesNoCredentials:
    @pytest.mark.parametrize("args", [["backup", "run"], ["--json", "backup", "run"]])
    def test_run_output_in_either_mode(self, args: list[str]) -> None:
        result = invoke(args)
        combined = result.stdout + (result.stderr or "")
        for secret in ("AKIA", "r2-secret", "postgresql://", "PGPASSWORD", "BAO_TOKEN"):
            assert secret not in combined

    def test_a_preflight_failure_names_the_setting_not_its_value(self) -> None:
        from src.services.backup.engine import BackupPreflightError

        report = PreflightReport(missing_settings=("BACKUP_AGE_RECIPIENT",))
        result = invoke(["--json", "backup", "run"], run=BackupPreflightError(report))
        assert result.exit_code != 0
        payload = json.loads(result.stdout)
        assert "BACKUP_AGE_RECIPIENT" in payload["error"]


class TestRunExitStatus:
    def test_success_exits_zero(self) -> None:
        assert invoke(["backup", "run"]).exit_code == 0

    def test_any_failed_store_exits_non_zero(self) -> None:
        """A failing store must never leave a green exit status behind — that is
        exactly how the backup this replaces stayed broken and invisible."""
        assert invoke(["backup", "run"], run=make_result(failed=True)).exit_code != 0

    def test_a_failed_run_reports_that_no_manifest_was_written(self) -> None:
        result = invoke(["--json", "backup", "run"], run=make_result(failed=True))
        assert json.loads(result.stdout)["manifest_written"] is False


class TestVerify:
    def test_missing_binaries_are_named_individually(self) -> None:
        report = PreflightReport(missing_binaries=("age", "rclone"))
        result = invoke(["--json", "backup", "verify"], verify=VerifyResult(preflight=report))
        assert result.exit_code != 0
        payload = json.loads(result.stdout)
        assert payload["missing_binaries"] == ["age", "rclone"]

    def test_an_absent_canary_is_distinguishable_from_a_decryption_failure(self) -> None:
        """Conflating them tells an operator their key is wrong when the truth is
        that no backup has ever run."""
        absent = VerifyResult(
            preflight=PreflightReport(),
            canary_present=False,
            detail="No canary object found — has `aca backup run` ever succeeded?",
        )
        broken = VerifyResult(
            preflight=PreflightReport(),
            canary_present=True,
            canary_decrypted=False,
            detail="Canary did not decrypt with the configured identity.",
        )
        absent_payload = json.loads(invoke(["--json", "backup", "verify"], verify=absent).stdout)
        broken_payload = json.loads(invoke(["--json", "backup", "verify"], verify=broken).stdout)
        assert absent_payload["canary_present"] is False
        assert absent_payload["canary_decrypted"] is None
        assert broken_payload["canary_present"] is True
        assert broken_payload["canary_decrypted"] is False
        assert absent_payload["detail"] != broken_payload["detail"]

    def test_a_decryption_failure_exits_non_zero(self) -> None:
        broken = VerifyResult(
            preflight=PreflightReport(),
            canary_present=True,
            canary_decrypted=False,
        )
        assert invoke(["backup", "verify"], verify=broken).exit_code != 0


class TestListIsReadOnly:
    def test_no_subcommand_or_flag_can_delete(self) -> None:
        """Retention is enforced by target lifecycle rules. There is deliberately no
        delete path in this command group, so "no unattended deletion" is a property
        of the code rather than a promise in a runbook."""
        help_text = runner.invoke(app, ["backup", "--help"]).stdout
        assert "delete" not in help_text.lower()
        assert "prune" not in help_text.lower()
        for subcommand in ("run", "verify", "list"):
            text = runner.invoke(app, ["backup", subcommand, "--help"]).stdout.lower()
            assert "--delete" not in text
            assert "--prune" not in text

    def test_empty_listing_is_not_an_error(self) -> None:
        result = invoke(["backup", "list"], list=[])
        assert result.exit_code == 0


def _verified() -> VerifyResult:
    return VerifyResult(
        preflight=PreflightReport(),
        canary_present=True,
        canary_decrypted=True,
        manifest_present=True,
    )
