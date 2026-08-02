"""Behavioral tests for the private Obsidian ingest-state repository."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.repositories.obsidian_ingest import (
    ObsidianIngestRepository,
    ObsidianIngestRepositoryError,
)

SOURCE_A = "1" * 64
SOURCE_B = "2" * 64
PATH_A = "a" * 64
FILE_A = "b" * 64
FILE_B = "c" * 64


def _sessions(test_engine):
    engine = create_async_engine(test_engine.url.set(drivername="postgresql+asyncpg"))
    return engine, async_sessionmaker(engine, expire_on_commit=False)


@pytest.mark.asyncio
async def test_observation_deduplicates_unchanged_versions_and_isolates_sources(
    test_engine,
) -> None:
    engine, sessions = _sessions(test_engine)
    now = datetime(2026, 8, 2, 12, tzinfo=UTC)
    try:
        async with sessions() as session:
            repository = ObsidianIngestRepository(session)
            first = await repository.observe_file_version(
                SOURCE_A, PATH_A, FILE_A, observed_mtime_ns=10, observed_size=20, now=now
            )
            unchanged = await repository.observe_file_version(
                SOURCE_A, PATH_A, FILE_A, observed_mtime_ns=11, observed_size=20, now=now
            )
            changed = await repository.observe_file_version(
                SOURCE_A, PATH_A, FILE_B, observed_mtime_ns=12, observed_size=21, now=now
            )
            other_source = await repository.observe_file_version(
                SOURCE_B, PATH_A, FILE_A, observed_mtime_ns=10, observed_size=20, now=now
            )
            await session.commit()

            assert first.eligible is True
            assert unchanged.event_id == first.event_id
            assert unchanged.eligible is False
            assert unchanged.unchanged is True
            assert changed.event_id != first.event_id
            assert changed.eligible is True
            assert other_source.state_id != first.state_id
    finally:
        async with sessions() as session:
            await session.execute(
                text(
                    "DELETE FROM obsidian_ingest_events "
                    "WHERE configured_source_digest IN (:source_a, :source_b)"
                ),
                {"source_a": SOURCE_A, "source_b": SOURCE_B},
            )
            await session.execute(
                text(
                    "DELETE FROM obsidian_ingest_state "
                    "WHERE configured_source_digest IN (:source_a, :source_b)"
                ),
                {"source_a": SOURCE_A, "source_b": SOURCE_B},
            )
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_missing_marker_is_non_destructive_and_reobservation_restores_state(
    test_engine,
) -> None:
    engine, sessions = _sessions(test_engine)
    now = datetime(2026, 8, 2, 12, tzinfo=UTC)
    try:
        async with sessions() as session:
            repository = ObsidianIngestRepository(session)
            observed = await repository.observe_file_version(
                SOURCE_A, PATH_A, FILE_A, observed_mtime_ns=10, observed_size=20, now=now
            )
            assert await repository.mark_missing(SOURCE_A, PATH_A, now=now + timedelta(hours=1))
            missing = await repository.lookup_event(SOURCE_A, PATH_A, FILE_A)
            assert missing is not None
            assert missing.status == "deferred"
            assert missing.error_code == "file_missing"

            restored = await repository.observe_file_version(
                SOURCE_A,
                PATH_A,
                FILE_A,
                observed_mtime_ns=10,
                observed_size=20,
                now=now + timedelta(hours=2),
            )
            await session.commit()

            assert restored.event_id == observed.event_id
            assert restored.status == "discovered"
            assert restored.eligible is True
    finally:
        async with sessions() as session:
            await session.execute(
                text("DELETE FROM obsidian_ingest_events WHERE configured_source_digest = :source"),
                {"source": SOURCE_A},
            )
            await session.execute(
                text("DELETE FROM obsidian_ingest_state WHERE configured_source_digest = :source"),
                {"source": SOURCE_A},
            )
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_validation_errors_are_bounded_codes_without_private_input() -> None:
    secret_path = "/Users/alice/private-vault/board-notes.md"
    repository = ObsidianIngestRepository(AsyncMock(spec=AsyncSession))

    with pytest.raises(ObsidianIngestRepositoryError) as digest_error:
        await repository.lookup_event(SOURCE_A, secret_path, FILE_A)
    assert str(digest_error.value) == "invalid_digest"
    assert secret_path not in repr(digest_error.value)

    with pytest.raises(ObsidianIngestRepositoryError) as code_error:
        await repository.fail_claim(
            claim=AsyncMock(),
            error_code=secret_path,
            now=datetime.now(UTC),
        )
    assert str(code_error.value) == "invalid_error_code"
    assert secret_path not in repr(code_error.value)
