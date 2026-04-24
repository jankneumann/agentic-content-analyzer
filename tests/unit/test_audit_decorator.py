"""Unit tests for the `@audited(operation=...)` decorator.

The decorator must:
1. Preserve the wrapped handler's return value.
2. Attach ``operation`` onto ``request.state`` so the middleware can read it.
3. Be an identity on functions that don't receive a Request argument
   (i.e. still attaches a static marker on the wrapped callable).
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from src.api.middleware.audit import AUDIT_STATE_ATTR, audited


def test_decorator_preserves_return_value_and_sets_state():
    @audited(operation="foo.bar")
    async def handler(request):
        return {"ok": True}

    request = SimpleNamespace(state=SimpleNamespace())
    result = asyncio.run(handler(request))

    assert result == {"ok": True}
    assert getattr(request.state, AUDIT_STATE_ATTR) == "foo.bar"


def test_decorator_sets_static_marker_on_callable():
    @audited(operation="kb.purge")
    async def handler(request):
        return "noop"

    # The decorator should stamp the operation on the function object so tests
    # that inspect routes without invoking them can discover it.
    assert getattr(handler, "__audit_operation__", None) == "kb.purge"


def test_decorator_accepts_sync_and_async_handlers():
    @audited(operation="sync.op")
    def sync_handler(request):
        return 1

    @audited(operation="async.op")
    async def async_handler(request):
        return 2

    req = SimpleNamespace(state=SimpleNamespace())
    assert sync_handler(req) == 1
    assert getattr(req.state, AUDIT_STATE_ATTR) == "sync.op"

    req2 = SimpleNamespace(state=SimpleNamespace())
    assert asyncio.run(async_handler(req2)) == 2
    assert getattr(req2.state, AUDIT_STATE_ATTR) == "async.op"


def test_decorator_does_not_crash_when_request_absent():
    """If the handler is called without a Request arg (e.g. during introspection
    or testing), the decorator must not raise."""

    @audited(operation="no.req")
    async def handler() -> str:
        return "hello"

    assert asyncio.run(handler()) == "hello"
