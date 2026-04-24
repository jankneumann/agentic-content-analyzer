"""Tests for ``GET /api/v1/kb/lint`` and ``POST /api/v1/kb/lint/fix``.

Covers:
- GET lint is read-only — returns 200 with stale/orphaned/score_anomaly arrays
  using the quantitative thresholds from the spec (stale >30d, orphaned means
  zero refs AND zero related topics, score_anomaly requires ≥10 category samples).
- POST lint/fix applies corrections and records an audit row tagged
  ``kb.lint.fix``.
- POST lint/fix when there are no issues returns a 200 with an empty
  ``corrections_applied`` array.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from src.models.topic import Topic, TopicStatus

pytestmark = pytest.mark.usefixtures("api_test_env")


@pytest.fixture
def kb_lint_db(monkeypatch, db_session):
    """Point the new kb_routes module's ``get_db`` at the per-test session."""

    @contextmanager
    def _fake_get_db():
        yield db_session

    monkeypatch.setattr("src.api.routes.kb_routes.get_db", _fake_get_db)
    return _fake_get_db


def _make_topic(
    db_session,
    *,
    slug: str,
    name: str | None = None,
    category: str = "ml_ai",
    status: TopicStatus = TopicStatus.ACTIVE,
    last_compiled_at: datetime | None = None,
    relevance_score: float = 0.5,
    source_content_ids: list[int] | None = None,
    related_topic_ids: list[int] | None = None,
) -> Topic:
    topic = Topic(
        slug=slug,
        name=name or slug.replace("-", " ").title(),
        category=category,
        status=status,
        article_version=1,
        relevance_score=relevance_score,
        last_compiled_at=last_compiled_at,
        source_content_ids=source_content_ids or [],
        related_topic_ids=related_topic_ids or [],
    )
    db_session.add(topic)
    db_session.commit()
    db_session.refresh(topic)
    return topic


# ---------------------------------------------------------------------------
# GET /api/v1/kb/lint
# ---------------------------------------------------------------------------


class TestLintRead:
    def test_response_shape(self, client, kb_lint_db):
        resp = client.get("/api/v1/kb/lint")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert set(body.keys()) == {"stale_topics", "orphaned_topics", "score_anomalies"}
        assert isinstance(body["stale_topics"], list)
        assert isinstance(body["orphaned_topics"], list)
        assert isinstance(body["score_anomalies"], list)

    def test_flags_stale_over_30_days(self, client, db_session, kb_lint_db):
        now = datetime.now(UTC)
        _make_topic(
            db_session,
            slug="fresh",
            last_compiled_at=now,
            source_content_ids=[1],
        )
        _make_topic(
            db_session,
            slug="stale-one",
            last_compiled_at=now - timedelta(days=40),
            source_content_ids=[2],
        )
        resp = client.get("/api/v1/kb/lint")
        assert resp.status_code == 200
        stale_slugs = [t["slug"] for t in resp.json()["stale_topics"]]
        assert "stale-one" in stale_slugs
        assert "fresh" not in stale_slugs

    def test_flags_orphaned_zero_refs_and_zero_degree(self, client, db_session, kb_lint_db):
        _make_topic(
            db_session,
            slug="orphan",
            source_content_ids=[],
            related_topic_ids=[],
        )
        _make_topic(
            db_session,
            slug="has-refs",
            source_content_ids=[1],
            related_topic_ids=[],
        )
        _make_topic(
            db_session,
            slug="has-edges",
            source_content_ids=[],
            related_topic_ids=[2],
        )
        resp = client.get("/api/v1/kb/lint")
        assert resp.status_code == 200
        orphan_slugs = [t["slug"] for t in resp.json()["orphaned_topics"]]
        assert "orphan" in orphan_slugs
        assert "has-refs" not in orphan_slugs
        assert "has-edges" not in orphan_slugs

    def test_score_anomaly_skipped_when_category_sample_below_10(
        self, client, db_session, kb_lint_db
    ):
        # Only 3 topics in category: anomaly scan should skip it entirely.
        _make_topic(db_session, slug="a", relevance_score=0.1, category="small")
        _make_topic(db_session, slug="b", relevance_score=0.2, category="small")
        _make_topic(db_session, slug="c", relevance_score=0.99, category="small")
        resp = client.get("/api/v1/kb/lint")
        assert resp.status_code == 200
        anomaly_slugs = [t["slug"] for t in resp.json()["score_anomalies"]]
        # "c" is numerically anomalous but sample is below 10 → not flagged.
        assert "c" not in anomaly_slugs

    def test_score_anomaly_flags_outlier_with_sufficient_sample(
        self, client, db_session, kb_lint_db
    ):
        # Seed 10 topics at ~0.5 and one extreme outlier at 0.99 (>3 sigma).
        for i in range(10):
            _make_topic(
                db_session,
                slug=f"cat-{i}",
                relevance_score=0.5,
                category="big",
            )
        _make_topic(db_session, slug="outlier", relevance_score=0.99, category="big")
        resp = client.get("/api/v1/kb/lint")
        assert resp.status_code == 200
        anomaly_slugs = [t["slug"] for t in resp.json()["score_anomalies"]]
        assert "outlier" in anomaly_slugs

    def test_lint_is_read_only(self, client, db_session, kb_lint_db):
        topic = _make_topic(
            db_session,
            slug="unchanged",
            source_content_ids=[],
            related_topic_ids=[],
        )
        status_before = topic.status
        resp = client.get("/api/v1/kb/lint")
        assert resp.status_code == 200
        db_session.expire_all()
        topic = db_session.get(Topic, topic.id)
        assert topic.status == status_before


# ---------------------------------------------------------------------------
# POST /api/v1/kb/lint/fix
# ---------------------------------------------------------------------------


class TestLintFix:
    def test_no_issues_returns_empty_corrections(self, client, db_session, kb_lint_db):
        # Healthy topic: not orphaned, not stale.
        _make_topic(
            db_session,
            slug="healthy",
            last_compiled_at=datetime.now(UTC),
            source_content_ids=[1],
        )
        resp = client.post("/api/v1/kb/lint/fix")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body == {"corrections_applied": []}

    def test_orphans_are_archived(self, client, db_session, kb_lint_db):
        orphan = _make_topic(
            db_session,
            slug="lonely",
            source_content_ids=[],
            related_topic_ids=[],
        )
        resp = client.post("/api/v1/kb/lint/fix")
        assert resp.status_code == 200
        body = resp.json()
        fix_slugs = [c["slug"] for c in body["corrections_applied"]]
        assert "lonely" in fix_slugs

        db_session.expire_all()
        reloaded = db_session.get(Topic, orphan.id)
        assert reloaded.status == TopicStatus.ARCHIVED

    def test_stale_topics_marked_stale(self, client, db_session, kb_lint_db):
        old = datetime.now(UTC) - timedelta(days=60)
        topic = _make_topic(
            db_session,
            slug="old",
            last_compiled_at=old,
            source_content_ids=[1],
            status=TopicStatus.ACTIVE,
        )
        resp = client.post("/api/v1/kb/lint/fix")
        assert resp.status_code == 200
        db_session.expire_all()
        reloaded = db_session.get(Topic, topic.id)
        assert reloaded.status == TopicStatus.STALE
        fix_types = [c["fix_type"] for c in resp.json()["corrections_applied"]]
        assert "status:stale" in fix_types

    def test_fix_records_audit_with_operation(self, client, db_session, kb_lint_db):
        _make_topic(
            db_session,
            slug="healthy",
            last_compiled_at=datetime.now(UTC),
            source_content_ids=[1],
        )
        captured: list[dict] = []

        def capture_writer(**kwargs):
            captured.append(kwargs)

        with patch(
            "src.api.middleware.audit._default_writer",
            side_effect=capture_writer,
        ):
            resp = client.post("/api/v1/kb/lint/fix")

        assert resp.status_code == 200
        fix_rows = [row for row in captured if row.get("path") == "/api/v1/kb/lint/fix"]
        assert fix_rows, f"expected a /kb/lint/fix audit row, captured={captured}"
        assert fix_rows[0]["operation"] == "kb.lint.fix"

    def test_fix_endpoint_requires_auth_in_production(self, monkeypatch):
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
                resp = c.post("/api/v1/kb/lint/fix")
                assert resp.status_code in (401, 403)
        finally:
            get_settings.cache_clear()
