"""CI installs the project from uv.lock, never from the newest allowed versions.

Unpinned ``uv pip install -e ".[dev]"`` resolved whatever PyPI served that day,
so new releases (SQLAlchemy 2.1, mcp 2.0, trafilatura 2.3) turned every branch
red overnight, while the Docker image (``uv sync --frozen``) kept running the
locked versions CI was no longer testing.
"""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
CONSTRAINTS = '-c "$RUNNER_TEMP/uv-constraints.txt"'
EXPORT = re.compile(r"uv export --locked\b.*-o \"\$RUNNER_TEMP/uv-constraints\.txt\"")
PROJECT_INSTALL = re.compile(r"uv pip install\b.*\s-e\s+\"\.")


def _job_scripts() -> list[tuple[str, list[str]]]:
    jobs = []
    for workflow in WORKFLOWS:
        for name, job in (yaml.safe_load(workflow.read_text()).get("jobs") or {}).items():
            scripts = [step["run"] for step in job.get("steps", []) if "run" in step]
            jobs.append((f"{workflow.name}:{name}", scripts))
    return jobs


def test_every_project_install_is_constrained_to_the_lock() -> None:
    checked = 0
    for job, scripts in _job_scripts():
        exported = False
        for script in scripts:
            for line in script.splitlines():
                if EXPORT.search(line):
                    exported = True
                if PROJECT_INSTALL.search(line):
                    checked += 1
                    assert CONSTRAINTS in line, f"{job}: unconstrained install: {line.strip()}"
                    assert exported, f"{job}: installs before exporting uv.lock constraints"
    assert checked >= 10, "expected the CI, deploy, neon and scheduled jobs to install the project"


def test_dependabot_updates_the_lock() -> None:
    config = yaml.safe_load((ROOT / ".github" / "dependabot.yml").read_text())
    ecosystems = {update["package-ecosystem"] for update in config["updates"]}
    assert "uv" in ecosystems
    assert "pip" not in ecosystems, "the pip ecosystem bumps ranges but never uv.lock"
