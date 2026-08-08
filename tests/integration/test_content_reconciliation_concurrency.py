"""PostgreSQL concurrency coverage for generation-guarded Content writes."""

from __future__ import annotations

import json
from contextlib import contextmanager
from unittest.mock import AsyncMock

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.agents.base import AgentResponse
from src.models.content import Content, ContentSource, ContentStatus
from src.models.summary import Summary, SummaryData
from src.processors.summarizer import ContentSummarizer
from src.queue.execution_claim import (
    ClaimCancelled,
    ClaimSuperseded,
    ContentExecutionPhase,
    ExecutionClaim,
    acquire_content_execution,
    bind_execution_claim,
    guard_content_execution,
)


def test_content_transaction_lock_excludes_second_connection(test_db_engine: Engine) -> None:
    from src.queue.content_execution_lock import (
        _CONTENT_EXECUTION_LOCK_NAMESPACE,
        lock_content_transaction,
    )

    holder_connection = test_db_engine.connect()
    holder_transaction = holder_connection.begin()
    holder = Session(bind=holder_connection)
    contender = test_db_engine.connect()
    try:
        lock_content_transaction(holder, 1701)
        acquired_while_held = contender.execute(
            sa.text("SELECT pg_try_advisory_xact_lock(:namespace, :content_id)"),
            {"namespace": _CONTENT_EXECUTION_LOCK_NAMESPACE, "content_id": 1701},
        ).scalar_one()
        assert acquired_while_held is False
        contender.rollback()

        holder_transaction.rollback()
        acquired_after_end = contender.execute(
            sa.text("SELECT pg_try_advisory_xact_lock(:namespace, :content_id)"),
            {"namespace": _CONTENT_EXECUTION_LOCK_NAMESPACE, "content_id": 1701},
        ).scalar_one()
        assert acquired_after_end is True
        contender.rollback()
    finally:
        holder.close()
        if holder_transaction.is_active:
            holder_transaction.rollback()
        holder_connection.close()
        contender.close()


@pytest.fixture(scope="module", autouse=True)
def _queue_claim_table(test_db_engine: Engine):
    with test_db_engine.begin() as connection:
        connection.execute(
            sa.text(
                """
                CREATE TABLE pgqueuer_jobs (
                    id BIGSERIAL PRIMARY KEY,
                    entrypoint TEXT NOT NULL,
                    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                    status TEXT NOT NULL,
                    claim_generation BIGINT NOT NULL,
                    claim_protocol_version SMALLINT NOT NULL
                )
                """
            )
        )
    yield
    with test_db_engine.begin() as connection:
        connection.execute(sa.text("DROP TABLE pgqueuer_jobs"))


def _create_content(session: Session, *, source_id: str) -> Content:
    content = Content(
        source_type=ContentSource.WEBPAGE,
        source_id=source_id,
        source_url=f"https://example.com/{source_id}",
        title=source_id,
        markdown_content="# pending",
        content_hash=source_id,
        status=ContentStatus.PENDING,
    )
    session.add(content)
    session.flush()
    return content


def _create_claimed_job(session: Session, *, content_id: int) -> int:
    job_id = session.execute(
        sa.text(
            """
            INSERT INTO pgqueuer_jobs (
                entrypoint, payload, status, claim_generation, claim_protocol_version
            )
            VALUES (
                'ingestion.execute',
                CAST(:payload AS jsonb),
                'in_progress', 1, 2
            )
            RETURNING id
            """
        ),
        {"payload": json.dumps({"content_id": content_id, "cancel_requested": False})},
    ).scalar_one()
    return int(job_id)


def test_same_operation_new_generation_renews_failed_parsing_owner(db_session: Session) -> None:
    content = _create_content(db_session, source_id="renew-owner")
    job_id = _create_claimed_job(db_session, content_id=content.id)

    with bind_execution_claim(ExecutionClaim(job_id=job_id, claim_generation=1)):
        acquired = acquire_content_execution(
            db_session,
            content.id,
            ContentExecutionPhase.PARSING,
        )
        assert acquired.status is ContentStatus.PARSING
        assert acquired.status_operation_id == job_id
        assert acquired.status_claim_generation == 1
        assert acquired.status_owner_version == 1
        acquired.status = ContentStatus.FAILED
        acquired.status_owner_version = 2
        db_session.flush()

    db_session.execute(
        sa.text("UPDATE pgqueuer_jobs SET claim_generation = 2 WHERE id = :job_id"),
        {"job_id": job_id},
    )

    with bind_execution_claim(ExecutionClaim(job_id=job_id, claim_generation=2)):
        renewed = acquire_content_execution(
            db_session,
            content.id,
            ContentExecutionPhase.PARSING,
        )

    assert renewed.status is ContentStatus.PARSING
    assert renewed.status_operation_id == job_id
    assert renewed.status_claim_generation == 2
    assert renewed.status_owner_version == 3


def test_cancelled_and_superseded_claims_cannot_reach_domain_commit(db_session: Session) -> None:
    content = _create_content(db_session, source_id="stale-commit")
    job_id = _create_claimed_job(db_session, content_id=content.id)
    with bind_execution_claim(ExecutionClaim(job_id=job_id, claim_generation=1)):
        acquire_content_execution(db_session, content.id, ContentExecutionPhase.PARSING)
        db_session.flush()

    db_session.execute(
        sa.text("UPDATE pgqueuer_jobs SET status = 'failed' WHERE id = :job_id"),
        {"job_id": job_id},
    )
    with bind_execution_claim(ExecutionClaim(job_id=job_id, claim_generation=1)):
        with pytest.raises(ClaimSuperseded):
            guard_content_execution(db_session, content.id, ContentExecutionPhase.PARSING)

    db_session.execute(
        sa.text(
            """
            UPDATE pgqueuer_jobs
            SET status = 'in_progress', payload = payload || '{"cancel_requested": true}'::jsonb
            WHERE id = :job_id
            """
        ),
        {"job_id": job_id},
    )
    with bind_execution_claim(ExecutionClaim(job_id=job_id, claim_generation=1)):
        with pytest.raises(ClaimCancelled):
            guard_content_execution(db_session, content.id, ContentExecutionPhase.PARSING)

    db_session.refresh(content)
    assert content.status is ContentStatus.PARSING
    assert content.status_claim_generation == 1


def test_legacy_protocol_claim_cannot_acquire_owned_content(db_session: Session) -> None:
    content = _create_content(db_session, source_id="legacy-protocol")
    job_id = _create_claimed_job(db_session, content_id=content.id)
    db_session.execute(
        sa.text("UPDATE pgqueuer_jobs SET claim_protocol_version = 1 WHERE id = :job_id"),
        {"job_id": job_id},
    )

    with bind_execution_claim(
        ExecutionClaim(job_id=job_id, claim_generation=1, claim_protocol_version=1)
    ):
        with pytest.raises(ClaimSuperseded):
            acquire_content_execution(db_session, content.id, ContentExecutionPhase.PARSING)

    db_session.refresh(content)
    assert content.status is ContentStatus.PENDING
    assert content.status_operation_id is None


@pytest.mark.asyncio
async def test_url_extraction_success_clears_exact_owner(db_session: Session, monkeypatch) -> None:
    from src.services.url_extractor import URLExtractor

    content = _create_content(db_session, source_id="url-success")
    job_id = _create_claimed_job(db_session, content_id=content.id)
    with bind_execution_claim(ExecutionClaim(job_id=job_id, claim_generation=1)):
        owned = acquire_content_execution(
            db_session,
            content.id,
            ContentExecutionPhase.PARSING,
        )
        owned.status = ContentStatus.FAILED
        owned.error_message = "Content extraction failed. Please try again later."
        owned.status_owner_version = 2
        db_session.commit()
    db_session.execute(
        sa.text("UPDATE pgqueuer_jobs SET claim_generation = 2 WHERE id = :job_id"),
        {"job_id": job_id},
    )
    db_session.commit()
    extractor = URLExtractor(db_session)
    monkeypatch.setattr(
        extractor,
        "_fetch_url",
        AsyncMock(return_value=("<p>fresh</p>", "https://example.com/final")),
    )
    monkeypatch.setattr(
        extractor,
        "_parse_html",
        AsyncMock(return_value=("# fresh", {"title": "Fresh"})),
    )

    with bind_execution_claim(ExecutionClaim(job_id=job_id, claim_generation=2)):
        result = await extractor.extract_content(content.id, resume_owned=True)

    assert result.status is ContentStatus.PARSED
    assert result.markdown_content == "# fresh"
    assert result.error_message is None
    assert result.status_operation_id is None
    assert result.status_claim_generation is None


@pytest.mark.asyncio
async def test_url_extraction_failure_retains_exact_owner(
    test_db_engine: Engine, monkeypatch
) -> None:
    from src.services.url_extractor import URLExtractor

    SessionLocal = sessionmaker(bind=test_db_engine)
    setup = SessionLocal()
    content = _create_content(setup, source_id="url-failure")
    job_id = _create_claimed_job(setup, content_id=content.id)
    content_id = content.id
    setup.commit()
    setup.close()
    writer = SessionLocal()
    extractor = URLExtractor(writer)
    monkeypatch.setattr(
        extractor,
        "_fetch_url",
        AsyncMock(side_effect=RuntimeError("network failed")),
    )

    with bind_execution_claim(ExecutionClaim(job_id=job_id, claim_generation=1)):
        with pytest.raises(RuntimeError, match="network failed"):
            await extractor.extract_content(content_id)

    writer.close()
    with SessionLocal() as verifier:
        persisted = verifier.get(Content, content_id)
        assert persisted is not None
        assert persisted.status is ContentStatus.FAILED
        assert persisted.status_operation_id == job_id
        assert persisted.status_claim_generation == 1
        assert persisted.status_operation_phase == "parsing"
        assert persisted.status_owner_version == 2


@pytest.mark.asyncio
async def test_url_extraction_superseded_during_compute_cannot_commit(
    test_db_engine: Engine, monkeypatch
) -> None:
    from src.services.url_extractor import URLExtractor

    SessionLocal = sessionmaker(bind=test_db_engine)
    setup = SessionLocal()
    content = _create_content(setup, source_id="url-superseded")
    job_id = _create_claimed_job(setup, content_id=content.id)
    content_id = content.id
    setup.commit()
    setup.close()

    writer = SessionLocal()
    extractor = URLExtractor(writer)
    monkeypatch.setattr(
        extractor,
        "_fetch_url",
        AsyncMock(return_value=("<p>fresh</p>", "https://example.com/final")),
    )

    async def supersede_during_parse(_html: str, _url: str):
        with SessionLocal.begin() as superseder:
            superseder.execute(
                sa.text("UPDATE pgqueuer_jobs SET claim_generation = 2 WHERE id = :job_id"),
                {"job_id": job_id},
            )
        return "# fresh", {"title": "Fresh"}

    monkeypatch.setattr(extractor, "_parse_html", supersede_during_parse)

    with bind_execution_claim(ExecutionClaim(job_id=job_id, claim_generation=1)):
        with pytest.raises(ClaimSuperseded):
            await extractor.extract_content(content_id)

    writer.close()
    with SessionLocal() as verifier:
        persisted = verifier.get(Content, content_id)
        assert persisted is not None
        assert persisted.status is ContentStatus.PARSING
        assert persisted.markdown_content == "# pending"
        assert persisted.status_claim_generation == 1
        generation = verifier.execute(
            sa.text("SELECT claim_generation FROM pgqueuer_jobs WHERE id = :job_id"),
            {"job_id": job_id},
        ).scalar_one()
        assert generation == 2


@pytest.mark.asyncio
async def test_url_extraction_content_displaced_during_compute_cannot_commit(
    test_db_engine: Engine, monkeypatch
) -> None:
    from src.services.url_extractor import URLExtractor

    SessionLocal = sessionmaker(bind=test_db_engine)
    setup = SessionLocal()
    content = _create_content(setup, source_id="url-content-displaced")
    job_id = _create_claimed_job(setup, content_id=content.id)
    content_id = content.id
    setup.commit()
    setup.close()

    writer = SessionLocal()
    extractor = URLExtractor(writer)
    monkeypatch.setattr(
        extractor,
        "_fetch_url",
        AsyncMock(return_value=("<p>fresh</p>", "https://example.com/final")),
    )

    async def displace_during_parse(_html: str, _url: str):
        with SessionLocal.begin() as displacer:
            displacer.execute(
                sa.text(
                    """
                    UPDATE contents
                    SET status = 'pending', status_operation_id = NULL,
                        status_claim_generation = NULL, status_operation_phase = NULL,
                        status_owner_version = NULL
                    WHERE id = :content_id
                    """
                ),
                {"content_id": content_id},
            )
        return "# fresh", {"title": "Fresh"}

    monkeypatch.setattr(extractor, "_parse_html", displace_during_parse)

    with bind_execution_claim(ExecutionClaim(job_id=job_id, claim_generation=1)):
        with pytest.raises(ClaimSuperseded):
            await extractor.extract_content(content_id)

    writer.close()
    with SessionLocal() as verifier:
        persisted = verifier.get(Content, content_id)
        assert persisted is not None
        assert persisted.status is ContentStatus.PENDING
        assert persisted.markdown_content == "# pending"
        assert persisted.status_operation_id is None


def test_summary_commit_records_exact_provenance(db_session: Session, monkeypatch) -> None:
    content = _create_content(db_session, source_id="summary-provenance")
    content.status = ContentStatus.PARSED
    db_session.flush()
    job_id = _create_claimed_job(db_session, content_id=content.id)

    class Agent:
        def summarize_content(self, _content: Content) -> AgentResponse:
            return AgentResponse(
                success=True,
                data=SummaryData(
                    content_id=content.id,
                    executive_summary="Exact owner",
                    key_themes=[],
                    strategic_insights=[],
                    technical_details=[],
                    actionable_items=[],
                    notable_quotes=[],
                    relevance_scores={},
                    agent_framework="test",
                    model_used="test",
                ),
            )

    @contextmanager
    def get_test_db():
        yield db_session

    monkeypatch.setattr("src.processors.summarizer.get_db", get_test_db)
    summarizer = ContentSummarizer(agent=Agent())

    with bind_execution_claim(ExecutionClaim(job_id=job_id, claim_generation=1)):
        assert summarizer.summarize_content(content.id) is True

    summary = db_session.query(Summary).filter(Summary.content_id == content.id).one()
    assert summary.operation_id == job_id
    assert summary.operation_claim_generation == 1
    db_session.refresh(content)
    assert content.status is ContentStatus.COMPLETED
    assert content.status_operation_id is None


def test_summary_superseded_during_compute_inserts_nothing(
    test_db_engine: Engine, monkeypatch
) -> None:
    SessionLocal = sessionmaker(bind=test_db_engine)
    setup = SessionLocal()
    content = _create_content(setup, source_id="summary-superseded")
    content.status = ContentStatus.PARSED
    setup.flush()
    job_id = _create_claimed_job(setup, content_id=content.id)
    content_id = content.id
    setup.commit()
    setup.close()

    writer = SessionLocal()

    class Agent:
        def summarize_content(self, _content: Content) -> AgentResponse:
            with SessionLocal.begin() as superseder:
                superseder.execute(
                    sa.text("UPDATE pgqueuer_jobs SET claim_generation = 2 WHERE id = :job_id"),
                    {"job_id": job_id},
                )
            return AgentResponse(
                success=True,
                data=SummaryData(
                    content_id=content.id,
                    executive_summary="Must not persist",
                    key_themes=[],
                    strategic_insights=[],
                    technical_details=[],
                    actionable_items=[],
                    notable_quotes=[],
                    relevance_scores={},
                    agent_framework="test",
                    model_used="test",
                ),
            )

    @contextmanager
    def get_test_db():
        yield writer

    monkeypatch.setattr("src.processors.summarizer.get_db", get_test_db)
    summarizer = ContentSummarizer(agent=Agent())

    with bind_execution_claim(ExecutionClaim(job_id=job_id, claim_generation=1)):
        with pytest.raises(ClaimSuperseded):
            summarizer.summarize_content(content_id)

    writer.close()
    with SessionLocal() as verifier:
        assert verifier.query(Summary).filter(Summary.content_id == content_id).count() == 0
        persisted = verifier.get(Content, content_id)
        assert persisted is not None
        assert persisted.status is ContentStatus.PROCESSING
        assert persisted.status_claim_generation == 1
        generation = verifier.execute(
            sa.text("SELECT claim_generation FROM pgqueuer_jobs WHERE id = :job_id"),
            {"job_id": job_id},
        ).scalar_one()
        assert generation == 2


def test_summary_content_displaced_during_compute_inserts_nothing(
    test_db_engine: Engine, monkeypatch
) -> None:
    SessionLocal = sessionmaker(bind=test_db_engine)
    setup = SessionLocal()
    content = _create_content(setup, source_id="summary-content-displaced")
    content.status = ContentStatus.PARSED
    setup.flush()
    job_id = _create_claimed_job(setup, content_id=content.id)
    content_id = content.id
    setup.commit()
    setup.close()

    writer = SessionLocal()

    class Agent:
        def summarize_content(self, _content: Content) -> AgentResponse:
            with SessionLocal.begin() as displacer:
                displacer.execute(
                    sa.text(
                        """
                        UPDATE contents
                        SET status = 'parsed', status_operation_id = NULL,
                            status_claim_generation = NULL, status_operation_phase = NULL,
                            status_owner_version = NULL
                        WHERE id = :content_id
                        """
                    ),
                    {"content_id": content_id},
                )
            return AgentResponse(
                success=True,
                data=SummaryData(
                    content_id=content_id,
                    executive_summary="Must not persist",
                    key_themes=[],
                    strategic_insights=[],
                    technical_details=[],
                    actionable_items=[],
                    notable_quotes=[],
                    relevance_scores={},
                    agent_framework="test",
                    model_used="test",
                ),
            )

    @contextmanager
    def get_test_db():
        yield writer

    monkeypatch.setattr("src.processors.summarizer.get_db", get_test_db)
    summarizer = ContentSummarizer(agent=Agent())

    with bind_execution_claim(ExecutionClaim(job_id=job_id, claim_generation=1)):
        with pytest.raises(ClaimSuperseded):
            summarizer.summarize_content(content_id)

    writer.close()
    with SessionLocal() as verifier:
        assert verifier.query(Summary).filter(Summary.content_id == content_id).count() == 0
        persisted = verifier.get(Content, content_id)
        assert persisted is not None
        assert persisted.status is ContentStatus.PARSED
        assert persisted.status_operation_id is None
        generation = verifier.execute(
            sa.text("SELECT claim_generation FROM pgqueuer_jobs WHERE id = :job_id"),
            {"job_id": job_id},
        ).scalar_one()
        assert generation == 1
