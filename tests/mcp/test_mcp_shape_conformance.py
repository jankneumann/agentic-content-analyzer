"""Shape-conformance tests for the 4 refactored MCP tools.

Each tool's return shape (both HTTP and in-process mode) must match the
corresponding OpenAPI schema in `contracts/openapi/v1.yaml`. This test
validates at the key-presence + type level — per PLAN_FIX round 2 H2, the
MCP and OpenAPI shapes are canonical and must not drift.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src import mcp_server as mcp

# ---------------------------------------------------------------------------
# Canonical required-field sets from contracts/openapi/v1.yaml
# ---------------------------------------------------------------------------

KB_SEARCH_RESULT_REQUIRED = {"slug", "title", "score", "excerpt", "last_compiled_at"}
KB_SEARCH_TOP_REQUIRED = {"topics", "total_count"}

GRAPH_ENTITY_REQUIRED = {"id", "name", "type", "score"}
GRAPH_RELATIONSHIP_REQUIRED = {"source_id", "target_id", "type", "score"}
GRAPH_QUERY_TOP_REQUIRED = {"entities", "relationships"}

REFS_EXTRACT_REQUIRED = {"references_extracted", "content_processed", "has_more"}
REFS_RESOLVE_REQUIRED = {"resolved_count", "still_unresolved_count", "has_more"}


@pytest.fixture
def http_mode_env(monkeypatch):
    monkeypatch.setenv("ACA_API_BASE_URL", "https://api.test.example")
    monkeypatch.setenv("ACA_ADMIN_KEY", "k")
    monkeypatch.delenv("ACA_MCP_STRICT_HTTP", raising=False)


# ---------------------------------------------------------------------------
# HTTP-mode shape pass-through (shape set by the server; MCP only forwards)
# ---------------------------------------------------------------------------


def test_kb_search_http_response_has_required_keys(http_mode_env):
    client = MagicMock()
    client.kb_search.return_value = {
        "topics": [
            {
                "slug": "moe",
                "title": "Mixture of Experts",
                "score": 0.87,
                "excerpt": "Sparse MoE models...",
                "last_compiled_at": "2026-04-20T10:00:00Z",
            }
        ],
        "total_count": 1,
    }
    with patch.object(mcp, "_get_api_client", return_value=client):
        data = json.loads(mcp.search_knowledge_base(query="moe"))
    assert KB_SEARCH_TOP_REQUIRED.issubset(data.keys())
    for topic in data["topics"]:
        assert KB_SEARCH_RESULT_REQUIRED.issubset(topic.keys())


def test_graph_query_http_response_has_score_on_relationships(http_mode_env):
    client = MagicMock()
    client.graph_query.return_value = {
        "entities": [{"id": "a", "name": "A", "type": "Model", "score": 0.9}],
        "relationships": [{"source_id": "a", "target_id": "b", "type": "USES", "score": 0.8}],
    }
    with patch.object(mcp, "_get_api_client", return_value=client):
        data = json.loads(mcp.search_knowledge_graph(query="ai"))
    assert GRAPH_QUERY_TOP_REQUIRED.issubset(data.keys())
    for rel in data["relationships"]:
        assert GRAPH_RELATIONSHIP_REQUIRED.issubset(rel.keys())
        assert isinstance(rel["score"], (int, float))


def test_extract_references_http_response_has_has_more(http_mode_env):
    client = MagicMock()
    client.references_extract.return_value = {
        "references_extracted": 0,
        "content_processed": 0,
        "has_more": False,
    }
    with patch.object(mcp, "_get_api_client", return_value=client):
        data = json.loads(mcp.extract_references(after="2026-04-01"))
    assert REFS_EXTRACT_REQUIRED.issubset(data.keys())
    # next_cursor should be absent when has_more=False.
    if not data["has_more"]:
        assert "next_cursor" not in data or data["next_cursor"] is None


def test_resolve_references_http_response_has_required_keys(http_mode_env):
    client = MagicMock()
    client.references_resolve.return_value = {
        "resolved_count": 0,
        "still_unresolved_count": 0,
        "has_more": False,
    }
    with patch.object(mcp, "_get_api_client", return_value=client):
        data = json.loads(mcp.resolve_references())
    assert REFS_RESOLVE_REQUIRED.issubset(data.keys())


# ---------------------------------------------------------------------------
# In-process mode shape conformance (the harder test — adapters must match)
# ---------------------------------------------------------------------------


def test_search_knowledge_base_inprocess_shape_conforms(monkeypatch):
    """IR-006 fix: in-process MUST match HTTP behavior exactly — including
    dropping rows whose last_compiled_at/updated_at/created_at are all None
    (no fabricated `datetime.now()` timestamps)."""
    from datetime import UTC, datetime

    monkeypatch.delenv("ACA_API_BASE_URL", raising=False)
    monkeypatch.delenv("ACA_ADMIN_KEY", raising=False)

    # Topic with a valid last_compiled_at — included.
    compiled = MagicMock()
    compiled.slug = "demo"
    compiled.name = "Demo Title"
    compiled.status = None
    compiled.summary = "demo summary text"
    compiled.article_md = "Demo article mentions demo in text."
    compiled.relevance_score = 0.5
    compiled.mention_count = 3
    compiled.last_compiled_at = datetime(2026, 4, 20, 10, tzinfo=UTC)
    compiled.updated_at = None
    compiled.created_at = None

    # Topic with NO timestamp at all — dropped to match HTTP.
    orphan = MagicMock()
    orphan.slug = "demo-orphan"
    orphan.name = "Demo Orphan"
    orphan.status = None
    orphan.summary = "demo but unpublished"
    orphan.article_md = "demo"
    orphan.relevance_score = 0.3
    orphan.mention_count = 1
    orphan.last_compiled_at = None
    orphan.updated_at = None
    orphan.created_at = None

    class FakeQuery:
        def filter(self, *a, **k):
            return self

        def order_by(self, *a):
            return self

        def limit(self, *a):
            return self

        def all(self):
            return [compiled, orphan]

    class FakeDB:
        def query(self, *a):
            return FakeQuery()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    def fake_get_db():
        return FakeDB()

    with patch("src.storage.database.get_db", fake_get_db):
        data = json.loads(mcp.search_knowledge_base(query="demo"))

    assert KB_SEARCH_TOP_REQUIRED.issubset(data.keys())
    # Orphan dropped → only one topic returned, matching HTTP semantics.
    assert len(data["topics"]) == 1
    assert data["topics"][0]["slug"] == "demo"
    assert KB_SEARCH_RESULT_REQUIRED.issubset(data["topics"][0].keys())
    assert isinstance(data["topics"][0]["last_compiled_at"], str)
    # total_count is the FULL ranked count (pre-limit) — the orphan matched the
    # query too, so it's still counted in the total even though excluded from
    # topics (mirrors HTTP behavior before the timestamp filter).
    assert data["total_count"] >= 1


def test_resolve_references_inprocess_shape_conforms(monkeypatch):
    monkeypatch.delenv("ACA_API_BASE_URL", raising=False)
    monkeypatch.delenv("ACA_ADMIN_KEY", raising=False)

    class FakeResolver:
        def __init__(self, db):
            pass

        def resolve_batch(self, n):
            return 4

    class FakeCountQuery:
        def filter(self, *a, **k):
            return self

        def count(self):
            return 9

    class FakeDB:
        def query(self, *a):
            return FakeCountQuery()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    def fake_get_db():
        return FakeDB()

    with (
        patch("src.services.reference_resolver.ReferenceResolver", FakeResolver),
        patch("src.storage.database.get_db", fake_get_db),
    ):
        data = json.loads(mcp.resolve_references(batch_size=50))

    assert REFS_RESOLVE_REQUIRED.issubset(data.keys())
    assert data["resolved_count"] == 4
    assert data["still_unresolved_count"] == 9
    assert data["has_more"] is True  # 9 still unresolved
