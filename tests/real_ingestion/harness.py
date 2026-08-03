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

import socket
from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, patch

import asyncpg
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from src.config.sources import (
    ObsidianVaultSource,
    SourcesConfig,
    configured_source_public_key,
)
from src.ingestion.commands import IngestCommandBase
from src.ingestion.content_references import record_content_reference
from src.ingestion.real_ingest_evidence import (
    SourceEvidence,
    classify_source_outcome,
)
from src.ingestion.real_ingest_policy import LIVE_ADAPTER_POLICIES
from src.ingestion.registry import (
    SOURCE_REGISTRY,
    SourceDescriptor,
    SourceRegistry,
    configured_source_digest,
    configured_source_version,
)
from src.ingestion.result import IngestionResponse
from src.ingestion.service import IngestionService
from src.models.content import Content, ContentSource
from src.models.jobs import OperationType
from src.queue import worker
from src.queue.workflow_handlers import build_workflow_handler_registry
from src.services.operation_service import OperationService
from src.services.upload_service import MaterializedUpload
from tests.factories.content import ContentFactory
from tests.factories.summary import SummaryFactory
from tests.fixtures.sources.library import SOURCE_FIXTURES, SourceFixture
from tests.fixtures.sources.obsidian import (
    TemporaryObsidianVault,
    create_temporary_obsidian_vault,
)

# Deterministic instant so ordering/timestamps never depend on wall clock.
PERIOD_START = datetime(2026, 7, 1, tzinfo=UTC)


def reject_external_fixture_network(
    connect: Callable[[socket.socket, Any], Any],
    sock: socket.socket,
    address: Any,
) -> Any:
    """Permit local database sockets while prohibiting fixture egress."""

    if isinstance(address, tuple):
        host = str(address[0]).lower()
        if host not in {"localhost", "127.0.0.1", "::1"}:
            raise AssertionError("Obsidian fixture attempted external network access")
    return connect(sock, address)


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
    "obsidian_vault",
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
    #: Content IDs independently observed in the database for this submission.
    persisted_content_ids: tuple[int, ...] = ()
    #: The operation's failure diagnostic, if it terminated in failure.
    problem_detail: str | None = None
    #: Private Obsidian state rows added by this submission.
    source_state_row_delta: int = 0
    #: Immutable Obsidian file-version events added by this submission.
    source_event_row_delta: int = 0
    source_state_status_delta: dict[str, int] = field(default_factory=dict)
    source_event_status_delta: dict[str, int] = field(default_factory=dict)
    source_state_attempt_delta: int = 0
    source_event_attempt_delta: int = 0


@dataclass(frozen=True)
class _ObsidianPrivateSnapshot:
    state_statuses: dict[str, int]
    event_statuses: dict[str, int]
    state_attempts: int
    event_attempts: int


def _counter_delta(before: dict[str, int], after: dict[str, int]) -> dict[str, int]:
    return {
        key: after.get(key, 0) - before.get(key, 0)
        for key in before.keys() | after.keys()
        if after.get(key, 0) != before.get(key, 0)
    }


def _outcome(
    key: str,
    operation_id: int,
    terminal: Any,
    result: dict[str, Any] | None,
    claimed_content_ids: tuple[int, ...],
    content_delta: int,
    source_state_delta: int = 0,
    source_event_delta: int = 0,
    source_state_status_delta: dict[str, int] | None = None,
    source_event_status_delta: dict[str, int] | None = None,
    source_state_attempt_delta: int = 0,
    source_event_attempt_delta: int = 0,
    persisted_content_ids: tuple[int, ...] = (),
) -> RealIngestOutcome:
    """Assemble a RealIngestOutcome from a terminal operation handle."""

    problem_detail = terminal.problem.detail if terminal.problem else None
    return RealIngestOutcome(
        key=key,
        operation_id=str(operation_id),
        status=terminal.status.value,
        result=result,
        claimed_content_ids=claimed_content_ids,
        content_row_delta=content_delta,
        succeeded=terminal.status.value == "completed",
        persisted_content_ids=persisted_content_ids,
        problem_detail=problem_detail,
        source_state_row_delta=source_state_delta,
        source_event_row_delta=source_event_delta,
        source_state_status_delta=source_state_status_delta or {},
        source_event_status_delta=source_event_status_delta or {},
        source_state_attempt_delta=source_state_attempt_delta,
        source_event_attempt_delta=source_event_attempt_delta,
    )


def _fixture_response(fixture: SourceFixture, content_id: int) -> IngestionResponse:
    """The canonical single-item ingestion response for a committed fixture row."""

    return IngestionResponse(
        command=fixture.response_command,
        source=fixture.response_source,
        status="ok",
        items_ingested=1,
        details={"content_id": content_id, "results": [{"content_id": content_id}]},
    )


def _asyncpg_dsn(engine: Engine) -> str:
    """Render an asyncpg-compatible DSN, stripping any SQLAlchemy ``+driver``."""

    raw = engine.url.render_as_string(hide_password=False)
    scheme, _, rest = raw.partition("://")
    base_scheme = scheme.split("+", 1)[0]
    return f"{base_scheme}://{rest}"


class RealIngestionHarness:
    """Submit fixture commands through the canonical workflow against a real DB."""

    def __init__(
        self,
        engine: Engine,
        conn: asyncpg.Connection,
        token: str,
        workspace: Path,
    ) -> None:
        self._engine = engine
        self._conn = conn
        self._token = token
        self._workspace = workspace
        self._sessionmaker = sessionmaker(bind=engine)
        self._created_content_ids: list[int] = []
        self._job_ids: list[int] = []
        self._obsidian_vault: TemporaryObsidianVault | None = None
        self._obsidian_source_digest: str | None = None

    async def submit_fixture(self, key: str) -> RealIngestOutcome:
        """Submit one fixture command and drive its durable operation to terminal.

        Used by both tiers: the PR tier for its 6 representative sources and the
        scheduled tier (offline) for the full fixture-backed set.
        """

        fixture = SOURCE_FIXTURES[key]
        if key == "obsidian_vault":
            return await self._submit_obsidian_fixture(fixture)
        source_registry = self._fixture_registry(key, fixture)
        operations = OperationService(connection=self._conn)

        handle = await operations.submit(OperationType.INGESTION_EXECUTE, dict(fixture.command))
        operation_id = int(handle.operation_id)
        self._job_ids.append(operation_id)

        before = len(self._created_content_ids)
        await self._drive_job(
            operations, operation_id, source_registry, files_key=key if key == "files" else None
        )

        terminal = await operations.get(operation_id)
        result = terminal.result if isinstance(terminal.result, dict) else None
        delta = self._content_delta(key)
        if result is not None:
            # Trust the durable result's own claim, even an explicit empty one: a
            # completed operation that claims zero IDs while a row was persisted is
            # exactly the durable-result regression this tier exists to catch.
            # Substituting the harness's private creation log here would mask it and
            # let ``assert_result_matches_delta`` pass. Fall back to the run log only
            # when there is no result record at all (e.g. a failure before
            # ``attach_result`` ran), where the operation makes no claim to trust.
            claimed = tuple(result.get("content_ids", []))
        else:
            claimed = tuple(self._created_content_ids[before:])
        return _outcome(key, operation_id, terminal, result, claimed, delta)

    async def _submit_obsidian_fixture(self, fixture: SourceFixture) -> RealIngestOutcome:
        """Drive the real filesystem adapter against a bounded temporary vault."""

        vault, source, secret = self._obsidian_fixture_config()
        digest = configured_source_digest(source, secret=secret)
        source_key = configured_source_public_key(source, secret=secret)
        command = {
            **fixture.command,
            "source_key": source_key,
            "configured_source_version": configured_source_version(source, secret=secret),
        }
        descriptor = SOURCE_REGISTRY.get("obsidian_vault")
        source_registry = SourceRegistry([descriptor])
        ingestion_service = IngestionService(
            registry=source_registry,
            configured_source_key_secret=secret,
            source_config_loader=lambda: SourcesConfig(sources=[source]),
        )
        operations = OperationService(connection=self._conn)
        before_private = self._obsidian_private_snapshot(digest)
        before_content_ids = self._obsidian_content_ids(digest)

        handle = await operations.submit(OperationType.INGESTION_EXECUTE, command)
        operation_id = int(handle.operation_id)
        self._job_ids.append(operation_id)
        await self._drive_job(
            operations,
            operation_id,
            source_registry,
            ingestion_service=ingestion_service,
            obsidian_settings=SimpleNamespace(
                get_configured_source_key_secret=lambda: secret,
                get_obsidian_allowed_roots=lambda: (vault.approved_root,),
                obsidian_compatible_worker=True,
            ),
        )

        terminal = await operations.get(operation_id)
        result = terminal.result if isinstance(terminal.result, dict) else None
        claimed = tuple(result.get("content_ids", [])) if result else ()
        new_ids = sorted(self._obsidian_content_ids(digest) - before_content_ids)
        self._created_content_ids.extend(new_ids)
        after_private = self._obsidian_private_snapshot(digest)
        state_status_delta = _counter_delta(
            before_private.state_statuses,
            after_private.state_statuses,
        )
        event_status_delta = _counter_delta(
            before_private.event_statuses,
            after_private.event_statuses,
        )
        return _outcome(
            "obsidian_vault",
            operation_id,
            terminal,
            result,
            claimed,
            len(new_ids),
            sum(state_status_delta.values()),
            sum(event_status_delta.values()),
            state_status_delta,
            event_status_delta,
            after_private.state_attempts - before_private.state_attempts,
            after_private.event_attempts - before_private.event_attempts,
            tuple(new_ids),
        )

    def _obsidian_fixture_config(
        self,
    ) -> tuple[TemporaryObsidianVault, ObsidianVaultSource, str]:
        if self._obsidian_vault is None:
            self._obsidian_vault = create_temporary_obsidian_vault(self._workspace)
        config = self._obsidian_vault.source_config()
        config["vault_id"] = f"fixture-{self._token}"
        source = ObsidianVaultSource.model_validate(config)
        secret = "real-ingestion-obsidian-fixture-secret"
        self._obsidian_source_digest = configured_source_digest(source, secret=secret)
        return self._obsidian_vault, source, secret

    def change_obsidian_fixture(self) -> None:
        """Advance the mutable fixture note to its second file version."""

        if self._obsidian_vault is None:
            raise AssertionError("Obsidian fixture must be submitted before it can change")
        self._obsidian_vault.write_changed_version()

    def _obsidian_private_snapshot(self, digest: str) -> _ObsidianPrivateSnapshot:
        with self._sessionmaker() as session:
            state_rows = session.execute(
                text(
                    "SELECT status, count(*), coalesce(sum(attempt_count), 0) "
                    "FROM obsidian_ingest_state WHERE configured_source_digest = :digest "
                    "GROUP BY status"
                ),
                {"digest": digest},
            ).all()
            event_rows = session.execute(
                text(
                    "SELECT status, count(*), coalesce(sum(attempt_count), 0) "
                    "FROM obsidian_ingest_events WHERE configured_source_digest = :digest "
                    "GROUP BY status"
                ),
                {"digest": digest},
            ).all()
        return _ObsidianPrivateSnapshot(
            state_statuses={str(status): int(count) for status, count, _ in state_rows},
            event_statuses={str(status): int(count) for status, count, _ in event_rows},
            state_attempts=sum(int(attempts) for _, _, attempts in state_rows),
            event_attempts=sum(int(attempts) for _, _, attempts in event_rows),
        )

    def _obsidian_content_ids(self, digest: str) -> set[int]:
        """Snapshot digest-scoped persisted rows independently of result claims."""

        with self._sessionmaker() as session:
            rows = session.execute(
                text(
                    "SELECT DISTINCT content_id FROM obsidian_ingest_events "
                    "WHERE configured_source_digest = :digest AND content_id IS NOT NULL"
                ),
                {"digest": digest},
            ).scalars()
            return {int(content_id) for content_id in rows}

    async def submit_live(self, key: str) -> RealIngestOutcome:
        """Submit a source's real command through the *real* registry (live network).

        No fixture orchestrator is injected: the genuine adapter runs, persisting
        through the application's own database session. For coherent verification
        the live tier runs with ``DATABASE_URL`` pointed at the same database this
        harness reads (see the scheduled workflow), so the claimed content IDs can
        be counted back. The DB delta is derived from the claimed IDs (real feeds
        are non-deterministic, so an absolute count is not asserted).
        """

        fixture = SOURCE_FIXTURES[key]
        operations = OperationService(connection=self._conn)

        command = dict(fixture.command)
        if key == "obsidian_vault":
            from src.config.settings import get_settings

            settings = get_settings()
            sources = settings.get_sources_config().get_obsidian_vault_sources()
            ready_sources = [
                source
                for source in sources
                if SOURCE_REGISTRY.get(key).resolve_readiness(source).ready
            ]
            if len(ready_sources) != 1:
                raise AssertionError("Live Obsidian fixture requires exactly one ready source")
            source = ready_sources[0]
            secret = settings.get_configured_source_key_secret()
            command.update(
                source_key=configured_source_public_key(source, secret=secret),
                configured_source_version=configured_source_version(source, secret=secret),
            )

        handle = await operations.submit(OperationType.INGESTION_EXECUTE, command)
        operation_id = int(handle.operation_id)
        self._job_ids.append(operation_id)

        await self._drive_job(operations, operation_id, self._live_registry(key))

        terminal = await operations.get(operation_id)
        result = terminal.result if isinstance(terminal.result, dict) else None
        claimed = tuple(result.get("content_ids", [])) if result else ()
        # Record the live-created rows for cleanup and count how many persisted.
        self._created_content_ids.extend(int(cid) for cid in claimed)
        delta = self._content_delta_for_ids(claimed)
        return _outcome(key, operation_id, terminal, result, claimed, delta)

    async def _drive_job(
        self,
        operations: OperationService,
        operation_id: int,
        source_registry: SourceRegistry,
        *,
        files_key: str | None = None,
        ingestion_service: IngestionService | None = None,
        obsidian_settings: Any | None = None,
    ) -> None:
        """Claim and process one durable job to a terminal state, as the worker does."""

        registry = build_workflow_handler_registry(
            operation_service=operations,
            ingestion_service=ingestion_service,
            source_registry=source_registry,
        )
        entrypoint = OperationType.INGESTION_EXECUTE.value
        worker_handler = registry.worker_handler(OperationType.INGESTION_EXECUTE)

        original = worker._handlers.get(entrypoint)
        worker._handlers[entrypoint] = worker_handler  # type: ignore[assignment]
        try:
            with ExitStack() as stack:
                # Stub the queue side-channels (heartbeat pool + notifications).
                stack.enter_context(patch("src.queue.setup.touch_job_heartbeat", AsyncMock()))
                stack.enter_context(patch.object(worker, "_emit_job_notification", AsyncMock()))
                # The files source takes IngestionService's upload-materialization
                # branch instead of the descriptor orchestrator, so stub both seams
                # to commit deterministically without a real uploaded artifact.
                if files_key is not None:
                    self._enter_files_patches(stack, files_key, SOURCE_FIXTURES[files_key])
                if obsidian_settings is not None:
                    self._enter_obsidian_patches(stack, obsidian_settings)
                job = await self._claim(operation_id)
                await worker._process_job(self._conn, job)
        finally:
            if original is None:
                worker._handlers.pop(entrypoint, None)
            else:
                worker._handlers[entrypoint] = original

    def evidence(self, outcome: RealIngestOutcome) -> SourceEvidence:
        """Classify a real outcome from its durable operation/result record."""

        failure_class = classify_source_outcome(
            status=outcome.status,
            claimed_content_ids=outcome.claimed_content_ids,
            content_delta=outcome.content_row_delta,
            problem_detail=outcome.problem_detail,
        )
        return SourceEvidence(
            key=outcome.key,
            operation_id=outcome.operation_id,
            failure_class=failure_class,
            claimed=len(outcome.claimed_content_ids),
            delta=outcome.content_row_delta,
            detail=outcome.problem_detail,
        )

    def _fixture_registry(self, key: str, fixture: SourceFixture) -> SourceRegistry:
        """Build a single-source registry whose orchestrator commits deterministically."""

        command = SOURCE_REGISTRY.parse_command(fixture.command)
        descriptor = SOURCE_REGISTRY.get(command.kind)  # type: ignore[attr-defined]

        def orchestrator(typed_command: IngestCommandBase) -> IngestionResponse:
            return self._persist(key, fixture, typed_command, descriptor)

        return SourceRegistry([replace(descriptor, orchestrator=orchestrator)])

    def _live_registry(self, key: str) -> SourceRegistry:
        """The real single-source registry for ``key`` with the live retry limit applied.

        ``submit_live`` runs the genuine adapter and orchestrator, but the
        live-adapter policy — not the registry default — is the single source of
        truth for how many live attempts a retryable failure (e.g. HTTP 429) gets.
        Override only the descriptor's ``retry_policy.max_attempts`` so the workflow
        handler honors the policy while every other real behavior is preserved.
        """

        command = SOURCE_REGISTRY.parse_command(SOURCE_FIXTURES[key].command)
        descriptor = SOURCE_REGISTRY.get(command.kind)  # type: ignore[attr-defined]
        max_attempts = LIVE_ADAPTER_POLICIES[key].max_attempts
        retry_policy = replace(descriptor.retry_policy, max_attempts=max_attempts)
        return SourceRegistry([replace(descriptor, retry_policy=retry_policy)])

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
            raise AssertionError(f"Fixture '{key}' did not resolve to exactly one content source")
        source = next(iter(sources))
        content_id = self._commit_content(key, fixture, source)
        return _fixture_response(fixture, content_id)

    def _commit_content(self, key: str, fixture: SourceFixture, source: ContentSource) -> int:
        """Commit one Content+Summary for ``key`` and return the new content ID."""

        index = len(self._created_content_ids) + 1
        session = self._sessionmaker()
        ContentFactory._meta.sqlalchemy_session = session  # type: ignore[attr-defined]
        SummaryFactory._meta.sqlalchemy_session = session  # type: ignore[attr-defined]
        try:
            content = cast(
                Content,
                ContentFactory(
                    source_type=source,
                    source_id=f"real-ingest:{self._token}:{key}:{index}",
                    source_url=f"https://fixtures.test/{key}/{index}",
                    title=fixture.title,
                    publication=f"Fixture {key}",
                    published_date=PERIOD_START + timedelta(minutes=index),
                    ingested_at=PERIOD_START + timedelta(minutes=index),
                    markdown_content=f"# {fixture.title}\n\nDeterministic content for {key}.",
                ),
            )
            content_id = content.id
            assert content_id is not None  # committed by the factory, so populated
            SummaryFactory(
                content=content,
                content_id=content_id,
                executive_summary=f"Persisted summary for {key}",
            )
            record_content_reference(content_id, content.canonical_id)
        finally:
            ContentFactory._meta.sqlalchemy_session = None  # type: ignore[attr-defined]
            SummaryFactory._meta.sqlalchemy_session = None  # type: ignore[attr-defined]
            session.close()

        self._created_content_ids.append(content_id)
        return content_id

    def _enter_files_patches(self, stack: ExitStack, key: str, fixture: SourceFixture) -> None:
        """Stub upload materialization + ingest_files so the files path commits."""

        @contextmanager
        def _materialize_sync(
            _self: Any, _upload_ids: list[str]
        ) -> Iterator[list[MaterializedUpload]]:
            yield [
                MaterializedUpload(
                    path=Path("fixture-upload.md"),
                    title=fixture.title,
                    publication=f"Fixture {key}",
                )
            ]

        def _ingest_files(**_kwargs: Any) -> IngestionResponse:
            content_id = self._commit_content(key, fixture, ContentSource.FILE_UPLOAD)
            return _fixture_response(fixture, content_id)

        stack.enter_context(
            patch("src.services.upload_service.UploadService.materialize_sync", _materialize_sync)
        )
        stack.enter_context(patch("src.ingestion.orchestrator.ingest_files", _ingest_files))

    def _enter_obsidian_patches(self, stack: ExitStack, fixture_settings: Any) -> None:
        """Bind the real adapter to this DB and reject any non-loopback network."""

        @contextmanager
        def _fixture_db() -> Iterator[Any]:
            session = self._sessionmaker()
            try:
                yield session
            finally:
                session.close()

        original_connect = socket.socket.connect

        def _loopback_only(sock: socket.socket, address: Any) -> Any:
            return reject_external_fixture_network(original_connect, sock, address)

        stack.enter_context(
            patch("src.config.settings.get_settings", return_value=fixture_settings)
        )
        stack.enter_context(patch("src.storage.database.get_db", _fixture_db))
        stack.enter_context(patch.object(socket.socket, "connect", _loopback_only))

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

    def _content_delta_for_ids(self, content_ids: tuple[int, ...]) -> int:
        """Count how many of the claimed content IDs are actually persisted."""

        if not content_ids:
            return 0
        with self._sessionmaker() as session:
            return int(
                session.execute(
                    text("SELECT count(*) FROM contents WHERE id = ANY(:ids)"),
                    {"ids": list(content_ids)},
                ).scalar_one()
            )

    async def cleanup(self) -> None:
        """Delete every committed row and durable job this harness created."""

        if self._obsidian_source_digest is not None:
            with self._sessionmaker() as session:
                session.execute(
                    text(
                        "DELETE FROM obsidian_ingest_events "
                        "WHERE configured_source_digest = :digest"
                    ),
                    {"digest": self._obsidian_source_digest},
                )
                session.execute(
                    text(
                        "DELETE FROM obsidian_ingest_state WHERE configured_source_digest = :digest"
                    ),
                    {"digest": self._obsidian_source_digest},
                )
                session.commit()
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
