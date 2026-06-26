"""Result-handler protocol + registry for batch reconciliation.

When the poll worker sees a ``SUCCEEDED`` job, it looks up the handler
registered for each request's ``model_step`` and asks it to apply the generated
text back to the target row. Each pipeline phase (content_filtering, youtube,
…) registers exactly one handler here; Phase 0 ships only the protocol and the
registry — the concrete handlers land with their phases.

Keeping the registry generic (keyed by :class:`ModelStep`) means the poll
worker stays step-agnostic: it never imports content/youtube logic directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from src.utils.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from src.config.models import ModelStep

logger = get_logger(__name__)


@runtime_checkable
class ResultHandler(Protocol):
    """Applies one reconciled batch result to its target row.

    Implementations must be idempotent: the poll worker may retry a job whose
    reconciliation was interrupted, so applying the same result twice must not
    corrupt the row or double-process it.
    """

    def apply(self, db: Session, target_id: str, result_text: str) -> None:
        """Write ``result_text`` back to the row identified by ``target_id``.

        Args:
            db: Active session (the poll worker's transaction).
            target_id: Stringified primary key of the target row.
            result_text: The model output reconciled for this request.
        """
        ...


class ResultHandlerRegistry:
    """Maps a :class:`ModelStep` to the :class:`ResultHandler` that reconciles it."""

    def __init__(self) -> None:
        self._handlers: dict[ModelStep, ResultHandler] = {}

    def register(self, step: ModelStep, handler: ResultHandler) -> None:
        """Register (or replace) the handler for ``step``.

        Last registration wins — tests and phase modules can override a handler
        without raising, which keeps registration order from being load-bearing.
        """
        if step in self._handlers:
            logger.debug("overriding batch result handler", extra={"model_step": step.value})
        self._handlers[step] = handler

    def get(self, step: ModelStep) -> ResultHandler | None:
        """Return the handler for ``step``, or ``None`` if none is registered."""
        return self._handlers.get(step)

    def __contains__(self, step: ModelStep) -> bool:
        return step in self._handlers

    def steps(self) -> list[ModelStep]:
        """All steps that currently have a handler (stable for assertions)."""
        return list(self._handlers)


#: Process-wide registry. Phase modules call ``result_handlers.register(...)``
#: at import time; the poll worker reads from it. Tests may use a fresh
#: ``ResultHandlerRegistry()`` to stay isolated.
result_handlers = ResultHandlerRegistry()
