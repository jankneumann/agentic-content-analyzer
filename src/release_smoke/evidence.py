"""Schema and semantic validation for minimized release-smoke evidence."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from importlib.resources import files
from typing import Any, Literal, cast

import jsonschema

from src.release_smoke.models import normalize_origin

_SENSITIVE = re.compile(
    r"(?i)(authorization|cookie|x-admin-key|password|bearer|api[_-]?key|secret)"
)
_MAX_RUN_WINDOW = timedelta(hours=1)
_MAX_TOTAL_ASSET_BYTES = 67_108_864
_PREOBSERVATION_CODES = frozenset(
    {
        "API_UNOBSERVED",
        "FRONTEND_UNOBSERVED",
        "TARGET_POLICY_INVALID",
        "VALIDATOR_OUTPUT_REJECTED",
    }
)


def _schema() -> dict[str, Any]:
    resource = files("src.release_smoke").joinpath("release_smoke_evidence.schema.json")
    return cast(dict[str, Any], json.loads(resource.read_text(encoding="utf-8")))


def _path(error: jsonschema.ValidationError) -> str:
    location = ".".join(str(part) for part in error.absolute_path)
    return location or "<root>"


def _parse_utc(value: object, field: str, errors: list[str]) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        errors.append(f"{field} must be UTC")
        return None
    return parsed.astimezone(UTC)


def validate_evidence(document: object) -> list[str]:
    """Return sanitized schema and semantic errors; empty means valid."""
    errors: list[str] = []
    validator = jsonschema.Draft202012Validator(
        _schema(),
        format_checker=jsonschema.FormatChecker(),
    )
    for error in sorted(
        validator.iter_errors(document),
        key=lambda item: "/".join(str(part) for part in item.path),
    ):
        errors.append(f"{_path(error)}: schema validation failed ({error.validator})")
    if not isinstance(document, dict):
        return errors

    try:
        serialized = json.dumps(document, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError):
        serialized = ""
        errors.append("<root>: evidence is not JSON-serializable")
    if _SENSITIVE.search(serialized):
        errors.append("<root>: evidence contains sensitive field names or values")

    started = _parse_utc(document.get("started_at"), "started_at", errors)
    finished = _parse_utc(document.get("finished_at"), "finished_at", errors)
    if started is not None and finished is not None:
        if finished < started:
            errors.append("<root>: run time window is reversed")
        elif finished - started > _MAX_RUN_WINDOW:
            errors.append("<root>: run time window exceeds one hour")

    result = document.get("result")
    failure_codes = document.get("failure_codes")
    safe_failure_codes = (
        {code for code in failure_codes if isinstance(code, str)}
        if isinstance(failure_codes, list)
        else set()
    )
    checks = document.get("checks")
    if result == "passed":
        if failure_codes:
            errors.append("failure_codes: passing evidence must not contain failures")
        if isinstance(checks, list) and any(
            isinstance(check, dict) and check.get("status") != "passed" for check in checks
        ):
            errors.append("checks: passing evidence requires every check to pass")
        if document.get("retired_route_count") != 0:
            errors.append("retired_route_count: passing evidence requires zero retired routes")
        expected_checks = {
            "api_discovery": "api",
            "cli_discovery": "cli",
            "frontend_discovery": "frontend",
        }
        valid_checks: set[str] = set()
        check_names: list[str] = []
        if isinstance(checks, list):
            for check in checks:
                if not isinstance(check, dict):
                    continue
                name = check.get("name")
                if isinstance(name, str):
                    check_names.append(name)
                if (
                    isinstance(name, str)
                    and check.get("status") == "passed"
                    and expected_checks.get(name) == check.get("surface")
                ):
                    valid_checks.add(name)
        if len(check_names) != len(set(check_names)):
            errors.append("checks: check names must be unique")
        if not set(expected_checks).issubset(valid_checks):
            errors.append("checks: passing evidence is missing a required surface check")
        if not isinstance(document.get("assets"), list) or not document["assets"]:
            errors.append("assets: passing evidence requires a nonempty asset inventory")
        if document.get("target") in {"staging", "ephemeral"}:
            mutation_passed = (
                any(
                    isinstance(check, dict)
                    and check.get("name") == "mutation_operation"
                    and check.get("surface") == "mutation"
                    and check.get("status") == "passed"
                    for check in checks
                )
                if isinstance(checks, list)
                else False
            )
            if not mutation_passed:
                errors.append("checks: mutation target requires a passing mutation check")
            operation = document.get("operation")
            if not isinstance(operation, dict) or operation.get("status") != "completed":
                errors.append("operation: mutation target requires a completed operation")
    elif result == "failed":
        if not failure_codes:
            errors.append("failure_codes: failed evidence requires a stable failure code")
        if isinstance(checks, list) and not any(
            isinstance(check, dict) and check.get("status") == "failed" for check in checks
        ):
            errors.append("checks: failed evidence requires a failed check")

    for surface_name in ("frontend", "api"):
        surface = document.get(surface_name)
        if not isinstance(surface, dict):
            continue
        origin = surface.get("origin")
        if isinstance(origin, str):
            try:
                if normalize_origin(origin) != origin:
                    errors.append(f"{surface_name}.origin: origin is not canonical")
            except ValueError:
                errors.append(f"{surface_name}.origin: origin is unsafe")
        observed = surface.get("observed_revision")
        expected = surface.get("expected_revision")
        if result == "passed" and expected is not None and observed != expected:
            errors.append(f"{surface_name}: observed revision does not match expected revision")
        if any(
            surface.get(field) is None
            for field in ("origin", "observed_revision", "revision_source")
        ):
            required = f"{surface_name.upper()}_UNOBSERVED"
            if result != "failed" or not (
                {required, "VALIDATOR_OUTPUT_REJECTED"} & safe_failure_codes
            ):
                errors.append(
                    f"{surface_name}: null observations require a matching pre-observation failure"
                )
        if result == "passed" and document.get("target") != "local":
            if surface.get("expected_revision") is None:
                errors.append(f"{surface_name}.expected_revision: release target requires a SHA")
            trusted_sources = (
                {"railway_commit_sha"}
                if surface_name == "api"
                else {"railway_commit_sha", "github_sha", "verified_detached_sha"}
            )
            if surface.get("revision_source") not in trusted_sources:
                errors.append(f"{surface_name}.revision_source: provenance is untrusted")

    if isinstance(failure_codes, list):
        for code in failure_codes:
            if (
                isinstance(code, str)
                and code.endswith("_UNOBSERVED")
                and code not in (_PREOBSERVATION_CODES)
            ):
                errors.append("failure_codes: unsupported pre-observation code")

    assets = document.get("assets")
    if isinstance(assets, list):
        total = sum(
            asset.get("size_bytes", 0)
            for asset in assets
            if isinstance(asset, dict) and isinstance(asset.get("size_bytes"), int)
        )
        if total > _MAX_TOTAL_ASSET_BYTES:
            errors.append("assets: total asset bytes exceed 64 MiB")

    operation = document.get("operation")
    if document.get("target") == "production" and operation is not None:
        errors.append("operation: production evidence cannot contain a mutation")
    if (
        isinstance(operation, dict)
        and operation.get("status") not in {"ambiguous"}
        and operation.get("id") is None
    ):
        errors.append("operation.id: terminal operation evidence requires an ID")
    return sorted(set(errors))


def minimal_validator_failure_evidence(
    *,
    run_id: str,
    target: Literal["production", "staging", "ephemeral", "local"],
    started_at: str,
    finished_at: str,
) -> dict[str, Any]:
    """Build a fixed-field failure envelope without copying rejected output."""
    surface = {
        "origin": None,
        "observed_revision": None,
        "revision_source": None,
        "expected_revision": None,
    }
    return {
        "schema_version": 1,
        "run_id": run_id,
        "target": target,
        "started_at": started_at,
        "finished_at": finished_at,
        "frontend": dict(surface),
        "api": dict(surface),
        "checks": [
            {
                "name": "evidence_validation",
                "surface": "evidence",
                "status": "failed",
            }
        ],
        "retired_route_count": 0,
        "assets": [],
        "operation": None,
        "result": "failed",
        "failure_codes": ["VALIDATOR_OUTPUT_REJECTED"],
    }
