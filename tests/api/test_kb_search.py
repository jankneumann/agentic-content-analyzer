"""Tests for ``GET /api/v1/kb/search``.

Covers:
- matching-query returns ranked topics with required fields
- empty result returns 200 with empty list
- auth enforcement in production (401/403)
- ``limit`` parameter caps the returned list; ``total_count`` is the full match
- ``last_compiled_at`` is populated on every row (OpenAPI required)
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime

import pytest

from src.models.topic import Topic, TopicStatus

pytestmark = pytest.mark.usefixtures("api_test_env")


@pytest.fixture
def kb_search_db(monkeypatch, db_session):
    """Point ``kb_search_routes.get_db`` at the per-test session.

    The shared ``client`` fixture patches ``get_db`` in a hardcoded list of
    route modules; new modules under ``src.api.routes.*`` are not covered,
    so we patch them explicitly here.
    """

    @contextmanager
    def _fake_get_db():
        yield db_session

    monkeypatch.setattr("src.api.routes.kb_search_routes.get_db", _fake_get_db)
    return _fake_get_db


def _make_topic(
    db_session,
    *,
    slug: str,
    name: str,
    summary: str = "",
    article_md: str = "",
    last_compiled_at: datetime | None = None,
    status: TopicStatus = TopicStatus.ACTIVE,
    relevance_score: float = 0.5,
) -> Topic:
    topic = Topic(
        slug=slug,
        name=name,
        category="ml_ai",
        status=status,
        summary=summary,
        article_md=article_md,
        article_version=1,
        relevance_score=relevance_score,
        last_compiled_at=last_compiled_at or datetime(2026, 4, 1, tzinfo=UTC),
    )
    db_session.add(topic)
    db_session.commit()
    db_session.refresh(topic)
    return topic


class TestSearchMatching:
    def test_returns_matching_topics(self, client, db_session, kb_search_db):
        _make_topic(
            db_session,
            slug="moe",
            name="Mixture of Experts",
            summary="Sparse MoE routing",
            article_md="# MoE\n\nMixture of experts activates a subset.",
        )
        _make_topic(
            db_session,
            slug="diffusion",
            name="Diffusion Models",
            summary="Image generation",
            article_md="# Diffusion\n\nNot about experts.",
        )
        resp = client.get("/api/v1/kb/search", params={"q": "Mixture"})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "topics" in body
        assert "total_count" in body
        assert body["total_count"] >= 1
        slugs = [t["slug"] for t in body["topics"]]
        assert "moe" in slugs

    def test_result_row_shape(self, client, db_session, kb_search_db):
        _make_topic(
            db_session,
            slug="moe",
            name="Mixture of Experts",
            summary="Sparse MoE routing",
            article_md="MoE activates a subset.",
        )
        resp = client.get("/api/v1/kb/search", params={"q": "Mixture"})
        assert resp.status_code == 200
        topic = resp.json()["topics"][0]
        assert set(topic.keys()) >= {
            "slug",
            "title",
            "score",
            "excerpt",
            "last_compiled_at",
        }
        assert topic["last_compiled_at"] is not None

    def test_last_compiled_at_present_on_every_row(self, client, db_session, kb_search_db):
        # Two topics match; both must include last_compiled_at non-null.
        _make_topic(
            db_session,
            slug="moe-a",
            name="Mixture of Experts A",
            article_md="Mixture of experts route",
            last_compiled_at=datetime(2026, 4, 1, tzinfo=UTC),
        )
        _make_topic(
            db_session,
            slug="moe-b",
            name="Mixture of Experts B",
            article_md="mixture of experts route",
            last_compiled_at=datetime(2026, 4, 10, tzinfo=UTC),
        )
        resp = client.get("/api/v1/kb/search", params={"q": "Mixture"})
        assert resp.status_code == 200
        for t in resp.json()["topics"]:
            assert t["last_compiled_at"] is not None
            assert len(t["last_compiled_at"]) > 0


class TestSearchEmpty:
    def test_no_matches_returns_empty(self, client, db_session, kb_search_db):
        _make_topic(
            db_session,
            slug="moe",
            name="Mixture of Experts",
            article_md="Expert routing",
        )
        resp = client.get("/api/v1/kb/search", params={"q": "zzz-no-such-topic"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["topics"] == []
        assert body["total_count"] == 0


class TestSearchLimit:
    def test_limit_caps_returned_topics(self, client, db_session, kb_search_db):
        # Seed 7 matching topics
        for i in range(7):
            _make_topic(
                db_session,
                slug=f"topic-{i}",
                name=f"Mixture variant {i}",
                article_md="mixture of experts description",
                relevance_score=0.5 + i * 0.05,
            )
        resp = client.get("/api/v1/kb/search", params={"q": "Mixture", "limit": 3})
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["topics"]) == 3
        assert body["total_count"] == 7

    def test_limit_validation_422(self, client, kb_search_db):
        resp = client.get("/api/v1/kb/search", params={"q": "hi", "limit": 500})
        assert resp.status_code == 422

    def test_query_required(self, client, kb_search_db):
        resp = client.get("/api/v1/kb/search")
        assert resp.status_code == 422


class TestSearchAuth:
    def test_unauthenticated_in_production(self, monkeypatch):
        from fastapi.testclient import TestClient

        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("APP_SECRET_KEY", "test-secret-key-at-least-32-characters-long!")
        monkeypatch.setenv("ADMIN_API_KEY", "right-key")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic")
        monkeypatch.setenv("WORKER_ENABLED", "false")

        from src.config.settings import get_settings

        get_settings.cache_clear()
        try:
            from src.api.app import app

            with TestClient(app, base_url="https://testserver") as c:
                resp = c.get("/api/v1/kb/search", params={"q": "hi"})
                assert resp.status_code in (401, 403)
        finally:
            get_settings.cache_clear()
