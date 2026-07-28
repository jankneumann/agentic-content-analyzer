"""Configuration contract for the enforced CLI gen-eval jobs."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPO_ROOT / ".github/workflows/cli-gen-eval.yml"
READ_ONLY_CATEGORIES = "plumbing discovery validation"
MUTATING_CATEGORIES = "workflow-submission operation-control"


def _workflow() -> dict[str, Any]:
    return cast(dict[str, Any], yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8")))


def _job(name: str) -> dict[str, Any]:
    return cast(dict[str, Any], _workflow()["jobs"][name])


def _step(job: dict[str, Any], name: str) -> dict[str, Any]:
    return next(step for step in job["steps"] if step.get("name") == name)


def test_triggers_separate_pull_request_reads_from_dispatched_mutations() -> None:
    workflow = _workflow()
    triggers = cast(dict[str, Any], workflow.get("on") or workflow.get(cast(Any, True)))

    assert triggers == {"pull_request": None, "workflow_dispatch": None}
    assert workflow["permissions"] == {"contents": "read"}
    assert set(workflow["jobs"]) == {"read-only", "staging-mutation"}

    read_only = _job("read-only")
    staging = _job("staging-mutation")
    assert read_only["if"] == "github.event_name == 'pull_request'"
    assert "environment" not in read_only
    assert staging["if"] == (
        "github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main'"
    )
    assert staging["environment"] == "release-smoke-staging"


def test_actions_and_toolchain_are_immutable() -> None:
    for job in _workflow()["jobs"].values():
        for step in job["steps"]:
            action = step.get("uses")
            if action is not None:
                assert re.fullmatch(r"[^@]+@[0-9a-f]{40}", action)
            if step.get("name") == "Install uv":
                assert step["with"]["version"] == "0.9.18"


def test_contract_enforces_before_the_runner_is_acquired_from_the_pin() -> None:
    workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")

    for job_name in ("read-only", "staging-mutation"):
        job = _job(job_name)
        names = [step.get("name") for step in job["steps"]]
        contract = _step(job, "Validate runner-independent contract")
        acquire = _step(job, "Acquire and verify pinned runner")

        assert names.index(contract["name"]) < names.index(acquire["name"])
        assert contract["run"] == "make gen-eval-contract"
        assert "./evaluation/run-gate.sh --resolve-only" in acquire["run"]
        assert job["env"]["ACA_GEN_EVAL_REQUIRE"] == "1"

    assert "ACA_GEN_EVAL_BIN" not in workflow_text
    assert "ACA_GEN_EVAL_PROJECT" not in workflow_text
    assert "agentic-coding-tools.git" not in workflow_text
    assert "../agentic-coding-tools" not in workflow_text


def test_pull_request_job_runs_only_the_enforced_read_only_selection() -> None:
    job = _job("read-only")
    run = _step(job, "Run read-only CLI gen-eval")

    assert job["env"]["API_BASE_URL"] == "http://127.0.0.1:8000"
    assert "${{ secrets." not in str(job)
    assert run["continue-on-error"] is True
    assert f"--categories {READ_ONLY_CATEGORIES}" in run["run"]
    assert f"--categories {MUTATING_CATEGORIES}" not in run["run"]
    assert "--target-policy" not in run["run"]
    assert "--offline" not in run["run"]
    assert '--output-dir "$RUNNER_TEMP/cli-gen-eval"' in run["run"]


def test_staging_job_binds_mutation_policy_to_protected_environment() -> None:
    job = _job("staging-mutation")
    materialize = _step(job, "Materialize protected staging target policy")
    run = _step(job, "Run guarded staging CLI gen-eval")

    assert job["env"]["API_BASE_URL"] == "${{ vars.API_ORIGIN }}"
    assert run["env"] == {
        "ACA_RELEASE_SMOKE": "1",
        "ADMIN_API_KEY": "${{ secrets.ADMIN_API_KEY }}",
    }
    assert materialize["env"] == {
        "ACA_TARGET_ID": "${{ vars.TARGET_ID }}",
        "ACA_FRONTEND_ORIGIN": "${{ vars.FRONTEND_ORIGIN }}",
        "ACA_API_ORIGIN": "${{ vars.API_ORIGIN }}",
        "ACA_EXPECTED_FRONTEND_REVISION": "${{ vars.EXPECTED_FRONTEND_REVISION }}",
        "ACA_EXPECTED_API_REVISION": "${{ vars.EXPECTED_API_REVISION }}",
        "ACA_PRODUCTION_TARGET_IDS_JSON": "${{ vars.PRODUCTION_TARGET_IDS_JSON }}",
        "ACA_PRODUCTION_ORIGINS_JSON": "${{ vars.PRODUCTION_ORIGINS_JSON }}",
    }
    assert 'target: "staging"' in materialize["run"]
    assert "try ($production_target_ids_json | fromjson) catch null" in materialize["run"]
    assert "try ($production_origins_json | fromjson) catch null" in materialize["run"]
    assert "expected_frontend_revision: $expected_frontend_revision" in materialize["run"]
    assert "expected_api_revision: $expected_api_revision" in materialize["run"]
    assert "${{ inputs." not in materialize["run"]
    assert run["continue-on-error"] is True
    assert f"--categories {MUTATING_CATEGORIES}" in run["run"]
    assert '--target-policy "$RUNNER_TEMP/cli-gen-eval-policy.json"' in run["run"]
    assert f"--categories {READ_ONLY_CATEGORIES}" not in run["run"]


def test_only_credible_reports_are_retained_without_masking_gate_failure() -> None:
    for job_name, artifact_suffix in (
        ("read-only", "read-only"),
        ("staging-mutation", "staging"),
    ):
        job = _job(job_name)
        names = [step.get("name") for step in job["steps"]]
        run_name = (
            "Run read-only CLI gen-eval"
            if job_name == "read-only"
            else "Run guarded staging CLI gen-eval"
        )
        validate_name = "Validate report credibility for retention"
        upload_name = "Retain CLI gen-eval evidence"
        enforce_name = "Enforce CLI gen-eval gate"
        validate = _step(job, validate_name)
        upload = _step(job, upload_name)
        enforce = _step(job, enforce_name)

        assert (
            names.index(run_name)
            < names.index(validate_name)
            < names.index(upload_name)
            < names.index(enforce_name)
        )
        assert validate["if"] == "always()"
        assert "scripts/minimize_gen_eval_report.py" in validate["run"]
        assert '"$RUNNER_TEMP/cli-gen-eval/gen-eval-report.json"' in validate["run"]
        assert '"$RUNNER_TEMP/cli-gen-eval-artifact/gen-eval-report.json"' in validate["run"]
        assert "--fail-threshold 0" in validate["run"]
        assert "--expectation" in validate["run"]
        assert upload["if"] == "always() && steps.validate.outcome == 'success'"
        assert upload["uses"].startswith("actions/upload-artifact@")
        assert upload["with"]["name"].startswith(f"cli-gen-eval-{artifact_suffix}-")
        assert (
            "${{ runner.temp }}/cli-gen-eval-artifact/gen-eval-report.json"
            in upload["with"]["path"]
        )
        assert (
            "${{ runner.temp }}/cli-gen-eval-artifact/gen-eval-expectation.json"
            in upload["with"]["path"]
        )
        assert "${{ runner.temp }}/cli-gen-eval/gen-eval-report.json" not in upload["with"]["path"]
        assert upload["with"]["if-no-files-found"] == "error"
        assert upload["with"]["retention-days"] == 14
        assert enforce["if"] == "always()"
        assert 'test "$RUN_OUTCOME" = "success"' in enforce["run"]
        assert 'test "$VALIDATION_OUTCOME" = "success"' in enforce["run"]


def test_ci_uses_the_gate_owned_deterministic_generation_mode() -> None:
    gate_text = (REPO_ROOT / "scripts/run_gen_eval_gate.py").read_text(encoding="utf-8")
    workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert '"--mode",' in gate_text
    assert '"template-only",' in gate_text
    for credential in (
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GOOGLE_API_KEY",
        "GEMINI_API_KEY",
    ):
        assert credential not in workflow_text
