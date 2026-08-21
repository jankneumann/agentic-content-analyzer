"""Orchestration for `aca backup run | verify | list`.

Approach C: Python decides *what* to back up and *whether it worked*; native tools
do the moving. No artifact passes through the interpreter, and every decision that
could hide a broken backup is made here where a test can reach it.

Four defences against the failure this change exists to eliminate — a backup that
reports success and is not restorable — are implemented in `_run_store`:

1. every pipeline stage's exit status is checked, not just the last one;
2. the stored object's size is read back and compared to the bytes streamed;
3. a store with no digest is failed rather than recorded;
4. the manifest is not written at all when a required store failed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from src.services.backup import target as target_module
from src.services.backup.executor import Stage, run_command, run_pipeline
from src.services.backup.models import (
    FAIL_SIZE_MISMATCH,
    FAIL_STAGE_EXIT,
    BackupRunResult,
    StoreResult,
    retention_tier_for,
)
from src.services.backup.preflight import PreflightReport, check_run_prerequisites
from src.services.backup.stores import StorePlan, plan_all
from src.services.backup.target import (
    BackupTargetNotConfiguredError,
    TargetConfig,
    artifact_key,
    canary_key,
    encrypt_stage,
    list_objects,
    manifest_key,
    put_text,
    run_stamp,
    stored_size,
    upload_stage,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


class BackupPreflightError(RuntimeError):
    """A prerequisite is missing. Raised before any store or target is contacted."""

    def __init__(self, report: PreflightReport) -> None:
        super().__init__(report.describe())
        self.report = report


@dataclass(frozen=True)
class VerifyResult:
    """What `aca backup verify` learned, without ever writing to the target."""

    preflight: PreflightReport
    canary_present: bool | None = None
    canary_decrypted: bool | None = None
    manifest_present: bool | None = None
    detail: str | None = None

    @property
    def ok(self) -> bool:
        return bool(
            self.preflight.ok and self.canary_present and self.canary_decrypted is not False
        )


class BackupEngine:
    """One backup run, one verify, one listing."""

    def __init__(self, settings: Any, *, now: datetime | None = None) -> None:
        self._settings = settings
        self._now = now or datetime.now(UTC)
        self._environment = str(getattr(settings, "environment", "development"))

    # ------------------------------------------------------------------ run

    def run(self) -> BackupRunResult:
        plans = plan_all(self._settings)

        # A6.4 — preflight FIRST. A missing `age` discovered after pg_dump has read
        # a production database is a preflight that did not happen.
        report = check_run_prerequisites(self._settings, plans)
        if not report.ok:
            raise BackupPreflightError(report)

        config = TargetConfig.from_settings(self._settings)
        recipient = str(self._settings.backup_age_recipient)
        started_at = self._now
        tier = retention_tier_for(started_at.date())
        stamp = run_stamp(started_at)

        results = [
            self._run_store(plan, config=config, recipient=recipient, tier=tier, stamp=stamp)
            for plan in plans
        ]

        run_result = BackupRunResult(
            environment=self._environment,
            started_at=started_at,
            completed_at=datetime.now(UTC),
            retention_tier=tier,
            prefix=config.prefix,
            stores=tuple(results),
        )

        if run_result.succeeded:
            self._write_canary(config, recipient)
            self._write_manifest(config, run_result)
        else:
            # Deliberately leaves the PREVIOUS manifest in place. Overwriting it
            # with a failed run's timestamp would make a broken backup look fresh —
            # the one thing the freshness check must never be told.
            logger.error(
                "backup run did not write a manifest: required store(s) failed: %s",
                ", ".join(str(s.store) for s in run_result.failed_required_stores),
            )
        return run_result

    def _run_store(
        self,
        plan: StorePlan,
        *,
        config: TargetConfig,
        recipient: str,
        tier: Any,
        stamp: str,
    ) -> StoreResult:
        if not plan.runnable:
            return StoreResult.skipped(plan.store, plan.skip_reason or "unavailable")

        key = artifact_key(config.prefix, tier, stamp, plan.artifact_name)
        assert plan.stage is not None  # `runnable` guarantees it; kept for type narrowing
        stages: list[Stage] = [
            plan.stage,
            encrypt_stage(recipient),
            upload_stage(config, key),
        ]
        pipeline = run_pipeline(stages)

        if not pipeline.ok:
            # A6.1 — a shell pipeline reports the LAST stage's status, so pg_dump
            # dying halfway still yields zero from rclone. Every stage is checked.
            logger.error(
                "backup store %s failed at stage(s): %s",
                plan.store,
                ", ".join(pipeline.failed_stages),
            )
            return StoreResult.failed(plan.store, FAIL_STAGE_EXIT)

        if pipeline.checksum_sha256 is None or pipeline.bytes_streamed is None:
            return StoreResult.failed(plan.store, FAIL_STAGE_EXIT)

        remote_size = stored_size(config, key)
        if remote_size != pipeline.bytes_streamed:
            # A successful upload of a truncated stream is still a successful
            # upload. This is what makes "rclone exited 0" into evidence.
            logger.error(
                "backup store %s size mismatch: streamed %s, stored %s",
                plan.store,
                pipeline.bytes_streamed,
                remote_size,
            )
            return StoreResult.failed(plan.store, FAIL_SIZE_MISMATCH)

        return StoreResult.succeeded(
            plan.store,
            artifact_key=key,
            size=pipeline.bytes_streamed,
            checksum_sha256=pipeline.checksum_sha256,
        )

    def _write_canary(self, config: TargetConfig, recipient: str) -> None:
        """Write the canary through the SAME encryption path as store artifacts.

        A canary placed by hand proves that a human once ran `age` correctly. This
        one proves the pipeline that produced today's backups can produce something
        the identity can open.
        """
        key = canary_key(config.prefix, self._environment)
        pipeline = run_pipeline(
            [
                Stage(name="canary", argv=("printf", "%s", target_module.CANARY_PLAINTEXT)),
                encrypt_stage(recipient),
                upload_stage(config, key),
            ],
            measure=False,
        )
        if not pipeline.ok:
            logger.warning(
                "backup canary was not written (stages: %s); `aca backup verify` will "
                "report an absent canary",
                ", ".join(pipeline.failed_stages),
            )

    def _write_manifest(self, config: TargetConfig, result: BackupRunResult) -> None:
        import json

        key = manifest_key(config.prefix, self._environment)
        outcome = put_text(config, key, json.dumps(result.manifest(), indent=2, sort_keys=True))
        if not outcome.ok:
            logger.error("backup manifest upload failed (exit %s)", outcome.returncode)

    # --------------------------------------------------------------- verify

    def verify(self) -> VerifyResult:
        plans = plan_all(self._settings)
        report = check_run_prerequisites(self._settings, plans)

        identity = getattr(self._settings, "backup_age_identity_path", None)
        if not identity:
            report = PreflightReport(
                missing_binaries=report.missing_binaries,
                missing_settings=report.missing_settings,
                identity_problem=(
                    "BACKUP_AGE_IDENTITY_PATH is not set, so decryption cannot be "
                    "verified. Backups may still be produced; whether they can be "
                    "read is unknown."
                ),
            )
        if report.missing_binaries or report.missing_settings:
            return VerifyResult(preflight=report)

        try:
            config = TargetConfig.from_settings(self._settings)
        except BackupTargetNotConfiguredError as exc:
            return VerifyResult(preflight=report, detail=str(exc))

        key = canary_key(config.prefix, self._environment)
        entries = list_objects(config, sub_prefix=f"manifests/{self._environment}")
        names = {str(entry.get("Name") or "") for entry in entries}
        manifest_present = "latest.json" in names
        present = f"{target_module.CANARY_NAME}{target_module.ENCRYPTED_SUFFIX}" in names
        if not present:
            # An ABSENT canary is not a decryption failure. Conflating them tells an
            # operator their key is wrong when the truth is no backup has ever run.
            return VerifyResult(
                preflight=report,
                canary_present=False,
                manifest_present=manifest_present,
                detail="No canary object found — has `aca backup run` ever succeeded?",
            )

        if not identity:
            return VerifyResult(
                preflight=report,
                canary_present=True,
                manifest_present=manifest_present,
                detail=report.identity_problem,
            )

        decrypted = run_command(
            ["rclone", "cat", config.remote_path(key)],
            env=config.rclone_env(),
        )
        if not decrypted.ok:
            return VerifyResult(
                preflight=report,
                canary_present=True,
                canary_decrypted=False,
                manifest_present=manifest_present,
                detail="Canary could not be fetched from the backup target.",
            )
        opened = run_command(
            ["age", "--decrypt", "--identity", str(identity)],
            stdin_text=decrypted.stdout,
        )
        matched = opened.ok and opened.stdout.strip() == target_module.CANARY_PLAINTEXT
        return VerifyResult(
            preflight=report,
            canary_present=True,
            canary_decrypted=matched,
            manifest_present=manifest_present,
            detail=None if matched else "Canary did not decrypt with the configured identity.",
        )

    # ----------------------------------------------------------------- list

    def list_backups(self) -> list[dict[str, Any]]:
        """Read-only listing of artifacts under the configured prefix."""
        config = TargetConfig.from_settings(self._settings)
        entries = list_objects(config)
        listed: list[dict[str, Any]] = []
        for entry in entries:
            path = str(entry.get("Path") or "")
            if path.endswith(".json"):
                continue
            listed.append(
                {
                    "key": f"{config.prefix}/{path}",
                    "size": entry.get("Size"),
                    "modified_at": entry.get("ModTime"),
                }
            )
        return sorted(listed, key=lambda item: str(item["key"]))
