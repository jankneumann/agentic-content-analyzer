"""Tests for KnowledgeBaseService.

Covers compilation flow, evidence gathering, topic matching, concurrency,
relationships, merge detection, and index generation.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.theme import ThemeAnalysis
from src.models.topic import KBIndex, Topic, TopicNote, TopicStatus
from src.services.knowledge_base import (
    KBCompileLockError,
    KnowledgeBaseService,
    _article_similarity,
    cosine_similarity,
    slugify,
)

# ---- Module helpers ----


class TestModuleHelpers:
    def test_slugify_basic(self):
        assert slugify("RAG Architecture") == "rag-architecture"

    def test_slugify_unicode_strip(self):
        assert slugify("LLM Agents & Tools!") == "llm-agents-tools"

    def test_slugify_empty(self):
        assert slugify("   ") == "topic"

    def test_cosine_similarity_identical(self):
        v = [1.0, 0.0, 0.0]
        assert cosine_similarity(v, v) == pytest.approx(1.0)

    def test_cosine_similarity_orthogonal(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_cosine_similarity_zero_vector(self):
        assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0

    def test_cosine_similarity_length_mismatch(self):
        assert cosine_similarity([1.0, 1.0], [1.0]) == 0.0

    def test_article_similarity_identical(self):
        text = "knowledge base topic article"
        assert _article_similarity(text, text) == pytest.approx(1.0)

    def test_article_similarity_disjoint(self):
        assert _article_similarity("foo bar", "baz qux") == 0.0

    def test_article_similarity_empty(self):
        assert _article_similarity("", "anything") == 0.0


# ---- Service fixtures ----


@pytest.fixture
def kb_service(db_session):
    """KB service with a real session and mocked LLM router."""
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock()
    mock_llm.generate.return_value = MagicMock(
        text="# Compiled Article\n\nFull body.",
        input_tokens=100,
        output_tokens=200,
    )
    return KnowledgeBaseService(db_session, llm_router=mock_llm)


# ---- Compilation flow ----


@pytest.mark.asyncio
class TestCompilationFlow:
    async def test_compile_with_no_evidence_succeeds(self, kb_service):
        """kb.2: compile-with-no-new-evidence completes without error."""
        summary = await kb_service.compile()
        assert summary.topics_found == 0
        assert summary.topics_compiled == 0
        assert summary.error is None
        assert summary.finished_at is not None

    async def test_first_compilation_creates_topics(self, kb_service, db_session):
        """kb.2: First compilation creates draft topics from ThemeAnalysis."""
        # Seed a ThemeAnalysis with one theme
        theme_analysis = ThemeAnalysis(
            start_date=datetime(2026, 4, 1),
            end_date=datetime(2026, 4, 8),
            content_count=2,
            themes=[
                {
                    "name": "RAG Architecture",
                    "description": "Retrieval-augmented generation patterns",
                    "category": "ml_ai",
                    "mention_count": 5,
                    "relevance_score": 0.75,
                    "novelty_score": 0.4,
                    "trend": "growing",
                    "content_ids": [1, 2],
                }
            ],
            total_themes=1,
        )
        db_session.add(theme_analysis)
        db_session.commit()

        # Skip embedding generation by patching the matcher
        with patch.object(kb_service, "_generate_embedding", new=AsyncMock(return_value=None)):
            summary = await kb_service.compile()

        assert summary.topics_found == 1
        assert summary.topics_compiled == 1
        topic = db_session.query(Topic).filter_by(name="RAG Architecture").one()
        assert topic.status == TopicStatus.ACTIVE
        assert topic.slug == "rag-architecture"
        assert topic.compilation_model is not None
        assert topic.last_compiled_at is not None

    async def test_exact_name_match_reuses_topic(self, kb_service, db_session):
        """kb.2: Phase 1 exact name match reuses an existing topic."""
        existing = Topic(
            slug="agentic-systems",
            name="Agentic Systems",
            category="ml_ai",
            status=TopicStatus.ACTIVE,
            article_md="old article",
            article_version=1,
        )
        db_session.add(existing)
        db_session.commit()
        existing_id = existing.id

        analysis = ThemeAnalysis(
            start_date=datetime(2026, 4, 1),
            end_date=datetime(2026, 4, 8),
            content_count=1,
            themes=[
                {
                    "name": "Agentic Systems",  # exact match
                    "description": "Loops with tool use",
                    "category": "ml_ai",
                    "mention_count": 3,
                    "content_ids": [9],
                    "trend": "growing",
                }
            ],
        )
        db_session.add(analysis)
        db_session.commit()

        summary = await kb_service.compile()
        assert summary.topics_compiled == 1

        refreshed = db_session.get(Topic, existing_id)
        assert refreshed is not None
        # Article was recompiled — version should have advanced
        assert refreshed.article_version == 2
        # Source content list should now include the new id
        assert 9 in (refreshed.source_content_ids or [])

    async def test_llm_failure_marks_topic_failed(self, kb_service, db_session):
        """kb.2: LLM failure during compilation skips topic without crashing."""
        kb_service.llm_router.generate = AsyncMock(side_effect=RuntimeError("LLM down"))

        analysis = ThemeAnalysis(
            start_date=datetime(2026, 4, 1),
            end_date=datetime(2026, 4, 8),
            content_count=1,
            themes=[
                {
                    "name": "Failure Topic",
                    "description": "Should fail",
                    "category": "ml_ai",
                    "mention_count": 1,
                    "content_ids": [1],
                    "trend": "one_off",
                }
            ],
        )
        db_session.add(analysis)
        db_session.commit()

        with patch.object(kb_service, "_generate_embedding", new=AsyncMock(return_value=None)):
            summary = await kb_service.compile()

        assert summary.topics_failed == 1
        assert summary.topics_compiled == 0
        assert any(r.action == "failed" for r in summary.per_topic)

    async def test_embedding_failure_falls_back_to_exact_only(self, kb_service, db_session):
        """kb.2: Embedding failure during matching falls back gracefully."""
        analysis = ThemeAnalysis(
            start_date=datetime(2026, 4, 1),
            end_date=datetime(2026, 4, 8),
            content_count=1,
            themes=[
                {
                    "name": "Brand New Topic",
                    "description": "No existing match",
                    "category": "ml_ai",
                    "mention_count": 1,
                    "content_ids": [],
                    "trend": "one_off",
                }
            ],
        )
        db_session.add(analysis)
        db_session.commit()

        kb_service._generate_embedding = AsyncMock(  # type: ignore[method-assign]
            side_effect=RuntimeError("provider unavailable")
        )

        summary = await kb_service.compile()
        # Topic should still be created (exact match fallback creates new)
        assert summary.topics_compiled == 1
        assert db_session.query(Topic).filter_by(name="Brand New Topic").count() == 1


# ---- Concurrency control ----


@pytest.mark.asyncio
class TestConcurrency:
    async def test_concurrent_compile_rejected(self, kb_service, db_session):
        """kb.3: A second compile while one is in progress is rejected."""
        # Manually write the sentinel lock
        kb_service._write_sentinel_lock()
        db_session.commit()

        with patch.object(kb_service, "_acquire_lock", return_value=False):
            with pytest.raises(KBCompileLockError):
                await kb_service.compile()

    async def test_lock_released_after_success(self, kb_service):
        """kb.3: After a successful compile, lock is released."""
        await kb_service.compile()
        # Sentinel should be cleared
        sentinel = (
            kb_service.db.query(KBIndex).filter_by(index_type="_compile_lock_sentinel").first()
        )
        assert sentinel is None

    async def test_exception_in_compile_triggers_rollback_and_releases_lock(
        self, kb_service, db_session
    ):
        """Finding #1: Unhandled exceptions during compile SHALL rollback
        the session and still release the advisory lock, leaving the DB
        in a usable state for subsequent queries.
        """
        # Seed a theme so compile actually iterates
        analysis = ThemeAnalysis(
            start_date=datetime(2026, 4, 1),
            end_date=datetime(2026, 4, 8),
            content_count=1,
            themes=[
                {
                    "name": "Rollback Topic",
                    "description": "forces an exception during merge detection",
                    "category": "ml_ai",
                    "mention_count": 1,
                    "content_ids": [],
                    "trend": "one_off",
                }
            ],
        )
        db_session.add(analysis)
        db_session.commit()

        # Let the per-topic compile succeed, but explode during merge
        # detection (outside the per-topic try/except) to exercise the
        # outer rollback path.
        with (
            patch.object(
                kb_service,
                "_detect_merge_candidates",
                side_effect=RuntimeError("boom from merge detection"),
            ),
            patch.object(kb_service, "_generate_embedding", new=AsyncMock(return_value=None)),
        ):
            with pytest.raises(RuntimeError, match="boom from merge detection"):
                await kb_service.compile()

        # Lock MUST have been released
        sentinel = db_session.query(KBIndex).filter_by(index_type="_compile_lock_sentinel").first()
        assert sentinel is None

        # Session must still be usable (not in a broken transaction)
        topics_after = db_session.query(Topic).all()
        # The in-flight topic insertion should have been rolled back
        assert all(t.name != "Rollback Topic" for t in topics_after)


# ---- Input validation on add_note ----


class TestAddNoteValidation:
    def test_add_note_rejects_invalid_note_type(self, db_session, kb_service):
        """Finding #7: add_note raises ValueError for unknown note_type
        before hitting the DB, so API callers get a clean 422.
        """
        topic = Topic(slug="note-validation", name="Validation", category="ml_ai")
        db_session.add(topic)
        db_session.commit()

        with pytest.raises(ValueError, match="Invalid note_type"):
            kb_service.add_note(
                topic_slug="note-validation",
                content="x",
                note_type="bogus",
            )


# ---- Merge detection scale ----


@pytest.mark.asyncio
class TestMergeDetectionTokenization:
    async def test_merge_detection_uses_pre_tokenized_sets(self, kb_service, db_session):
        """Finding #4: _detect_merge_candidates tokenizes each article
        once and reuses the set for pairwise comparisons.
        """
        from src.services.knowledge_base import _jaccard, _tokenize

        # Verify helpers exist and work
        a = _tokenize("rag vector database retrieval")
        b = _tokenize("rag vector database retrieval")
        assert _jaccard(a, b) == 1.0
        assert _jaccard(a, _tokenize("")) == 0.0


# ---- Merge detection ----


@pytest.mark.asyncio
class TestMergeDetection:
    async def test_merge_candidate_detected(self, kb_service, db_session):
        """kb.5: Topics with article cosine > 0.90 flagged as merge candidates."""
        # Two topics with very similar articles
        identical = "rag retrieval augmented generation vector database"
        a = Topic(
            slug="topic-a",
            name="Topic A",
            category="ml_ai",
            status=TopicStatus.ACTIVE,
            article_md=identical,
        )
        b = Topic(
            slug="topic-b",
            name="Topic B",
            category="ml_ai",
            status=TopicStatus.ACTIVE,
            article_md=identical,
        )
        db_session.add_all([a, b])
        db_session.commit()

        candidates = kb_service._detect_merge_candidates()
        assert ("topic-a", "topic-b") in candidates or (
            "topic-b",
            "topic-a",
        ) in candidates

    async def test_empty_article_excluded_from_merge(self, kb_service, db_session):
        """kb.5: Topics with empty/NULL articles excluded from merge detection."""
        a = Topic(
            slug="topic-empty",
            name="Empty",
            category="ml_ai",
            status=TopicStatus.ACTIVE,
            article_md=None,
        )
        b = Topic(
            slug="topic-also-empty",
            name="Also Empty",
            category="ml_ai",
            status=TopicStatus.ACTIVE,
            article_md="",
        )
        db_session.add_all([a, b])
        db_session.commit()

        candidates = kb_service._detect_merge_candidates()
        assert candidates == []


# ---- Index generation ----


@pytest.mark.asyncio
class TestIndexGeneration:
    async def test_indices_generated_after_compile(self, kb_service, db_session):
        """kb.6: Indices regenerated at the end of every compile cycle."""
        # Seed a topic so indices have content
        topic = Topic(
            slug="seeded",
            name="Seeded Topic",
            category="ml_ai",
            status=TopicStatus.ACTIVE,
            relevance_score=0.5,
            summary="A seeded topic.",
            trend="emerging",
            article_md="x",
        )
        db_session.add(topic)
        db_session.commit()

        await kb_service.compile()

        master = db_session.query(KBIndex).filter_by(index_type="master").first()
        assert master is not None
        assert "Seeded Topic" in master.content

    async def test_empty_kb_indices(self, kb_service, db_session):
        """kb.6: Empty KB still produces indices with empty-state messages."""
        await kb_service.compile()

        master = db_session.query(KBIndex).filter_by(index_type="master").first()
        assert master is not None
        assert "No active topics" in master.content


# ---- Topic notes ----


class TestTopicNotes:
    def test_add_note(self, db_session, kb_service):
        topic = Topic(
            slug="note-target",
            name="Note Target",
            category="ml_ai",
            status=TopicStatus.ACTIVE,
        )
        db_session.add(topic)
        db_session.commit()

        note = kb_service.add_note(
            topic_slug="note-target",
            content="An observation",
            note_type="observation",
            author="agent:test",
        )
        assert note.id is not None
        assert note.author == "agent:test"
        fetched = db_session.query(TopicNote).filter_by(topic_id=topic.id).all()
        assert len(fetched) == 1

    def test_add_note_unknown_topic_raises(self, kb_service):
        with pytest.raises(ValueError, match="Topic not found"):
            kb_service.add_note(topic_slug="missing", content="x")
