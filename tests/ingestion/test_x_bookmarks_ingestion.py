"""Incremental X bookmarks ingestion into Content rows (ri-12).

Network-free: X is an ``httpx.MockTransport`` that serves a fake bookmarks
timeline built from ``tests/fixtures/x_bookmarks_graphql.py`` and paginates it
by cursor like X's web app. Rows land in the real test database through the
rolled-back ``db_session``. Every cookie value is a sentinel that an autouse
fixture keeps out of logs and stdout/stderr.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest
from sqlalchemy import func, select

from src.config.credentials import X_AUTH_TOKEN, X_CT0, CredentialProvider
from src.config.sources import XBookmarksSource, configured_source_public_key
from src.contracts.workflow_models import UrlIngestCommand
from src.ingestion.credential_failures import CREDENTIALS_MISSING, SESSION_EXPIRED
from src.ingestion.service import IngestionService
from src.ingestion.x_bookmarks import (
    BACKFILL_CURSOR_SETTING_KEY,
    BOOKMARKED_KEY,
    ITEM_CAP_REACHED,
    LINK_EXPANSION_CAPPED,
    LINK_EXPANSION_FAILED,
    PAGE_CAP_REACHED,
    PERSISTENCE_ERROR,
    RATE_LIMITED,
    X_BOOKMARK_TAG,
    SettingsBackfillCursorStore,
    XBookmarksIngestionService,
    bookmark_content_data,
    bookmark_thread,
    expansion_skip_reason,
    link_idempotency_key,
    link_references,
)
from src.ingestion.x_bookmarks_client import (
    GRAPHQL_BASE_URL,
    XBookmarksClient,
    XPost,
    parse_tweet_result,
)
from src.ingestion.xsearch import (
    GrokXContentIngestionService,
    XPostContent,
    XThreadData,
    format_thread_markdown,
    thread_to_content_data,
)
from src.models.content import Content, ContentSource, ContentStatus
from src.models.content_reference import ContentReference
from src.models.jobs import JobStatus, OperationType
from src.queue.workflow_handlers import build_workflow_handler_registry
from tests.fixtures import x_bookmarks_graphql as fx

AUTH_TOKEN = "authSENTINELtoken0123456789abcdef0123"
CT0 = "ct0SENTINELvalue0123456789abcdef"
SENTINELS = (AUTH_TOKEN, CT0)
QUERY_ID = "CachedQueryId_1234"
NOW = 1_800_000_000.0
PAGE_SIZE = 2
SECRET = "x-bookmarks-ingestion-test-secret-0123456789"
SOURCE = XBookmarksSource(name="x-bookmarks", enabled=True, max_entries=100, expand_links=False)


# -- fakes ------------------------------------------------------------------------


class FakeBao:
    def __init__(self, values: dict[str, str]) -> None:
        self.cache = dict(values)

    def read(self) -> dict[str, str]:
        return dict(self.cache)

    def refresh(self, *, min_interval_s: float = 0.0) -> bool:
        return False


def make_provider(values: dict[str, str]) -> CredentialProvider:
    settings = SimpleNamespace(substack_session_cookie=None, x_auth_token=None, x_ct0=None)
    bao = FakeBao(values)
    return CredentialProvider(
        settings_factory=lambda: settings, bao_reader=bao.read, bao_refresher=bao.refresh
    )


class QueryIdStore:
    def get(self) -> str:
        return QUERY_ID

    def set(self, query_id: str) -> None:
        raise AssertionError("the cached query ID is valid")

    def clear(self) -> None:
        raise AssertionError("the cached query ID is valid")


class FakeTimeline:
    """X's bookmarks timeline, newest first, paginated by a position cursor.

    A cursor names the last post of the page it closes (``after:<id>``), so it
    stays valid when new bookmarks are added on top, like X's own cursors.

    ``overrides`` maps a 1-based GraphQL request number to a canned response,
    to inject a 429, a 401, or a 5xx on that request.
    """

    def __init__(self, post_ids: list[str]) -> None:
        self.post_ids = list(post_ids)
        self.results: dict[str, dict[str, Any]] = {}
        self.overrides: dict[int, Callable[[], httpx.Response]] = {}
        self.graphql_calls = 0
        self.cursors: list[str | None] = []

    def bookmark(self, *post_ids: str) -> None:
        """Bookmark posts on another device: they go to the top."""
        self.post_ids[:0] = list(post_ids)

    def result(self, post_id: str) -> dict[str, Any]:
        return self.results.get(post_id) or fx.tweet_result(post_id, f"Post {post_id} on agents")

    def handler(self, request: httpx.Request) -> httpx.Response:
        if not str(request.url).startswith(GRAPHQL_BASE_URL):
            raise AssertionError(f"unexpected request to {request.url.host}")
        self.graphql_calls += 1
        override = self.overrides.get(self.graphql_calls)
        if override is not None:
            return override()
        variables = json.loads(request.url.params["variables"])
        self.cursors.append(variables.get("cursor"))
        cursor = variables.get("cursor")
        offset = self.post_ids.index(cursor.removeprefix("after:")) + 1 if cursor else 0
        count = int(variables["count"])
        window = self.post_ids[offset : offset + count]
        more = offset + count < len(self.post_ids)
        return httpx.Response(
            200,
            json=fx.bookmarks_response(
                [self.result(post_id) for post_id in window],
                bottom_cursor=f"after:{window[-1]}" if more else None,
            ),
        )


@pytest.fixture(autouse=True)
def _no_sentinel_leaks(caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str]):
    caplog.set_level(logging.DEBUG)
    yield
    captured = capsys.readouterr()
    logged = "\n".join(
        record.getMessage() for when in ("setup", "call") for record in caplog.get_records(when)
    )
    for sentinel in SENTINELS:
        assert sentinel not in logged
        assert sentinel not in captured.out
        assert sentinel not in captured.err


@pytest.fixture
def credentials() -> dict[str, str]:
    return {X_AUTH_TOKEN: AUTH_TOKEN, X_CT0: CT0}


@pytest.fixture
def timeline() -> FakeTimeline:
    return FakeTimeline(["105", "104", "103", "102", "101"])


@pytest.fixture
def client_factory(
    timeline: FakeTimeline, credentials: dict[str, str]
) -> Iterator[Callable[[], XBookmarksClient]]:
    clients: list[XBookmarksClient] = []

    def build() -> XBookmarksClient:
        client = XBookmarksClient(
            credentials=make_provider(credentials),
            query_id_store=QueryIdStore(),
            http=httpx.Client(transport=httpx.MockTransport(timeline.handler)),
            sink_factory=lambda _clock: None,
            page_size=PAGE_SIZE,
            page_delay_s=0.0,
            sleep=lambda _seconds: None,
            clock=lambda: NOW,
        )
        clients.append(client)
        return client

    yield build
    for client in clients:
        client.close()


@pytest.fixture
def use_db(db_session: Any) -> Iterator[Any]:
    @contextmanager
    def get_db() -> Iterator[Any]:
        yield db_session

    with (
        patch("src.ingestion.x_bookmarks.get_db", get_db),
        patch("src.ingestion.xsearch.get_db", get_db),
    ):
        yield db_session


@pytest.fixture
def make_service(
    client_factory: Callable[[], XBookmarksClient],
) -> Callable[..., XBookmarksIngestionService]:
    def build(**overrides: Any) -> XBookmarksIngestionService:
        options: dict[str, Any] = {"client_factory": client_factory}
        options.update(overrides)
        return XBookmarksIngestionService(**options)

    return build


def bookmark_rows(db: Any) -> list[Content]:
    return (
        db.query(Content)
        .filter(Content.source_type == ContentSource.X_BOOKMARKS)
        .order_by(Content.source_id)
        .all()
    )


def post_rows(db: Any, post_id: str) -> list[Content]:
    return db.query(Content).filter(Content.source_id == f"xpost:{post_id}").all()


def count_contents(db: Any) -> int:
    return db.execute(select(func.count()).select_from(Content)).scalar_one()


def cursor_store() -> SettingsBackfillCursorStore:
    """The production store, reading the test database through the patched get_db."""
    return SettingsBackfillCursorStore()


def rerun(timeline: FakeTimeline) -> None:
    timeline.graphql_calls = 0
    timeline.cursors.clear()


# -- incremental sync ------------------------------------------------------------------


def test_first_run_walks_every_page_and_ingests_each_bookmark_once(
    use_db, make_service, timeline
) -> None:
    timeline.results["104"] = fx.tweet_result("104", "Duplicate across pages")
    # X can repeat a post across page boundaries; it is still one row.
    timeline.post_ids = ["105", "104", "104", "103", "102", "101"]

    response = make_service().ingest()

    assert (response.status, response.items_ingested, response.items_failed) == ("ok", 5, 0)
    assert timeline.graphql_calls == 3
    assert response.details["walk_stop_reason"] == "exhausted"
    rows = bookmark_rows(use_db)
    assert [row.source_id for row in rows] == [f"xpost:{i}" for i in range(101, 106)]
    assert all(row.status == ContentStatus.PENDING for row in rows)
    assert all(row.metadata_json[BOOKMARKED_KEY] is True for row in rows)
    assert cursor_store().get() is None


def test_second_run_on_unchanged_bookmarks_reads_one_page_and_ingests_nothing(
    use_db, make_service, timeline
) -> None:
    make_service().ingest()
    timeline.graphql_calls = 0
    before = count_contents(use_db)

    response = make_service().ingest()

    assert timeline.graphql_calls == 1
    assert (response.status, response.items_ingested) == ("ok", 0)
    assert response.items_skipped == PAGE_SIZE
    assert response.details["walk_stop_reason"] == "stop_when"
    assert response.warnings == []
    assert count_contents(use_db) == before


def test_new_bookmarks_on_top_ingest_only_the_new_ones(use_db, make_service, timeline) -> None:
    make_service().ingest()
    timeline.bookmark("107", "106")
    timeline.graphql_calls = 0

    response = make_service().ingest()

    # Page one is all new, page two is all known: the walk stops there.
    assert timeline.graphql_calls == 2
    assert response.items_ingested == 2
    assert {row.source_id for row in bookmark_rows(use_db)} >= {"xpost:106", "xpost:107"}
    assert len(bookmark_rows(use_db)) == 7


def test_full_walks_every_page_and_writes_nothing_new(use_db, make_service, timeline) -> None:
    make_service().ingest()
    timeline.graphql_calls = 0

    response = make_service().ingest(full=True)

    assert timeline.graphql_calls == 3
    assert (response.items_ingested, response.items_skipped) == (0, 5)
    assert response.details["walk_stop_reason"] == "exhausted"
    assert len(bookmark_rows(use_db)) == 5


def test_max_items_caps_rows_and_warns_that_older_bookmarks_were_not_read(
    use_db, make_service, timeline
) -> None:
    response = make_service().ingest(max_items=3)

    assert response.items_ingested == 3
    assert [row.source_id for row in bookmark_rows(use_db)] == [
        "xpost:103",
        "xpost:104",
        "xpost:105",
    ]
    assert [warning.code for warning in response.warnings] == [ITEM_CAP_REACHED]
    assert "next run resumes the backfill" in response.warnings[0].message
    assert timeline.graphql_calls == 2
    # Page two overflowed after one post: the backfill re-reads that page.
    assert cursor_store().get() == "after:104"
    assert response.details["backfill_pending"] is True


def test_max_items_exactly_matching_the_timeline_does_not_warn(
    use_db, make_service, timeline
) -> None:
    timeline.post_ids = ["102", "101"]

    response = make_service().ingest(max_items=2)

    assert (response.items_ingested, response.warnings) == (2, [])
    assert cursor_store().get() is None


def test_page_cap_persists_what_was_read_with_a_warning(use_db, make_service, timeline) -> None:
    response = make_service(max_pages=1).ingest()

    assert (response.status, response.items_ingested) == ("ok", 2)
    assert [warning.code for warning in response.warnings] == [PAGE_CAP_REACHED]
    assert cursor_store().get() == "after:104"


def test_force_reprocess_resets_existing_rows_in_place(use_db, make_service, timeline) -> None:
    make_service().ingest()
    for row in bookmark_rows(use_db):
        row.status = ContentStatus.COMPLETED
    use_db.flush()

    response = make_service().ingest(force_reprocess=True)

    # Incremental: only the first (all-known) page is walked and reset.
    assert response.items_ingested == PAGE_SIZE
    statuses = {row.source_id: row.status for row in bookmark_rows(use_db)}
    assert statuses["xpost:105"] == statuses["xpost:104"] == ContentStatus.PENDING
    assert statuses["xpost:101"] == ContentStatus.COMPLETED
    assert len(statuses) == 5


# -- backfill cursor ----------------------------------------------------------------------


def test_capped_runs_backfill_older_batches_until_the_oldest_clears_the_cursor(
    use_db, make_service, timeline
) -> None:
    first = make_service().ingest(max_items=2)
    assert first.items_ingested == 2
    assert timeline.cursors == [None]
    assert cursor_store().get() == "after:104"

    # The head page is known, so the walk stops there and the backfill resumes.
    rerun(timeline)
    second = make_service().ingest(max_items=2)
    assert timeline.cursors == [None, "after:104"]
    assert second.items_ingested == 2
    assert second.details["backfill_pages_fetched"] == 1
    assert cursor_store().get() == "after:102"

    rerun(timeline)
    third = make_service().ingest(max_items=2)
    assert timeline.cursors == [None, "after:102"]
    assert (third.items_ingested, third.warnings) == (1, [])
    assert third.details["backfill_stop_reason"] == "exhausted"
    assert cursor_store().get() is None
    assert len(bookmark_rows(use_db)) == 5

    # Nothing left to backfill: the head walk alone, one page.
    rerun(timeline)
    fourth = make_service().ingest(max_items=2)
    assert (timeline.cursors, fourth.items_ingested) == ([None], 0)


def test_new_bookmarks_are_read_before_the_backfill_resumes(use_db, make_service, timeline) -> None:
    make_service().ingest(max_items=2)
    timeline.bookmark("107", "106")
    rerun(timeline)

    response = make_service().ingest()

    assert timeline.cursors == [None, "after:106", "after:104", "after:102"]
    assert response.items_ingested == 5
    assert len(bookmark_rows(use_db)) == 7
    assert cursor_store().get() is None


def test_a_newer_gap_replaces_the_saved_cursor_and_the_backfill_covers_both(
    use_db, make_service, timeline
) -> None:
    make_service().ingest(max_items=2)
    timeline.bookmark("107", "106")
    rerun(timeline)

    # The head alone spends the budget: its own gap supersedes the older one.
    capped = make_service().ingest(max_items=2)
    assert (timeline.cursors, capped.items_ingested) == ([None], 2)
    assert cursor_store().get() == "after:106"

    rerun(timeline)
    response = make_service().ingest()
    assert timeline.cursors == [None, "after:106", "after:104", "after:102"]
    assert response.items_ingested == 3
    assert len(bookmark_rows(use_db)) == 7
    assert cursor_store().get() is None


def test_full_ignores_and_resets_the_cursor(use_db, make_service, timeline) -> None:
    cursor_store().set("after:103")

    response = make_service().ingest(full=True)

    assert timeline.cursors == [None, "after:104", "after:102"]
    assert response.items_ingested == 5
    assert cursor_store().get() is None


def test_a_failed_session_leaves_the_cursor_untouched(use_db, make_service, timeline) -> None:
    make_service().ingest(max_items=2)
    timeline.overrides[2] = lambda: httpx.Response(401, json={"errors": [{"code": 32}]})
    rerun(timeline)

    response = make_service().ingest()

    assert [error.code for error in response.errors] == [SESSION_EXPIRED]
    assert cursor_store().get() == "after:104"
    assert len(bookmark_rows(use_db)) == 2


def test_cursor_store_ignores_invalid_values(use_db) -> None:
    from src.services.settings_service import SettingsService

    SettingsService(use_db).set(BACKFILL_CURSOR_SETTING_KEY, "x" * 5000)

    assert cursor_store().get() is None
    cursor_store().set("")
    cursor_store().clear()
    assert cursor_store().get() is None


# -- failures -------------------------------------------------------------------------


def test_expired_session_fails_closed_with_zero_rows_and_no_db_writes(
    use_db, make_service, timeline
) -> None:
    timeline.overrides[1] = lambda: httpx.Response(401, json={"errors": [{"code": 32}]})
    before = count_contents(use_db)

    with patch.object(XBookmarksIngestionService, "_persist") as persist:
        response = make_service().ingest()

    persist.assert_not_called()
    assert (response.status, response.items_ingested) == ("error", 0)
    assert [error.code for error in response.errors] == [SESSION_EXPIRED]
    assert "aca auth session x" in response.errors[0].message
    assert count_contents(use_db) == before


def test_session_expiring_on_a_later_page_still_persists_nothing(
    use_db, make_service, timeline
) -> None:
    timeline.overrides[2] = lambda: httpx.Response(401, json={"errors": [{"code": 32}]})

    response = make_service().ingest()

    assert [error.code for error in response.errors] == [SESSION_EXPIRED]
    assert response.items_ingested == 0
    assert bookmark_rows(use_db) == []
    assert cursor_store().get() is None


def test_missing_credentials_fail_closed_before_any_request(
    use_db, make_service, timeline, credentials
) -> None:
    credentials.clear()

    response = make_service().ingest()

    assert [error.code for error in response.errors] == [CREDENTIALS_MISSING]
    assert timeline.graphql_calls == 0
    assert bookmark_rows(use_db) == []


def test_rate_limit_mid_walk_persists_the_pages_read_and_warns(
    use_db, make_service, timeline
) -> None:
    timeline.overrides[2] = lambda: httpx.Response(
        429, json={}, headers={"x-rate-limit-reset": str(int(NOW) + 3600)}
    )

    response = make_service().ingest()

    assert (response.status, response.items_ingested) == ("ok", 2)
    assert [warning.code for warning in response.warnings] == [RATE_LIMITED]
    assert response.details["rate_limit_reset_at"] is not None
    assert [row.source_id for row in bookmark_rows(use_db)] == ["xpost:104", "xpost:105"]
    assert cursor_store().get() == "after:104"

    # The next run catches up on the head, then backfills what was missed.
    timeline.overrides.clear()
    timeline.graphql_calls = 0
    timeline.cursors.clear()
    again = make_service().ingest()
    assert again.items_ingested == 3
    assert timeline.cursors == [None, "after:104", "after:102"]
    assert cursor_store().get() is None


def test_rate_limit_before_the_first_page_is_an_error(use_db, make_service, timeline) -> None:
    timeline.overrides[1] = lambda: httpx.Response(
        429, json={}, headers={"x-rate-limit-reset": str(int(NOW) + 3600)}
    )

    response = make_service().ingest()

    assert (response.status, [e.code for e in response.errors]) == ("error", [RATE_LIMITED])


def test_upstream_failure_mid_walk_keeps_what_was_read(use_db, make_service, timeline) -> None:
    timeline.overrides[2] = lambda: httpx.Response(503, text="over capacity")

    response = make_service().ingest()

    assert response.status == "partial"
    assert response.items_ingested == 2
    assert [error.code for error in response.errors] == ["fetch_error"]
    assert cursor_store().get() == "after:104"


# -- cross-source dedup ------------------------------------------------------------------


def _xsearch_row(db: Any, post_id: str) -> Content:
    thread = XThreadData(
        root_post_id=post_id,
        thread_post_ids=[post_id],
        author_handle="alice",
        posts=[XPostContent(text="Found by Grok", post_id=post_id)],
    )
    data = thread_to_content_data(thread, "prompt", 1)
    row = Content(
        source_type=ContentSource.XSEARCH,
        source_id=data.source_id,
        title=data.title,
        markdown_content=data.markdown_content,
        content_hash=data.content_hash,
        metadata_json=data.metadata_json,
        status=ContentStatus.COMPLETED,
    )
    db.add(row)
    db.flush()
    return row


def test_post_grok_search_already_stored_is_flagged_not_duplicated(
    use_db, make_service, timeline
) -> None:
    existing = _xsearch_row(use_db, "104")

    response = make_service().ingest()

    assert response.items_ingested == 4
    assert response.details["linked_existing"] == 1
    (row,) = post_rows(use_db, "104")
    assert row.id == existing.id
    assert row.source_type == ContentSource.XSEARCH
    assert row.metadata_json[BOOKMARKED_KEY] is True
    assert row.metadata_json["search_query"] == "prompt"
    assert row.status == ContentStatus.COMPLETED

    # The flagged row now counts as known: the next run stops on page one.
    timeline.graphql_calls = 0
    again = make_service().ingest()
    assert (timeline.graphql_calls, again.items_ingested) == (1, 0)


def test_grok_search_does_not_duplicate_a_bookmarked_post(use_db, make_service) -> None:
    make_service().ingest()
    service = GrokXContentIngestionService(api_key="test-key")
    grok_answer = json.dumps(
        [{"post_id": "103", "author_handle": "alice", "text": "Surfaced by Grok"}]
    )

    with patch.object(service.client, "search", return_value=(grok_answer, 1)):
        response = service.ingest_threads(prompt="agents")

    assert (response.items_ingested, response.items_skipped) == (0, 1)
    (row,) = post_rows(use_db, "103")
    assert row.source_type == ContentSource.X_BOOKMARKS


def test_grok_search_force_reprocess_resets_a_bookmark_row_instead_of_duplicating(
    use_db, make_service
) -> None:
    make_service().ingest()
    (bookmark,) = post_rows(use_db, "103")
    bookmark.status = ContentStatus.COMPLETED
    markdown = bookmark.markdown_content
    use_db.flush()
    service = GrokXContentIngestionService(api_key="test-key")
    grok_answer = json.dumps(
        [{"post_id": "103", "author_handle": "alice", "text": "Surfaced by Grok"}]
    )

    with patch.object(service.client, "search", return_value=(grok_answer, 1)):
        response = service.ingest_threads(prompt="agents", force_reprocess=True)

    assert response.items_ingested == 1
    (row,) = post_rows(use_db, "103")
    assert row.id == bookmark.id
    assert row.source_type == ContentSource.X_BOOKMARKS
    assert row.status == ContentStatus.PENDING
    assert row.markdown_content == markdown


# -- document shape ---------------------------------------------------------------------


def _rich_post() -> Any:
    quoted = fx.tweet_result(
        "900",
        "Quoted thoughts https://t.co/q",
        user=fx.user_result("bob", "Bob", "2002"),
        urls=[fx.url_entity("https://t.co/q", "https://example.org/paper")],
    )
    result = fx.tweet_result(
        "1850000000000000001",
        "Read this https://t.co/a",
        urls=[fx.url_entity("https://t.co/a", "https://example.com/article")],
        media=[fx.photo_media()],
        quoted=quoted,
        hashtags=["ai"],
        mentions=["bob"],
    )
    post = parse_tweet_result(result)
    assert post is not None
    return post


def test_a_bookmark_renders_through_the_grok_search_markdown_path() -> None:
    post = _rich_post()

    data = bookmark_content_data(post)

    assert data.markdown_content == format_thread_markdown(bookmark_thread(post))
    assert data.source_type == ContentSource.X_BOOKMARKS
    assert data.source_id == "xpost:1850000000000000001"
    assert data.source_url == "https://x.com/alice/status/1850000000000000001"
    assert data.title == "@alice: Read this https://example.com/article"
    assert data.author == "@alice"
    assert data.published_date == datetime(2018, 10, 10, 20, 19, 24, tzinfo=UTC)
    assert data.markdown_content.startswith("# @alice - Read this")
    assert "## Quoted Post" in data.markdown_content
    assert "> Quoted thoughts https://example.org/paper" in data.markdown_content
    assert "- [https://pbs.twimg.com/media/PHOTO1.jpg]" in data.markdown_content
    assert data.links_json == ["https://example.com/article", "https://example.org/paper"]
    metadata = data.metadata_json or {}
    assert metadata[BOOKMARKED_KEY] is True
    assert (metadata["author_handle"], metadata["likes"], metadata["retweets"]) == (
        "alice",
        42,
        7,
    )
    assert metadata["replies"] == 4
    assert metadata["media_urls"] == ["https://pbs.twimg.com/media/PHOTO1.jpg"]
    assert metadata["linked_urls"] == data.links_json
    assert metadata["quoted_post"]["post_id"] == "900"
    assert metadata["quoted_post"]["author_handle"] == "bob"
    assert "search_query" not in metadata


def test_grok_search_rendering_is_unchanged_by_the_shared_path() -> None:
    thread = XThreadData(
        root_post_id="1850000000000000001",
        thread_post_ids=["1850000000000000001", "1850000000000000002"],
        author_handle="alice",
        author_name="Alice Example",
        posts=[
            XPostContent(
                text="First post about agents https://example.com/a",
                post_id="1850000000000000001",
            ),
            XPostContent(text="Second post", post_id="1850000000000000002"),
        ],
        posted_at=datetime(2026, 9, 20, 8, 30, tzinfo=UTC),
        is_thread=True,
        thread_length=2,
        likes=1234,
        retweets=56,
        replies=7,
        media_urls=["https://pbs.twimg.com/media/A.jpg"],
        linked_urls=["https://example.com/a"],
        hashtags=["ai"],
        mentions=["bob"],
        source_url="https://x.com/alice/status/1850000000000000001",
    )

    data = thread_to_content_data(thread, "prompt", 3)

    # Pinned from the adapter before the renderer was shared.
    assert data.content_hash == "782d93c3253ed4808ec6cae884f7b10c5064eabef7b211f262de7362abf17902"
    assert data.title == "@alice: First post about agents https://example.com/a"
    assert list(data.metadata_json or {}) == [
        "root_post_id",
        "thread_post_ids",
        "author_handle",
        "author_name",
        "posted_at",
        "likes",
        "retweets",
        "replies",
        "is_thread",
        "thread_length",
        "media_urls",
        "linked_urls",
        "hashtags",
        "mentions",
        "search_query",
        "tool_calls_made",
    ]
    solo = XThreadData(
        root_post_id="42",
        thread_post_ids=["42"],
        author_handle="bob",
        posts=[XPostContent(text="Solo post", post_id="42")],
    )
    assert format_thread_markdown(solo) == (
        "# @bob - Solo post\n\n**Posted**: Unknown\n\n## Content\n\nSolo post\n"
    )


# -- hooks -------------------------------------------------------------------------------


def test_outbound_links_are_referenced_explicitly_without_the_inline_hook(
    use_db, make_service, timeline
) -> None:
    timeline.post_ids = ["1850000000000000001"]
    timeline.results["1850000000000000001"] = fx.tweet_result(
        "1850000000000000001",
        "Read this https://t.co/a",
        urls=[fx.url_entity("https://t.co/a", "https://example.com/article")],
    )

    with patch("src.services.reference_hook.on_content_ingested") as hook:
        response = make_service().ingest()

    (row,) = bookmark_rows(use_db)
    assert response.items_ingested == 1
    assert row.links_json == ["https://example.com/article"]
    hook.assert_not_called()
    (reference,) = (
        use_db.query(ContentReference).filter(ContentReference.source_content_id == row.id).all()
    )
    assert reference.external_url == "https://example.com/article"
    assert reference.external_id is None


def test_orchestrator_runs_the_filter_hook_and_defers_expand_links_to_the_source(
    use_db, client_factory, timeline, caplog
) -> None:
    from src.ingestion import orchestrator

    config = SimpleNamespace(
        get_x_bookmarks_sources=lambda: [SOURCE.model_copy(update={"expand_links": True})]
    )
    started = datetime.now(UTC).replace(tzinfo=None)
    with (
        patch("src.ingestion.x_bookmarks.XBookmarksClient", client_factory),
        patch("src.config.sources.load_sources_config", return_value=config),
        patch("src.ingestion.filter_hook.apply_filter_to_recent") as filter_hook,
    ):
        response = orchestrator.ingest_x_bookmarks(max_items=2)

    assert response.items_ingested == 2
    assert response.details["expand_links"] is True
    filter_hook.assert_called_once()
    since = filter_hook.call_args.kwargs["since"]
    assert started <= since
    assert all(row.ingested_at >= since for row in bookmark_rows(use_db))
    (outcome,) = response.source_outcomes
    assert outcome.status == "ok"
    assert outcome.items_ingested == 2
    assert "x_bookmarks.expand_links" in caplog.text


# -- durable path -------------------------------------------------------------------------


class _Operations:
    def __init__(self) -> None:
        self.attached: list[dict[str, Any]] = []

    async def attach_result(self, _operation_id: int, result: dict[str, Any]) -> None:
        self.attached.append(result)

    async def update_progress(self, *_args: object) -> None:
        return None

    async def checkpoint_cancellation(self, *_args: object, **_kwargs: object) -> None:
        return None

    async def get(self, operation_id: int) -> SimpleNamespace:
        return SimpleNamespace(
            operation_id=operation_id, status=JobStatus.IN_PROGRESS, resource=None
        )


@pytest.mark.asyncio
async def test_durable_operation_records_rows_content_ids_and_the_source_outcome(
    use_db, client_factory
) -> None:
    operations = _Operations()
    registry = build_workflow_handler_registry(
        operation_service=operations,
        ingestion_service=IngestionService(configured_source_key_secret=SECRET),
    )
    payload = {
        "kind": "x_bookmarks",
        "max_items": 4,
        "configured_sources": [SOURCE.model_dump(mode="json")],
    }

    with (
        patch("src.ingestion.x_bookmarks.XBookmarksClient", client_factory),
        patch("src.ingestion.filter_hook.apply_filter_to_recent", MagicMock()),
    ):
        await registry.dispatch(OperationType.INGESTION_EXECUTE, 41, payload)

    (result,) = operations.attached
    rows = bookmark_rows(use_db)
    assert len(rows) == 4
    assert result["command_key"] == "x_bookmarks"
    assert result["emitted_sources"] == ["x_bookmarks"]
    assert (result["status"], result["outcome"]) == ("ok", "success")
    assert result["items_ingested"] == 4
    assert result["content_ids"] == sorted(row.id for row in rows)
    assert result["warnings"][0]["code"] == ITEM_CAP_REACHED
    assert result["source_outcomes_omitted"] == 0
    (outcome,) = result["source_outcomes"]
    assert outcome["source_key"] == configured_source_public_key(SOURCE, secret=SECRET)
    assert (outcome["status"], outcome["items_ingested"]) == ("ok", 4)


@pytest.mark.asyncio
async def test_durable_operation_fails_closed_on_an_expired_session(
    use_db, client_factory, timeline
) -> None:
    from src.queue.workflow_handlers import WorkflowExecutionError

    timeline.overrides[1] = lambda: httpx.Response(401, json={"errors": [{"code": 32}]})
    operations = _Operations()
    registry = build_workflow_handler_registry(
        operation_service=operations,
        ingestion_service=IngestionService(configured_source_key_secret=SECRET),
    )
    payload = {"kind": "x_bookmarks", "configured_sources": [SOURCE.model_dump(mode="json")]}

    with (
        patch("src.ingestion.x_bookmarks.XBookmarksClient", client_factory),
        patch("src.ingestion.filter_hook.apply_filter_to_recent", MagicMock()),
        pytest.raises(WorkflowExecutionError, match="Ingestion 'x_bookmarks' failed"),
    ):
        await registry.dispatch(OperationType.INGESTION_EXECUTE, 42, payload)

    (result,) = operations.attached
    assert result["command_key"] == "x_bookmarks"
    assert (result["status"], result["outcome"]) == ("error", "failed")
    assert (result["items_ingested"], result["content_ids"]) == (0, [])
    assert [error["code"] for error in result["errors"]] == [SESSION_EXPIRED]
    (outcome,) = result["source_outcomes"]
    assert outcome["status"] == "error"
    assert bookmark_rows(use_db) == []


# -- linked articles (ri-13) ----------------------------------------------------------

ARTICLE = "https://example.com/article"


class RecordingSubmitter:
    """The link submitter's test double: records each url command it is handed."""

    def __init__(self, *, fail_on: int | None = None) -> None:
        self.commands: list[UrlIngestCommand] = []
        self.keys: list[str] = []
        self.fail_on = fail_on

    def __call__(self, command: UrlIngestCommand, *, idempotency_key: str) -> str:
        if self.fail_on is not None and len(self.commands) + 1 >= self.fail_on:
            raise OSError("queue unavailable")
        self.commands.append(command)
        self.keys.append(idempotency_key)
        return str(len(self.commands))

    @property
    def urls(self) -> list[str]:
        return [str(command.url) for command in self.commands]


def links_post(timeline: FakeTimeline, post_id: str, *urls: str) -> None:
    timeline.results[post_id] = fx.tweet_result(
        post_id,
        "Worth reading " + " ".join(f"https://t.co/{i}" for i in range(len(urls))),
        urls=[fx.url_entity(f"https://t.co/{i}", url) for i, url in enumerate(urls)],
    )


def references_of(db: Any, row: Content) -> list[ContentReference]:
    return (
        db.query(ContentReference)
        .filter(ContentReference.source_content_id == row.id)
        .order_by(ContentReference.external_url)
        .all()
    )


def test_expand_links_submits_one_url_operation_and_references_the_article(
    use_db, make_service, timeline
) -> None:
    timeline.post_ids = ["201"]
    links_post(timeline, "201", ARTICLE)
    submitter = RecordingSubmitter()

    with patch("src.services.reference_hook.on_content_ingested") as hook:
        response = make_service(link_submitter=submitter).ingest(expand_links=True)

    (row,) = bookmark_rows(use_db)
    (command,) = submitter.commands
    assert str(command.url) == ARTICLE
    assert command.tags == [X_BOOKMARK_TAG]
    assert command.notes == f"Linked from the X bookmark {row.source_url}"
    assert (command.routing_mode, command.force_reprocess) == ("auto", False)
    assert submitter.keys == [link_idempotency_key(ARTICLE)]
    (reference,) = references_of(use_db, row)
    assert (reference.external_url, reference.external_id) == (ARTICLE, None)
    assert reference.resolution_status == "unresolved"
    hook.assert_not_called()
    assert (response.status, response.warnings) == ("ok", [])
    assert response.details["links_submitted"] == 1
    assert response.details["references_recorded"] == 1
    # The post row stays the receipt: no article row is written inline.
    assert use_db.query(Content).filter(Content.source_url == ARTICLE).all() == []


def test_expand_links_off_submits_nothing_but_still_records_the_reference(
    use_db, make_service, timeline
) -> None:
    timeline.post_ids = ["201"]
    links_post(timeline, "201", ARTICLE)
    submitter = RecordingSubmitter()

    response = make_service(link_submitter=submitter).ingest(expand_links=False)

    (row,) = bookmark_rows(use_db)
    assert submitter.commands == []
    assert [ref.external_url for ref in references_of(use_db, row)] == [ARTICLE]
    assert response.details["links_submitted"] == 0
    assert response.details["references_recorded"] == 1


def test_a_link_shared_by_two_bookmarks_is_submitted_once_and_referenced_twice(
    use_db, make_service, timeline
) -> None:
    timeline.post_ids = ["202", "201"]
    links_post(timeline, "202", ARTICLE)
    links_post(timeline, "201", ARTICLE, "https://example.org/other")
    submitter = RecordingSubmitter()

    response = make_service(link_submitter=submitter).ingest(expand_links=True)

    assert submitter.urls == [ARTICLE, "https://example.org/other"]
    rows = bookmark_rows(use_db)
    assert [len(references_of(use_db, row)) for row in rows] == [2, 1]
    assert response.details["links_submitted"] == 2
    assert response.details["references_recorded"] == 3


def test_a_rerun_over_known_bookmarks_submits_nothing(use_db, make_service, timeline) -> None:
    timeline.post_ids = ["201"]
    links_post(timeline, "201", ARTICLE)
    make_service(link_submitter=RecordingSubmitter()).ingest(expand_links=True)
    submitter = RecordingSubmitter()

    response = make_service(link_submitter=submitter).ingest(expand_links=True)

    assert submitter.commands == []
    assert response.items_ingested == 0
    assert response.details["links_submitted"] == 0
    (row,) = bookmark_rows(use_db)
    assert len(references_of(use_db, row)) == 1


def test_a_link_already_stored_as_content_is_not_submitted(use_db, make_service, timeline) -> None:
    use_db.add(
        Content(
            source_type=ContentSource.WEBPAGE,
            source_id=f"webpage:{ARTICLE}",
            source_url=ARTICLE,
            title="Already saved",
            markdown_content="",
            content_hash="0" * 64,
            status=ContentStatus.COMPLETED,
        )
    )
    use_db.flush()
    timeline.post_ids = ["201"]
    links_post(timeline, "201", ARTICLE)
    submitter = RecordingSubmitter()

    response = make_service(link_submitter=submitter).ingest(expand_links=True)

    assert submitter.commands == []
    assert response.details["links_skipped_by_reason"] == {"already_stored": 1}
    (row,) = bookmark_rows(use_db)
    assert [ref.external_url for ref in references_of(use_db, row)] == [ARTICLE]


def test_media_and_feed_links_are_never_submitted(use_db, make_service, timeline) -> None:
    timeline.post_ids = ["201"]
    links_post(
        timeline,
        "201",
        "https://pbs.twimg.com/media/PHOTO9.jpg",
        "https://video.twimg.com/ext_tw_video/9/pu/vid/high.mp4",
        "https://blog.example.com/feed.xml",
        "https://arxiv.org/abs/2401.00001v2",
        ARTICLE,
    )
    submitter = RecordingSubmitter()

    response = make_service(link_submitter=submitter).ingest(expand_links=True)

    assert submitter.urls == ["https://arxiv.org/abs/2401.00001v2", ARTICLE]
    assert response.details["links_skipped_by_reason"] == {"feed_or_playlist": 1, "x_media": 2}
    (row,) = bookmark_rows(use_db)
    refs = {
        (ref.external_id_type, ref.external_id, ref.external_url)
        for ref in references_of(use_db, row)
    }
    # The feed is referenced (it is a link off X), media is not.
    assert refs == {
        ("arxiv", "2401.00001", "https://arxiv.org/abs/2401.00001"),
        (None, None, "https://blog.example.com/feed.xml"),
        (None, None, ARTICLE),
    }


def test_self_and_non_http_links_are_skipped_defensively(use_db, make_service) -> None:
    # The client already drops these; a post built directly still never submits them.
    post = XPost(
        post_id="301",
        url="https://x.com/alice/status/301",
        text="self links only",
        outbound_urls=(
            "https://x.com/bob/status/1",
            "https://mobile.twitter.com/bob",
            "https://t.co/abc",
            "ftp://files.example.com/paper.pdf",
            ARTICLE,
        ),
    )
    submitter = RecordingSubmitter()

    expansion = make_service(link_submitter=submitter, max_expanded_links=10)._expand_links(
        [post], enabled=True
    )

    assert submitter.urls == [ARTICLE]
    assert expansion.skipped == {"x_self_link": 3, "unsupported_link": 1}
    assert [ref.external_url for ref in link_references(post)] == [ARTICLE]


@pytest.mark.parametrize(
    ("url", "reason"),
    [
        ("https://example.com/a", None),
        ("http://example.com/a", None),
        ("https://x.com/a/status/1", "x_self_link"),
        ("https://twitter.com/a", "x_self_link"),
        ("https://t.co/x", "x_self_link"),
        ("https://pbs.twimg.com/media/a.jpg", "x_media"),
        ("https://video.twimg.com/v.mp4", "x_media"),
        ("mailto:a@example.com", "unsupported_link"),
        ("javascript:alert(1)", "unsupported_link"),
        ("https://", "unsupported_link"),
        ("https://www.youtube.com/playlist?list=PL123", "feed_or_playlist"),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", None),
    ],
)
def test_expansion_skip_reasons(url: str, reason: str | None) -> None:
    assert expansion_skip_reason(url) == reason


def test_a_failed_submission_keeps_the_rows_and_warns(use_db, make_service, timeline) -> None:
    timeline.post_ids = ["203", "202", "201"]
    for index, post_id in enumerate(timeline.post_ids):
        links_post(timeline, post_id, f"https://example.com/{index}")
    submitter = RecordingSubmitter(fail_on=2)

    response = make_service(link_submitter=submitter).ingest(expand_links=True)

    assert (response.status, response.items_ingested) == ("ok", 3)
    assert submitter.urls == ["https://example.com/0"]
    assert [warning.code for warning in response.warnings] == [LINK_EXPANSION_FAILED]
    assert "2 linked article(s) were not submitted" in response.warnings[0].message
    assert "example.com" not in response.warnings[0].message
    assert (response.details["links_submitted"], response.details["links_failed"]) == (1, 2)
    assert all(len(references_of(use_db, row)) == 1 for row in bookmark_rows(use_db))


def test_expansion_outside_the_worker_warns_instead_of_running_inline(
    use_db, make_service, timeline
) -> None:
    timeline.post_ids = ["201"]
    links_post(timeline, "201", ARTICLE)

    response = make_service().ingest(expand_links=True)

    assert (response.status, response.items_ingested) == ("ok", 1)
    (warning,) = response.warnings
    assert warning.code == LINK_EXPANSION_FAILED
    assert "durable ingestion worker" in warning.message
    assert use_db.query(Content).filter(Content.source_url == ARTICLE).all() == []


def test_submissions_per_run_are_capped(use_db, make_service, timeline) -> None:
    timeline.post_ids = ["203", "202", "201"]
    for index, post_id in enumerate(timeline.post_ids):
        links_post(timeline, post_id, f"https://example.com/{index}")
    submitter = RecordingSubmitter()

    response = make_service(link_submitter=submitter, max_expanded_links=2).ingest(
        expand_links=True
    )

    assert submitter.urls == ["https://example.com/0", "https://example.com/1"]
    assert [warning.code for warning in response.warnings] == [LINK_EXPANSION_CAPPED]
    assert (response.details["links_capped"], response.details["max_expanded_links"]) == (1, 2)
    assert response.details["references_recorded"] == 3


def test_the_cap_defaults_to_the_setting() -> None:
    from src.config.settings import Settings

    assert Settings(_env_file=None).x_bookmarks_max_expanded_links == 50


def test_a_reference_failure_keeps_the_row_and_warns(use_db, make_service, timeline) -> None:
    timeline.post_ids = ["201"]
    links_post(timeline, "201", ARTICLE)

    with patch(
        "src.services.reference_extractor.ReferenceExtractor.store_references",
        side_effect=RuntimeError("boom"),
    ):
        response = make_service(link_submitter=RecordingSubmitter()).ingest()

    (row,) = bookmark_rows(use_db)
    assert references_of(use_db, row) == []
    assert (response.status, response.items_ingested) == ("ok", 1)
    assert [warning.code for warning in response.warnings] == [PERSISTENCE_ERROR]


def test_link_expansion_codes_are_public_diagnostics() -> None:
    from src.ingestion.result_sanitizer import (
        SAFE_INGESTION_DIAGNOSTIC_CODES,
        sanitize_ingestion_metadata,
    )

    assert {LINK_EXPANSION_CAPPED, LINK_EXPANSION_FAILED} <= SAFE_INGESTION_DIAGNOSTIC_CODES
    projection = sanitize_ingestion_metadata(
        details={
            "links_submitted": 2,
            "links_skipped": 1,
            "references_recorded": 3,
            "links_skipped_by_reason": {"x_media": 1},
        }
    )
    assert projection["details"] == {
        "links_skipped": 1,
        "links_submitted": 2,
        "references_recorded": 3,
    }


class _SubmittingOperations(_Operations):
    """The workflow handler's operations double, plus canonical ``submit``."""

    def __init__(self) -> None:
        super().__init__()
        self.submitted: list[tuple[OperationType, dict[str, Any], str | None]] = []

    async def submit(
        self,
        operation_type: OperationType,
        normalized_input: dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> SimpleNamespace:
        self.submitted.append((operation_type, normalized_input, idempotency_key))
        return SimpleNamespace(operation_id=str(900 + len(self.submitted)))


@pytest.mark.asyncio
async def test_durable_operation_submits_linked_articles_through_the_worker_operations(
    use_db, client_factory, timeline
) -> None:
    timeline.post_ids = ["201"]
    links_post(timeline, "201", ARTICLE)
    operations = _SubmittingOperations()
    registry = build_workflow_handler_registry(
        operation_service=operations,
        ingestion_service=IngestionService(configured_source_key_secret=SECRET),
    )
    source = SOURCE.model_copy(update={"expand_links": True})
    payload = {"kind": "x_bookmarks", "configured_sources": [source.model_dump(mode="json")]}

    with (
        patch("src.ingestion.x_bookmarks.XBookmarksClient", client_factory),
        patch("src.ingestion.filter_hook.apply_filter_to_recent", MagicMock()),
    ):
        await registry.dispatch(OperationType.INGESTION_EXECUTE, 43, payload)

    (row,) = bookmark_rows(use_db)
    assert operations.submitted == [
        (
            OperationType.INGESTION_EXECUTE,
            {
                "kind": "url",
                "url": ARTICLE,
                "tags": [X_BOOKMARK_TAG],
                "notes": f"Linked from the X bookmark {row.source_url}",
                "routing_mode": "auto",
                "force_reprocess": False,
            },
            link_idempotency_key(ARTICLE),
        )
    ]
    (result,) = operations.attached
    assert (result["status"], result["warnings"]) == ("ok", [])
    assert result["details"] == {
        "links_skipped": 0,
        "links_submitted": 1,
        "references_recorded": 1,
    }


@pytest.mark.asyncio
async def test_real_operation_service_queues_one_url_operation_per_link(
    use_db, make_service, timeline, test_engine
) -> None:
    import asyncio

    import asyncpg

    from src.queue.follow_up_operations import bind_follow_up_operations
    from src.services.operation_service import OperationService

    timeline.post_ids = ["202", "201"]
    links_post(timeline, "202", ARTICLE)
    links_post(timeline, "201", ARTICLE)
    key = link_idempotency_key(ARTICLE)
    conn = await asyncpg.connect(test_engine.url.render_as_string(hide_password=False))
    try:
        with bind_follow_up_operations(OperationService(connection=conn)):
            first = await asyncio.to_thread(make_service().ingest, expand_links=True)
            # Rewriting the rows expands them again: the key collapses onto the
            # still-queued operation instead of queueing a second one.
            again = await asyncio.to_thread(
                make_service().ingest, expand_links=True, force_reprocess=True, full=True
            )
        jobs = await conn.fetch(
            "SELECT entrypoint, status, payload FROM pgqueuer_jobs WHERE idempotency_key = $1",
            key,
        )
    finally:
        await conn.execute("DELETE FROM pgqueuer_jobs WHERE idempotency_key = $1", key)
        await conn.close()

    assert (first.details["links_submitted"], first.warnings) == (1, [])
    assert again.items_ingested == 2
    assert again.details["links_submitted"] == 1
    (job,) = jobs
    assert (job["entrypoint"], job["status"]) == ("ingestion.execute", "queued")
    payload = json.loads(job["payload"])
    assert payload["operation_type"] == "ingestion.execute"
    assert payload["input"]["kind"] == "url"
    assert payload["input"]["url"] == ARTICLE
