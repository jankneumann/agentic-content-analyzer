#!/usr/bin/env python3
"""Validate a sanitized release-smoke evidence JSON document."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.release_smoke.evidence import (  # noqa: E402
    minimal_validator_failure_evidence,
    validate_evidence,
)
from src.release_smoke.models import TargetClass  # noqa: E402


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    parser.add_argument(
        "--replace-invalid-with-failure-target",
        choices=("production", "staging", "ephemeral", "local"),
    )
    args = parser.parse_args()
    errors: list[str]
    try:
        document = json.loads(args.evidence.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        document = None
        errors = ["<root>: evidence is unreadable"]
    else:
        errors = validate_evidence(document)
    if errors:
        if args.replace_invalid_with_failure_target is not None:
            now = _utc_now()
            document = minimal_validator_failure_evidence(
                run_id=uuid.uuid4().hex,
                target=cast(TargetClass, args.replace_invalid_with_failure_target),
                started_at=now,
                finished_at=now,
            )
            fallback_errors = validate_evidence(document)
            if fallback_errors:
                print("release-smoke evidence: INVALID")
                print("- <root>: safe failure envelope could not be validated")
                return 1
            args.evidence.parent.mkdir(parents=True, exist_ok=True)
            args.evidence.write_text(
                json.dumps(document, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            print("release-smoke evidence: VALID (safe failure envelope)")
            return 0
        print("release-smoke evidence: INVALID")
        for error in errors:
            print(f"- {error}")
        return 1
    print("release-smoke evidence: VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
