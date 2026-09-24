"""PostgreSQL evidence: a dead Substack session becomes exactly one actionable alert.

Nothing between the adapter and the webhook is stubbed except the two network
edges (Substack and the alert receiver, both ``httpx.MockTransport``):

    real SubstackContentIngestionService (fail closed, ``session_expired``)
      -> real ingestion handler (result attached, operation failed)
      -> real ``pgqueuer_jobs`` terminal trigger (pending terminal event)
      -> real worker alert tick: real classifier, REAL telemetry emitter,
         real delivery outbox, real ``WebhookAlertSink``
      -> the diagnostic URL the alert carries, served by the real routes.
"""

from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager, contextmanager
from types import SimpleNamespace

import asyncpg
import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.orm import sessionmaker

from src.api.dependencies import verify_admin_key
from src.api.operation_routes import router as operation_router
from src.api.workflow_dependencies import get_operation_service
from src.services.alert_sinks import WebhookAlertSink
from src.services.operation_service import OperationService
from tests.real_ingestion.dead_session import (
    DEAD_SUBSTACK_COOKIE,
    dead_substack_session_orchestrator,
)
from tests.real_ingestion.harness import RealIngestionHarness, _asyncpg_dsn

pytestmark = pytest.mark.integration

ORIGIN = "https://ops.example.com"
ENDPOINT = "https://alerts.example.com/hook"


def _webhook_alert_settings() -> SimpleNamespace:
    return SimpleNamespace(
        workflow_alert_sink="webhook",
        workflow_alert_diagnostic_origin=ORIGIN,
        workflow_alert_webhook_endpoint=ENDPOINT,
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
        workflow_alert_batch_size=50,
        get_workflow_alert_allowed_hosts=lambda: ("alerts.example.com",),
        is_development=False,
    )


@pytest.mark.asyncio
async def test_dead_substack_session_is_delivered_once_with_its_refresh_command(
    test_engine,
    tmp_path,
    monkeypatch,
) -> None:
    from src.queue import worker

    received: list[httpx.Request] = []

    def receiver(request: httpx.Request) -> httpx.Response:
        received.append(request)
        return httpx.Response(202)

    async def public_address(_host: str, _port: int) -> tuple[str, ...]:
        return ("93.184.216.34",)

    def build_sink(settings: SimpleNamespace) -> WebhookAlertSink:
        return WebhookAlertSink(
            endpoint=settings.workflow_alert_webhook_endpoint,
            allowed_hosts=settings.get_workflow_alert_allowed_hosts(),
            secret=None,
            timeout_seconds=settings.workflow_alert_timeout_seconds,
            max_retry_after_seconds=settings.workflow_alert_max_retry_after_seconds,
            client=httpx.AsyncClient(transport=httpx.MockTransport(receiver)),
            resolver=public_address,
        )

    factory = sessionmaker(bind=test_engine, expire_on_commit=False)

    @contextmanager
    def get_db():
        with factory() as db:
            yield db

    monkeypatch.setattr("src.storage.database.get_db", get_db)
    monkeypatch.setattr(worker, "_build_workflow_alert_sink", build_sink)

    conn = await asyncpg.connect(_asyncpg_dsn(test_engine))
    harness = RealIngestionHarness(
        test_engine, conn, token=uuid.uuid4().hex[:12], workspace=tmp_path
    )
    event_ids: list[uuid.UUID] = []
    try:
        outcome = await harness.submit_with_orchestrator(
            "substack", dead_substack_session_orchestrator()
        )
        operation_id = int(outcome.operation_id)
        assert outcome.status == "failed"
        assert outcome.content_row_delta == 0

        event = await conn.fetchrow(
            "SELECT id, classification_status FROM workflow_terminal_events "
            "WHERE operation_id = $1",
            operation_id,
        )
        assert event is not None
        event_ids.append(event["id"])
        assert event["classification_status"] == "pending"

        alert_settings = _webhook_alert_settings()
        assert await worker._run_workflow_alert_maintenance_tick(
            conn, alert_settings=alert_settings
        )
        # A second tick must neither reclassify nor redeliver.
        await worker._run_workflow_alert_maintenance_tick(conn, alert_settings=alert_settings)

        ours = [
            request
            for request in received
            if json.loads(request.content)["event_id"] == str(event["id"])
        ]
        assert len(ours) == 1
        body = json.loads(ours[0].content)
        assert body["severity"] == "error"
        assert body["outcome"] == "failed"
        assert body["workflow_type"] == "ingestion.execute"
        assert body["codes"] == ["operation_failed", "session_expired"]
        assert body["remediation_command"] == "aca auth session substack"
        assert body["diagnostic_url"] == f"{ORIGIN}/api/v1/operations/{operation_id}"
        assert ours[0].headers["Idempotency-Key"].startswith("workflow-alert:")
        assert DEAD_SUBSTACK_COOKIE not in ours[0].content.decode()
        assert "substack.sid" not in ours[0].content.decode()

        row = await conn.fetchrow(
            """
            SELECT event.classification_status, event.telemetry_emitted_at,
                   COUNT(delivery.id) AS deliveries,
                   COUNT(delivery.id) FILTER (WHERE delivery.status = 'delivered')
                       AS delivered
            FROM workflow_terminal_events AS event
            LEFT JOIN workflow_alert_deliveries AS delivery ON delivery.event_id = event.id
            WHERE event.id = $1
            GROUP BY event.id
            """,
            event["id"],
        )
        assert row["classification_status"] == "ready"
        # Set only by the REAL emitter returning True.
        assert row["telemetry_emitted_at"] is not None
        assert (row["deliveries"], row["delivered"]) == (1, 1)

        # The alert's own follow-up links resolve through the real routes.
        app = FastAPI()
        app.include_router(operation_router)
        app.dependency_overrides[verify_admin_key] = lambda: None
        app.dependency_overrides[get_operation_service] = lambda: OperationService(connection=conn)

        @asynccontextmanager
        async def queue_connection(*_args, **_kwargs):
            yield conn

        monkeypatch.setattr(
            "src.api.operation_routes.queue_setup._queue_connection", queue_connection
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url=ORIGIN
        ) as client:
            operation = await client.get(body["diagnostic_url"].removeprefix(ORIGIN))
            diagnostic = await client.get(f"/api/v1/workflow-terminal-events/{event['id']}")

        assert operation.status_code == 200
        assert operation.json()["status"] == "failed"
        assert [error["code"] for error in operation.json()["result"]["errors"]] == [
            "session_expired"
        ]
        assert DEAD_SUBSTACK_COOKIE not in operation.text
        assert diagnostic.status_code == 200
        assert diagnostic.json()["classification_status"] == "ready"
        assert diagnostic.json()["delivery_counts"]["delivered"] == 1
    finally:
        if event_ids:
            await conn.execute(
                "DELETE FROM workflow_alert_deliveries WHERE event_id = ANY($1::uuid[])",
                event_ids,
            )
            await conn.execute(
                "DELETE FROM workflow_terminal_events WHERE id = ANY($1::uuid[])", event_ids
            )
        try:
            await harness.cleanup()
        finally:
            await conn.close()
