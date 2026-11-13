"""Fake queue connection for unit tests that mock `enqueue_queue_job`.

`OperationService` enqueues and then persists the submission context in the same
transaction. A test that mocks only `enqueue_queue_job` would otherwise send that
UPDATE to whatever database `DATABASE_URL` names, where the mocked job id does not
exist. This connection accepts the UPDATE and serves a parent's stored context.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest


def stored_context(operation_id: int) -> dict[str, Any]:
    """A valid persisted submission context for a root operation."""
    trace_id = f"{operation_id:032x}"
    span_id = f"{operation_id:016x}"
    return {
        "schema_version": 1,
        "operation_id": str(operation_id),
        "root_operation_id": str(operation_id),
        "parent_operation_id": None,
        "traceparent": f"00-{trace_id}-{span_id}-01",
        "tracestate": None,
        "trace_id": trace_id,
        "span_id": span_id,
        "claim_generation": "0",
        "attempt_number": None,
        "entrypoint": "pipeline.run",
        "service_name": "aca-api",
        "service_instance_id": "api-1",
        "environment": "test",
        "release_revision": "test-revision",
        "authority_fingerprint": None,
        "ownership_epoch": None,
        "stage": "submit",
        "resource_kind": None,
        "resource_key": None,
    }


class FakeSubmissionConnection:
    """Records submission-context writes; parents always have a stored context."""

    def __init__(self) -> None:
        self.persisted: list[tuple[Any, ...]] = []

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[FakeSubmissionConnection]:
        yield self

    async def fetchval(self, query: str, *args: Any) -> Any:
        if "SELECT submission_context" in query:
            return stored_context(args[0])
        if "INSERT INTO pgqueuer_jobs" in query:
            # A CLI command in the same test reserves its own operational root.
            return 9_000 + len(self.persisted)
        if "RETURNING" in query:
            # Its attempt evidence insert returns the operation id it was given.
            return args[0] if args else 1
        return None

    async def execute(self, _query: str, *args: Any) -> str:
        self.persisted.append(args)
        return "UPDATE 1"


def install_fake_submission_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> FakeSubmissionConnection:
    from src.queue import setup as queue_setup

    connection = FakeSubmissionConnection()

    @asynccontextmanager
    async def fake_queue_connection(_conn: Any = None) -> AsyncIterator[FakeSubmissionConnection]:
        yield connection

    monkeypatch.setattr(queue_setup, "_queue_connection", fake_queue_connection)
    return connection
