"""Transport-resilience tests (design.md D11).

The `ApiClient._request_with_retry` implements the D11 policy:
- 30s per-request timeout
- 1 retry with 1s backoff on {429, 502, 503, 504, connect/read error}
- Non-retryable 4xx propagates immediately
- Timeout does NOT silently fall back — it raises, so the MCP tool surfaces
  an error rather than masking the problem as in-process success.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest

from src.cli.api_client import ApiClient


def _make_response(status_code: int, body: dict | None = None) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = body or {}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"status={status_code}", request=MagicMock(), response=resp
        )
    return resp


def test_retryable_503_is_retried_once_then_succeeds(monkeypatch):
    client = ApiClient(base_url="http://test", admin_key="k")
    calls = iter([_make_response(503), _make_response(200, {"ok": True})])
    monkeypatch.setattr(client._client, "request", lambda *a, **k: next(calls))
    # Patch sleep to zero so test is fast.
    monkeypatch.setattr("src.cli.api_client.time.sleep", lambda s: None)
    result = client._request_with_retry("GET", "/api/v1/kb/search")
    assert result == {"ok": True}
    client.close()


def test_retryable_all_attempts_fail_raises(monkeypatch):
    client = ApiClient(base_url="http://test", admin_key="k")
    resp = _make_response(502)
    monkeypatch.setattr(client._client, "request", lambda *a, **k: resp)
    monkeypatch.setattr("src.cli.api_client.time.sleep", lambda s: None)
    with pytest.raises(httpx.HTTPStatusError):
        client._request_with_retry("GET", "/api/v1/kb/search")
    client.close()


def test_non_retryable_400_propagates_without_retry(monkeypatch):
    client = ApiClient(base_url="http://test", admin_key="k")
    call_count = {"n": 0}

    def fake_request(*a, **k):
        call_count["n"] += 1
        return _make_response(400)

    monkeypatch.setattr(client._client, "request", fake_request)
    monkeypatch.setattr("src.cli.api_client.time.sleep", lambda s: None)
    with pytest.raises(httpx.HTTPStatusError):
        client._request_with_retry("GET", "/api/v1/kb/search")
    # Non-retryable: called exactly once, no retry.
    assert call_count["n"] == 1
    client.close()


def test_connect_error_is_retried(monkeypatch):
    client = ApiClient(base_url="http://test", admin_key="k")
    call_count = {"n": 0}

    def fake_request(*a, **k):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise httpx.ConnectError("connection refused")
        return _make_response(200, {"ok": True})

    monkeypatch.setattr(client._client, "request", fake_request)
    monkeypatch.setattr("src.cli.api_client.time.sleep", lambda s: None)
    result = client._request_with_retry("GET", "/api/v1/kb/search")
    assert result == {"ok": True}
    assert call_count["n"] == 2
    client.close()


def test_timeout_is_not_retried_as_transient(monkeypatch):
    """httpx.TimeoutException isn't in our retryable set — it surfaces to caller."""
    client = ApiClient(base_url="http://test", admin_key="k")

    def fake_request(*a, **k):
        raise httpx.TimeoutException("read timeout")

    monkeypatch.setattr(client._client, "request", fake_request)
    monkeypatch.setattr("src.cli.api_client.time.sleep", lambda s: None)
    with pytest.raises(httpx.TimeoutException):
        client._request_with_retry("GET", "/api/v1/kb/search")
    client.close()


def test_retry_policy_respects_custom_attempts(monkeypatch):
    client = ApiClient(base_url="http://test", admin_key="k")
    call_count = {"n": 0}

    def fake_request(*a, **k):
        call_count["n"] += 1
        return _make_response(503)

    monkeypatch.setattr(client._client, "request", fake_request)
    monkeypatch.setattr("src.cli.api_client.time.sleep", lambda s: None)
    with pytest.raises(httpx.HTTPStatusError):
        client._request_with_retry("GET", "/api/v1/kb/search", attempts=2)
    # attempts=2 → 3 total calls (1 initial + 2 retries).
    assert call_count["n"] == 3
    client.close()
