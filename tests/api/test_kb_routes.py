"""Knowledge base API endpoint tests.

Covers topic CRUD, notes, compile (with lock conflict), and index
retrieval. Compile and Q&A paths mock the KB service to avoid hitting
the LLM.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.models.topic import KBIndex, Topic, TopicStatus
from src.services.knowledge_base import CompileSummary, KBCompileLockError

# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #


def _make_topic(
    db_session,
    *,
    slug: str,
    name: str,
    category: str = "ml_ai",
    status: TopicStatus = TopicStatus.ACTIVE,
    summary: str = "Topic summary",
    article_md: str = "# Topic\n\nBody.",
    trend: str = "growing",
    relevance_score: float = 0.7,
    mention_count: int = 3,
) -> Topic:
    topic = Topic(
        slug=slug,
        name=name,
        category=category,
        status=status,
        summary=summary,
        article_md=article_md,
        article_version=1,
        trend=trend,
        relevance_score=relevance_score,
        mention_count=mention_count,
    )
    db_session.add(topic)
    db_session.commit()
    db_session.refresh(topic)
    return topic


# ---------------------------------------------------------------------- #
# Topic listing
# ---------------------------------------------------------------------- #


class TestListTopics:
    def test_list_empty_returns_200(self, client):
        resp = client.get("/api/v1/kb/topics")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_returns_active_topics(self, client, db_session):
        _make_topic(db_session, slug="t1", name="Topic 1", relevance_score=0.9)
        _make_topic(db_session, slug="t2", name="Topic 2", relevance_score=0.5)
        resp = client.get("/api/v1/kb/topics")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        # Sorted by relevance_score desc
        assert data[0]["slug"] == "t1"
        assert data[1]["slug"] == "t2"

    def test_list_filters_archived_by_default(self, client, db_session):
        _make_topic(db_session, slug="live", name="Live")
        _make_topic(
            db_session,
            slug="dead",
            name="Dead",
            status=TopicStatus.ARCHIVED,
        )
        resp = client.get("/api/v1/kb/topics")
        data = resp.json()
        slugs = [row["slug"] for row in data]
        assert "live" in slugs
        assert "dead" not in slugs

    def test_list_filter_by_category(self, client, db_session):
        _make_topic(db_session, slug="ml", name="ML Topic", category="ml_ai")
        _make_topic(
            db_session,
            slug="sec",
            name="Security Topic",
            category="security",
        )
        resp = client.get("/api/v1/kb/topics?category=security")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["slug"] == "sec"

    def test_list_filter_by_status_includes_archived(self, client, db_session):
        _make_topic(
            db_session,
            slug="arch",
            name="Archived",
            status=TopicStatus.ARCHIVED,
        )
        resp = client.get("/api/v1/kb/topics?status=archived")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["status"] == "archived"

    def test_list_pagination_limits(self, client, db_session):
        for idx in range(5):
            _make_topic(
                db_session,
                slug=f"p-{idx}",
                name=f"Page {idx}",
                relevance_score=1.0 - (idx * 0.05),
            )
        resp = client.get("/api/v1/kb/topics?limit=2&offset=1")
        data = resp.json()
        assert len(data) == 2


# ---------------------------------------------------------------------- #
# Topic detail
# ---------------------------------------------------------------------- #


class TestGetTopic:
    def test_get_existing_topic(self, client, db_session):
        _make_topic(
            db_session,
            slug="detail",
            name="Detail Topic",
            article_md="# Detail\n\nContent.",
        )
        resp = client.get("/api/v1/kb/topics/detail")
        assert resp.status_code == 200
        data = resp.json()
        assert data["slug"] == "detail"
        assert data["article_md"].startswith("# Detail")

    def test_get_missing_topic_404(self, client):
        resp = client.get("/api/v1/kb/topics/does-not-exist")
        assert resp.status_code == 404


# ---------------------------------------------------------------------- #
# Topic create / update / archive
# ---------------------------------------------------------------------- #


class TestCreateTopic:
    def test_create_returns_201(self, client):
        resp = client.post(
            "/api/v1/kb/topics",
            json={"name": "Brand New", "category": "ml_ai"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["slug"] == "brand-new"
        assert data["status"] == "draft"

    def test_create_unique_slug_on_collision(self, client, db_session):
        _make_topic(db_session, slug="agents", name="Agents")
        resp = client.post(
            "/api/v1/kb/topics",
            json={"name": "Agents", "category": "ml_ai"},
        )
        assert resp.status_code == 201
        assert resp.json()["slug"] == "agents-2"

    def test_create_missing_required_fields(self, client):
        resp = client.post("/api/v1/kb/topics", json={"name": "No Category"})
        assert resp.status_code == 422

    def test_create_rejects_invalid_category(self, client):
        """Finding #6: bogus category returns 422, not 201."""
        resp = client.post(
            "/api/v1/kb/topics",
            json={"name": "Bad Category", "category": "not_a_real_cat"},
        )
        assert resp.status_code == 422
        assert "Invalid category" in resp.text


class TestUpdateTopic:
    def test_update_summary_and_trend(self, client, db_session):
        _make_topic(db_session, slug="up", name="Up", summary="old")
        resp = client.patch(
            "/api/v1/kb/topics/up",
            json={"summary": "new summary", "trend": "emerging"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"] == "new summary"
        assert data["trend"] == "emerging"

    def test_update_article_increments_version(self, client, db_session):
        _make_topic(db_session, slug="ver", name="Ver")
        resp = client.patch(
            "/api/v1/kb/topics/ver",
            json={"article_md": "# New body"},
        )
        assert resp.status_code == 200
        assert resp.json()["article_version"] == 2

    def test_update_missing_topic_404(self, client):
        resp = client.patch(
            "/api/v1/kb/topics/missing",
            json={"summary": "ignored"},
        )
        assert resp.status_code == 404

    def test_update_invalid_status_422(self, client, db_session):
        _make_topic(db_session, slug="bad", name="Bad")
        resp = client.patch(
            "/api/v1/kb/topics/bad",
            json={"status": "not-a-real-status"},
        )
        assert resp.status_code == 422

    def test_update_status_can_unarchive(self, client, db_session):
        _make_topic(
            db_session,
            slug="rev",
            name="Rev",
            status=TopicStatus.ARCHIVED,
        )
        resp = client.patch(
            "/api/v1/kb/topics/rev",
            json={"status": "active"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    def test_update_rejects_invalid_category(self, client, db_session):
        """Finding #6: category on PATCH is validated against enum."""
        _make_topic(db_session, slug="cat", name="Cat")
        resp = client.patch(
            "/api/v1/kb/topics/cat",
            json={"category": "not_valid"},
        )
        assert resp.status_code == 422

    def test_update_rejects_out_of_range_relevance(self, client, db_session):
        """Finding #5: relevance_score is bounded 0..1."""
        _make_topic(db_session, slug="rng", name="Range")
        resp = client.patch(
            "/api/v1/kb/topics/rng",
            json={"relevance_score": 42.0},
        )
        assert resp.status_code == 422


class TestArchiveTopic:
    def test_delete_soft_archives_topic(self, client, db_session):
        topic = _make_topic(db_session, slug="del", name="Delete")
        resp = client.delete("/api/v1/kb/topics/del")
        assert resp.status_code == 204
        db_session.refresh(topic)
        assert topic.status == TopicStatus.ARCHIVED

    def test_delete_missing_topic_404(self, client):
        resp = client.delete("/api/v1/kb/topics/ghost")
        assert resp.status_code == 404


# ---------------------------------------------------------------------- #
# Topic notes
# ---------------------------------------------------------------------- #


class TestTopicNotes:
    def test_list_notes_empty(self, client, db_session):
        _make_topic(db_session, slug="nn", name="NoNotes")
        resp = client.get("/api/v1/kb/topics/nn/notes")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_notes_missing_topic_404(self, client):
        resp = client.get("/api/v1/kb/topics/missing/notes")
        assert resp.status_code == 404

    def test_create_note(self, client, db_session):
        topic = _make_topic(db_session, slug="nc", name="NoteCreator")
        resp = client.post(
            "/api/v1/kb/topics/nc/notes",
            json={
                "content": "An observation",
                "note_type": "observation",
                "author": "tester",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["content"] == "An observation"
        assert data["author"] == "tester"
        assert data["topic_id"] == topic.id
        assert data["note_type"] == "observation"

    def test_create_note_missing_topic_404(self, client):
        resp = client.post(
            "/api/v1/kb/topics/missing/notes",
            json={"content": "body"},
        )
        assert resp.status_code == 404

    def test_create_note_rejects_invalid_type(self, client, db_session):
        """Finding #7: invalid note_type returns 422, not 500."""
        _make_topic(db_session, slug="nt", name="NoteType")
        resp = client.post(
            "/api/v1/kb/topics/nt/notes",
            json={"content": "body", "note_type": "rant"},
        )
        assert resp.status_code == 422
        assert "Invalid note_type" in resp.text

    def test_create_and_list_note_roundtrip(self, client, db_session):
        _make_topic(db_session, slug="rt", name="RoundTrip")
        client.post(
            "/api/v1/kb/topics/rt/notes",
            json={"content": "first", "note_type": "insight"},
        )
        client.post(
            "/api/v1/kb/topics/rt/notes",
            json={"content": "second", "note_type": "question"},
        )
        resp = client.get("/api/v1/kb/topics/rt/notes")
        data = resp.json()
        assert len(data) == 2
        assert {n["content"] for n in data} == {"first", "second"}


# ---------------------------------------------------------------------- #
# Compile endpoint
# ---------------------------------------------------------------------- #


class TestCompile:
    def test_compile_returns_200_with_summary(self, client, db_session):
        fake_summary = CompileSummary(started_at=datetime.now(UTC))
        fake_summary.finished_at = datetime.now(UTC)
        fake_summary.topics_found = 2
        fake_summary.topics_compiled = 2

        fake_service = MagicMock()
        fake_service.compile = AsyncMock(return_value=fake_summary)

        with patch(
            "src.api.kb_routes.KnowledgeBaseService",
            return_value=fake_service,
        ):
            resp = client.post("/api/v1/kb/compile")

        assert resp.status_code == 200
        data = resp.json()
        assert data["topics_found"] == 2
        assert data["topics_compiled"] == 2
        assert data["error"] is None

    def test_compile_lock_conflict_returns_409(self, client):
        fake_service = MagicMock()
        fake_service.compile = AsyncMock(
            side_effect=KBCompileLockError("Another KB compilation is already in progress.")
        )
        with patch(
            "src.api.kb_routes.KnowledgeBaseService",
            return_value=fake_service,
        ):
            resp = client.post("/api/v1/kb/compile")

        assert resp.status_code == 409
        assert "already in progress" in resp.json()["detail"]

    def test_compile_unexpected_failure_500(self, client):
        fake_service = MagicMock()
        fake_service.compile = AsyncMock(side_effect=RuntimeError("boom"))
        with patch(
            "src.api.kb_routes.KnowledgeBaseService",
            return_value=fake_service,
        ):
            resp = client.post("/api/v1/kb/compile")
        assert resp.status_code == 500


# ---------------------------------------------------------------------- #
# Index endpoint
# ---------------------------------------------------------------------- #


class TestIndex:
    def test_get_master_index(self, client, db_session):
        db_session.add(
            KBIndex(
                index_type="master",
                content="# Master\n\n- Topic A",
                generated_at=datetime(2026, 4, 1, 10, 0, 0),
            )
        )
        db_session.commit()
        resp = client.get("/api/v1/kb/index")
        assert resp.status_code == 200
        data = resp.json()
        assert data["index_type"] == "master"
        assert "Topic A" in data["content"]
        assert data["generated_at"] is not None

    def test_get_missing_index_returns_empty(self, client):
        resp = client.get("/api/v1/kb/index")
        assert resp.status_code == 200
        data = resp.json()
        assert data["content"] == ""
        assert data["generated_at"] is None

    def test_get_category_index(self, client, db_session):
        db_session.add(
            KBIndex(
                index_type="category_ml_ai",
                content="# Category: ml_ai\n\n- Topic X",
                generated_at=datetime(2026, 4, 1, 10, 0, 0),
            )
        )
        db_session.commit()
        resp = client.get("/api/v1/kb/index?category=ml_ai")
        data = resp.json()
        assert data["index_type"] == "category_ml_ai"
        assert "Topic X" in data["content"]


# ---------------------------------------------------------------------- #
# Query endpoint
# ---------------------------------------------------------------------- #


class TestQuery:
    def test_query_returns_answer(self, client, db_session):
        _make_topic(
            db_session,
            slug="qa-topic",
            name="Q&A Topic",
            summary="Some summary",
            article_md="Article body with RAG information",
        )
        fake_qa = MagicMock()
        fake_qa.query = AsyncMock(
            return_value={
                "answer": "Synthesized answer",
                "topics": ["qa-topic"],
                "truncated": False,
            }
        )
        with patch("src.api.kb_routes.KBQAService", return_value=fake_qa):
            resp = client.post(
                "/api/v1/kb/query",
                json={"question": "What is RAG?"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "Synthesized answer"
        assert data["topics"] == ["qa-topic"]

    def test_query_llm_failure_returns_502(self, client):
        fake_qa = MagicMock()
        fake_qa.query = AsyncMock(side_effect=RuntimeError("llm down"))
        with patch("src.api.kb_routes.KBQAService", return_value=fake_qa):
            resp = client.post(
                "/api/v1/kb/query",
                json={"question": "Any question"},
            )
        assert resp.status_code == 502

    def test_query_empty_question_422(self, client):
        resp = client.post("/api/v1/kb/query", json={"question": ""})
        assert resp.status_code == 422
