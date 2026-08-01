"""PostgreSQL evidence for graph-aware operation retention."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import asyncpg
import pytest

from src.models.jobs import OperationPayloadV2, OperationStatus, OperationType
from src.queue import setup as queue_setup, worker
from src.services.operation_service import OperationService

pytestmark = pytest.mark.integration

_BASE_ID = 9_500_000


async def _connect(test_engine) -> asyncpg.Connection:
    return await asyncpg.connect(test_engine.url.render_as_string(hide_password=False))


async def _insert_job(
    conn: asyncpg.Connection,
    job_id: int,
    *,
    status: str,
    age: str | None,
    parent_job_id: int | None = None,
) -> None:
    await conn.execute(
        """
        INSERT INTO pgqueuer_jobs (
            id, entrypoint, payload, status, parent_job_id, completed_at
        )
        VALUES (
            $1, 'ingestion.execute', '{}'::jsonb, $2, $3,
            CASE WHEN $4::text IS NULL
                THEN NULL
                ELSE CURRENT_TIMESTAMP - $4::interval
            END
        )
        """,
        job_id,
        status,
        parent_job_id,
        age,
    )


async def _delete_fixture_jobs(conn: asyncpg.Connection, first_id: int, last_id: int) -> None:
    await conn.execute(
        "DELETE FROM pgqueuer_jobs WHERE id BETWEEN $1 AND $2",
        first_id,
        last_id,
    )


@pytest.mark.asyncio
async def test_retention_deletes_only_whole_eligible_graphs_at_strict_cutoffs(
    test_engine,
) -> None:
    conn = await _connect(test_engine)
    transaction = conn.transaction()
    await transaction.start()
    try:
        await _insert_job(conn, _BASE_ID + 0, status="completed", age="31 days")
        await _insert_job(
            conn,
            _BASE_ID + 1,
            status="cancelled",
            age="31 days",
            parent_job_id=_BASE_ID + 0,
        )

        await _insert_job(conn, _BASE_ID + 10, status="completed", age="31 days")
        await _insert_job(
            conn,
            _BASE_ID + 11,
            status="in_progress",
            age=None,
            parent_job_id=_BASE_ID + 10,
        )

        await _insert_job(conn, _BASE_ID + 20, status="completed", age="31 days")
        await _insert_job(
            conn,
            _BASE_ID + 21,
            status="completed",
            age=None,
            parent_job_id=_BASE_ID + 20,
        )

        await _insert_job(conn, _BASE_ID + 30, status="completed", age="100 days")
        await _insert_job(
            conn,
            _BASE_ID + 31,
            status="failed",
            age="89 days",
            parent_job_id=_BASE_ID + 30,
        )

        await _insert_job(conn, _BASE_ID + 40, status="completed", age="91 days")
        await _insert_job(
            conn,
            _BASE_ID + 41,
            status="failed",
            age="91 days",
            parent_job_id=_BASE_ID + 40,
        )

        await _insert_job(conn, _BASE_ID + 50, status="completed", age="30 days")
        await _insert_job(conn, _BASE_ID + 60, status="cancelled", age="31 days")

        deleted = await queue_setup.cleanup_old_jobs(
            older_than_days=30,
            failed_older_than_days=90,
            batch_size=100,
            conn=conn,
        )

        assert deleted == 5
        rows = await conn.fetch(
            "SELECT id, parent_job_id FROM pgqueuer_jobs WHERE id BETWEEN $1 AND $2",
            _BASE_ID,
            _BASE_ID + 60,
        )
        remaining = {int(row["id"]): row["parent_job_id"] for row in rows}
        assert remaining == {
            _BASE_ID + 10: None,
            _BASE_ID + 11: _BASE_ID + 10,
            _BASE_ID + 20: None,
            _BASE_ID + 21: _BASE_ID + 20,
            _BASE_ID + 30: None,
            _BASE_ID + 31: _BASE_ID + 30,
            _BASE_ID + 50: None,
        }
    finally:
        await transaction.rollback()
        await conn.close()


@pytest.mark.asyncio
async def test_retention_batch_is_root_bounded_and_restart_idempotent(test_engine) -> None:
    conn = await _connect(test_engine)
    transaction = conn.transaction()
    await transaction.start()
    try:
        await _insert_job(conn, _BASE_ID + 100, status="completed", age="31 days")
        await _insert_job(conn, _BASE_ID + 101, status="completed", age="31 days")

        first = await queue_setup.cleanup_old_jobs(batch_size=1, conn=conn)
        second = await queue_setup.cleanup_old_jobs(batch_size=1, conn=conn)
        duplicate = await queue_setup.cleanup_old_jobs(batch_size=1, conn=conn)

        assert (first, second, duplicate) == (1, 1, 0)
    finally:
        await transaction.rollback()
        await conn.close()


@pytest.mark.asyncio
async def test_retention_transactionally_rechecks_a_graph_that_turns_active(test_engine) -> None:
    locker = await _connect(test_engine)
    cleaner = await _connect(test_engine)
    child_id = _BASE_ID + 201
    transaction: asyncpg.Transaction | None = locker.transaction()
    cleanup: asyncio.Task[int] | None = None
    await transaction.start()
    try:
        await _insert_job(locker, _BASE_ID + 200, status="completed", age="31 days")
        await _insert_job(
            locker,
            child_id,
            status="completed",
            age="31 days",
            parent_job_id=_BASE_ID + 200,
        )
        await transaction.commit()
        transaction = None

        transaction = locker.transaction()
        await transaction.start()
        await locker.fetchval("SELECT id FROM pgqueuer_jobs WHERE id = $1 FOR UPDATE", child_id)
        cleanup = asyncio.create_task(queue_setup.cleanup_old_jobs(conn=cleaner))
        await asyncio.sleep(0.1)
        await locker.execute(
            "UPDATE pgqueuer_jobs SET status = 'queued', completed_at = NULL WHERE id = $1",
            child_id,
        )
        await transaction.commit()
        transaction = None

        assert await cleanup == 0
        cleanup = None
        rows = await cleaner.fetch(
            "SELECT id, parent_job_id FROM pgqueuer_jobs WHERE id IN ($1, $2) ORDER BY id",
            _BASE_ID + 200,
            child_id,
        )
        assert [(row["id"], row["parent_job_id"]) for row in rows] == [
            (_BASE_ID + 200, None),
            (child_id, _BASE_ID + 200),
        ]
    finally:
        if cleanup is not None:
            cleanup.cancel()
            await asyncio.gather(cleanup, return_exceptions=True)
        if transaction is not None:
            await transaction.rollback()
        await _delete_fixture_jobs(cleaner, _BASE_ID + 200, child_id)
        await locker.close()
        await cleaner.close()


@pytest.mark.asyncio
async def test_depth_three_child_enqueue_serializes_with_retention(test_engine) -> None:
    """A child insert cannot cross a retention transaction and become detached."""

    cleaner = await _connect(test_engine)
    enqueuer = await _connect(test_engine)
    root_id = _BASE_ID + 300
    parent_id = _BASE_ID + 302
    enqueue: asyncio.Task[tuple[int, bool]] | None = None
    transaction: asyncpg.Transaction | None = cleaner.transaction()
    try:
        await _insert_job(cleaner, root_id, status="completed", age="1000 days")
        await _insert_job(
            cleaner,
            root_id + 1,
            status="completed",
            age="1000 days",
            parent_job_id=root_id,
        )
        await _insert_job(
            cleaner,
            parent_id,
            status="completed",
            age="1000 days",
            parent_job_id=root_id + 1,
        )

        await transaction.start()
        await cleaner.fetchval(
            "SELECT pg_advisory_xact_lock("
            "hashtextextended('aca:operation-graph:' || ($1::bigint)::text, 0))",
            root_id,
        )
        enqueue = asyncio.create_task(
            queue_setup.enqueue_queue_job(
                "summarize_content",
                {"content_id": 777},
                parent_job_id=parent_id,
                conn=enqueuer,
                idempotency_key=f"retention-race:{root_id}",
            )
        )

        await asyncio.sleep(0.1)
        assert not enqueue.done(), "child enqueue must wait for the root retention lock"

        assert await queue_setup.cleanup_old_jobs(batch_size=1, conn=cleaner) == 3
        await transaction.commit()
        transaction = None

        with pytest.raises(RuntimeError, match="live operation graph"):
            await enqueue
        enqueue = None

        rows = await cleaner.fetch(
            "SELECT id, parent_job_id FROM pgqueuer_jobs WHERE id BETWEEN $1 AND $2",
            root_id,
            parent_id + 1,
        )
        assert rows == []
    finally:
        if enqueue is not None:
            enqueue.cancel()
            await asyncio.gather(enqueue, return_exceptions=True)
        if transaction is not None:
            await transaction.rollback()
        await _delete_fixture_jobs(cleaner, root_id, parent_id + 1)
        await cleaner.close()
        await enqueuer.close()


@pytest.mark.asyncio
async def test_depth_three_active_child_prevents_retention_after_enqueue_wins(
    test_engine,
) -> None:
    """A committed active child remains attached when its enqueue wins the root lock."""

    cleaner = await _connect(test_engine)
    enqueuer = await _connect(test_engine)
    root_id = _BASE_ID + 400
    parent_id = _BASE_ID + 402
    child_id: int | None = None
    cleanup: asyncio.Task[int] | None = None
    transaction: asyncpg.Transaction | None = enqueuer.transaction()
    try:
        await _insert_job(cleaner, root_id, status="completed", age="1000 days")
        await _insert_job(
            cleaner,
            root_id + 1,
            status="completed",
            age="1000 days",
            parent_job_id=root_id,
        )
        await _insert_job(
            cleaner,
            parent_id,
            status="completed",
            age="1000 days",
            parent_job_id=root_id + 1,
        )

        await transaction.start()
        child_id, created = await queue_setup.enqueue_queue_job(
            "summarize_content",
            {"content_id": 778},
            parent_job_id=parent_id,
            conn=enqueuer,
            idempotency_key=f"retention-race-active:{root_id}",
        )
        assert created is True

        cleanup = asyncio.create_task(queue_setup.cleanup_old_jobs(batch_size=1, conn=cleaner))
        await asyncio.sleep(0.1)
        assert not cleanup.done(), "retention must wait for the child enqueue transaction"

        await transaction.commit()
        transaction = None
        assert await cleanup == 0
        cleanup = None

        row = await cleaner.fetchrow(
            "SELECT status, parent_job_id FROM pgqueuer_jobs WHERE id = $1",
            child_id,
        )
        assert row is not None
        assert (row["status"], row["parent_job_id"]) == ("queued", parent_id)
    finally:
        if cleanup is not None:
            cleanup.cancel()
            await asyncio.gather(cleanup, return_exceptions=True)
        if transaction is not None:
            await transaction.rollback()
        if child_id is not None:
            await cleaner.execute("DELETE FROM pgqueuer_jobs WHERE id = $1", child_id)
        await _delete_fixture_jobs(cleaner, root_id, parent_id)
        await cleaner.close()
        await enqueuer.close()


@pytest.mark.asyncio
async def test_retry_and_retention_share_root_lock_without_deadlock_or_lost_retry(
    test_engine,
) -> None:
    """Retry must serialize before its child-first CTE mutates graph lifecycle."""

    blocker = await _connect(test_engine)
    retry_conn = await _connect(test_engine)
    cleaner = await _connect(test_engine)
    observer = await _connect(test_engine)
    root_id = _BASE_ID + 500
    child_id = root_id + 1
    retry: asyncio.Task | None = None
    cleanup: asyncio.Task[int] | None = None
    transaction: asyncpg.Transaction | None = blocker.transaction()
    try:
        await blocker.execute(
            """
            INSERT INTO pgqueuer_jobs (
                id, entrypoint, payload, status, completed_at
            )
            VALUES ($1, 'pipeline.run', $2::jsonb, 'failed', NOW() - INTERVAL '1000 days')
            """,
            root_id,
            json.dumps(
                OperationPayloadV2(
                    operation_type=OperationType.PIPELINE_RUN,
                    input={"period": "daily"},
                    result={"retry_child_operation_ids": [child_id]},
                ).model_dump(mode="json")
            ),
        )
        await blocker.execute(
            """
            INSERT INTO pgqueuer_jobs (
                id, entrypoint, payload, status, parent_job_id, completed_at
            )
            VALUES (
                $1, 'summarization.run', $2::jsonb, 'failed', $3,
                NOW() - INTERVAL '1000 days'
            )
            """,
            child_id,
            json.dumps(
                OperationPayloadV2(
                    operation_type=OperationType.SUMMARIZATION_RUN,
                    input={},
                ).model_dump(mode="json")
            ),
            root_id,
        )

        await transaction.start()
        await blocker.fetchval(
            "SELECT id FROM pgqueuer_jobs WHERE id = $1 FOR UPDATE",
            child_id,
        )

        retry = asyncio.create_task(OperationService(connection=retry_conn).retry(root_id))
        await asyncio.sleep(0.1)
        assert not retry.done(), "retry must be waiting on the child row"
        graph_lock_available = await observer.fetchval(
            "SELECT pg_try_advisory_xact_lock("
            "hashtextextended('aca:operation-graph:' || ($1::bigint)::text, 0))",
            root_id,
        )
        assert graph_lock_available is False, "retry must own the graph lock before row updates"

        cleanup = asyncio.create_task(queue_setup.cleanup_old_jobs(batch_size=1, conn=cleaner))
        await asyncio.sleep(0.1)
        assert not cleanup.done(), "retention must wait for the retry graph lock"

        await transaction.commit()
        transaction = None
        handle = await retry
        retry = None
        assert handle.status is OperationStatus.QUEUED
        assert await cleanup == 0
        cleanup = None

        rows = await cleaner.fetch(
            "SELECT id, status, parent_job_id FROM pgqueuer_jobs "
            "WHERE id = ANY($1::bigint[]) ORDER BY id",
            [root_id, child_id],
        )
        assert [(row["id"], row["status"], row["parent_job_id"]) for row in rows] == [
            (root_id, "queued", None),
            (child_id, "queued", root_id),
        ]
    finally:
        for task in (retry, cleanup):
            if task is not None:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        if transaction is not None:
            await transaction.rollback()
        await cleaner.execute(
            "DELETE FROM pgqueuer_jobs WHERE id = ANY($1::bigint[])",
            [child_id, root_id],
        )
        await blocker.close()
        await retry_conn.close()
        await cleaner.close()
        await observer.close()


@pytest.mark.asyncio
async def test_retention_advisory_lock_excludes_a_second_worker(test_engine) -> None:
    leader = await _connect(test_engine)
    follower = await _connect(test_engine)
    try:
        await leader.fetchval(
            "SELECT pg_advisory_lock($1::bigint)",
            worker._RETENTION_MAINTENANCE_ADVISORY_LOCK,
        )

        ran = await worker._run_retention_maintenance_tick(
            follower,
            retention_settings=SimpleNamespace(
                job_retention_days=30,
                failed_job_retention_days=90,
                job_retention_batch_size=100,
            ),
        )

        assert ran is False
    finally:
        await leader.execute(
            "SELECT pg_advisory_unlock($1::bigint)",
            worker._RETENTION_MAINTENANCE_ADVISORY_LOCK,
        )
        await leader.close()
        await follower.close()
