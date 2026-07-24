"""Configuration contract for protected deployed release-smoke jobs."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPO_ROOT / ".github/workflows/release-smoke.yml"


def _workflow() -> dict[str, Any]:
    return cast(dict[str, Any], yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8")))


def _job(name: str) -> dict[str, Any]:
    return cast(dict[str, Any], _workflow()["jobs"][name])


def _step(job: dict[str, Any], name: str) -> dict[str, Any]:
    return next(step for step in job["steps"] if step.get("name") == name)


def test_caller_selects_only_a_fixed_tier() -> None:
    workflow = _workflow()
    triggers = cast(dict[str, Any], workflow.get("on") or workflow.get(cast(Any, True)))
    trigger = triggers["workflow_dispatch"]

    assert trigger["inputs"] == {
        "tier": {
            "description": "Already-deployed target tier to verify",
            "required": True,
            "type": "choice",
            "options": ["production", "staging"],
        }
    }
    assert workflow["permissions"] == {"contents": "read"}
    assert set(workflow["jobs"]) == {"production-read-only", "staging-mutation"}


def test_jobs_use_separate_approval_protected_environments() -> None:
    production = _job("production-read-only")
    staging = _job("staging-mutation")

    assert production["if"] == "inputs.tier == 'production'"
    assert production["environment"] == "release-smoke-production"
    assert staging["if"] == "inputs.tier == 'staging'"
    assert staging["environment"] == "release-smoke-staging"
    assert production["timeout-minutes"] == staging["timeout-minutes"] == 20
    assert "permissions" not in production
    assert "permissions" not in staging


def test_secret_bearing_jobs_pin_actions_and_toolchain() -> None:
    for job in _workflow()["jobs"].values():
        for step in job["steps"]:
            action = step.get("uses")
            if action is not None:
                assert re.fullmatch(r"[^@]+@[0-9a-f]{40}", action)
            if step.get("name") == "Install uv":
                assert step["with"]["version"] == "0.9.18"


def test_exact_target_policy_comes_only_from_environment_variables() -> None:
    expected_vars = {
        "ACA_TARGET_ID": "${{ vars.TARGET_ID }}",
        "ACA_FRONTEND_ORIGIN": "${{ vars.FRONTEND_ORIGIN }}",
        "ACA_API_ORIGIN": "${{ vars.API_ORIGIN }}",
        "ACA_EXPECTED_FRONTEND_REVISION": "${{ vars.EXPECTED_FRONTEND_REVISION }}",
        "ACA_EXPECTED_API_REVISION": "${{ vars.EXPECTED_API_REVISION }}",
        "ACA_PRODUCTION_TARGET_IDS_JSON": "${{ vars.PRODUCTION_TARGET_IDS_JSON }}",
        "ACA_PRODUCTION_ORIGINS_JSON": "${{ vars.PRODUCTION_ORIGINS_JSON }}",
    }

    for job_name, step_name, target in (
        ("production-read-only", "Materialize protected production policy", "production"),
        ("staging-mutation", "Materialize protected staging policy", "staging"),
    ):
        step = _step(_job(job_name), step_name)
        assert step["env"] == expected_vars
        assert f'target: "{target}"' in step["run"]
        assert '--arg production_target_ids_json "$ACA_PRODUCTION_TARGET_IDS_JSON"' in step["run"]
        assert "try ($production_target_ids_json | fromjson) catch null" in step["run"]
        assert '--arg production_origins_json "$ACA_PRODUCTION_ORIGINS_JSON"' in step["run"]
        assert "try ($production_origins_json | fromjson) catch null" in step["run"]
        assert "${{ inputs." not in step["run"]


def test_credentials_are_environment_only_and_production_cannot_mutate() -> None:
    production = _step(_job("production-read-only"), "Run production read-only smoke")
    staging = _step(
        _job("staging-mutation"),
        "Run approval-controlled staging mutation smoke",
    )
    expected_secret_env = {
        "ADMIN_API_KEY": "${{ secrets.ADMIN_API_KEY }}",
        "APP_SECRET_KEY": "${{ secrets.APP_SECRET_KEY }}",
    }

    assert production["env"] == staging["env"] == expected_secret_env
    assert "--target production" in production["run"]
    assert "--allow-mutations" not in production["run"]
    assert "--fixture" not in production["run"]
    assert "--target staging" in staging["run"]
    assert "--allow-mutations" in staging["run"]
    assert "--fixture url.json" in staging["run"]
    for job in _workflow()["jobs"].values():
        for step in job["steps"]:
            assert "${{ secrets." not in step.get("run", "")


def test_validated_evidence_is_the_only_retained_artifact() -> None:
    for job_name, suffix in (
        ("production-read-only", "production"),
        ("staging-mutation", "staging"),
    ):
        job = _job(job_name)
        names = [step.get("name") for step in job["steps"]]
        validate_name = "Validate sanitized evidence"
        upload_name = f"Retain validated {suffix} evidence"
        validate = _step(job, validate_name)
        upload = _step(job, upload_name)
        enforce = _step(job, f"Enforce {suffix} compatibility gate")

        assert (
            names.index(validate_name)
            < names.index(upload_name)
            < names.index(f"Enforce {suffix} compatibility gate")
        )
        assert validate["if"] == "always()"
        assert f"--replace-invalid-with-failure-target {suffix}" in validate["run"]
        assert upload["if"] == "always() && steps.validate.outcome == 'success'"
        assert upload["uses"].startswith("actions/upload-artifact@")
        assert upload["with"]["path"] == "${{ runner.temp }}/release-smoke-evidence.json"
        assert upload["with"]["if-no-files-found"] == "error"
        assert upload["with"]["retention-days"] == 14
        assert enforce["if"] == "always()"
        assert 'test "$VALIDATION_OUTCOME" = "success"' in enforce["run"]
        assert 'test "$SMOKE_OUTCOME" = "success"' in enforce["run"]

    workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8").casefold()
    for unsafe_artifact in ("playwright-report", "trace.zip", "video", "har", "raw log"):
        assert unsafe_artifact not in workflow_text


def test_workflow_verifies_an_existing_release_without_deploying() -> None:
    workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "scripts/run_release_smoke.py" in workflow_text
    assert "scripts/validate_release_smoke_evidence.py" in workflow_text
    assert "railway up" not in workflow_text
    assert "git push" not in workflow_text
