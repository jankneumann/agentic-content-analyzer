#!/usr/bin/env python3
"""Validate sanitized evidence for a production frontend Railway release."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)
CI_RESULT_PATTERN = re.compile(
    r"^(?P<conclusion>[a-z_]+)\s*;\s*checked_sha=(?P<sha>[0-9a-f]{40})$",
    re.IGNORECASE,
)
CORRELATION_TIME_PATTERN = re.compile(r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z\b")
REQUEST_ATTRIBUTION_PATTERN = re.compile(r"\brequestId\s+[^;\s]+", re.IGNORECASE)
BROWSER_ATTRIBUTION_PATTERN = re.compile(
    r"\b(?:chrome|chromium|headlesschrome|playwright|devtools|firefox|webkit)\b",
    re.IGNORECASE,
)

EXPECTED_TARGETS = {
    "Railway project ID": "4b0db3b8-110d-4a13-81d5-440aa2ddc98d",
    "Railway environment ID": "cd39a506-8d8f-4aa2-b298-766fde2b8dd8",
    "Railway frontend service ID": "00281b0e-9de9-414d-844e-da3ab02836f5",
    "Backend service ID": "46b135a6-d361-4985-947b-e27049f612a7",
}

REQUIRED_FIELDS = (
    "Candidate commit SHA",
    "Candidate branch",
    "GitHub `frontend-release` check URL",
    "GitHub check conclusion and checked SHA",
    "Working tree clean",
    "Candidate pushed",
    "Railway project ID",
    "Railway environment ID",
    "Railway frontend service ID",
    "Public frontend URL",
    "Active deployment ID before release",
    "Active revision before release",
    "Last successful deployment ID",
    "Last successful revision",
    "Rollback command",
    "Abort criteria evaluated",
    "Deployment start UTC",
    "Deployment end UTC",
    "Deployment ID",
    "Deployed candidate revision",
    "Release stamp path",
    "Release stamp SHA-256",
    "Served frontend revision",
    "Served frontend revision source",
    "Railway CLI release message",
    "Uploaded lockfile observed",
    "Railpack install command",
    "Railpack Node version",
    "Build status",
    "Deployment status",
    "Revision matches CI-passed candidate",
    "Verification window start UTC",
    "Verification window end UTC",
    "Browser/session attribution",
    "Public route and load status",
    "Capability request method/path",
    "Capability response status",
    "Capability source options rendered",
    "Canary request method/path",
    "Canary response status",
    "Canary source kind",
    "Sanitized canary marker",
    "Visible form submission count",
    "Durable operation ID",
    "Durable operation terminal status",
    "Client retries observed",
    "Retention/cleanup disposition",
    "Backend service ID",
    "Log query window",
    "Capability request correlation",
    "Canonical ingestion request correlation",
    "`POST /api/v1/contents/ingest` count",
    "`POST /api/v1/content/save-url` count",
    "Acceptance outcomes passed",
    "Rollback required",
    "Rollback deployment ID",
)


def _parse_fields(markdown: str) -> tuple[dict[str, str], list[str]]:
    fields: dict[str, str] = {}
    errors: list[str] = []
    for line_number, line in enumerate(markdown.splitlines(), start=1):
        if not line.startswith("- ") or ":" not in line:
            continue
        label, value = line[2:].split(":", 1)
        label = label.strip()
        if label in fields:
            errors.append(f"{label}: duplicate field on line {line_number}")
            continue
        fields[label] = value.strip()
    return fields, errors


def _parse_utc(value: str, label: str, errors: list[str]) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{label}: expected an ISO-8601 UTC timestamp, got {value!r}")
        return None
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        errors.append(f"{label}: timestamp must include the UTC offset, got {value!r}")
        return None
    return parsed


def _parse_int(fields: dict[str, str], label: str, errors: list[str]) -> int | None:
    try:
        return int(fields[label])
    except ValueError:
        errors.append(f"{label}: expected an integer, got {fields[label]!r}")
        return None


def _require_true(fields: dict[str, str], label: str, errors: list[str]) -> None:
    if fields[label].casefold() != "true":
        errors.append(f"{label}: expected true, got {fields[label]!r}")


def _require_2xx(fields: dict[str, str], label: str, errors: list[str]) -> None:
    status = _parse_int(fields, label, errors)
    if status is not None and not 200 <= status < 300:
        errors.append(f"{label}: expected a successful 2xx status, got {status}")


def _validate_correlation(
    *,
    label: str,
    value: str,
    expected_parts: tuple[str, ...],
    verification_start: datetime | None,
    verification_end: datetime | None,
    errors: list[str],
) -> None:
    if any(expected not in value for expected in expected_parts):
        errors.append(
            f"{label} must include the canonical path, response status, "
            "and associated durable operation when applicable"
        )

    if REQUEST_ATTRIBUTION_PATTERN.search(value) is None:
        errors.append(f"{label}: request attribution must include a nonblank requestId")

    timestamp_match = CORRELATION_TIME_PATTERN.search(value)
    if timestamp_match is None:
        errors.append(f"{label}: correlation timestamp must be a parseable ISO-8601 UTC value")
    else:
        timestamp = _parse_utc(
            timestamp_match.group(0),
            f"{label} timestamp",
            errors,
        )
        if (
            timestamp is not None
            and verification_start is not None
            and verification_end is not None
            and not verification_start <= timestamp <= verification_end
        ):
            errors.append(f"{label}: timestamp must fall within the verification window")

    if BROWSER_ATTRIBUTION_PATTERN.search(value) is None:
        errors.append(f"{label}: browser attribution is required")


def validate_evidence(markdown: str) -> list[str]:
    """Return actionable contract violations found in a Markdown evidence record."""

    fields, errors = _parse_fields(markdown)
    for label in REQUIRED_FIELDS:
        if label not in fields:
            errors.append(f"{label}: required field is missing")
        elif not fields[label].strip():
            errors.append(f"{label}: critical field must not be blank")

    if errors:
        return errors

    candidate_sha = fields["Candidate commit SHA"].casefold()
    if not SHA_PATTERN.fullmatch(candidate_sha):
        errors.append("Candidate commit SHA: expected a full 40-character hexadecimal commit SHA")

    ci_match = CI_RESULT_PATTERN.fullmatch(fields["GitHub check conclusion and checked SHA"])
    ci_sha: str | None = None
    if ci_match is None:
        errors.append(
            "GitHub check conclusion and checked SHA: expected "
            "'success; checked_sha=<40-character SHA>'"
        )
    else:
        ci_sha = ci_match.group("sha").casefold()
        if ci_match.group("conclusion").casefold() != "success":
            errors.append(
                f"GitHub check conclusion must be successful, got {ci_match.group('conclusion')!r}"
            )

    deployed_sha = fields["Deployed candidate revision"].casefold()
    if not SHA_PATTERN.fullmatch(deployed_sha):
        errors.append(
            "Deployed candidate revision: expected a full 40-character hexadecimal commit SHA"
        )
    if ci_sha is not None and (candidate_sha != ci_sha or candidate_sha != deployed_sha):
        errors.append(
            "Release revision mismatch: candidate, CI checked SHA, and deployed "
            "candidate revision must be identical"
        )
    if fields["Release stamp path"] != "web/release-build.json":
        errors.append("Release stamp path must be web/release-build.json")
    if SHA256_PATTERN.fullmatch(fields["Release stamp SHA-256"]) is None:
        errors.append("Release stamp SHA-256 must be a 64-character hexadecimal digest")
    if fields["Served frontend revision"].casefold() != candidate_sha:
        errors.append("Served frontend revision must match the candidate revision")
    if fields["Served frontend revision source"] != "verified_detached_sha":
        errors.append("Served frontend revision source must be verified_detached_sha")
    expected_cli_message = f"frontend-release {candidate_sha}"
    if fields["Railway CLI release message"] != expected_cli_message:
        errors.append(
            "Railway CLI release message: expected "
            f"{expected_cli_message!r}, got {fields['Railway CLI release message']!r}"
        )
    expected_build_facts = {
        "Uploaded lockfile observed": "web/package-lock.json",
        "Railpack install command": "npm ci",
    }
    for label, expected in expected_build_facts.items():
        if fields[label] != expected:
            errors.append(f"{label}: expected {expected!r}, got {fields[label]!r}")
    if re.fullmatch(r"22(?:\.\d+){0,2}", fields["Railpack Node version"]) is None:
        errors.append(
            f"Railpack Node version: expected Node 22.x, got {fields['Railpack Node version']!r}"
        )

    for label in ("Build status", "Deployment status"):
        if fields[label].casefold() != "success":
            errors.append(f"{label} must be successful (SUCCESS), got {fields[label]!r}")
    if fields["Durable operation terminal status"].casefold() != "completed":
        errors.append(
            "Durable operation terminal status must be successful (completed), got "
            f"{fields['Durable operation terminal status']!r}"
        )

    for label in (
        "Working tree clean",
        "Candidate pushed",
        "Revision matches CI-passed candidate",
        "Acceptance outcomes passed",
    ):
        _require_true(fields, label, errors)

    for label, expected in EXPECTED_TARGETS.items():
        if fields[label] != expected:
            errors.append(
                f"{label}: expected scoped production target {expected!r}, got {fields[label]!r}"
            )

    deployment_start = _parse_utc(fields["Deployment start UTC"], "Deployment start UTC", errors)
    deployment_end = _parse_utc(fields["Deployment end UTC"], "Deployment end UTC", errors)
    verification_start = _parse_utc(
        fields["Verification window start UTC"],
        "Verification window start UTC",
        errors,
    )
    verification_end = _parse_utc(
        fields["Verification window end UTC"],
        "Verification window end UTC",
        errors,
    )

    for start, end, description in (
        (deployment_start, deployment_end, "Deployment"),
        (verification_start, verification_end, "Verification"),
    ):
        if start is not None and end is not None and start >= end:
            errors.append(f"{description} window start must be before its end")
    if (
        deployment_end is not None
        and verification_start is not None
        and deployment_end > verification_start
    ):
        errors.append("Verification window must start after the deployment completes")

    log_window_parts = fields["Log query window"].split("/")
    if len(log_window_parts) != 2:
        errors.append("Log query window: expected '<ISO-8601 UTC start>/<ISO-8601 UTC end>'")
    else:
        log_start = _parse_utc(log_window_parts[0], "Log query window start", errors)
        log_end = _parse_utc(log_window_parts[1], "Log query window end", errors)
        if log_start is not None and log_end is not None:
            if log_start >= log_end:
                errors.append("Log query window start must be before its end")
            if (
                verification_start is not None
                and verification_end is not None
                and (log_start > verification_start or log_end < verification_end)
            ):
                errors.append(
                    "Log query window must cover the complete browser verification window"
                )

    expected_routes = {
        "Capability request method/path": "GET /api/v1/capabilities",
        "Canary request method/path": "POST /api/v1/ingestions",
    }
    for label, expected in expected_routes.items():
        if fields[label] != expected:
            errors.append(f"{label}: expected canonical route {expected!r}")
    if fields["Canary source kind"].casefold() != "url":
        errors.append("Canary source kind: expected 'url'")
    if not fields["Capability source options rendered"].casefold().startswith("true"):
        errors.append("Capability source options rendered: expected true")

    _require_2xx(fields, "Capability response status", errors)
    _require_2xx(fields, "Canary response status", errors)
    if not re.search(r"\b2\d\d\b", fields["Public route and load status"]):
        errors.append("Public route and load status: expected a successful 2xx status")

    submission_count = _parse_int(fields, "Visible form submission count", errors)
    if submission_count is not None and submission_count != 1:
        errors.append(f"Visible form submission count must be exactly 1, got {submission_count}")
    retry_count = _parse_int(fields, "Client retries observed", errors)
    if retry_count is not None and retry_count != 0:
        errors.append(f"Client retries observed must be exactly 0, got {retry_count}")

    for label in (
        "`POST /api/v1/contents/ingest` count",
        "`POST /api/v1/content/save-url` count",
    ):
        route_count = _parse_int(fields, label, errors)
        if route_count is not None and route_count != 0:
            errors.append(f"{label}: retired route count must be 0, got {route_count}")

    _validate_correlation(
        label="Capability request correlation",
        value=fields["Capability request correlation"],
        expected_parts=("GET /api/v1/capabilities", fields["Capability response status"]),
        verification_start=verification_start,
        verification_end=verification_end,
        errors=errors,
    )
    _validate_correlation(
        label="Canonical ingestion request correlation",
        value=fields["Canonical ingestion request correlation"],
        expected_parts=(
            "POST /api/v1/ingestions",
            fields["Canary response status"],
            fields["Durable operation ID"],
        ),
        verification_start=verification_start,
        verification_end=verification_end,
        errors=errors,
    )

    if fields["Rollback required"].casefold() not in {"true", "false"}:
        errors.append("Rollback required: expected true or false")

    return errors


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate a production frontend deployment evidence Markdown file."
    )
    parser.add_argument("evidence", type=Path, help="Path to production-deployment.md")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        markdown = args.evidence.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"evidence validation failed: {exc}", file=sys.stderr)
        return 1

    errors = validate_evidence(markdown)
    if errors:
        print(
            f"evidence validation failed with {len(errors)} error(s):",
            file=sys.stderr,
        )
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"evidence validation passed: {args.evidence}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
