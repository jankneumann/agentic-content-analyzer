"""Observe disk usage and execute bounded GX-10 storage actions."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
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


@dataclass(slots=True)
class StorageRuntime:
    """Connect the pure policy controller to throttle, cleanup, and alert actions."""

    invoke: ActionInvoker
    controller: StorageController = field(default_factory=StorageController)

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
            "stage": "storage_governance",
            "usage_percent": usage_percent,
            "state": str(decision.state),
        }
        self.invoke(
            "throttle",
            {
                **common,
                "scheduled_ingestion_concurrency": decision.scheduled_ingestion_concurrency,
                "pause_nonessential_ingestion": decision.pause_nonessential_ingestion,
                "suppress_success_excerpts": decision.suppress_success_excerpts,
            },
        )
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
                self.invoke("alert", asdict(alert))
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
    parser.add_argument("--outcome-specific-retention", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    disk = shutil.disk_usage(args.filesystem)
    usage_percent = int((disk.used * 100) / disk.total)
    runtime = StorageRuntime(invoke=CommandInvoker(_load_commands(args.actions)))
    attributes: dict[str, Any] = {
        "storage.operation_id": args.operation_id,
        "storage.filesystem": str(args.filesystem),
    }
    with operational_stage(
        "gx10.storage.monitor",
        stage="storage_governance",
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
            },
            sort_keys=True,
        )
    )
    return 0
