"""Integration checks for retained workflow terminal evidence."""

from __future__ import annotations

import asyncio

import asyncpg
import pytest

from src.queue import setup as queue_setup

pytestmark = pytest.mark.integration


async def _connect(test_engine) -> asyncpg.Connection:
    return await asyncpg.connect(test_engine.url.render_as_string(hide_password=False))


@pytest.mark.asyncio
async def test_queue_bootstrap_is_postgresql_valid_and_idempotent(
    test_engine,
    monkeypatch,
) -> None:
    database_url = test_engine.url.render_as_string(hide_password=False)
    monkeypatch.setattr(queue_setup, "get_queue_connection_string", lambda: database_url)

    await queue_setup.init_queue_schema()
    await queue_setup.init_queue_schema()

    conn = await _connect(test_engine)
    try:
        trigger_counts = await conn.fetch(
            """
            SELECT tgname, COUNT(*) AS trigger_count
            FROM pg_trigger
            WHERE NOT tgisinternal
              AND tgname IN (
                'pgqueuer_jobs_capture_terminal_event',
                'content_reconciliation_actions_capture_terminal_event'
              )
            GROUP BY tgname
            ORDER BY tgname
            """
        )
        assert [(row["tgname"], row["trigger_count"]) for row in trigger_counts] == [
            ("content_reconciliation_actions_capture_terminal_event", 1),
            ("pgqueuer_jobs_capture_terminal_event", 1),
        ]
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_terminal_event_survives_graph_operation_cleanup(test_engine) -> None:
    conn = await _connect(test_engine)
    transaction = conn.transaction()
    await transaction.start()
    try:
        root_id = await conn.fetchval(
            """
            INSERT INTO pgqueuer_jobs (
                entrypoint, payload, status, completed_at
            ) VALUES (
                'pipeline.run', '{}'::jsonb, 'queued', NULL
            ) RETURNING id
            """
        )
        await conn.execute(
            """
            UPDATE pgqueuer_jobs
            SET status = 'completed', completed_at = NOW() - INTERVAL '31 days'
            WHERE id = $1
            """,
            root_id,
        )
        event_id = await conn.fetchval(
            "SELECT id FROM workflow_terminal_events WHERE operation_id = $1",
            root_id,
        )
        assert event_id is not None

        await conn.execute("DELETE FROM pgqueuer_jobs WHERE id = $1", root_id)
        retained = await conn.fetchrow(
            """
            SELECT operation_id, claim_generation, terminal_status
            FROM workflow_terminal_events WHERE id = $1
            """,
            event_id,
        )
        assert tuple(retained.values()) == (root_id, 0, "completed")
    finally:
        await transaction.rollback()
        await conn.close()


@pytest.mark.asyncio
async def test_concurrent_terminal_replay_cannot_duplicate_intent(test_engine) -> None:
    setup = await _connect(test_engine)
    job_id = await setup.fetchval(
        """
        INSERT INTO pgqueuer_jobs (entrypoint, payload, status)
        VALUES ('ingestion.execute', '{}'::jsonb, 'queued') RETURNING id
        """
    )
    await setup.close()

    first = await _connect(test_engine)
    second = await _connect(test_engine)
    try:
        first_result, second_result = await asyncio.gather(
            first.execute(
                """
                UPDATE pgqueuer_jobs SET status = 'cancelled', completed_at = NOW()
                WHERE id = $1 AND status = 'queued'
                """,
                job_id,
            ),
            second.execute(
                """
                UPDATE pgqueuer_jobs SET status = 'cancelled', completed_at = NOW()
                WHERE id = $1 AND status = 'queued'
                """,
                job_id,
            ),
        )
        assert sorted([first_result, second_result]) == ["UPDATE 0", "UPDATE 1"]
        count = await first.fetchval(
            "SELECT COUNT(*) FROM workflow_terminal_events WHERE operation_id = $1",
            job_id,
        )
        assert count == 1
    finally:
        await first.execute("DELETE FROM pgqueuer_jobs WHERE id = $1", job_id)
        await second.close()
        await first.close()
