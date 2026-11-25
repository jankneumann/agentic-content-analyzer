"""Run the daily pipeline for every UTC day that has not completed yet.

Fired by ``aca-gx10-daily-pipeline.timer``. Nothing else schedules ingestion on
the gx-10, and the 2026-10-12 outage showed that a missed day is never made up
by itself, so this catches up: it keeps the last completed day in a state
file and submits each later day, oldest first, up to yesterday.

The submission goes through the API inside the running api container, the
same path as a person typing ``aca pipeline run``. The per-day idempotency key
makes a rerun while that day is still running attach to it instead of starting
a second run. Stdlib only: it runs under the system interpreter.

Exit status is non-zero when a day fails or times out, so the unit's
``OnFailure=`` alert fires; the state file is not advanced past that day, so
the next run retries it.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path


def _read_last_completed(state_file: Path) -> date | None:
    try:
        raw = json.loads(state_file.read_text())
    except FileNotFoundError:
        return None
    return date.fromisoformat(raw["last_completed"])


def _write_last_completed(state_file: Path, day: date) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=state_file.parent, prefix=".daily-pipeline.")
    with os.fdopen(fd, "w") as handle:
        json.dump({"last_completed": day.isoformat()}, handle)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, state_file)


def days_to_run(last_completed: date | None, today: date, max_catchup_days: int) -> list[date]:
    """Days after ``last_completed`` up to yesterday, capped to the newest N."""

    yesterday = today - timedelta(days=1)
    first = yesterday if last_completed is None else last_completed + timedelta(days=1)
    days = [first + timedelta(days=offset) for offset in range((yesterday - first).days + 1)]
    return days[-max_catchup_days:]


def pipeline_command(podman: str, container: str, day: date, timeout_seconds: int) -> list[str]:
    start = datetime(day.year, day.month, day.day, tzinfo=UTC)
    return [
        podman,
        "exec",
        # The container's *_PROXY points at Squid, which refuses loopback.
        "--env",
        "NO_PROXY=127.0.0.1,localhost",
        "--env",
        "API_BASE_URL=http://127.0.0.1:8000",
        container,
        "aca",
        "--json",
        "pipeline",
        "run",
        "--period",
        "daily",
        "--period-start",
        start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "--period-end",
        (start + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "--idempotency-key",
        f"daily-pipeline:{day.isoformat()}",
        "--wait",
        "--timeout",
        str(timeout_seconds),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--state-file", type=Path, required=True)
    parser.add_argument("--container", default="aca-gx10_api_1")
    parser.add_argument("--podman", default="/usr/bin/podman")
    parser.add_argument("--max-catchup-days", type=int, default=14)
    parser.add_argument("--timeout-seconds", type=int, default=10_800)
    parser.add_argument("--today", type=date.fromisoformat, default=None, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    today = args.today or datetime.now(UTC).date()
    last = _read_last_completed(args.state_file)
    days = days_to_run(last, today, args.max_catchup_days)
    if last is not None and days and days[0] > last + timedelta(days=1):
        print(
            f"daily pipeline: skipping {days[0] - last - timedelta(days=1)} beyond the "
            f"{args.max_catchup_days}-day catch-up window after {last}; backfill them by hand",
            file=sys.stderr,
        )
    if not days:
        print(f"daily pipeline: up to date through {last}", file=sys.stderr)
        return 0

    for day in days:
        print(f"daily pipeline: running {day}", file=sys.stderr, flush=True)
        result = subprocess.run(
            pipeline_command(args.podman, args.container, day, args.timeout_seconds),
            check=False,
            stdout=subprocess.PIPE,
            text=True,
        )
        status = _operation_status(result.stdout)
        # A wait that times out returns the still-running operation with exit 0,
        # so only a terminal "completed" counts; "partial" sources are reported
        # by the workflow alert, not here.
        if result.returncode != 0 or status != "completed":
            print(
                f"daily pipeline: {day} ended exit={result.returncode} status={status}; "
                "it is retried next run",
                file=sys.stderr,
            )
            return result.returncode or 1
        _write_last_completed(args.state_file, day)
    return 0


def _operation_status(stdout: str) -> str | None:
    """Status of the one JSON document ``aca --json`` prints, if any."""

    try:
        document = json.loads(stdout.strip().splitlines()[-1])
    except (IndexError, ValueError):
        return None
    status = document.get("status") if isinstance(document, dict) else None
    return status if isinstance(status, str) else None


if __name__ == "__main__":
    raise SystemExit(main())
