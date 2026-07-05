"""Fixtures for the regression suite.

`test_agent_routes_registered_without_breaking_existing` fails in the CI `rest`
shard because, by the time it runs, the shared `src.api.app` singleton has only
~5 routes — every `app.include_router(...)` effectively added nothing, even
though the individual routers (e.g. agent_router) still hold their routes. This
is pre-existing global-state pollution in the shard (the suite already documents
OpenTelemetry-instrumentation leakage in tests/security/test_production_validation.py),
surfaced by cross-test import ordering. It is not caused by the feature under
test.

This autouse fixture makes the route-inventory assertion deterministic: it
resets telemetry + uninstruments the global OTEL instrumentors that leak across
tests, then evicts the cached `src.api` route modules and app so the test's own
`from src.api.app import app` rebuilds a pristine, fully-wired application.
Diagnostics are printed to stderr so CI still shows the observed state.
"""

import sys

import pytest


def _uninstrument_global_otel() -> list[str]:
    notes: list[str] = []
    try:
        from src.telemetry import reset_telemetry

        reset_telemetry()
        notes.append("reset_telemetry ok")
    except Exception as e:
        notes.append(f"reset_telemetry: {type(e).__name__}")
    instrumentors = [
        ("opentelemetry.instrumentation.fastapi", "FastAPIInstrumentor"),
        ("opentelemetry.instrumentation.sqlalchemy", "SQLAlchemyInstrumentor"),
        ("opentelemetry.instrumentation.httpx", "HTTPXClientInstrumentor"),
        ("opentelemetry.instrumentation.logging", "LoggingInstrumentor"),
    ]
    for mod_name, cls_name in instrumentors:
        try:
            mod = __import__(mod_name, fromlist=[cls_name])
            getattr(mod, cls_name)().uninstrument()
            notes.append(f"{cls_name} uninstrumented")
        except Exception as e:
            notes.append(f"{cls_name}: {type(e).__name__}")
    return notes


def _evict_api_modules() -> None:
    for name in [n for n in list(sys.modules) if n.startswith("src.api.") and "route" in n]:
        del sys.modules[name]
    sys.modules.pop("src.api.app", None)


@pytest.fixture(autouse=True)
def _rebuild_pristine_app(request):
    if "test_agent_routes_registered" not in request.node.name:
        yield
        return

    def report(tag: str) -> None:
        app_mod = sys.modules.get("src.api.app")
        n = len(app_mod.app.routes) if app_mod is not None else -1
        print(f"[ROUTEDIAG {tag}] src.api.app routes={n}", file=sys.stderr)

    report("BEFORE")
    notes = _uninstrument_global_otel()
    print(f"[ROUTEDIAG UNINSTRUMENT] {notes}", file=sys.stderr)
    _evict_api_modules()
    # Probe: does a freshly rebuilt app now have its routers?
    try:
        import src.api.app as fresh

        fpaths = [r.path for r in fresh.app.routes if hasattr(r, "path")]
        print(
            f"[ROUTEDIAG FRESH] routes={len(fpaths)} /agent/={any('/agent/' in p for p in fpaths)}",
            file=sys.stderr,
        )
        # Evict again so the test's own import rebuilds cleanly.
        _evict_api_modules()
    except Exception as e:
        print(f"[ROUTEDIAG FRESH] rebuild raised {type(e).__name__}: {e}", file=sys.stderr)
    yield
