"""Tests for Topic, TopicNote, and KBIndex models."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from src.models.topic import KBIndex, Topic, TopicNote, TopicNoteType, TopicStatus

# ---- Enum tests ----


class TestEnums:
    def test_topic_status_values(self):
        assert TopicStatus.DRAFT == "draft"
        assert TopicStatus.ACTIVE == "active"
        assert TopicStatus.STALE == "stale"
        assert TopicStatus.ARCHIVED == "archived"
        assert TopicStatus.MERGED == "merged"

    def test_topic_note_type_values(self):
        assert TopicNoteType.OBSERVATION == "observation"
        assert TopicNoteType.QUESTION == "question"
        assert TopicNoteType.CORRECTION == "correction"
        assert TopicNoteType.INSIGHT == "insight"


# ---- Topic CRUD tests ----


class TestTopicCRUD:
    def test_create_topic_minimal(self, db_session):
        """Validates kb.1: Create topic with required fields, defaults applied."""
        topic = Topic(
            slug="rag-architecture",
            name="RAG Architecture",
            category="ml_ai",
        )
        db_session.add(topic)
        db_session.commit()

        fetched = db_session.query(Topic).filter_by(slug="rag-architecture").one()
        assert fetched.id is not None
        assert fetched.status == TopicStatus.DRAFT
        assert fetched.article_version == 1
        assert fetched.relevance_score == 0.0
        assert fetched.mention_count == 0
        assert fetched.source_content_ids == []
        assert fetched.related_topic_ids == []

    def test_create_topic_full(self, db_session):
        """Validates kb.1: All optional fields persist correctly."""
        now = datetime.now(UTC).replace(tzinfo=None)
        topic = Topic(
            slug="agentic-systems",
            name="Agentic Systems",
            category="ml_ai",
            status=TopicStatus.ACTIVE,
            summary="Agentic systems use LLMs as reasoning loops.",
            article_md="# Agentic Systems\n\nFull article...",
            article_version=3,
            trend="growing",
            relevance_score=0.85,
            novelty_score=0.6,
            mention_count=12,
            source_content_ids=[1, 2, 3],
            source_summary_ids=[10, 20],
            source_theme_ids=[100],
            related_topic_ids=[2, 3],
            last_compiled_at=now,
            last_evidence_at=now,
            compilation_model="claude-sonnet-4-5",
            compilation_token_usage=4500,
        )
        db_session.add(topic)
        db_session.commit()

        fetched = db_session.query(Topic).filter_by(slug="agentic-systems").one()
        assert fetched.article_version == 3
        assert fetched.source_content_ids == [1, 2, 3]
        assert fetched.related_topic_ids == [2, 3]
        assert fetched.compilation_model == "claude-sonnet-4-5"

    def test_slug_uniqueness(self, db_session):
        """Validates kb.1: Topic slug uniqueness scenario."""
        topic1 = Topic(slug="duplicate-slug", name="Topic A", category="ml_ai")
        topic2 = Topic(slug="duplicate-slug", name="Topic B", category="ml_ai")

        db_session.add(topic1)
        db_session.commit()

        db_session.add(topic2)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_archived_topic_excluded_from_active_query(self, db_session):
        """Validates kb.1: Archived topics SHALL NOT appear in indices."""
        active = Topic(
            slug="active-1",
            name="Active",
            category="ml_ai",
            status=TopicStatus.ACTIVE,
        )
        archived = Topic(
            slug="archived-1",
            name="Archived",
            category="ml_ai",
            status=TopicStatus.ARCHIVED,
        )
        db_session.add_all([active, archived])
        db_session.commit()

        active_topics = db_session.query(Topic).filter(Topic.status == TopicStatus.ACTIVE).all()
        assert len(active_topics) == 1
        assert active_topics[0].slug == "active-1"

    def test_self_referential_parent(self, db_session):
        """Validates kb.1: parent_topic_id self-referential FK."""
        parent = Topic(slug="ml-systems", name="ML Systems", category="ml_ai")
        db_session.add(parent)
        db_session.commit()

        child = Topic(
            slug="rag-systems",
            name="RAG Systems",
            category="ml_ai",
            parent_topic_id=parent.id,
        )
        db_session.add(child)
        db_session.commit()

        fetched = db_session.query(Topic).filter_by(slug="rag-systems").one()
        assert fetched.parent_topic_id == parent.id


# ---- TopicNote tests ----


class TestTopicNote:
    def test_create_topic_note(self, db_session):
        """Validates kb.1: Topic note creation scenario."""
        topic = Topic(slug="topic-with-note", name="Topic", category="ml_ai")
        db_session.add(topic)
        db_session.commit()

        note = TopicNote(
            topic_id=topic.id,
            note_type=TopicNoteType.INSIGHT,
            content="This topic is gaining momentum.",
            author="agent:strategist",
        )
        db_session.add(note)
        db_session.commit()

        fetched = db_session.query(TopicNote).filter_by(topic_id=topic.id).one()
        assert fetched.note_type == TopicNoteType.INSIGHT
        assert fetched.author == "agent:strategist"
        assert fetched.filed_back is False

    def test_topic_note_cascade_delete(self, db_session):
        """Validates kb.1: TopicNote cascade-deletes with parent Topic."""
        topic = Topic(slug="cascade-topic", name="Topic", category="ml_ai")
        db_session.add(topic)
        db_session.commit()

        note = TopicNote(topic_id=topic.id, content="Note 1")
        db_session.add(note)
        db_session.commit()

        topic_id = topic.id
        db_session.delete(topic)
        db_session.commit()

        remaining = db_session.query(TopicNote).filter_by(topic_id=topic_id).all()
        assert len(remaining) == 0


# ---- KBIndex tests ----


class TestKBIndex:
    def test_create_index(self, db_session):
        """Validates kb.6: KBIndex stores cached markdown by index_type."""
        index = KBIndex(
            index_type="master",
            content="# Master Index\n\n- Topic A\n- Topic B",
        )
        db_session.add(index)
        db_session.commit()

        fetched = db_session.query(KBIndex).filter_by(index_type="master").one()
        assert "Master Index" in fetched.content
        assert fetched.generated_at is not None

    def test_index_type_uniqueness(self, db_session):
        """Validates kb.6: One row per index_type."""
        idx1 = KBIndex(index_type="master", content="v1")
        idx2 = KBIndex(index_type="master", content="v2")

        db_session.add(idx1)
        db_session.commit()

        db_session.add(idx2)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()
