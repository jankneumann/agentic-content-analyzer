"""Top-level release-smoke orchestration with minimized evidence output."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from src.release_smoke.browser import (
    AssetManifestError,
    load_retired_routes,
    run_browser_discovery,
)
from src.release_smoke.evidence import (
    minimal_validator_failure_evidence,
    validate_evidence,
)
from src.release_smoke.models import ProtectedTargetPolicy
from src.release_smoke.mutation import MutationSmokeError, run_mutation
from src.release_smoke.runner import (
    ReleaseSmokeError,
    run_api_discovery,
    run_cli_discovery,
)

_MAX_POLICY_BYTES = 16_384


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def load_protected_policy(path: Path) -> ProtectedTargetPolicy:
    """Load a small, non-symlink target policy selected by protected CI."""
    if path.is_symlink():
        raise ReleaseSmokeError("Protected target policy must not be a symlink")
    try:
        if path.stat().st_size > _MAX_POLICY_BYTES:
            raise ReleaseSmokeError("Protected target policy exceeds 16 KiB")
        document = json.loads(path.read_text(encoding="utf-8"))
        return ProtectedTargetPolicy.model_validate(document)
    except (OSError, ValueError, ValidationError) as exc:
        raise ReleaseSmokeError("Protected target policy is invalid") from exc


def _surface(
    policy: ProtectedTargetPolicy,
    name: str,
    *,
    revision: str | None = None,
    revision_source: str | None = None,
) -> dict[str, Any]:
    return {
        "origin": getattr(policy, f"{name}_origin"),
        "observed_revision": revision,
        "revision_source": revision_source,
        "expected_revision": getattr(policy, f"expected_{name}_revision"),
    }


def run_release_smoke(
    policy: ProtectedTargetPolicy,
    *,
    admin_key: str,
    app_secret: str | None,
    repo_root: Path,
    allow_mutations: bool = False,
    fixture_name: str | None = None,
) -> dict[str, Any]:
    """Run all release surfaces and return only schema-valid sanitized evidence."""
    run_id = uuid.uuid4().hex
    started_at = _utc_now()
    checks: list[dict[str, str]] = []
    failures: list[str] = []
    frontend = _surface(policy, "frontend")
    api = _surface(policy, "api")
    assets: list[dict[str, Any]] = []
    retired_route_count = 0
    operation: dict[str, str | None] | None = None

    try:
        api_observation = run_api_discovery(policy, admin_key=admin_key)
        api = _surface(
            policy,
            "api",
            revision=api_observation.revision,
            revision_source=api_observation.revision_source,
        )
        checks.append({"name": "api_discovery", "surface": "api", "status": "passed"})
    except ReleaseSmokeError:
        failures.append("API_UNOBSERVED")
        checks.append({"name": "api_discovery", "surface": "api", "status": "failed"})

    try:
        run_cli_discovery(policy, admin_key=admin_key)
        checks.append({"name": "cli_discovery", "surface": "cli", "status": "passed"})
    except ReleaseSmokeError:
        failures.append("CLI_DISCOVERY_FAILED")
        checks.append({"name": "cli_discovery", "surface": "cli", "status": "failed"})

    try:
        retired_routes = load_retired_routes(
            repo_root / "config" / "release_smoke_retired_routes.json"
        )
        browser_observation = run_browser_discovery(
            policy,
            app_secret=app_secret,
            retired_routes=retired_routes,
        )
        frontend = _surface(
            policy,
            "frontend",
            revision=browser_observation.revision,
            revision_source=browser_observation.revision_source,
        )
        assets = [
            {"sha256": asset.sha256, "size_bytes": asset.size_bytes}
            for asset in browser_observation.assets
        ]
        retired_route_count = browser_observation.retired_route_count
        if retired_route_count:
            failures.append("RETIRED_ROUTE_DETECTED")
            status = "failed"
        else:
            status = "passed"
        checks.append({"name": "frontend_discovery", "surface": "frontend", "status": status})
    except AssetManifestError:
        failures.append("FRONTEND_UNOBSERVED")
        checks.append({"name": "frontend_discovery", "surface": "frontend", "status": "failed"})

    if allow_mutations:
        if failures:
            failures.append("MUTATION_PRECONDITION_FAILED")
            checks.append(
                {"name": "mutation_operation", "surface": "mutation", "status": "skipped"}
            )
        elif fixture_name is None:
            failures.append("MUTATION_FIXTURE_REQUIRED")
            checks.append({"name": "mutation_operation", "surface": "mutation", "status": "failed"})
        else:
            try:
                mutation = run_mutation(
                    policy,
                    allow_mutations=True,
                    fixture_name=fixture_name,
                    repo_root=repo_root,
                    run_id=run_id,
                    admin_key=admin_key,
                )
                operation = {
                    "id": mutation.operation_id,
                    "status": mutation.status,
                }
                checks.append(
                    {"name": "mutation_operation", "surface": "mutation", "status": "passed"}
                )
            except MutationSmokeError as exc:
                failures.append(exc.code)
                if exc.status is not None:
                    operation = {
                        "id": exc.operation_id,
                        "status": exc.status,
                    }
                checks.append(
                    {"name": "mutation_operation", "surface": "mutation", "status": "failed"}
                )

    finished_at = _utc_now()
    evidence: dict[str, Any] = {
        "schema_version": 1,
        "run_id": run_id,
        "target": policy.target,
        "started_at": started_at,
        "finished_at": finished_at,
        "frontend": frontend,
        "api": api,
        "checks": checks,
        "retired_route_count": retired_route_count,
        "assets": assets,
        "operation": operation,
        "result": "failed" if failures else "passed",
        "failure_codes": sorted(set(failures)),
    }
    if validate_evidence(evidence):
        fallback = minimal_validator_failure_evidence(
            run_id=run_id,
            target=policy.target,
            started_at=started_at,
            finished_at=finished_at,
        )
        if validate_evidence(fallback):
            raise ReleaseSmokeError("Unable to produce schema-valid failure evidence")
        return fallback
    return evidence
