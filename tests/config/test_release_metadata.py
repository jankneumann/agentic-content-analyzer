"""Configuration and build tests for served frontend release metadata."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = REPO_ROOT / "web"
SHA = "c" * 40


def test_vite_config_owns_revision_provenance_and_complete_asset_manifest() -> None:
    config = (WEB_ROOT / "vite.config.ts").read_text(encoding="utf-8")

    assert "RAILWAY_GIT_COMMIT_SHA" in config
    assert "GITHUB_SHA" in config
    assert "release-build.json" in config
    assert "verified_detached_sha" in config
    assert "release-revision" in config
    assert "release-revision-source" in config
    assert "release-assets.json" in config
    assert "createHash" in config


def test_production_build_embeds_revision_and_manifest() -> None:
    npm = shutil.which("npm")
    assert npm is not None
    env = os.environ.copy()
    env.pop("RAILWAY_GIT_COMMIT_SHA", None)
    env["GITHUB_SHA"] = SHA
    subprocess.run(
        [npm, "run", "build"],
        cwd=WEB_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    html = (WEB_ROOT / "dist" / "index.html").read_text(encoding="utf-8")
    manifest = json.loads((WEB_ROOT / "dist" / "release-assets.json").read_text(encoding="utf-8"))

    assert f'content="{SHA}"' in html
    assert 'name="release-revision-source" content="github_sha"' in html
    assert manifest["revision"] == SHA
    assert manifest["revision_source"] == "github_sha"
    assert manifest["javascript"]
    assert all(
        set(asset) == {"path", "size_bytes", "sha256"}
        and asset["path"].endswith(".js")
        and len(asset["sha256"]) == 64
        for asset in manifest["javascript"]
    )
