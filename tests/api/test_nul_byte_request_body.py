"""Regression tests: NUL bytes in JSON request *bodies* must yield 4xx, never 500.

Background
----------
PR #482 added :class:`NulByteGuardMiddleware` for NUL bytes in the URL path and
query string. Request bodies were left uncovered, so the same character class
still reached the drivers — and the two drivers disagree about what to raise:

- SQLAlchemy/psycopg2 raises a bare ``builtins.ValueError``
  ("A string literal cannot contain NUL (0x00) characters."), which no handler
  maps, so it falls through to the catch-all and returns **500**.
- asyncpg raises ``UntranslatableCharacterError``, a subclass of
  ``asyncpg.exceptions.DataError``, which *is* mapped to 422.

``POST /api/v1/agent/task`` hits the psycopg2 path first (``create_task``) and
never reaches the asyncpg enqueue, so it returned 500 — breaching the
``tests/contract/test_fuzz.py`` invariant that schema-valid input never yields
>= 500. Fixing this per-driver would need one handler per driver quirk; the
guard fixes every current and future write path at one choke point.

The vector is specifically the *escaped* form ``\\u0000``. A raw NUL byte inside
a JSON string is not legal JSON, and the strict ``json.loads`` FastAPI uses
already rejects it with 422 on its own.
"""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel

from src.api.middleware.nul_byte_guard import NulByteGuardMiddleware

# A NUL byte is illegal in PostgreSQL text and must never reach the driver.
NUL = "\x00"

_JSON_HEADERS = {"content-type": "application/json"}


def _json_bytes(payload: dict) -> bytes:
    """Serialize ``payload``, emitting NUL as the JSON escape ``\\u0000``.

    Sent as raw ``content=`` rather than ``json=`` so the escape survives
    verbatim and the test exercises the byte sequence a real client sends.
    """
    return json.dumps(payload).encode()


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        # psycopg2 path: AgentTaskService.create_task persists `prompt` via
        # SQLAlchemy and raises a bare ValueError -> unmapped -> 500.
        ("/api/v1/agent/task", {"prompt": f"summarize{NUL}", "task_type": "analysis"}),
        # Same driver, different route: KBQAService._search_topics builds an
        # ILIKE from the question.
        ("/api/v1/kb/query", {"question": f"what is{NUL} new"}),
    ],
)
def test_nul_byte_in_json_body_is_rejected_without_server_error(client, path, payload):
    """A NUL byte in a JSON body is a client error, not a server error."""
    response = client.post(path, content=_json_bytes(payload), headers=_JSON_HEADERS)

    assert response.status_code < 500, (
        f"POST {path} with a NUL in the body returned {response.status_code}; "
        f"NUL bytes are invalid input and must produce a 4xx: {response.text[:300]}"
    )
    assert response.status_code == 422, (
        f"POST {path} with a NUL in the body should be 422, got {response.status_code}"
    )
    assert NUL not in response.text, "the offending NUL byte was echoed back to the caller"


def test_nul_byte_nested_in_json_body_is_rejected(client):
    """The guard walks the whole document, not just top-level string values."""
    payload = {
        "prompt": "summarize",
        "task_type": "analysis",
        "params": {"nested": [{"deep": f"value{NUL}"}]},
    }
    response = client.post(
        "/api/v1/agent/task", content=_json_bytes(payload), headers=_JSON_HEADERS
    )

    assert response.status_code == 422, (
        f"A NUL nested inside `params` must still be rejected, got {response.status_code}"
    )


def test_ordinary_json_body_still_reaches_the_handler(client):
    """The guard must not reject legitimate JSON bodies.

    With an empty KB, ``KBQAService.query`` short-circuits before any LLM call,
    so this exercises the full middleware -> route -> service path cheaply.
    """
    response = client.post(
        "/api/v1/kb/query",
        content=_json_bytes({"question": "what is new in AI"}),
        headers=_JSON_HEADERS,
    )

    assert response.status_code == 200, (
        f"An ordinary question must still be answered, got {response.status_code}: "
        f"{response.text[:300]}"
    )


def test_literal_backslash_u0000_text_is_not_rejected(client):
    """`\\u0000` written as six literal characters is ordinary text, not a NUL.

    The guard's cheap pre-filter scans for the ASCII tail ``u0000``, which this
    body contains; the exact check must then parse and clear it. Rejecting here
    would be a false positive on valid input.
    """
    # Built by concatenation so this source file never holds the sequence
    # (or a real NUL) itself: a backslash followed by four ASCII digits.
    literal_escape = "\\" + "u0000"
    response = client.post(
        "/api/v1/kb/query",
        content=_json_bytes({"question": f"what does the {literal_escape} escape mean?"}),
        headers=_JSON_HEADERS,
    )

    assert response.status_code == 200, (
        "text mentioning the escape sequence is valid input and must not be "
        f"rejected, got {response.status_code}: {response.text[:300]}"
    )


# ---------------------------------------------------------------------------
# Middleware-level behaviour, isolated from route side effects.
# ---------------------------------------------------------------------------


class _Echo(BaseModel):
    value: str


@pytest.fixture
def guarded_app_client() -> TestClient:
    """A minimal app carrying only the guard, for content-type/replay checks."""
    app = FastAPI()
    app.add_middleware(NulByteGuardMiddleware)

    @app.post("/echo")
    async def echo(body: _Echo) -> dict[str, str]:
        return {"value": body.value}

    @app.post("/binary")
    async def binary(request: Request) -> dict[str, int]:
        raw = await request.body()
        return {"length": len(raw)}

    return TestClient(app)


def test_handler_still_receives_the_body_after_inspection(guarded_app_client):
    """Reading the body in middleware must not starve the downstream handler.

    Starlette's ``_CachedRequest`` replays a body consumed inside ``dispatch``;
    this asserts that contract holds rather than assuming it.
    """
    response = guarded_app_client.post(
        "/echo", content=_json_bytes({"value": "intact"}), headers=_JSON_HEADERS
    )

    assert response.status_code == 200, response.text
    assert response.json() == {"value": "intact"}


def test_non_json_bodies_are_passed_through_uninspected(guarded_app_client):
    """A NUL is legitimate in binary payloads; only JSON text is inspected.

    Multipart uploads carry arbitrary file bytes, and buffering them to scan
    for a byte that is *valid* there would be both wrong and expensive.
    """
    payload = b"\x89PNG\x00\x00binary\x00content"
    response = guarded_app_client.post(
        "/binary", content=payload, headers={"content-type": "application/octet-stream"}
    )

    assert response.status_code == 200, (
        f"binary bodies must pass through the guard, got {response.status_code}: "
        f"{response.text[:200]}"
    )
    assert response.json() == {"length": len(payload)}
