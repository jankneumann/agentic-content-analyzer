"""Convergence must never stage .git-context runtime manifests (issue #502)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS = (
    Path(__file__).resolve().parents[1] / ".agents" / "skills" / "merge-pull-requests" / "scripts"
)
sys.path.insert(0, str(_SCRIPTS))

from main_convergence import (  # noqa: E402
    GIT_CONTEXT_PREFIX,
    ConvergenceApparatusError,
    run_command,
    stage_convergence_tree,
)

MANIFEST = f"{GIT_CONTEXT_PREFIX}/context-refresh-manifest.json"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],  # noqa: S607
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def _repo(tmp_path: Path, *, ignore_git_context: bool) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "convergence@example.test")
    _git(repo, "config", "user.name", "Convergence Test")
    gitignore = repo / ".gitignore"
    lines = ["*.pyc\n"]
    if ignore_git_context:
        lines.append(".git-context/\n")
    gitignore.write_text("".join(lines))
    (repo / "docs" / "merge-logs").mkdir(parents=True)
    (repo / "docs" / "merge-logs" / "context-convergence.jsonl").write_text("{}\n")
    (repo / "cleanup.txt").write_text("staged cleanup output\n")
    runtime = repo / GIT_CONTEXT_PREFIX
    runtime.mkdir()
    (runtime / "context-refresh-manifest.json").write_text('{"ephemeral": true}\n')
    _git(repo, "add", ".gitignore", "docs/merge-logs/context-convergence.jsonl")
    _git(repo, "commit", "-m", "init")
    return repo


def _cached(repo: Path) -> list[str]:
    diff = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],  # noqa: S607
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in diff.stdout.splitlines() if line]


def test_stage_convergence_excludes_runtime_manifest(tmp_path: Path) -> None:
    repo = _repo(tmp_path, ignore_git_context=True)
    stage_convergence_tree(
        repo,
        run_command,
        record_path="docs/merge-logs/context-convergence.jsonl",
        sweepable=True,
    )
    cached = _cached(repo)
    assert MANIFEST not in cached
    assert not any(path.startswith(f"{GIT_CONTEXT_PREFIX}/") for path in cached)
    assert "cleanup.txt" in cached


def test_stage_convergence_fails_closed_without_ignore_rule(tmp_path: Path) -> None:
    repo = _repo(tmp_path, ignore_git_context=False)
    with pytest.raises(ConvergenceApparatusError, match="not gitignored"):
        stage_convergence_tree(
            repo,
            run_command,
            record_path="docs/merge-logs/context-convergence.jsonl",
            sweepable=True,
        )
    assert MANIFEST not in _cached(repo)


def test_driver_source_does_not_issue_bare_git_add_all() -> None:
    source = (_SCRIPTS / "main_convergence.py").read_text()
    assert '["git", "add", "-A"]' not in source
    assert "stage_convergence_tree" in source
