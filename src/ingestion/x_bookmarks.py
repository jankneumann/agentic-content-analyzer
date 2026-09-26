"""Incremental ingestion of the operator's X bookmarks as Content rows.

Sits on :class:`~src.ingestion.x_bookmarks_client.XBookmarksClient` (the HTTP
layer) and owns what the client does not: which bookmarks are new, the Content
row each one becomes, and the envelope the durable workflow records.

* **Incremental walk**: pages are read newest-first and the walk stops after the
  first page whose every post is already stored as a bookmark, so a nightly run
  against unchanged bookmarks reads exactly one page. ``full=True`` walks every
  page (up to the client's page cap). ``max_items`` caps the rows a run writes.
* **Backfill cursor**: a walk cut short (rate limit, page cap, ``max_items``,
  upstream failure) keeps what it read and saves where it stopped as the
  settings override ``x_bookmarks.backfill_cursor``. The next run first walks
  the head as above and, once caught up, resumes from that cursor with the
  budget left, so older bookmarks are never stranded. Reaching the oldest
  bookmark clears it; ``full=True`` ignores it and resets it.
* **Fetch everything, then persist**: every page is read before the first row
  is written, so a missing or dead session (``credentials_missing`` /
  ``session_expired``, even on a later page) fails closed with zero rows and
  leaves the cursor untouched.
* **One document shape for X**: each post renders through the Grok search
  adapter's thread-to-markdown path (:func:`src.ingestion.xsearch.format_thread_markdown`)
  under ``source_id = "xpost:<post id>"``, and carries ``bookmarked: true`` in
  ``metadata_json``.
* **Linked articles**: every row written in a run gets a ``content_reference``
  to each outbound article link, committed with the row. With ``expand_links``
  on, each distinct link that is not stored yet is also submitted as its own
  canonical ``url`` ingestion operation (bounded per run by
  ``x_bookmarks_max_expanded_links``), handed to the worker's
  ``OperationService`` through :mod:`src.queue.follow_up_operations`; the post
  row stays the receipt. X self links, X media hosts, non-http(s) links, and
  feed or playlist URLs are never submitted.
* **Cross-source dedup**: ``contents`` is unique on ``(source_type,
  source_id)`` only, so a post Grok search already stored would otherwise get
  a second row. A bookmark whose ``xpost:<id>`` exists under another source is
  not inserted: the existing row is marked ``bookmarked`` and counts as known
  from then on. Grok search, in turn, skips any ``xpost:<id>`` that exists
  under any source (its level-1 check), so it never duplicates a bookmark.

Nothing here reads, logs, or returns a session cookie: the client resolves the
session per request and raises value-free errors.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Final, Protocol
from urllib.parse import urlsplit

from pydantic import ValidationError
from sqlalchemy import or_, select

from src.contracts.workflow_models import UrlIngestCommand
from src.ingestion.credential_failures import CredentialFailureError
from src.ingestion.gmail import ContentData
from src.ingestion.log_redaction import log_error_type
from src.ingestion.result import (
    IngestionError,
    IngestionResponse,
    IngestionWarning,
    derive_status,
)
from src.ingestion.url_router import RouteKind, classify_url as classify_route
from src.ingestion.x_bookmarks_client import (
    DEFAULT_MAX_PAGES,
    WalkStopReason,
    XBookmarksClient,
    XBookmarksClientError,
    XPost,
    is_x_self_link,
)
from src.ingestion.xsearch import (
    XPostContent,
    XQuotedPost,
    XThreadData,
    build_thread_metadata,
    format_thread_markdown,
    thread_title,
)
from src.models.content import Content, ContentSource, ContentStatus
from src.queue.follow_up_operations import FollowUpUnavailableError, submit_follow_up_ingestion
from src.services.reference_extractor import (
    ExtractedReference,
    ReferenceExtractor,
    classify_url as classify_reference_url,
)
from src.storage.database import get_db
from src.utils.content_hash import generate_markdown_hash
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = get_logger(__name__)

__all__ = [
    "BACKFILL_CURSOR_SETTING_KEY",
    "BOOKMARKED_KEY",
    "ITEM_CAP_REACHED",
    "LINK_EXPANSION_CAPPED",
    "LINK_EXPANSION_FAILED",
    "PAGE_CAP_REACHED",
    "RATE_LIMITED",
    "X_BOOKMARK_TAG",
    "BackfillCursorStore",
    "LinkSubmitter",
    "SettingsBackfillCursorStore",
    "XBookmarksIngestionService",
    "bookmark_content_data",
    "bookmark_thread",
    "expansion_skip_reason",
    "link_idempotency_key",
    "link_references",
    "link_skip_reason",
    "post_source_id",
]

COMMAND: Final = "ingest.x-bookmarks"
SOURCE: Final = "x_bookmarks"

BOOKMARKED_KEY: Final = "bookmarked"
"""``metadata_json`` flag on every row the operator bookmarked, whatever its source."""

QUOTED_TEXT_SUMMARY_CHARS: Final = 280
UNKNOWN_HANDLE: Final = "unknown"

# Envelope codes for a walk that ended before it reached known bookmarks.
RATE_LIMITED: Final = "rate_limited"
PAGE_CAP_REACHED: Final = "page_cap_reached"
ITEM_CAP_REACHED: Final = "item_cap_reached"
FETCH_ERROR: Final = "fetch_error"
PERSISTENCE_ERROR: Final = "persistence_error"
# Envelope codes for linked-article expansion; the bookmark rows are kept.
LINK_EXPANSION_CAPPED: Final = "link_expansion_capped"
LINK_EXPANSION_FAILED: Final = "link_expansion_failed"


def post_source_id(post_id: str) -> str:
    """The ``source_id`` of an X post, shared with Grok search (``xpost:<id>``)."""
    return f"xpost:{post_id}"


# -- document shape -----------------------------------------------------------


def _outbound_links(post: XPost) -> list[str]:
    """The post's outbound links, then its quoted post's, without duplicates."""
    quoted = post.quoted.outbound_urls if post.quoted is not None else ()
    return list(dict.fromkeys((*post.outbound_urls, *quoted)))


def bookmark_thread(post: XPost) -> XThreadData:
    """Map a bookmarked post onto the Grok search adapter's thread record."""
    quoted = post.quoted
    return XThreadData(
        root_post_id=post.post_id,
        thread_post_ids=[post.post_id],
        author_handle=post.author_handle or UNKNOWN_HANDLE,
        author_name=post.author_name or "",
        posts=[XPostContent(text=post.text, post_id=post.post_id)],
        posted_at=post.created_at,
        is_thread=False,
        thread_length=1,
        likes=post.like_count,
        retweets=post.repost_count,
        replies=post.reply_count,
        media_urls=list(post.media_urls),
        linked_urls=_outbound_links(post),
        hashtags=list(post.hashtags),
        mentions=list(post.mentions),
        source_url=post.url,
        quoted=(
            XQuotedPost(
                post_id=quoted.post_id,
                author_handle=quoted.author_handle,
                text=quoted.text,
                source_url=quoted.url,
            )
            if quoted is not None
            else None
        ),
    )


def _quoted_summary(quoted: XPost | None) -> dict[str, Any] | None:
    if quoted is None:
        return None
    return {
        "post_id": quoted.post_id,
        "url": quoted.url,
        "author_handle": quoted.author_handle,
        "author_name": quoted.author_name,
        "posted_at": quoted.created_at.isoformat() if quoted.created_at else None,
        "text": quoted.text[:QUOTED_TEXT_SUMMARY_CHARS],
        "outbound_urls": list(quoted.outbound_urls),
    }


def bookmark_metadata(post: XPost, thread: XThreadData) -> dict[str, Any]:
    """Grok search's X post metadata keys plus the bookmark-only fields."""
    return {
        **build_thread_metadata(thread),
        "author_id": post.author_id,
        "conversation_id": post.conversation_id,
        "in_reply_to_post_id": post.in_reply_to_post_id,
        "is_long_form": post.is_long_form,
        "quoted_post": _quoted_summary(post.quoted),
        BOOKMARKED_KEY: True,
    }


def bookmark_content_data(post: XPost) -> ContentData:
    """The Content row of one bookmarked post, in the Grok search document shape."""
    thread = bookmark_thread(post)
    markdown = format_thread_markdown(thread)
    title = thread_title(thread) if post.text.strip() else f"@{thread.author_handle}: X Post"
    return ContentData(
        source_type=ContentSource.X_BOOKMARKS,
        source_id=post_source_id(post.post_id),
        source_url=post.url,
        title=title,
        author=f"@{post.author_handle}" if post.author_handle else None,
        publication="X (Twitter)",
        published_date=post.created_at,
        markdown_content=markdown,
        links_json=list(thread.linked_urls) or None,
        metadata_json=bookmark_metadata(post, thread),
        content_hash=generate_markdown_hash(markdown),
    )


# -- linked articles --------------------------------------------------------------

X_BOOKMARK_TAG: Final = "x-bookmark"
"""Tag on every url operation submitted for a bookmark's linked article."""

LINK_IDEMPOTENCY_PREFIX: Final = "x_bookmarks.link:"
_MEDIA_HOSTS: Final = ("twimg.com",)  # pbs.twimg.com images, video.twimg.com videos
_HTTP_SCHEMES: Final = frozenset({"http", "https"})

# Why an outbound link is not submitted (``details.links_skipped_by_reason``).
SKIP_UNSUPPORTED: Final = "unsupported_link"
SKIP_SELF_LINK: Final = "x_self_link"
SKIP_MEDIA: Final = "x_media"
SKIP_COLLECTION: Final = "feed_or_playlist"
SKIP_ALREADY_STORED: Final = "already_stored"


def link_skip_reason(url: str) -> str | None:
    """Why a link is never an article reference: None for an http(s) link off X.

    X self links are already dropped by the client; the check here is defensive.
    """
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower().rstrip(".")
    except ValueError:
        return SKIP_UNSUPPORTED
    if parts.scheme.lower() not in _HTTP_SCHEMES or not host:
        return SKIP_UNSUPPORTED
    if is_x_self_link(url):
        return SKIP_SELF_LINK
    if any(host == base or host.endswith("." + base) for base in _MEDIA_HOSTS):
        return SKIP_MEDIA
    return None


def expansion_skip_reason(url: str) -> str | None:
    """Why a link is not submitted as a url operation: None for an article link.

    Beyond :func:`link_skip_reason`, a feed or YouTube playlist is a collection
    whose url route would ingest every item in it, so it is referenced only.
    """
    reason = link_skip_reason(url)
    if reason is not None:
        return reason
    if classify_route(url) in (RouteKind.RSS_FEED, RouteKind.YOUTUBE_PLAYLIST):
        return SKIP_COLLECTION
    return None


def link_references(post: XPost) -> list[ExtractedReference]:
    """One reference per distinct article link of the post (and its quoted post).

    arXiv, DOI and Semantic Scholar links become identifier references; any
    other link is a URL-only reference.
    """
    refs: dict[tuple[str | None, str | None, str | None], ExtractedReference] = {}
    for url in _outbound_links(post):
        if link_skip_reason(url) is not None:
            continue
        ref = classify_reference_url(url) or ExtractedReference(external_url=url)
        refs.setdefault((ref.external_id, ref.external_id_type, ref.external_url), ref)
    return list(refs.values())


def link_idempotency_key(url: str) -> str:
    """The url operation's idempotency key: one active operation per linked URL."""
    return LINK_IDEMPOTENCY_PREFIX + hashlib.sha256(url.encode("utf-8")).hexdigest()


class LinkSubmitter(Protocol):
    """Submit one canonical url ingestion operation; return its operation ID."""

    def __call__(self, command: UrlIngestCommand, *, idempotency_key: str) -> str: ...


def submit_link_operation(command: UrlIngestCommand, *, idempotency_key: str) -> str:
    """The production submitter: the worker's ``OperationService``, never inline work."""
    handle = submit_follow_up_ingestion(command, idempotency_key=idempotency_key)
    return str(handle.operation_id)


# -- backfill cursor ------------------------------------------------------------

BACKFILL_CURSOR_SETTING_KEY: Final = "x_bookmarks.backfill_cursor"
"""``settings_overrides`` key holding where an interrupted walk continues.

Beside ``x_bookmarks.graphql_query_id`` (the client's query ID cache). The
value is X's opaque ``cursor-bottom`` position token, not a credential.
"""

MAX_CURSOR_CHARS: Final = 4096


class BackfillCursorStore(Protocol):
    """Durable home of the backfill cursor. Must not raise."""

    def get(self) -> str | None: ...

    def set(self, cursor: str) -> None: ...

    def clear(self) -> None: ...


def _is_valid_cursor(value: object) -> bool:
    return (
        isinstance(value, str)
        and 0 < len(value) <= MAX_CURSOR_CHARS
        and value.isprintable()
        and not value.isspace()
    )


class SettingsBackfillCursorStore:
    """Keep the backfill cursor in ``settings_overrides`` (via :class:`SettingsService`).

    Fails open like the query ID cache: a database error is logged by type, a
    failed read means no backfill this run, a failed write means the next run
    re-reads from the previous position.
    """

    def __init__(
        self,
        *,
        key: str = BACKFILL_CURSOR_SETTING_KEY,
        db_factory: Callable[[], AbstractContextManager[Any]] | None = None,
    ) -> None:
        self._key = key
        self._db_factory = db_factory or (lambda: get_db())

    def get(self) -> str | None:
        from src.services.settings_service import SettingsService

        try:
            with self._db_factory() as db:
                value = SettingsService(db).get(self._key)
        except Exception as exc:
            logger.warning(f"x_bookmarks.backfill_cursor_unavailable ({log_error_type(exc)})")
            return None
        return value if _is_valid_cursor(value) else None

    def set(self, cursor: str) -> None:
        from src.services.settings_service import SettingsService

        if not _is_valid_cursor(cursor):
            return
        try:
            with self._db_factory() as db:
                SettingsService(db).set(
                    self._key,
                    cursor,
                    description="Where the X bookmarks backfill resumes (managed by ingestion)",
                )
        except Exception as exc:
            logger.warning(f"x_bookmarks.backfill_cursor_write_failed ({log_error_type(exc)})")

    def clear(self) -> None:
        from src.services.settings_service import SettingsService

        try:
            with self._db_factory() as db:
                SettingsService(db).delete(self._key)
        except Exception as exc:
            logger.warning(f"x_bookmarks.backfill_cursor_clear_failed ({log_error_type(exc)})")


# -- the service ----------------------------------------------------------------


@dataclass
class _Collected:
    """Posts to write, across every pass of one run."""

    posts: list[XPost] = field(default_factory=list)
    seen: set[str] = field(default_factory=set)
    known_skipped: int = 0


@dataclass
class _Pass:
    """One walk over the timeline: the head walk, or a backfill from the cursor."""

    start_cursor: str | None = field(default=None, repr=False)
    pages_fetched: int = 0
    stop_reason: WalkStopReason | None = None
    caught_up: bool = False
    """Stopped on a page whose every post is already stored."""
    reached_end: bool = False
    """Read to the oldest bookmark: nothing below this pass is unread."""
    item_cap_reached: bool = False
    rate_limit_reset_at: datetime | None = None
    fetch_error: IngestionError | None = None
    resume_cursor: str | None = field(default=None, repr=False)
    """Where the unread remainder starts; None when the pass left no gap."""

    @property
    def gap_code(self) -> str | None:
        """Why the pass left unread bookmarks behind, as an envelope code."""
        if self.resume_cursor is None:
            return None
        if self.stop_reason is WalkStopReason.RATE_LIMITED:
            return RATE_LIMITED
        if self.stop_reason is WalkStopReason.PAGE_CAP:
            return PAGE_CAP_REACHED
        if self.item_cap_reached:
            return ITEM_CAP_REACHED
        return FETCH_ERROR


@dataclass
class _PersistResult:
    written: int = 0
    linked: int = 0
    skipped: int = 0
    errors: list[IngestionError] = field(default_factory=list)
    written_posts: list[XPost] = field(default_factory=list)
    """Posts whose row this run inserted or rewrote, in walk order."""
    references_recorded: int = 0
    reference_failures: int = 0


@dataclass
class _Expansion:
    """What linked-article expansion did for the rows written in one run."""

    limit: int = 0
    submitted: int = 0
    capped: int = 0
    failed: int = 0
    unavailable: bool = False
    skipped: dict[str, int] = field(default_factory=dict)

    def skip(self, reason: str) -> None:
        self.skipped[reason] = self.skipped.get(reason, 0) + 1


class XBookmarksIngestionService:
    """Sync the operator's X bookmarks into ``contents``.

    A run is a head walk from the newest bookmark that stops at the first fully
    known page, then, when the head caught up and budget remains, a backfill
    walk from the saved cursor that resumes where an earlier partial walk
    stopped. ``client_factory`` builds the HTTP client and ``cursor_store``
    holds the backfill cursor; both are injectable for network-free tests.
    ``link_submitter`` submits linked-article url operations (the worker's
    ``OperationService`` by default) and ``max_expanded_links`` bounds them per
    run (``x_bookmarks_max_expanded_links`` by default).
    """

    def __init__(
        self,
        *,
        client_factory: Callable[[], XBookmarksClient] | None = None,
        cursor_store: BackfillCursorStore | None = None,
        max_pages: int = DEFAULT_MAX_PAGES,
        link_submitter: LinkSubmitter | None = None,
        max_expanded_links: int | None = None,
    ) -> None:
        self._client_factory = client_factory or XBookmarksClient
        self._cursor_store: BackfillCursorStore = cursor_store or SettingsBackfillCursorStore()
        self._max_pages = max_pages
        self._link_submitter: LinkSubmitter = link_submitter or submit_link_operation
        self._max_expanded_links = max_expanded_links

    def ingest(
        self,
        *,
        max_items: int | None = None,
        full: bool = False,
        expand_links: bool = False,
        force_reprocess: bool = False,
    ) -> IngestionResponse:
        """Walk, then persist, then move the cursor. Never raises for a session problem."""
        mode = "full" if full else "incremental"
        logger.info(f"x_bookmarks.sync_started: {mode} walk (max_items={max_items})")
        stored_cursor = self._cursor_store.get()
        collected = _Collected()
        backfill: _Pass | None = None
        try:
            with self._client_factory() as client:
                head = self._walk(
                    client,
                    collected,
                    start_cursor=None,
                    stop_on_known=not full,
                    max_items=max_items,
                    max_pages=self._max_pages,
                    force_reprocess=force_reprocess,
                )
                if (
                    not full
                    and stored_cursor is not None
                    and head.caught_up
                    and (max_items is None or len(collected.posts) < max_items)
                    and head.pages_fetched < self._max_pages
                ):
                    backfill = self._walk(
                        client,
                        collected,
                        start_cursor=stored_cursor,
                        stop_on_known=False,
                        max_items=max_items,
                        max_pages=self._max_pages - head.pages_fetched,
                        force_reprocess=force_reprocess,
                    )
        except CredentialFailureError as exc:
            # Nothing is written, not even the cursor: the next run starts over.
            logger.error(f"x_bookmarks.{exc.code}: ingestion failed closed with zero rows")
            return IngestionResponse(
                command=COMMAND,
                source=SOURCE,
                status="error",
                errors=[exc.to_ingestion_error()],
                details={"full": full, "expand_links": expand_links},
            )

        persisted = self._persist(collected.posts, force_reprocess=force_reprocess)
        backfill_pending = self._move_cursor(stored_cursor, head, backfill, full=full)
        expansion = self._expand_links(persisted.written_posts, enabled=expand_links)
        return self._response(
            collected,
            head,
            backfill,
            persisted,
            expansion,
            backfill_pending=backfill_pending,
            full=full,
            expand_links=expand_links,
        )

    # -- walk ------------------------------------------------------------------

    def _walk(
        self,
        client: XBookmarksClient,
        collected: _Collected,
        *,
        start_cursor: str | None,
        stop_on_known: bool,
        max_items: int | None,
        max_pages: int,
        force_reprocess: bool,
    ) -> _Pass:
        """One pass: read pages until caught up, capped, or exhausted. Writes nothing.

        Credential failures propagate (the caller fails closed); any other
        client error ends the pass and keeps the pages already read.
        """
        result = _Pass(start_cursor=start_cursor)
        page_known: frozenset[str] = frozenset()
        page_has_more = False
        overflowed = False
        request_cursor = start_cursor  # the cursor that fetched the current page
        next_cursor = start_cursor  # the cursor the next request uses
        overflow_cursor: str | None = None

        # Called by the walk after this loop has consumed each page, so it sees
        # that page's known IDs and the posts collected so far.
        def stop_when(page_ids: tuple[str, ...]) -> bool:
            if stop_on_known and page_ids and all(post_id in page_known for post_id in page_ids):
                result.caught_up = True
                return True
            if max_items is not None and len(collected.posts) >= max_items:
                result.item_cap_reached = overflowed or page_has_more
                result.reached_end = not result.item_cap_reached
                return True
            return False

        walk = client.iter_pages(
            stop_when=stop_when, max_pages=max_pages, start_cursor=start_cursor
        )
        try:
            for page in walk:
                request_cursor, next_cursor = next_cursor, page.next_cursor
                page_known = self._known_post_ids(page.post_ids)
                page_has_more = page.next_cursor is not None
                for post in page.posts:
                    if post.post_id in collected.seen:
                        continue
                    collected.seen.add(post.post_id)
                    if post.post_id in page_known and not force_reprocess:
                        collected.known_skipped += 1
                    elif max_items is not None and len(collected.posts) >= max_items:
                        if not overflowed:
                            overflowed, overflow_cursor = True, request_cursor
                    else:
                        collected.posts.append(post)
        except XBookmarksClientError as exc:
            logger.warning(
                f"x_bookmarks.walk_failed ({log_error_type(exc)}) after "
                f"{walk.pages_fetched} page(s); keeping what was read"
            )
            result.fetch_error = IngestionError(code=FETCH_ERROR, message=str(exc))
        result.pages_fetched = walk.pages_fetched
        result.stop_reason = walk.stop_reason
        result.rate_limit_reset_at = walk.rate_limit_reset_at
        if result.stop_reason is WalkStopReason.EXHAUSTED and result.fetch_error is None:
            result.reached_end = True
        if result.item_cap_reached:
            # Re-read the page that overflowed (its taken posts are then known);
            # a cap reached exactly at a page end continues on the next page.
            result.resume_cursor = overflow_cursor if overflowed else next_cursor
        elif result.fetch_error is not None or result.stop_reason in (
            WalkStopReason.RATE_LIMITED,
            WalkStopReason.PAGE_CAP,
        ):
            result.resume_cursor = next_cursor
        return result

    @staticmethod
    def _known_post_ids(post_ids: Sequence[str]) -> frozenset[str]:
        """Post IDs already stored as bookmarks: X bookmark rows, or flagged rows.

        Reads columns only, so the lookup never counts as touching a row.
        """
        if not post_ids:
            return frozenset()
        source_ids = [post_source_id(post_id) for post_id in post_ids]
        with get_db() as db:
            stored = db.execute(
                select(Content.source_id).where(
                    Content.source_id.in_(source_ids),
                    or_(
                        Content.source_type == ContentSource.X_BOOKMARKS,
                        Content.metadata_json.contains({BOOKMARKED_KEY: True}),
                    ),
                )
            ).scalars()
            return frozenset(source_id.removeprefix("xpost:") for source_id in stored)

    def _move_cursor(
        self,
        stored: str | None,
        head: _Pass,
        backfill: _Pass | None,
        *,
        full: bool,
    ) -> bool:
        """Save, advance, or clear the backfill cursor; True while a gap remains.

        A gap the head walk left is newer than any saved one, and a backfill
        from it walks down through everything older, so it replaces the saved
        cursor. Reaching the oldest bookmark clears it. A full walk that read
        at least one page resets it from its own outcome.
        """
        if full and head.pages_fetched == 0:
            return stored is not None  # nothing was read: nothing to reset from
        target: str | None
        if head.resume_cursor is not None:
            target = head.resume_cursor
        elif full or head.reached_end:
            target = None
        elif backfill is not None and backfill.resume_cursor is not None:
            target = backfill.resume_cursor
        elif backfill is not None and backfill.reached_end:
            target = None
        else:
            return stored is not None
        if target is None:
            if stored is not None:
                self._cursor_store.clear()
                logger.info("x_bookmarks.backfill_complete: reached the oldest bookmark")
            return False
        if target != stored:
            self._cursor_store.set(target)
            logger.info("x_bookmarks.backfill_cursor_saved: the next run resumes the walk")
        return True

    # -- persistence -----------------------------------------------------------

    def _persist(self, posts: Sequence[XPost], *, force_reprocess: bool) -> _PersistResult:
        result = _PersistResult()
        if not posts:
            return result
        with get_db() as db:
            source_ids = [post_source_id(post.post_id) for post in posts]
            existing: dict[str, list[Content]] = {}
            for row in db.query(Content).filter(Content.source_id.in_(source_ids)).all():
                existing.setdefault(row.source_id, []).append(row)

            for post in posts:
                data = bookmark_content_data(post)
                try:
                    with db.begin_nested():
                        row = self._persist_one(
                            db,
                            data,
                            existing.get(data.source_id, []),
                            force_reprocess=force_reprocess,
                            result=result,
                        )
                except Exception as exc:
                    logger.warning(
                        f"x_bookmarks.persist_failed: {data.source_id} ({log_error_type(exc)})"
                    )
                    result.errors.append(
                        IngestionError(
                            code=PERSISTENCE_ERROR,
                            message=f"{data.source_id} could not be stored",
                            url=data.source_url,
                        )
                    )
                    continue
                if row is not None:
                    result.written_posts.append(post)
                    self._record_references(db, row, post, result)
            db.commit()
        return result

    @staticmethod
    def _record_references(db: Session, row: Content, post: XPost, result: _PersistResult) -> None:
        """Reference each article link from the written row, in its own savepoint.

        The references commit with the row; a failure drops only the references
        (the row is kept) and is reported as a warning.
        """
        refs = link_references(post)
        if not refs:
            return
        try:
            with db.begin_nested():
                result.references_recorded += ReferenceExtractor().store_references(
                    row.id, refs, db, commit=False
                )
        except Exception as exc:
            logger.warning(
                f"x_bookmarks.references_failed: {row.source_id} ({log_error_type(exc)})"
            )
            result.reference_failures += 1

    @staticmethod
    def _persist_one(
        db: Session,
        data: ContentData,
        rows: list[Content],
        *,
        force_reprocess: bool,
        result: _PersistResult,
    ) -> Content | None:
        """Write one post; return its row when inserted or rewritten, else None."""
        bookmark_row = next(
            (row for row in rows if row.source_type == ContentSource.X_BOOKMARKS), None
        )
        if bookmark_row is not None:
            if not force_reprocess:
                result.skipped += 1
                return None
            _apply(bookmark_row, data)
            bookmark_row.status = ContentStatus.PENDING
            bookmark_row.error_message = None
            db.flush()
            result.written += 1
            return bookmark_row

        if rows:
            # The post is already stored under another source (Grok search):
            # never a second row. Flag it so later walks count it as known.
            other = rows[0]
            if not (other.metadata_json or {}).get(BOOKMARKED_KEY):
                other.metadata_json = {**(other.metadata_json or {}), BOOKMARKED_KEY: True}
                db.flush()
            logger.info(
                f"x_bookmarks.linked_existing: {data.source_id} is stored as "
                f"{other.source_type}; marked bookmarked"
            )
            result.linked += 1
            return None

        content = Content(
            source_type=data.source_type,
            source_id=data.source_id,
            status=ContentStatus.PENDING,
            ingested_at=datetime.now(UTC).replace(tzinfo=None),
        )
        _apply(content, data)
        db.add(content)
        db.flush()
        result.written += 1
        return content

    # -- link expansion (ri-13) ------------------------------------------------

    def _expand_links(self, posts: Sequence[XPost], *, enabled: bool) -> _Expansion:
        """Submit one url operation per distinct article link of the written posts.

        ``enabled`` is already resolved against the source's ``expand_links``.
        Only rows written in this run are expanded, so a rerun over known
        bookmarks submits nothing. A link already stored as content, or seen
        earlier in the run, is not submitted again, and the idempotency key
        collapses a submission onto a still-active one for the same URL. The
        first failed submission stops the rest: the rows are committed, and the
        unsubmitted links keep their references.
        """
        result = _Expansion()
        if not enabled or not posts:
            return result
        result.limit = self._expansion_limit()

        candidates: dict[str, XPost] = {}
        seen: set[str] = set()
        for post in posts:
            for url in _outbound_links(post):
                if url in seen:
                    continue
                seen.add(url)
                reason = expansion_skip_reason(url)
                if reason is not None:
                    result.skip(reason)
                    continue
                candidates[url] = post
        for url in self._stored_urls(list(candidates)):
            del candidates[url]
            result.skip(SKIP_ALREADY_STORED)

        pending = list(candidates.items())
        result.capped = max(0, len(pending) - result.limit)
        for index, (url, post) in enumerate(pending[: result.limit]):
            try:
                command = UrlIngestCommand(
                    url=url,
                    tags=[X_BOOKMARK_TAG],
                    notes=f"Linked from the X bookmark {post.url}",
                )
            except ValidationError:
                result.skip(SKIP_UNSUPPORTED)
                continue
            try:
                self._link_submitter(command, idempotency_key=link_idempotency_key(url))
            except FollowUpUnavailableError:
                result.unavailable = True
            except Exception as exc:
                logger.warning(f"x_bookmarks.link_submit_failed ({log_error_type(exc)})")
            else:
                result.submitted += 1
                continue
            result.failed = min(result.limit, len(pending)) - index
            break

        skipped = sum(result.skipped.values())
        logger.info(
            f"x_bookmarks.expand_links: {result.submitted} url operation(s) submitted, "
            f"{skipped} link(s) skipped, {result.capped} over the limit of {result.limit}, "
            f"{result.failed} not submitted"
        )
        return result

    def _expansion_limit(self) -> int:
        if self._max_expanded_links is not None:
            return max(0, self._max_expanded_links)
        from src.config.settings import get_settings

        return get_settings().x_bookmarks_max_expanded_links

    @staticmethod
    def _stored_urls(urls: Sequence[str]) -> list[str]:
        """The URLs already stored as content (the url adapter's own dedup key)."""
        if not urls:
            return []
        with get_db() as db:
            stored = set(
                db.execute(select(Content.source_url).where(Content.source_url.in_(urls))).scalars()
            )
        return [url for url in urls if url in stored]

    # -- envelope ------------------------------------------------------------------

    @staticmethod
    def _response(
        collected: _Collected,
        head: _Pass,
        backfill: _Pass | None,
        persisted: _PersistResult,
        expansion: _Expansion,
        *,
        backfill_pending: bool,
        full: bool,
        expand_links: bool,
    ) -> IngestionResponse:
        errors: list[IngestionError] = []
        warnings: list[IngestionWarning] = []
        for walk_pass, label in ((head, "walk"), (backfill, "backfill")):
            if walk_pass is None:
                continue
            if walk_pass.fetch_error is not None:
                errors.append(walk_pass.fetch_error)
            if (
                walk_pass is head
                and head.stop_reason is WalkStopReason.RATE_LIMITED
                and head.pages_fetched == 0
            ):
                errors.append(
                    IngestionError(
                        code=RATE_LIMITED,
                        message="X rate-limited the bookmarks walk before the first page",
                    )
                )
                continue
            code = walk_pass.gap_code
            if code is None or code == FETCH_ERROR:
                continue
            warnings.append(
                IngestionWarning(code=code, message=_gap_message(code, label, walk_pass))
            )
        errors.extend(persisted.errors)
        warnings.extend(_link_warnings(persisted, expansion))

        items_ingested = persisted.written
        items_failed = len(persisted.errors)
        pages = head.pages_fetched + (backfill.pages_fetched if backfill else 0)
        logger.info(
            f"x_bookmarks.sync_finished: {items_ingested} written, {persisted.linked} linked, "
            f"{collected.known_skipped + persisted.skipped} known, {pages} page(s), "
            f"head={head.stop_reason}, backfill={backfill.stop_reason if backfill else None}, "
            f"backfill_pending={backfill_pending}"
        )
        reset_at = (backfill.rate_limit_reset_at if backfill else None) or (
            head.rate_limit_reset_at
        )
        return IngestionResponse(
            command=COMMAND,
            source=SOURCE,
            status=derive_status(
                items_ingested=items_ingested, items_failed=items_failed, errors=errors
            ),
            items_ingested=items_ingested,
            items_skipped=collected.known_skipped + persisted.skipped + persisted.linked,
            items_failed=items_failed,
            errors=errors,
            warnings=warnings,
            details={
                "full": full,
                "expand_links": expand_links,
                "pages_fetched": pages,
                "walk_stop_reason": head.stop_reason.value if head.stop_reason else None,
                "backfill_pages_fetched": backfill.pages_fetched if backfill else 0,
                "backfill_stop_reason": (
                    backfill.stop_reason.value if backfill and backfill.stop_reason else None
                ),
                "backfill_pending": backfill_pending,
                "rate_limit_reset_at": reset_at.isoformat() if reset_at else None,
                "linked_existing": persisted.linked,
                "references_recorded": persisted.references_recorded,
                "links_submitted": expansion.submitted,
                "links_skipped": sum(expansion.skipped.values()),
                "links_skipped_by_reason": dict(sorted(expansion.skipped.items())),
                "links_capped": expansion.capped,
                "links_failed": expansion.failed,
                "max_expanded_links": expansion.limit,
            },
        )


def _link_warnings(persisted: _PersistResult, expansion: _Expansion) -> list[IngestionWarning]:
    """Counts only: never a URL, so a warning cannot carry a link's query string."""
    warnings: list[IngestionWarning] = []
    if persisted.reference_failures:
        warnings.append(
            IngestionWarning(
                code=PERSISTENCE_ERROR,
                message=(
                    f"The links of {persisted.reference_failures} bookmark(s) could not be "
                    "recorded as references; the bookmarks were stored"
                ),
            )
        )
    if expansion.capped:
        warnings.append(
            IngestionWarning(
                code=LINK_EXPANSION_CAPPED,
                message=(
                    f"{expansion.capped} linked article(s) exceeded the limit of "
                    f"{expansion.limit} per run and were not submitted; their references "
                    "are kept"
                ),
            )
        )
    if expansion.failed:
        reason = (
            "link expansion needs the durable ingestion worker"
            if expansion.unavailable
            else "the url operation could not be submitted"
        )
        warnings.append(
            IngestionWarning(
                code=LINK_EXPANSION_FAILED,
                message=(
                    f"{expansion.failed} linked article(s) were not submitted ({reason}); "
                    "the bookmarks and their references were stored"
                ),
            )
        )
    return warnings


def _gap_message(code: str, label: str, walk_pass: _Pass) -> str:
    reason = {
        RATE_LIMITED: f"X rate-limited the {label} after {walk_pass.pages_fetched} page(s)",
        PAGE_CAP_REACHED: f"The {label} stopped at the run's page cap",
        ITEM_CAP_REACHED: f"The {label} reached max_items",
    }[code]
    return f"{reason}; older bookmarks remain unread and the next run resumes the backfill"


def _apply(content: Content, data: ContentData) -> None:
    content.source_url = data.source_url
    content.title = data.title[:1000]
    content.author = data.author
    content.publication = data.publication
    content.published_date = data.published_date
    content.markdown_content = data.markdown_content
    content.links_json = data.links_json
    content.metadata_json = data.metadata_json
    content.content_hash = data.content_hash
