"""Paid Substack posts are fetched with the live session cookie (ri-18).

Network-free: every Substack answer comes from an ``httpx.MockTransport`` that
serves a teaser body to a request without the valid ``substack.sid`` and the
full body to one that carries it, the way Substack's paywall does. No test
sends or prints a real cookie.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

import src.config.bao_secrets as bao_mod
import src.config.credentials as credentials_mod
from src.config.credentials import SUBSTACK_SESSION_COOKIE, CredentialProvider
from src.config.sources import SubstackSource
from src.ingestion.credential_failures import CREDENTIALS_MISSING, SESSION_EXPIRED
from src.ingestion.real_ingest_policy import LiveDecision, evaluate_live_adapter
from src.ingestion.registry import SOURCE_REGISTRY
from src.ingestion.substack import (
    BODY_FULL,
    BODY_STATE_KEY,
    BODY_TEASER,
    SESSION_PROBE_URL,
    SUBSTACK_REFRESH_COMMAND,
    SubstackClient,
    SubstackContentIngestionService,
    is_teaser_body,
)
from src.models.content import Content, ContentSource, ContentStatus
from src.models.summary import Summary
from src.utils.content_hash import generate_markdown_hash

GOOD_COOKIE = "sid-paid-reader-value-111"
OTHER_COOKIE = "sid-rotated-value-222"
ALL_COOKIES = (GOOD_COOKIE, OTHER_COOKIE)

PUBLICATION = "https://paid.substack.com"
ARCHIVE_URL = f"{PUBLICATION}/api/v1/archive"
SOURCE = SubstackSource(name="Paid", url=PUBLICATION)

FULL_WORDS = 120
TEASER_WORDS = 12


def _full_html(post_id: int) -> str:
    words = " ".join(f"insight{post_id}w{i}" for i in range(FULL_WORDS))
    return f"<p>Paid analysis {post_id} begins.</p><p>{words}</p><p>PAID-ENDING-{post_id}</p>"


def _teaser_html(post_id: int) -> str:
    words = " ".join(f"insight{post_id}w{i}" for i in range(TEASER_WORDS))
    return f"<p>Paid analysis {post_id} begins.</p><p>{words}</p>"


def _archive_entry(post_id: int, *, audience: str = "only_paid") -> dict[str, Any]:
    # The archive listing carries metadata only, never the body.
    return {
        "id": post_id,
        "slug": f"post-{post_id}",
        "title": f"Paid post {post_id}",
        "canonical_url": f"{PUBLICATION}/p/post-{post_id}",
        "post_date": "2026-09-20T10:00:00Z",
        "audience": audience,
        "wordcount": FULL_WORDS + 6,
    }


def _settings(cookie: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(substack_session_cookie=cookie, x_auth_token=None, x_ct0=None)


class _FakeBao:
    """In-memory OpenBao: ``remote`` is the KV path, ``cache`` the worker's copy."""

    def __init__(self, cookie: str | None) -> None:
        self.remote: dict[str, str] = {SUBSTACK_SESSION_COOKIE: cookie} if cookie else {}
        self.cache: dict[str, str] = dict(self.remote)
        self.refreshes = 0

    def read(self) -> dict[str, str]:
        return dict(self.cache)

    def refresh(self, *, min_interval_s: float = 0.0) -> bool:
        self.refreshes += 1
        changed = self.cache != self.remote
        self.cache = dict(self.remote)
        return changed

    def provider(self) -> CredentialProvider:
        return CredentialProvider(
            settings_factory=_settings, bao_reader=self.read, bao_refresher=self.refresh
        )


def _sid(request: httpx.Request) -> str | None:
    for part in request.headers.get("cookie", "").split(";"):
        name, _, value = part.strip().partition("=")
        if name == "substack.sid":
            return value
    return None


class _PaywalledSubstack:
    """Serves the full body only to a request carrying ``paying_cookie``."""

    def __init__(
        self,
        entries: list[dict[str, Any]],
        *,
        paying_cookie: str = GOOD_COOKIE,
        override: Callable[[httpx.Request], httpx.Response | None] | None = None,
    ) -> None:
        self.entries = entries
        self.paying_cookie = paying_cookie
        self.override = override
        self.calls: list[tuple[str, str | None]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        sid = _sid(request)
        self.calls.append((str(request.url.copy_with(query=None)), sid))
        if self.override is not None and (answer := self.override(request)) is not None:
            return answer
        path = request.url.path
        if str(request.url).startswith(SESSION_PROBE_URL):
            return httpx.Response(200, json={"subscriptions": [], "publications": []})
        if path == "/api/v1/archive":
            return httpx.Response(200, json=self.entries)
        if path.startswith("/api/v1/posts/"):
            slug = path.rsplit("/", 1)[-1]
            entry = next((e for e in self.entries if e["slug"] == slug), None)
            if entry is None:
                return httpx.Response(404, json={"error": "not found"})
            post_id = entry["id"]
            paid = entry["audience"] == "only_paid"
            body = (
                _full_html(post_id)
                if not paid or sid == self.paying_cookie
                else _teaser_html(post_id)
            )
            return httpx.Response(200, json={**entry, "body_html": body})
        return httpx.Response(404)

    def post_fetch_calls(self) -> list[tuple[str, str | None]]:
        return [call for call in self.calls if not call[0].startswith(SESSION_PROBE_URL)]


def _service(provider: CredentialProvider, transport: Any) -> SubstackContentIngestionService:
    service = SubstackContentIngestionService(credentials=provider)
    service.client.close()
    service.client = SubstackClient(
        credentials=provider,
        http_client=httpx.Client(transport=httpx.MockTransport(transport)),
        request_delay_s=0,
    )
    return service


@contextmanager
def _captured_logs() -> Iterator[list[logging.LogRecord]]:
    records: list[logging.LogRecord] = []

    class _Handler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = _Handler(level=logging.DEBUG)
    root = logging.getLogger("src")
    previous = root.level
    root.setLevel(logging.DEBUG)
    root.addHandler(handler)
    try:
        yield records
    finally:
        root.removeHandler(handler)
        root.setLevel(previous)


def _assert_no_cookie(*texts: object) -> None:
    blob = "\n".join(str(text) for text in texts)
    for value in ALL_COOKIES:
        assert value not in blob


def _log_blob(records: list[logging.LogRecord]) -> str:
    return "\n".join(f"{r.getMessage()} {r.args!r} {r.exc_text or ''}" for r in records)


class _RecordingDb:
    """Mock session that records added rows; every dedup query finds nothing."""

    def __init__(self) -> None:
        self.db = MagicMock()
        self.db.query.return_value.filter.return_value.first.return_value = None
        self.added: list[Content] = []
        self.db.add.side_effect = self.added.append

    @contextmanager
    def get_db(self) -> Iterator[MagicMock]:
        yield self.db


@contextmanager
def _persist_into(get_db: Callable[[], Any]) -> Iterator[None]:
    with (
        patch("src.ingestion.substack.get_db", get_db),
        patch("src.ingestion.substack.find_existing_substack_content", return_value=None),
        patch("src.services.indexing.index_content"),
    ):
        yield


@pytest.fixture(autouse=True)
def _isolate(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    bao_mod.clear_bao_cache()
    monkeypatch.setattr(credentials_mod, "_default_provider", None)
    yield
    bao_mod.clear_bao_cache()


# -- teaser detection ------------------------------------------------------------


@pytest.mark.parametrize(
    ("post", "teaser"),
    [
        ({"audience": "everyone", "body_html": ""}, False),  # free: never a teaser
        ({"audience": "only_paid"}, True),  # no body at all
        ({"audience": "only_paid", "body_html": "   "}, True),
        ({"audience": "founding", "body_html": _teaser_html(1), "wordcount": 126}, True),
        ({"audience": "only_paid", "body_html": _full_html(1), "wordcount": 126}, False),
        ({"audience": "only_paid", "body_html": _teaser_html(1)}, False),  # no evidence
        ({"audience": "only_paid", "body_html": _teaser_html(1), "wordcount": True}, False),
    ],
)
def test_teaser_detection_uses_audience_body_and_wordcount(
    post: dict[str, Any], teaser: bool
) -> None:
    assert is_teaser_body(post) is teaser


# -- acceptance 1: the full paid body is ingested with the cookie ------------------


def test_paid_post_is_ingested_in_full_with_the_cookie() -> None:
    substack = _PaywalledSubstack([_archive_entry(101), _archive_entry(102)])
    service = _service(_FakeBao(GOOD_COOKIE).provider(), substack)
    recorder = _RecordingDb()

    with _persist_into(recorder.get_db):
        response = service.ingest_content(sources=[SOURCE])
    service.close()

    assert response.status == "ok"
    assert response.items_ingested == 2
    assert [row.source_id for row in recorder.added] == ["101", "102"]
    for row in recorder.added:
        assert f"PAID-ENDING-{row.source_id}" in row.markdown_content
        assert row.metadata_json[BODY_STATE_KEY] == BODY_FULL
        assert row.metadata_json["audience"] == "only_paid"
        assert row.status == ContentStatus.PARSED
    assert (f"{PUBLICATION}/api/v1/posts/post-101", GOOD_COOKIE) in substack.calls


def test_the_same_post_fetched_without_the_paying_cookie_is_a_teaser() -> None:
    """Control for the mock: a session that does not unlock the tier gets the teaser."""
    substack = _PaywalledSubstack([_archive_entry(101)], paying_cookie=OTHER_COOKIE)
    service = _service(_FakeBao(GOOD_COOKIE).provider(), substack)
    recorder = _RecordingDb()

    with _captured_logs() as records, _persist_into(recorder.get_db):
        response = service.ingest_content(sources=[SOURCE])
    service.close()

    assert response.items_ingested == 1
    (row,) = recorder.added
    assert "PAID-ENDING-101" not in row.markdown_content
    assert row.metadata_json[BODY_STATE_KEY] == BODY_TEASER
    assert "substack.paid_teasers" in _log_blob(records)


# -- acceptance 2: every post-fetch request carries the live cookie ----------------


def test_every_post_fetch_request_carries_the_live_cookie_and_nothing_leaks() -> None:
    bao = _FakeBao(GOOD_COOKIE)
    substack = _PaywalledSubstack([_archive_entry(i) for i in (101, 102, 103)])
    service = _service(bao.provider(), substack)
    recorder = _RecordingDb()

    with _captured_logs() as records, _persist_into(recorder.get_db):
        response = service.ingest_content(sources=[SOURCE])
    service.close()

    post_calls = substack.post_fetch_calls()
    assert [url for url, _ in post_calls] == [
        ARCHIVE_URL,
        f"{PUBLICATION}/api/v1/posts/post-101",
        f"{PUBLICATION}/api/v1/posts/post-102",
        f"{PUBLICATION}/api/v1/posts/post-103",
    ]
    assert {sid for _, sid in post_calls} == {GOOD_COOKIE}
    _assert_no_cookie(response.model_dump_json(), _log_blob(records))


def test_a_rotated_cookie_reaches_the_next_post_request() -> None:
    bao = _FakeBao(GOOD_COOKIE)
    provider = bao.provider()
    entries = [_archive_entry(101), _archive_entry(102)]

    def rotate_after_first_post(request: httpx.Request) -> httpx.Response | None:
        if request.url.path.endswith("/post-101"):
            bao.remote[SUBSTACK_SESSION_COOKIE] = bao.cache[SUBSTACK_SESSION_COOKIE] = OTHER_COOKIE
        return None

    substack = _PaywalledSubstack(
        entries, paying_cookie=OTHER_COOKIE, override=rotate_after_first_post
    )
    client = SubstackClient(
        credentials=provider,
        http_client=httpx.Client(transport=httpx.MockTransport(substack)),
        request_delay_s=0,
    )
    try:
        posts = client.fetch_posts(PUBLICATION, max_entries=2)
    finally:
        client.close()

    assert [sid for _, sid in substack.calls] == [GOOD_COOKIE, GOOD_COOKIE, OTHER_COOKIE]
    assert "PAID-ENDING-102" in posts[1]["body_html"]


def test_a_dead_session_on_a_post_body_fails_closed_without_the_value() -> None:
    bao = _FakeBao(GOOD_COOKIE)

    def refuse_post_bodies(request: httpx.Request) -> httpx.Response | None:
        if request.url.path.startswith("/api/v1/posts/"):
            return httpx.Response(401, json={"error": "Not authorized"})
        return None

    substack = _PaywalledSubstack([_archive_entry(101)], override=refuse_post_bodies)
    service = _service(bao.provider(), substack)

    with (
        _captured_logs() as records,
        patch("src.ingestion.substack.get_db") as get_db,
    ):
        response = service.ingest_content(sources=[SOURCE])
    service.close()

    assert response.status == "error"
    assert response.items_ingested == 0
    assert [error.code for error in response.errors] == [SESSION_EXPIRED]
    assert bao.refreshes == 1
    get_db.assert_not_called()
    _assert_no_cookie(response.model_dump_json(), _log_blob(records))


def test_publication_host_move_is_followed_once_with_the_cookie() -> None:
    moved = "https://www.paid-newsletter.com"

    def host_move(request: httpx.Request) -> httpx.Response | None:
        if request.url.host == "paid.substack.com":
            target = request.url.copy_with(scheme="https", host="www.paid-newsletter.com")
            return httpx.Response(301, headers={"location": str(target)})
        return None

    substack = _PaywalledSubstack([_archive_entry(101)], override=host_move)
    client = SubstackClient(
        credentials=_FakeBao(GOOD_COOKIE).provider(),
        http_client=httpx.Client(transport=httpx.MockTransport(substack)),
        request_delay_s=0,
    )
    try:
        posts = client.fetch_posts(PUBLICATION, max_entries=1)
    finally:
        client.close()

    assert substack.calls == [
        (ARCHIVE_URL, GOOD_COOKIE),
        (f"{moved}/api/v1/archive", GOOD_COOKIE),
        (f"{PUBLICATION}/api/v1/posts/post-101", GOOD_COOKIE),
        (f"{moved}/api/v1/posts/post-101", GOOD_COOKIE),
    ]
    assert "PAID-ENDING-101" in posts[0]["body_html"]


def test_redirect_to_another_path_is_not_followed() -> None:
    def elsewhere(request: httpx.Request) -> httpx.Response | None:
        if request.url.path == "/api/v1/archive":
            return httpx.Response(302, headers={"location": "https://tracker.example/collect"})
        return None

    substack = _PaywalledSubstack([_archive_entry(101)], override=elsewhere)
    client = SubstackClient(
        credentials=_FakeBao(GOOD_COOKIE).provider(),
        http_client=httpx.Client(transport=httpx.MockTransport(substack)),
        request_delay_s=0,
    )
    try:
        assert client.fetch_posts(PUBLICATION, max_entries=1) == []
    finally:
        client.close()
    assert substack.calls == [(ARCHIVE_URL, GOOD_COOKIE)]


@pytest.mark.parametrize("slug", ["../../api/v1/subscriptions", "a/b", "", None, "-x"])
def test_unsafe_slug_is_never_requested(slug: Any) -> None:
    entry = {**_archive_entry(101), "slug": slug}
    substack = _PaywalledSubstack([entry])
    client = SubstackClient(
        credentials=_FakeBao(GOOD_COOKIE).provider(),
        http_client=httpx.Client(transport=httpx.MockTransport(substack)),
        request_delay_s=0,
    )
    try:
        posts = client.fetch_posts(PUBLICATION, max_entries=1)
    finally:
        client.close()
    assert substack.calls == [(ARCHIVE_URL, GOOD_COOKIE)]
    assert posts == [entry]


# -- a 403 on a publication endpoint is settled by the session probe ------------------


def _probe_then(later: Callable[[], httpx.Response]) -> Callable[[httpx.Request], Any]:
    """Probe answers 200 on the run's first probe, then ``later()`` on re-probes."""
    probes = {"n": 0}

    def answer(request: httpx.Request) -> httpx.Response | None:
        if str(request.url).startswith(SESSION_PROBE_URL):
            probes["n"] += 1
            if probes["n"] > 1:
                return later()
            return None
        if request.url.path in ("/api/v1/posts/post-102", "/api/v1/posts/post-103"):
            return httpx.Response(403, json={"error": "Forbidden"})
        return None

    return answer


def _founding_entries() -> list[dict[str, Any]]:
    entries = [_archive_entry(101), _archive_entry(102), _archive_entry(103)]
    for entry in entries[1:]:
        entry["audience"] = "founding"
        entry["truncated_body_text"] = f"Founding preview {entry['id']}."
    return entries


def _probe_count(substack: _PaywalledSubstack) -> int:
    return sum(1 for url, _ in substack.calls if url.startswith(SESSION_PROBE_URL))


def test_post_403_with_a_live_session_keeps_the_teaser_and_continues() -> None:
    bao = _FakeBao(GOOD_COOKIE)
    provider = bao.provider()
    substack = _PaywalledSubstack(
        _founding_entries(),
        override=_probe_then(lambda: httpx.Response(200, json={"subscriptions": []})),
    )
    service = _service(provider, substack)
    recorder = _RecordingDb()

    with _captured_logs() as records, _persist_into(recorder.get_db):
        response = service.ingest_content(sources=[SOURCE])
    service.close()

    assert response.status == "ok"
    assert response.items_ingested == 3
    full, *teasers = recorder.added
    assert full.metadata_json[BODY_STATE_KEY] == BODY_FULL
    for row in teasers:
        assert row.metadata_json[BODY_STATE_KEY] == BODY_TEASER
        assert row.markdown_content == f"Founding preview {row.source_id}."
    assert _probe_count(substack) == 2  # the run's probe plus ONE re-probe for two 403s
    assert bao.refreshes == 0
    metadata = provider.metadata(SUBSTACK_SESSION_COOKIE)
    assert metadata.rejected_at is None  # a per-post refusal is not a session verdict
    blob = _log_blob(records)
    assert "substack.post_access_denied" in blob
    assert "post-102" in blob and "post-103" in blob
    _assert_no_cookie(response.model_dump_json(), blob)


def test_post_403_with_a_dead_session_fails_closed_with_zero_rows() -> None:
    bao = _FakeBao(GOOD_COOKIE)
    provider = bao.provider()
    substack = _PaywalledSubstack(
        _founding_entries(),
        override=_probe_then(lambda: httpx.Response(401, json={"error": "Not authorized"})),
    )
    service = _service(provider, substack)

    with _captured_logs() as records, patch("src.ingestion.substack.get_db") as get_db:
        response = service.ingest_content(sources=[SOURCE])
    service.close()

    assert response.status == "error"
    assert response.items_ingested == 0
    assert [error.code for error in response.errors] == [SESSION_EXPIRED]
    get_db.assert_not_called()
    assert bao.refreshes == 1  # the probe's own refresh-once
    assert provider.metadata(SUBSTACK_SESSION_COOKIE).rejected_at is not None
    # Nothing after the failed re-probe: post-103 was never requested.
    assert (f"{PUBLICATION}/api/v1/posts/post-103", GOOD_COOKIE) not in substack.calls
    _assert_no_cookie(response.model_dump_json(), _log_blob(records))


def test_archive_403_with_a_live_session_skips_only_that_publication() -> None:
    other = SubstackSource(name="Other", url="https://other.substack.com")

    def forbid_paid_archive(request: httpx.Request) -> httpx.Response | None:
        if request.url.host == "paid.substack.com" and request.url.path == "/api/v1/archive":
            return httpx.Response(403, json={"error": "Forbidden"})
        return None

    substack = _PaywalledSubstack([_archive_entry(101)], override=forbid_paid_archive)
    service = _service(_FakeBao(GOOD_COOKIE).provider(), substack)
    recorder = _RecordingDb()

    with _captured_logs() as records, _persist_into(recorder.get_db):
        response = service.ingest_content(sources=[SOURCE, other])
    service.close()

    assert response.items_ingested == 1  # the other publication still ran
    assert "substack.archive_access_denied" in _log_blob(records)


def test_cloudflare_403_is_neither_probed_nor_a_verdict() -> None:
    def challenge(request: httpx.Request) -> httpx.Response | None:
        if request.url.path.startswith("/api/v1/posts/"):
            return httpx.Response(403, headers={"cf-mitigated": "challenge"})
        return None

    substack = _PaywalledSubstack([_archive_entry(101)], override=challenge)
    client = SubstackClient(
        credentials=_FakeBao(GOOD_COOKIE).provider(),
        http_client=httpx.Client(transport=httpx.MockTransport(substack)),
        request_delay_s=0,
    )
    try:
        posts = client.fetch_posts(PUBLICATION, max_entries=1)
    finally:
        client.close()
    assert _probe_count(substack) == 0
    assert "body_html" not in posts[0]


# -- polite pacing ------------------------------------------------------------------------


def test_post_detail_requests_are_paced() -> None:
    slept: list[float] = []
    substack = _PaywalledSubstack([_archive_entry(i) for i in (101, 102, 103)])
    client = SubstackClient(
        credentials=_FakeBao(GOOD_COOKIE).provider(),
        http_client=httpx.Client(transport=httpx.MockTransport(substack)),
        request_delay_s=1.5,
        sleep=slept.append,
    )
    try:
        client.fetch_posts(PUBLICATION, max_entries=3)
        client.fetch_posts(PUBLICATION, max_entries=1)  # pacing spans publications
        client.begin_run()
        client.fetch_posts(PUBLICATION, max_entries=1)  # a new run starts unpaced
    finally:
        client.close()
    assert slept == [1.5, 1.5, 1.5]


def test_request_delay_defaults_to_the_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.config.settings import Settings

    assert Settings(_env_file=None).substack_request_delay_s == 1.0
    fake = SimpleNamespace(substack_request_delay_s=0.25)
    monkeypatch.setattr("src.ingestion.substack.get_settings", lambda: fake)
    client = SubstackClient(credentials=_FakeBao(GOOD_COOKIE).provider())
    try:
        assert client._request_delay_s == 0.25
    finally:
        client.close()


# -- acceptance 3: no cookie fails closed with credentials_missing -----------------


def test_cookie_less_run_returns_zero_rows_with_credentials_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bao = _FakeBao(None)
    provider = bao.provider()
    monkeypatch.setattr(credentials_mod, "_default_provider", provider)
    substack = _PaywalledSubstack([_archive_entry(101)])
    service = _service(provider, substack)

    with _captured_logs() as records, patch("src.ingestion.substack.get_db") as get_db:
        response = service.ingest_content(sources=[SOURCE])
    service.close()

    assert response.status == "error"
    assert response.items_ingested == 0
    assert [error.code for error in response.errors] == [CREDENTIALS_MISSING]
    message = response.errors[0].message
    assert "substack.sid" in message
    assert SUBSTACK_REFRESH_COMMAND in message
    assert substack.calls == []  # no request at all, logged out or otherwise
    assert bao.refreshes == 1  # one bounded OpenBao refresh before failing closed
    get_db.assert_not_called()
    assert "substack.credentials_missing" in _log_blob(records)

    readiness = SOURCE_REGISTRY.get("substack").resolve_readiness(SOURCE)
    assert (readiness.ready, readiness.code) == (False, CREDENTIALS_MISSING)


def test_cookie_patched_into_openbao_is_found_by_the_refresh() -> None:
    bao = _FakeBao(None)
    bao.remote[SUBSTACK_SESSION_COOKIE] = GOOD_COOKIE  # written, not yet cached
    substack = _PaywalledSubstack([_archive_entry(101)])
    service = _service(bao.provider(), substack)
    recorder = _RecordingDb()

    with _persist_into(recorder.get_db):
        response = service.ingest_content(sources=[SOURCE])
    service.close()

    assert response.status == "ok"
    assert response.items_ingested == 1
    assert {sid for _, sid in substack.calls} == {GOOD_COOKIE}


def test_run_without_enabled_sources_needs_no_cookie() -> None:
    service = _service(_FakeBao(None).provider(), _PaywalledSubstack([]))
    disabled = SubstackSource(name="Off", url=PUBLICATION, enabled=False)
    response = service.ingest_content(sources=[disabled])
    service.close()
    assert response.status == "ok"
    assert response.errors == []


def test_live_ingest_tier_skips_substack_without_the_cookie() -> None:
    skipped = evaluate_live_adapter("substack", live_enabled=True, env={})
    assert skipped.decision is LiveDecision.SKIP_MISSING_CREDENTIAL
    assert "SUBSTACK_SESSION_COOKIE" in skipped.reason
    live = evaluate_live_adapter(
        "substack", live_enabled=True, env={"SUBSTACK_SESSION_COOKIE": "x"}
    )
    assert live.decision is LiveDecision.LIVE


# -- acceptance 4: a stored teaser is upgraded on the next authenticated run -------


def _stored_row(
    db_session: Any,
    post_id: int,
    *,
    markdown: str,
    metadata: dict[str, Any] | None,
    status: ContentStatus = ContentStatus.COMPLETED,
) -> Content:
    row = Content(
        source_type=ContentSource.SUBSTACK,
        source_id=str(post_id),
        source_url=f"{PUBLICATION}/p/post-{post_id}",
        title=f"Paid post {post_id}",
        publication="Paid",
        markdown_content=markdown,
        metadata_json=metadata,
        raw_content=_teaser_html(post_id),
        raw_format="html",
        parser_used="substack_api",
        content_hash=generate_markdown_hash(markdown),
        status=status,
    )
    db_session.add(row)
    db_session.flush()
    return row


def _teaser_markdown(post_id: int) -> str:
    return f"Paid analysis {post_id} begins.\n\n" + " ".join(
        f"insight{post_id}w{i}" for i in range(TEASER_WORDS)
    )


def _run_authenticated(db_session: Any, entries: list[dict[str, Any]]) -> tuple[Any, list[str]]:
    """Run once with the paying cookie; return the envelope and re-indexed source ids."""

    @contextmanager
    def get_db() -> Iterator[Any]:
        yield db_session

    service = _service(_FakeBao(GOOD_COOKIE).provider(), _PaywalledSubstack(entries))
    try:
        with (
            patch("src.ingestion.substack.get_db", get_db),
            patch("src.services.indexing.index_content"),
            patch("src.services.indexing.reindex_content") as reindex,
        ):
            response = service.ingest_content(sources=[SOURCE])
    finally:
        service.close()
    return response, [call.args[0].source_id for call in reindex.call_args_list]


def test_stored_teaser_rows_are_upgraded_and_resummarized(db_session: Any) -> None:
    from tests.factories.summary import SummaryFactory

    # Recorded as a teaser by this adapter...
    marked = _stored_row(
        db_session,
        201,
        markdown=_teaser_markdown(201),
        metadata={BODY_STATE_KEY: BODY_TEASER, "audience": "only_paid"},
    )
    # ...and one stored before bodies were classified (always fetched logged out).
    legacy = _stored_row(db_session, 202, markdown=_teaser_markdown(202), metadata={"post_id": 202})
    SummaryFactory(content=marked, content_id=marked.id)
    SummaryFactory(content=legacy, content_id=legacy.id)

    response, reindexed = _run_authenticated(db_session, [_archive_entry(201), _archive_entry(202)])

    assert response.status == "ok"
    assert response.items_ingested == 2
    assert reindexed == ["201", "202"]
    for row in (marked, legacy):
        db_session.refresh(row)
        assert "PAID-ENDING" in row.markdown_content
        assert row.metadata_json[BODY_STATE_KEY] == BODY_FULL
        assert row.status == ContentStatus.PARSED
        assert row.content_hash == generate_markdown_hash(row.markdown_content)
        assert db_session.query(Summary).filter(Summary.content_id == row.id).count() == 0
    assert (
        db_session.query(Content).filter(Content.source_type == ContentSource.SUBSTACK).count() == 2
    )


def test_upgrade_stays_narrow(db_session: Any) -> None:
    # A full body already stored: dedup skips it.
    full_markdown = "Paid analysis 301 is complete. " + "word " * 150
    full = _stored_row(
        db_session, 301, markdown=full_markdown, metadata={BODY_STATE_KEY: BODY_FULL}
    )
    # A free post (never a teaser), even with a short stored body.
    free = _stored_row(db_session, 302, markdown="short free note", metadata=None)
    # A teaser the ingestion filter rejected keeps its decision.
    filtered = _stored_row(
        db_session,
        303,
        markdown=_teaser_markdown(303),
        metadata={BODY_STATE_KEY: BODY_TEASER},
        status=ContentStatus.FILTERED_OUT,
    )
    # A teaser being summarized right now waits for the next run.
    busy = _stored_row(
        db_session,
        304,
        markdown=_teaser_markdown(304),
        metadata={BODY_STATE_KEY: BODY_TEASER},
        status=ContentStatus.PROCESSING,
    )

    response, reindexed = _run_authenticated(
        db_session,
        [
            _archive_entry(301),
            _archive_entry(302, audience="everyone"),
            _archive_entry(303),
            _archive_entry(304),
        ],
    )

    assert response.items_ingested == 1  # only the filtered-out teaser's body changed
    assert reindexed == ["303"]
    for row in (full, free, filtered, busy):
        db_session.refresh(row)
    assert full.markdown_content == full_markdown
    assert free.markdown_content == "short free note"
    assert "PAID-ENDING-303" in filtered.markdown_content
    assert filtered.status == ContentStatus.FILTERED_OUT
    assert busy.markdown_content == _teaser_markdown(304)
    assert busy.status == ContentStatus.PROCESSING
