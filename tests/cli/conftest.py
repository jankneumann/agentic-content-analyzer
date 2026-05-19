"""Shared fixtures for CLI tests."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from src.cli.app import app
from src.cli.output import _set_direct_mode, _set_json_mode


@pytest.fixture
def runner():
    """Create a Typer CliRunner for testing CLI commands."""
    return CliRunner()


@pytest.fixture
def cli_app():
    """Return the root Typer app for invocation."""
    return app


@pytest.fixture(autouse=True)
def reset_cli_modes():
    """Reset module-level CLI flags between tests.

    Both `_json_mode` and `_direct_mode` in `src/cli/output.py` are module
    globals flipped on by `--json` / `--direct` options and never reset.
    Without this fixture, test order can produce flakes where a later test
    silently runs in JSON or direct mode because an earlier test set them.
    """
    _set_json_mode(False)
    _set_direct_mode(False)
    yield
    _set_json_mode(False)
    _set_direct_mode(False)
