"""Tests for the detached-HEAD frontend release identity stamp."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.stamp_release_revision import StampError, write_release_stamp


def _git(repo: Path, *args: str) -> str:
    git = shutil.which("git")
    assert git is not None
    result = subprocess.run(
        [git, *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


@pytest.fixture
def committed_repo(tmp_path: Path) -> tuple[Path, str]:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "release-smoke@example.invalid")
    _git(tmp_path, "config", "user.name", "Release Smoke Test")
    (tmp_path / "web").mkdir()
    (tmp_path / "tracked.txt").write_text("tracked\n", encoding="utf-8")
    _git(tmp_path, "add", "tracked.txt")
    _git(tmp_path, "commit", "-qm", "fixture")
    revision = _git(tmp_path, "rev-parse", "HEAD")
    _git(tmp_path, "switch", "--detach", revision)
    return tmp_path, revision


def test_stamp_binds_canonical_payload_to_clean_head(
    committed_repo: tuple[Path, str],
) -> None:
    repo, revision = committed_repo

    result = write_release_stamp(repo, revision)

    stamp_path = repo / "web" / "release-build.json"
    assert json.loads(stamp_path.read_text(encoding="utf-8")) == {
        "schema_version": 1,
        "revision": revision,
        "revision_source": "verified_detached_sha",
    }
    assert result.revision == revision
    assert result.sha256


def test_stamp_rejects_revision_that_is_not_head(
    committed_repo: tuple[Path, str],
) -> None:
    repo, _ = committed_repo

    with pytest.raises(StampError, match="does not match HEAD"):
        write_release_stamp(repo, "b" * 40)


def test_stamp_rejects_dirty_tracked_checkout(
    committed_repo: tuple[Path, str],
) -> None:
    repo, revision = committed_repo
    (repo / "tracked.txt").write_text("changed\n", encoding="utf-8")

    with pytest.raises(StampError, match="tracked or untracked"):
        write_release_stamp(repo, revision)


def test_stamp_rejects_attached_branch(
    committed_repo: tuple[Path, str],
) -> None:
    repo, revision = committed_repo
    _git(repo, "switch", "-c", "release-candidate")

    with pytest.raises(StampError, match="detached"):
        write_release_stamp(repo, revision)


def test_stamp_rejects_untracked_build_input(
    committed_repo: tuple[Path, str],
) -> None:
    repo, revision = committed_repo
    (repo / "web" / "injected.ts").write_text("export const injected = true\n")

    with pytest.raises(StampError, match="tracked or untracked"):
        write_release_stamp(repo, revision)


def test_stamp_rejects_existing_or_symlink_output(
    committed_repo: tuple[Path, str],
) -> None:
    repo, revision = committed_repo
    target = repo / "web" / "release-build.json"
    target.symlink_to(repo / "tracked.txt")

    with pytest.raises(StampError, match="already exists"):
        write_release_stamp(repo, revision)


@pytest.mark.parametrize("revision", ["short", "A" * 40, "../" + "a" * 40])
def test_stamp_requires_lowercase_full_sha(
    committed_repo: tuple[Path, str],
    revision: str,
) -> None:
    repo, _ = committed_repo

    with pytest.raises(StampError, match="40-character"):
        write_release_stamp(repo, revision)
