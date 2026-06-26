"""Gemini batch-execution service layer (Phase 0 core infrastructure).

This package holds the deferred-completion batch pipeline: in-memory request
types (:mod:`src.services.batch.types`), the collector that persists pending
requests, and the per-step result handlers that reconcile completed batches.

Everything here is inert until ``batch.enabled`` is flipped on in
``settings/models.yaml`` — see :meth:`src.config.models.ModelConfig.is_batch_enabled`.
"""

from src.services.batch.types import (
    TERMINAL_BATCH_STATES,
    BatchPollResult,
    BatchRequest,
    BatchState,
)

__all__ = [
    "BatchRequest",
    "BatchPollResult",
    "BatchState",
    "TERMINAL_BATCH_STATES",
]
