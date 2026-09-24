"""The X Bookmarks GraphQL client, network-free over ``httpx.MockTransport``.

Covers query ID discovery (runtime chunk map and main.js), the durable query
ID cache, rediscovery on a stale ID, the cursor walk and its stop hooks, 429
handling with a fake clock, ct0 write-back through a fake OpenBao adapter,
dead-session handling, missing credentials, and the tweet-to-record mapping.

Every cookie value is a sentinel; an autouse fixture fails any test that lets
one reach a log record or stdout/stderr.
"""

from __future__ import annotations

import contextlib
import json
import logging
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from src.cli.secret_sinks import BaoSink
from src.config import bao_secrets
from src.config.credentials import X_AUTH_TOKEN, X_CT0, CredentialProvider
from src.ingestion.credential_failures import (
    CREDENTIALS_MISSING,
    SESSION_EXPIRED,
    CredentialsMissingError,
    SessionExpiredError,
)
from src.ingestion.x_bookmarks_client import (
    GRAPHQL_BASE_URL,
    QUERY_ID_SETTING_KEY,
    QueryIdDiscoveryError,
    SettingsQueryIdStore,
    WalkStopReason,
    XBookmarksClient,
    XBookmarksUpstreamError,
    _default_sink_factory,
    extract_bookmarks_query_id,
    is_x_self_link,
    parse_bookmarks_page,
    parse_tweet_result,
)
from src.ingestion.x_web import X_WEB_BEARER_TOKEN
from tests.fixtures import x_bookmarks_graphql as fx

AUTH_TOKEN = "authSENTINELtoken0123456789abcdef0123"
CT0 = "ct0SENTINELvalue0123456789abcdef"
ROTATED_CT0 = "ct0ROTATEDsentinel9876543210fedcba"
FRESH_AUTH_TOKEN = "authFRESHsentinel0123456789abcdef"
FRESH_CT0 = "ct0FRESHsentinel0123456789abcdef"
SENTINELS = (AUTH_TOKEN, CT0, ROTATED_CT0, FRESH_AUTH_TOKEN, FRESH_CT0, X_WEB_BEARER_TOKEN)

CACHED_QUERY_ID = "CachedQueryId_1234"
DISCOVERED_QUERY_ID = "FreshQueryId-5678"
NOW = 1_800_000_000.0

# -- fakes ---------------------------------------------------------------------


class FakeBao:
    """The OpenBao cache behind a real CredentialProvider."""

    def __init__(self, values: dict[str, str]) -> None:
        self.cache = dict(values)
        self.on_refresh: dict[str, str] | None = None
        self.refreshes = 0

    def read(self) -> dict[str, str]:
        return dict(self.cache)

    def refresh(self, *, min_interval_s: float = 0.0) -> bool:
        self.refreshes += 1
        if self.on_refresh is None:
            return False
        self.cache.update(self.on_refresh)
        return True

    def write(self, values: dict[str, str]) -> list[str]:
        self.cache.update(values)
        return sorted(values)


def make_provider(bao: FakeBao) -> CredentialProvider:
    settings = SimpleNamespace(substack_session_cookie=None, x_auth_token=None, x_ct0=None)
    return CredentialProvider(
        settings_factory=lambda: settings,
        bao_reader=bao.read,
        bao_refresher=bao.refresh,
        bao_writer=bao.write,
        clock=lambda: datetime.fromtimestamp(NOW, UTC),
    )


class MemoryQueryIdStore:
    def __init__(self, value: str | None = None) -> None:
        self.value = value
        self.sets: list[str] = []
        self.clears = 0

    def get(self) -> str | None:
        return self.value

    def set(self, query_id: str) -> None:
        self.sets.append(query_id)
        self.value = query_id

    def clear(self) -> None:
        self.clears += 1
        self.value = None


class FakeHvacAdapter:
    """``client.adapter`` of hvac: records the server-side merge-patch calls."""

    def __init__(self, *, fail: bool = False) -> None:
        self.calls: list[dict[str, Any]] = []
        self.fail = fail

    def request(self, method: str, url: str, **kwargs: Any) -> None:
        if self.fail:
            raise ConnectionError("bao down")
        self.calls.append({"method": method, "url": url, **kwargs})


class FakeX:
    """Routes requests to x.com and abs.twimg.com; records what was sent."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.graphql: list[Callable[[httpx.Request], httpx.Response]] = []
        self.page = lambda request: httpx.Response(
            200, text=fx.bookmarks_page_html(), headers={"content-type": "text/html"}
        )
        self.bundles: dict[str, str] = {}

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        url = str(request.url.copy_with(query=None))
        if url.startswith(GRAPHQL_BASE_URL):
            if not self.graphql:
                raise AssertionError(f"unexpected GraphQL request {url}")
            return self.graphql.pop(0)(request)
        if url == "https://x.com/i/bookmarks":
            return self.page(request)
        if url in self.bundles:
            return httpx.Response(200, text=self.bundles[url])
        return httpx.Response(404, text="Not Found")

    def graphql_requests(self) -> list[httpx.Request]:
        return [r for r in self.requests if str(r.url).startswith(GRAPHQL_BASE_URL)]


def json_response(body: Any, status: int = 200, **headers: str) -> Callable[..., httpx.Response]:
    return lambda request: httpx.Response(status, json=body, headers=headers)


def page(*results: dict[str, Any], cursor: str | None = None, **headers: str):
    return json_response(fx.bookmarks_response(list(results), bottom_cursor=cursor), **headers)


def variables_of(request: httpx.Request) -> dict[str, Any]:
    return json.loads(request.url.params["variables"])


@pytest.fixture(autouse=True)
def _no_sentinel_leaks(caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str]):
    caplog.set_level(logging.DEBUG)
    yield
    captured = capsys.readouterr()
    # caplog.text only holds the current (teardown) phase: read the test's records.
    logged = "\n".join(
        record.getMessage() for when in ("setup", "call") for record in caplog.get_records(when)
    )
    for sentinel in SENTINELS:
        assert sentinel not in logged
        assert sentinel not in captured.out
        assert sentinel not in captured.err


@pytest.fixture
def bao() -> FakeBao:
    return FakeBao({X_AUTH_TOKEN: AUTH_TOKEN, X_CT0: CT0})


@pytest.fixture
def fake_x() -> FakeX:
    return FakeX()


@pytest.fixture
def sleeps() -> list[float]:
    return []


@pytest.fixture
def adapter() -> FakeHvacAdapter:
    return FakeHvacAdapter()


@pytest.fixture
def make_client(
    bao: FakeBao, fake_x: FakeX, sleeps: list[float], adapter: FakeHvacAdapter
) -> Iterator[Callable[..., XBookmarksClient]]:
    clients: list[XBookmarksClient] = []

    def sink_factory(clock: Callable[[], datetime]) -> BaoSink:
        return BaoSink(client=SimpleNamespace(adapter=adapter), clock=clock, echo=None)

    def build(**overrides: Any) -> XBookmarksClient:
        options: dict[str, Any] = {
            "credentials": make_provider(bao),
            "query_id_store": MemoryQueryIdStore(CACHED_QUERY_ID),
            "http": httpx.Client(transport=httpx.MockTransport(fake_x.handler)),
            "sink_factory": sink_factory,
            "page_delay_s": 1.0,
            "sleep": sleeps.append,
            "clock": lambda: NOW,
        }
        options.update(overrides)
        client = XBookmarksClient(**options)
        clients.append(client)
        return client

    yield build
    for client in clients:
        client.close()


def post(post_id: str, text: str = "hello") -> dict[str, Any]:
    return fx.tweet_result(post_id, text)


# -- query ID discovery and cache ------------------------------------------------


def test_discovers_the_query_id_from_the_runtime_chunk_map(make_client, fake_x) -> None:
    store = MemoryQueryIdStore()
    # The map keeps 7 hex characters; the served file name has an 8th.
    fake_x.bundles[fx.bookmarks_chunk_url("a")] = fx.bundle_js(DISCOVERED_QUERY_ID)
    fake_x.graphql.append(page(post("1")))
    client = make_client(query_id_store=store)

    pages = list(client.iter_pages())

    assert [p.post_ids for p in pages] == [("1",)]
    assert store.sets == [DISCOVERED_QUERY_ID]
    graphql = fake_x.graphql_requests()
    assert graphql[0].url.path == f"/i/api/graphql/{DISCOVERED_QUERY_ID}/Bookmarks"
    page_request = next(r for r in fake_x.requests if r.url.path == "/i/bookmarks")
    assert page_request.headers["cookie"] == f"auth_token={AUTH_TOKEN}; ct0={CT0}"
    assert "authorization" not in page_request.headers
    bundle_requests = [r for r in fake_x.requests if r.url.host == "abs.twimg.com"]
    assert [str(r.url) for r in bundle_requests] == [
        fx.bookmarks_chunk_url(),
        fx.bookmarks_chunk_url("a"),
    ]
    for request in bundle_requests:  # the static host never sees the session
        assert "cookie" not in request.headers
        assert "authorization" not in request.headers
        assert "x-csrf-token" not in request.headers


def test_falls_back_to_main_js_when_the_page_has_no_runtime(make_client, fake_x) -> None:
    store = MemoryQueryIdStore()
    fake_x.page = lambda request: httpx.Response(
        200, text=fx.bookmarks_page_html(with_runtime=False), headers={"content-type": "text/html"}
    )
    fake_x.bundles[fx.MAIN_BUNDLE_URL] = fx.bundle_js(DISCOVERED_QUERY_ID)
    fake_x.graphql.append(page(post("1")))

    list(make_client(query_id_store=store).iter_pages())

    assert store.value == DISCOVERED_QUERY_ID
    assert fake_x.graphql_requests()[0].url.path.endswith(f"/{DISCOVERED_QUERY_ID}/Bookmarks")


def test_discovery_fails_with_a_typed_error_when_no_bundle_has_the_id(make_client, fake_x) -> None:
    fake_x.graphql.append(page(post("1")))  # never reached
    client = make_client(query_id_store=MemoryQueryIdStore())

    with pytest.raises(QueryIdDiscoveryError):
        list(client.iter_pages())
    assert fake_x.graphql_requests() == []


def test_a_cached_query_id_is_reused_without_scraping(make_client, fake_x) -> None:
    store = MemoryQueryIdStore(CACHED_QUERY_ID)
    fake_x.graphql.append(page(post("1")))

    list(make_client(query_id_store=store).iter_pages())

    assert [r.url.path for r in fake_x.requests] == [f"/i/api/graphql/{CACHED_QUERY_ID}/Bookmarks"]
    assert store.sets == [] and store.clears == 0


@pytest.mark.parametrize(
    "stale",
    [
        lambda request: httpx.Response(404, text=""),
        json_response(fx.query_not_found_response()),
    ],
    ids=["http-404", "graphql-query-not-found"],
)
def test_a_stale_query_id_is_invalidated_rediscovered_once_and_retried(
    make_client, fake_x, stale
) -> None:
    store = MemoryQueryIdStore(CACHED_QUERY_ID)
    fake_x.bundles[fx.bookmarks_chunk_url()] = fx.bundle_js(DISCOVERED_QUERY_ID)
    fake_x.graphql.extend([stale, page(post("1"))])

    walk = make_client(query_id_store=store).iter_pages()
    pages = list(walk)

    assert [p.post_ids for p in pages] == [("1",)]
    assert (store.clears, store.sets, walk.rediscovered_query_id) == (
        1,
        [DISCOVERED_QUERY_ID],
        True,
    )
    assert [r.url.path.split("/")[-2] for r in fake_x.graphql_requests()] == [
        CACHED_QUERY_ID,
        DISCOVERED_QUERY_ID,
    ]
    # The retry repeats the same page (first page: no cursor).
    assert all("cursor" not in variables_of(r) for r in fake_x.graphql_requests())


class StickyQueryIdStore(MemoryQueryIdStore):
    """A cache whose clear fails silently (database down): it keeps the stale ID."""

    def clear(self) -> None:
        self.clears += 1


def test_a_stale_id_is_not_reread_from_a_cache_that_failed_to_clear(make_client, fake_x) -> None:
    store = StickyQueryIdStore(CACHED_QUERY_ID)
    fake_x.bundles[fx.bookmarks_chunk_url()] = fx.bundle_js(DISCOVERED_QUERY_ID)
    fake_x.graphql.extend([lambda request: httpx.Response(404, text=""), page(post("1"))])

    assert len(list(make_client(query_id_store=store).iter_pages())) == 1
    assert fake_x.graphql_requests()[1].url.path.split("/")[-2] == DISCOVERED_QUERY_ID


def test_a_second_stale_answer_after_rediscovery_raises(make_client, fake_x) -> None:
    fake_x.bundles[fx.bookmarks_chunk_url()] = fx.bundle_js(DISCOVERED_QUERY_ID)
    not_found = lambda request: httpx.Response(404, text="")  # noqa: E731
    fake_x.graphql.extend([not_found, not_found])

    with pytest.raises(QueryIdDiscoveryError):
        list(make_client().iter_pages())
    assert len(fake_x.graphql_requests()) == 2


def test_extract_bookmarks_query_id_ignores_other_operations() -> None:
    assert extract_bookmarks_query_id(fx.bundle_js("Qid_abcdefgh")) == "Qid_abcdefgh"
    assert (
        extract_bookmarks_query_id('queryId:"AbCdEfGhIj",operationName:"BookmarkFolders"') is None
    )


# -- pagination ------------------------------------------------------------------


def test_two_page_cursor_walk(make_client, fake_x, sleeps) -> None:
    fake_x.graphql.extend(
        [
            page(post("3"), post("2"), cursor="CURSOR-A"),
            page(post("1"), cursor="CURSOR-B"),
            page(cursor="CURSOR-C"),  # X answers the end with cursors and no posts
        ]
    )

    walk = make_client(page_size=20).iter_pages()
    pages = list(walk)

    assert [p.post_ids for p in pages] == [("3", "2"), ("1",)]
    assert [p.number for p in pages] == [1, 2]
    assert (walk.stop_reason, walk.pages_fetched) == (WalkStopReason.EXHAUSTED, 3)
    sent = [variables_of(r) for r in fake_x.graphql_requests()]
    assert [v.get("cursor") for v in sent] == [None, "CURSOR-A", "CURSOR-B"]
    assert all(v["count"] == 20 and v["includePromotedContent"] is False for v in sent)
    assert sleeps == [1.0, 1.0]  # the pause between pages, never before the first


def test_graphql_requests_carry_the_web_session_headers(make_client, fake_x) -> None:
    fake_x.graphql.append(page(post("1")))

    list(make_client().iter_pages())

    request = fake_x.graphql_requests()[0]
    assert request.headers["authorization"] == f"Bearer {X_WEB_BEARER_TOKEN}"
    assert request.headers["cookie"] == f"auth_token={AUTH_TOKEN}; ct0={CT0}"
    assert request.headers["x-csrf-token"] == CT0
    assert request.headers["referer"] == "https://x.com/i/bookmarks"
    assert json.loads(request.url.params["features"])["graphql_timeline_v2_bookmark_timeline"]
    assert "withGrokAnalyze" in json.loads(request.url.params["fieldToggles"])


def test_stop_when_ends_the_walk_after_page_one(make_client, fake_x) -> None:
    fake_x.graphql.extend([page(post("2"), cursor="CURSOR-A"), page(post("1"))])
    seen: list[tuple[str, ...]] = []

    def stop_when(ids: tuple[str, ...]) -> bool:
        seen.append(ids)
        return True

    walk = make_client().iter_pages(stop_when=stop_when)
    pages = list(walk)

    assert [p.post_ids for p in pages] == [("2",)]
    assert seen == [("2",)]
    assert walk.stop_reason is WalkStopReason.STOP_WHEN
    assert len(fake_x.graphql_requests()) == 1


def test_the_page_cap_is_hard(make_client, fake_x) -> None:
    fake_x.graphql.extend([page(post("2"), cursor="A"), page(post("1"), cursor="B")])

    walk = make_client().iter_pages(max_pages=1)

    assert len(list(walk)) == 1
    assert walk.stop_reason is WalkStopReason.PAGE_CAP
    assert len(fake_x.graphql_requests()) == 1
    with pytest.raises(ValueError):
        make_client().iter_pages(max_pages=501)
    with pytest.raises(ValueError):
        make_client(page_size=101)


def test_a_repeated_cursor_ends_the_walk(make_client, fake_x) -> None:
    fake_x.graphql.extend([page(post("2"), cursor="SAME"), page(post("1"), cursor="SAME")])

    walk = make_client().iter_pages()

    assert len(list(walk)) == 2
    assert walk.stop_reason is WalkStopReason.EXHAUSTED


def test_a_caller_breaking_out_is_recorded(make_client, fake_x) -> None:
    fake_x.graphql.extend([page(post("2"), cursor="A")])
    walk = make_client().iter_pages()

    for _page in walk:
        break

    assert walk.stop_reason is WalkStopReason.CALLER_STOPPED
    with pytest.raises(RuntimeError):
        iter(walk)


# -- rate limits -------------------------------------------------------------------


def test_429_waits_until_x_rate_limit_reset_then_retries(make_client, fake_x, sleeps) -> None:
    fake_x.graphql.extend(
        [
            json_response(
                {"errors": [{"code": 88}]}, 429, **{"x-rate-limit-reset": str(int(NOW) + 30)}
            ),
            page(post("1")),
        ]
    )

    walk = make_client().iter_pages()
    pages = list(walk)

    assert [p.post_ids for p in pages] == [("1",)]
    assert sleeps == [30.0]
    assert walk.stop_reason is WalkStopReason.EXHAUSTED


def test_a_rate_limit_beyond_the_cap_stops_gracefully_with_a_partial_walk(
    make_client, fake_x, sleeps
) -> None:
    reset = int(NOW) + 3_600
    fake_x.graphql.extend(
        [
            page(post("2"), cursor="A"),
            json_response({}, 429, **{"x-rate-limit-reset": str(reset)}),
        ]
    )

    walk = make_client(max_rate_limit_wait_s=900).iter_pages()
    pages = list(walk)

    assert [p.post_ids for p in pages] == [("2",)]
    assert walk.stop_reason is WalkStopReason.RATE_LIMITED
    assert walk.rate_limit_reset_at == datetime.fromtimestamp(reset, UTC)
    assert sleeps == [1.0]  # the page pause only; no hour-long sleep


def test_repeated_429s_on_one_page_stop_the_walk(make_client, fake_x, sleeps) -> None:
    limited = json_response({}, 429)  # no reset header: default wait
    fake_x.graphql.extend([limited, limited, limited])

    walk = make_client().iter_pages()

    assert list(walk) == []
    assert walk.stop_reason is WalkStopReason.RATE_LIMITED
    assert sleeps == [60.0, 60.0]


# -- ct0 rotation --------------------------------------------------------------------


def _set_cookie(value: str) -> str:
    return f"ct0={value}; Max-Age=21600; Expires=Thu, 01 Jan 2027 00:00:00 GMT; Path=/; Domain=.x.com; Secure; SameSite=Lax"


def test_a_rotated_ct0_is_written_back_once_with_the_pair_and_used_next(
    make_client, fake_x, adapter, bao
) -> None:
    fake_x.graphql.extend(
        [
            page(post("2"), cursor="A", **{"set-cookie": _set_cookie(ROTATED_CT0)}),
            page(post("1")),
        ]
    )
    provider = make_provider(bao)

    list(make_client(credentials=provider).iter_pages())

    assert len(adapter.calls) == 1
    call = adapter.calls[0]
    assert (call["method"], call["url"]) == ("PATCH", "/v1/secret/data/newsletter")
    assert call["headers"] == {"Content-Type": "application/merge-patch+json"}
    saved_at = datetime.fromtimestamp(NOW, UTC).isoformat(timespec="seconds")
    assert call["json"] == {
        "data": {
            X_AUTH_TOKEN: AUTH_TOKEN,
            X_CT0: ROTATED_CT0,
            f"{X_AUTH_TOKEN}_SAVED_AT": saved_at,
            f"{X_CT0}_SAVED_AT": saved_at,
        }
    }
    second = fake_x.graphql_requests()[1]
    assert second.headers["x-csrf-token"] == ROTATED_CT0
    assert second.headers["cookie"] == f"auth_token={AUTH_TOKEN}; ct0={ROTATED_CT0}"
    assert provider.get(X_CT0) == ROTATED_CT0
    assert provider.metadata(X_CT0).saved_at == datetime.fromtimestamp(NOW, UTC)
    # The accepted pair after the rotation is the one marked verified.
    assert provider.metadata(X_CT0).last_verified_at is not None


def test_an_unchanged_or_deleted_ct0_is_not_written(make_client, fake_x, adapter) -> None:
    fake_x.graphql.extend(
        [
            page(post("3"), cursor="A", **{"set-cookie": _set_cookie(CT0)}),
            page(post("2"), cursor="B", **{"set-cookie": "ct0=; Max-Age=0; Path=/"}),
            page(post("1"), **{"set-cookie": f"ct0={ROTATED_CT0}; Max-Age=0; Path=/"}),
        ]
    )

    list(make_client().iter_pages())

    assert adapter.calls == []


def test_without_openbao_the_rotated_ct0_is_applied_locally(
    make_client, fake_x, bao, caplog
) -> None:
    fake_x.graphql.extend(
        [page(post("2"), cursor="A", **{"set-cookie": _set_cookie(ROTATED_CT0)}), page(post("1"))]
    )
    provider = make_provider(bao)

    list(make_client(credentials=provider, sink_factory=lambda clock: None).iter_pages())

    assert provider.get(X_CT0) == ROTATED_CT0
    assert fake_x.graphql_requests()[1].headers["x-csrf-token"] == ROTATED_CT0
    assert "OpenBao is not configured" in caplog.text


def test_a_failed_write_back_never_fails_the_fetch(make_client, fake_x, bao, caplog) -> None:
    fake_x.graphql.extend(
        [page(post("2"), cursor="A", **{"set-cookie": _set_cookie(ROTATED_CT0)}), page(post("1"))]
    )
    failing = FakeHvacAdapter(fail=True)
    client = make_client(
        credentials=make_provider(bao),
        sink_factory=lambda clock: BaoSink(client=SimpleNamespace(adapter=failing), clock=clock),
    )

    pages = list(client.iter_pages())

    assert [p.post_ids for p in pages] == [("2",), ("1",)]
    assert fake_x.graphql_requests()[1].headers["x-csrf-token"] == ROTATED_CT0
    assert "ct0_write_back_failed (SecretSinkError)" in caplog.text


def test_the_bao_sink_report_does_not_reach_stdout(make_client, fake_x, capsys, caplog) -> None:
    # The worker's sink is quiet (echo=None, as _default_sink_factory builds it):
    # stdout stays clean and the write-back is recorded as a value-free log line.
    caplog.set_level(logging.INFO)
    fake_x.graphql.append(page(post("1"), **{"set-cookie": _set_cookie(ROTATED_CT0)}))

    list(make_client().iter_pages())

    out, _err = capsys.readouterr()
    assert out == ""
    assert "x_bookmarks.ct0_written_back" in caplog.text


def test_the_default_sink_reuses_the_workers_authenticated_client(monkeypatch) -> None:
    monkeypatch.delenv("BAO_ADDR", raising=False)
    assert _default_sink_factory(lambda: datetime.now(UTC)) is None

    worker_client = SimpleNamespace(adapter=FakeHvacAdapter())
    monkeypatch.setenv("BAO_ADDR", "http://bao.test:8200")
    monkeypatch.setattr(bao_secrets, "get_authenticated_bao_client", lambda: worker_client)
    sink = _default_sink_factory(lambda: datetime.now(UTC))

    assert isinstance(sink, BaoSink)
    assert sink._get_client() is worker_client


def test_get_authenticated_bao_client_is_none_without_openbao(monkeypatch) -> None:
    monkeypatch.delenv("BAO_ADDR", raising=False)
    bao_secrets.clear_bao_cache()
    try:
        assert bao_secrets.is_bao_configured() is False
        assert bao_secrets.get_authenticated_bao_client() is None
    finally:
        bao_secrets.clear_bao_cache()


# -- dead sessions and missing credentials ------------------------------------------


def test_401_refreshes_once_then_fails_closed_and_marks_both_rejected(
    make_client, fake_x, bao
) -> None:
    fake_x.graphql.append(json_response({"errors": [{"code": 32}]}, 401))
    provider = make_provider(bao)

    with pytest.raises(SessionExpiredError) as excinfo:
        list(make_client(credentials=provider).iter_pages())

    assert bao.refreshes == 1
    assert len(fake_x.graphql_requests()) == 1  # refresh changed nothing: no retry
    assert excinfo.value.code == SESSION_EXPIRED
    assert excinfo.value.refresh_command == "aca auth session x"
    assert excinfo.value.__cause__ is None and excinfo.value.__context__ is None
    for name in (X_AUTH_TOKEN, X_CT0):
        assert provider.metadata(name).rejected_at is not None
    for sentinel in SENTINELS:
        assert sentinel not in str(excinfo.value)


def test_a_refreshed_pair_that_is_still_refused_is_retried_once(make_client, fake_x, bao) -> None:
    bao.on_refresh = {X_AUTH_TOKEN: FRESH_AUTH_TOKEN, X_CT0: FRESH_CT0}
    refused = json_response({"errors": [{"code": 32}]}, 401)
    fake_x.graphql.extend([refused, refused])
    provider = make_provider(bao)

    with pytest.raises(SessionExpiredError):
        list(make_client(credentials=provider).iter_pages())

    retry = fake_x.graphql_requests()[1]
    assert retry.headers["x-csrf-token"] == FRESH_CT0
    assert provider.metadata(X_CT0).rejected_at is not None


def test_a_refreshed_pair_that_works_recovers(make_client, fake_x, bao) -> None:
    bao.on_refresh = {X_AUTH_TOKEN: FRESH_AUTH_TOKEN, X_CT0: FRESH_CT0}
    fake_x.graphql.extend([json_response({}, 403), page(post("1"))])
    provider = make_provider(bao)

    pages = list(make_client(credentials=provider).iter_pages())

    assert [p.post_ids for p in pages] == [("1",)]
    assert provider.metadata(X_CT0).rejected_at is None
    assert provider.metadata(X_AUTH_TOKEN).last_verified_at is not None


def test_an_html_login_page_yields_session_expired(make_client, fake_x) -> None:
    login = lambda request: httpx.Response(  # noqa: E731
        200,
        text='<html><body><div id="LoginForm"></div></body></html>',
        headers={"content-type": "text/html; charset=utf-8"},
    )
    fake_x.graphql.extend([login])

    with pytest.raises(SessionExpiredError):
        list(make_client().iter_pages())


def test_a_login_redirect_on_the_discovery_page_yields_session_expired(make_client, fake_x) -> None:
    fake_x.page = lambda request: httpx.Response(
        302,
        headers={"location": "https://x.com/i/flow/login?redirect_after_login=%2Fi%2Fbookmarks"},
    )

    with pytest.raises(SessionExpiredError):
        list(make_client(query_id_store=MemoryQueryIdStore()).iter_pages())


def test_a_cloudflare_403_is_not_a_session_verdict(make_client, fake_x, bao) -> None:
    fake_x.graphql.append(json_response({}, 403, **{"cf-mitigated": "challenge"}))
    provider = make_provider(bao)

    with pytest.raises(XBookmarksUpstreamError) as excinfo:
        list(make_client(credentials=provider).iter_pages())

    assert excinfo.value.status_code == 403
    assert bao.refreshes == 0
    assert provider.metadata(X_CT0).rejected_at is None


def test_a_network_error_is_reported_by_type_without_the_request(make_client, fake_x) -> None:
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    fake_x.graphql.append(boom)

    with pytest.raises(XBookmarksUpstreamError) as excinfo:
        list(make_client().iter_pages())

    assert "ConnectError" in str(excinfo.value)
    assert excinfo.value.__cause__ is None and excinfo.value.__context__ is None


@pytest.mark.parametrize(
    ("values", "label"),
    [
        ({X_CT0: CT0}, "x.auth_token"),
        ({X_AUTH_TOKEN: AUTH_TOKEN}, "x.ct0"),
        ({}, "x.auth_token/x.ct0"),
    ],
)
def test_a_missing_cookie_raises_credentials_missing_before_any_request(
    make_client, fake_x, values, label
) -> None:
    bao = FakeBao(values)

    with pytest.raises(CredentialsMissingError) as excinfo:
        list(make_client(credentials=make_provider(bao)).iter_pages())

    assert excinfo.value.code == CREDENTIALS_MISSING
    assert excinfo.value.credential_label == label
    assert bao.refreshes == 1  # one bounded refresh before failing closed
    assert fake_x.requests == []


def test_a_pair_patched_in_since_boot_is_picked_up_by_the_refresh(make_client, fake_x) -> None:
    bao = FakeBao({})
    bao.on_refresh = {X_AUTH_TOKEN: AUTH_TOKEN, X_CT0: CT0}
    fake_x.graphql.append(page(post("1")))

    assert len(list(make_client(credentials=make_provider(bao)).iter_pages())) == 1


# -- record mapping -----------------------------------------------------------------


def test_note_tweet_quoted_media_and_links_map_to_the_record() -> None:
    quoted = fx.tweet_result(
        "200",
        "the quoted post https://t.co/q1",
        user=fx.user_result("bob", "Bob", "2002", new_shape=False),
        urls=[fx.url_entity("https://t.co/q1", "https://blog.example/quoted")],
        quoted=fx.tweet_result("300", "a quote of a quote"),
    )
    result = fx.tweet_result(
        "100",
        "Truncated legacy text https://t.co/aaa https://t.co/video1",
        urls=[
            fx.url_entity("https://t.co/aaa", "https://paper.example/a"),
            fx.url_entity("https://t.co/self", "https://x.com/bob/status/200"),
        ],
        media=[fx.video_media(), fx.photo_media()],
        note_text=(
            "The full long-form text, well past 280 characters, with a link "
            "https://t.co/bbb and #agents"
        ),
        note_urls=[
            fx.url_entity("https://t.co/bbb", "https://article.example/b"),
            fx.url_entity("https://t.co/ccc", "https://twitter.com/i/lists/1"),
        ],
        quoted=quoted,
        conversation_id="99",
        in_reply_to="98",
        hashtags=["agents"],
        mentions=["carol"],
        visibility_wrapper=True,
    )

    record = parse_tweet_result(result)

    assert record is not None
    assert record.post_id == "100"
    assert record.url == "https://x.com/alice/status/100"
    assert record.text.startswith("The full long-form text")
    assert "https://article.example/b" in record.text and "t.co" not in record.text
    assert record.is_long_form is True
    assert (record.author_handle, record.author_name, record.author_id) == (
        "alice",
        "Alice Example",
        "1001",
    )
    assert record.created_at == datetime(2018, 10, 10, 20, 19, 24, tzinfo=UTC)
    assert (record.conversation_id, record.in_reply_to_post_id) == ("99", "98")
    assert record.outbound_urls == ("https://paper.example/a", "https://article.example/b")
    assert record.media_urls == (
        "https://video.twimg.com/ext_tw_video/VIDEO1/pu/vid/high.mp4",
        "https://pbs.twimg.com/media/PHOTO1.jpg",
    )
    assert (record.hashtags, record.mentions) == (("agents",), ("carol",))
    assert (record.like_count, record.repost_count, record.reply_count) == (42, 7, 4)

    assert record.quoted is not None
    assert record.quoted.post_id == "200"
    assert record.quoted.author_handle == "bob"  # the older legacy author shape
    assert record.quoted.url == "https://x.com/bob/status/200"
    assert record.quoted.text == "the quoted post https://blog.example/quoted"
    assert record.quoted.outbound_urls == ("https://blog.example/quoted",)
    assert record.quoted.quoted is None  # one level only


def test_legacy_text_is_unescaped_and_media_links_dropped() -> None:
    record = parse_tweet_result(
        fx.tweet_result("7", "R&amp;D &gt; hype https://t.co/photo1", media=[fx.photo_media()])
    )

    assert record is not None
    assert (record.text, record.is_long_form) == ("R&D > hype", False)
    assert record.outbound_urls == ()


def test_unusable_results_are_skipped_and_the_page_keeps_order() -> None:
    body = fx.bookmarks_response(
        [post("5"), fx.tombstone_result(), post("4"), post("5")], bottom_cursor="NEXT"
    )

    parsed = parse_bookmarks_page(body, number=3)

    assert (parsed.post_ids, parsed.next_cursor, parsed.number) == (("5", "4"), "NEXT", 3)
    assert parse_tweet_result({"__typename": "TweetUnavailable"}) is None
    assert parse_bookmarks_page({"data": {}}).posts == ()


def test_author_less_posts_fall_back_to_the_web_status_url() -> None:
    result = fx.tweet_result("8", "text")
    result["core"] = {}

    record = parse_tweet_result(result)

    assert record is not None
    assert record.url == "https://x.com/i/web/status/8"
    assert record.author_handle is None


@pytest.mark.parametrize(
    ("url", "self_link"),
    [
        ("https://x.com/a/status/1", True),
        ("https://mobile.twitter.com/a", True),
        ("https://t.co/abc", True),
        ("https://pic.x.com/abc", True),
        ("https://notx.com/a", False),
        ("https://example.com/x.com", False),
    ],
)
def test_is_x_self_link(url: str, self_link: bool) -> None:
    assert is_x_self_link(url) is self_link


def test_records_do_not_repr_cursors() -> None:
    parsed = parse_bookmarks_page(fx.bookmarks_response([post("1")], bottom_cursor="SECRETISH"))
    assert "SECRETISH" not in repr(parsed)


# -- the durable query ID cache ---------------------------------------------------------


def test_settings_query_id_store_round_trips_through_settings_overrides(db_session) -> None:
    from src.services.settings_service import SettingsService

    store = SettingsQueryIdStore(db_factory=lambda: contextlib.nullcontext(db_session))

    assert store.get() is None
    store.set(DISCOVERED_QUERY_ID)
    assert store.get() == DISCOVERED_QUERY_ID
    assert SettingsService(db_session).get(QUERY_ID_SETTING_KEY) == DISCOVERED_QUERY_ID

    SettingsService(db_session).set(QUERY_ID_SETTING_KEY, "bad id with spaces")
    assert store.get() is None  # a malformed value is a miss, never a URL path

    store.clear()
    assert SettingsService(db_session).get(QUERY_ID_SETTING_KEY) is None


def test_settings_query_id_store_fails_open_when_the_database_is_down(caplog) -> None:
    def broken() -> contextlib.AbstractContextManager[Any]:
        raise ConnectionError("db down")

    store = SettingsQueryIdStore(db_factory=broken)

    assert store.get() is None
    store.set(DISCOVERED_QUERY_ID)
    store.clear()
    assert "query_id_cache_unavailable (ConnectionError)" in caplog.text


def test_page_delay_defaults_to_one_second() -> None:
    from src.config.settings import Settings

    assert Settings(_env_file=None).x_bookmarks_page_delay_s == 1.0
