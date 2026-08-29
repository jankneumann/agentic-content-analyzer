"""Shared fixtures for CLI tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from typer.testing import CliRunner

from src.cli.app import app
from src.cli.output import _set_direct_mode, _set_json_mode
from src.contracts.operation_context import OperationContext, bind_operation_context


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


@pytest.fixture(autouse=True)
def bind_cli_unit_operation() -> Iterator[None]:
    """Isolate legacy CLI unit tests from the production durable store."""
    context = OperationContext(
        schema_version=1,
        operation_id="9002",
        root_operation_id="9002",
        parent_operation_id=None,
        traceparent="00-11111111111111111111111111111111-2222222222222222-01",
        tracestate=None,
        trace_id="11111111111111111111111111111111",
        span_id="2222222222222222",
        claim_generation="0",
        attempt_number="1",
        entrypoint="test.cli",
        service_name="aca-test",
        service_instance_id="test-1",
        environment="test",
        release_revision="test",
        stage="submit",
        resource_kind=None,
        resource_key=None,
    )
    with bind_operation_context(context):
        yield
