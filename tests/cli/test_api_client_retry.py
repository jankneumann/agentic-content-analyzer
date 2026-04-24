"""CLI-side tests for the new retry + timeout behavior on `ApiClient`.

Ensures the 4 new MCP-style methods (`kb_search`, `graph_query`,
`references_extract`, `references_resolve`) all route through
`_request_with_retry` with the D11 defaults (30s timeout, 1 retry).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx

from src.cli.api_client import ApiClient


def _ok(body: dict) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.json.return_value = body
    resp.raise_for_status = MagicMock()
    return resp


def test_kb_search_routes_through_retry_wrapper():
    client = ApiClient(base_url="http://test", admin_key="k")
    with patch.object(
        client, "_request_with_retry", return_value={"topics": [], "total_count": 0}
    ) as m:
        result = client.kb_search(query="x", limit=5)
    m.assert_called_once_with("GET", "/api/v1/kb/search", params={"q": "x", "limit": 5})
    assert result == {"topics": [], "total_count": 0}
    client.close()


def test_graph_query_routes_through_retry_wrapper():
    client = ApiClient(base_url="http://test", admin_key="k")
    with patch.object(
        client, "_request_with_retry", return_value={"entities": [], "relationships": []}
    ) as m:
        result = client.graph_query(query="x", limit=5)
    m.assert_called_once_with("POST", "/api/v1/graph/query", json={"query": "x", "limit": 5})
    assert "entities" in result
    client.close()


def test_references_extract_drops_none_values():
    client = ApiClient(base_url="http://test", admin_key="k")
    with patch.object(
        client,
        "_request_with_retry",
        return_value={"references_extracted": 0, "content_processed": 0, "has_more": False},
    ) as m:
        client.references_extract(since="2026-04-01", until=None, batch_size=50)
    call = m.call_args
    # None values stripped from payload.
    assert call.kwargs["json"] == {"since": "2026-04-01", "batch_size": 50}
    client.close()


def test_references_resolve_default_body_is_empty_dict():
    client = ApiClient(base_url="http://test", admin_key="k")
    with patch.object(
        client,
        "_request_with_retry",
        return_value={"resolved_count": 0, "still_unresolved_count": 0, "has_more": False},
    ) as m:
        client.references_resolve()
    assert m.call_args.kwargs["json"] == {}
    client.close()


def test_references_resolve_with_batch_size():
    client = ApiClient(base_url="http://test", admin_key="k")
    with patch.object(
        client,
        "_request_with_retry",
        return_value={"resolved_count": 0, "still_unresolved_count": 0, "has_more": False},
    ) as m:
        client.references_resolve(batch_size=200)
    assert m.call_args.kwargs["json"] == {"batch_size": 200}
    client.close()


def test_default_timeout_is_30_seconds(monkeypatch):
    """D11: MCP endpoints should use a 30s timeout by default."""
    from src.cli.api_client import _MCP_REQUEST_TIMEOUT

    assert _MCP_REQUEST_TIMEOUT == 30.0


def test_default_retry_attempts_is_one():
    from src.cli.api_client import _DEFAULT_RETRY_ATTEMPTS

    assert _DEFAULT_RETRY_ATTEMPTS == 1


def test_default_retry_backoff_is_one_second():
    from src.cli.api_client import _DEFAULT_RETRY_BACKOFF_SECONDS

    assert _DEFAULT_RETRY_BACKOFF_SECONDS == 1.0


def test_retryable_statuses_match_d11_matrix():
    from src.cli.api_client import _RETRYABLE_STATUS

    # D11: {429, 502, 503, 504, connection-reset}. Status subset:
    assert frozenset({429, 502, 503, 504}) == _RETRYABLE_STATUS
