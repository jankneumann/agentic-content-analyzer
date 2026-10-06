"""Follow-up operations lent by the ingestion handler to its worker thread (ri-13)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from src.contracts.workflow_models import UrlIngestCommand
from src.models.jobs import OperationType
from src.queue.follow_up_operations import (
    FollowUpSubmissionError,
    FollowUpUnavailableError,
    bind_follow_up_operations,
    current_follow_up_operations,
    submit_follow_up_ingestion,
)

COMMAND = UrlIngestCommand(url="https://example.com/a", tags=["x-bookmark"])


class Operations:
    def __init__(self, *, delay_s: float = 0.0) -> None:
        self.calls: list[tuple[OperationType, dict[str, Any], str | None]] = []
        self.delay_s = delay_s

    async def submit(
        self,
        operation_type: OperationType,
        normalized_input: dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> SimpleNamespace:
        await asyncio.sleep(self.delay_s)
        self.calls.append((operation_type, normalized_input, idempotency_key))
        return SimpleNamespace(operation_id="77")


def test_nothing_is_bound_outside_a_handler() -> None:
    assert current_follow_up_operations() is None
    with pytest.raises(FollowUpUnavailableError):
        submit_follow_up_ingestion(COMMAND, idempotency_key="k" * 8)


@pytest.mark.asyncio
async def test_a_worker_thread_submits_on_the_bound_loop() -> None:
    operations = Operations()

    with bind_follow_up_operations(operations):
        handle = await asyncio.to_thread(
            submit_follow_up_ingestion, COMMAND, idempotency_key="key-123456"
        )

    assert handle.operation_id == "77"
    assert operations.calls == [
        (
            OperationType.INGESTION_EXECUTE,
            {
                "kind": "url",
                "url": "https://example.com/a",
                "tags": ["x-bookmark"],
                "routing_mode": "auto",
                "force_reprocess": False,
            },
            "key-123456",
        )
    ]
    assert current_follow_up_operations() is None


@pytest.mark.asyncio
async def test_submitting_on_the_loop_itself_is_refused_instead_of_deadlocking() -> None:
    with (
        bind_follow_up_operations(Operations()),
        pytest.raises(FollowUpSubmissionError, match="off the worker loop"),
    ):
        submit_follow_up_ingestion(COMMAND, idempotency_key="key-123456")


@pytest.mark.asyncio
async def test_a_slow_submission_times_out() -> None:
    with (
        bind_follow_up_operations(Operations(delay_s=5.0), timeout_s=0.05),
        pytest.raises(FollowUpSubmissionError, match="timed out"),
    ):
        await asyncio.to_thread(submit_follow_up_ingestion, COMMAND, idempotency_key="key-1")
