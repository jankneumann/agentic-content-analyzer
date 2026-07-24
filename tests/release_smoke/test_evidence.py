"""Sanitized release-smoke evidence schema and semantic tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from src.release_smoke.browser import AssetEvidence, BrowserObservation
from src.release_smoke.evidence import (
    minimal_validator_failure_evidence,
    validate_evidence,
)
from src.release_smoke.models import ProtectedTargetPolicy, SurfaceObservation
from src.release_smoke.orchestrator import run_release_smoke
from src.release_smoke.runner import ReleaseSmokeError

REPO_ROOT = Path(__file__).resolve().parents[2]
SHA = "a" * 40


def _valid_evidence() -> dict[str, object]:
    return {
        "schema_version": 1,
        "run_id": "1" * 32,
        "target": "production",
        "started_at": "2026-07-23T00:00:00Z",
        "finished_at": "2026-07-23T00:00:05Z",
        "frontend": {
            "origin": "https://frontend.example.test",
            "observed_revision": SHA,
            "revision_source": "verified_detached_sha",
            "expected_revision": SHA,
        },
        "api": {
            "origin": "https://api.example.test",
            "observed_revision": SHA,
            "revision_source": "railway_commit_sha",
            "expected_revision": SHA,
        },
        "checks": [
            {"name": "api_discovery", "surface": "api", "status": "passed"},
            {"name": "cli_discovery", "surface": "cli", "status": "passed"},
            {
                "name": "frontend_discovery",
                "surface": "frontend",
                "status": "passed",
            },
        ],
        "retired_route_count": 0,
        "assets": [{"sha256": "b" * 64, "size_bytes": 100}],
        "operation": None,
        "result": "passed",
        "failure_codes": [],
    }


def test_valid_sanitized_evidence_passes() -> None:
    assert validate_evidence(_valid_evidence()) == []


def test_failed_pre_observation_envelope_allows_nulls_with_stable_code() -> None:
    evidence = minimal_validator_failure_evidence(
        run_id="1" * 32,
        target="production",
        started_at="2026-07-23T00:00:00Z",
        finished_at="2026-07-23T00:00:01Z",
    )

    assert validate_evidence(evidence) == []
    assert evidence["frontend"]["origin"] is None
    assert evidence["api"]["observed_revision"] is None


def test_passing_evidence_cannot_have_null_observation() -> None:
    evidence = _valid_evidence()
    assert isinstance(evidence["frontend"], dict)
    evidence["frontend"]["observed_revision"] = None

    assert validate_evidence(evidence)


def test_passing_evidence_requires_zero_retired_routes_and_matching_revisions() -> None:
    retired = deepcopy(_valid_evidence())
    retired["retired_route_count"] = 1
    mismatch = deepcopy(_valid_evidence())
    assert isinstance(mismatch["api"], dict)
    mismatch["api"]["expected_revision"] = "c" * 40

    assert any("retired" in error for error in validate_evidence(retired))
    assert any("revision" in error for error in validate_evidence(mismatch))


def test_sensitive_or_additional_fields_are_rejected() -> None:
    evidence = _valid_evidence()
    evidence["request_headers"] = {"Authorization": "Bearer credential"}

    errors = validate_evidence(evidence)

    assert errors
    assert any("request_headers" in error or "sensitive" in error for error in errors)


def test_schema_errors_never_echo_rejected_values() -> None:
    evidence = _valid_evidence()
    assert isinstance(evidence["frontend"], dict)
    secret_value = "api_key=TOPSECRET"
    evidence["frontend"]["origin"] = secret_value
    evidence["failure_codes"] = [{}]

    errors = validate_evidence(evidence)

    assert errors
    assert secret_value not in json.dumps(errors)


def test_passing_release_requires_all_surfaces_and_trusted_provenance() -> None:
    missing_check = _valid_evidence()
    assert isinstance(missing_check["checks"], list)
    missing_check["checks"] = missing_check["checks"][:1]
    bad_provenance = _valid_evidence()
    assert isinstance(bad_provenance["api"], dict)
    bad_provenance["api"]["revision_source"] = "local_development"
    missing_expectation = _valid_evidence()
    assert isinstance(missing_expectation["api"], dict)
    missing_expectation["api"]["expected_revision"] = None
    wrong_surface = _valid_evidence()
    assert isinstance(wrong_surface["checks"], list)
    assert isinstance(wrong_surface["checks"][0], dict)
    wrong_surface["checks"][0]["surface"] = "evidence"
    no_assets = _valid_evidence()
    no_assets["assets"] = []

    assert any("required surface" in error for error in validate_evidence(missing_check))
    assert any("provenance" in error for error in validate_evidence(bad_provenance))
    assert any("requires a SHA" in error for error in validate_evidence(missing_expectation))
    assert any("required surface" in error for error in validate_evidence(wrong_surface))
    assert any("nonempty asset" in error for error in validate_evidence(no_assets))


def test_passing_mutation_target_requires_completed_operation() -> None:
    evidence = _valid_evidence()
    evidence["target"] = "staging"

    errors = validate_evidence(evidence)

    assert any("mutation check" in error for error in errors)
    assert any("completed operation" in error for error in errors)


def test_reversed_or_unbounded_window_is_rejected() -> None:
    evidence = _valid_evidence()
    evidence["finished_at"] = "2026-07-22T00:00:00Z"

    assert any("time" in error or "window" in error for error in validate_evidence(evidence))


def test_runtime_schema_matches_reviewed_openspec_contract() -> None:
    runtime = json.loads(
        (REPO_ROOT / "src/release_smoke/release_smoke_evidence.schema.json").read_text()
    )
    reviewed = json.loads(
        (
            REPO_ROOT
            / "openspec/changes/add-cross-surface-release-smoke-tests/contracts"
            / "release-smoke-evidence.schema.json"
        ).read_text()
    )

    assert runtime == reviewed


def test_standalone_validator_imports_repository_package(tmp_path: Path) -> None:
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(_valid_evidence()), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/validate_release_smoke_evidence.py"),
            str(evidence_path),
        ],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "release-smoke evidence: VALID"


def test_standalone_validator_never_echoes_rejected_values(tmp_path: Path) -> None:
    evidence_path = tmp_path / "invalid.json"
    secret_value = "api_key=TOPSECRET"
    evidence_path.write_text(
        json.dumps(
            {
                "frontend": {"origin": secret_value},
                "failure_codes": ["TOPSECRET_UNOBSERVED"],
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/validate_release_smoke_evidence.py"),
            str(evidence_path),
        ],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert secret_value not in result.stdout
    assert secret_value not in result.stderr
    assert "TOPSECRET_UNOBSERVED" not in result.stdout
    assert "TOPSECRET_UNOBSERVED" not in result.stderr


def test_standalone_validator_replaces_missing_output_with_safe_envelope(
    tmp_path: Path,
) -> None:
    evidence_path = tmp_path / "missing.json"

    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/validate_release_smoke_evidence.py"),
            str(evidence_path),
            "--replace-invalid-with-failure-target",
            "production",
        ],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))

    assert result.returncode == 2
    assert evidence["result"] == "failed"
    assert evidence["failure_codes"] == ["VALIDATOR_OUTPUT_REJECTED"]
    assert validate_evidence(evidence) == []


def test_standalone_runner_writes_valid_failure_evidence_before_observation(
    tmp_path: Path,
) -> None:
    policy_path = tmp_path / "invalid-policy.json"
    policy_path.write_text("{}", encoding="utf-8")
    evidence_path = tmp_path / "evidence.json"

    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/run_release_smoke.py"),
            "--policy-file",
            str(policy_path),
            "--output",
            str(evidence_path),
            "--target",
            "production",
        ],
        cwd=tmp_path,
        env={"ADMIN_API_KEY": "test-only", "PATH": os.environ["PATH"]},
        check=False,
        capture_output=True,
        text=True,
    )
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))

    assert result.returncode == 1
    assert evidence["result"] == "failed"
    assert evidence["failure_codes"] == ["VALIDATOR_OUTPUT_REJECTED"]
    assert validate_evidence(evidence) == []


def test_orchestrator_returns_minimized_passing_evidence(
    monkeypatch,
    tmp_path: Path,
) -> None:
    policy = ProtectedTargetPolicy(
        target_id="production-primary",
        target="production",
        frontend_origin="https://frontend.example.test",
        api_origin="https://api.example.test",
        expected_frontend_revision=SHA,
        expected_api_revision=SHA,
        production_target_ids=["production-primary"],
        production_origins=[
            "https://frontend.example.test",
            "https://api.example.test",
        ],
    )
    monkeypatch.setattr(
        "src.release_smoke.orchestrator.run_api_discovery",
        lambda *_args, **_kwargs: SurfaceObservation(
            revision=SHA,
            revision_source="railway_commit_sha",
        ),
    )
    monkeypatch.setattr(
        "src.release_smoke.orchestrator.run_cli_discovery",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "src.release_smoke.orchestrator.load_retired_routes",
        lambda *_args, **_kwargs: (),
    )
    monkeypatch.setattr(
        "src.release_smoke.orchestrator.run_browser_discovery",
        lambda *_args, **_kwargs: BrowserObservation(
            revision=SHA,
            revision_source="verified_detached_sha",
            assets=(AssetEvidence(path="/app.js", sha256="b" * 64, size_bytes=10),),
            retired_route_count=0,
        ),
    )

    evidence = run_release_smoke(
        policy,
        admin_key="admin",
        app_secret="app-password",
        repo_root=tmp_path,
    )

    assert evidence["result"] == "passed"
    assert evidence["assets"] == [{"sha256": "b" * 64, "size_bytes": 10}]
    assert "app-password" not in json.dumps(evidence)


def test_orchestrator_replaces_invalid_output_with_safe_failure_envelope(
    monkeypatch,
    tmp_path: Path,
) -> None:
    policy = ProtectedTargetPolicy(
        target_id="local-fixture",
        target="local",
        frontend_origin="http://127.0.0.1:5173",
        api_origin="http://127.0.0.1:8000",
        expected_frontend_revision=None,
        expected_api_revision=None,
        production_target_ids=[],
        production_origins=[],
    )
    monkeypatch.setattr(
        "src.release_smoke.orchestrator.run_api_discovery",
        lambda *_args, **_kwargs: SurfaceObservation(
            revision="development",
            revision_source="local_development",
        ),
    )
    monkeypatch.setattr(
        "src.release_smoke.orchestrator.run_cli_discovery",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "src.release_smoke.orchestrator.load_retired_routes",
        lambda *_args, **_kwargs: (),
    )
    monkeypatch.setattr(
        "src.release_smoke.orchestrator.run_browser_discovery",
        lambda *_args, **_kwargs: BrowserObservation(
            revision="development",
            revision_source="local_development",
            assets=(),
            retired_route_count=0,
        ),
    )
    validations = iter((["synthetic invalid report"], []))
    monkeypatch.setattr(
        "src.release_smoke.orchestrator.validate_evidence",
        lambda _document: next(validations),
    )

    evidence = run_release_smoke(
        policy,
        admin_key="admin",
        app_secret=None,
        repo_root=tmp_path,
    )

    assert evidence["result"] == "failed"
    assert evidence["failure_codes"] == ["VALIDATOR_OUTPUT_REJECTED"]


def test_fixture_without_mutation_authorization_fails_before_network(
    monkeypatch,
    tmp_path: Path,
) -> None:
    policy = ProtectedTargetPolicy(
        target_id="local-fixture",
        target="local",
        frontend_origin="http://127.0.0.1:5173",
        api_origin="http://127.0.0.1:8000",
        expected_frontend_revision=None,
        expected_api_revision=None,
        production_target_ids=[],
        production_origins=[],
    )
    called = False

    def unexpected_network(*_args, **_kwargs) -> SurfaceObservation:
        nonlocal called
        called = True
        raise AssertionError("network must not run")

    monkeypatch.setattr(
        "src.release_smoke.orchestrator.run_api_discovery",
        unexpected_network,
    )

    with pytest.raises(ReleaseSmokeError, match="explicit authorization"):
        run_release_smoke(
            policy,
            admin_key="admin",
            app_secret=None,
            repo_root=tmp_path,
            fixture_name="url.json",
        )

    assert called is False
