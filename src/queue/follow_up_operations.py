"""Submit follow-up durable operations from ingestion code on a worker thread.

The canonical ingestion handler runs a source's synchronous orchestrator
function with :func:`asyncio.to_thread`, while :class:`OperationService` is
async. Instead of starting a private event loop in that thread (and a queue
connection bound to it), the handler binds the worker's own loop and
``OperationService`` here for the duration of the call. ``to_thread`` copies
context variables into the thread, so the ingestion code finds the binding and
hands each submission back to the worker loop with
:func:`asyncio.run_coroutine_threadsafe`, waiting until the durable row exists.

Outside a canonical ingestion handler nothing is bound, and a submission fails
with :class:`FollowUpUnavailableError` instead of executing work inline.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Final

from pydantic import BaseModel

from src.models.jobs import OperationHandle, OperationType

__all__ = [
    "DEFAULT_SUBMIT_TIMEOUT_S",
    "FollowUpOperations",
    "FollowUpSubmissionError",
    "FollowUpUnavailableError",
    "bind_follow_up_operations",
    "current_follow_up_operations",
    "submit_follow_up_ingestion",
]

DEFAULT_SUBMIT_TIMEOUT_S: Final = 30.0


class FollowUpSubmissionError(RuntimeError):
    """A follow-up operation could not be submitted. Carries no input value."""


class FollowUpUnavailableError(FollowUpSubmissionError):
    """No canonical ingestion handler bound a worker loop for follow-up work."""


@dataclass(frozen=True)
class FollowUpOperations:
    """The worker loop and ``OperationService`` an ingestion handler lends its thread."""

    loop: asyncio.AbstractEventLoop
    operations: Any
    timeout_s: float = DEFAULT_SUBMIT_TIMEOUT_S

    def submit(
        self,
        operation_type: OperationType,
        normalized_input: dict[str, Any],
        *,
        idempotency_key: str,
    ) -> OperationHandle:
        """Submit on the worker loop and block this thread until it is durable."""
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is self.loop:
            # Blocking the loop on its own future would never return.
            raise FollowUpSubmissionError("follow-up submission must run off the worker loop")
        if self.loop.is_closed():
            raise FollowUpSubmissionError("the worker loop is closed")
        future = asyncio.run_coroutine_threadsafe(
            self.operations.submit(
                operation_type,
                normalized_input,
                idempotency_key=idempotency_key,
            ),
            self.loop,
        )
        try:
            handle: OperationHandle = future.result(timeout=self.timeout_s)
        except concurrent.futures.TimeoutError as exc:
            future.cancel()
            raise FollowUpSubmissionError("follow-up submission timed out") from exc
        return handle


_CURRENT_FOLLOW_UP: ContextVar[FollowUpOperations | None] = ContextVar(
    "current_follow_up_operations",
    default=None,
)


def current_follow_up_operations() -> FollowUpOperations | None:
    """The binding of the ingestion handler running this code, if any."""
    return _CURRENT_FOLLOW_UP.get()


@contextmanager
def bind_follow_up_operations(
    operations: Any,
    *,
    timeout_s: float = DEFAULT_SUBMIT_TIMEOUT_S,
) -> Iterator[FollowUpOperations]:
    """Lend the running loop and ``operations`` to code this task runs in a thread.

    Must be entered on the worker's event loop, around the ``asyncio.to_thread``
    call that runs the ingestion.
    """
    binding = FollowUpOperations(
        loop=asyncio.get_running_loop(),
        operations=operations,
        timeout_s=timeout_s,
    )
    token = _CURRENT_FOLLOW_UP.set(binding)
    try:
        yield binding
    finally:
        _CURRENT_FOLLOW_UP.reset(token)


def submit_follow_up_ingestion(command: BaseModel, *, idempotency_key: str) -> OperationHandle:
    """Submit one canonical ``ingestion.execute`` operation for ``command``.

    The payload is the command's public JSON shape, as the HTTP submission route
    stores it. Raises :class:`FollowUpUnavailableError` outside a worker handler.
    """
    binding = current_follow_up_operations()
    if binding is None:
        raise FollowUpUnavailableError("follow-up operations need the durable ingestion worker")
    return binding.submit(
        OperationType.INGESTION_EXECUTE,
        command.model_dump(mode="json", exclude_none=True),
        idempotency_key=idempotency_key,
    )
