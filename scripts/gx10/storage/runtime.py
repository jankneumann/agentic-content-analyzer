"""Observe disk usage and execute bounded GX-10 storage actions."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.clients.operational_observability import operational_stage
from src.services.storage_governance import (
    CleanupResult,
    RetentionCapabilities,
    StorageController,
    StorageDecision,
    plan_retention,
)

ActionInvoker = Callable[[str, dict[str, object]], bool]
_MAX_STATE_BYTES = 4096


def _load_controller(path: Path) -> StorageController:
    if path.is_symlink():
        raise ValueError("storage state must be a regular non-symlink file")
    if not path.exists():
        return StorageController()
    metadata = path.lstat()
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise ValueError("storage state must be a regular non-symlink file")
    if stat.S_IMODE(metadata.st_mode) & 0o077:
        raise ValueError("storage state permissions must not allow group or other access")
    if metadata.st_size > _MAX_STATE_BYTES:
        raise ValueError("storage state exceeds the bounded size limit")
    raw = path.read_bytes()
    if len(raw) > _MAX_STATE_BYTES:
        raise ValueError("storage state exceeds the bounded size limit")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("storage state must be a JSON object")
    return StorageController.from_state(value)


def _save_controller(path: Path, controller: StorageController) -> None:
    payload = json.dumps(controller.to_state(), sort_keys=True, separators=(",", ":")).encode()
    if len(payload) > _MAX_STATE_BYTES:
        raise ValueError("storage state exceeds the bounded size limit")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(prefix=".storage-state-", dir=path.parent) as temporary:
        candidate = Path(temporary) / "state.json"
        descriptor = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(descriptor, payload)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.replace(candidate, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)


@dataclass(slots=True)
class StorageRuntime:
    """Connect the pure policy controller to throttle, cleanup, and alert actions."""

    invoke: ActionInvoker
    controller: StorageController = field(default_factory=StorageController)
    state_file: Path | None = None
    action_failures: tuple[str, ...] = field(default=(), init=False)

    def __post_init__(self) -> None:
        if self.state_file is not None:
            self.controller = _load_controller(self.state_file)

    def run_cycle(
        self,
        *,
        usage_percent: int,
        scheduled_ingestion_concurrency: int,
        now: datetime,
        operation_id: str,
        trace_id: str,
        outcome_specific_retention: bool,
    ) -> StorageDecision:
        decision = self.controller.evaluate(
            usage_percent=usage_percent,
            scheduled_ingestion_concurrency=scheduled_ingestion_concurrency,
            now=now,
            operation_id=operation_id,
            trace_id=trace_id,
        )
        if self.state_file is not None:
            _save_controller(self.state_file, self.controller)
        retention = plan_retention(
            RetentionCapabilities(
                outcome_specific_deletion=outcome_specific_retention,
            ),
            successful_days=30,
            failed_days=90,
            high_watermark_persists=decision.run_supported_cleanup,
        )
        common: dict[str, object] = {
            "operation_id": operation_id,
            "trace_id": trace_id,
            "stage": "cleanup",
            "usage_percent": usage_percent,
            "state": str(decision.state),
        }
        throttle_succeeded = self.invoke(
            "throttle",
            {
                **common,
                "scheduled_ingestion_concurrency": decision.scheduled_ingestion_concurrency,
                "pause_nonessential_ingestion": decision.pause_nonessential_ingestion,
                "suppress_success_excerpts": decision.suppress_success_excerpts,
            },
        )
        failures: list[str] = []
        failure_alert: dict[str, object] | None = None
        if not throttle_succeeded:
            diagnostic = (
                "critical_pause_action_failed"
                if decision.pause_nonessential_ingestion
                else "storage_throttle_action_failed"
            )
            failures.append(diagnostic)
            failure_alert = {
                "operation_id": operation_id,
                "trace_id": trace_id,
                "stage": "alert",
                "outcome": "permanent_failure",
                "diagnostic_code": diagnostic,
            }
        cleanup_alert = None
        if decision.run_supported_cleanup:
            cleanup_payload = {**common, "retention": asdict(retention)}
            succeeded = self.invoke("cleanup", cleanup_payload)
            cleanup_alert = self.controller.record_cleanup(
                CleanupResult.successful()
                if succeeded
                else CleanupResult.failed("supported_cleanup_failed"),
                operation_id=operation_id,
                trace_id=trace_id,
            ).alert
        for alert in (decision.alert, cleanup_alert):
            if alert is not None:
                if not self.invoke("alert", asdict(alert)):
                    failures.append("storage_alert_delivery_failed")
        if failure_alert is not None and not self.invoke("alert", failure_alert):
            failures.append("storage_alert_delivery_failed")
        self.action_failures = tuple(dict.fromkeys(failures))[:4]
        return decision


@dataclass(frozen=True, slots=True)
class CommandInvoker:
    commands: Mapping[str, tuple[str, ...]]

    def __call__(self, action: str, payload: dict[str, object]) -> bool:
        argv = self.commands.get(action)
        if not argv:
            return False
        completed = subprocess.run(
            list(argv),
            input=json.dumps(payload, sort_keys=True).encode(),
            capture_output=True,
            check=False,
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
        )
        return completed.returncode == 0


def _load_commands(path: Path) -> dict[str, tuple[str, ...]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("action configuration must be an object")
    commands: dict[str, tuple[str, ...]] = {}
    for action in ("throttle", "cleanup", "alert"):
        argv = value.get(action)
        if (
            not isinstance(argv, list)
            or not argv
            or not all(isinstance(part, str) and part for part in argv)
        ):
            raise ValueError(f"{action} must be a non-empty argv list")
        commands[action] = tuple(argv)
    return commands


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gx10-storage")
    parser.add_argument("--filesystem", type=Path, default=Path("/"))
    parser.add_argument("--concurrency", type=int, required=True)
    parser.add_argument("--operation-id", required=True)
    parser.add_argument("--trace-id", required=True)
    parser.add_argument("--actions", type=Path, required=True)
    parser.add_argument(
        "--state-file",
        type=Path,
        default=Path("/var/lib/aca/gx10/storage-controller.json"),
    )
    parser.add_argument("--interval-seconds", type=float, default=60.0)
    parser.add_argument("--max-cycles", type=int, default=1)
    parser.add_argument("--outcome-specific-retention", action="store_true")
    return parser


def run_monitor_schedule(
    run_once: Callable[[], int],
    *,
    interval_seconds: float,
    max_cycles: int | None,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    if interval_seconds <= 0:
        raise ValueError("monitor interval must be positive")
    if max_cycles is not None and max_cycles < 1:
        raise ValueError("max_cycles must be positive or None")
    completed = 0
    while max_cycles is None or completed < max_cycles:
        result = run_once()
        completed += 1
        if result != 0:
            return result
        if max_cycles is None or completed < max_cycles:
            sleep(interval_seconds)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    runtime = StorageRuntime(
        invoke=CommandInvoker(_load_commands(args.actions)),
        state_file=args.state_file,
    )

    def run_once() -> int:
        disk = shutil.disk_usage(args.filesystem)
        usage_percent = int((disk.used * 100) / disk.total)
        attributes: dict[str, Any] = {
            "storage.operation_id": args.operation_id,
            "storage.filesystem": str(args.filesystem),
            "storage.substage": "monitor",
        }
        with operational_stage(
            "gx10.storage.monitor",
            stage="cleanup",
            attributes=attributes,
        ):
            decision = runtime.run_cycle(
                usage_percent=usage_percent,
                scheduled_ingestion_concurrency=args.concurrency,
                now=datetime.now(UTC),
                operation_id=args.operation_id,
                trace_id=args.trace_id,
                outcome_specific_retention=args.outcome_specific_retention,
            )
        print(
            json.dumps(
                {
                    "usage_percent": usage_percent,
                    "state": str(decision.state),
                    "scheduled_ingestion_concurrency": (decision.scheduled_ingestion_concurrency),
                    "trace_id": args.trace_id,
                    "action_failures": list(runtime.action_failures),
                },
                sort_keys=True,
            )
        )
        return 1 if runtime.action_failures else 0

    return run_monitor_schedule(
        run_once,
        interval_seconds=args.interval_seconds,
        max_cycles=None if args.max_cycles == 0 else args.max_cycles,
    )
