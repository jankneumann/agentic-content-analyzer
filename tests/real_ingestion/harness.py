"""Harness that drives fixture ingestion through the canonical durable workflow.

Unlike ``tests/fixtures/sources/harness.py`` (which calls ``IngestionService``
directly inside a single rolled-back transaction), this harness exercises the
*real* submission path RI-05 cares about:

    OperationService.submit  ->  pgqueuer_jobs (queued)
                             ->  worker claim (queued -> in_progress)
                             ->  worker._process_job -> ingestion handler
                             ->  IngestionService.execute (fixture orchestrator)
                             ->  committed Content rows
                             ->  OperationService result attached + job completed

Because the queue uses an ``asyncpg`` connection and the ORM writes go through a
separate SQLAlchemy session, the persisted rows MUST be committed for both sides
to see them — the rollback-per-test pattern would make a cross-connection tier
lie. Every row this harness writes is therefore committed and cleaned up
explicitly in :meth:`cleanup`.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import asyncpg
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from src.ingestion.commands import IngestCommandBase
from src.ingestion.content_references import record_content_reference
from src.ingestion.registry import SOURCE_REGISTRY, SourceDescriptor, SourceRegistry
from src.ingestion.result import IngestionResponse
from src.models.jobs import OperationType
from src.queue import worker
from src.queue.workflow_handlers import build_workflow_handler_registry
from src.services.operation_service import OperationService
from tests.factories.content import ContentFactory
from tests.factories.summary import SummaryFactory
from tests.fixtures.sources.library import SOURCE_FIXTURES, SourceFixture

# Deterministic instant so ordering/timestamps never depend on wall clock.
PERIOD_START = datetime(2026, 7, 1, tzinfo=UTC)

# The curated pull-request tier: representative typed sources spanning email,
# feeds, direct URLs, video, academic search, and blogs. Keys index
# ``SOURCE_FIXTURES``; the spec names the last two with hyphens.
PR_TIER_KEYS: tuple[str, ...] = (
    "rss",
    "gmail",
    "url",
    "youtube_playlist",
    "arxiv_search",
    "blog",
)


@dataclass(frozen=True)
class RealIngestOutcome:
    """The durable operation and the database delta it actually produced."""

    key: str
    operation_id: str
    status: str
    result: dict[str, Any] | None
    #: Content IDs the durable result *claims* to have persisted.
    claimed_content_ids: tuple[int, ...]
    #: Content rows this submission actually committed (queried fresh).
    content_row_delta: int
    #: Whether the durable job reached a successful terminal state.
    succeeded: bool


def _asyncpg_dsn(engine: Engine) -> str:
    """Render an asyncpg-compatible DSN, stripping any SQLAlchemy ``+driver``."""

    raw = engine.url.render_as_string(hide_password=False)
    scheme, _, rest = raw.partition("://")
    base_scheme = scheme.split("+", 1)[0]
    return f"{base_scheme}://{rest}"


class RealIngestionHarness:
    """Submit fixture commands through the canonical workflow against a real DB."""

    def __init__(self, engine: Engine, conn: asyncpg.Connection, token: str) -> None:
        self._engine = engine
        self._conn = conn
        self._token = token
        self._sessionmaker = sessionmaker(bind=engine)
        self._created_content_ids: list[int] = []
        self._job_ids: list[int] = []

    async def submit_pr_source(self, key: str) -> RealIngestOutcome:
        """Submit one PR-tier fixture command and drive it to a terminal state."""

        fixture = SOURCE_FIXTURES[key]
        source_registry = self._fixture_registry(key, fixture)
        operations = OperationService(connection=self._conn)

        handle = await operations.submit(OperationType.INGESTION_EXECUTE, dict(fixture.command))
        operation_id = int(handle.operation_id)
        self._job_ids.append(operation_id)

        registry = build_workflow_handler_registry(
            operation_service=operations,
            source_registry=source_registry,
        )
        entrypoint = OperationType.INGESTION_EXECUTE.value
        worker_handler = registry.worker_handler(OperationType.INGESTION_EXECUTE)

        before = len(self._created_content_ids)
        original = worker._handlers.get(entrypoint)
        worker._handlers[entrypoint] = worker_handler
        try:
            with (
                patch("src.queue.setup.touch_job_heartbeat", AsyncMock()),
                patch.object(worker, "_emit_job_notification", AsyncMock()),
            ):
                job = await self._claim(operation_id)
                await worker._process_job(self._conn, job)
        finally:
            if original is None:
                worker._handlers.pop(entrypoint, None)
            else:
                worker._handlers[entrypoint] = original

        terminal = await operations.get(operation_id)
        result = terminal.result if isinstance(terminal.result, dict) else None
        claimed = tuple(result.get("content_ids", [])) if result else ()
        delta = self._content_delta(key)
        claimed_from_run = tuple(self._created_content_ids[before:])
        return RealIngestOutcome(
            key=key,
            operation_id=str(operation_id),
            status=terminal.status.value,
            result=result,
            claimed_content_ids=claimed or claimed_from_run,
            content_row_delta=delta,
            succeeded=terminal.status.value == "completed",
        )

    def _fixture_registry(self, key: str, fixture: SourceFixture) -> SourceRegistry:
        """Build a single-source registry whose orchestrator commits deterministically."""

        command = SOURCE_REGISTRY.parse_command(fixture.command)
        descriptor = SOURCE_REGISTRY.get(command.kind)

        def orchestrator(typed_command: IngestCommandBase) -> IngestionResponse:
            return self._persist(key, fixture, typed_command, descriptor)

        return SourceRegistry([replace(descriptor, orchestrator=orchestrator)])

    def _persist(
        self,
        key: str,
        fixture: SourceFixture,
        typed_command: IngestCommandBase,
        descriptor: SourceDescriptor,
    ) -> IngestionResponse:
        """Commit exactly one Content+Summary to the test database (worker thread)."""

        sources = descriptor.resolve_sources(typed_command)
        if len(sources) != 1:
            raise AssertionError(
                f"PR-tier fixture '{key}' did not resolve to exactly one content source"
            )
        source = next(iter(sources))
        index = len(self._created_content_ids) + 1

        session = self._sessionmaker()
        ContentFactory._meta.sqlalchemy_session = session  # type: ignore[attr-defined]
        SummaryFactory._meta.sqlalchemy_session = session  # type: ignore[attr-defined]
        try:
            content = ContentFactory(
                source_type=source,
                source_id=f"real-ingest:{self._token}:{key}:{index}",
                source_url=f"https://fixtures.test/{key}/{index}",
                title=fixture.title,
                publication=f"Fixture {key}",
                published_date=PERIOD_START + timedelta(minutes=index),
                ingested_at=PERIOD_START + timedelta(minutes=index),
                markdown_content=f"# {fixture.title}\n\nDeterministic content for {key}.",
            )
            SummaryFactory(
                content=content,
                content_id=content.id,
                executive_summary=f"Persisted summary for {key}",
            )
            record_content_reference(content.id, content.canonical_id)
            content_id = content.id
        finally:
            ContentFactory._meta.sqlalchemy_session = None  # type: ignore[attr-defined]
            SummaryFactory._meta.sqlalchemy_session = None  # type: ignore[attr-defined]
            session.close()

        self._created_content_ids.append(content_id)
        return IngestionResponse(
            command=fixture.response_command,
            source=fixture.response_source,
            status="ok",
            items_ingested=1,
            details={"content_id": content_id, "results": [{"content_id": content_id}]},
        )

    async def recount(self, outcome: RealIngestOutcome) -> RealIngestOutcome:
        """Re-read the DB delta for an outcome (its claim is unchanged)."""

        delta = self._content_delta(outcome.key)
        return replace(outcome, content_row_delta=delta)

    async def _claim(self, operation_id: int) -> dict[str, Any]:
        """Transition our queued job to in_progress, as the worker poller would."""

        row = await self._conn.fetchrow(
            """
            UPDATE pgqueuer_jobs
            SET status = 'in_progress',
                started_at = COALESCE(started_at, NOW()),
                heartbeat_at = NOW()
            WHERE id = $1 AND status = 'queued'
            RETURNING id, entrypoint, payload
            """,
            operation_id,
        )
        if row is None:
            raise AssertionError(f"Operation {operation_id} was not claimable from 'queued'")
        return dict(row)

    def _content_delta(self, key: str) -> int:
        """Count committed Content rows this harness wrote for ``key`` (fresh read)."""

        with self._sessionmaker() as session:
            return int(
                session.execute(
                    text("SELECT count(*) FROM contents WHERE source_id LIKE :prefix"),
                    {"prefix": f"real-ingest:{self._token}:{key}:%"},
                ).scalar_one()
            )

    async def cleanup(self) -> None:
        """Delete every committed row and durable job this harness created."""

        if self._created_content_ids:
            ids = self._created_content_ids
            with self._sessionmaker() as session:
                # Delete summaries explicitly; content_references FKs to
                # contents.id are ON DELETE CASCADE / SET NULL, so removing the
                # contents rows tidies any references automatically.
                session.execute(
                    text("DELETE FROM summaries WHERE content_id = ANY(:ids)"),
                    {"ids": ids},
                )
                session.execute(
                    text("DELETE FROM contents WHERE id = ANY(:ids)"),
                    {"ids": ids},
                )
                session.commit()
        if self._job_ids:
            await self._conn.execute(
                "DELETE FROM pgqueuer_jobs WHERE id = ANY($1::bigint[])",
                self._job_ids,
            )


def assert_result_matches_delta(outcome: RealIngestOutcome) -> None:
    """DB-delta assertion helper reused by every tier test (task 1.3).

    A terminal operation is only trustworthy if the count it *claims* matches the
    rows the database actually holds — the "claims results the database did not
    persist" failure must surface here as a persistence mismatch, not pass
    silently.
    """

    assert outcome.succeeded, (
        f"Operation {outcome.operation_id} for '{outcome.key}' did not complete: "
        f"status={outcome.status}"
    )
    # Primary persistence invariant: the count the durable result *claims* must
    # equal the rows the database actually holds. A completed operation that
    # claims more than it persisted is the persistence failure the spec targets.
    assert len(outcome.claimed_content_ids) == outcome.content_row_delta, (
        f"Operation for '{outcome.key}' claimed {len(outcome.claimed_content_ids)} "
        f"content rows but the database delta was {outcome.content_row_delta}"
    )
    # Secondary guard: a successful fixture ingestion must persist something,
    # catching the silent claims=0/delta=0 no-op that equality alone would pass.
    assert outcome.content_row_delta >= 1, f"Fixture '{outcome.key}' persisted no Content rows"
