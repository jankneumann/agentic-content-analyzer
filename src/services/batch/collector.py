"""BatchCollector — persists deferred LLM requests as ``pending`` rows.

The collector is the single write-side seam between a pipeline step and the
batch pipeline. When ``is_batch_enabled(step)`` is true, a step calls
:meth:`BatchCollector.enqueue` instead of invoking the LLM inline; the request
is serialized into a ``batch_requests`` row and picked up later by the submit
worker. When batching is off, no step touches this class at all.

An active-target unique index and lookup make re-enqueueing the same
``(step, content_id)`` idempotent. Each new execution attempt gets a fresh
``request_key`` for provider correlation.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from src.models.batch import BatchRequest as BatchRequestRow, BatchRequestStatus
from src.services.batch.types import BatchRequest
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from src.config.models import ModelConfig, ModelStep

logger = get_logger(__name__)


class BatchCollector:
    """Serializes step requests into ``pending`` ``batch_requests`` rows."""

    def __init__(self, model_config: ModelConfig) -> None:
        """Args:
        model_config: Resolves the model id for a step so requests are
            grouped by the same ``(step, model)`` the submit worker flushes on.
        """
        self.model_config = model_config

    @staticmethod
    def build_request_key(step: ModelStep, content_id: int) -> str:
        """Return a provider correlation key unique to this execution attempt."""
        return f"{step.value}:{content_id}:{uuid.uuid4().hex}"

    @staticmethod
    def _contains_credentials(value: Any) -> bool:
        """Reject explicit credential fields before a payload reaches JSON storage."""
        credential_keys = {"api_key", "apikey", "authorization", "credential", "secret", "token"}
        if isinstance(value, dict):
            return any(
                (
                    (normalized := str(key).lower().replace("-", "_")) in credential_keys
                    or normalized.endswith(
                        ("_api_key", "_credential", "_credentials", "_secret", "_token")
                    )
                )
                or BatchCollector._contains_credentials(item)
                for key, item in value.items()
            )
        if isinstance(value, (list, tuple)):
            return any(BatchCollector._contains_credentials(item) for item in value)
        return False

    def enqueue(
        self,
        db: Session,
        step: ModelStep,
        content_id: int,
        request: BatchRequest,
    ) -> BatchRequestRow | None:
        """Persist (or reuse) a ``pending`` batch request for one target row.

        The caller supplies the session so the enqueue shares the surrounding
        ingestion/processing transaction. Idempotent: if a row already exists
        for the derived ``request_key`` it is returned unchanged rather than
        duplicated.

        Args:
            db: Active SQLAlchemy session (caller-owned transaction).
            step: Pipeline step — also selects the model id.
            content_id: Integer primary key of the Content row to reconcile.
            request: In-memory request payload (contents + config); its ``key``
                field is advisory — the collector assigns the canonical key.

        Returns:
            The persisted (or pre-existing) ``batch_requests`` ORM row, flushed
            so it is visible to subsequent queries in the same transaction.
        """
        if not self.model_config.is_batch_enabled(step):
            logger.debug("batch enqueue skipped", extra={"model_step": step.value})
            return None
        if isinstance(content_id, bool) or not isinstance(content_id, int):
            raise TypeError("content_id must be an integer")
        if self._contains_credentials(request.config):
            raise ValueError("batch request config must not contain credentials")

        active_statuses = tuple(
            status.value
            for status in (
                BatchRequestStatus.PENDING,
                BatchRequestStatus.CLAIMED,
                BatchRequestStatus.SUBMITTED,
                BatchRequestStatus.FALLBACK,
            )
        )
        existing = (
            db.query(BatchRequestRow)
            .filter(
                BatchRequestRow.model_step == step.value,
                BatchRequestRow.content_id == content_id,
                BatchRequestRow.status.in_(active_statuses),
            )
            .first()
        )
        if existing is not None:
            logger.debug(
                "batch enqueue idempotent hit",
                extra={"request_key": existing.request_key, "status": existing.status},
            )
            return existing

        model_id = self.model_config.get_model_for_step(step)
        request_key = self.build_request_key(step, content_id)
        row = BatchRequestRow(
            request_key=request_key,
            model_step=step.value,
            model_id=model_id,
            content_id=content_id,
            request_payload={"contents": request.contents, "config": request.config},
            status=BatchRequestStatus.PENDING.value,
        )
        db.add(row)
        # Flush so a subsequent enqueue/select in the same txn sees this row
        # (autoflush=False + dedup-loop gotcha — see CLAUDE.md).
        db.flush()
        logger.info(
            "enqueued batch request",
            extra={"request_key": request_key, "model_step": step.value, "model_id": model_id},
        )
        return row
