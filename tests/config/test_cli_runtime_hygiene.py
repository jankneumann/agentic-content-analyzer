"""Regression tests for warning-free default CLI configuration."""

from __future__ import annotations

import tomllib
from pathlib import Path

import yaml
from packaging.requirements import Requirement
from packaging.version import Version

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_crawl4ai_extra_constrains_chardet_to_requests_compatible_range() -> None:
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    dependencies = project["project"]["optional-dependencies"]["crawl4ai"]
    chardet = next(Requirement(value) for value in dependencies if value.startswith("chardet"))

    assert Version("5.2") in chardet.specifier
    assert Version("6") not in chardet.specifier

    lock = tomllib.loads((REPO_ROOT / "uv.lock").read_text())
    locked = next(package for package in lock["package"] if package["name"] == "chardet")
    assert Version(locked["version"]) in chardet.specifier


def test_mcp_is_capped_below_the_mcperror_rename() -> None:
    """mcp 2.0 renamed McpError -> MCPError, breaking src/mcp_tools/runtime.py.

    CI installs with `uv pip install` (not --frozen), so it resolves the
    newest allowed version. Without an upper bound, the 2.0 release turned
    every mcp import into an ImportError and took `main` red across
    contract-test, test (cli-stack), and typecheck simultaneously.
    """
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    dependencies = project["project"]["dependencies"]
    mcp = next(r for r in (Requirement(value) for value in dependencies) if r.name == "mcp")

    assert Version("1.26") in mcp.specifier, "the known-good 1.x line must stay installable"
    assert Version("2.0") not in mcp.specifier, (
        "mcp 2.0 renamed McpError -> MCPError; migrate src/mcp_tools/runtime.py "
        "and the two test modules before lifting this cap"
    )

    lock = tomllib.loads((REPO_ROOT / "uv.lock").read_text())
    locked = next(package for package in lock["package"] if package["name"] == "mcp")
    assert Version(locked["version"]) in mcp.specifier


def test_typer_cap_tracks_docling() -> None:
    """typer's ceiling is docling's ceiling. Move both together.

    docling-slim[standard] (docling >= 2.123) declares typer<0.27.0. Our own
    code no longer constrains typer at all: src/cli/app.py imports whichever
    click flavour the installed typer was built against, and mypy is clean under
    both typer 0.19.2 and 0.27.1. So this test pins our cap to docling's, and the
    day docling lifts theirs is the day this assertion should move.

    History: this cap sat at <0.20 because docling <2.123 required typer<0.20.0
    and because app.py's get_command override named click's types. Both are
    resolved; the surviving constraint is docling-slim's <0.27.
    """
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    dependencies = project["project"]["dependencies"]
    typer = next(r for r in (Requirement(value) for value in dependencies) if r.name == "typer")

    assert Version("0.19.2") in typer.specifier, "the known-good line must stay installable"
    assert Version("0.20") in typer.specifier, (
        "typer 0.20+ is now allowed: the app.py typing blocker and the docling<2.123 "
        "cap are both resolved -- do not reintroduce <0.20"
    )
    assert Version("0.27") not in typer.specifier, (
        "docling-slim[standard] declares typer<0.27.0, so typer 0.27+ is unsatisfiable. "
        "Lift this together with docling's cap, not before."
    )

    lock = tomllib.loads((REPO_ROOT / "uv.lock").read_text())
    locked = next(package for package in lock["package"] if package["name"] == "typer")
    assert Version(locked["version"]) in typer.specifier
    assert Version(locked["version"]) >= Version("0.20"), "the lock should actually use the lifted cap"

def test_local_profile_uses_only_canonical_neo4j_keys() -> None:
    profile = yaml.safe_load((REPO_ROOT / "profiles/local.yaml").read_text())
    neo4j = profile["settings"]["neo4j"]

    assert neo4j["neo4j_uri"] == "bolt://localhost:7687"
    assert neo4j["neo4j_user"] == "neo4j"
    assert "neo4j_password" in neo4j
    assert not any(key.startswith("neo4j_local_") for key in neo4j)
