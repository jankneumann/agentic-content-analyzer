"""Tests for HTTP-mode routing of the 4 MCP tools.

When `ACA_API_BASE_URL` + `ACA_ADMIN_KEY` are set, each tool must call the
corresponding HTTP endpoint via `ApiClient` instead of executing in-process.

Tests mock `ApiClient` methods and verify the tool's JSON output is derived
from the mocked HTTP response, confirming the HTTP branch was taken.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src import mcp_server as mcp


@pytest.fixture
def http_mode_env(monkeypatch):
    monkeypatch.setenv("ACA_API_BASE_URL", "https://api.test.example")
    monkeypatch.setenv("ACA_ADMIN_KEY", "test-key")
    monkeypatch.delenv("ACA_MCP_STRICT_HTTP", raising=False)


def _make_client(**method_returns):
    client = MagicMock()
    for name, value in method_returns.items():
        getattr(client, name).return_value = value
    client.close = MagicMock()
    return client


def test_search_knowledge_base_http_mode_calls_kb_search(http_mode_env):
    fake_client = _make_client(
        kb_search={
            "topics": [
                {
                    "slug": "moe",
                    "title": "Mixture of Experts",
                    "score": 0.9,
                    "excerpt": "Sparse MoE...",
                    "last_compiled_at": "2026-04-20T10:00:00Z",
                }
            ],
            "total_count": 1,
        }
    )
    with patch.object(mcp, "_get_api_client", return_value=fake_client):
        raw = mcp.search_knowledge_base(query="moe", limit=5)
    fake_client.kb_search.assert_called_once_with(query="moe", limit=5)
    fake_client.close.assert_called_once()
    assert json.loads(raw) == {
        "topics": [
            {
                "slug": "moe",
                "title": "Mixture of Experts",
                "score": 0.9,
                "excerpt": "Sparse MoE...",
                "last_compiled_at": "2026-04-20T10:00:00Z",
            }
        ],
        "total_count": 1,
    }


def test_search_knowledge_graph_http_mode_calls_graph_query(http_mode_env):
    fake_client = _make_client(
        graph_query={
            "entities": [{"id": "a", "name": "A", "type": "Model", "score": 0.8}],
            "relationships": [{"source_id": "a", "target_id": "b", "type": "USES", "score": 0.7}],
        }
    )
    with patch.object(mcp, "_get_api_client", return_value=fake_client):
        raw = mcp.search_knowledge_graph(query="transformer", limit=3)
    fake_client.graph_query.assert_called_once_with(query="transformer", limit=3)
    data = json.loads(raw)
    assert data["entities"][0]["name"] == "A"
    assert data["relationships"][0]["score"] == 0.7


def test_extract_references_http_mode_passes_since_until(http_mode_env):
    fake_client = _make_client(
        references_extract={
            "references_extracted": 3,
            "content_processed": 2,
            "has_more": False,
        }
    )
    with patch.object(mcp, "_get_api_client", return_value=fake_client):
        raw = mcp.extract_references(after="2026-04-01", before="2026-04-15", batch_size=20)
    fake_client.references_extract.assert_called_once()
    kwargs = fake_client.references_extract.call_args.kwargs
    assert kwargs["since"] == "2026-04-01"
    assert kwargs["until"] == "2026-04-15"
    assert kwargs["batch_size"] == 20
    data = json.loads(raw)
    assert data["has_more"] is False


def test_extract_references_falls_back_to_in_process_when_unsupported_filter(http_mode_env):
    # HTTP endpoint doesn't accept source/dry_run — we fall through.
    # Use a mock that will fail if HTTP path is taken.
    fake_client = _make_client()
    fake_client.references_extract.side_effect = AssertionError("HTTP should not be called")
    # In-process path needs a DB — stub get_db so we just verify we didn't hit HTTP.
    with patch.object(mcp, "_get_api_client", return_value=fake_client):
        try:
            mcp.extract_references(source="rss", batch_size=1)
        except Exception:
            # DB call may fail — that's fine, we're only verifying HTTP wasn't called.
            pass
    fake_client.references_extract.assert_not_called()


def test_resolve_references_http_mode_calls_references_resolve(http_mode_env):
    fake_client = _make_client(
        references_resolve={
            "resolved_count": 7,
            "still_unresolved_count": 12,
            "has_more": True,
        }
    )
    with patch.object(mcp, "_get_api_client", return_value=fake_client):
        raw = mcp.resolve_references(batch_size=50)
    fake_client.references_resolve.assert_called_once_with(batch_size=50)
    data = json.loads(raw)
    assert data == {"resolved_count": 7, "still_unresolved_count": 12, "has_more": True}


def test_strict_http_mode_returns_error_when_config_missing(monkeypatch):
    monkeypatch.delenv("ACA_API_BASE_URL", raising=False)
    monkeypatch.delenv("ACA_ADMIN_KEY", raising=False)
    monkeypatch.setenv("ACA_MCP_STRICT_HTTP", "1")
    raw = mcp.search_knowledge_base(query="anything", limit=1)
    data = json.loads(raw)
    assert data["error"] == "strict_http_unavailable"
    assert data["tool"] == "search_knowledge_base"
