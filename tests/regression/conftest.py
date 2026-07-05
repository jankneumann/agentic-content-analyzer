"""Fixtures for the regression suite.

``test_agent_routes_registered_without_breaking_existing`` inspects the shared
``src.api.app`` singleton's route table. That singleton is built once per pytest
process and shared across the whole ``rest`` shard.

Some other tests in that shard grab a shared ``APIRouter`` object and mutate it
in place (e.g. ``tests/evaluation/test_evaluation_api.py`` does
``clean_router = router; clean_router.dependencies = []`` — ``clean_router`` is
NOT a copy). If such a mutation empties a router's ``.routes`` before the app is
first constructed, ``FastAPI.include_router`` copies the now-empty router into
the app and the route never appears — making the route-inventory assertion here
fail depending on cross-test import ordering.

To make the assertion deterministic, drop the cached ``src.api`` route modules
and the app module so the test's own ``from src.api.app import app`` rebuilds a
pristine application with every router freshly registered. Reloading only
``src.api.app`` is insufficient: it re-runs ``include_router`` against the
already-emptied router objects, so the route modules themselves must be
re-imported.
"""

import sys

import pytest


@pytest.fixture(autouse=True)
def _rebuild_api_app_singleton():
    """Evict cached src.api route modules + app so the app is rebuilt pristine."""
    for name in [n for n in list(sys.modules) if n.startswith("src.api.") and "route" in n]:
        del sys.modules[name]
    sys.modules.pop("src.api.app", None)
    yield
