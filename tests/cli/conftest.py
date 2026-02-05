"""Shared fixtures for CLI tests."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from src.cli.app import app
from src.cli.output import _set_json_mode


@pytest.fixture
def runner():
    """Create a Typer CliRunner for testing CLI commands."""
    return CliRunner()


@pytest.fixture
def cli_app():
    """Return the root Typer app for invocation."""
    return app


@pytest.fixture(autouse=True)
def reset_json_mode():
    """Reset JSON mode between tests to avoid leaking state."""
    _set_json_mode(False)
    yield
    _set_json_mode(False)
