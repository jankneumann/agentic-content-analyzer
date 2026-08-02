"""PostgreSQL evidence for bounded and atomic Content reconciliation."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import asyncpg
import pytest

from src.contracts.workflow_models import ContentReconciliationRequest
from src.models.jobs import OperationPayloadV2
from src.queue.content_execution_lock import _CONTENT_EXECUTION_LOCK_NAMESPACE
from src.services.content_reconciliation_service import (
    ContentReconciliationApplyDisabledError,
    ContentReconciliationService,
)

pytestmark = pytest.mark.integration

_BASE_ID = 9_700_000


async def _connect(test_engine) -> asyncpg.Connection:
    return await asyncpg.connect(test_engine.url.render_as_string(hide_password=False))


async def _insert_owned_candidate(
    conn: asyncpg.Connection,
    *,
    content_id: int,
    operation_id: int,
    phase: str,
    content_status: str,
    operation_status: str,
    retry_count: int = 0,
    cancel_requested: bool = False,
    force: bool = False,
    heartbeat_at: datetime | None = None,
    completed_at: datetime | None = None,
    protocol: int = 2,
) -> None:
    operation_type = "ingestion.execute" if phase == "parsing" else "summarization.run"
    payload = OperationPayloadV2(
        operation_type=operation_type,
        input={"force": force} if force else {},
        cancel_requested=cancel_requested,
    ).model_dump(mode="json")
    await conn.execute(
        """
        INSERT INTO pgqueuer_jobs (
            id, entrypoint, payload, status, retry_count, heartbeat_at,
            claim_generation, claim_protocol_version, completed_at
        ) VALUES ($1, $2, $3::jsonb, $4, $5, $6, 1, $7, $8)
        """,
        operation_id,
        operation_type,
        json.dumps(payload),
        operation_status,
        retry_count,
        heartbeat_at,
        protocol,
        completed_at,
    )
    await conn.execute(
        """
        INSERT INTO contents (
            id, source_type, source_id, title, markdown_content, content_hash, status,
            status_operation_id, status_claim_generation,
            status_operation_phase, status_owner_version
        ) VALUES (
            $1, 'manual', $2, 'reconciliation fixture', '# fixture', $2,
            $3, $4, 1, $5, 1
        )
        """,
        content_id,
        f"reconciliation-{content_id}",
        content_status,
        operation_id,
        phase,
    )


async def _insert_matching_summary(
    conn: asyncpg.Connection,
    *,
    content_id: int,
    operation_id: int,
) -> datetime:
    created_at = (datetime.now(UTC) - timedelta(minutes=2)).replace(tzinfo=None)
    await conn.execute(
        """
        INSERT INTO summaries (
            content_id, executive_summary, key_themes, strategic_insights,
            technical_details, actionable_items, notable_quotes, relevance_scores,
            agent_framework, model_used, created_at,
            operation_id, operation_claim_generation
        ) VALUES (
            $1, 'summary', '[]'::json, '[]'::json, '[]'::json,
            '[]'::json, '[]'::json, '{}'::json, 'test', 'test', $3, $2, 1
        )
        """,
        content_id,
        operation_id,
        created_at,
    )
    return created_at


def _service(
    conn: asyncpg.Connection,
    *,
    apply_enabled: bool,
    batch_size: int = 50,
) -> ContentReconciliationService:
    return ContentReconciliationService(
        connection=conn,
        stale_seconds=3600,
        max_retries=3,
        batch_size=batch_size,
        lock_timeout_ms=250,
        statement_timeout_ms=5000,
        apply_enabled=apply_enabled,
    )


@pytest.mark.asyncio
async def test_dry_run_is_read_only_bounded_and_keyset_paginated(test_engine) -> None:
    conn = await _connect(test_engine)
    transaction = conn.transaction()
    await transaction.start()
    try:
        for offset in range(3):
            await _insert_owned_candidate(
                conn,
                content_id=_BASE_ID + offset,
                operation_id=_BASE_ID + 100 + offset,
                phase="processing",
                content_status="failed",
                operation_status="failed",
            )
        before = await conn.fetch(
            """
            SELECT c.id, c.status, c.status_owner_version, j.status AS operation_status,
                   j.retry_count, j.claim_protocol_version
            FROM contents AS c
            JOIN pgqueuer_jobs AS j ON j.id = c.status_operation_id
            WHERE c.id BETWEEN $1 AND $2
            ORDER BY c.id
            """,
            _BASE_ID,
            _BASE_ID + 2,
        )

        report = await _service(conn, apply_enabled=False, batch_size=2).reconcile(
            ContentReconciliationRequest(apply=False, limit=2)
        )

        assert report.mode == "dry_run"
        assert report.scanned == report.reported == 2
        assert [item.content_id for item in report.items] == [_BASE_ID, _BASE_ID + 1]
        assert report.next_after_content_id == _BASE_ID + 1
        assert all(item.projection == "proposed" for item in report.items)
        assert all(item.action == "retry_operation" for item in report.items)
        after = await conn.fetch(
            """
            SELECT c.id, c.status, c.status_owner_version, j.status AS operation_status,
                   j.retry_count, j.claim_protocol_version
            FROM contents AS c
            JOIN pgqueuer_jobs AS j ON j.id = c.status_operation_id
            WHERE c.id BETWEEN $1 AND $2
            ORDER BY c.id
            """,
            _BASE_ID,
            _BASE_ID + 2,
        )
        assert [tuple(row) for row in after] == [tuple(row) for row in before]
        assert (
            await conn.fetchval(
                "SELECT COUNT(*) FROM content_reconciliation_actions WHERE content_id BETWEEN $1 AND $2",
                _BASE_ID,
                _BASE_ID + 2,
            )
            == 0
        )
    finally:
        await transaction.rollback()
        await conn.close()


@pytest.mark.asyncio
async def test_apply_gate_fails_closed_without_mutation(test_engine) -> None:
    conn = await _connect(test_engine)
    transaction = conn.transaction()
    await transaction.start()
    try:
        await _insert_owned_candidate(
            conn,
            content_id=_BASE_ID + 10,
            operation_id=_BASE_ID + 110,
            phase="processing",
            content_status="failed",
            operation_status="failed",
        )

        with pytest.raises(ContentReconciliationApplyDisabledError):
            await _service(conn, apply_enabled=False).reconcile(
                ContentReconciliationRequest(apply=True)
            )

        assert (
            await conn.fetchval(
                "SELECT status FROM contents WHERE id = $1",
                _BASE_ID + 10,
            )
            == "failed"
        )
    finally:
        await transaction.rollback()
        await conn.close()


@pytest.mark.asyncio
async def test_dry_run_rejects_multi_content_url_success_evidence(test_engine) -> None:
    conn = await _connect(test_engine)
    transaction = conn.transaction()
    await transaction.start()
    content_id = _BASE_ID + 11
    operation_id = _BASE_ID + 111
    try:
        await _insert_owned_candidate(
            conn,
            content_id=content_id,
            operation_id=operation_id,
            phase="parsing",
            content_status="parsing",
            operation_status="completed",
            completed_at=datetime.now(UTC),
        )
        result = {
            "command_key": "url",
            "resolved_route": "webpage",
            "status": "ok",
            "outcome": "success",
            "content_ids": [content_id, content_id + 1],
        }
        await conn.execute(
            """
            UPDATE pgqueuer_jobs
            SET payload = payload || jsonb_build_object('result', $2::jsonb)
            WHERE id = $1
            """,
            operation_id,
            json.dumps(result),
        )

        report = await _service(conn, apply_enabled=False).reconcile(
            ContentReconciliationRequest(apply=False)
        )

        item = next(item for item in report.items if item.content_id == content_id)
        assert (item.action, item.reason) == ("none", "completed_output_missing")
    finally:
        await transaction.rollback()
        await conn.close()


@pytest.mark.asyncio
async def test_dry_run_rejects_non_array_url_content_id_evidence(test_engine) -> None:
    conn = await _connect(test_engine)
    transaction = conn.transaction()
    await transaction.start()
    content_id = _BASE_ID + 12
    operation_id = _BASE_ID + 112
    try:
        await _insert_owned_candidate(
            conn,
            content_id=content_id,
            operation_id=operation_id,
            phase="parsing",
            content_status="parsing",
            operation_status="completed",
            completed_at=datetime.now(UTC),
        )
        result = {
            "command_key": "url",
            "resolved_route": "webpage",
            "status": "ok",
            "outcome": "success",
            "content_ids": {"unexpected": content_id},
        }
        await conn.execute(
            """
            UPDATE pgqueuer_jobs
            SET payload = payload || jsonb_build_object('result', $2::jsonb)
            WHERE id = $1
            """,
            operation_id,
            json.dumps(result),
        )

        report = await _service(conn, apply_enabled=False).reconcile(
            ContentReconciliationRequest(apply=False)
        )

        item = next(item for item in report.items if item.content_id == content_id)
        assert (item.action, item.reason) == ("none", "completed_output_missing")
    finally:
        await transaction.rollback()
        await conn.close()


@pytest.mark.asyncio
async def test_dry_run_rejects_out_of_range_url_content_id_evidence(test_engine) -> None:
    conn = await _connect(test_engine)
    transaction = conn.transaction()
    await transaction.start()
    content_id = _BASE_ID + 13
    operation_id = _BASE_ID + 113
    try:
        await _insert_owned_candidate(
            conn,
            content_id=content_id,
            operation_id=operation_id,
            phase="parsing",
            content_status="parsing",
            operation_status="completed",
            completed_at=datetime.now(UTC),
        )
        result = {
            "command_key": "url",
            "resolved_route": "webpage",
            "status": "ok",
            "outcome": "success",
            "content_ids": [9_999_999_999_999_999_999],
        }
        await conn.execute(
            """
            UPDATE pgqueuer_jobs
            SET payload = payload || jsonb_build_object('result', $2::jsonb)
            WHERE id = $1
            """,
            operation_id,
            json.dumps(result),
        )

        report = await _service(conn, apply_enabled=False).reconcile(
            ContentReconciliationRequest(apply=False)
        )

        item = next(item for item in report.items if item.content_id == content_id)
        assert (item.action, item.reason) == ("none", "completed_output_missing")
    finally:
        await transaction.rollback()
        await conn.close()


@pytest.mark.asyncio
async def test_apply_projects_matching_summary_and_audits_on_supplied_connection(
    test_engine,
) -> None:
    conn = await _connect(test_engine)
    transaction = conn.transaction()
    await transaction.start()
    content_id = _BASE_ID + 20
    operation_id = _BASE_ID + 120
    try:
        await _insert_owned_candidate(
            conn,
            content_id=content_id,
            operation_id=operation_id,
            phase="processing",
            content_status="processing",
            operation_status="completed",
            completed_at=datetime.now(UTC),
        )
        summary_created_at = await _insert_matching_summary(
            conn,
            content_id=content_id,
            operation_id=operation_id,
        )
        await conn.fetchval(
            "SELECT pg_advisory_xact_lock($1::integer, $2::integer)",
            _CONTENT_EXECUTION_LOCK_NAMESPACE,
            content_id,
        )
        run_id = uuid4()

        report = await _service(conn, apply_enabled=True).reconcile(
            ContentReconciliationRequest(apply=True),
            run_id=run_id,
        )

        assert report.counts.applied == report.counts.projected == 1
        assert report.items[0].projection == "observed"
        assert report.items[0].action == "project_completed"
        content = await conn.fetchrow(
            """
            SELECT status, error_message, processed_at, status_operation_id,
                   status_claim_generation, status_operation_phase, status_owner_version
            FROM contents WHERE id = $1
            """,
            content_id,
        )
        assert content is not None
        assert content["status"] == "completed"
        assert content["error_message"] is None
        assert content["processed_at"] == summary_created_at.replace(tzinfo=None)
        assert tuple(content)[3:] == (None, None, None, None)
        audit = await conn.fetchrow(
            """
            SELECT run_id, action, reason, content_status_before, content_status_after
            FROM content_reconciliation_actions WHERE content_id = $1
            """,
            content_id,
        )
        assert audit is not None
        assert UUID(str(audit["run_id"])) == run_id
        assert (audit["action"], audit["reason"]) == (
            "project_completed",
            "summary_exists",
        )
    finally:
        await transaction.rollback()
        await conn.close()


@pytest.mark.parametrize("phase", ["parsing", "processing"])
@pytest.mark.asyncio
async def test_apply_recovers_stale_owner_to_failed_then_retries_same_operation(
    test_engine,
    phase: str,
) -> None:
    conn = await _connect(test_engine)
    transaction = conn.transaction()
    await transaction.start()
    offset = 30 if phase == "parsing" else 31
    content_id = _BASE_ID + offset
    operation_id = _BASE_ID + 130 + offset
    transitional = phase
    try:
        await _insert_owned_candidate(
            conn,
            content_id=content_id,
            operation_id=operation_id,
            phase=phase,
            content_status=transitional,
            operation_status="in_progress",
            heartbeat_at=datetime.now(UTC) - timedelta(hours=2),
        )

        report = await _service(conn, apply_enabled=True).reconcile(
            ContentReconciliationRequest(apply=True)
        )

        item = next(item for item in report.items if item.content_id == content_id)
        assert (item.action, item.reason, item.applied) == (
            "retry_operation",
            "stale_operation",
            True,
        )
        assert (item.operation_status_after, item.retry_count_after) == ("queued", 1)
        content = await conn.fetchrow(
            """
            SELECT status, status_operation_id, status_claim_generation,
                   status_operation_phase, status_owner_version
            FROM contents WHERE id = $1
            """,
            content_id,
        )
        assert tuple(content) == ("failed", operation_id, 1, phase, 2)
        operation = await conn.fetchrow(
            """
            SELECT status, retry_count, claim_generation, claim_protocol_version
            FROM pgqueuer_jobs WHERE id = $1
            """,
            operation_id,
        )
        assert tuple(operation) == ("queued", 1, 1, 1)
        audit = await conn.fetchrow(
            """
            SELECT content_status_before, content_status_after,
                   operation_status_before, operation_status_after,
                   retry_count_before, retry_count_after
            FROM content_reconciliation_actions WHERE content_id = $1
            """,
            content_id,
        )
        assert tuple(audit) == (
            transitional,
            "failed",
            "in_progress",
            "queued",
            0,
            1,
        )
    finally:
        await transaction.rollback()
        await conn.close()


@pytest.mark.asyncio
async def test_audit_failure_rolls_back_item_and_continues_later_items(
    test_engine,
    monkeypatch,
) -> None:
    conn = await _connect(test_engine)
    transaction = conn.transaction()
    await transaction.start()
    first_content = _BASE_ID + 40
    second_content = _BASE_ID + 41
    try:
        for content_id, operation_id in (
            (first_content, _BASE_ID + 140),
            (second_content, _BASE_ID + 141),
        ):
            await _insert_owned_candidate(
                conn,
                content_id=content_id,
                operation_id=operation_id,
                phase="processing",
                content_status="processing",
                operation_status="completed",
                completed_at=datetime.now(UTC),
            )
            await _insert_matching_summary(
                conn,
                content_id=content_id,
                operation_id=operation_id,
            )
        service = _service(conn, apply_enabled=True)
        insert_action = service._insert_action

        async def fail_first_action(*args, **kwargs):
            decision = kwargs["decision"]
            if decision.content_id == first_content:
                raise RuntimeError("audit unavailable")
            return await insert_action(*args, **kwargs)

        monkeypatch.setattr(service, "_insert_action", fail_first_action)

        report = await service.reconcile(ContentReconciliationRequest(apply=True))

        assert [(item.content_id, item.reason) for item in report.items] == [
            (first_content, "apply_failed"),
            (second_content, "summary_exists"),
        ]
        states = await conn.fetch(
            "SELECT id, status FROM contents WHERE id IN ($1, $2) ORDER BY id",
            first_content,
            second_content,
        )
        assert [(row["id"], row["status"]) for row in states] == [
            (first_content, "processing"),
            (second_content, "completed"),
        ]
        assert (
            await conn.fetchval(
                "SELECT COUNT(*) FROM content_reconciliation_actions WHERE content_id IN ($1, $2)",
                first_content,
                second_content,
            )
            == 1
        )
        assert report.counts.failed == 1
        assert report.counts.applied == 1
        failure_event = await conn.fetchrow(
            """
            SELECT event_key, classification_status, envelope
            FROM workflow_terminal_events
            WHERE reconciliation_run_id = $1
              AND reconciliation_content_id = $2
            """,
            report.run_id,
            first_content,
        )
        assert failure_event is not None
        assert failure_event["event_key"] == (
            f"reconciliation-failure:{report.run_id}:content:{first_content}:reason:apply_failed"
        )
        assert failure_event["classification_status"] == "pending"
        assert failure_event["envelope"] is None
    finally:
        await transaction.rollback()
        await conn.close()


@pytest.mark.asyncio
async def test_repeated_apply_does_not_duplicate_repair_or_audit(test_engine) -> None:
    conn = await _connect(test_engine)
    transaction = conn.transaction()
    await transaction.start()
    content_id = _BASE_ID + 50
    operation_id = _BASE_ID + 150
    try:
        await _insert_owned_candidate(
            conn,
            content_id=content_id,
            operation_id=operation_id,
            phase="processing",
            content_status="processing",
            operation_status="completed",
            completed_at=datetime.now(UTC),
        )
        await _insert_matching_summary(
            conn,
            content_id=content_id,
            operation_id=operation_id,
        )
        service = _service(conn, apply_enabled=True)

        first = await service.reconcile(ContentReconciliationRequest(apply=True))
        second = await service.reconcile(ContentReconciliationRequest(apply=True))

        assert first.counts.applied == 1
        assert second.scanned == second.reported == second.counts.applied == 0
        assert (
            await conn.fetchval(
                "SELECT COUNT(*) FROM content_reconciliation_actions WHERE content_id = $1",
                content_id,
            )
            == 1
        )
    finally:
        await transaction.rollback()
        await conn.close()


@pytest.mark.asyncio
async def test_apply_reports_revalidation_conflict_when_heartbeat_refreshes(
    test_engine,
    monkeypatch,
) -> None:
    conn = await _connect(test_engine)
    transaction = conn.transaction()
    await transaction.start()
    content_id = _BASE_ID + 60
    operation_id = _BASE_ID + 160
    try:
        await _insert_owned_candidate(
            conn,
            content_id=content_id,
            operation_id=operation_id,
            phase="processing",
            content_status="processing",
            operation_status="in_progress",
            heartbeat_at=datetime.now(UTC) - timedelta(hours=2),
        )
        service = _service(conn, apply_enabled=True)
        read_candidate = service._read_candidate

        async def refresh_then_read(candidate_content_id: int):
            await conn.execute(
                "UPDATE pgqueuer_jobs SET heartbeat_at = NOW() WHERE id = $1",
                operation_id,
            )
            return await read_candidate(candidate_content_id)

        monkeypatch.setattr(service, "_read_candidate", refresh_then_read)

        report = await service.reconcile(ContentReconciliationRequest(apply=True))

        item = next(item for item in report.items if item.content_id == content_id)
        assert (item.action, item.reason, item.applied) == (
            "none",
            "revalidation_conflict",
            False,
        )
        assert (
            await conn.fetchval(
                "SELECT COUNT(*) FROM content_reconciliation_actions WHERE content_id = $1",
                content_id,
            )
            == 0
        )
    finally:
        await transaction.rollback()
        await conn.close()


@pytest.mark.asyncio
async def test_apply_reports_apply_failed_when_operation_graph_vanishes(
    test_engine,
    monkeypatch,
) -> None:
    conn = await _connect(test_engine)
    transaction = conn.transaction()
    await transaction.start()
    content_id = _BASE_ID + 71
    operation_id = _BASE_ID + 231
    try:
        await _insert_owned_candidate(
            conn,
            content_id=content_id,
            operation_id=operation_id,
            phase="processing",
            content_status="failed",
            operation_status="failed",
        )

        async def vanished_root(*args, **kwargs):
            return None

        monkeypatch.setattr(
            "src.services.content_reconciliation_service.queue_setup._resolve_operation_graph_root",
            vanished_root,
        )

        report = await _service(conn, apply_enabled=True).reconcile(
            ContentReconciliationRequest(apply=True)
        )

        item = next(item for item in report.items if item.content_id == content_id)
        assert (item.action, item.reason, item.applied) == (
            "none",
            "apply_failed",
            False,
        )
        assert report.counts.retried == 0
        assert report.counts.failed == 1
        assert (
            await conn.fetchval(
                """
                SELECT COUNT(*) FROM workflow_terminal_events
                WHERE reconciliation_run_id = $1
                  AND reconciliation_content_id = $2
                  AND source_kind = 'reconciliation_failure'
                """,
                report.run_id,
                content_id,
            )
            == 1
        )
    finally:
        await transaction.rollback()
        await conn.close()


@pytest.mark.asyncio
async def test_apply_reports_execution_locked_on_content_lock_contention(test_engine) -> None:
    conn = await _connect(test_engine)
    holder = await _connect(test_engine)
    transaction = conn.transaction()
    holder_transaction = holder.transaction()
    await transaction.start()
    await holder_transaction.start()
    content_id = _BASE_ID + 61
    operation_id = _BASE_ID + 161
    try:
        await _insert_owned_candidate(
            conn,
            content_id=content_id,
            operation_id=operation_id,
            phase="processing",
            content_status="processing",
            operation_status="in_progress",
            heartbeat_at=datetime.now(UTC) - timedelta(hours=2),
        )
        await holder.fetchval(
            "SELECT pg_advisory_xact_lock($1::integer, $2::integer)",
            _CONTENT_EXECUTION_LOCK_NAMESPACE,
            content_id,
        )

        report = await _service(conn, apply_enabled=True).reconcile(
            ContentReconciliationRequest(apply=True)
        )

        item = next(item for item in report.items if item.content_id == content_id)
        assert (item.action, item.reason, item.applied) == (
            "none",
            "execution_locked",
            False,
        )
        assert (
            await conn.fetchval(
                "SELECT status FROM pgqueuer_jobs WHERE id = $1",
                operation_id,
            )
            == "in_progress"
        )
    finally:
        await holder_transaction.rollback()
        await transaction.rollback()
        await holder.close()
        await conn.close()


@pytest.mark.parametrize(
    ("operation_status", "heartbeat_at", "expected_reason"),
    [
        ("in_progress", datetime.now(UTC), "active_operation"),
        ("failed", None, "execution_locked"),
    ],
)
@pytest.mark.asyncio
async def test_apply_skips_locks_for_fresh_noop_but_reports_failed_retry_contention(
    test_engine,
    operation_status: str,
    heartbeat_at: datetime | None,
    expected_reason: str,
) -> None:
    conn = await _connect(test_engine)
    holder = await _connect(test_engine)
    transaction = conn.transaction()
    holder_transaction = holder.transaction()
    await transaction.start()
    await holder_transaction.start()
    offset = 68 if operation_status == "in_progress" else 69
    content_id = _BASE_ID + offset
    operation_id = _BASE_ID + 260 + offset
    try:
        await _insert_owned_candidate(
            conn,
            content_id=content_id,
            operation_id=operation_id,
            phase="processing",
            content_status=("processing" if operation_status == "in_progress" else "failed"),
            operation_status=operation_status,
            heartbeat_at=heartbeat_at,
        )
        await holder.fetchval(
            "SELECT pg_advisory_xact_lock($1::integer, $2::integer)",
            _CONTENT_EXECUTION_LOCK_NAMESPACE,
            content_id,
        )

        report = await _service(conn, apply_enabled=True).reconcile(
            ContentReconciliationRequest(apply=True)
        )

        item = next(item for item in report.items if item.content_id == content_id)
        assert (item.action, item.reason, item.applied) == (
            "none",
            expected_reason,
            False,
        )
    finally:
        await holder_transaction.rollback()
        await transaction.rollback()
        await holder.close()
        await conn.close()


@pytest.mark.asyncio
async def test_apply_finalizes_abandoned_stale_cancellation(test_engine) -> None:
    conn = await _connect(test_engine)
    transaction = conn.transaction()
    await transaction.start()
    content_id = _BASE_ID + 62
    operation_id = _BASE_ID + 162
    try:
        await _insert_owned_candidate(
            conn,
            content_id=content_id,
            operation_id=operation_id,
            phase="processing",
            content_status="processing",
            operation_status="in_progress",
            cancel_requested=True,
            heartbeat_at=datetime.now(UTC) - timedelta(hours=2),
        )

        report = await _service(conn, apply_enabled=True).reconcile(
            ContentReconciliationRequest(apply=True)
        )

        item = next(item for item in report.items if item.content_id == content_id)
        assert (item.action, item.reason, item.applied) == (
            "cancel_restore_parsed",
            "cancellation_requested",
            True,
        )
        assert (
            await conn.fetchval(
                "SELECT status FROM pgqueuer_jobs WHERE id = $1",
                operation_id,
            )
            == "cancelled"
        )
        content = await conn.fetchrow(
            "SELECT status, status_operation_id, processed_at FROM contents WHERE id = $1",
            content_id,
        )
        assert tuple(content) == ("parsed", None, None)
    finally:
        await transaction.rollback()
        await conn.close()


@pytest.mark.parametrize(
    ("phase", "expected_status"),
    [("parsing", "pending"), ("processing", "parsed")],
)
@pytest.mark.asyncio
async def test_apply_restores_terminal_cancelled_owner(
    test_engine,
    phase: str,
    expected_status: str,
) -> None:
    conn = await _connect(test_engine)
    transaction = conn.transaction()
    await transaction.start()
    offset = 63 if phase == "parsing" else 64
    content_id = _BASE_ID + offset
    operation_id = _BASE_ID + 160 + offset
    try:
        await _insert_owned_candidate(
            conn,
            content_id=content_id,
            operation_id=operation_id,
            phase=phase,
            content_status="failed",
            operation_status="cancelled",
        )

        report = await _service(conn, apply_enabled=True).reconcile(
            ContentReconciliationRequest(apply=True)
        )

        item = next(item for item in report.items if item.content_id == content_id)
        assert item.applied is True
        assert item.content_status_after == expected_status
        content = await conn.fetchrow(
            """
            SELECT status, error_message, status_operation_id,
                   status_claim_generation, status_operation_phase, status_owner_version
            FROM contents WHERE id = $1
            """,
            content_id,
        )
        assert tuple(content) == (expected_status, None, None, None, None, None)
    finally:
        await transaction.rollback()
        await conn.close()


@pytest.mark.parametrize(
    ("force", "protocol", "expected_reason"),
    [(True, 2, "forced_reprocessing"), (False, 1, "incompatible_worker")],
)
@pytest.mark.asyncio
async def test_apply_force_and_legacy_protocol_are_noops(
    test_engine,
    force: bool,
    protocol: int,
    expected_reason: str,
) -> None:
    conn = await _connect(test_engine)
    transaction = conn.transaction()
    await transaction.start()
    offset = 65 if force else 66
    content_id = _BASE_ID + offset
    operation_id = _BASE_ID + 160 + offset
    try:
        await _insert_owned_candidate(
            conn,
            content_id=content_id,
            operation_id=operation_id,
            phase="processing",
            content_status="failed",
            operation_status="failed",
            force=force,
            protocol=protocol,
        )

        report = await _service(conn, apply_enabled=True).reconcile(
            ContentReconciliationRequest(apply=True)
        )

        item = next(item for item in report.items if item.content_id == content_id)
        assert (item.action, item.reason, item.applied) == (
            "none",
            expected_reason,
            False,
        )
        assert (
            await conn.fetchval(
                "SELECT retry_count FROM pgqueuer_jobs WHERE id = $1",
                operation_id,
            )
            == 0
        )
    finally:
        await transaction.rollback()
        await conn.close()


@pytest.mark.asyncio
async def test_retry_notification_rolls_back_when_audit_insert_fails(
    test_engine,
    monkeypatch,
) -> None:
    conn = await _connect(test_engine)
    listener = await _connect(test_engine)
    content_id = _BASE_ID + 67
    operation_id = _BASE_ID + 227
    notifications: list[str] = []

    def capture(*args) -> None:
        notifications.append(str(args[-1]))

    await listener.add_listener("pgqueuer", capture)
    try:
        await _insert_owned_candidate(
            conn,
            content_id=content_id,
            operation_id=operation_id,
            phase="processing",
            content_status="failed",
            operation_status="failed",
        )
        service = _service(conn, apply_enabled=True)

        async def fail_action(*args, **kwargs) -> None:
            raise RuntimeError("audit unavailable")

        monkeypatch.setattr(service, "_insert_action", fail_action)

        report = await service.reconcile(ContentReconciliationRequest(apply=True))
        await asyncio.sleep(0.05)

        item = next(item for item in report.items if item.content_id == content_id)
        assert item.reason == "apply_failed"
        assert notifications == []
        operation = await conn.fetchrow(
            "SELECT status, retry_count FROM pgqueuer_jobs WHERE id = $1",
            operation_id,
        )
        assert tuple(operation) == ("failed", 0)
    finally:
        await listener.remove_listener("pgqueuer", capture)
        await conn.execute("DELETE FROM contents WHERE id = $1", content_id)
        await conn.execute("DELETE FROM pgqueuer_jobs WHERE id = $1", operation_id)
        await listener.close()
        await conn.close()


@pytest.mark.asyncio
async def test_retry_notification_commits_with_action_audit(test_engine) -> None:
    conn = await _connect(test_engine)
    listener = await _connect(test_engine)
    content_id = _BASE_ID + 70
    operation_id = _BASE_ID + 230
    notifications: list[str] = []

    def capture(*args) -> None:
        notifications.append(str(args[-1]))

    await listener.add_listener("pgqueuer", capture)
    try:
        await _insert_owned_candidate(
            conn,
            content_id=content_id,
            operation_id=operation_id,
            phase="processing",
            content_status="failed",
            operation_status="failed",
        )

        report = await _service(conn, apply_enabled=True).reconcile(
            ContentReconciliationRequest(apply=True)
        )
        await asyncio.sleep(0.05)

        item = next(item for item in report.items if item.content_id == content_id)
        assert (item.operation_status_after, item.retry_count_after, item.applied) == (
            "queued",
            1,
            True,
        )
        audit = await conn.fetchrow(
            """
            SELECT operation_status_after, retry_count_after
            FROM content_reconciliation_actions WHERE content_id = $1
            """,
            content_id,
        )
        assert tuple(audit) == ("queued", 1)
        assert notifications == ["operation_retry"]
    finally:
        await listener.remove_listener("pgqueuer", capture)
        await listener.close()
        await conn.close()
