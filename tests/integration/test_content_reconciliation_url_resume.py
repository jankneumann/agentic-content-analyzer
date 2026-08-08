"""End-to-end PostgreSQL regression for canonical URL retry recovery."""

from __future__ import annotations

import json
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import asyncpg
import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from src.contracts.workflow_models import IngestionResultV2
from src.models.jobs import OperationPayloadV2, OperationType
from src.queue.execution_claim import ExecutionClaim, bind_execution_claim
from src.queue.workflow_handlers import build_workflow_handler_registry
from src.services.operation_service import OperationService
from src.services.url_extractor import URLExtractor

pytestmark = pytest.mark.integration

_BASE_ID = 9_850_000
_RETRY_CEILING = 3


def _checkpoint(content_id: int) -> dict:
    return IngestionResultV2(
        command_key="url",
        resolved_route="webpage",
        emitted_sources=["url"],
        status="partial",
        outcome="partial",
        items_ingested=1,
        items_skipped=0,
        items_failed=0,
        content_ids=[content_id],
        errors=[{"code": "extraction_failed", "message": "URL extraction failed"}],
        warnings=[],
        errors_omitted=0,
        warnings_omitted=0,
        source_outcomes=[],
        source_outcomes_omitted=0,
        details={},
        details_omitted=0,
    ).model_dump(mode="json")


async def _insert_failed_url_owner(
    conn: asyncpg.Connection,
    *,
    operation_id: int,
    content_id: int,
    with_checkpoint: bool,
) -> tuple[str, dict]:
    source_url = f"https://example.com/reconciliation-resume-{content_id}"
    command = {
        "kind": "url",
        "url": source_url,
        "routing_mode": "webpage",
    }
    payload = OperationPayloadV2(
        operation_type=OperationType.INGESTION_EXECUTE,
        input=command,
        progress=10,
        message="URL extraction failed",
        result=_checkpoint(content_id) if with_checkpoint else None,
    ).model_dump(mode="json")
    await conn.execute(
        """
        INSERT INTO pgqueuer_jobs (
            id, entrypoint, payload, status, error, retry_count,
            heartbeat_at, claim_generation, claim_protocol_version, completed_at
        ) VALUES (
            $1, 'ingestion.execute', $2::jsonb, 'failed',
            'URL extraction failed and is resumable', 0,
            NOW(), 1, 2, NOW()
        )
        """,
        operation_id,
        json.dumps(payload),
    )
    await conn.execute(
        """
        INSERT INTO contents (
            id, source_type, source_id, source_url, title, markdown_content,
            content_hash, status, error_message, status_operation_id,
            status_claim_generation, status_operation_phase, status_owner_version
        ) VALUES (
            $1, 'webpage', $2, $3, $3, '# extraction failed', $2,
            'failed', 'Content extraction failed. Please try again later.',
            $4, 1, 'parsing', 2
        )
        """,
        content_id,
        f"url-resume-{content_id}",
        source_url,
        operation_id,
    )
    return source_url, command


async def _claim_retry(conn: asyncpg.Connection, operation_id: int) -> int:
    row = await conn.fetchrow(
        """
        UPDATE pgqueuer_jobs
        SET status = 'in_progress', claim_protocol_version = 2,
            started_at = NOW(), heartbeat_at = NOW()
        WHERE id = $1 AND status = 'queued'
        RETURNING claim_generation, claim_protocol_version
        """,
        operation_id,
    )
    assert row is not None
    assert row["claim_protocol_version"] == 2
    return int(row["claim_generation"])


@pytest.mark.asyncio
@pytest.mark.parametrize("with_checkpoint", [True, False], ids=["checkpoint", "owner-fallback"])
async def test_canonical_url_retry_resumes_exact_owned_content(
    test_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    with_checkpoint: bool,
) -> None:
    """Retry consumes either strict checkpoint evidence or one exact persisted owner."""

    offset = 0 if with_checkpoint else 1
    operation_id = _BASE_ID + offset
    content_id = _BASE_ID + 100 + offset
    conn = await asyncpg.connect(test_engine.url.render_as_string(hide_password=False))
    try:
        source_url, command = await _insert_failed_url_owner(
            conn,
            operation_id=operation_id,
            content_id=content_id,
            with_checkpoint=with_checkpoint,
        )
        operations = OperationService(connection=conn)

        retried = await operations.retry(operation_id)
        assert retried.status.value == "queued"
        assert retried.retry_count == 1
        assert retried.retry_count < _RETRY_CEILING
        if with_checkpoint:
            assert retried.result == _checkpoint(content_id)
        else:
            assert retried.result is None

        claim_generation = await _claim_retry(conn, operation_id)
        assert claim_generation == 2

        SessionLocal = sessionmaker(bind=test_engine, expire_on_commit=False)

        @contextmanager
        def test_database_session():
            with SessionLocal() as session:
                try:
                    yield session
                    session.commit()
                except Exception:
                    session.rollback()
                    raise

        monkeypatch.setattr("src.storage.database.get_db", test_database_session)
        monkeypatch.setattr(
            URLExtractor,
            "_fetch_url",
            AsyncMock(return_value=("<html><title>Recovered</title></html>", source_url)),
        )
        monkeypatch.setattr(
            URLExtractor,
            "_parse_html",
            AsyncMock(return_value=("# Recovered\n\nExact URL content.", {"title": "Recovered"})),
        )
        aggregate_ingestion = Mock(
            side_effect=AssertionError(
                "retry must bypass classification and aggregate deduplication"
            )
        )
        registry = build_workflow_handler_registry(
            operation_service=operations,
            ingestion_service=SimpleNamespace(execute=aggregate_ingestion),
        )

        with bind_execution_claim(
            ExecutionClaim(
                job_id=operation_id,
                claim_generation=claim_generation,
                claim_protocol_version=2,
            )
        ):
            await registry.dispatch(OperationType.INGESTION_EXECUTE, operation_id, command)

        aggregate_ingestion.assert_not_called()
        row = await conn.fetchrow(
            """
            SELECT status, error_message, markdown_content,
                   status_operation_id, status_claim_generation,
                   status_operation_phase, status_owner_version
            FROM contents
            WHERE id = $1
            """,
            content_id,
        )
        assert row is not None
        assert row["status"] == "parsed"
        assert row["error_message"] is None
        assert row["markdown_content"] == "# Recovered\n\nExact URL content."
        assert row["status_operation_id"] is None
        assert row["status_claim_generation"] is None
        assert row["status_operation_phase"] is None
        assert row["status_owner_version"] is None

        final = await operations.get(operation_id)
        assert final.result is not None
        assert final.result["status"] == "ok"
        assert final.result["outcome"] == "success"
        assert final.result["content_ids"] == [content_id]
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM contents WHERE source_url = $1",
                source_url,
            )
            == 1
        )
    finally:
        await conn.execute("DELETE FROM contents WHERE id = $1", content_id)
        await conn.execute("DELETE FROM pgqueuer_jobs WHERE id = $1", operation_id)
        await conn.close()
