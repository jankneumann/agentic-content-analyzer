"""PostgreSQL integration evidence for terminal-event retry and routing seams."""

from __future__ import annotations

import importlib
import json
from types import SimpleNamespace

import asyncpg
import pytest

from src.services.operation_service import OperationService
from src.services.workflow_terminal_event_service import WorkflowTerminalEventService

pytestmark = pytest.mark.integration

_BASE_ID = 9_940_000


async def _connect(test_engine) -> asyncpg.Connection:
    return await asyncpg.connect(test_engine.url.render_as_string(hide_password=False))


async def _insert_job(
    connection: asyncpg.Connection,
    *,
    operation_id: int,
    operation_type: str,
    status: str = "queued",
    parent_job_id: int | None = None,
) -> None:
    await connection.execute(
        """
        INSERT INTO pgqueuer_jobs (
            id, entrypoint, payload, status, parent_job_id,
            claim_generation, claim_protocol_version
        ) VALUES ($1, $2, $3::jsonb, $4, $5, 0, 2)
        """,
        operation_id,
        operation_type,
        json.dumps(
            {
                "schema_version": 2,
                "operation_type": operation_type,
                "input": {},
                "progress": 0,
                "message": "Queued",
                "cancel_requested": False,
                "resource": None,
                "result": None,
                "problem": None,
            }
        ),
        status,
        parent_job_id,
    )


def _noop_alert_settings() -> SimpleNamespace:
    return SimpleNamespace(
        workflow_alert_sink="noop",
        workflow_alert_diagnostic_origin=None,
    )


@pytest.mark.asyncio
async def test_retry_classifies_terminal_attempt_before_mutable_job_reset(
    test_engine,
    monkeypatch,
) -> None:
    connection = await _connect(test_engine)
    transaction = connection.transaction()
    await transaction.start()
    operation_id = _BASE_ID + 1
    try:
        await _insert_job(
            connection,
            operation_id=operation_id,
            operation_type="digest.create",
        )
        await connection.execute(
            "UPDATE pgqueuer_jobs SET status = 'failed', completed_at = NOW() WHERE id = $1",
            operation_id,
        )
        monkeypatch.setattr(
            importlib.import_module("src.config.settings"),
            "get_settings",
            _noop_alert_settings,
        )

        handle = await OperationService(connection=connection).retry(operation_id)

        assert str(handle.status) == "queued"
        event = await connection.fetchrow(
            """
            SELECT id, classification_status, envelope
            FROM workflow_terminal_events
            WHERE operation_id = $1 AND claim_generation = 0
            """,
            operation_id,
        )
        assert event is not None
        assert event["classification_status"] == "telemetry_only"
        assert event["envelope"] is None
        diagnostic = await WorkflowTerminalEventService(connection).get_diagnostic(event["id"])
        assert diagnostic is not None
        assert diagnostic.operation_id == str(operation_id)
        assert diagnostic.delivery_counts.model_dump() == {
            "pending": 0,
            "leased": 0,
            "delivered": 0,
            "permanent_failure": 0,
            "exhausted": 0,
        }
    finally:
        await transaction.rollback()
        await connection.close()


@pytest.mark.asyncio
async def test_child_retry_under_nonterminal_root_closes_old_attempt_without_alert(
    test_engine,
    monkeypatch,
) -> None:
    connection = await _connect(test_engine)
    transaction = connection.transaction()
    await transaction.start()
    root_id = _BASE_ID + 10
    child_id = _BASE_ID + 11
    try:
        await _insert_job(
            connection,
            operation_id=root_id,
            operation_type="pipeline.run",
            status="in_progress",
        )
        await _insert_job(
            connection,
            operation_id=child_id,
            operation_type="ingestion.execute",
            parent_job_id=root_id,
        )
        await connection.execute(
            "UPDATE pgqueuer_jobs SET status = 'failed', completed_at = NOW() WHERE id = $1",
            child_id,
        )
        monkeypatch.setattr(
            importlib.import_module("src.config.settings"),
            "get_settings",
            _noop_alert_settings,
        )

        await OperationService(connection=connection).retry(child_id)

        event = await connection.fetchrow(
            """
            SELECT classification_status, envelope
            FROM workflow_terminal_events
            WHERE operation_id = $1 AND claim_generation = 0
            """,
            child_id,
        )
        assert event is not None
        assert event["classification_status"] == "telemetry_only"
        assert event["envelope"] is None
        assert (
            await connection.fetchval(
                "SELECT COUNT(*) FROM workflow_alert_deliveries WHERE event_id IN "
                "(SELECT id FROM workflow_terminal_events WHERE operation_id = $1)",
                child_id,
            )
            == 0
        )
    finally:
        await transaction.rollback()
        await connection.close()
