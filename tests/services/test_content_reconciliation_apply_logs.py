"""Per-item apply_failed logs must not carry payloads or exception text."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from src.services.content_reconciliation_service import ContentReconciliationService

HOSTILE = "password=supersecret payload={'token': 'sk-live'} deadlock at /var/lib/postgresql"


def _row() -> dict[str, object]:
    return {
        "content_id": 41,
        "content_status": "processing",
        "owner_operation_id": 901,
        "owner_claim_generation": 3,
        "owner_phase": "processing",
        "owner_version": 5,
        "operation_id": 901,
        "operation_status": "failed",
        "operation_claim_generation": 3,
        "operation_claim_protocol_version": 2,
        "operation_retry_count": 1,
        "operation_cancel_requested": False,
        "operation_force": False,
        "operation_is_stale": True,
        "matching_summary": False,
        "mismatched_summary": False,
        "extraction_succeeded": False,
        "operation_heartbeat_at": None,
        "operation_completed_at": None,
    }


class _FakeConnection:
    def transaction(self):
        @asynccontextmanager
        async def _tx():
            yield

        return _tx()

    async def execute(self, *_args, **_kwargs):
        return None


@pytest.mark.asyncio
async def test_apply_failed_logs_classification_without_payload(caplog):
    service = ContentReconciliationService(
        connection=_FakeConnection(),  # type: ignore[arg-type]
        stale_seconds=30,
        max_retries=3,
        batch_size=10,
        lock_timeout_ms=50,
        statement_timeout_ms=100,
        apply_enabled=True,
    )
    service._apply_one = AsyncMock(side_effect=RuntimeError(HOSTILE))  # type: ignore[method-assign]
    run_id = UUID("16fd2706-8baf-433b-82eb-8c7fada847da")

    with caplog.at_level(logging.WARNING, logger="src.services.content_reconciliation_service"):
        items = await service._apply_page([_row()], run_id=run_id)  # type: ignore[arg-type]

    assert len(items) == 1
    assert items[0].reason == "apply_failed"
    blob = caplog.text
    assert HOSTILE not in blob
    assert "supersecret" not in blob
    assert "sk-live" not in blob
    assert "/var/lib/postgresql" not in blob
    assert "password=" not in blob
    matching = [
        record
        for record in caplog.records
        if record.getMessage() == "content reconciliation apply_failed"
    ]
    assert matching
    assert matching[0].content_id == 41
    assert matching[0].error_type == "RuntimeError"
    assert matching[0].reconciliation_run_id == str(run_id)
