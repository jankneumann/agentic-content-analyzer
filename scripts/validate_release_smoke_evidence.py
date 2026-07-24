#!/usr/bin/env python3
"""Validate a sanitized release-smoke evidence JSON document."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.release_smoke.evidence import validate_evidence  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args()
    try:
        document = json.loads(args.evidence.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print("release-smoke evidence: INVALID (unreadable JSON)")
        return 1
    errors = validate_evidence(document)
    if errors:
        print("release-smoke evidence: INVALID")
        for error in errors:
            print(f"- {error}")
        return 1
    print("release-smoke evidence: VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
