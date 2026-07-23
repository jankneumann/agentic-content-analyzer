"""Regression contract for the production frontend CI gate."""

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CI_WORKFLOW = REPO_ROOT / ".github/workflows/ci.yml"


def _frontend_job() -> dict[str, Any]:
    workflow = yaml.safe_load(CI_WORKFLOW.read_text())
    return workflow["jobs"]["frontend-release"]


def _step(job: dict[str, Any], name: str) -> dict[str, Any]:
    return next(step for step in job["steps"] if step.get("name") == name)


def test_frontend_release_job_uses_node_22_and_least_privilege() -> None:
    workflow = yaml.safe_load(CI_WORKFLOW.read_text())
    job = workflow["jobs"]["frontend-release"]

    assert job["name"] == "frontend-release"
    assert job["runs-on"] == "ubuntu-latest"
    assert workflow["permissions"] == {"contents": "read"}
    assert "permissions" not in job

    node_step = _step(job, "Set up Node.js")
    assert node_step["uses"].startswith("actions/setup-node@")
    assert node_step["with"]["node-version"] == "22"
    assert node_step["with"]["cache"] == "npm"
    assert node_step["with"]["cache-dependency-path"] == "web/package-lock.json"


def test_frontend_release_job_runs_reproducible_build_commands() -> None:
    job = _frontend_job()

    expected_commands = [
        ("Install frontend dependencies", "npm ci"),
        ("Check generated workflow contracts", "npm run contracts:check"),
        (
            "Run workflow contract client tests",
            "npm test -- --run src/lib/api/__tests__/workflow-contracts.test.ts",
        ),
        ("Build production frontend", "npm run build"),
    ]
    for name, command in expected_commands:
        step = _step(job, name)
        assert step["working-directory"] == "web"
        assert step["run"] == command

    step_names = [step.get("name") for step in job["steps"]]
    assert step_names.index("Install frontend dependencies") < step_names.index(
        "Check generated workflow contracts"
    )
    assert step_names.index("Check generated workflow contracts") < step_names.index(
        "Run workflow contract client tests"
    )
    assert step_names.index("Run workflow contract client tests") < step_names.index(
        "Build production frontend"
    )


def test_frontend_release_job_installs_python_and_uv_for_contract_generation() -> None:
    job = _frontend_job()

    python_step = _step(job, "Set up Python")
    assert python_step["uses"].startswith("actions/setup-python@")
    assert python_step["with"]["python-version"] == "3.12"

    uv_step = _step(job, "Install uv")
    assert uv_step["uses"].startswith("astral-sh/setup-uv@")
