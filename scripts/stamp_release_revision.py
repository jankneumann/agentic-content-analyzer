#!/usr/bin/env python3
"""Create the bounded revision stamp consumed by the isolated frontend build."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from src.clients.operational_observability import bootstrap_entrypoint

_COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")
_STAMP_RELATIVE_PATH = Path("web/release-build.json")


class StampError(ValueError):
    """The detached checkout cannot produce a trusted release stamp."""


@dataclass(frozen=True)
class StampResult:
    path: Path
    revision: str
    sha256: str


def _git(repo_root: Path, *args: str) -> str:
    git = shutil.which("git")
    if git is None:
        raise StampError("git is required to verify a release checkout")
    result = subprocess.run(
        [git, *args],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise StampError("Unable to verify detached release checkout")
    return result.stdout.strip()


def write_release_stamp(repo_root: Path, revision: str) -> StampResult:
    """Bind a canonical frontend build stamp to the clean checkout HEAD."""
    root = repo_root.resolve(strict=True)
    if not _COMMIT_SHA.fullmatch(revision):
        raise StampError("Revision must be a lowercase 40-character commit SHA")

    head = _git(root, "rev-parse", "HEAD")
    if revision != head:
        raise StampError("Requested revision does not match HEAD")
    if _git(root, "branch", "--show-current"):
        raise StampError("Release checkout HEAD must be detached")

    web_root = (root / "web").resolve(strict=True)
    target = web_root / _STAMP_RELATIVE_PATH.name
    if target.exists() or target.is_symlink():
        raise StampError("Release stamp already exists")
    if _git(root, "status", "--porcelain"):
        raise StampError("Release checkout has tracked or untracked changes")

    payload = {
        "schema_version": 1,
        "revision": revision,
        "revision_source": "verified_detached_sha",
    }
    encoded = (json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n").encode()

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=web_root, delete=False) as temporary:
            temporary.write(encoded)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        temporary_path.chmod(0o644)
        temporary_path.replace(target)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()

    return StampResult(
        path=target,
        revision=revision,
        sha256=hashlib.sha256(encoded).hexdigest(),
    )


@bootstrap_entrypoint("bootstrap.stamp_release_revision")
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("revision", help="Expected clean detached HEAD SHA")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root (defaults to current directory)",
    )
    args = parser.parse_args()
    try:
        result = write_release_stamp(args.repo_root, args.revision)
    except StampError as exc:
        parser.error(str(exc))
    print(f"{result.path}: revision={result.revision} sha256={result.sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
