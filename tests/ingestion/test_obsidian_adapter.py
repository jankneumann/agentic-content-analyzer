"""Unit-facing behavior for the private Obsidian adapter foundation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

import src.ingestion.obsidian_adapter as adapter_module
from src.ingestion.content_references import collect_content_references
from src.ingestion.obsidian_adapter import ObsidianAdapterConfig, ingest_obsidian_vault
from src.ingestion.obsidian_parser import ClipParseLimits
from src.ingestion.obsidian_scanner import ScanLimits
from src.models.content import Content, ContentSource
from src.queue.execution_claim import ClaimCancelled, ExecutionClaim, bind_execution_claim

SOURCE_DIGEST = "7" * 64


def _note(body: str, *, url: str = "https://example.test/article?utm_source=private") -> str:
    return f"---\nsource_url: {url}\ncaptured_at: 2026-08-02T10:00:00Z\n---\n{body}\n"


def _job(session: Session) -> int:
    return int(
        session.scalar(
            text(
                "INSERT INTO pgqueuer_jobs "
                "(entrypoint, payload, status, claim_generation, claim_protocol_version) "
                "VALUES ('ingestion.execute', CAST(:payload AS jsonb), 'in_progress', 1, 2) "
                "RETURNING id"
            ),
            {"payload": json.dumps({"cancel_requested": False})},
        )
    )


def _config(tmp_path: Path) -> tuple[ObsidianAdapterConfig, Path]:
    approved = tmp_path / "approved"
    inbox = approved / "vault" / "Inbox"
    inbox.mkdir(parents=True)
    return (
        ObsidianAdapterConfig(
            configured_source_digest=SOURCE_DIGEST,
            vault_path=approved / "vault",
            ingest_folder="Inbox",
            allowed_roots=(approved,),
            scan_limits=ScanLimits(settle_seconds=0),
        ),
        inbox,
    )


def _cleanup_committed_adapter_rows(sessions, job_id: int) -> None:
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
        cleanup.execute(text("DELETE FROM pgqueuer_jobs WHERE id = :job_id"), {"job_id": job_id})


def test_adapter_persists_authoritative_markdown_with_bounded_outcome(
    db_session: Session, tmp_path: Path
) -> None:
    config, inbox = _config(tmp_path)
    original = _note("# Saved\n\nannotation [[Topic|label]]")
    inbox.joinpath("private-note.md").write_text(original)
    job_id = _job(db_session)

    with bind_execution_claim(ExecutionClaim(job_id=job_id, claim_generation=1)):
        outcome = ingest_obsidian_vault(db_session, config)

    content = db_session.query(Content).one()
    assert (outcome.persisted, outcome.skipped, outcome.failed) == (1, 0, 0)
    assert outcome.content_ids == (content.id,)
    assert content.source_type is ContentSource.OBSIDIAN
    assert content.markdown_content == "# Saved\n\nannotation label\n"
    assert content.source_url == "https://example.test/article"
    assert content.raw_content is None
    assert "private-note.md" not in repr(outcome)
    assert original not in repr(outcome)


def test_unavailable_mount_returns_only_stable_diagnostic(
    db_session: Session, tmp_path: Path
) -> None:
    approved = tmp_path / "approved"
    approved.mkdir()
    config = ObsidianAdapterConfig(
        configured_source_digest=SOURCE_DIGEST,
        vault_path=approved / "missing",
        ingest_folder="Inbox",
        allowed_roots=(approved,),
    )
    job_id = _job(db_session)

    with bind_execution_claim(ExecutionClaim(job_id=job_id, claim_generation=1)):
        outcome = ingest_obsidian_vault(db_session, config)

    assert (outcome.persisted, outcome.skipped, outcome.failed) == (0, 0, 1)
    assert [item.code for item in outcome.diagnostics] == ["source_unavailable"]
    assert str(config.vault_path) not in repr(outcome)


def test_parse_failure_is_bounded_and_does_not_abort_safe_sibling(
    db_session: Session, tmp_path: Path
) -> None:
    config, inbox = _config(tmp_path)
    inbox.joinpath("a-invalid.md").write_bytes(b"\xffprivate")
    inbox.joinpath("b-valid.md").write_text(_note("valid"))
    job_id = _job(db_session)

    with bind_execution_claim(ExecutionClaim(job_id=job_id, claim_generation=1)):
        outcome = ingest_obsidian_vault(db_session, config)

    assert (outcome.persisted, outcome.skipped, outcome.failed) == (1, 0, 1)
    assert "invalid_encoding" in [item.code for item in outcome.diagnostics]
    assert b"\xffprivate".hex() not in repr(outcome)


def test_persistence_failure_is_bounded_and_redacted(
    test_engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, inbox = _config(tmp_path)
    inbox.joinpath("clip.md").write_text(_note("safe body"))
    sessions = sessionmaker(bind=test_engine, expire_on_commit=False)
    with sessions.begin() as setup:
        job_id = _job(setup)

    def fail_persistence(*_args, **_kwargs):
        raise RuntimeError("database exploded at /private/vault/clip.md with safe body")

    monkeypatch.setattr("src.ingestion.obsidian_adapter._persist_content", fail_persistence)
    try:
        with sessions() as worker:
            with bind_execution_claim(ExecutionClaim(job_id=job_id, claim_generation=1)):
                outcome = ingest_obsidian_vault(worker, config)

        assert (outcome.persisted, outcome.failed) == (0, 1)
        assert [item.code for item in outcome.diagnostics] == ["persistence_error"]
        assert "/private/vault" not in repr(outcome)
        assert "safe body" not in repr(outcome)
    finally:
        _cleanup_committed_adapter_rows(sessions, job_id)


def test_cancellation_before_persistence_rolls_back_note_claim(
    test_engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, inbox = _config(tmp_path)
    inbox.joinpath("clip.md").write_text(_note("body"))
    sessions = sessionmaker(bind=test_engine, expire_on_commit=False)
    with sessions.begin() as setup:
        job_id = _job(setup)
    saw_claim = False

    def cancel_during_persistence(session, *_args, **_kwargs):
        nonlocal saw_claim
        claimed = session.scalar(
            text("SELECT count(*) FROM obsidian_ingest_events WHERE status = 'claimed'")
        )
        saw_claim = bool(claimed)
        raise ClaimCancelled("cancelled")

    monkeypatch.setattr(
        "src.ingestion.obsidian_adapter._persist_content", cancel_during_persistence
    )
    try:
        with sessions() as worker:
            with bind_execution_claim(ExecutionClaim(job_id=job_id, claim_generation=1)):
                with pytest.raises(ClaimCancelled):
                    ingest_obsidian_vault(worker, config)

        with sessions() as verifier:
            claimed = verifier.scalar(
                text("SELECT count(*) FROM obsidian_ingest_events WHERE status = 'claimed'")
            )
        assert saw_claim is True
        assert claimed == 0
    finally:
        _cleanup_committed_adapter_rows(sessions, job_id)


def test_cancellation_between_candidates_leaves_no_permanent_claim(
    db_session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, inbox = _config(tmp_path)
    inbox.joinpath("a.md").write_text(_note("first"))
    inbox.joinpath("b.md").write_text(_note("second"))
    job_id = _job(db_session)
    real_check = adapter_module.check_execution_claim
    real_persist = adapter_module._persist_content
    first_persisted = False

    def track_persistence(*args, **kwargs):
        nonlocal first_persisted
        result = real_persist(*args, **kwargs)
        first_persisted = True
        return result

    def cancel_between(session):
        if first_persisted:
            raise ClaimCancelled("cancelled")
        return real_check(session)

    monkeypatch.setattr("src.ingestion.obsidian_adapter._persist_content", track_persistence)
    monkeypatch.setattr("src.ingestion.obsidian_adapter.check_execution_claim", cancel_between)
    with bind_execution_claim(ExecutionClaim(job_id=job_id, claim_generation=1)):
        with pytest.raises(ClaimCancelled):
            ingest_obsidian_vault(db_session, config)

    assert db_session.scalar(text("SELECT count(*) FROM contents")) == 1
    assert (
        db_session.scalar(
            text("SELECT count(*) FROM obsidian_ingest_events WHERE status = 'claimed'")
        )
        == 0
    )


def test_success_and_failure_do_not_mutate_vault_entries(
    db_session: Session, tmp_path: Path
) -> None:
    config, inbox = _config(tmp_path)
    inbox.joinpath("good.md").write_text(_note("body"))
    inbox.joinpath("bad.md").write_bytes(b"\xffprivate")
    before = {path.name: path.read_bytes() for path in inbox.iterdir()}
    job_id = _job(db_session)

    with bind_execution_claim(ExecutionClaim(job_id=job_id, claim_generation=1)):
        ingest_obsidian_vault(db_session, config)

    after = {path.name: path.read_bytes() for path in inbox.iterdir()}
    assert after == before


def test_generated_export_note_is_counted_as_skipped(db_session: Session, tmp_path: Path) -> None:
    config, inbox = _config(tmp_path)
    inbox.joinpath("generated.md").write_text(
        "---\ngenerator: aca\naca_id: digest-1\n---\n# Generated\n"
    )
    job_id = _job(db_session)

    with bind_execution_claim(ExecutionClaim(job_id=job_id, claim_generation=1)):
        outcome = ingest_obsidian_vault(db_session, config)

    assert (outcome.persisted, outcome.skipped, outcome.failed) == (0, 1, 0)
    assert [item.code for item in outcome.diagnostics] == ["generated_content"]


def test_failed_note_commit_does_not_publish_rolled_back_content_reference(
    test_engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, inbox = _config(tmp_path)
    inbox.joinpath("clip.md").write_text(_note("body"))
    sessions = sessionmaker(bind=test_engine, expire_on_commit=False)
    with sessions.begin() as setup:
        job_id = _job(setup)

    def fail_commit(session: Session) -> None:
        session.rollback()
        raise RuntimeError("private commit failure")

    monkeypatch.setattr("src.ingestion.obsidian_adapter._commit_transaction", fail_commit)
    try:
        with sessions() as worker, collect_content_references() as references:
            with bind_execution_claim(ExecutionClaim(job_id=job_id, claim_generation=1)):
                outcome = ingest_obsidian_vault(worker, config)
            assert references == set()
        assert outcome.failed == 1
        assert [item.code for item in outcome.diagnostics] == ["persistence_error"]
    finally:
        _cleanup_committed_adapter_rows(sessions, job_id)


def test_adapter_url_limit_matches_content_storage_boundary(tmp_path: Path) -> None:
    config, _ = _config(tmp_path)
    assert config.parse_limits.max_url_chars == 2_000

    with pytest.raises(ValueError, match="invalid_parse_limits"):
        ObsidianAdapterConfig(
            configured_source_digest=SOURCE_DIGEST,
            vault_path=tmp_path / "vault",
            ingest_folder="Inbox",
            allowed_roots=(tmp_path,),
            parse_limits=ClipParseLimits(max_url_chars=2_001),
        )


def test_two_thousand_character_url_persists_within_content_column(
    db_session: Session, tmp_path: Path
) -> None:
    config, inbox = _config(tmp_path)
    prefix = "https://example.test/"
    source_url = prefix + ("a" * (2_000 - len(prefix)))
    inbox.joinpath("clip.md").write_text(_note("body", url=source_url))
    job_id = _job(db_session)

    with bind_execution_claim(ExecutionClaim(job_id, 1)):
        outcome = ingest_obsidian_vault(db_session, config)

    assert outcome.persisted == 1
    assert db_session.query(Content).one().source_url == source_url
