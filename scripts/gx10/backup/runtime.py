"""Execute complete encrypted GX-10 backups and isolated restore drills."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from scripts.gx10.storage.runtime import StorageRuntime
from src.clients.operational_observability import operational_stage
from src.services.backup.gx10 import (
    AgeRecipientCatalog,
    BackupComponent,
    BackupManifest,
    BackupQuota,
    EncryptedArtifact,
    GX10BackupController,
    GX10RestoreDrill,
    MaintenanceCorrelation,
    OpenBaoAgeAdapter,
    OpenBaoAgeMaterialProvider,
    RestoreDrillResult,
    RestoreValidation,
)

_AGE_ENVELOPE = b"age-encryption.org/v1\n"


def _safe_command(argv: Sequence[str], *, payload: bytes | None = None) -> bytes:
    if not argv:
        raise ValueError("component command argv must not be empty")
    completed = subprocess.run(
        list(argv),
        input=payload,
        capture_output=True,
        check=False,
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
    )
    if completed.returncode != 0:
        raise RuntimeError(f"component command failed: {argv[0]}")
    return completed.stdout or b""


def _component_commands(
    plan: Mapping[str, Any],
    key: str,
) -> dict[BackupComponent, tuple[str, ...]]:
    value = plan.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    commands: dict[BackupComponent, tuple[str, ...]] = {}
    for component in BackupComponent:
        argv = value.get(str(component))
        if (
            not isinstance(argv, list)
            or not argv
            or not all(isinstance(part, str) and part for part in argv)
        ):
            raise ValueError(f"{key}.{component} must be a non-empty argv list")
        commands[component] = tuple(argv)
    if set(value) != {str(component) for component in BackupComponent}:
        raise ValueError(f"{key} must contain exactly the GX-10 component inventory")
    return commands


def _openbao_age_adapter() -> OpenBaoAgeAdapter:
    return OpenBaoAgeAdapter(material=OpenBaoAgeMaterialProvider())


def _producer(argv: tuple[str, ...]) -> Callable[[], bytes]:
    def produce() -> bytes:
        return _safe_command(argv)

    return produce


def resolve_manifest_artifact_path(artifact_dir: Path, name: str) -> Path:
    artifact_name = Path(name)
    if not name or artifact_name.is_absolute() or artifact_name.name != name:
        raise ValueError("manifest artifact name must be a single relative filename")
    root = artifact_dir.resolve()
    resolved = (artifact_dir / artifact_name).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("manifest artifact name escapes the artifact directory")
    return resolved


def _production_source_inventory(plan: Mapping[str, Any]) -> dict[BackupComponent, Path]:
    value = plan.get("production_sources")
    if not isinstance(value, dict):
        raise ValueError("production_sources must be a complete object")
    expected = {str(component) for component in BackupComponent}
    if set(value) != expected:
        raise ValueError("production_sources must contain exactly the GX-10 component inventory")
    sources: dict[BackupComponent, Path] = {}
    for component in BackupComponent:
        raw = value[str(component)]
        if not isinstance(raw, str) or not raw:
            raise ValueError(f"production_sources.{component} must be an absolute path")
        source = Path(raw)
        if not source.is_absolute() or not source.exists():
            raise ValueError(f"production_sources.{component} must be an existing absolute path")
        sources[component] = source
    if len({source.resolve() for source in sources.values()}) != len(sources):
        raise ValueError("production_sources must identify distinct component paths")
    return sources


def run_daily_backup_schedule(
    run_once: Callable[[], int],
    *,
    max_runs: int | None,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    if max_runs is not None and max_runs < 1:
        raise ValueError("max_runs must be positive or None")
    completed = 0
    while max_runs is None or completed < max_runs:
        result = run_once()
        completed += 1
        if result != 0:
            return result
        if max_runs is None or completed < max_runs:
            sleep(24 * 60 * 60)
    return 0


def run_scheduled_backup(
    *,
    plan_path: Path,
    output_dir: Path,
    correlation: MaintenanceCorrelation,
    quota: BackupQuota,
    age: OpenBaoAgeAdapter | None = None,
    clock: Callable[[], datetime] | None = None,
) -> BackupManifest:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if not isinstance(plan, dict):
        raise ValueError("backup plan must be an object")
    commands = _component_commands(plan, "producers")
    age_adapter = age or _openbao_age_adapter()
    output_dir.mkdir(parents=True, exist_ok=True)

    def store(name: str, payload: bytes) -> None:
        if not payload.startswith(_AGE_ENVELOPE):
            raise RuntimeError("refusing to store a non-age artifact")
        (output_dir / name).write_bytes(payload)

    controller = GX10BackupController(
        producers={component: _producer(argv) for component, argv in commands.items()},
        encrypt=age_adapter.encrypt,
        store=store,
        clock=clock,
    )
    started_at = datetime.now(UTC)
    with operational_stage(
        "gx10.backup.scheduled",
        stage="backup",
        attributes={"backup.operation_id": correlation.operation_id},
    ):
        manifest = controller.run(
            recipient_catalog=age_adapter.catalog(),
            correlation=correlation,
            quota=quota,
            started_at=started_at,
        )
    (output_dir / "manifest.json").write_text(manifest.to_json(), encoding="utf-8")
    return manifest


def run_isolated_restore(
    *,
    plan_path: Path,
    manifest_path: Path,
    artifact_dir: Path,
    isolated_root: Path,
    correlation: MaintenanceCorrelation,
    age: OpenBaoAgeAdapter | None = None,
) -> RestoreDrillResult:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if not isinstance(plan, dict):
        raise ValueError("restore plan must be an object")
    restore_commands = _component_commands(plan, "restore")
    validate_commands = _component_commands(plan, "validate")
    manifest = BackupManifest.from_json(manifest_path.read_text(encoding="utf-8"))
    successful = {
        result.component: result for result in manifest.components if result.outcome == "succeeded"
    }
    if set(successful) != set(BackupComponent):
        raise ValueError("restore manifest must contain every successful component")
    production_sources = _production_source_inventory(plan)
    artifacts = {
        component: EncryptedArtifact(
            component=component,
            name=successful[component].artifact_name or "",
            payload=resolve_manifest_artifact_path(
                artifact_dir, successful[component].artifact_name or ""
            ).read_bytes(),
            checksum_sha256=successful[component].checksum_sha256 or "",
            encryption_recipient=successful[component].encryption_recipient or "",
            completed_at=manifest.completed_at,
        )
        for component in BackupComponent
    }
    age_adapter = age or _openbao_age_adapter()

    def restore_handler(argv: tuple[str, ...]) -> Callable[[bytes, Path], None]:
        def restore(payload: bytes, target: Path) -> None:
            target.mkdir(parents=True, exist_ok=True)
            _safe_command((*argv, str(target)), payload=payload)

        return restore

    def validate_handler(argv: tuple[str, ...]) -> Callable[[Path], bool]:
        def validate(target: Path) -> bool:
            try:
                _safe_command((*argv, str(target)))
            except RuntimeError:
                return False
            return True

        return validate

    drill = GX10RestoreDrill(
        decrypt=age_adapter.decrypt,
        restore={component: restore_handler(argv) for component, argv in restore_commands.items()},
        validate={
            component: validate_handler(argv) for component, argv in validate_commands.items()
        },
    )
    metadata = plan.get("metadata_probe")
    if not isinstance(metadata, dict):
        raise ValueError("metadata_probe must be an object")

    def probe() -> RestoreValidation:
        checks: dict[str, bool] = {}
        for name in ("application_operation_rows", "langfuse_trace_metadata"):
            argv = metadata.get(name)
            if not isinstance(argv, list) or not argv:
                raise ValueError(f"metadata_probe.{name} must be an argv list")
            try:
                _safe_command(tuple(str(part) for part in argv))
            except RuntimeError:
                checks[name] = False
            else:
                checks[name] = True
        return RestoreValidation(**checks)

    recipient_catalog = age_adapter.catalog()
    return drill.run_drill(
        artifacts=artifacts,
        targets={component: isolated_root / str(component) for component in BackupComponent},
        isolated_root=isolated_root,
        production_sources=production_sources,
        available_recipients=(
            recipient_catalog.validated_active(),
            *recipient_catalog.retained,
        ),
        correlation=correlation,
        metadata_probe=probe,
    )


def _synthetic_ciphertext(payload: bytes, recipient: str) -> bytes:
    return _AGE_ENVELOPE + hashlib.sha256(recipient.encode() + payload).digest()


def run_synthetic_checkpoint(output: Path) -> dict[str, Any]:
    """Execute deterministic synthetic contracts and truthfully record native limits."""
    trace_id = "c" * 32
    correlation = MaintenanceCorrelation(operation_id="gx10-checkpoint", trace_id=trace_id)
    start = datetime(2026, 8, 29, 12, tzinfo=UTC)
    storage_events: list[tuple[str, dict[str, object]]] = []

    def invoke_storage(action: str, payload: dict[str, object]) -> bool:
        storage_events.append((action, payload))
        return action != "cleanup"

    storage = StorageRuntime(invoke=invoke_storage)
    high = storage.run_cycle(
        usage_percent=80,
        scheduled_ingestion_concurrency=8,
        now=start,
        operation_id=correlation.operation_id,
        trace_id=trace_id,
        outcome_specific_retention=False,
    )
    critical = storage.run_cycle(
        usage_percent=90,
        scheduled_ingestion_concurrency=8,
        now=start + timedelta(minutes=1),
        operation_id=correlation.operation_id,
        trace_id=trace_id,
        outcome_specific_retention=False,
    )
    storage.run_cycle(
        usage_percent=85,
        scheduled_ingestion_concurrency=8,
        now=start + timedelta(minutes=2),
        operation_id=correlation.operation_id,
        trace_id=trace_id,
        outcome_specific_retention=False,
    )
    recovered = storage.run_cycle(
        usage_percent=85,
        scheduled_ingestion_concurrency=8,
        now=start + timedelta(minutes=17),
        operation_id=correlation.operation_id,
        trace_id=trace_id,
        outcome_specific_retention=False,
    )

    stored: dict[str, bytes] = {}

    def synthetic_producer(component: BackupComponent) -> Callable[[], bytes]:
        def produce() -> bytes:
            return f"synthetic:{component}".encode()

        return produce

    controller = GX10BackupController(
        producers={component: synthetic_producer(component) for component in BackupComponent},
        encrypt=_synthetic_ciphertext,
        store=stored.__setitem__,
        clock=lambda: start + timedelta(minutes=5),
    )
    manifest = controller.run(
        recipient_catalog=AgeRecipientCatalog(active="age1" + "a" * 58, retained=()),
        correlation=correlation,
        quota=BackupQuota(limit_bytes=1_000_000, used_bytes=0),
        started_at=start,
    )

    with tempfile.TemporaryDirectory(prefix="gx10-checkpoint-") as temporary:
        root = Path(temporary)
        production_sources = {
            component: root / "production" / str(component) for component in BackupComponent
        }
        for source in production_sources.values():
            source.mkdir(parents=True)
        sentinel = production_sources[BackupComponent.APPLICATION_POSTGRESQL] / "sentinel"
        sentinel.write_text("untouched", encoding="utf-8")
        artifacts = {
            result.component: EncryptedArtifact(
                component=result.component,
                name=result.artifact_name or "",
                payload=stored[result.artifact_name or ""],
                checksum_sha256=result.checksum_sha256 or "",
                encryption_recipient=result.encryption_recipient or "",
                completed_at=manifest.completed_at,
            )
            for result in manifest.components
        }
        restore_times = iter(
            [
                start + timedelta(hours=1),
                *(start + timedelta(hours=1, minutes=index + 1) for index in range(6)),
                start + timedelta(hours=2),
            ]
        )
        drill = GX10RestoreDrill(
            decrypt=lambda _payload, _recipient: b"synthetic-restored",
            restore={
                component: (lambda _payload, target: target.mkdir(parents=True))
                for component in BackupComponent
            },
            validate={component: (lambda target: target.is_dir()) for component in BackupComponent},
            clock=lambda: next(restore_times),
        )
        restore_result = drill.run_drill(
            artifacts=artifacts,
            targets={
                component: root / "isolated" / str(component) for component in BackupComponent
            },
            isolated_root=root / "isolated",
            production_sources=production_sources,
            available_recipients=("age1" + "a" * 58,),
            correlation=correlation,
            metadata_probe=lambda: RestoreValidation(
                application_operation_rows=True,
                langfuse_trace_metadata=True,
            ),
        )
        source_untouched = sentinel.read_text(encoding="utf-8") == "untouched"

    cleanup_alert = next(
        payload
        for action, payload in storage_events
        if action == "alert" and payload.get("diagnostic_code") == "supported_cleanup_failed"
    )
    evidence: dict[str, Any] = {
        "schema_version": 1,
        "evidence_status": "partial",
        "task_8_10": {
            "status": "incomplete",
            "reason": "native_age_and_component_clis_unavailable",
        },
        "checkpoint_mode": "synthetic",
        "native_age_drill": {
            "status": "unavailable" if shutil.which("age") is None else "not_executed",
            "reason": "age_cli_absent" if shutil.which("age") is None else "component_clis_absent",
        },
        "storage": {
            "disk_metrics_percent": [80, 90, 85, 85],
            "states": [str(high.state), str(critical.state), str(recovered.state)],
            "cleanup_failure": cleanup_alert,
        },
        "backup": {
            "manifest": json.loads(manifest.to_json()),
            "checksums": {
                str(result.component): result.checksum_sha256 for result in manifest.components
            },
            "trace_id": trace_id,
        },
        "restore": {
            "outcome": restore_result.outcome,
            "source_untouched": source_untouched,
            "trace_id": restore_result.trace_id,
            "measured_rpo_rto": asdict(restore_result.objectives),
            "metadata_validation": asdict(restore_result.validation),
        },
    }
    normalized = cast(dict[str, Any], json.loads(json.dumps(evidence, sort_keys=True)))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(normalized, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return normalized


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gx10-backup")
    subparsers = parser.add_subparsers(dest="command", required=True)
    checkpoint = subparsers.add_parser("checkpoint")
    checkpoint.add_argument("--output", type=Path, required=True)
    backup = subparsers.add_parser("backup")
    scheduled = subparsers.add_parser("schedule")
    for command in (backup, scheduled):
        command.add_argument("--plan", type=Path, required=True)
        command.add_argument("--output", type=Path, required=True)
        command.add_argument("--operation-id", required=True)
        command.add_argument("--trace-id", required=True)
        command.add_argument("--quota-bytes", type=int, required=True)
    scheduled.add_argument("--max-runs", type=int, default=0)
    restore = subparsers.add_parser("restore")
    restore.add_argument("--plan", type=Path, required=True)
    restore.add_argument("--manifest", type=Path, required=True)
    restore.add_argument("--artifacts", type=Path, required=True)
    restore.add_argument("--isolated-root", type=Path, required=True)
    restore.add_argument("--operation-id", required=True)
    restore.add_argument("--trace-id", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "checkpoint":
        print(json.dumps(run_synthetic_checkpoint(args.output), sort_keys=True))
        return 0
    correlation = MaintenanceCorrelation(
        operation_id=args.operation_id,
        trace_id=args.trace_id,
    )
    if args.command in {"backup", "schedule"}:

        def run_once() -> int:
            manifest = run_scheduled_backup(
                plan_path=args.plan,
                output_dir=args.output,
                correlation=correlation,
                quota=BackupQuota(limit_bytes=args.quota_bytes, used_bytes=0),
            )
            print(manifest.to_json())
            return 0 if manifest.outcome == "succeeded" else 1

        if args.command == "schedule":
            return run_daily_backup_schedule(
                run_once,
                max_runs=None if args.max_runs == 0 else args.max_runs,
            )
        return run_once()
    result = run_isolated_restore(
        plan_path=args.plan,
        manifest_path=args.manifest,
        artifact_dir=args.artifacts,
        isolated_root=args.isolated_root,
        correlation=correlation,
    )
    print(
        json.dumps(
            {
                "outcome": result.outcome,
                "trace_id": result.trace_id,
                "objectives": asdict(result.objectives),
                "diagnostic_codes": result.diagnostic_codes,
            },
            sort_keys=True,
        )
    )
    return 0 if result.outcome == "succeeded" else 1
