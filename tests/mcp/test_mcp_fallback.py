"""Tests for the `_get_api_client()` helper — HTTP / in-process fallback semantics.

Covers spec scenarios from `specs/mcp-http-client/spec.md`:
- HTTP config present → returns ApiClient
- HTTP config absent → returns None
- Partial config → returns None + stderr warning (never tool-response pollution)
- `--strict-http` flag (via ACA_MCP_STRICT_HTTP env) still returns None so
  callers can produce a typed error rather than silently fall back.
"""

from __future__ import annotations

import pytest

from src.mcp_server import _get_api_client, _strict_http_mode


@pytest.fixture(autouse=True)
def _clean_mcp_env(monkeypatch):
    monkeypatch.delenv("ACA_API_BASE_URL", raising=False)
    monkeypatch.delenv("ACA_ADMIN_KEY", raising=False)
    monkeypatch.delenv("ACA_MCP_STRICT_HTTP", raising=False)
    yield


def test_returns_client_when_both_env_vars_set(monkeypatch):
    monkeypatch.setenv("ACA_API_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("ACA_ADMIN_KEY", "k")
    client = _get_api_client()
    assert client is not None
    assert hasattr(client, "kb_search")
    client.close()


def test_returns_none_when_both_env_vars_absent():
    assert _get_api_client() is None


def test_partial_config_base_only_warns_stderr(monkeypatch, capsys):
    monkeypatch.setenv("ACA_API_BASE_URL", "https://api.example.com")
    assert _get_api_client() is None
    err = capsys.readouterr().err
    assert "ACA_ADMIN_KEY" in err
    assert "partial HTTP config" in err


def test_partial_config_key_only_warns_stderr(monkeypatch, capsys):
    monkeypatch.setenv("ACA_ADMIN_KEY", "k")
    assert _get_api_client() is None
    err = capsys.readouterr().err
    assert "ACA_API_BASE_URL" in err


def test_partial_config_does_not_pollute_stdout(monkeypatch, capsys):
    monkeypatch.setenv("ACA_API_BASE_URL", "https://api.example.com")
    _get_api_client()
    captured = capsys.readouterr()
    assert captured.out == ""


def test_strict_http_mode_env_detection(monkeypatch):
    monkeypatch.setenv("ACA_MCP_STRICT_HTTP", "1")
    assert _strict_http_mode() is True

    monkeypatch.setenv("ACA_MCP_STRICT_HTTP", "on")
    assert _strict_http_mode() is True

    monkeypatch.setenv("ACA_MCP_STRICT_HTTP", "false")
    assert _strict_http_mode() is False

    monkeypatch.delenv("ACA_MCP_STRICT_HTTP", raising=False)
    assert _strict_http_mode() is False


def test_whitespace_only_config_treated_as_absent(monkeypatch):
    monkeypatch.setenv("ACA_API_BASE_URL", "   ")
    monkeypatch.setenv("ACA_ADMIN_KEY", "k")
    # The base_url is whitespace after .strip() → treated as missing.
    assert _get_api_client() is None
