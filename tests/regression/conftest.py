"""Fixtures for the regression suite.

The FastAPI application in ``src.api.app`` is a module-level singleton shared
across the whole pytest process. Some DB-backed tests elsewhere in the shared
``rest`` shard mutate that singleton, which can leave it without its full set of
routers by the time this suite runs. Route-inventory assertions here (e.g.
``test_agent_routes_registered_without_breaking_existing``) must be resilient to
that cross-test ordering.

Reloading ``src.api.app`` reconstructs a pristine, fully-wired application (all
routers re-included on a fresh ``FastAPI`` instance) without depending on the
possibly-mutated current state — a plain snapshot/restore can't help because the
mutation happens in an earlier test, before this fixture would run.
"""

import importlib

import pytest


@pytest.fixture(autouse=True)
def _pristine_app_singleton():
    """Reload src.api.app before each regression test so route assertions see a
    complete app regardless of earlier tests mutating the shared singleton."""
    try:
        import src.api.app as app_module

        importlib.reload(app_module)
    except Exception:
        # If the app module can't be reloaded, fall back to whatever state
        # exists rather than erroring the whole suite.
        pass
    yield
