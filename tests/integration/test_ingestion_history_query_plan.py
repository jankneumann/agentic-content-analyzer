"""PostgreSQL integration query-plan guard for compact ingestion history."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from typing import Any
from unittest.mock import AsyncMock

import asyncpg
import pytest

from src.services.operation_service import OperationService

_PLAN_ROW_COUNT = 10_000
_MAX_SELECTIVE_ROWS_SCANNED = 128
_CURSOR_SIGNING_KEY = "history-cursor-signing-key-for-plan-tests"
_FIXTURE_MARKER = "ri07-history-plan"

pytestmark = pytest.mark.integration


def _plan_nodes(plan: dict[str, Any]) -> Iterable[dict[str, Any]]:
    yield plan
    for child in plan.get("Plans", []):
        yield from _plan_nodes(child)


def _history_scan_evidence(plan: dict[str, Any]) -> tuple[int, set[str]]:
    rows_scanned = 0
    index_names: set[str] = set()
    for node in _plan_nodes(plan):
        index_name = node.get("Index Name")
        if isinstance(index_name, str):
            index_names.add(index_name)
        if node.get("Relation Name") != "pgqueuer_jobs":
            continue
        loops = int(node.get("Actual Loops", 1))
        rows_scanned += loops * (
            int(node.get("Actual Rows", 0))
            + int(node.get("Rows Removed by Filter", 0))
            + int(node.get("Rows Removed by Index Recheck", 0))
        )
    return rows_scanned, index_names


def _plan_summary(plan: dict[str, Any]) -> str:
    summary = []
    for node in _plan_nodes(plan):
        if node.get("Relation Name") == "pgqueuer_jobs" or node.get("Node Type") == "Sort":
            summary.append(
                {
                    "node": node.get("Node Type"),
                    "index": node.get("Index Name"),
                    "actual_rows": node.get("Actual Rows"),
                    "loops": node.get("Actual Loops"),
                    "removed": node.get("Rows Removed by Filter", 0),
                }
            )
    return json.dumps(summary, sort_keys=True)


async def _history_query_and_args(**filters: object) -> tuple[str, tuple[object, ...]]:
    connection = AsyncMock()
    connection.fetch.return_value = []
    await OperationService(
        connection=connection,
        cursor_signing_key=_CURSOR_SIGNING_KEY,
    ).list_ingestion_history(limit=50, **filters)
    query, *args = connection.fetch.await_args.args
    return query, tuple(args)


async def _explain_history(
    connection: asyncpg.Connection,
    **filters: object,
) -> dict[str, Any]:
    query, args = await _history_query_and_args(**filters)
    raw_plan = await connection.fetchval(
        f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}",
        *args,
    )
    document = json.loads(raw_plan) if isinstance(raw_plan, str) else raw_plan
    return document[0]["Plan"]


@pytest.mark.asyncio
async def test_ingestion_history_query_plans_bound_selective_scans(test_engine) -> None:
    """Representative history queries use indexes instead of scanning retention."""

    dsn = test_engine.url.render_as_string(hide_password=False)
    connection = await asyncpg.connect(dsn)
    parent_operation_id: int | None = None
    try:
        parent_operation_id = await connection.fetchval(
            """
            INSERT INTO pgqueuer_jobs (
                entrypoint, payload, status, completed_at
            ) VALUES (
                'pipeline.run',
                jsonb_build_object('plan_fixture', $1::text),
                'completed',
                NOW()
            )
            RETURNING id
            """,
            _FIXTURE_MARKER,
        )
        await connection.execute(
            """
            INSERT INTO pgqueuer_jobs (
                entrypoint, payload, status, parent_job_id, created_at, completed_at
            )
            SELECT
                'ingestion.execute',
                jsonb_build_object(
                    'schema_version', 2,
                    'operation_type', 'ingestion.execute',
                    'plan_fixture', $1::text,
                    'input', jsonb_build_object(
                        'kind', CASE
                            WHEN generated_id % 2000 = 0 THEN 'x_search'
                            ELSE 'rss'
                        END
                    ),
                    'result', jsonb_build_object(
                        'schema_version', 2,
                        'command_key', CASE
                            WHEN generated_id % 2000 = 0 THEN 'x_search'
                            ELSE 'rss'
                        END,
                        'outcome', CASE
                            WHEN generated_id % 2500 = 0 THEN 'partial'
                            ELSE 'success'
                        END,
                        'items_ingested', 1,
                        'items_skipped', 0,
                        'items_failed', CASE
                            WHEN generated_id % 2500 = 0 THEN 1
                            ELSE 0
                        END,
                        'source_outcomes', jsonb_build_array(
                            jsonb_build_object(
                                'source_key', 'src_' || substr(md5(generated_id::text), 1, 20),
                                'status', CASE
                                    WHEN generated_id % 2500 = 0 THEN 'partial'
                                    ELSE 'ok'
                                END,
                                'items_ingested', 1,
                                'items_failed', CASE
                                    WHEN generated_id % 2500 = 0 THEN 1
                                    ELSE 0
                                END,
                                'errors', jsonb_build_array(),
                                'warnings', jsonb_build_array()
                            )
                        )
                    )
                ),
                CASE
                    WHEN generated_id % 29 = 0 THEN 'failed'
                    WHEN generated_id % 31 = 0 THEN 'cancelled'
                    ELSE 'completed'
                END,
                CASE
                    WHEN generated_id % 2000 = 0 THEN $2::bigint
                    ELSE NULL
                END,
                NOW() - generated_id * INTERVAL '1 second',
                NOW() - generated_id * INTERVAL '1 second'
            FROM generate_series(1, $3::integer) AS generated_id
            """,
            _FIXTURE_MARKER,
            parent_operation_id,
            _PLAN_ROW_COUNT,
        )
        source_key = "src_" + hashlib.md5(b"7777", usedforsecurity=False).hexdigest()[:20]
        await connection.execute(
            """
            INSERT INTO pgqueuer_jobs (
                entrypoint, payload, status, created_at, completed_at
            )
            SELECT
                'ingestion.execute',
                jsonb_build_object(
                    'schema_version', 2,
                    'operation_type', 'ingestion.execute',
                    'plan_fixture', $1::text,
                    'input', jsonb_build_object('kind', 'rss'),
                    'result', jsonb_build_object(
                        'schema_version', 2,
                        'command_key', 'rss',
                        'outcome', 'success',
                        'items_ingested', 1,
                        'items_skipped', 0,
                        'items_failed', 0,
                        'source_outcomes', (
                            SELECT jsonb_agg(
                                jsonb_build_object(
                                    'source_key', CASE
                                        WHEN source_ordinality = 101 THEN $2::text
                                        ELSE 'src_' || substr(
                                            md5(('outside_' || source_ordinality)::text),
                                            1,
                                            20
                                        )
                                    END,
                                    'status', 'ok',
                                    'items_ingested', 1,
                                    'items_failed', 0,
                                    'errors', jsonb_build_array(),
                                    'warnings', jsonb_build_array()
                                )
                                ORDER BY source_ordinality
                            )
                            FROM generate_series(1, 101) AS source_ordinality
                        )
                    )
                ),
                'completed',
                NOW() - INTERVAL '3 hours',
                NOW() - INTERVAL '3 hours'
            """,
            _FIXTURE_MARKER,
            source_key,
        )
        await connection.execute("ANALYZE pgqueuer_jobs")
        await connection.execute("SET max_parallel_workers_per_gather = 0")

        fixture_count = await connection.fetchval(
            "SELECT COUNT(*) FROM pgqueuer_jobs WHERE payload->>'plan_fixture' = $1",
            _FIXTURE_MARKER,
        )
        assert fixture_count >= _PLAN_ROW_COUNT

        source_page = await OperationService(
            connection=connection,
            cursor_signing_key=_CURSOR_SIGNING_KEY,
        ).list_ingestion_history(configured_source_key=source_key)
        assert len(source_page.data) == 1
        assert source_page.data[0].source_outcomes[0].source_key == source_key

        history_queries = {
            "ordered": {},
            "command": {"command_key": "x_search"},
            "configured_source": {"configured_source_key": source_key},
            "outcome": {"outcome": "partial"},
            "parent": {"parent_operation_id": str(parent_operation_id)},
        }
        evidence: dict[str, tuple[int, set[str], dict[str, Any]]] = {}
        for name, filters in history_queries.items():
            plan = await _explain_history(connection, **filters)
            rows_scanned, index_names = _history_scan_evidence(plan)
            evidence[name] = (rows_scanned, index_names, plan)

        failures = []
        ordered_rows, ordered_indexes, ordered_plan = evidence["ordered"]
        if any(node.get("Node Type") == "Sort" for node in _plan_nodes(ordered_plan)):
            failures.append(f"ordered requires Sort: {_plan_summary(ordered_plan)}")
        if not ordered_indexes:
            failures.append(f"ordered has no index: {_plan_summary(ordered_plan)}")
        if ordered_rows > _MAX_SELECTIVE_ROWS_SCANNED:
            failures.append(f"ordered scanned {ordered_rows} rows: {_plan_summary(ordered_plan)}")
        for name, (rows_scanned, index_names, plan) in evidence.items():
            if name == "ordered":
                continue
            if not index_names:
                failures.append(f"{name} has no index: {_plan_summary(plan)}")
            if rows_scanned > _MAX_SELECTIVE_ROWS_SCANNED:
                failures.append(f"{name} scanned {rows_scanned} rows: {_plan_summary(plan)}")
        assert not failures, "\n".join(failures)
    finally:
        await connection.execute(
            "DELETE FROM pgqueuer_jobs WHERE payload->>'plan_fixture' = $1",
            _FIXTURE_MARKER,
        )
        if parent_operation_id is not None:
            await connection.execute(
                "DELETE FROM pgqueuer_jobs WHERE id = $1",
                parent_operation_id,
            )
        await connection.close()
