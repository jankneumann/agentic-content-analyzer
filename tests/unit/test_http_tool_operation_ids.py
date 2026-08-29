"""Lock OpenAPI operationIds used by agentic-assistant HTTP-tool binding.

The assistant indexes FastAPI operations by operationId and binds
preferred_tools as ``content_analyzer:search`` and
``content_analyzer:knowledge_graph``. FastAPI's default munged ids
(``search_knowledge_base_api_v1_kb_search_get``) do not match those
keys, so the teacher role silently dropped both tools (issue #421).
"""

from __future__ import annotations

from src.api.app import app
from src.api.routes.graph_routes import router as graph_router
from src.api.routes.kb_search_routes import router as kb_search_router


def _route_operation_id(router, *, path: str, method: str) -> str | None:
    method = method.upper()
    for route in router.routes:
        if getattr(route, "path", None) != path:
            continue
        if method not in getattr(route, "methods", set()):
            continue
        return getattr(route, "operation_id", None)
    raise AssertionError(f"no {method} {path} on {router.prefix}")


def test_kb_search_route_declares_operation_id_search() -> None:
    assert _route_operation_id(kb_search_router, path="/api/v1/kb/search", method="GET") == "search"


def test_graph_query_route_declares_operation_id_knowledge_graph() -> None:
    assert (
        _route_operation_id(graph_router, path="/api/v1/graph/query", method="POST")
        == "knowledge_graph"
    )


def test_openapi_emits_http_tool_operation_ids() -> None:
    """agentic-assistant binds tools from /openapi.json operationId values."""
    spec = app.openapi()
    assert spec["paths"]["/api/v1/kb/search"]["get"]["operationId"] == "search"
    assert spec["paths"]["/api/v1/graph/query"]["post"]["operationId"] == "knowledge_graph"
