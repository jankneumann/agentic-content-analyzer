"""Tests for ``POST /api/v1/graph/query`` and ``POST /api/v1/graph/extract-entities``.

Covers:
- query returns entities + relationships with required ``score`` on each
  relationship; empty query response
- query returns 504 on graph backend timeout (10s)
- extract-entities: success returns 200 with ``graph_episode_id``
- extract-entities: 404 when content missing (RFC 7807 Problem body)
- extract-entities: 409 when content has no summary (RFC 7807 Problem body)
- extract-entities: 504 on graph backend timeout (30s)
- extract-entities: audit row is written with ``operation=graph.extract_entities``
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.content import Content, ContentSource, ContentStatus
from src.models.summary import Summary

pytestmark = pytest.mark.usefixtures("api_test_env")


@pytest.fixture
def graph_db(monkeypatch, db_session):
    """Patch get_db in the new graph_routes module."""

    @contextmanager
    def _fake_get_db():
        yield db_session

    monkeypatch.setattr("src.api.routes.graph_routes.get_db", _fake_get_db)
    return _fake_get_db


def _mock_graphiti_client(results=None):
    """Return an AsyncMock that behaves like GraphitiClient."""
    client = MagicMock()
    client.search_related_concepts = AsyncMock(return_value=results or [])
    client.add_content_summary = AsyncMock(return_value="episode-123")
    client.close = MagicMock()
    return client


def _patch_graphiti(client_mock):
    """Patch ``GraphitiClient.create`` inside graph_routes."""
    return patch(
        "src.storage.graphiti_client.GraphitiClient.create",
        AsyncMock(return_value=client_mock),
    )


# ---------------------------------------------------------------------------
# POST /api/v1/graph/query
# ---------------------------------------------------------------------------


class TestGraphQuery:
    def test_returns_entities_and_relationships(self, client, graph_db):
        raw = [
            {
                "uuid": "entity-1",
                "name": "Mixture of Experts",
                "type": "Concept",
                "score": 0.9,
            },
            {
                "source_node_uuid": "e1",
                "target_node_uuid": "e2",
                "name": "USES",
                "score": 0.85,
            },
        ]
        with _patch_graphiti(_mock_graphiti_client(raw)):
            resp = client.post(
                "/api/v1/graph/query",
                json={"query": "mixture of experts", "limit": 20},
            )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert len(body["entities"]) == 1
        assert len(body["relationships"]) == 1
        entity = body["entities"][0]
        assert set(entity.keys()) == {"id", "name", "type", "score"}
        rel = body["relationships"][0]
        assert set(rel.keys()) == {"source_id", "target_id", "type", "score"}
        assert isinstance(rel["score"], float)

    def test_empty_result(self, client, graph_db):
        with _patch_graphiti(_mock_graphiti_client([])):
            resp = client.post("/api/v1/graph/query", json={"query": "nothing"})
        assert resp.status_code == 200
        body = resp.json()
        assert body == {"entities": [], "relationships": []}

    def test_empty_query_rejected_422(self, client, graph_db):
        resp = client.post("/api/v1/graph/query", json={"query": ""})
        assert resp.status_code == 422

    def test_missing_query_rejected_422(self, client, graph_db):
        resp = client.post("/api/v1/graph/query", json={})
        assert resp.status_code == 422

    def test_timeout_returns_504(self, client, graph_db):
        async def slow_search(*_a, **_kw):
            raise TimeoutError  # simulate wait_for raising

        mock_client = _mock_graphiti_client()
        mock_client.search_related_concepts = AsyncMock(side_effect=asyncio.TimeoutError)
        with _patch_graphiti(mock_client):
            resp = client.post("/api/v1/graph/query", json={"query": "timeout"})

        assert resp.status_code == 504
        assert "application/problem+json" in resp.headers.get("content-type", "")
        body = resp.json()
        assert body["status"] == 504
        assert body["title"] == "Gateway Timeout"


# ---------------------------------------------------------------------------
# POST /api/v1/graph/extract-entities
# ---------------------------------------------------------------------------


def _seed_content(db_session, *, include_summary: bool = True) -> int:
    content = Content(
        source_type=ContentSource.GMAIL,
        source_id="seed-1",
        title="Test content",
        markdown_content="# Title\nBody.",
        content_hash="hash-seed-1",
        status=ContentStatus.COMPLETED,
        ingested_at=datetime.now(UTC),
    )
    db_session.add(content)
    db_session.commit()
    db_session.refresh(content)
    if include_summary:
        summary = Summary(
            content_id=content.id,
            executive_summary="Exec",
            key_themes=["llm"],
            strategic_insights=["insight"],
            technical_details=[],
            actionable_items=[],
            notable_quotes=[],
            relevance_scores={"cto_leadership": 0.8},
            agent_framework="claude",
            model_used="claude-sonnet-4-5",
        )
        db_session.add(summary)
        db_session.commit()
    return content.id


class TestExtractEntities:
    def test_success_returns_episode_id(self, client, db_session, graph_db):
        content_id = _seed_content(db_session, include_summary=True)
        mock_client = _mock_graphiti_client()
        mock_client.add_content_summary = AsyncMock(return_value="ep-success")
        with _patch_graphiti(mock_client):
            resp = client.post(
                "/api/v1/graph/extract-entities",
                json={"content_id": content_id},
            )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["graph_episode_id"] == "ep-success"
        assert "entities_added" in body
        assert "relationships_added" in body

    def test_missing_content_returns_404(self, client, graph_db):
        resp = client.post(
            "/api/v1/graph/extract-entities",
            json={"content_id": 999999},
        )
        assert resp.status_code == 404

    def test_content_without_summary_returns_409(self, client, db_session, graph_db):
        content_id = _seed_content(db_session, include_summary=False)
        resp = client.post(
            "/api/v1/graph/extract-entities",
            json={"content_id": content_id},
        )
        assert resp.status_code == 409

    def test_timeout_returns_504(self, client, db_session, graph_db):
        content_id = _seed_content(db_session, include_summary=True)
        mock_client = _mock_graphiti_client()
        mock_client.add_content_summary = AsyncMock(side_effect=asyncio.TimeoutError)
        with _patch_graphiti(mock_client):
            resp = client.post(
                "/api/v1/graph/extract-entities",
                json={"content_id": content_id},
            )

        assert resp.status_code == 504
        body = resp.json()
        assert body["status"] == 504
        assert "application/problem+json" in resp.headers.get("content-type", "")

    def test_audit_records_operation(self, client, db_session, graph_db):
        content_id = _seed_content(db_session, include_summary=True)
        captured: list[dict] = []

        def capture_writer(**kwargs):
            captured.append(kwargs)

        mock_client = _mock_graphiti_client()
        mock_client.add_content_summary = AsyncMock(return_value="ep-audit")
        with (
            _patch_graphiti(mock_client),
            patch(
                "src.api.middleware.audit._default_writer",
                side_effect=capture_writer,
            ),
        ):
            resp = client.post(
                "/api/v1/graph/extract-entities",
                json={"content_id": content_id},
            )
        assert resp.status_code == 200
        rows = [row for row in captured if row.get("path") == "/api/v1/graph/extract-entities"]
        assert rows, f"expected audit row, captured={captured}"
        assert rows[0]["operation"] == "graph.extract_entities"

    def test_rejects_extra_fields_422(self, client, graph_db):
        resp = client.post(
            "/api/v1/graph/extract-entities",
            json={"content_id": 1, "extra": "nope"},
        )
        assert resp.status_code == 422
