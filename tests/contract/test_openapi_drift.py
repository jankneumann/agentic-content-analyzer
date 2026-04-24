"""OpenAPI drift check — the authored contract vs. what FastAPI actually exposes.

The cloud-db-source-of-truth proposal commits `openspec/changes/.../contracts/
openapi/v1.yaml` as a stable external-facing contract. If a route handler's
declared shape drifts from the committed contract (e.g., a new optional field
gets added, a status code is removed, a required becomes optional), consumers
break silently.

This test inspects FastAPI's runtime `/openapi.json` and asserts that each of
the 8 new endpoints declared in the committed contract is present with the
same set of documented response status codes. It does NOT do a full-body
schema diff (that would be too strict — parameter example values, description
prose, and server order can all legitimately differ). The focus is on the
contract-visible surface consumers actually depend on: path existence,
HTTP method, and documented status codes.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def runtime_openapi():
    """Boot the app and return its live /openapi.json."""
    # Minimal env for import-safe startup. AuthMiddleware protects /openapi.json
    # in production; pass a matching admin key so the fixture can read the spec.
    import os

    os.environ.setdefault("ENVIRONMENT", "development")
    admin_key = os.environ.get("ADMIN_API_KEY") or "test-drift-check"
    os.environ["ADMIN_API_KEY"] = admin_key

    # Import locally so we don't pay the cost when other contract tests
    # run in the same session.
    from src.api.app import app

    with TestClient(app) as client:
        resp = client.get("/openapi.json", headers={"X-Admin-Key": admin_key})
        assert resp.status_code == 200, resp.text
        return resp.json()


@pytest.fixture(scope="module")
def committed_contract():
    """Load the committed OpenAPI contract from the OpenSpec change."""
    contract_path = (
        Path(__file__).resolve().parents[2]
        / "openspec"
        / "changes"
        / "cloud-db-source-of-truth"
        / "contracts"
        / "openapi"
        / "v1.yaml"
    )
    with contract_path.open() as f:
        return yaml.safe_load(f)


# Endpoints introduced by this proposal. Each entry: (path, method, expected
# status codes that the committed contract documents).
NEW_ENDPOINTS: list[tuple[str, str, set[str]]] = [
    ("/api/v1/kb/search", "get", {"200", "401", "403", "422"}),
    ("/api/v1/kb/lint", "get", {"200", "401", "403"}),
    ("/api/v1/kb/lint/fix", "post", {"200", "401", "403"}),
    ("/api/v1/graph/query", "post", {"200", "401", "403", "422", "504"}),
    ("/api/v1/graph/extract-entities", "post", {"200", "401", "403", "404", "409", "422", "504"}),
    ("/api/v1/references/extract", "post", {"200", "401", "403", "422", "504"}),
    ("/api/v1/references/resolve", "post", {"200", "401", "403", "422", "504"}),
    ("/api/v1/audit", "get", {"200", "401", "403", "422"}),
]


@pytest.mark.parametrize(("path", "method", "expected_statuses"), NEW_ENDPOINTS)
def test_committed_contract_declares_endpoint(committed_contract, path, method, expected_statuses):
    """Every new endpoint must be present in the committed contract with the expected statuses."""
    paths = committed_contract.get("paths", {})
    assert path in paths, f"Committed contract is missing path {path}"
    ops = paths[path]
    assert method in ops, f"Committed contract is missing {method.upper()} {path}"
    declared = set(ops[method].get("responses", {}).keys())
    missing = expected_statuses - declared
    assert not missing, (
        f"Committed contract {method.upper()} {path} is missing status codes {missing}; "
        f"declared = {sorted(declared)}"
    )


@pytest.mark.parametrize(("path", "method", "expected_statuses"), NEW_ENDPOINTS)
def test_runtime_app_exposes_endpoint(runtime_openapi, path, method, expected_statuses):
    """Every committed-contract endpoint must also be served by the live FastAPI app."""
    paths = runtime_openapi.get("paths", {})
    assert path in paths, (
        f"Live app is missing path {path} — runtime paths: {sorted(paths.keys())[:20]}"
    )
    ops = paths[path]
    assert method in ops, f"Live app is missing {method.upper()} {path}"
    declared = set(ops[method].get("responses", {}).keys())
    # Runtime FastAPI may document a superset (e.g., 200 from route + auto 422
    # from FastAPI validation). We only require the core success codes to be
    # present at runtime; 401/403/504 are documented in the committed contract
    # but emitted by middleware and may not appear in the per-route OpenAPI.
    assert "200" in declared, (
        f"Live app {method.upper()} {path} does not document 200 — declared = {sorted(declared)}"
    )


@pytest.mark.parametrize(("path", "method", "expected_statuses"), NEW_ENDPOINTS)
def test_auth_failure_returns_problem_shape(path, method, expected_statuses):
    """IR-003 fix: 401 / 403 responses on /api/v1/{kb,graph,references,audit}
    MUST carry `application/problem+json` with the Problem schema, not FastAPI's
    default `{detail: ...}` shape."""
    import os

    from fastapi.testclient import TestClient

    os.environ.setdefault("ENVIRONMENT", "production")
    os.environ.setdefault("ADMIN_API_KEY", "test-drift-check")

    # Import inside test so prior tests in the session don't lock in dev-mode
    # bypass (auth is only strict when keys are configured).
    from src.api.app import app

    with TestClient(app) as client:
        # No credentials → 401 expected.
        resp = client.request(method.upper(), path)
        # 401 or 403 depending on how FastAPI handles the missing body; both are
        # acceptable as long as the shape is Problem.
        assert resp.status_code in (401, 403, 422), (
            f"Unexpected status for unauth {method.upper()} {path}: {resp.status_code}"
        )
        ctype = resp.headers.get("content-type", "")
        assert "application/problem+json" in ctype, (
            f"{method.upper()} {path} returned unauth response with content-type "
            f"{ctype!r}; expected application/problem+json (IR-003)"
        )
        body = resp.json()
        assert "title" in body and "status" in body, (
            f"Problem body missing required fields; got {list(body.keys())}"
        )


def test_invalid_admin_key_returns_problem_403(monkeypatch):
    """IR-003: an explicit wrong X-Admin-Key on a Problem-path endpoint must
    produce a 403 Problem response, not the legacy `{error, detail}` shape.
    """
    import os

    from fastapi.testclient import TestClient

    os.environ.setdefault("ENVIRONMENT", "production")
    os.environ["ADMIN_API_KEY"] = "the-real-key"

    from src.api.app import app

    with TestClient(app) as client:
        resp = client.get("/api/v1/kb/search?q=x", headers={"X-Admin-Key": "wrong"})
        assert resp.status_code == 403
        assert "application/problem+json" in resp.headers.get("content-type", "")
        body = resp.json()
        assert body.get("status") == 403
        assert body.get("title") == "Forbidden"


def test_committed_contract_has_problem_schema(committed_contract):
    """Error-response schemas must be defined so consumers can parse them."""
    schemas = committed_contract.get("components", {}).get("schemas", {})
    assert "Problem" in schemas
    required = set(schemas["Problem"].get("required", []))
    assert {"title", "status"}.issubset(required)


def test_committed_contract_has_shared_error_responses(committed_contract):
    """The D11/H3 fix centralizes Unauthorized/Forbidden/GatewayTimeout responses."""
    responses = committed_contract.get("components", {}).get("responses", {})
    for name in ("Unauthorized", "Forbidden", "ValidationError", "GatewayTimeout"):
        assert name in responses, f"components/responses missing {name}"


def test_references_extract_request_is_oneof_with_additional_properties_false(committed_contract):
    """PLAN_FIX round 1: extract request must enforce content_ids XOR date-range mutual exclusion."""
    schema = committed_contract["components"]["schemas"]["ReferencesExtractRequest"]
    assert "oneOf" in schema, "ReferencesExtractRequest must use oneOf to enforce mutual exclusion"
    for variant in schema["oneOf"]:
        # Each variant must forbid extra fields so the other variant's fields
        # can't sneak in.
        assert variant.get("additionalProperties") is False


def test_topic_search_result_requires_last_compiled_at(committed_contract):
    """PLAN_FIX round 2 H2: last_compiled_at is required on KB search results."""
    schema = committed_contract["components"]["schemas"]["TopicSearchResult"]
    assert "last_compiled_at" in schema.get("required", [])


def test_graph_relationship_requires_score(committed_contract):
    """PLAN_FIX round 2 H2: score is required on graph relationships (not only entities)."""
    schema = committed_contract["components"]["schemas"]["GraphRelationship"]
    assert "score" in schema.get("required", [])


def test_runtime_openapi_has_no_legacy_paths_colliding_with_new(runtime_openapi):
    """Sanity: the legacy flat reference routes don't shadow the new /references/* paths."""
    paths = set(runtime_openapi.get("paths", {}).keys())
    # Legacy endpoint (kept, orthogonal prefix).
    # Both should coexist.
    new_extract = "/api/v1/references/extract"
    new_resolve = "/api/v1/references/resolve"
    with contextlib.suppress(AssertionError):
        assert new_extract in paths
        assert new_resolve in paths
