"""PostgreSQL integration evidence for terminal-event retry and routing seams."""

from __future__ import annotations

import importlib
import json
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import asyncpg
import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import sessionmaker

from src.contracts.workflow_alert_models import WorkflowAlertEnvelopeV1
from src.models.workflow_alert import WorkflowAlertDelivery, WorkflowTerminalEvent
from src.services.alert_sinks import SinkDeliveryResult
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


def _webhook_alert_settings(*, batch_size: int = 2) -> SimpleNamespace:
    return SimpleNamespace(
        workflow_alert_sink="webhook",
        workflow_alert_diagnostic_origin="https://ops.example.com",
        workflow_alert_webhook_endpoint="https://alerts.example.com/hook",
        workflow_alert_webhook_secret=None,
        workflow_alert_timeout_seconds=1,
        workflow_alert_lease_seconds=10,
        workflow_alert_max_attempts=5,
        workflow_alert_base_backoff_seconds=30,
        workflow_alert_max_backoff_seconds=3600,
        workflow_alert_max_retry_after_seconds=3600,
        workflow_alert_delivery_max_age_seconds=604800,
        workflow_alert_retention_days=30,
        workflow_alert_exhausted_retention_days=90,
        workflow_alert_batch_size=batch_size,
        get_workflow_alert_allowed_hosts=lambda: ("alerts.example.com",),
        is_development=False,
    )


def _ready_event(*, operation_id: int, event_id: UUID, now: datetime) -> WorkflowTerminalEvent:
    envelope = WorkflowAlertEnvelopeV1(
        event_id=event_id,
        event_key=f"operation:{operation_id}:claim:0:status:failed",
        occurred_at=now,
        severity="error",
        outcome="failed",
        source_kind="operation",
        workflow_type="ingestion.execute",
        release_revision="development",
        release_revision_source="local_development",
        operation_id=str(operation_id),
        attempt=1,
        diagnostic_url=f"https://ops.example.com/api/v1/operations/{operation_id}",
        resource_refs=[],
        source_keys=[],
        counts={"items_failed": 1},
        codes=["operation_failed"],
    )
    return WorkflowTerminalEvent(
        id=event_id,
        event_key=envelope.event_key,
        source_kind="operation",
        operation_id=operation_id,
        claim_generation=0,
        terminal_status="failed",
        classification_status="ready",
        envelope=envelope.model_dump(mode="json"),
        occurred_at=now,
        created_at=now,
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


@pytest.mark.asyncio
async def test_aged_ready_backlog_larger_than_batch_all_gets_durable_delivery(
    test_engine,
    monkeypatch,
) -> None:
    from src.queue import worker

    factory = sessionmaker(bind=test_engine, expire_on_commit=False)
    old = datetime.now(UTC) - timedelta(days=45)
    event_ids = [uuid4() for _ in range(5)]
    with factory() as db:
        db.add_all(
            [
                _ready_event(
                    operation_id=_BASE_ID + 100 + index,
                    event_id=event_id,
                    now=old,
                )
                for index, event_id in enumerate(event_ids)
            ]
        )
        db.commit()

    @contextmanager
    def get_db():
        with factory() as db:
            yield db

    sink = SimpleNamespace()

    async def deliver(*_args, **_kwargs):
        return SinkDeliveryResult(disposition="success")

    sink.deliver = deliver
    monkeypatch.setattr("src.storage.database.get_db", get_db)
    monkeypatch.setattr(worker, "_build_workflow_alert_sink", lambda _settings: sink)
    connection = await _connect(test_engine)
    try:
        for _ in range(3):
            assert await worker._run_workflow_alert_maintenance_tick(
                connection,
                alert_settings=_webhook_alert_settings(batch_size=2),
            )

        with factory() as db:
            delivered_event_ids = set(
                db.scalars(
                    select(WorkflowAlertDelivery.event_id).where(
                        WorkflowAlertDelivery.event_id.in_(event_ids)
                    )
                )
            )
            assert delivered_event_ids == set(event_ids)
            assert set(
                db.scalars(
                    select(WorkflowAlertDelivery.status).where(
                        WorkflowAlertDelivery.event_id.in_(event_ids)
                    )
                )
            ) == {"delivered"}
    finally:
        await connection.close()
        with factory() as db:
            db.execute(
                delete(WorkflowAlertDelivery).where(WorkflowAlertDelivery.event_id.in_(event_ids))
            )
            db.execute(delete(WorkflowTerminalEvent).where(WorkflowTerminalEvent.id.in_(event_ids)))
            db.commit()


@pytest.mark.asyncio
async def test_retained_delivery_and_ready_parent_age_out_without_redelivery(
    test_engine,
    monkeypatch,
) -> None:
    from src.queue import worker

    factory = sessionmaker(bind=test_engine, expire_on_commit=False)
    old = datetime.now(UTC) - timedelta(days=45)
    event_id = uuid4()
    delivery_id = uuid4()
    with factory() as db:
        db.add(_ready_event(operation_id=_BASE_ID + 200, event_id=event_id, now=old))
        db.flush()
        db.add(
            WorkflowAlertDelivery(
                id=delivery_id,
                event_id=event_id,
                sink_name="webhook",
                status="delivered",
                attempt_count=1,
                next_attempt_at=old,
                delivered_at=old,
                created_at=old,
                updated_at=old,
            )
        )
        db.commit()
        assert (
            worker._cleanup_terminal_workflow_alert_records(
                db,
                now=datetime.now(UTC),
                retention_days=30,
                exhausted_retention_days=90,
                batch_size=2,
            )
            == 1
        )
        assert db.get(WorkflowAlertDelivery, delivery_id) is None
        assert db.get(WorkflowTerminalEvent, event_id) is None

    @contextmanager
    def get_db():
        with factory() as db:
            yield db

    sink = SimpleNamespace(deliver=pytest.fail)
    monkeypatch.setattr("src.storage.database.get_db", get_db)
    monkeypatch.setattr(worker, "_build_workflow_alert_sink", lambda _settings: sink)
    connection = await _connect(test_engine)
    try:
        assert await worker._run_workflow_alert_maintenance_tick(
            connection,
            alert_settings=_webhook_alert_settings(batch_size=2),
        )
        with factory() as db:
            assert db.get(WorkflowAlertDelivery, delivery_id) is None
            assert db.get(WorkflowTerminalEvent, event_id) is None
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_fair_pending_cohorts_include_child_under_sustained_root_backlog(
    test_engine,
) -> None:
    from src.queue import worker

    connection = await _connect(test_engine)
    root_ids = [_BASE_ID + 300 + index for index in range(6)]
    child_ids = [_BASE_ID + 400 + index for index in range(2)]
    event_ids: list[UUID] = []
    try:
        for root_id in root_ids:
            await _insert_job(
                connection,
                operation_id=root_id,
                operation_type="pipeline.run",
                status="failed",
            )
        for child_id in child_ids:
            await _insert_job(
                connection,
                operation_id=child_id,
                operation_type="ingestion.execute",
                status="failed",
                parent_job_id=root_ids[-1],
            )
        for operation_id in [*root_ids, *child_ids]:
            event_id = uuid4()
            event_ids.append(event_id)
            await connection.execute(
                """
                INSERT INTO workflow_terminal_events (
                    id, event_key, source_kind, operation_id, claim_generation,
                    terminal_status, classification_status, occurred_at, created_at
                ) VALUES ($1, $2, 'operation', $3, 0, 'failed', 'pending', NOW(), NOW())
                """,
                event_id,
                f"operation:{operation_id}:claim:0:status:failed",
                operation_id,
            )

        root_limit, child_limit = worker._workflow_alert_cohort_sizes(4)
        selected_events = await connection.fetch(
            worker._WORKFLOW_ALERT_PENDING_EVENT_QUERY,
            root_limit,
            child_limit,
        )
        selected = await connection.fetch(
            "SELECT operation_id FROM workflow_terminal_events WHERE id = ANY($1::uuid[])",
            [row["id"] for row in selected_events],
        )
        selected_ids = {int(row["operation_id"]) for row in selected}

        assert len(selected_ids.intersection(root_ids)) == root_limit
        assert len(selected_ids.intersection(child_ids)) == child_limit
    finally:
        await connection.execute(
            "DELETE FROM workflow_terminal_events WHERE id = ANY($1::uuid[])",
            event_ids,
        )
        await connection.execute(
            "DELETE FROM pgqueuer_jobs WHERE id = ANY($1::bigint[])",
            child_ids,
        )
        await connection.execute(
            "DELETE FROM pgqueuer_jobs WHERE id = ANY($1::bigint[])",
            root_ids,
        )
        await connection.close()
