"""Transactional leasing and crash-recovery coverage for Obsidian ingestion."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.repositories.obsidian_ingest import ObsidianIngestRepository

SOURCE = "3" * 64
PATH = "d" * 64
FILE = "e" * 64


def _sessions(test_engine):
    engine = create_async_engine(test_engine.url.set(drivername="postgresql+asyncpg"))
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _insert_job(session, suffix: str) -> int:
    return int(
        await session.scalar(
            text(
                "INSERT INTO pgqueuer_jobs (entrypoint, payload, status) "
                "VALUES ('obsidian.ingest', CAST(:payload AS jsonb), 'queued') RETURNING id"
            ),
            {"payload": '{"fixture":"' + suffix + '"}'},
        )
    )


async def _insert_content(session, suffix: str) -> int:
    return int(
        await session.scalar(
            text(
                "INSERT INTO contents "
                "(source_type, source_id, title, markdown_content, content_hash, status) "
                "VALUES ('manual', :source_id, 'fixture', '# fixture', :hash, 'pending') "
                "RETURNING id"
            ),
            {"source_id": f"obsidian-state-{suffix}", "hash": suffix.rjust(64, "0")},
        )
    )


async def _cleanup(sessions) -> None:
    async with sessions() as session:
        await session.execute(
            text("DELETE FROM obsidian_ingest_events WHERE configured_source_digest = :source"),
            {"source": SOURCE},
        )
        await session.execute(
            text("DELETE FROM obsidian_ingest_state WHERE configured_source_digest = :source"),
            {"source": SOURCE},
        )
        await session.execute(text("DELETE FROM contents WHERE source_id LIKE 'obsidian-state-%'"))
        await session.execute(
            text("DELETE FROM pgqueuer_jobs WHERE entrypoint = 'obsidian.ingest'")
        )
        await session.commit()


@pytest.mark.asyncio
async def test_concurrent_claim_has_one_winner_then_expired_lease_is_reclaimed(
    test_engine,
) -> None:
    engine, sessions = _sessions(test_engine)
    now = datetime(2026, 8, 2, 12, tzinfo=UTC)
    try:
        async with sessions() as setup:
            observed = await ObsidianIngestRepository(setup).observe_file_version(
                SOURCE, PATH, FILE, observed_mtime_ns=10, observed_size=20, now=now
            )
            first_job = await _insert_job(setup, "first")
            second_job = await _insert_job(setup, "second")
            await setup.commit()

        async with sessions() as first_session, sessions() as second_session:
            first_repository = ObsidianIngestRepository(first_session)
            second_repository = ObsidianIngestRepository(second_session)
            first_claim = await first_repository.claim_file_version(
                observed.event_id, first_job, now=now, lease_seconds=30
            )
            assert first_claim is not None

            losing_task = asyncio.create_task(
                second_repository.claim_file_version(
                    observed.event_id, second_job, now=now, lease_seconds=30
                )
            )
            await asyncio.sleep(0.05)
            assert not losing_task.done()
            await first_session.commit()
            assert await asyncio.wait_for(losing_task, timeout=2) is None
            await second_session.commit()

        async with sessions() as recovery:
            repository = ObsidianIngestRepository(recovery)
            second_claim = await repository.claim_file_version(
                observed.event_id,
                second_job,
                now=now + timedelta(seconds=31),
                lease_seconds=30,
            )
            assert second_claim is not None
            assert second_claim.attempt_count == 2
            content_id = await _insert_content(recovery, "101")
            assert (
                await repository.complete_claim(
                    first_claim, content_id=content_id, now=now + timedelta(seconds=32)
                )
                is False
            )
            assert (
                await repository.complete_claim(
                    second_claim, content_id=content_id, now=now + timedelta(seconds=32)
                )
                is True
            )
            await recovery.commit()
    finally:
        await _cleanup(sessions)
        await engine.dispose()


@pytest.mark.asyncio
async def test_claim_attempts_are_bounded_and_ingested_versions_are_not_reclaimed(
    test_engine,
) -> None:
    engine, sessions = _sessions(test_engine)
    now = datetime(2026, 8, 2, 12, tzinfo=UTC)
    try:
        async with sessions() as session:
            repository = ObsidianIngestRepository(session)
            observed = await repository.observe_file_version(
                SOURCE, PATH, FILE, observed_mtime_ns=10, observed_size=20, now=now
            )
            job = await _insert_job(session, "bounded")
            await session.commit()

            first = await repository.claim_file_version(
                observed.event_id, job, now=now, lease_seconds=1, max_attempts=2
            )
            await session.commit()
            assert first is not None
            second = await repository.claim_file_version(
                observed.event_id,
                job,
                now=now + timedelta(seconds=2),
                lease_seconds=1,
                max_attempts=2,
            )
            await session.commit()
            assert second is not None
            assert (
                await repository.claim_file_version(
                    observed.event_id,
                    job,
                    now=now + timedelta(seconds=4),
                    lease_seconds=1,
                    max_attempts=2,
                )
                is None
            )
            await session.rollback()
    finally:
        await _cleanup(sessions)
        await engine.dispose()


@pytest.mark.asyncio
async def test_reconciliation_closes_content_commit_crash_window_idempotently(
    test_engine,
) -> None:
    engine, sessions = _sessions(test_engine)
    now = datetime(2026, 8, 2, 12, tzinfo=UTC)
    try:
        async with sessions() as session:
            repository = ObsidianIngestRepository(session)
            observed = await repository.observe_file_version(
                SOURCE, PATH, FILE, observed_mtime_ns=10, observed_size=20, now=now
            )
            content_id = await _insert_content(session, "201")
            other_content_id = await _insert_content(session, "202")
            await session.commit()

            assert await repository.reconcile_content(
                observed.event_id, content_id=content_id, now=now + timedelta(minutes=1)
            )
            assert await repository.reconcile_content(
                observed.event_id, content_id=content_id, now=now + timedelta(minutes=2)
            )
            assert not await repository.reconcile_content(
                observed.event_id, content_id=other_content_id, now=now + timedelta(minutes=3)
            )
            reconciled = await repository.lookup_event(SOURCE, PATH, FILE)
            assert reconciled is not None
            assert reconciled.status == "ingested"
            assert reconciled.content_id == content_id
            await session.commit()
    finally:
        await _cleanup(sessions)
        await engine.dispose()
