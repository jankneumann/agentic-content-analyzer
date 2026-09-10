#!/usr/bin/env python3
"""Prune rendered change-graph assets for pull requests that closed long ago.

The assets branch grows by one directory per push, and nothing ever removes
them. Old directories cost nothing but storage, and their comments are on
closed pull requests nobody revisits, so they are deleted after a grace period.

Dry run by default. A retention job that deletes on its first run, before
anyone has read what it would delete, is how a retention job removes something
it should not have.

Usage:
    python3 scripts/prune_change_graph_assets.py --root . --closed closed.json
    python3 scripts/prune_change_graph_assets.py --root . --closed closed.json --apply
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_GRACE_DAYS = 90


@dataclass(frozen=True)
class Candidate:
    """One pull request's asset directory, and why it is a candidate."""

    number: int
    path: Path
    closed_at: datetime
    reason: str


def plan(
    root: Path,
    closed: dict[int, datetime],
    *,
    now: datetime,
    grace_days: int = DEFAULT_GRACE_DAYS,
) -> list[Candidate]:
    """Return the directories eligible for deletion, oldest first.

    A directory whose pull request is absent from *closed* is kept. Absence is
    not evidence of closure: an incomplete listing must never be read as
    permission to delete.
    """
    cutoff = now - timedelta(days=grace_days)
    candidates: list[Candidate] = []

    for entry in sorted(root.iterdir() if root.is_dir() else []):
        if not entry.is_dir() or not entry.name.isdigit():
            continue
        number = int(entry.name)
        closed_at = closed.get(number)
        if closed_at is None:
            logger.debug("keeping %s: no closure recorded", entry.name)
            continue
        if closed_at > cutoff:
            logger.debug("keeping %s: closed %s, inside the grace period", entry.name, closed_at)
            continue
        candidates.append(
            Candidate(
                number=number,
                path=entry,
                closed_at=closed_at,
                reason=f"closed {(now - closed_at).days} days ago",
            )
        )

    return sorted(candidates, key=lambda c: c.closed_at)


def load_closed(path: Path) -> dict[int, datetime]:
    """Read `[{"number": 1, "closed_at": "..."}]`, as the GitHub API returns it."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    closed: dict[int, datetime] = {}
    for item in raw:
        stamp = item.get("closed_at")
        if not stamp:
            continue
        parsed = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
        closed[int(item["number"])] = parsed.astimezone(UTC)
    return closed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="prune_change_graph_assets",
        description="Delete change-graph assets for long-closed pull requests.",
    )
    parser.add_argument("--root", type=Path, required=True, help="Assets checkout")
    parser.add_argument(
        "--closed", type=Path, required=True, help="JSON listing of closed pull requests"
    )
    parser.add_argument(
        "--grace-days", type=int, default=DEFAULT_GRACE_DAYS,
        help=f"Keep assets this long after closure (default: {DEFAULT_GRACE_DAYS})",
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Actually delete. Without it nothing is removed.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
    args = build_parser().parse_args(argv)

    candidates = plan(
        args.root,
        load_closed(args.closed),
        now=datetime.now(UTC),
        grace_days=args.grace_days,
    )
    if not candidates:
        logger.info("nothing to prune")
        return 0

    for candidate in candidates:
        logger.info(
            "%s %s (%s)",
            "removing" if args.apply else "would remove",
            candidate.path,
            candidate.reason,
        )
        if args.apply:
            shutil.rmtree(candidate.path)

    logger.info(
        "%d %s%s",
        len(candidates),
        "directories removed" if args.apply else "directories would be removed",
        "" if args.apply else "; pass --apply to delete them",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
