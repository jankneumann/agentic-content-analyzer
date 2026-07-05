"""Temporary diagnostics for the regression suite.

`test_agent_routes_registered_without_breaking_existing` fails in the `rest` CI
shard (but not locally, and not on the base commit), and reproduction requires
the full Postgres-extension-backed shard. This autouse fixture prints the real
state of the shared FastAPI app + agent router around that test so CI reveals
the actual mechanism. Remove once the root cause is fixed.
"""

import sys

import pytest


def _report(tag: str) -> None:
    lines = [f"[ROUTEDIAG {tag}]"]
    app_mod = sys.modules.get("src.api.app")
    lines.append(f"  src.api.app cached: {app_mod is not None}")
    if app_mod is not None:
        paths = [r.path for r in app_mod.app.routes if hasattr(r, "path")]
        lines.append(f"  app total routes: {len(paths)}")
        lines.append(f"  /agent/ present: {any('/agent/' in p for p in paths)}")
        lines.append(f"  agent-ish paths: {[p for p in paths if 'agent' in p][:6]}")
    ar = sys.modules.get("src.api.agent_routes")
    lines.append(f"  src.api.agent_routes cached: {ar is not None}")
    if ar is not None:
        lines.append(f"  agent_router.routes count: {len(ar.router.routes)}")
        lines.append(f"  agent_router id: {id(ar.router)}")
    # Fresh rebuild attempt
    try:
        for name in [n for n in list(sys.modules) if n.startswith("src.api.") and "route" in n]:
            del sys.modules[name]
        sys.modules.pop("src.api.app", None)
        import src.api.app as fresh

        fpaths = [r.path for r in fresh.app.routes if hasattr(r, "path")]
        lines.append(f"  FRESH /agent/ present: {any('/agent/' in p for p in fpaths)}")
        lines.append(f"  FRESH total routes: {len(fpaths)}")
        import src.api.agent_routes as far

        lines.append(f"  FRESH agent_router.routes count: {len(far.router.routes)}")
    except Exception as e:
        lines.append(f"  FRESH rebuild raised: {type(e).__name__}: {e}")
    print("\n".join(lines), file=sys.stderr)


@pytest.fixture(autouse=True)
def _diagnose_agent_routes(request):
    if "test_agent_routes_registered" not in request.node.name:
        yield
        return
    _report("BEFORE")
    yield
    _report("AFTER")
