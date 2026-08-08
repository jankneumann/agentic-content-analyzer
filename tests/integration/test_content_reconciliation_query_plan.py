"""Measured PostgreSQL plan guard for bounded Content reconciliation scans."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any
from unittest.mock import AsyncMock

import asyncpg
import pytest

from src.services.content_reconciliation_service import ContentReconciliationService

pytestmark = pytest.mark.integration

_BASE_ID = 9_800_000
_IRRELEVANT_ROWS = 10_001
_MAX_CONTENT_ROWS_SCANNED = 128
_EXISTING_STATUS_INDEX = "ix_contents_status"


def _plan_nodes(plan: dict[str, Any]) -> Iterable[dict[str, Any]]:
    yield plan
    for child in plan.get("Plans", []):
        yield from _plan_nodes(child)


def _content_scan_evidence(plan: dict[str, Any]) -> tuple[int, set[str]]:
    rows_scanned = 0
    indexes: set[str] = set()
    for node in _plan_nodes(plan):
        index_name = node.get("Index Name")
        if isinstance(index_name, str):
            indexes.add(index_name)
        if node.get("Relation Name") != "contents":
            continue
        loops = int(node.get("Actual Loops", 1))
        rows_scanned += loops * (
            int(node.get("Actual Rows", 0))
            + int(node.get("Rows Removed by Filter", 0))
            + int(node.get("Rows Removed by Index Recheck", 0))
        )
    return rows_scanned, indexes


async def _candidate_query() -> tuple[str, tuple[object, ...]]:
    connection = AsyncMock()
    connection.fetch.return_value = []
    service = ContentReconciliationService(
        connection=connection,
        stale_seconds=3600,
        max_retries=3,
        batch_size=50,
        lock_timeout_ms=250,
        statement_timeout_ms=5000,
        apply_enabled=False,
    )
    await service._scan(after_content_id=_BASE_ID - 1, limit=1)
    query, *args = connection.fetch.await_args.args
    return query, tuple(args)


@pytest.mark.asyncio
async def test_candidate_scan_uses_bounded_existing_index(test_engine) -> None:
    connection = await asyncpg.connect(test_engine.url.render_as_string(hide_password=False))
    transaction = connection.transaction()
    await transaction.start()
    try:
        await connection.execute(
            """
            INSERT INTO contents (
                id, source_type, source_id, title, markdown_content,
                content_hash, status
            )
            SELECT
                $1 + generated_id,
                'manual',
                'reconciliation-plan-' || generated_id,
                'irrelevant',
                '# irrelevant',
                md5(generated_id::text),
                'pending'
            FROM generate_series(0, $2 - 1) AS generated_id
            """,
            _BASE_ID,
            _IRRELEVANT_ROWS,
        )
        operation_id = _BASE_ID + _IRRELEVANT_ROWS + 100
        candidate_id = _BASE_ID + _IRRELEVANT_ROWS
        await connection.execute(
            """
            INSERT INTO pgqueuer_jobs (
                id, entrypoint, payload, status, retry_count,
                claim_generation, claim_protocol_version
            ) VALUES (
                $1, 'summarization.run',
                '{"schema_version":2,"operation_type":"summarization.run",'
                    '"input":{},"cancel_requested":false}'::jsonb,
                'failed', 0, 1, 2
            )
            """,
            operation_id,
        )
        await connection.execute(
            """
            INSERT INTO contents (
                id, source_type, source_id, title, markdown_content,
                content_hash, status, status_operation_id,
                status_claim_generation, status_operation_phase, status_owner_version
            ) VALUES (
                $1, 'manual', 'reconciliation-plan-candidate', 'candidate',
                '# candidate', 'candidate', 'failed', $2, 1, 'processing', 1
            )
            """,
            candidate_id,
            operation_id,
        )
        await connection.execute("ANALYZE contents")

        query, args = await _candidate_query()
        raw_plan = await connection.fetchval(
            f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}",
            *args,
        )
        document = json.loads(raw_plan) if isinstance(raw_plan, str) else raw_plan
        rows_scanned, indexes = _content_scan_evidence(document[0]["Plan"])

        assert _EXISTING_STATUS_INDEX in indexes, (rows_scanned, indexes, document)
        assert rows_scanned <= _MAX_CONTENT_ROWS_SCANNED, (
            rows_scanned,
            indexes,
            document,
        )
    finally:
        await transaction.rollback()
        await connection.close()
