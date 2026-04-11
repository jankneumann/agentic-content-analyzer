"""Tests for KBQAService and KBHealthService.

Covers Q&A query flow (basic, empty, file-back, truncation) and health
checks (stale detection, merge candidates, coverage gaps, lint_fix).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.topic import Topic, TopicNote, TopicStatus
from src.services.kb_health import KBHealthService
from src.services.kb_qa import KBQAService

# ---------------------------------------------------------------------- #
# Fixtures
# ---------------------------------------------------------------------- #


@pytest.fixture
def mock_llm_response():
    """A stub LLMResponse-like object with a default answer."""
    return MagicMock(
        text="Compiled answer referencing topic articles.",
        input_tokens=50,
        output_tokens=150,
    )


@pytest.fixture
def qa_service(db_session, mock_llm_response):
    """KB Q&A service with mocked LLM router."""
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value=mock_llm_response)
    return KBQAService(db_session, llm_router=mock_llm)


@pytest.fixture
def health_service(db_session):
    """KB health service — no mocks needed."""
    return KBHealthService(db_session)


def _make_topic(
    db_session,
    *,
    slug: str,
    name: str,
    category: str = "ml_ai",
    status: TopicStatus = TopicStatus.ACTIVE,
    summary: str = "",
    article_md: str = "",
    mention_count: int = 1,
    relevance_score: float = 0.5,
    last_evidence_at: datetime | None = None,
    last_compiled_at: datetime | None = None,
    trend: str | None = "growing",
) -> Topic:
    """Create and commit a Topic into the test session."""
    topic = Topic(
        slug=slug,
        name=name,
        category=category,
        status=status,
        summary=summary,
        article_md=article_md,
        article_version=1,
        trend=trend,
        mention_count=mention_count,
        relevance_score=relevance_score,
        last_evidence_at=last_evidence_at,
        last_compiled_at=last_compiled_at,
    )
    db_session.add(topic)
    db_session.commit()
    db_session.refresh(topic)
    return topic


# ====================================================================== #
# KBQAService
# ====================================================================== #


class TestKBQABasic:
    @pytest.mark.asyncio
    async def test_query_returns_answer_for_matched_topic(self, qa_service, db_session):
        _make_topic(
            db_session,
            slug="rag-architecture",
            name="RAG Architecture",
            summary="Retrieval-augmented generation patterns.",
            article_md="# RAG\n\nRetrieval-augmented generation combines retrieval and generation.",
            relevance_score=0.8,
        )

        result = await qa_service.query("What is RAG architecture?")

        assert result["topics"] == ["rag-architecture"]
        assert result["answer"].startswith("Compiled answer")
        assert result["truncated"] is False
        qa_service.llm_router.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_no_match_returns_empty_answer(self, qa_service):
        """kb.8: No relevant topics -> empty answer with message."""
        result = await qa_service.query("anything unrelated here")
        assert result["answer"] == ""
        assert result["topics"] == []
        assert "No relevant KB content" in (result.get("message") or "")
        # LLM should NOT be called when no topics match
        qa_service.llm_router.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_query_empty_question(self, qa_service):
        """An empty question short-circuits without an LLM call."""
        result = await qa_service.query("   ")
        assert result["answer"] == ""
        assert result["topics"] == []
        qa_service.llm_router.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_query_excludes_archived_topics(self, qa_service, db_session):
        _make_topic(
            db_session,
            slug="archived-rag",
            name="Archived RAG",
            summary="Old RAG material",
            article_md="Old RAG details.",
            status=TopicStatus.ARCHIVED,
        )
        result = await qa_service.query("RAG")
        assert result["topics"] == []
        assert result["answer"] == ""

    @pytest.mark.asyncio
    async def test_query_file_back_creates_insight_notes(self, qa_service, db_session):
        """kb.8: file_back=True records an insight note on each referenced topic."""
        topic = _make_topic(
            db_session,
            slug="agents",
            name="Agents",
            summary="Autonomous agent loops",
            article_md="Agents can plan and act.",
        )

        result = await qa_service.query(
            "How do agents work?",
            file_back=True,
        )
        assert result["topics"] == ["agents"]

        notes = db_session.query(TopicNote).filter_by(topic_id=topic.id).all()
        assert len(notes) == 1
        note = notes[0]
        note_type = note.note_type.value if hasattr(note.note_type, "value") else note.note_type
        assert note_type == "insight"
        assert note.author == "system"
        assert "How do agents work" in note.content

    @pytest.mark.asyncio
    async def test_query_truncation_at_max_topics(self, qa_service, db_session):
        """kb.8: >10 matching topics -> top 10 used, truncated=True."""
        for idx in range(15):
            _make_topic(
                db_session,
                slug=f"llm-topic-{idx}",
                name=f"LLM topic {idx}",
                summary="Large language models and LLM architectures.",
                article_md=f"LLM details number {idx}.",
                relevance_score=1.0 - (idx * 0.01),
            )

        result = await qa_service.query("llm")
        assert len(result["topics"]) == 10
        assert result["truncated"] is True
        assert "omitted" in result["answer"]

    @pytest.mark.asyncio
    async def test_query_llm_failure_propagates(self, qa_service, db_session):
        """kb.8: LLM failure raises — route layer maps to 502."""
        _make_topic(
            db_session,
            slug="vector-db",
            name="Vector DB",
            summary="Vector database performance.",
            article_md="Pgvector, Qdrant, Milvus overview.",
        )
        qa_service.llm_router.generate = AsyncMock(side_effect=RuntimeError("LLM provider down"))
        with pytest.raises(RuntimeError, match="LLM provider down"):
            await qa_service.query("vector")


# ====================================================================== #
# KBHealthService
# ====================================================================== #


class TestKBHealthLint:
    def test_lint_detects_stale_topics(self, health_service, db_session):
        """kb.9: Topics with no evidence in >threshold days flagged stale."""
        now = datetime.now(UTC).replace(tzinfo=None)
        stale_dt = now - timedelta(days=60)

        _make_topic(
            db_session,
            slug="fresh-topic",
            name="Fresh",
            article_md="Fresh content",
            last_evidence_at=now,
            last_compiled_at=now,
        )
        _make_topic(
            db_session,
            slug="old-topic",
            name="Old",
            article_md="Old content",
            last_evidence_at=stale_dt,
            last_compiled_at=stale_dt,
        )

        findings = health_service.lint()
        assert "old-topic" in findings["stale"]
        assert "fresh-topic" not in findings["stale"]
        assert "# KB Health Report" in findings["report_md"]
        assert "Stale Topics" in findings["report_md"]

    def test_lint_detects_merge_candidates(self, health_service, db_session):
        """kb.9: Topic pairs with similar articles flagged as merges."""
        same_article = "rag retrieval augmented generation vector search llms embeddings"
        _make_topic(
            db_session,
            slug="rag-one",
            name="RAG One",
            article_md=same_article,
        )
        _make_topic(
            db_session,
            slug="rag-two",
            name="RAG Two",
            article_md=same_article,
        )

        findings = health_service.lint()
        pairs = findings["merge_candidates"]
        assert ("rag-one", "rag-two") in pairs or ("rag-two", "rag-one") in pairs
        assert "Merge Candidates" in findings["report_md"]

    def test_lint_detects_coverage_gaps(self, health_service, db_session):
        """kb.9: Categories with < min_topics flagged as coverage gaps."""
        # Only one ML topic — all other categories will be gaps
        _make_topic(
            db_session,
            slug="solo-ml",
            name="Solo ML",
            category="ml_ai",
        )
        findings = health_service.lint()
        gaps = findings["coverage_gaps"]
        assert "ml_ai" in gaps
        assert "security" in gaps
        assert "Coverage Gaps" in findings["report_md"]

    def test_lint_no_coverage_gap_when_min_met(self, health_service, db_session):
        """kb.9: Categories meeting the minimum are not flagged."""
        minimum = health_service.settings.kb_min_topics_per_category
        for idx in range(minimum):
            _make_topic(
                db_session,
                slug=f"ml-{idx}",
                name=f"ML {idx}",
                category="ml_ai",
            )
        findings = health_service.lint()
        assert "ml_ai" not in findings["coverage_gaps"]

    def test_lint_produces_quality_scores(self, health_service, db_session):
        now = datetime.now(UTC).replace(tzinfo=None)
        _make_topic(
            db_session,
            slug="scored",
            name="Scored",
            article_md="A" * 500,
            mention_count=5,
            last_evidence_at=now,
            last_compiled_at=now,
        )
        findings = health_service.lint()
        assert "scored" in findings["quality_scores"]
        score = findings["quality_scores"]["scored"]
        assert 0.0 <= score <= 1.0

    def test_lint_fix_marks_stale_topics(self, health_service, db_session):
        """kb.9: lint_fix flips stale topics to STALE status."""
        stale_dt = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=60)
        topic = _make_topic(
            db_session,
            slug="stale-me",
            name="Stale Me",
            article_md="Stale content",
            last_evidence_at=stale_dt,
            last_compiled_at=stale_dt,
        )

        result = health_service.lint_fix()
        assert result["fixed_count"] == 1
        assert "stale-me" in result["stale"]
        db_session.refresh(topic)
        assert topic.status == TopicStatus.STALE
        assert "Auto-fix applied" in result["report_md"]

    def test_lint_fix_no_stale_topics(self, health_service, db_session):
        """kb.9: lint_fix with nothing stale reports zero fixes."""
        now = datetime.now(UTC).replace(tzinfo=None)
        _make_topic(
            db_session,
            slug="current",
            name="Current",
            article_md="Fresh",
            last_evidence_at=now,
            last_compiled_at=now,
        )
        result = health_service.lint_fix()
        assert result["fixed_count"] == 0
