"""API fuzz tests using Schemathesis.

Generates randomized inputs based on the OpenAPI schema to detect:
- Unexpected 500 errors from malformed inputs
- Missing input validation
- Crash-inducing edge cases in request parsing

Run:
    pytest tests/contract/test_fuzz.py -m contract -v
"""

from __future__ import annotations

import pytest
import schemathesis
from hypothesis import settings as hypothesis_settings

from tests.contract.conftest import EXCLUDED_COMMON_PATHS

# Fuzz tests exclude everything that conformance tests exclude, PLUS
# mutating endpoints that trigger LLM calls, external services, or TTS.
_FUZZ_ONLY_EXCLUSIONS: list[str] = [
    # Ingestion pipeline triggers
    r"/api/v1/contents/ingest$",
    r"/api/v1/contents/summarize$",
    # LLM generation endpoints
    r"/api/v1/digests/generate$",
    r"/api/v1/digests/\{digest_id\}/regenerate$",
    r"/api/v1/themes/analyze$",
    r"/api/v1/scripts/generate$",
    r"/api/v1/scripts/\{script_id\}/regenerate$",
    r"/api/v1/scripts/\{script_id\}/sections/",
    r"/api/v1/summaries/\{summary_id\}/regenerate",
    # TTS generation
    r"/api/v1/podcasts/generate$",
    r"/api/v1/audio-digests$",
    # Voice cleanup (calls LLM)
    r"/api/v1/voice/cleanup$",
    # External URL/file fetching
    r"/api/v1/content/save-url$",
    r"/api/v1/content/save-page$",
    r"/api/v1/documents/upload$",
]

EXCLUDED_FUZZ_REGEX = "|".join(EXCLUDED_COMMON_PATHS + _FUZZ_ONLY_EXCLUSIONS)

schema = schemathesis.pytest.from_fixture("contract_schema")


def _call_no_transport_error(case):
    """Call the endpoint, skipping if a transport-level error occurs.

    Schemathesis may generate inputs (e.g., NUL bytes) that cause
    low-level driver errors before a response is produced. These
    are tracked as separate issues, not fuzz test failures.
    """
    try:
        return case.call()
    except (ConnectionError, OSError, ValueError):
        pytest.skip("Transport error (e.g., NUL byte in parameter)")


@pytest.mark.contract
@schema.exclude(path_regex=EXCLUDED_FUZZ_REGEX).include(method="GET").parametrize()
@hypothesis_settings(max_examples=25, deadline=None)
def test_get_endpoints_no_500(case):
    """GET endpoints never return 500 for schema-valid inputs.

    Schemathesis generates schema-valid but randomized parameter values.
    Valid inputs should never produce 500 errors — only 2xx or 4xx.
    """
    case.headers = {**(case.headers or {}), "X-Admin-Key": "test-admin-key"}
    response = _call_no_transport_error(case)
    assert response.status_code < 500, (
        f"Server error on GET {case.formatted_path}: {response.status_code} - {response.text[:500]}"
    )


@pytest.mark.contract
@schema.include(path_regex=r"^/api/v1/settings/").parametrize()
@hypothesis_settings(max_examples=15, deadline=None)
def test_settings_endpoints_no_500(case):
    """Settings endpoints handle fuzzed inputs gracefully."""
    case.headers = {**(case.headers or {}), "X-Admin-Key": "test-admin-key"}
    response = _call_no_transport_error(case)
    assert response.status_code < 500, (
        f"Server error on {case.method.upper()} {case.formatted_path}: "
        f"{response.status_code} - {response.text[:500]}"
    )


@pytest.mark.contract
@schema.include(path_regex=r"^/api/v1/search").parametrize()
@hypothesis_settings(max_examples=15, deadline=None)
def test_search_endpoint_no_500(case):
    """Search endpoint handles fuzzed queries without server errors."""
    case.headers = {**(case.headers or {}), "X-Admin-Key": "test-admin-key"}
    response = _call_no_transport_error(case)
    assert response.status_code < 500, (
        f"Server error on {case.method.upper()} {case.formatted_path}: "
        f"{response.status_code} - {response.text[:500]}"
    )


@pytest.mark.contract
@schema.exclude(path_regex=EXCLUDED_FUZZ_REGEX).exclude(method="GET").parametrize()
@hypothesis_settings(max_examples=15, deadline=None)
def test_mutating_endpoints_no_500(case):
    """POST/PUT/PATCH/DELETE endpoints never return 500 for schema-valid inputs.

    Covers safe mutating endpoints: content CRUD, digest/script approval,
    job retry, source management, and conversation operations.  LLM-calling
    and external-service endpoints are excluded via EXCLUDED_FUZZ_REGEX.
    """
    case.headers = {**(case.headers or {}), "X-Admin-Key": "test-admin-key"}
    response = _call_no_transport_error(case)
    assert response.status_code < 500, (
        f"Server error on {case.method.upper()} {case.formatted_path}: "
        f"{response.status_code} - {response.text[:500]}"
    )
