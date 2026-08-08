"""Behavioral tests for the private Obsidian ingest-state repository."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

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
    return sessionmaker(bind=test_engine, expire_on_commit=False)


def _cleanup(sessions, *sources: str) -> None:
    with sessions() as session:
        session.execute(
            text(
                "DELETE FROM obsidian_ingest_events WHERE configured_source_digest = ANY(:sources)"
            ),
            {"sources": list(sources)},
        )
        session.execute(
            text(
                "DELETE FROM obsidian_ingest_state WHERE configured_source_digest = ANY(:sources)"
            ),
            {"sources": list(sources)},
        )
        session.commit()


def test_observation_deduplicates_unchanged_versions_and_isolates_sources(
    test_engine,
) -> None:
    sessions = _sessions(test_engine)
    now = datetime(2026, 8, 2, 12, tzinfo=UTC)
    try:
        with sessions() as session:
            repository = ObsidianIngestRepository(session)
            first = repository.observe_file_version(
                SOURCE_A, PATH_A, FILE_A, observed_mtime_ns=10, observed_size=20, now=now
            )
            unchanged = repository.observe_file_version(
                SOURCE_A, PATH_A, FILE_A, observed_mtime_ns=11, observed_size=20, now=now
            )
            changed = repository.observe_file_version(
                SOURCE_A, PATH_A, FILE_B, observed_mtime_ns=12, observed_size=21, now=now
            )
            other_source = repository.observe_file_version(
                SOURCE_B, PATH_A, FILE_A, observed_mtime_ns=10, observed_size=20, now=now
            )
            session.commit()

            assert first.eligible is True
            assert unchanged.event_id == first.event_id
            assert unchanged.eligible is False
            assert unchanged.unchanged is True
            assert changed.event_id != first.event_id
            assert changed.eligible is True
            assert other_source.state_id != first.state_id
    finally:
        _cleanup(sessions, SOURCE_A, SOURCE_B)


def test_missing_marker_is_non_destructive_and_reobservation_restores_state(
    test_engine,
) -> None:
    sessions = _sessions(test_engine)
    now = datetime(2026, 8, 2, 12, tzinfo=UTC)
    try:
        with sessions() as session:
            repository = ObsidianIngestRepository(session)
            observed = repository.observe_file_version(
                SOURCE_A, PATH_A, FILE_A, observed_mtime_ns=10, observed_size=20, now=now
            )
            assert not repository.mark_missing(
                SOURCE_A,
                PATH_A,
                expected_observation_generation=observed.observation_generation,
                now=now + timedelta(hours=1),
                grace_seconds=60,
            )
            grace_state = session.execute(
                text(
                    "SELECT status, missing_since FROM obsidian_ingest_state "
                    "WHERE configured_source_digest = :source"
                ),
                {"source": SOURCE_A},
            ).one()
            assert grace_state.status == "discovered"
            assert grace_state.missing_since is not None
            session.execute(
                text(
                    "UPDATE obsidian_ingest_state "
                    "SET missing_since = clock_timestamp() - INTERVAL '61 seconds' "
                    "WHERE configured_source_digest = :source"
                ),
                {"source": SOURCE_A},
            )
            assert repository.mark_missing(
                SOURCE_A,
                PATH_A,
                expected_observation_generation=observed.observation_generation,
                now=now + timedelta(hours=2),
                grace_seconds=60,
            )
            missing = repository.lookup_event(SOURCE_A, PATH_A, FILE_A)
            assert missing is not None
            assert missing.status == "deferred"
            assert missing.error_code == "file_missing"

            restored = repository.observe_file_version(
                SOURCE_A,
                PATH_A,
                FILE_A,
                observed_mtime_ns=10,
                observed_size=20,
                now=now + timedelta(hours=3),
            )
            session.commit()

            assert restored.event_id == observed.event_id
            assert restored.status == "discovered"
            assert restored.eligible is True
    finally:
        _cleanup(sessions, SOURCE_A)


def test_validation_errors_are_bounded_codes_without_private_input() -> None:
    secret_path = "/Users/alice/private-vault/board-notes.md"
    repository = ObsidianIngestRepository(Mock(spec=Session))

    with pytest.raises(ObsidianIngestRepositoryError) as digest_error:
        repository.lookup_event(SOURCE_A, secret_path, FILE_A)
    assert str(digest_error.value) == "invalid_digest"
    assert secret_path not in repr(digest_error.value)

    with pytest.raises(ObsidianIngestRepositoryError) as code_error:
        repository.fail_claim(
            claim=Mock(),
            error_code=secret_path,
            now=datetime.now(UTC),
        )
    assert str(code_error.value) == "invalid_error_code"
    assert secret_path not in repr(code_error.value)

    for invalid_generation in (-1, True):
        with pytest.raises(ObsidianIngestRepositoryError, match="^invalid_observation_generation$"):
            repository.mark_missing(
                SOURCE_A,
                PATH_A,
                expected_observation_generation=invalid_generation,
                now=datetime.now(UTC),
            )


def test_first_post_upgrade_missing_scan_accepts_generation_zero(test_engine) -> None:
    sessions = _sessions(test_engine)
    now = datetime(2026, 8, 2, 12, tzinfo=UTC)
    try:
        with sessions.begin() as session:
            repository = ObsidianIngestRepository(session)
            repository.observe_file_version(
                SOURCE_A, PATH_A, FILE_A, observed_mtime_ns=10, observed_size=20, now=now
            )
            session.execute(
                text(
                    "UPDATE obsidian_ingest_state SET observation_generation = 0 "
                    "WHERE configured_source_digest = :source "
                    "AND relative_path_digest = :path"
                ),
                {"source": SOURCE_A, "path": PATH_A},
            )

            assert not repository.mark_missing(
                SOURCE_A,
                PATH_A,
                expected_observation_generation=0,
                now=now,
                grace_seconds=60,
            )
            missing_since = session.scalar(
                text(
                    "SELECT missing_since FROM obsidian_ingest_state "
                    "WHERE configured_source_digest = :source "
                    "AND relative_path_digest = :path"
                ),
                {"source": SOURCE_A, "path": PATH_A},
            )
            assert missing_since is not None
    finally:
        _cleanup(sessions, SOURCE_A)


def test_missing_compare_and_set_rejects_stale_observation_generation(test_engine) -> None:
    sessions = _sessions(test_engine)
    now = datetime(2026, 8, 2, 12, tzinfo=UTC)
    try:
        with sessions.begin() as session:
            repository = ObsidianIngestRepository(session)
            first = repository.observe_file_version(
                SOURCE_A, PATH_A, FILE_A, observed_mtime_ns=10, observed_size=20, now=now
            )
            reappeared = repository.observe_file_version(
                SOURCE_A, PATH_A, FILE_A, observed_mtime_ns=11, observed_size=20, now=now
            )
            assert reappeared.observation_generation == first.observation_generation + 1
            assert not repository.mark_missing(
                SOURCE_A,
                PATH_A,
                expected_observation_generation=first.observation_generation,
                now=now,
                grace_seconds=60,
            )
    finally:
        _cleanup(sessions, SOURCE_A)
