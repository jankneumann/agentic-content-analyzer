"""BatchCollector — persists deferred LLM requests as ``pending`` rows.

The collector is the single write-side seam between a pipeline step and the
batch pipeline. When ``is_batch_enabled(step)`` is true, a step calls
:meth:`BatchCollector.enqueue` instead of invoking the LLM inline; the request
is serialized into a ``batch_requests`` row and picked up later by the submit
worker. When batching is off, no step touches this class at all.

``request_key`` is derived deterministically from ``(step, target_table,
target_id)`` so re-enqueueing the same target is idempotent — a re-run after a
crash won't create duplicate batch rows or double-charge.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.models.batch import BatchRequest as BatchRequestRow
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
    def build_request_key(step: ModelStep, target_table: str, target_id: object) -> str:
        """Deterministic, idempotent key for a (step, row) pair.

        Echoed into the Gemini request metadata and stored UNIQUE on the row,
        so the same target enqueued twice collapses to one batch request.
        """
        return f"{step.value}:{target_table}:{target_id}"

    def enqueue(
        self,
        db: Session,
        step: ModelStep,
        target_table: str,
        target_id: object,
        request: BatchRequest,
    ) -> BatchRequestRow:
        """Persist (or reuse) a ``pending`` batch request for one target row.

        The caller supplies the session so the enqueue shares the surrounding
        ingestion/processing transaction. Idempotent: if a row already exists
        for the derived ``request_key`` it is returned unchanged rather than
        duplicated.

        Args:
            db: Active SQLAlchemy session (caller-owned transaction).
            step: Pipeline step — also selects the model id.
            target_table: Table the reconciled result writes back to (e.g. ``"contents"``).
            target_id: Primary key of the target row (stringified for storage).
            request: In-memory request payload (contents + config); its ``key``
                field is advisory — the collector assigns the canonical key.

        Returns:
            The persisted (or pre-existing) ``batch_requests`` ORM row, flushed
            so it is visible to subsequent queries in the same transaction.
        """
        target_id_str = str(target_id)
        request_key = self.build_request_key(step, target_table, target_id_str)

        existing = (
            db.query(BatchRequestRow).filter(BatchRequestRow.request_key == request_key).first()
        )
        if existing is not None:
            logger.debug(
                "batch enqueue idempotent hit",
                extra={"request_key": request_key, "status": existing.status},
            )
            return existing

        model_id = self.model_config.get_model_for_step(step)
        row = BatchRequestRow(
            request_key=request_key,
            model_step=step.value,
            model_id=model_id,
            target_table=target_table,
            target_id=target_id_str,
            request_payload={"contents": request.contents, "config": request.config},
            status="pending",
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
