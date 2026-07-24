#!/usr/bin/env python3
"""Run the deployed cross-surface release gate and write sanitized evidence."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.release_smoke.evidence import validate_evidence  # noqa: E402
from src.release_smoke.orchestrator import (  # noqa: E402
    load_protected_policy,
    run_release_smoke,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-mutations", action="store_true")
    parser.add_argument("--fixture")
    args = parser.parse_args()

    admin_key = os.environ.get("ADMIN_API_KEY")
    if not admin_key:
        parser.error("ADMIN_API_KEY must be provided through the environment")
    policy = load_protected_policy(args.policy_file)
    evidence = run_release_smoke(
        policy,
        admin_key=admin_key,
        app_secret=os.environ.get("APP_SECRET_KEY"),
        repo_root=Path(__file__).resolve().parents[1],
        allow_mutations=args.allow_mutations,
        fixture_name=args.fixture,
    )
    if validate_evidence(evidence):
        raise RuntimeError("Release-smoke orchestrator returned invalid evidence")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"release-smoke result={evidence['result']} evidence={args.output}")
    return 0 if evidence["result"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
