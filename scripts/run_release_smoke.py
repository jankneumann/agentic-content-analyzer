#!/usr/bin/env python3
"""Run the deployed cross-surface release gate and write sanitized evidence."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from src.clients.operational_observability import operational_entrypoint

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.release_smoke.evidence import (  # noqa: E402
    minimal_validator_failure_evidence,
    validate_evidence,
)
from src.release_smoke.models import TargetClass  # noqa: E402
from src.release_smoke.orchestrator import (  # noqa: E402
    load_protected_policy,
    run_release_smoke,
)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@operational_entrypoint("script.run_release_smoke", stage="fetch", service_name="aca-script")
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--target",
        choices=("production", "staging", "ephemeral", "local"),
        required=True,
    )
    parser.add_argument("--allow-mutations", action="store_true")
    parser.add_argument("--fixture")
    args = parser.parse_args()

    started_at = _utc_now()
    target = cast(TargetClass, args.target)
    admin_key = os.environ.get("ADMIN_API_KEY")
    try:
        if not admin_key:
            raise ValueError("Release-smoke admin credential is unavailable")
        policy = load_protected_policy(args.policy_file)
        if policy.target != target:
            raise ValueError("Protected policy target does not match the selected tier")
        evidence = run_release_smoke(
            policy,
            admin_key=admin_key,
            app_secret=os.environ.get("APP_SECRET_KEY"),
            repo_root=REPO_ROOT,
            allow_mutations=args.allow_mutations,
            fixture_name=args.fixture,
        )
        if validate_evidence(evidence):
            raise ValueError("Release-smoke orchestrator returned invalid evidence")
    except Exception:
        evidence = minimal_validator_failure_evidence(
            run_id=uuid.uuid4().hex,
            target=target,
            started_at=started_at,
            finished_at=_utc_now(),
        )
        if validate_evidence(evidence):
            raise RuntimeError("Unable to produce schema-valid release-smoke evidence") from None
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"release-smoke result={evidence['result']} evidence={args.output}")
    return 0 if evidence["result"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
