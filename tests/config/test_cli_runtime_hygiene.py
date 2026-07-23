"""Regression tests for warning-free default CLI configuration."""

from __future__ import annotations

import tomllib
from pathlib import Path

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
