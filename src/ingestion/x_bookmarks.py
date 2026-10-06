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
  budget left, so older bookmarks are never stranded. A post whose row failed
  to store pins the cursor to the page it came from (the newest such page), so
  the next run reads it again instead of stopping above it. Reaching the
  oldest bookmark clears it; ``full=True`` ignores it and resets it.
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
* **Link retry (ri-20)**: each bookmark reference carries an expansion state
  (``pending``, ``submitted``, ``skipped``, ``failed``; NULL for references of
  other sources). Every expand-links run writes each handled link's outcome to
  every reference of that link, then spends the budget it has left on older
  ``pending``/``failed`` references, oldest first, at most
  ``MAX_LINK_EXPANSION_ATTEMPTS`` times per link. ``retry_links=True`` runs only
  that retry pass: no timeline walk, no X session, no cursor movement.
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
from sqlalchemy import Select, func, or_, select, update

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
from src.models.content_reference import ContentReference, ExpansionState
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
    "MAX_LINK_EXPANSION_ATTEMPTS",
    "PAGE_CAP_REACHED",
    "RATE_LIMITED",
    "RETRY_NOTES",
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
    "reference_url",
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
MAX_LINK_EXPANSION_ATTEMPTS: Final = 3
"""Attempts (failed submissions; ``submitted`` is terminal) after which a link is not retried."""
_MAX_ATTEMPTS_STORED: Final = 100  # the column's CHECK ceiling
RETRY_NOTES: Final = "Retried link from an X bookmark"
_RETRYABLE_STATES: Final = (ExpansionState.PENDING.value, ExpansionState.FAILED.value)
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


def reference_url(url: str) -> str:
    """The ``external_url`` of the reference :func:`link_references` records for a link.

    An arXiv, DOI or Semantic Scholar link is stored under its canonical URL,
    so the outcome of submitting a link is written to the references of this
    URL, not of the one seen in the post.
    """
    ref = classify_reference_url(url) or ExtractedReference(external_url=url)
    return ref.external_url or url


def initial_expansion_state(url: str) -> ExpansionState:
    """A new bookmark reference's state: ``skipped`` for a link never submitted."""
    return ExpansionState.SKIPPED if expansion_skip_reason(url) else ExpansionState.PENDING


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
    page_cursors: dict[str, str | None] = field(default_factory=dict, repr=False)
    """The cursor that fetched each collected post's page (None: the newest page)."""

    def retry_cursor(self, failed_post_ids: Sequence[str]) -> str | None:
        """The newest page cursor holding a post that failed to store.

        A failure on the newest page needs none: the next head walk reads that
        page, and the unstored post keeps it from counting as caught up.
        """
        failed = set(failed_post_ids)
        for post in self.posts:
            if post.post_id in failed and self.page_cursors.get(post.post_id) is not None:
                return self.page_cursors[post.post_id]
        return None


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
    failed_post_ids: list[str] = field(default_factory=list)
    written_posts: list[XPost] = field(default_factory=list)
    """Posts whose row this run inserted or rewrote, in walk order."""
    references_recorded: int = 0
    reference_failures: int = 0


@dataclass
class _Expansion:
    """What linked-article expansion did in one run: new posts, then the retry pass."""

    limit: int = 0
    submitted: int = 0
    """Links of the posts written in this run that were submitted."""
    retried: int = 0
    """Older pending/failed links the retry pass submitted."""
    capped: int = 0
    failed: int = 0
    unavailable: bool = False
    pending: int = 0
    """Distinct links still pending or failed (under the attempt limit) after the run."""
    skipped: dict[str, int] = field(default_factory=dict)
    handled: set[str] = field(default_factory=set, repr=False)
    """Reference URLs whose outcome this run recorded: the retry pass skips them."""

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
        retry_links: bool = False,
    ) -> IngestionResponse:
        """Walk, then persist, then move the cursor. Never raises for a session problem.

        ``retry_links`` skips all of that and only retries the stored backlog
        of pending/failed links with the full link budget (see :meth:`_retry_only`).
        """
        if retry_links:
            return self._retry_only(full=full)
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
                details={"full": full, "expand_links": expand_links, "retry_links": False},
            )

        persisted = self._persist(collected.posts, force_reprocess=force_reprocess)
        backfill_pending = self._move_cursor(
            stored_cursor,
            head,
            backfill,
            full=full,
            retry_cursor=collected.retry_cursor(persisted.failed_post_ids),
        )
        expansion = self._expand_links(persisted.written_posts, enabled=expand_links)
        expansion.pending = self._pending_link_count()
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

    def _retry_only(self, *, full: bool) -> IngestionResponse:
        """Retry the stored backlog only: no client, no X request, no cursor write.

        Expansion is on regardless of the source's ``expand_links``, and the
        whole link budget goes to the oldest pending/failed links.
        """
        logger.info("x_bookmarks.retry_links: retrying stored links without a timeline walk")
        expansion = _Expansion(limit=self._expansion_limit())
        self._retry_links(expansion, budget=expansion.limit)
        expansion.pending = self._pending_link_count()
        self._log_expansion(expansion)
        return self._response(
            _Collected(),
            _Pass(),
            None,
            _PersistResult(),
            expansion,
            backfill_pending=self._cursor_store.get() is not None,
            full=full,
            expand_links=True,
            retry_links=True,
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
                        collected.page_cursors[post.post_id] = request_cursor
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
        retry_cursor: str | None = None,
    ) -> bool:
        """Save, advance, or clear the backfill cursor; True while a gap remains.

        A gap the head walk left is newer than any saved one, and a backfill
        from it walks down through everything older, so it replaces the saved
        cursor. Reaching the oldest bookmark clears it. A full walk that read
        at least one page resets it from its own outcome.

        ``retry_cursor`` (the newest page holding a post that failed to store)
        wins over all of these: it is newer than any gap this run left, and a
        backfill from it re-reads that post and walks down through the rest.
        """
        if full and head.pages_fetched == 0:
            return stored is not None  # nothing was read: nothing to reset from
        target: str | None
        if retry_cursor is not None:
            target = retry_cursor
        elif head.resume_cursor is not None:
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
                    result.failed_post_ids.append(post.post_id)
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
        (the row is kept) and is reported as a warning. Each reference without
        an expansion state starts ``pending`` (``skipped`` for a feed or
        playlist link); a state an earlier run recorded is kept.
        """
        refs = link_references(post)
        if not refs:
            return
        try:
            with db.begin_nested():
                result.references_recorded += ReferenceExtractor().store_references(
                    row.id, refs, db, commit=False
                )
                _initialize_expansion_states(db, row.id, refs)
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
        """Expand the links of the written posts, then retry older links on the budget left.

        ``enabled`` is already resolved against the source's ``expand_links``.
        The first failed submission stops the rest of the run, retry included.
        """
        result = _Expansion()
        if not enabled:
            return result
        result.limit = self._expansion_limit()
        if posts:
            self._expand_new_links(posts, result)
        if not result.failed:
            self._retry_links(result, budget=result.limit - result.submitted)
        self._log_expansion(result)
        return result

    def _expand_new_links(self, posts: Sequence[XPost], result: _Expansion) -> None:
        """Submit one url operation per distinct article link of the written posts.

        Only rows written in this run are expanded here, so a rerun over known
        bookmarks submits nothing new (the retry pass handles the backlog). A
        link already stored as content, or seen earlier in the run, is not
        submitted again, and the idempotency key collapses a submission onto a
        still-active one for the same URL. The first failed submission stops
        the rest: the rows are committed, and the unsubmitted links keep their
        references. Each outcome is written to every reference of the link.
        """
        outcomes: dict[str, ExpansionState] = {}
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
                    outcomes[reference_url(url)] = ExpansionState.SKIPPED
                    continue
                candidates[url] = post
        for url in self._stored_urls(list(candidates)):
            del candidates[url]
            result.skip(SKIP_ALREADY_STORED)
            outcomes[reference_url(url)] = ExpansionState.SKIPPED

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
                outcomes[reference_url(url)] = ExpansionState.SKIPPED
                continue
            outcome = self._submit_link(command, url, result)
            if outcome is not None:
                outcomes[reference_url(url)] = outcome
            if outcome is ExpansionState.SUBMITTED:
                result.submitted += 1
                continue
            result.failed = min(result.limit, len(pending)) - index
            break
        self._record_outcomes(outcomes, result)

    def _retry_links(self, result: _Expansion, *, budget: int) -> None:
        """Submit older pending/failed links, oldest reference first, within ``budget``.

        Applies the new-post skip rules (feed or playlist, X self or media
        links, already stored as content) and marks those ``skipped``; a skip
        spends no budget. Links this run already handled are left alone, and a
        link is not selected once it has been attempted
        ``MAX_LINK_EXPANSION_ATTEMPTS`` times. The first failed submission
        stops the pass, like the new-post loop.
        """
        outcomes: dict[str, ExpansionState] = {}
        stopped = False
        while budget > 0 and not stopped:
            batch = self._retry_candidates(limit=budget, exclude=result.handled)
            if not batch:
                break
            stored = set(self._stored_urls(batch))
            for index, url in enumerate(batch):
                result.handled.add(url)
                reason = expansion_skip_reason(url) or (
                    SKIP_ALREADY_STORED if url in stored else None
                )
                command: UrlIngestCommand | None = None
                if reason is None:
                    try:
                        command = UrlIngestCommand(
                            url=url, tags=[X_BOOKMARK_TAG], notes=RETRY_NOTES
                        )
                    except ValidationError:
                        reason = SKIP_UNSUPPORTED
                if command is None:
                    result.skip(reason or SKIP_UNSUPPORTED)
                    outcomes[url] = ExpansionState.SKIPPED
                    continue
                outcome = self._submit_link(command, url, result)
                if outcome is not None:
                    outcomes[url] = outcome
                if outcome is ExpansionState.SUBMITTED:
                    result.retried += 1
                    budget -= 1
                    continue
                result.failed += len(batch) - index
                stopped = True
                break
        self._record_outcomes(outcomes, result)

    def _submit_link(
        self, command: UrlIngestCommand, url: str, result: _Expansion
    ) -> ExpansionState | None:
        """Submit one link: ``submitted``, ``failed``, or None outside the worker.

        Outside the durable worker nothing can be submitted, which is not the
        link's fault, so that outcome records no attempt.
        """
        try:
            self._link_submitter(command, idempotency_key=link_idempotency_key(url))
        except FollowUpUnavailableError:
            result.unavailable = True
            return None
        except Exception as exc:
            logger.warning(f"x_bookmarks.link_submit_failed ({log_error_type(exc)})")
            return ExpansionState.FAILED
        return ExpansionState.SUBMITTED

    @staticmethod
    def _log_expansion(result: _Expansion) -> None:
        skipped = sum(result.skipped.values())
        logger.info(
            f"x_bookmarks.expand_links: {result.submitted} url operation(s) submitted, "
            f"{result.retried} retried, {skipped} link(s) skipped, {result.capped} over the "
            f"limit of {result.limit}, {result.failed} not submitted, {result.pending} pending"
        )

    @staticmethod
    def _record_outcomes(outcomes: dict[str, ExpansionState], result: _Expansion) -> None:
        """Write each link's outcome to every pending/failed reference of that link.

        ``submitted`` and ``failed`` count an attempt and stamp its time;
        ``skipped`` does not. ``submitted`` and ``skipped`` are terminal, so a
        reference already in either state is never touched. Fails open: an
        unrecorded outcome only means the link is considered again next run.
        """
        result.handled.update(outcomes)
        if not outcomes:
            return
        by_state: dict[ExpansionState, list[str]] = {}
        for url, state in outcomes.items():
            by_state.setdefault(state, []).append(url)
        attempted_at = datetime.now(UTC)
        try:
            with get_db() as db:
                with db.begin_nested():
                    for state, urls in by_state.items():
                        values: dict[str, Any] = {"expansion_state": state.value}
                        if state is not ExpansionState.SKIPPED:
                            values["expansion_attempts"] = func.least(
                                ContentReference.expansion_attempts + 1, _MAX_ATTEMPTS_STORED
                            )
                            values["expansion_attempted_at"] = attempted_at
                        db.execute(
                            update(ContentReference)
                            .where(
                                ContentReference.external_url.in_(urls),
                                ContentReference.expansion_state.in_(_RETRYABLE_STATES),
                            )
                            .values(**values)
                            .execution_options(synchronize_session=False)
                        )
                db.commit()
        except Exception as exc:
            logger.warning(f"x_bookmarks.link_state_write_failed ({log_error_type(exc)})")

    @staticmethod
    def _retryable_links() -> Select[tuple[str | None]]:
        """Distinct pending/failed reference URLs under the attempt limit."""
        return (
            select(ContentReference.external_url)
            .where(
                ContentReference.expansion_state.in_(_RETRYABLE_STATES),
                ContentReference.external_url.is_not(None),
            )
            .group_by(ContentReference.external_url)
            .having(func.max(ContentReference.expansion_attempts) < MAX_LINK_EXPANSION_ATTEMPTS)
        )

    def _retry_candidates(self, *, limit: int, exclude: set[str]) -> list[str]:
        """Up to ``limit`` retryable links, oldest reference first. Fails open to none."""
        statement = self._retryable_links()
        if exclude:
            statement = statement.where(ContentReference.external_url.not_in(sorted(exclude)))
        statement = statement.order_by(
            func.min(ContentReference.created_at), func.min(ContentReference.id)
        ).limit(limit)
        try:
            with get_db() as db:
                return [url for url in db.execute(statement).scalars() if url]
        except Exception as exc:
            logger.warning(f"x_bookmarks.link_retry_unavailable ({log_error_type(exc)})")
            return []

    def _pending_link_count(self) -> int:
        """How many distinct links are left to retry. Fails open to zero."""
        try:
            with get_db() as db:
                return int(
                    db.execute(
                        select(func.count()).select_from(self._retryable_links().subquery())
                    ).scalar_one()
                )
        except Exception as exc:
            logger.warning(f"x_bookmarks.link_backlog_unavailable ({log_error_type(exc)})")
            return 0

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
        retry_links: bool = False,
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
                "retry_links": retry_links,
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
                "links_retried": expansion.retried,
                "links_pending": expansion.pending,
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


def _initialize_expansion_states(
    db: Session, content_id: int, refs: Sequence[ExtractedReference]
) -> None:
    """Give the row's stateless references their initial expansion state."""
    by_state: dict[ExpansionState, list[str]] = {}
    for ref in refs:
        if ref.external_url:
            by_state.setdefault(initial_expansion_state(ref.external_url), []).append(
                ref.external_url
            )
    for state, urls in by_state.items():
        db.execute(
            update(ContentReference)
            .where(
                ContentReference.source_content_id == content_id,
                ContentReference.external_url.in_(urls),
                ContentReference.expansion_state.is_(None),
            )
            .values(expansion_state=state.value)
            .execution_options(synchronize_session=False)
        )


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
