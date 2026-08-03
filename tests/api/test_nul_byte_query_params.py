"""Regression tests: NUL bytes in query params must yield 4xx, never 500.

Background
----------
The `contract-test` CI job failed intermittently (~50% of runs) across
completely unrelated PRs, because Schemathesis generates NUL bytes (`\\x00`)
for free-text query parameters only on some random draws.

Two distinct root causes both surfaced as HTTP 500:

1. ``GET /api/v1/contents?publication=%00`` — the route declared
   ``publication: str | None`` but fed it into ``ContentQuery``, whose
   ``publication_search`` field is ``QueryText`` (``pattern=^[^\\x00]*$``).
   Pydantic raised ``ValidationError``, which subclasses ``ValueError``, so it
   landed in the generic ``ValueError`` handler — 422 for RFC-7807 "problem"
   paths, but **500** for legacy paths like ``/api/v1/contents``.

2. ``GET /api/v1/summaries?model_used=%00`` — the unconstrained ``str`` param
   reached psycopg2, which raises
   ``ValueError("A string literal cannot contain NUL (0x00) characters.")``,
   hitting the same handler and the same 500.

A NUL byte can never appear in PostgreSQL text, so it is never a valid value;
these are client errors and must be rejected at the request boundary.
"""

from __future__ import annotations

import pytest

# A NUL byte is illegal in PostgreSQL text and must never reach the driver.
NUL = "\x00"


@pytest.mark.parametrize(
    ("path", "param"),
    [
        # Root cause 1: pydantic ValidationError from in-route model construction.
        ("/api/v1/contents", "publication"),
        ("/api/v1/contents", "search"),
        # Root cause 2: unconstrained str reaching psycopg2.
        ("/api/v1/summaries", "model_used"),
    ],
)
def test_nul_byte_in_query_param_is_rejected_without_server_error(client, path, param):
    """A NUL byte in a free-text filter is a client error, not a server error."""
    response = client.get(path, params={param: NUL})

    assert response.status_code < 500, (
        f"GET {path}?{param}=<NUL> returned {response.status_code}; "
        f"NUL bytes are invalid input and must produce a 4xx: {response.text[:300]}"
    )
    assert response.status_code == 422, (
        f"GET {path}?{param}=<NUL> should be 422 Unprocessable Entity, got {response.status_code}"
    )


@pytest.mark.parametrize(
    ("path", "param"),
    [
        ("/api/v1/contents", "publication"),
        ("/api/v1/contents", "search"),
        ("/api/v1/summaries", "model_used"),
    ],
)
def test_ordinary_text_filter_still_reaches_the_handler(client, path, param):
    """The NUL guard must not reject legitimate free-text filter values."""
    response = client.get(path, params={param: "AI Weekly"})

    assert response.status_code == 200, (
        f"GET {path}?{param}=AI Weekly should still succeed, "
        f"got {response.status_code}: {response.text[:300]}"
    )


def test_overlong_text_filter_is_rejected_as_client_error(client):
    """QueryText caps free text at 500 chars; the route must enforce it as 422."""
    response = client.get("/api/v1/contents", params={"publication": "x" * 501})

    assert response.status_code == 422, (
        f"An over-length publication filter should be 422, got {response.status_code}"
    )


def test_nul_byte_in_path_is_rejected_without_echoing_it_back(client):
    """A NUL in the URL path is rejected, and never reflected into the response.

    The audit writer casts the request path into a Postgres column, so a path
    holding NUL must be refused before audit runs — see
    ``tests/api/test_audit_ordering.py::test_nul_byte_guard_wraps_audit_but_sits_inside_cors``.
    """
    # httpx refuses to build a URL from a raw NUL, so send the percent-encoded
    # form — which is exactly what a real client (and Schemathesis) emits.
    response = client.get("/api/v1/settings/voice/%00")

    assert response.status_code < 500, (
        f"A NUL byte in the path must not be a server error, got {response.status_code}"
    )
    assert NUL not in response.text, "the offending NUL byte was echoed back to the caller"
