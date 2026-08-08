"""Database integration coverage for immutable Obsidian note identities."""

from __future__ import annotations

import json
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Event
from time import monotonic, sleep

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

import src.ingestion.obsidian_adapter as adapter_module
from src.ingestion.obsidian_adapter import (
    ObsidianAdapterConfig,
    ingest_obsidian_vault,
    obsidian_source_id,
)
from src.ingestion.obsidian_scanner import ScanLimits
from src.models.content import Content, ContentSource
from src.models.obsidian_ingest import ObsidianIngestEvent, ObsidianIngestState
from src.queue.execution_claim import ClaimCancelled, ExecutionClaim, bind_execution_claim
from src.repositories.obsidian_ingest import ObsidianIngestRepository

SOURCE_DIGEST = "8" * 64


@pytest.fixture
def migration_db_session(test_engine) -> Generator[Session, None, None]:
    """Keep adapter transactions on the migration-built schema for this module."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


def _note(body: str, url: str = "https://example.test/shared") -> str:
    return f"---\nsource_url: {url}\ncaptured_at: 2026-08-02T10:00:00Z\n---\n{body}\n"


def _job(session: Session, suffix: int) -> int:
    return int(
        session.scalar(
            text(
                "INSERT INTO pgqueuer_jobs "
                "(entrypoint, payload, status, claim_generation, claim_protocol_version) "
                "VALUES ('ingestion.execute', CAST(:payload AS jsonb), 'in_progress', 1, 2) "
                "RETURNING id"
            ),
            {"payload": json.dumps({"cancel_requested": False, "fixture": suffix})},
        )
    )


def _run(session: Session, config: ObsidianAdapterConfig, suffix: int, *, force: bool = False):
    job_id = _job(session, suffix)
    with bind_execution_claim(ExecutionClaim(job_id=job_id, claim_generation=1)):
        return ingest_obsidian_vault(session, config, force_reprocess=force)


def test_unchanged_changed_renamed_deleted_and_reappearing_notes_are_idempotent(
    migration_db_session: Session, tmp_path: Path
) -> None:
    db_session = migration_db_session
    approved = tmp_path / "approved"
    inbox = approved / "vault" / "Inbox"
    inbox.mkdir(parents=True)
    note = inbox / "first.md"
    note.write_text(_note("first annotation"))
    config = ObsidianAdapterConfig(
        configured_source_digest=SOURCE_DIGEST,
        vault_path=approved / "vault",
        ingest_folder="Inbox",
        allowed_roots=(approved,),
        scan_limits=ScanLimits(settle_seconds=0),
    )

    first = _run(db_session, config, 1)
    unchanged = _run(db_session, config, 2)
    forced = _run(db_session, config, 3, force=True)
    note.write_text(_note("changed annotation"))
    changed = _run(db_session, config, 4)
    note.rename(inbox / "renamed.md")
    renamed = _run(db_session, config, 5)
    (inbox / "renamed.md").unlink()
    missing = _run(db_session, config, 6)
    (inbox / "renamed.md").write_text(_note("changed annotation"))
    reappeared = _run(db_session, config, 7)

    assert first.persisted == 1
    assert unchanged.skipped == 1
    assert forced.skipped == 1
    assert changed.persisted == 1
    assert renamed.persisted == 1
    assert missing.persisted == 0
    assert reappeared.skipped == 1
    assert (
        db_session.query(Content).filter(Content.source_type == ContentSource.OBSIDIAN).count() == 3
    )
    assert db_session.query(ObsidianIngestEvent).count() == 3


def test_same_canonical_url_preserves_distinct_annotations_under_one_primary(
    migration_db_session: Session, tmp_path: Path
) -> None:
    db_session = migration_db_session
    approved = tmp_path / "approved"
    inbox = approved / "vault" / "Inbox"
    inbox.mkdir(parents=True)
    inbox.joinpath("one.md").write_text(_note("annotation one"))
    inbox.joinpath("two.md").write_text(_note("annotation two"))
    config = ObsidianAdapterConfig(
        configured_source_digest=SOURCE_DIGEST,
        vault_path=approved / "vault",
        ingest_folder="Inbox",
        allowed_roots=(approved,),
    )

    outcome = _run(db_session, config, 8)
    rows = (
        db_session.query(Content)
        .filter(Content.source_type == ContentSource.OBSIDIAN)
        .order_by(Content.id)
        .all()
    )

    assert outcome.persisted == 2
    assert [row.markdown_content for row in rows] == ["annotation one\n", "annotation two\n"]
    assert rows[0].canonical_id is None
    assert rows[1].canonical_id == rows[0].id
    assert rows[0].source_id != rows[1].source_id


def test_two_operations_replay_one_file_version_without_duplicate_content(
    migration_db_session: Session, tmp_path: Path
) -> None:
    db_session = migration_db_session
    approved = tmp_path / "approved"
    inbox = approved / "vault" / "Inbox"
    inbox.mkdir(parents=True)
    inbox.joinpath("one.md").write_text(_note("one"))
    config = ObsidianAdapterConfig(
        configured_source_digest=SOURCE_DIGEST,
        vault_path=approved / "vault",
        ingest_folder="Inbox",
        allowed_roots=(approved,),
    )

    winner = _run(db_session, config, 10)
    loser = _run(db_session, config, 11)

    assert winner.persisted == 1
    assert loser.skipped == 1
    assert (
        db_session.query(Content).filter(Content.source_type == ContentSource.OBSIDIAN).count() == 1
    )
    assert db_session.query(ObsidianIngestEvent).count() == 1


def test_two_worker_sessions_contend_for_one_file_version(
    test_engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    approved = tmp_path / "approved"
    inbox = approved / "vault" / "Inbox"
    inbox.mkdir(parents=True)
    inbox.joinpath("one.md").write_text(_note("one"))
    config = ObsidianAdapterConfig(
        configured_source_digest=SOURCE_DIGEST,
        vault_path=approved / "vault",
        ingest_folder="Inbox",
        allowed_roots=(approved,),
    )
    sessions = sessionmaker(bind=test_engine, expire_on_commit=False)
    with sessions.begin() as setup:
        job_ids = (_job(setup, 20), _job(setup, 21))
    claim_boundary = Barrier(2)
    real_process = adapter_module._process_note

    def contend(*args, **kwargs):
        claim_boundary.wait(timeout=2)
        return real_process(*args, **kwargs)

    monkeypatch.setattr("src.ingestion.obsidian_adapter._process_note", contend)

    def run_worker(job_id: int):
        with sessions() as worker:
            with bind_execution_claim(ExecutionClaim(job_id=job_id, claim_generation=1)):
                return ingest_obsidian_vault(worker, config)

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = tuple(executor.map(run_worker, job_ids))

        assert sum(item.persisted for item in outcomes) == 1
        assert sum(item.skipped for item in outcomes) == 1
        with sessions() as verifier:
            assert (
                verifier.query(Content)
                .filter(Content.source_type == ContentSource.OBSIDIAN)
                .count()
                == 1
            )
            assert verifier.query(ObsidianIngestEvent).count() == 1
    finally:
        with sessions.begin() as cleanup:
            cleanup.execute(
                text("DELETE FROM obsidian_ingest_events WHERE configured_source_digest = :source"),
                {"source": SOURCE_DIGEST},
            )
            cleanup.execute(
                text("DELETE FROM obsidian_ingest_state WHERE configured_source_digest = :source"),
                {"source": SOURCE_DIGEST},
            )
            cleanup.execute(text("DELETE FROM contents WHERE source_type = 'obsidian'"))
            cleanup.execute(
                text("DELETE FROM pgqueuer_jobs WHERE id = ANY(:job_ids)"),
                {"job_ids": list(job_ids)},
            )


def test_external_cancellation_wins_between_committed_notes(
    test_engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    approved = tmp_path / "approved"
    inbox = approved / "vault" / "Inbox"
    inbox.mkdir(parents=True)
    inbox.joinpath("a.md").write_text(_note("one"))
    inbox.joinpath("b.md").write_text(_note("two"))
    config = ObsidianAdapterConfig(
        configured_source_digest=SOURCE_DIGEST,
        vault_path=approved / "vault",
        ingest_folder="Inbox",
        allowed_roots=(approved,),
    )
    sessions = sessionmaker(bind=test_engine, expire_on_commit=False)
    with sessions.begin() as setup:
        job_id = _job(setup, 22)
    first_note_committed = Event()
    cancellation_committed = Event()
    real_commit = adapter_module._commit_transaction
    commit_count = 0

    def pause_after_first_note(session: Session) -> None:
        nonlocal commit_count
        real_commit(session)
        commit_count += 1
        if commit_count == 1:
            first_note_committed.set()
            assert cancellation_committed.wait(timeout=2)

    monkeypatch.setattr(
        "src.ingestion.obsidian_adapter._commit_transaction", pause_after_first_note
    )

    def run_worker():
        with sessions() as worker:
            with bind_execution_claim(ExecutionClaim(job_id=job_id, claim_generation=1)):
                return ingest_obsidian_vault(worker, config)

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(run_worker)
            assert first_note_committed.wait(timeout=2)
            with sessions.begin() as canceller:
                canceller.execute(
                    text(
                        "UPDATE pgqueuer_jobs "
                        "SET payload = jsonb_set(payload, '{cancel_requested}', 'true'::jsonb) "
                        "WHERE id = :job_id"
                    ),
                    {"job_id": job_id},
                )
            cancellation_committed.set()
            with pytest.raises(ClaimCancelled):
                future.result(timeout=2)

        with sessions() as verifier:
            assert (
                verifier.query(Content)
                .filter(Content.source_type == ContentSource.OBSIDIAN)
                .count()
                == 1
            )
            assert (
                verifier.query(ObsidianIngestEvent)
                .filter(ObsidianIngestEvent.status == "claimed")
                .count()
                == 0
            )
    finally:
        cancellation_committed.set()
        with sessions.begin() as cleanup:
            cleanup.execute(
                text("DELETE FROM obsidian_ingest_events WHERE configured_source_digest = :source"),
                {"source": SOURCE_DIGEST},
            )
            cleanup.execute(
                text("DELETE FROM obsidian_ingest_state WHERE configured_source_digest = :source"),
                {"source": SOURCE_DIGEST},
            )
            cleanup.execute(text("DELETE FROM contents WHERE source_type = 'obsidian'"))
            cleanup.execute(
                text("DELETE FROM pgqueuer_jobs WHERE id = :job_id"), {"job_id": job_id}
            )


def test_crash_gap_reconciles_only_an_existing_obsidian_content_identity(
    migration_db_session: Session, tmp_path: Path
) -> None:
    db_session = migration_db_session
    approved = tmp_path / "approved"
    inbox = approved / "vault" / "Inbox"
    inbox.mkdir(parents=True)
    note = inbox / "one.md"
    note.write_text(_note("one"))
    config = ObsidianAdapterConfig(
        configured_source_digest=SOURCE_DIGEST,
        vault_path=approved / "vault",
        ingest_folder="Inbox",
        allowed_roots=(approved,),
    )
    scanned = config.scanner().scan().notes[0]
    source_id = obsidian_source_id(SOURCE_DIGEST, scanned.path_digest, scanned.content_sha256)
    observation = ObsidianIngestRepository(db_session).observe_file_version(
        SOURCE_DIGEST,
        scanned.path_digest,
        scanned.content_sha256,
        observed_mtime_ns=scanned.identity.mtime_ns,
        observed_size=scanned.identity.size,
        now=__import__("datetime").datetime.now(__import__("datetime").UTC),
    )
    unrelated = Content(
        source_type=ContentSource.MANUAL,
        source_id=source_id,
        source_url="https://example.test/shared",
        title="unrelated",
        markdown_content="unrelated",
        content_hash="1" * 64,
        status="pending",
    )
    db_session.add(unrelated)
    db_session.flush()

    outcome = _run(db_session, config, 12)
    event = db_session.get(ObsidianIngestEvent, observation.event_id)

    assert outcome.persisted == 1
    assert event is not None and event.content_id != unrelated.id
    linked = db_session.get(Content, event.content_id)
    assert linked is not None and linked.source_type is ContentSource.OBSIDIAN


def test_partial_scan_does_not_mark_an_unvisited_note_missing(
    migration_db_session: Session, tmp_path: Path
) -> None:
    db_session = migration_db_session
    approved = tmp_path / "approved"
    inbox = approved / "vault" / "Inbox"
    inbox.mkdir(parents=True)
    inbox.joinpath("a.md").write_text(_note("one"))
    inbox.joinpath("b.md").write_text(_note("two"))
    full_config = ObsidianAdapterConfig(
        configured_source_digest=SOURCE_DIGEST,
        vault_path=approved / "vault",
        ingest_folder="Inbox",
        allowed_roots=(approved,),
    )
    _run(db_session, full_config, 13)
    bounded_config = ObsidianAdapterConfig(
        configured_source_digest=SOURCE_DIGEST,
        vault_path=approved / "vault",
        ingest_folder="Inbox",
        allowed_roots=(approved,),
        scan_limits=ScanLimits(max_files=1),
    )

    outcome = _run(db_session, bounded_config, 14)

    assert "scan_file_limit" in [item.code for item in outcome.diagnostics]
    assert all(row.missing_since is None for row in db_session.query(ObsidianIngestState).all())


def test_missing_reconciliation_bounds_stored_state_enumeration(
    migration_db_session: Session, tmp_path: Path
) -> None:
    db_session = migration_db_session
    approved = tmp_path / "approved"
    inbox = approved / "vault" / "Inbox"
    inbox.mkdir(parents=True)
    inbox.joinpath("a.md").write_text(_note("one"))
    inbox.joinpath("b.md").write_text(_note("two"))
    full_config = ObsidianAdapterConfig(
        configured_source_digest=SOURCE_DIGEST,
        vault_path=approved / "vault",
        ingest_folder="Inbox",
        allowed_roots=(approved,),
    )
    _run(db_session, full_config, 15)
    inbox.joinpath("a.md").unlink()
    inbox.joinpath("b.md").unlink()
    bounded_config = ObsidianAdapterConfig(
        configured_source_digest=SOURCE_DIGEST,
        vault_path=approved / "vault",
        ingest_folder="Inbox",
        allowed_roots=(approved,),
        scan_limits=ScanLimits(max_entries=1),
    )

    outcome = _run(db_session, bounded_config, 16)

    assert [item.code for item in outcome.diagnostics] == ["scan_entry_limit"]
    assert all(row.missing_since is None for row in db_session.query(ObsidianIngestState).all())


def test_retry_exhaustion_is_retained_not_re_failed(test_engine, tmp_path: Path) -> None:
    """A spent retry budget stops producing new failures without going silent.

    The scan attempts nothing for this note — the budget is gone and the file is
    unchanged — so counting it as a fresh failure would drive every later scan of
    the vault to a failed durable operation and re-alert on a failure the event
    row already holds. It is reported as skipped, carrying a retained diagnostic
    so the stable code stays visible.
    """

    approved = tmp_path / "approved"
    inbox = approved / "vault" / "Inbox"
    inbox.mkdir(parents=True)
    inbox.joinpath("one.md").write_text(_note("one"))
    config = ObsidianAdapterConfig(
        configured_source_digest=SOURCE_DIGEST,
        vault_path=approved / "vault",
        ingest_folder="Inbox",
        allowed_roots=(approved,),
        max_attempts=1,
    )
    scanned = config.scanner().scan().notes[0]
    sessions = sessionmaker(bind=test_engine, expire_on_commit=False)
    with sessions.begin() as setup:
        repository = ObsidianIngestRepository(setup)
        observation = repository.observe_file_version(
            SOURCE_DIGEST,
            scanned.path_digest,
            scanned.content_sha256,
            observed_mtime_ns=scanned.identity.mtime_ns,
            observed_size=scanned.identity.size,
            now=adapter_module.datetime.now(adapter_module.UTC),
        )
        first_job = _job(setup, 30)
        claim = repository.claim_file_version(
            observation.event_id,
            first_job,
            now=adapter_module.datetime.now(adapter_module.UTC),
            max_attempts=1,
        )
        assert claim is not None
        assert repository.fail_claim(
            claim,
            error_code="persistence_error",
            now=adapter_module.datetime.now(adapter_module.UTC),
        )
        second_job = _job(setup, 31)
    try:
        with sessions() as worker:
            with bind_execution_claim(ExecutionClaim(second_job, 1)):
                outcome = ingest_obsidian_vault(worker, config)
        assert (outcome.persisted, outcome.skipped, outcome.failed) == (0, 1, 0)
        assert [item.code for item in outcome.diagnostics] == ["retry_exhausted"]
        assert [item.retained for item in outcome.diagnostics] == [True]
    finally:
        with sessions.begin() as cleanup:
            cleanup.execute(
                text("DELETE FROM obsidian_ingest_events WHERE configured_source_digest=:source"),
                {"source": SOURCE_DIGEST},
            )
            cleanup.execute(
                text("DELETE FROM obsidian_ingest_state WHERE configured_source_digest=:source"),
                {"source": SOURCE_DIGEST},
            )
            cleanup.execute(
                text("DELETE FROM pgqueuer_jobs WHERE id = ANY(:ids)"),
                {"ids": [first_job, second_job]},
            )


def test_matching_obsidian_crash_gap_reconciles_existing_content(
    migration_db_session: Session, tmp_path: Path
) -> None:
    db_session = migration_db_session
    config, inbox = _adapter_config_for_test(tmp_path)
    inbox.joinpath("one.md").write_text(_note("one"))
    scanned = config.scanner().scan().notes[0]
    source_id = obsidian_source_id(SOURCE_DIGEST, scanned.path_digest, scanned.content_sha256)
    observation = ObsidianIngestRepository(db_session).observe_file_version(
        SOURCE_DIGEST,
        scanned.path_digest,
        scanned.content_sha256,
        observed_mtime_ns=scanned.identity.mtime_ns,
        observed_size=scanned.identity.size,
        now=adapter_module.datetime.now(adapter_module.UTC),
    )
    existing = Content(
        source_type=ContentSource.OBSIDIAN,
        source_id=source_id,
        source_url="https://example.test/shared",
        title="existing",
        markdown_content="one\n",
        content_hash="4" * 64,
        status="pending",
    )
    db_session.add(existing)
    db_session.flush()

    outcome = _run(db_session, config, 32)

    event = db_session.get(ObsidianIngestEvent, observation.event_id)
    assert (outcome.persisted, outcome.skipped, outcome.failed) == (0, 1, 0)
    assert event is not None and event.content_id == existing.id


def _adapter_config_for_test(tmp_path: Path) -> tuple[ObsidianAdapterConfig, Path]:
    approved = tmp_path / "approved"
    inbox = approved / "vault" / "Inbox"
    inbox.mkdir(parents=True)
    return (
        ObsidianAdapterConfig(
            configured_source_digest=SOURCE_DIGEST,
            vault_path=approved / "vault",
            ingest_folder="Inbox",
            allowed_roots=(approved,),
        ),
        inbox,
    )


def test_generated_only_scan_still_marks_unrelated_prior_note_missing(
    migration_db_session: Session, tmp_path: Path
) -> None:
    db_session = migration_db_session
    config, inbox = _adapter_config_for_test(tmp_path)
    prior = inbox / "prior.md"
    prior.write_text(_note("prior"))
    _run(db_session, config, 33)
    prior.unlink()
    inbox.joinpath("generated.md").write_text(
        "---\ngenerator: aca\naca_id: digest-1\n---\n# Generated\n"
    )

    outcome = _run(db_session, config, 34)

    state = db_session.query(ObsidianIngestState).one()
    assert outcome.skipped == 1 and outcome.failed == 0
    assert state.missing_since is not None


def test_canonical_url_race_has_one_primary(
    test_engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    approved = tmp_path / "approved"
    for folder, body in (("One", "one"), ("Two", "two")):
        target = approved / "vault" / folder
        target.mkdir(parents=True)
        target.joinpath("clip.md").write_text(_note(body))
    configs = (
        ObsidianAdapterConfig("9" * 64, approved / "vault", "One", (approved,)),
        ObsidianAdapterConfig("a" * 64, approved / "vault", "Two", (approved,)),
    )
    sessions = sessionmaker(bind=test_engine, expire_on_commit=False)
    with sessions.begin() as setup:
        jobs = (_job(setup, 35), _job(setup, 36))
    boundary = Barrier(2)
    real_lock = adapter_module._lock_canonical_identity

    def synchronize(session: Session, digest: str) -> None:
        boundary.wait(timeout=2)
        real_lock(session, digest)

    monkeypatch.setattr("src.ingestion.obsidian_adapter._lock_canonical_identity", synchronize)

    def run_worker(item):
        job_id, config = item
        with sessions() as worker:
            with bind_execution_claim(ExecutionClaim(job_id, 1)):
                return ingest_obsidian_vault(worker, config)

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = tuple(executor.map(run_worker, zip(jobs, configs, strict=True)))
        assert sum(item.persisted for item in outcomes) == 2
        with sessions() as verifier:
            rows = verifier.query(Content).filter(Content.source_type == "obsidian").all()
            assert sum(row.canonical_id is None for row in rows) == 1
            assert sum(row.canonical_id is not None for row in rows) == 1
    finally:
        with sessions.begin() as cleanup:
            cleanup.execute(text("DELETE FROM obsidian_ingest_events"))
            cleanup.execute(text("DELETE FROM obsidian_ingest_state"))
            cleanup.execute(text("DELETE FROM contents WHERE source_type='obsidian'"))
            cleanup.execute(
                text("DELETE FROM pgqueuer_jobs WHERE id=ANY(:ids)"),
                {"ids": list(jobs)},
            )


def test_claim_held_cancellation_attempt_completes_after_rollback(
    test_engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, inbox = _adapter_config_for_test(tmp_path)
    inbox.joinpath("one.md").write_text(_note("one"))
    scanned = config.scanner().scan().notes[0]
    source_id = obsidian_source_id(SOURCE_DIGEST, scanned.path_digest, scanned.content_sha256)
    sessions = sessionmaker(bind=test_engine, expire_on_commit=False)
    with sessions.begin() as setup:
        job_id = _job(setup, 37)
    claim_held = Event()
    cancel_started = Event()
    release_worker = Event()
    backend_pids: dict[str, int] = {}

    def cancel_while_claimed(session: Session, *_args, **_kwargs):
        backend_pids["worker"] = int(session.scalar(text("SELECT pg_backend_pid()")))
        claim_held.set()
        assert release_worker.wait(timeout=10)
        raise ClaimCancelled("cancelled")

    monkeypatch.setattr("src.ingestion.obsidian_adapter._persist_content", cancel_while_claimed)

    def worker():
        with sessions() as session:
            with bind_execution_claim(ExecutionClaim(job_id, 1)):
                return ingest_obsidian_vault(session, config)

    def canceller():
        with sessions.begin() as session:
            backend_pids["canceller"] = int(session.scalar(text("SELECT pg_backend_pid()")))
            cancel_started.set()
            session.execute(
                text(
                    "UPDATE pgqueuer_jobs "
                    "SET payload=jsonb_set(payload,'{cancel_requested}','true'::jsonb) "
                    "WHERE id=:job_id"
                ),
                {"job_id": job_id},
            )

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            worker_future = executor.submit(worker)
            assert claim_held.wait(timeout=10)
            cancel_future = executor.submit(canceller)
            assert cancel_started.wait(timeout=10)
            blockers: list[int] = []
            deadline = monotonic() + 10
            with sessions() as observer:
                while monotonic() < deadline:
                    blockers = [
                        int(pid)
                        for pid in (
                            observer.scalar(
                                text("SELECT pg_blocking_pids(:pid)"),
                                {"pid": backend_pids["canceller"]},
                            )
                            or []
                        )
                    ]
                    if backend_pids["worker"] in blockers:
                        break
                    sleep(0.05)
            try:
                assert backend_pids["worker"] in blockers
            finally:
                release_worker.set()
            with pytest.raises(ClaimCancelled):
                worker_future.result(timeout=10)
            cancel_future.result(timeout=10)
        with sessions() as verifier:
            assert verifier.query(Content).filter(Content.source_id == source_id).count() == 0
            assert (
                verifier.query(ObsidianIngestEvent)
                .filter(
                    ObsidianIngestEvent.configured_source_digest == SOURCE_DIGEST,
                    ObsidianIngestEvent.status == "claimed",
                )
                .count()
                == 0
            )
    finally:
        release_worker.set()
        cancel_started.set()
        with sessions.begin() as cleanup:
            cleanup.execute(
                text("DELETE FROM obsidian_ingest_events WHERE configured_source_digest=:source"),
                {"source": SOURCE_DIGEST},
            )
            cleanup.execute(
                text("DELETE FROM obsidian_ingest_state WHERE configured_source_digest=:source"),
                {"source": SOURCE_DIGEST},
            )
            cleanup.execute(
                text("DELETE FROM contents WHERE source_id=:source_id"),
                {"source_id": source_id},
            )
            cleanup.execute(text("DELETE FROM pgqueuer_jobs WHERE id=:id"), {"id": job_id})
