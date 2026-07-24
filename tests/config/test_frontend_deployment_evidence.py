"""Tests for the sanitized production frontend deployment evidence contract."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from scripts.validate_frontend_deployment_evidence import validate_evidence

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts" / "validate_frontend_deployment_evidence.py"
RUNBOOK = REPO_ROOT / "docs" / "MOBILE_DEPLOYMENT.md"
SHA = "a" * 40


@pytest.fixture
def complete_evidence() -> str:
    return f"""# Production frontend deployment evidence

## Candidate and rollback manifest (capture before deployment)

- Candidate commit SHA: {SHA}
- Candidate branch: openspec/restore-railway-frontend-deployment
- GitHub `frontend-release` check URL: https://github.com/example/repo/actions/runs/123
- GitHub check conclusion and checked SHA: success; checked_sha={SHA}
- Working tree clean: true
- Candidate pushed: true
- Railway project ID: 4b0db3b8-110d-4a13-81d5-440aa2ddc98d
- Railway environment ID: cd39a506-8d8f-4aa2-b298-766fde2b8dd8
- Railway frontend service ID: 00281b0e-9de9-414d-844e-da3ab02836f5
- Public frontend URL: https://aca-app.example.test
- Active deployment ID before release: deployment-before
- Active revision before release: {"b" * 40}
- Last successful deployment ID: deployment-rollback
- Last successful revision: {"c" * 40}
- Rollback command: railway up --ci --project 4b0db3b8-110d-4a13-81d5-440aa2ddc98d
- Abort criteria evaluated: passed; recoverable prior release confirmed

## Railway release

- Deployment start UTC: 2026-07-23T14:00:00Z
- Deployment end UTC: 2026-07-23T14:05:00Z
- Deployment ID: deployment-new
- Deployed candidate revision: {SHA}
- Railway CLI release message: frontend-release {SHA}
- Uploaded lockfile observed: web/package-lock.json
- Railpack install command: npm ci
- Railpack Node version: 22.23.1
- Build status: SUCCESS
- Deployment status: SUCCESS
- Revision matches CI-passed candidate: true

## Browser and network verification

- Verification window start UTC: 2026-07-23T14:06:00Z
- Verification window end UTC: 2026-07-23T14:10:00Z
- Browser/session attribution: Chrome DevTools session release-{SHA[:8]}
- Public route and load status: GET / 200
- Capability request method/path: GET /api/v1/capabilities
- Capability response status: 200
- Capability source options rendered: true; url option visible
- Canary request method/path: POST /api/v1/ingestions
- Canary response status: 202
- Canary source kind: url
- Sanitized canary marker: aca-release-smoke-{SHA[:8]}
- Visible form submission count: 1
- Durable operation ID: operation-123
- Durable operation terminal status: completed
- Client retries observed: 0
- Retention/cleanup disposition: retained as labeled release evidence

## Bounded backend-log correlation

- Backend service ID: 46b135a6-d361-4985-947b-e27049f612a7
- Log query window: 2026-07-23T14:06:00Z/2026-07-23T14:10:00Z
- Capability request correlation: requestId capability-123; GET /api/v1/capabilities; 200; 2026-07-23T14:07:00Z; HeadlessChrome/149
- Canonical ingestion request correlation: requestId ingestion-123; operation-123; POST /api/v1/ingestions; 202; 2026-07-23T14:08:00Z; HeadlessChrome/149
- `POST /api/v1/contents/ingest` count: 0
- `POST /api/v1/content/save-url` count: 0

## Outcome

- Acceptance outcomes passed: true
- Rollback required: false
- Rollback deployment ID: deployment-rollback
- Notes: Sanitized test fixture; no credentials or headers.
"""


def _replace_field(evidence: str, label: str, value: str) -> str:
    lines = evidence.splitlines()
    prefix = f"- {label}:"
    return "\n".join(f"{prefix} {value}" if line.startswith(prefix) else line for line in lines)


def test_detached_release_runbook_stamps_before_upload() -> None:
    runbook = RUNBOOK.read_text(encoding="utf-8")
    stamp_command = 'python scripts/stamp_release_revision.py "$ACA_FRONTEND_CANDIDATE_SHA"'
    upload_command = "railway up"

    assert stamp_command in runbook
    assert runbook.index(stamp_command) < runbook.index(
        upload_command, runbook.index(stamp_command)
    )
    assert "`verified_detached_sha` provenance" in runbook
    assert "Record\n   that digest in the release evidence before upload" in runbook


def test_runbook_separates_deployment_from_protected_release_smoke() -> None:
    runbook = RUNBOOK.read_text(encoding="utf-8")

    assert "#### Automated cross-surface release gate" in runbook
    assert "`release-smoke-production`" in runbook
    assert "`release-smoke-staging`" in runbook
    assert "gh workflow run release-smoke.yml -f tier=production" in runbook
    assert "gh workflow run release-smoke.yml -f tier=staging" in runbook
    assert "it never performs deployment or rollback" in runbook


def test_complete_sanitized_evidence_passes(complete_evidence: str) -> None:
    assert validate_evidence(complete_evidence) == []


@pytest.mark.parametrize(
    "field",
    [
        "Candidate commit SHA",
        "GitHub `frontend-release` check URL",
        "Last successful deployment ID",
        "Rollback command",
        "Browser/session attribution",
        "Durable operation ID",
        "Canonical ingestion request correlation",
        "Rollback deployment ID",
    ],
)
def test_blank_critical_field_is_rejected(
    complete_evidence: str,
    field: str,
) -> None:
    errors = validate_evidence(_replace_field(complete_evidence, field, ""))

    assert any(field in error and "must not be blank" in error for error in errors)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        (
            "GitHub check conclusion and checked SHA",
            f"success; checked_sha={'d' * 40}",
        ),
        ("Deployed candidate revision", "e" * 40),
    ],
)
def test_candidate_ci_and_deployed_revisions_must_match(
    complete_evidence: str,
    field: str,
    value: str,
) -> None:
    errors = validate_evidence(_replace_field(complete_evidence, field, value))

    assert any("revision mismatch" in error for error in errors)


def test_railway_cli_release_message_must_name_candidate(
    complete_evidence: str,
) -> None:
    errors = validate_evidence(
        _replace_field(
            complete_evidence,
            "Railway CLI release message",
            f"frontend-release {'d' * 40}",
        )
    )

    assert any("Railway CLI release message" in error for error in errors)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        (
            "GitHub check conclusion and checked SHA",
            f"failure; checked_sha={SHA}",
            "GitHub check conclusion",
        ),
        ("Build status", "FAILED", "Build status"),
        ("Deployment status", "FAILED", "Deployment status"),
        ("Durable operation terminal status", "failed", "operation terminal status"),
    ],
)
def test_non_success_release_states_are_rejected(
    complete_evidence: str,
    field: str,
    value: str,
    message: str,
) -> None:
    errors = validate_evidence(_replace_field(complete_evidence, field, value))

    assert any(message in error and "successful" in error for error in errors)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("Deployment start UTC", "not-a-time"),
        ("Verification window end UTC", "2026-07-23T14:06:00"),
        ("Log query window", "2026-07-23T14:10:00Z/2026-07-23T14:06:00Z"),
    ],
)
def test_invalid_or_non_utc_windows_are_rejected(
    complete_evidence: str,
    field: str,
    value: str,
) -> None:
    errors = validate_evidence(_replace_field(complete_evidence, field, value))

    assert any("UTC" in error or "window" in error for error in errors)


@pytest.mark.parametrize(
    ("start_field", "end_field"),
    [
        ("Deployment start UTC", "Deployment end UTC"),
        ("Verification window start UTC", "Verification window end UTC"),
    ],
)
def test_reversed_windows_are_rejected(
    complete_evidence: str,
    start_field: str,
    end_field: str,
) -> None:
    evidence = _replace_field(
        complete_evidence,
        start_field,
        "2026-07-23T14:10:00Z",
    )
    evidence = _replace_field(evidence, end_field, "2026-07-23T14:00:00Z")

    errors = validate_evidence(evidence)

    assert any("must be before" in error for error in errors)


@pytest.mark.parametrize(
    "field",
    [
        "Browser/session attribution",
        "Capability request correlation",
        "Canonical ingestion request correlation",
    ],
)
def test_missing_browser_or_backend_correlation_is_rejected(
    complete_evidence: str,
    field: str,
) -> None:
    errors = validate_evidence(_replace_field(complete_evidence, field, ""))

    assert any("correlation" in error.lower() or field in error for error in errors)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        (
            "Capability request correlation",
            "GET /api/v1/capabilities; 200; 2026-07-23T14:07:00Z; HeadlessChrome/149",
            "request attribution",
        ),
        (
            "Canonical ingestion request correlation",
            "requestId ingestion-123; operation-123; POST /api/v1/ingestions; 202; "
            "2026-07-23T14:11:00Z; HeadlessChrome/149",
            "verification window",
        ),
        (
            "Capability request correlation",
            "requestId capability-123; GET /api/v1/capabilities; 200; not-a-time; "
            "HeadlessChrome/149",
            "timestamp",
        ),
        (
            "Canonical ingestion request correlation",
            "requestId ingestion-123; operation-123; POST /api/v1/ingestions; 202; "
            "2026-07-23T14:08:00Z; unknown-client",
            "browser attribution",
        ),
    ],
)
def test_backend_correlation_is_attributed_and_bounded(
    complete_evidence: str,
    field: str,
    value: str,
    message: str,
) -> None:
    errors = validate_evidence(_replace_field(complete_evidence, field, value))

    assert any(message in error for error in errors)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("Uploaded lockfile observed", "package-lock.json"),
        ("Railpack install command", "npm install"),
        ("Railpack Node version", "25.6.1"),
    ],
)
def test_railpack_build_facts_are_enforced(
    complete_evidence: str,
    field: str,
    value: str,
) -> None:
    errors = validate_evidence(_replace_field(complete_evidence, field, value))

    assert any(field in error for error in errors)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("Visible form submission count", "0", "exactly 1"),
        ("Visible form submission count", "2", "exactly 1"),
        ("Client retries observed", "1", "exactly 0"),
        ("`POST /api/v1/contents/ingest` count", "1", "retired route"),
        ("`POST /api/v1/content/save-url` count", "3", "retired route"),
    ],
)
def test_request_counts_enforce_one_shot_canonical_submission(
    complete_evidence: str,
    field: str,
    value: str,
    message: str,
) -> None:
    errors = validate_evidence(_replace_field(complete_evidence, field, value))

    assert any(message in error for error in errors)


def test_cli_returns_one_and_actionable_errors(
    complete_evidence: str,
    tmp_path: Path,
) -> None:
    evidence_path = tmp_path / "production-deployment.md"
    evidence_path.write_text(
        _replace_field(complete_evidence, "Deployment status", "FAILED"),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(VALIDATOR), str(evidence_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Deployment status" in result.stderr
    assert "FAILED" in result.stderr


def test_cli_returns_zero_for_complete_evidence(
    complete_evidence: str,
    tmp_path: Path,
) -> None:
    evidence_path = tmp_path / "production-deployment.md"
    evidence_path.write_text(complete_evidence, encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(VALIDATOR), str(evidence_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "evidence validation passed" in result.stdout
    assert result.stderr == ""
