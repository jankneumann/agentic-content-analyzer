"""In-memory request/result types for Gemini batch execution.

These are the *runtime* payloads the router speaks — distinct from the ORM rows
in :mod:`src.models.batch`. A :class:`BatchRequest` here is what gets submitted
to ``client.aio.batches.create``; a persisted ``batch_requests`` row is what survives
a worker restart. The collector serializes one into the other.

``key`` is the join key: it is stamped into each Gemini ``InlinedRequest.metadata``
and echoed back on the matching ``InlinedResponse.metadata``, so reconciliation
is an order-independent dictionary lookup (the provider does not promise that
responses come back in request order).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class BatchState(StrEnum):
    """Normalized batch-job lifecycle state.

    Maps the provider's verbose ``JOB_STATE_*`` enum down to the handful of
    states the workers actually branch on. ``PENDING``/``RUNNING`` are
    non-terminal (keep polling); the rest are terminal.
    """

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


#: Terminal states — the poller stops watching a job once it reaches one of these.
TERMINAL_BATCH_STATES: frozenset[BatchState] = frozenset(
    {
        BatchState.SUCCEEDED,
        BatchState.FAILED,
        BatchState.EXPIRED,
        BatchState.CANCELLED,
    }
)


@dataclass
class BatchRequest:
    """A single request to include in a Gemini batch submission.

    Attributes:
        key: Stable, unique ``request_key`` echoed back via provider metadata.
        contents: The ``GenerateContent`` ``contents`` payload — a plain string
            for text steps, or a list of parts (e.g. a YouTube-URL ``fileData``
            part plus a text prompt) for the native-video path.
        config: JSON-serializable kwargs for ``types.GenerateContentConfig``
            (``system_instruction``, ``max_output_tokens``, ``temperature``,
            ``media_resolution`` …). Kept as a dict so the request round-trips
            through the ``batch_requests.request_payload`` JSON column unchanged.
    """

    key: str
    contents: Any
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchPollResult:
    """Outcome of polling one batch job.

    ``state`` is always present. ``results_by_key`` is populated only when the
    job reached a success state — mapping ``request_key`` → generated text for
    every response that came back cleanly. Per-request failures land in
    ``errors_by_key`` (so the worker can route just those to synchronous
    fallback); a job-level failure message lands in ``error``.
    """

    state: BatchState
    results_by_key: dict[str, str] | None = None
    errors_by_key: dict[str, str] | None = None
    unmatched_errors: tuple[str, ...] = ()
    error: str | None = None

    @property
    def is_terminal(self) -> bool:
        """True once the job has reached a state the poller need not revisit."""
        return self.state in TERMINAL_BATCH_STATES
