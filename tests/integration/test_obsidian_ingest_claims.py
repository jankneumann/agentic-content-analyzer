"""Transactional leasing and crash-recovery coverage for Obsidian ingestion."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from src.repositories.obsidian_ingest import ObsidianIngestRepository

SOURCE = "3" * 64
PATH = "d" * 64
FILE = "e" * 64
NEW_FILE = "f" * 64


def _sessions(test_engine) -> sessionmaker[Session]:
    return sessionmaker(bind=test_engine, expire_on_commit=False)


def _insert_job(session: Session, suffix: str) -> int:
    return int(
        session.scalar(
            text(
                "INSERT INTO pgqueuer_jobs (entrypoint, payload, status) "
                "VALUES ('obsidian.ingest', CAST(:payload AS jsonb), 'queued') RETURNING id"
            ),
            {"payload": '{"fixture":"' + suffix + '"}'},
        )
    )


def _insert_content(session: Session, suffix: str) -> int:
    return int(
        session.scalar(
            text(
                "INSERT INTO contents "
                "(source_type, source_id, title, markdown_content, content_hash, status) "
                "VALUES ('manual', :source_id, 'fixture', '# fixture', :hash, 'pending') "
                "RETURNING id"
            ),
            {"source_id": f"obsidian-state-{suffix}", "hash": suffix.rjust(64, "0")},
        )
    )


def _cleanup(sessions: sessionmaker[Session]) -> None:
    with sessions() as session:
        session.execute(
            text("DELETE FROM obsidian_ingest_events WHERE configured_source_digest = :source"),
            {"source": SOURCE},
        )
        session.execute(
            text("DELETE FROM obsidian_ingest_state WHERE configured_source_digest = :source"),
            {"source": SOURCE},
        )
        session.execute(text("DELETE FROM contents WHERE source_id LIKE 'obsidian-state-%'"))
        session.execute(text("DELETE FROM pgqueuer_jobs WHERE entrypoint = 'obsidian.ingest'"))
        session.commit()


def _expire_claim(session: Session, event_id: int) -> None:
    session.execute(
        text(
            "UPDATE obsidian_ingest_events "
            "SET lease_expires_at = clock_timestamp() - INTERVAL '1 second' "
            "WHERE id = :event_id"
        ),
        {"event_id": event_id},
    )
    session.execute(
        text(
            "UPDATE obsidian_ingest_state "
            "SET lease_expires_at = clock_timestamp() - INTERVAL '1 second' "
            "WHERE current_file_hash = :file_hash"
        ),
        {"file_hash": FILE},
    )
    session.commit()


def test_concurrent_claim_has_one_winner_then_expired_lease_is_reclaimed(
    test_engine,
) -> None:
    sessions = _sessions(test_engine)
    now = datetime(2026, 8, 2, 12, tzinfo=UTC)
    try:
        with sessions() as setup:
            observed = ObsidianIngestRepository(setup).observe_file_version(
                SOURCE, PATH, FILE, observed_mtime_ns=10, observed_size=20, now=now
            )
            first_job = _insert_job(setup, "first")
            second_job = _insert_job(setup, "second")
            setup.commit()

        hostile_future = datetime(2099, 1, 1, tzinfo=UTC)

        def losing_claim():
            with sessions() as contender:
                result = ObsidianIngestRepository(contender).claim_file_version(
                    observed.event_id,
                    second_job,
                    now=hostile_future,
                    lease_seconds=30,
                )
                contender.commit()
                return result

        with sessions() as first_session, ThreadPoolExecutor(max_workers=1) as executor:
            first_claim = ObsidianIngestRepository(first_session).claim_file_version(
                observed.event_id, first_job, now=now, lease_seconds=30
            )
            assert first_claim is not None
            losing_future = executor.submit(losing_claim)
            time.sleep(0.05)
            assert not losing_future.done()
            first_session.commit()
            assert losing_future.result(timeout=2) is None

        with sessions() as recovery:
            repository = ObsidianIngestRepository(recovery)
            _expire_claim(recovery, observed.event_id)
            second_claim = repository.claim_file_version(
                observed.event_id,
                second_job,
                now=datetime(2000, 1, 1, tzinfo=UTC),
                lease_seconds=30,
            )
            assert second_claim is not None
            assert second_claim.attempt_count == 2
            content_id = _insert_content(recovery, "101")
            assert not repository.complete_claim(
                first_claim, content_id=content_id, now=now + timedelta(seconds=32)
            )
            assert repository.complete_claim(
                second_claim, content_id=content_id, now=now + timedelta(seconds=32)
            )
            recovery.commit()
    finally:
        _cleanup(sessions)


def test_claim_attempts_are_bounded_and_ingested_versions_are_not_reclaimed(
    test_engine,
) -> None:
    sessions = _sessions(test_engine)
    now = datetime(2026, 8, 2, 12, tzinfo=UTC)
    try:
        with sessions() as session:
            repository = ObsidianIngestRepository(session)
            observed = repository.observe_file_version(
                SOURCE, PATH, FILE, observed_mtime_ns=10, observed_size=20, now=now
            )
            job = _insert_job(session, "bounded")
            session.commit()

            first = repository.claim_file_version(
                observed.event_id, job, now=now, lease_seconds=1, max_attempts=2
            )
            session.commit()
            assert first is not None
            _expire_claim(session, observed.event_id)
            second = repository.claim_file_version(
                observed.event_id,
                job,
                now=now + timedelta(seconds=2),
                lease_seconds=1,
                max_attempts=2,
            )
            session.commit()
            assert second is not None
            _expire_claim(session, observed.event_id)
            assert (
                repository.claim_file_version(
                    observed.event_id,
                    job,
                    now=now + timedelta(seconds=4),
                    lease_seconds=1,
                    max_attempts=2,
                )
                is None
            )
            session.rollback()
    finally:
        _cleanup(sessions)


def test_changed_hash_releases_previous_claim_and_rejects_stale_completion(
    test_engine,
) -> None:
    sessions = _sessions(test_engine)
    now = datetime(2026, 8, 2, 12, tzinfo=UTC)
    try:
        with sessions() as setup:
            old_observation = ObsidianIngestRepository(setup).observe_file_version(
                SOURCE, PATH, FILE, observed_mtime_ns=10, observed_size=20, now=now
            )
            old_job = _insert_job(setup, "superseded-old")
            new_job = _insert_job(setup, "superseded-new")
            content_id = _insert_content(setup, "301")
            setup.commit()

        with sessions() as old_worker:
            old_claim = ObsidianIngestRepository(old_worker).claim_file_version(
                old_observation.event_id, old_job, now=now, lease_seconds=300
            )
            assert old_claim is not None
            old_worker.commit()

        with sessions() as scanner:
            new_observation = ObsidianIngestRepository(scanner).observe_file_version(
                SOURCE,
                PATH,
                NEW_FILE,
                observed_mtime_ns=11,
                observed_size=21,
                now=now + timedelta(seconds=1),
            )
            scanner.commit()
            assert new_observation.eligible is True

        with sessions() as verifier:
            repository = ObsidianIngestRepository(verifier)
            old_event = repository.lookup_event(SOURCE, PATH, FILE)
            assert old_event is not None
            assert old_event.status == "deferred"
            assert old_event.error_code == "claim_released"
            released = verifier.execute(
                text(
                    "SELECT claim_token, lease_expires_at, completed_at "
                    "FROM obsidian_ingest_events WHERE id = :event_id"
                ),
                {"event_id": old_observation.event_id},
            ).one()
            assert released.claim_token is None
            assert released.lease_expires_at is None
            assert released.completed_at is not None
            assert not repository.complete_claim(
                old_claim,
                content_id=content_id,
                now=now + timedelta(seconds=2),
            )

            new_claim = repository.claim_file_version(
                new_observation.event_id,
                new_job,
                now=now + timedelta(seconds=2),
            )
            assert new_claim is not None
            verifier.commit()
    finally:
        _cleanup(sessions)


def test_reconciliation_closes_content_commit_crash_window_idempotently(
    test_engine,
) -> None:
    sessions = _sessions(test_engine)
    now = datetime(2026, 8, 2, 12, tzinfo=UTC)
    try:
        with sessions() as session:
            repository = ObsidianIngestRepository(session)
            observed = repository.observe_file_version(
                SOURCE, PATH, FILE, observed_mtime_ns=10, observed_size=20, now=now
            )
            content_id = _insert_content(session, "201")
            other_content_id = _insert_content(session, "202")
            session.commit()

            assert repository.reconcile_content(
                observed.event_id,
                content_id=content_id,
                expected_source_id="obsidian-state-201",
                now=now + timedelta(minutes=1),
            )
            assert repository.reconcile_content(
                observed.event_id,
                content_id=content_id,
                expected_source_id="obsidian-state-201",
                now=now + timedelta(minutes=2),
            )
            assert not repository.reconcile_content(
                observed.event_id,
                content_id=other_content_id,
                expected_source_id="obsidian-state-201",
                now=now + timedelta(minutes=3),
            )
            reconciled = repository.lookup_event(SOURCE, PATH, FILE)
            assert reconciled is not None
            assert reconciled.status == "ingested"
            assert reconciled.content_id == content_id

            repository.observe_file_version(
                SOURCE,
                PATH,
                NEW_FILE,
                observed_mtime_ns=11,
                observed_size=21,
                now=now + timedelta(minutes=4),
            )
            preserved = repository.lookup_event(SOURCE, PATH, FILE)
            assert preserved is not None
            assert preserved.status == "ingested"
            assert preserved.content_id == content_id
            session.commit()
    finally:
        _cleanup(sessions)


def test_expired_claim_becomes_missing_only_after_database_timed_grace(test_engine) -> None:
    sessions = _sessions(test_engine)
    now = datetime(2026, 8, 2, 12, tzinfo=UTC)
    try:
        with sessions() as session:
            repository = ObsidianIngestRepository(session)
            observed = repository.observe_file_version(
                SOURCE, PATH, FILE, observed_mtime_ns=10, observed_size=20, now=now
            )
            job = _insert_job(session, "missing-expired")
            session.commit()
            claim = repository.claim_file_version(observed.event_id, job, now=now, lease_seconds=30)
            assert claim is not None
            session.commit()

            assert not repository.mark_missing(
                SOURCE,
                PATH,
                now=datetime(2099, 1, 1, tzinfo=UTC),
                grace_seconds=60,
            )
            _expire_claim(session, observed.event_id)
            assert (
                repository.claim_file_version(
                    observed.event_id,
                    job,
                    now=datetime(2099, 1, 1, tzinfo=UTC),
                )
                is None
            )
            session.execute(
                text(
                    "UPDATE obsidian_ingest_state "
                    "SET missing_since = clock_timestamp() - INTERVAL '61 seconds' "
                    "WHERE id = :state_id"
                ),
                {"state_id": claim.state_id},
            )
            session.commit()

            assert repository.mark_missing(
                SOURCE,
                PATH,
                now=datetime(2000, 1, 1, tzinfo=UTC),
                grace_seconds=60,
            )
            missing = repository.lookup_event(SOURCE, PATH, FILE)
            assert missing is not None
            assert missing.status == "deferred"
            assert missing.error_code == "file_missing"
            assert not repository.complete_claim(
                claim,
                content_id=999_999,
                now=datetime(2000, 1, 1, tzinfo=UTC),
            )
            session.rollback()
    finally:
        _cleanup(sessions)
