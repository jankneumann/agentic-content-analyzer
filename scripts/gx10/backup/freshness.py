"""Fail when the newest successful GX-10 backup is older than the RPO allows.

Every other backup alert fires from ``OnFailure=``, which needs the backup to
run and fail. After the 2026-10-12 reboot the timers were never enabled, so
nothing ran, nothing failed, and the host went eight days without a backup in
silence. This check reads the result instead of waiting for a failure.

It is stdlib-only and touches neither the runtime nor its rendered secrets on
purpose: the outage it exists for is the one where those are down.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path


def check(manifest_path: Path, *, max_age: timedelta, now: datetime) -> str | None:
    """Return why the backup is stale, or None when it is fresh."""
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        outcome = manifest["outcome"]
        completed_at = datetime.fromisoformat(manifest["completed_at"].replace("Z", "+00:00"))
    except FileNotFoundError:
        return f"no backup manifest at {manifest_path}"
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        return f"unreadable backup manifest {manifest_path}: {exc!r}"
    if completed_at.tzinfo is None:
        return f"backup manifest completed_at has no timezone: {manifest['completed_at']}"
    if outcome != "succeeded":
        # The run that wrote this already alerted; repeating it hourly keeps a
        # failed backup visible until a good one replaces it.
        return f"newest backup run ended {outcome} at {manifest['completed_at']}"
    age = now - completed_at
    if age > max_age:
        hours, limit = age.total_seconds() / 3600, max_age.total_seconds() / 3600
        return f"newest successful backup is {hours:.1f} h old (limit {limit:g} h)"
    return None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--max-age-hours", type=float, default=36.0)
    args = parser.parse_args(argv)
    problem = check(
        args.manifest,
        max_age=timedelta(hours=args.max_age_hours),
        now=datetime.now(UTC),
    )
    if problem:
        print(f"gx10 backup stale: {problem}", file=sys.stderr)
        return 1
    print("gx10 backup fresh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
