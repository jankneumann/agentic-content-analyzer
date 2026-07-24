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


def test_local_profile_uses_only_canonical_neo4j_keys() -> None:
    profile = yaml.safe_load((REPO_ROOT / "profiles/local.yaml").read_text())
    neo4j = profile["settings"]["neo4j"]

    assert neo4j["neo4j_uri"] == "bolt://localhost:7687"
    assert neo4j["neo4j_user"] == "neo4j"
    assert "neo4j_password" in neo4j
    assert not any(key.startswith("neo4j_local_") for key in neo4j)
