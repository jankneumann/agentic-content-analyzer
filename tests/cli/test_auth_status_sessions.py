"""Tests for the browser-session rows of ``aca auth status``.

Every credential value is a sentinel string that must never reach stdout or
stderr, in text or ``--json`` mode. The durable ``last_verified_at`` lookup is
exercised against a fake asyncpg connection, an ``httpx.MockTransport`` and a
refused connection; nothing touches the network.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from collections.abc import Iterator, Mapping
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from typer.testing import CliRunner

from src.cli import browser_session_status as bss, output
from src.cli.auth_commands import app
from src.config.credentials import CredentialProvider

SUBSTACK_SENTINEL = "SENTINEL-substack-sid-0f9e8d7c"
AUTH_TOKEN_SENTINEL = "SENTINEL-x-auth-token-1a2b3c4d"
CT0_SENTINEL = "SENTINEL-x-ct0-5e6f7a8b"
RAILWAY_SENTINEL = "SENTINEL-railway-gmail-token-9z8y"
SENTINELS = (SUBSTACK_SENTINEL, AUTH_TOKEN_SENTINEL, CT0_SENTINEL, RAILWAY_SENTINEL)

VERIFIED_AT = datetime(2026, 9, 20, 3, 0, tzinfo=UTC)


def _provider(
    bao: Mapping[str, str] | None = None, settings: Mapping[str, str] | None = None
) -> CredentialProvider:
    fields = {"substack_session_cookie": None, "x_auth_token": None, "x_ct0": None}
    fields.update(settings or {})
    return CredentialProvider(
        settings_factory=lambda: SimpleNamespace(**fields),
        bao_reader=lambda: dict(bao or {}),
    )


def _found(**last_success: datetime | None) -> bss.VerificationLookup:
    return bss.VerificationLookup(available=True, last_success=last_success, via="database")


def _rows_by_session(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {row["session"]: row for row in rows}


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """No railway CLI, no process env credentials, and clean CLI mode flags."""
    monkeypatch.setattr("shutil.which", lambda _: None)
    for name in ("SUBSTACK_SESSION_COOKIE", "X_AUTH_TOKEN", "X_CT0"):
        monkeypatch.delenv(name, raising=False)
    yield
    output._set_json_mode(False)
    output._set_direct_mode(False)
    output._set_remote_db(False)


@pytest.fixture
def full_bao(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider(
        bao={
            "SUBSTACK_SESSION_COOKIE": SUBSTACK_SENTINEL,
            "SUBSTACK_SESSION_COOKIE_SAVED_AT": "2026-09-01T10:00:00Z",
            "X_AUTH_TOKEN": AUTH_TOKEN_SENTINEL,
            "X_AUTH_TOKEN_SAVED_AT": "2026-09-10T08:00:00+00:00",
            "X_CT0": CT0_SENTINEL,
            "X_CT0_SAVED_AT": "2026-09-10T08:00:05Z",
        }
    )
    monkeypatch.setattr(bss, "get_credential_provider", lambda: provider)


def _assert_no_secret(*texts: str) -> None:
    for text in texts:
        for sentinel in SENTINELS:
            assert sentinel not in text


# -- rows -------------------------------------------------------------------


def test_rows_report_metadata_and_refresh_command(full_bao: None) -> None:
    rows, verification = bss.build_session_rows(
        lookup=lambda keys: _found(substack=VERIFIED_AT, x_bookmarks=None), environ={}
    )
    by_session = _rows_by_session(rows)

    assert verification.available is True
    substack = by_session["substack"]
    assert substack["present"] is True
    assert substack["source"] == "openbao"
    assert substack["saved_at"] == "2026-09-01T10:00:00Z"
    assert substack["last_verified_at"] == "2026-09-20T03:00:00Z"
    assert substack["last_verified_status"] == "verified"
    assert substack["refresh_command"] == "aca auth session substack"

    x = by_session["x"]
    assert x["present"] is True
    assert x["refresh_command"] == "aca auth session x"
    assert x["verified_by"] == "x_bookmarks"
    assert x["last_verified_at"] is None
    assert x["last_verified_status"] == "never"
    # The pair is only as fresh as its oldest half.
    assert x["saved_at"] == "2026-09-10T08:00:00Z"
    _assert_no_secret(json.dumps(rows))


def test_x_row_requires_both_keys() -> None:
    provider = _provider(bao={"X_AUTH_TOKEN": AUTH_TOKEN_SENTINEL})
    rows, _ = bss.build_session_rows(
        metadata=provider.metadata, lookup=lambda keys: _found(), environ={}
    )
    x = _rows_by_session(rows)["x"]

    assert x["present"] is False
    assert {c["name"]: c["present"] for c in x["credentials"]} == {
        "X_AUTH_TOKEN": True,
        "X_CT0": False,
    }
    assert x["saved_at"] is None


def test_x_row_present_with_both_keys_from_different_sources() -> None:
    provider = _provider(
        bao={"X_AUTH_TOKEN": AUTH_TOKEN_SENTINEL}, settings={"x_ct0": CT0_SENTINEL}
    )
    rows, _ = bss.build_session_rows(
        metadata=provider.metadata, lookup=lambda keys: _found(), environ={}
    )
    x = _rows_by_session(rows)["x"]

    assert x["present"] is True
    assert x["source"] == "mixed"
    assert [c["source"] for c in x["credentials"]] == ["openbao", "settings"]
    # Settings-sourced values carry no saved_at, so the pair has none.
    assert x["saved_at"] is None


def test_env_source_distinguished_from_settings() -> None:
    provider = _provider(settings={"substack_session_cookie": SUBSTACK_SENTINEL})
    rows, _ = bss.build_session_rows(
        metadata=provider.metadata,
        lookup=lambda keys: _found(),
        environ={"SUBSTACK_SESSION_COOKIE": SUBSTACK_SENTINEL},
    )
    assert _rows_by_session(rows)["substack"]["source"] == "env"

    rows, _ = bss.build_session_rows(
        metadata=provider.metadata, lookup=lambda keys: _found(), environ={}
    )
    assert _rows_by_session(rows)["substack"]["source"] == "settings"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026-09-01T10:00:00Z", "2026-09-01T10:00:00Z"),
        ("2026-09-01T12:00:00+02:00", "2026-09-01T10:00:00Z"),
        ("2026-09-01T10:00:00", "2026-09-01T10:00:00Z"),  # naive is UTC
        ("not-a-date", None),
        ("", None),
    ],
)
def test_saved_at_parsing(raw: str, expected: str | None) -> None:
    provider = _provider(
        bao={"SUBSTACK_SESSION_COOKIE": SUBSTACK_SENTINEL, "SUBSTACK_SESSION_COOKIE_SAVED_AT": raw}
    )
    rows, _ = bss.build_session_rows(
        metadata=provider.metadata, lookup=lambda keys: _found(), environ={}
    )
    assert _rows_by_session(rows)["substack"]["saved_at"] == expected


def test_lookup_is_asked_for_the_gated_command_keys() -> None:
    asked: list[list[str]] = []

    def lookup(keys: Any) -> bss.VerificationLookup:
        asked.append(list(keys))
        return _found()

    bss.build_session_rows(metadata=_provider().metadata, lookup=lookup, environ={})
    assert asked == [["substack", "x_bookmarks"]]


# -- durable last_verified_at lookup ----------------------------------------


def _history_row(job_id: int, command_key: str, outcome: str, completed_at: datetime) -> dict:
    return {
        "id": job_id,
        "entrypoint": "ingestion.execute",
        "status": "completed",
        "payload": {
            "schema_version": 2,
            "operation_type": "ingestion.execute",
            "input": {"kind": command_key, "session_cookie": SUBSTACK_SENTINEL},
            "progress": 100,
            "message": "Done",
            "result": {
                "schema_version": 2,
                "command_key": command_key,
                "outcome": outcome,
                "items_ingested": 1 if outcome == "success" else 0,
                "items_skipped": 0,
                "items_failed": 0,
                "source_outcomes": [],
            },
        },
        "priority": 0,
        "error": None,
        "retry_count": 0,
        "parent_job_id": None,
        "heartbeat_at": None,
        "created_at": completed_at,
        "started_at": completed_at,
        "completed_at": completed_at,
    }


def test_database_lookup_takes_latest_verifying_outcome() -> None:
    older = datetime(2026, 9, 18, 3, 0, tzinfo=UTC)
    newer = datetime(2026, 9, 21, 3, 0, tzinfo=UTC)
    by_query = {
        ("substack", "success"): [_history_row(1, "substack", "success", older)],
        ("substack", "zero_items"): [_history_row(2, "substack", "zero_items", newer)],
    }
    conn = MagicMock()

    async def fetch(_query: str, *args: Any) -> list[dict]:
        # $3 = command_key, $5 = outcome in list_ingestion_history.
        return by_query.get((args[2], args[4]), [])

    conn.fetch = AsyncMock(side_effect=fetch)

    found = bss._lookup_via_database(["substack", "x_bookmarks"], 5.0, connection=conn)

    assert found == {"substack": newer, "x_bookmarks": None}
    outcomes = sorted({call.args[5] for call in conn.fetch.await_args_list})
    assert outcomes == ["success", "zero_items"]


def test_lookup_reports_database_down(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(output, "is_remote_backend", lambda: False)
    monkeypatch.setattr(
        "src.queue.setup._open_queue_connection",
        AsyncMock(side_effect=ConnectionRefusedError("refused")),
    )

    verification = bss.lookup_last_verified(["substack"])

    assert verification.available is False
    assert verification.reason == "ConnectionRefusedError"


def test_lookup_is_bounded_by_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(output, "is_remote_backend", lambda: False)

    async def hang(*_args: Any, **_kwargs: Any) -> None:
        await asyncio.sleep(30)

    monkeypatch.setattr("src.queue.setup._open_queue_connection", hang)

    verification = bss.lookup_last_verified(["substack"], timeout_s=0.05)

    assert verification.available is False
    assert verification.reason == "TimeoutError"


def test_lookup_refuses_direct_read_under_remote_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(output, "is_remote_backend", lambda: True)
    output._set_direct_mode(True)
    opened = AsyncMock()
    monkeypatch.setattr("src.queue.setup._open_queue_connection", opened)

    verification = bss.lookup_last_verified(["substack"])

    assert verification.available is False
    assert "--remote-db" in (verification.reason or "")
    opened.assert_not_called()


def test_api_lookup_under_remote_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(output, "is_remote_backend", lambda: True)
    requests: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url)
        params = request.url.params
        data = []
        if params["command_key"] == "substack" and params["outcome"] == "success":
            data.append(
                {
                    "operation_id": "17",
                    "command_key": "substack",
                    "operation_status": "completed",
                    "outcome": "success",
                    "items_ingested": 2,
                    "items_skipped": 0,
                    "items_failed": 0,
                    "source_outcomes": [],
                    "retry_count": 0,
                    "status_url": "/api/v1/operations/17",
                    "created_at": "2026-09-20T02:59:00Z",
                    "completed_at": "2026-09-20T03:00:00Z",
                }
            )
        return httpx.Response(200, json={"data": data, "next_cursor": None})

    real_lookup = bss._lookup_via_api
    monkeypatch.setattr(
        bss,
        "_lookup_via_api",
        lambda keys, timeout_s: real_lookup(
            keys, timeout_s, transport=httpx.MockTransport(handler)
        ),
    )

    verification = bss.lookup_last_verified(["substack", "x_bookmarks"])

    assert verification.available is True
    assert verification.via == "api"
    assert verification.last_success == {"substack": VERIFIED_AT, "x_bookmarks": None}
    assert {url.path for url in requests} == {"/api/v1/ingestions"}
    # Absent filters are omitted, never serialized as empty query values.
    for url in requests:
        assert set(url.params.keys()) == {"limit", "command_key", "outcome"}
        assert url.params["limit"] == "1"


def test_api_lookup_problem_is_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(output, "is_remote_backend", lambda: True)
    real_lookup = bss._lookup_via_api

    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(
        bss,
        "_lookup_via_api",
        lambda keys, timeout_s: real_lookup(
            keys, timeout_s, transport=httpx.MockTransport(handler)
        ),
    )

    verification = bss.lookup_last_verified(["substack"])
    assert verification.available is False
    assert verification.reason == "ConnectError"


# -- aca auth status --------------------------------------------------------


def test_status_text_renders_sessions_without_values(
    runner: CliRunner, full_bao: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        bss, "lookup_last_verified", lambda keys: _found(substack=VERIFIED_AT, x_bookmarks=None)
    )

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0, result.output
    assert "Browser session status" in result.stdout
    assert "substack: [present, source openbao]" in result.stdout
    assert "aca auth session substack" in result.stdout
    assert "aca auth session x" in result.stdout
    assert "2026-09-20T03:00:00Z (last successful substack ingestion)" in result.stdout
    assert "never (no successful x_bookmarks ingestion)" in result.stdout
    assert "gmail" in result.stdout
    _assert_no_secret(result.stdout, result.stderr)


def test_status_text_flags_verification_older_than_save(
    runner: CliRunner, full_bao: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    before_save = datetime(2026, 8, 1, tzinfo=UTC)
    monkeypatch.setattr(bss, "lookup_last_verified", lambda keys: _found(substack=before_save))

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0, result.output
    assert "not yet verified since the last save" in result.stdout


def test_status_survives_database_down(
    runner: CliRunner, full_bao: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(output, "is_remote_backend", lambda: False)
    monkeypatch.setattr(
        "src.queue.setup._open_queue_connection",
        AsyncMock(side_effect=ConnectionRefusedError("refused")),
    )

    text = runner.invoke(app, ["status"])
    assert text.exit_code == 0, text.output
    assert "unknown (ingestion history unavailable)" in text.stdout
    assert "ConnectionRefusedError" in text.stderr

    as_json = runner.invoke(app, ["status", "--json"])
    assert as_json.exit_code == 0, as_json.output
    document = json.loads(as_json.stdout)
    assert document["last_verified_lookup"] == {
        "available": False,
        "via": None,
        "reason": "ConnectionRefusedError",
    }
    for row in document["browser_sessions"]:
        assert row["last_verified_at"] is None
        assert row["last_verified_status"] == "unknown"
    assert "ConnectionRefusedError" in as_json.stderr
    _assert_no_secret(text.stdout, text.stderr, as_json.stdout, as_json.stderr)


def test_status_json_is_one_document_without_values(
    runner: CliRunner, full_bao: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("shutil.which", lambda _: "/usr/local/bin/railway")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: MagicMock(
            returncode=0, stdout=f"GMAIL_OAUTH_TOKEN_JSON={RAILWAY_SENTINEL}\n", stderr=""
        ),
    )
    monkeypatch.setattr(
        bss, "lookup_last_verified", lambda keys: _found(substack=VERIFIED_AT, x_bookmarks=None)
    )

    result = runner.invoke(app, ["status", "--json"])

    assert result.exit_code == 0, result.output
    document = json.loads(result.stdout)  # exactly one JSON document
    assert set(document) == {"oauth", "browser_sessions", "last_verified_lookup"}
    assert [row["provider"] for row in document["oauth"]] == ["gmail", "youtube"]
    assert document["oauth"][0]["railway"]["token_set"] is True
    sessions = _rows_by_session(document["browser_sessions"])
    assert set(sessions) == {"substack", "x"}
    for row in sessions.values():
        assert {
            "session",
            "present",
            "source",
            "saved_at",
            "last_verified_at",
            "last_verified_status",
            "refresh_command",
            "credentials",
        } <= set(row)
    assert sessions["substack"]["last_verified_at"] == "2026-09-20T03:00:00Z"
    assert sessions["x"]["refresh_command"] == "aca auth session x"
    assert "OAuth credential status" not in result.stdout
    _assert_no_secret(result.stdout, result.stderr)


def test_global_json_flag_selects_json(
    runner: CliRunner, full_bao: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bss, "lookup_last_verified", lambda keys: _found())
    output._set_json_mode(True)

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0, result.output
    assert set(json.loads(result.stdout)) == {"oauth", "browser_sessions", "last_verified_lookup"}
