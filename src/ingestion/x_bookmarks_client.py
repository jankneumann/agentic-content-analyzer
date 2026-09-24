"""HTTP client for X's own Bookmarks GraphQL endpoint, driven by a browser session.

A port of the fetch layer of the MIT-licensed x-bookmarks-exporter
(github.com/displace-agency/x-bookmarks-exporter, ``src/api.ts``) from Node to
httpx, so the Python worker needs no Node runtime and shells out to nothing.
It covers the HTTP layer only: persistence and the orchestrator body belong to
the X bookmarks adapter, link expansion to a later step.

What it does:

* **Authentication**: every request to x.com carries the operator's
  ``auth_token``/``ct0`` session, read per request through the live
  :class:`~src.config.credentials.CredentialProvider`, plus the public web-app
  bearer token (:func:`src.ingestion.x_web.x_web_headers`). Requests to X's
  static bundle host never carry the session.
* **Query ID discovery**: X rotates the ``Bookmarks`` GraphQL query ID with its
  web deploys. The last good ID is cached durably as the settings override
  ``x_bookmarks.graphql_query_id``, so a run only scrapes X's bundles when the
  cache is empty or X rejects the ID (404 or a "query not found" GraphQL
  error); then the cache is invalidated, the ID rediscovered once, and the
  request retried once.
* **Pagination**: :meth:`XBookmarksClient.iter_pages` walks the bookmarks
  timeline newest-first by its ``cursor-bottom`` entries, with a hard page cap,
  a conservative page size, a pause between pages, and a ``stop_when`` hook.
* **Rate limits**: a 429 waits until ``x-rate-limit-reset`` when that is at
  most ``max_rate_limit_wait_s`` away; otherwise the walk stops gracefully with
  :attr:`WalkStopReason.RATE_LIMITED`, keeping the pages already yielded.
* **Dead sessions**: 401, a non-Cloudflare 403, a redirect to X's login flow,
  or an HTML login page in place of JSON triggers one OpenBao refresh and one
  retry when that produced different values; a session still refused is marked
  rejected on both credentials and raises
  :class:`~src.ingestion.credential_failures.SessionExpiredError`.
* **ct0 rotation**: X re-issues ``ct0`` in ``Set-Cookie``. Before the response
  is discarded the new value is written back with ``X_AUTH_TOKEN`` in ONE
  OpenBao PATCH (``BaoSink``) and applied to the local credential cache, and
  the next request uses it. A write-back failure never fails the fetch.

Security: cookie values never appear in a log line, an exception message, an
exception chain, or a record repr. httpx errors are reported by type only.
"""

from __future__ import annotations

import contextlib
import html
import json
import logging
import math
import re
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Final, Protocol
from urllib.parse import urlsplit

import httpx

from src.config.credentials import (
    X_AUTH_TOKEN,
    X_CT0,
    CredentialProvider,
    get_credential_provider,
)
from src.ingestion.credential_failures import (
    CredentialsMissingError,
    SessionExpiredError,
    refresh_command_for,
)
from src.ingestion.log_redaction import log_error_type
from src.ingestion.x_web import X_CT0_COOKIE, X_WEB_USER_AGENT, x_web_headers

logger = logging.getLogger(__name__)

__all__ = [
    "BOOKMARKS_PAGE_URL",
    "CLIENT_WEB_BASE_URL",
    "DEFAULT_MAX_PAGES",
    "DEFAULT_MAX_RATE_LIMIT_WAIT_S",
    "DEFAULT_PAGE_SIZE",
    "FEATURES",
    "FIELD_TOGGLES",
    "GRAPHQL_BASE_URL",
    "QUERY_ID_SETTING_KEY",
    "BookmarkWalk",
    "BookmarksPage",
    "QueryIdDiscoveryError",
    "QueryIdStore",
    "SettingsQueryIdStore",
    "WalkStopReason",
    "XBookmarksClient",
    "XBookmarksClientError",
    "XBookmarksUpstreamError",
    "XPost",
    "extract_bookmarks_query_id",
    "is_x_self_link",
    "parse_bookmarks_page",
    "parse_tweet_result",
]

SOURCE: Final = "x_bookmarks"
"""Ingestion ``command_key``; also names the source in credential failures."""

REFRESH_COMMAND: Final = refresh_command_for(SOURCE)
X_SESSION_LABEL: Final = "x.auth_token/x.ct0"

GRAPHQL_BASE_URL: Final = "https://x.com/i/api/graphql"
BOOKMARKS_PAGE_URL: Final = "https://x.com/i/bookmarks"
CLIENT_WEB_BASE_URL: Final = "https://abs.twimg.com/responsive-web/client-web/"

QUERY_ID_SETTING_KEY: Final = "x_bookmarks.graphql_query_id"
"""``settings_overrides`` key holding the last Bookmarks query ID X accepted."""

DEFAULT_PAGE_SIZE: Final = 20
MAX_PAGE_SIZE: Final = 100
DEFAULT_MAX_PAGES: Final = 50
HARD_MAX_PAGES: Final = 500

DEFAULT_MAX_RATE_LIMIT_WAIT_S: Final = 900.0
"""Longest 429 wait honoured in-process (15 minutes); beyond it the walk stops."""
DEFAULT_RATE_LIMIT_WAIT_S: Final = 60.0
"""Wait when a 429 carries no usable ``x-rate-limit-reset``."""
MIN_RATE_LIMIT_WAIT_S: Final = 5.0
MAX_RATE_LIMIT_WAITS_PER_PAGE: Final = 2

REQUEST_TIMEOUT_S: Final = 20.0

# GraphQL feature flags and field toggles X's web app sends with Bookmarks
# (copied from the exporter). X rejects the request when a required flag is
# missing, so a 400 naming a feature means this table needs updating.
FEATURES: Final[Mapping[str, bool]] = {
    "graphql_timeline_v2_bookmark_timeline": True,
    "rweb_tipjar_consumption_enabled": True,
    "responsive_web_graphql_exclude_directive_enabled": True,
    "verified_phone_label_enabled": False,
    "creator_subscriptions_tweet_preview_api_enabled": True,
    "responsive_web_graphql_timeline_navigation_enabled": True,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
    "communities_web_enable_tweet_community_results_fetch": True,
    "c9s_tweet_anatomy_moderator_badge_enabled": True,
    "articles_preview_enabled": True,
    "responsive_web_edit_tweet_api_enabled": True,
    "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
    "view_counts_everywhere_api_enabled": True,
    "longform_notetweets_consumption_enabled": True,
    "responsive_web_twitter_article_tweet_consumption_enabled": True,
    "tweet_awards_web_tipping_enabled": False,
    "creator_subscriptions_quote_tweet_preview_enabled": False,
    "freedom_of_speech_not_reach_fetch_enabled": True,
    "standardized_nudges_misinfo": True,
    "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
    "rweb_video_timestamps_enabled": True,
    "longform_notetweets_rich_text_read_enabled": True,
    "longform_notetweets_inline_media_enabled": True,
    "responsive_web_enhance_cards_enabled": False,
}

FIELD_TOGGLES: Final[Mapping[str, bool]] = {
    "withArticlePlainText": False,
    "withArticleRichContentState": False,
    "withGrokAnalyze": False,
    "withDisallowedReplyControls": False,
}

# -- errors -----------------------------------------------------------------


class XBookmarksClientError(Exception):
    """X could not be read for a reason other than the session. Value-free."""


class QueryIdDiscoveryError(XBookmarksClientError):
    """The Bookmarks query ID could not be found in X's web bundles."""


class XBookmarksUpstreamError(XBookmarksClientError):
    """X failed or answered unexpectedly (network error, 5xx, odd JSON)."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


# -- records ----------------------------------------------------------------


@dataclass(frozen=True)
class XPost:
    """One post as X's web app returns it. Carries no credential.

    ``text`` is the full note-tweet text when the post is long-form, with
    ``t.co`` links replaced by their expanded URLs and trailing media links
    removed. ``outbound_urls`` are the expanded links that leave X (links to
    x.com, twitter.com, and t.co are self links and excluded).
    """

    post_id: str
    url: str
    text: str
    author_id: str | None = None
    author_handle: str | None = None
    author_name: str | None = None
    created_at: datetime | None = None
    conversation_id: str | None = None
    in_reply_to_post_id: str | None = None
    outbound_urls: tuple[str, ...] = ()
    media_urls: tuple[str, ...] = ()
    hashtags: tuple[str, ...] = ()
    mentions: tuple[str, ...] = ()
    like_count: int = 0
    repost_count: int = 0
    reply_count: int = 0
    is_long_form: bool = False
    quoted: XPost | None = None
    """The quoted post, one level deep (a quote inside it is not followed)."""


@dataclass(frozen=True)
class BookmarksPage:
    """One page of the bookmarks timeline, newest bookmark first."""

    number: int
    """1-based position of this page in its walk."""
    posts: tuple[XPost, ...]
    next_cursor: str | None = field(default=None, repr=False)

    @property
    def post_ids(self) -> tuple[str, ...]:
        return tuple(post.post_id for post in self.posts)


class WalkStopReason(StrEnum):
    """Why :class:`BookmarkWalk` stopped fetching."""

    EXHAUSTED = "exhausted"
    """X returned an empty page or no further cursor: every bookmark was read."""
    STOP_WHEN = "stop_when"
    """The caller's ``stop_when`` hook asked to stop."""
    PAGE_CAP = "page_cap"
    """``max_pages`` pages were fetched; older bookmarks were not read."""
    RATE_LIMITED = "rate_limited"
    """X rate-limited the walk for longer than the client waits; partial read."""
    CALLER_STOPPED = "caller_stopped"
    """The caller stopped iterating early."""


# -- query ID cache ---------------------------------------------------------

_QUERY_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def _is_valid_query_id(value: object) -> bool:
    return isinstance(value, str) and bool(_QUERY_ID_RE.fullmatch(value))


class QueryIdStore(Protocol):
    """Durable home of the last good Bookmarks query ID. Must not raise."""

    def get(self) -> str | None: ...

    def set(self, query_id: str) -> None: ...

    def clear(self) -> None: ...


def _default_db_factory() -> contextlib.AbstractContextManager[Any]:
    from src.storage.database import get_db

    return get_db()


class SettingsQueryIdStore:
    """Keep the query ID in ``settings_overrides`` (via :class:`SettingsService`).

    The ID is a public identifier from X's JavaScript, not a secret, and an
    operator can pin one by hand with the settings override API. Database
    errors are logged by type and treated as a cache miss, so an unavailable
    database costs one bundle scrape, never the run.
    """

    def __init__(
        self,
        *,
        key: str = QUERY_ID_SETTING_KEY,
        db_factory: Callable[[], contextlib.AbstractContextManager[Any]] | None = None,
    ) -> None:
        self._key = key
        self._db_factory = db_factory or _default_db_factory

    def get(self) -> str | None:
        from src.services.settings_service import SettingsService

        try:
            with self._db_factory() as db:
                value = SettingsService(db).get(self._key)
        except Exception as exc:
            logger.warning("x_bookmarks.query_id_cache_unavailable (%s)", log_error_type(exc))
            return None
        return value if _is_valid_query_id(value) else None

    def set(self, query_id: str) -> None:
        from src.services.settings_service import SettingsService

        try:
            with self._db_factory() as db:
                SettingsService(db).set(
                    self._key,
                    query_id,
                    description="Last X Bookmarks GraphQL query ID X accepted (auto-discovered)",
                )
        except Exception as exc:
            logger.warning("x_bookmarks.query_id_cache_write_failed (%s)", log_error_type(exc))

    def clear(self) -> None:
        from src.services.settings_service import SettingsService

        try:
            with self._db_factory() as db:
                SettingsService(db).delete(self._key)
        except Exception as exc:
            logger.warning("x_bookmarks.query_id_cache_clear_failed (%s)", log_error_type(exc))


# -- query ID discovery (pure helpers) --------------------------------------

_INLINE_SCRIPT_RE = re.compile(r"<script[^>]*>([\s\S]*?)</script>", re.IGNORECASE)
_BOOKMARKS_CHUNK_RE = re.compile(r'(?<![\w"])(\d+):"((?:[A-Za-z0-9_.-]+~)*bundle\.Bookmarks)"')
_MAIN_BUNDLE_RE = re.compile(
    r'src="(https://abs\.twimg\.com/responsive-web/client-web(?:-legacy)?/main\.[A-Za-z0-9]+\.js)"'
)
_BOOKMARKS_QUERY_ID_RE = re.compile(r'queryId:"([A-Za-z0-9_-]+)",operationName:"Bookmarks"')


def extract_bookmarks_query_id(javascript: str) -> str | None:
    """Return the ``Bookmarks`` operation's query ID from a bundle, if present."""
    match = _BOOKMARKS_QUERY_ID_RE.search(javascript)
    if match and _is_valid_query_id(match.group(1)):
        return match.group(1)
    return None


def _bookmarks_chunk_urls(page_html: str) -> list[str]:
    """Candidate URLs of the webpack chunk that defines the Bookmarks query.

    The webpack runtime inlined in the page maps chunk IDs to names
    (``123:"shared~bundle.BookmarkFolders~bundle.Bookmarks"``) and to content
    hashes (``123:"abc1234"``); the chunk is served as ``<name>.<hash>.js``.
    X sometimes keeps 7 hex characters in the map but 8 in the file name, so
    the exporter also tries the hash with an ``a`` or ``b`` appended.
    """
    runtime = "\n".join(
        script for script in _INLINE_SCRIPT_RE.findall(page_html) if 'bundle.Bookmarks"' in script
    )
    chunks = {name: chunk_id for chunk_id, name in _BOOKMARKS_CHUNK_RE.findall(runtime)}
    # The exporter prefers the shared BookmarkFolders~Bookmarks chunk.
    ordered = sorted(chunks.items(), key=lambda item: item[0] == "bundle.Bookmarks")
    urls: list[str] = []
    for name, chunk_id in ordered:
        hashes = re.findall(rf'(?<![\w"]){chunk_id}:"([a-f0-9]{{7,20}})"', runtime)
        if not hashes:
            continue
        content_hash = hashes[-1]
        urls.extend(
            f"{CLIENT_WEB_BASE_URL}{name}.{content_hash}{suffix}.js" for suffix in ("", "a", "b")
        )
    return urls


def _main_bundle_url(page_html: str) -> str | None:
    match = _MAIN_BUNDLE_RE.search(page_html)
    return match.group(1) if match else None


# -- dead-session and error classification ----------------------------------

_LOGIN_PAGE_MARKERS: Final = ("LoginForm", "/i/flow/login")
_LOGIN_PATH_RE = re.compile(r"(^|/)(login|i/flow/login|account/access)(/|$)", re.IGNORECASE)
# X API error codes that mean "this session is not valid": 32 could not
# authenticate you, 89 invalid or expired token, 215 bad authentication data,
# 353 CSRF cookie and header mismatch.
_SESSION_ERROR_CODES: Final = frozenset({32, 89, 215, 353})
_QUERY_NOT_FOUND_RE = re.compile(
    r"query\s*(?:id\s*)?(?:was\s*)?not\s*found|could not resolve|unknown\s+query|"
    r"query:\s*unspecified",
    re.IGNORECASE,
)


def _is_cloudflare_challenge(response: httpx.Response) -> bool:
    return "cf-mitigated" in response.headers


def _redirects_to_login(response: httpx.Response) -> bool:
    if not response.is_redirect:
        return False
    path = urlsplit(response.headers.get("location", "")).path.strip("/")
    return bool(_LOGIN_PATH_RE.search(path))


def _json_body(response: httpx.Response) -> Any:
    content_type = response.headers.get("content-type", "").lower()
    if "json" not in content_type:
        return None
    try:
        return response.json()
    except ValueError:
        return None


def _graphql_errors(payload: Any) -> list[Mapping[str, Any]]:
    if not isinstance(payload, Mapping):
        return []
    errors = payload.get("errors")
    if not isinstance(errors, list):
        return []
    return [error for error in errors if isinstance(error, Mapping)]


def _has_data(payload: Any) -> bool:
    return isinstance(payload, Mapping) and isinstance(payload.get("data"), Mapping)


def _is_dead_api_response(response: httpx.Response) -> bool:
    """True when an authenticated GraphQL request came back logged out.

    401; a 403 that is not a Cloudflare challenge; a redirect into X's login
    flow; a 2xx HTML page where the endpoint returns JSON; or a JSON body with
    no data whose errors carry a session error code. 404, 429 and 5xx are not
    session verdicts.
    """
    status = response.status_code
    if status == 401:
        return True
    if status == 403:
        return not _is_cloudflare_challenge(response)
    if response.is_redirect:
        return _redirects_to_login(response)
    if response.is_success:
        if response.headers.get("content-type", "").lower().startswith("text/html"):
            return True
        payload = _json_body(response)
        if not _has_data(payload):
            return any(
                error.get("code") in _SESSION_ERROR_CODES for error in _graphql_errors(payload)
            )
    return False


def _is_dead_page_response(response: httpx.Response) -> bool:
    """True when the authenticated ``/i/bookmarks`` page came back logged out."""
    status = response.status_code
    if status == 401:
        return True
    if status == 403:
        return not _is_cloudflare_challenge(response)
    if response.is_redirect:
        return _redirects_to_login(response)
    if response.is_success:
        text = response.text
        return any(marker in text for marker in _LOGIN_PAGE_MARKERS)
    return False


def _is_stale_query_id(response: httpx.Response, payload: Any) -> bool:
    if response.status_code == 404:
        return True
    if _has_data(payload) or response.status_code not in (200, 400):
        return False
    messages = [str(error.get("message", "")) for error in _graphql_errors(payload)]
    if response.status_code == 400 and not messages:
        messages = [response.text[:2_000]]
    return any(_QUERY_NOT_FOUND_RE.search(message) for message in messages)


# -- Set-Cookie ct0 rotation --------------------------------------------------

_COOKIE_VALUE_RE = re.compile(r"^[A-Za-z0-9_-]{8,512}$")


def _rotated_ct0(response: httpx.Response) -> str | None:
    """The ``ct0`` value a ``Set-Cookie`` header issues, ignoring deletions."""
    issued: str | None = None
    for header in response.headers.get_list("set-cookie"):
        name, _, rest = header.partition("=")
        if name.strip() != X_CT0_COOKIE:
            continue
        value, *attributes = rest.split(";")
        value = value.strip().strip('"')
        deleted = False
        for attribute in attributes:
            key, _, attr_value = attribute.strip().partition("=")
            if key.lower() == "max-age":
                with contextlib.suppress(ValueError):
                    deleted = deleted or int(attr_value.strip()) <= 0
        if not deleted and _COOKIE_VALUE_RE.fullmatch(value):
            issued = value
    return issued


# -- tweet parsing ------------------------------------------------------------

_SELF_LINK_HOSTS: Final = ("x.com", "twitter.com", "t.co")
_CREATED_AT_FORMAT: Final = "%a %b %d %H:%M:%S %z %Y"


def is_x_self_link(url: str) -> bool:
    """True for links that stay on X (x.com, twitter.com, t.co, subdomains)."""
    host = (urlsplit(url).hostname or "").lower().rstrip(".")
    return any(host == base or host.endswith("." + base) for base in _SELF_LINK_HOSTS)


def _dig(value: Any, *keys: str) -> Any:
    for key in keys:
        if not isinstance(value, Mapping):
            return None
        value = value.get(key)
    return value


def _dicts(value: Any) -> list[Mapping[str, Any]]:
    return [item for item in value if isinstance(item, Mapping)] if isinstance(value, list) else []


def _str_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _unique(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def _parse_created_at(raw: Any) -> datetime | None:
    if not isinstance(raw, str):
        return None
    try:
        return datetime.strptime(raw, _CREATED_AT_FORMAT).astimezone(UTC)
    except ValueError:
        return None


def _media_urls(media: list[Mapping[str, Any]]) -> tuple[str, ...]:
    urls: list[str] = []
    for item in media:
        if item.get("type") in ("video", "animated_gif"):
            variants = [
                variant
                for variant in _dicts(_dig(item, "video_info", "variants"))
                if variant.get("content_type") == "video/mp4" and _str_or_none(variant.get("url"))
            ]
            if variants:
                best = max(variants, key=lambda variant: _int(variant.get("bitrate")))
                urls.append(str(best["url"]).split("?", 1)[0])
                continue
        media_url = _str_or_none(item.get("media_url_https"))
        if media_url:
            urls.append(media_url)
    return _unique(urls)


def _expand_text(
    text: str, url_entities: list[Mapping[str, Any]], media: list[Mapping[str, Any]]
) -> str:
    """Replace ``t.co`` links with their targets and drop trailing media links."""
    for entity in url_entities:
        short, expanded = _str_or_none(entity.get("url")), _str_or_none(entity.get("expanded_url"))
        if short and expanded:
            text = text.replace(short, expanded)
    for item in media:
        short = _str_or_none(item.get("url"))
        if short:
            text = text.replace(short, "")
    return text.strip()


def _outbound_urls(url_entities: list[Mapping[str, Any]]) -> tuple[str, ...]:
    urls: list[str] = []
    for entity in url_entities:
        expanded = _str_or_none(entity.get("expanded_url"))
        if not expanded or urlsplit(expanded).scheme not in ("http", "https"):
            continue
        if not is_x_self_link(expanded):
            urls.append(expanded)
    return _unique(urls)


def parse_tweet_result(result: Any, *, _depth: int = 0) -> XPost | None:
    """Map one ``tweet_results.result`` object to an :class:`XPost`.

    Handles the ``TweetWithVisibilityResults`` wrapper, the newer
    ``user_results.result.core`` author shape and the older ``legacy`` one,
    long-form note tweets, video variants, and one level of quoted post.
    Tombstones and unavailable posts return ``None``.
    """
    if not isinstance(result, Mapping):
        return None
    tweet = result.get("tweet") if isinstance(result.get("tweet"), Mapping) else result
    legacy = tweet.get("legacy")
    if not isinstance(legacy, Mapping):
        return None
    post_id = str(tweet.get("rest_id") or result.get("rest_id") or legacy.get("id_str") or "")
    if not post_id.isdigit():
        return None

    user = _dig(tweet, "core", "user_results", "result")
    user = user if isinstance(user, Mapping) else {}
    user_core = user.get("core") if isinstance(user.get("core"), Mapping) else {}
    user_legacy = user.get("legacy") if isinstance(user.get("legacy"), Mapping) else {}
    handle = _str_or_none(user_core.get("screen_name")) or _str_or_none(
        user_legacy.get("screen_name")
    )
    name = _str_or_none(user_core.get("name")) or _str_or_none(user_legacy.get("name"))

    note = _dig(tweet, "note_tweet", "note_tweet_results", "result")
    note = note if isinstance(note, Mapping) else {}
    note_text = _str_or_none(note.get("text"))
    entities = legacy.get("entities") if isinstance(legacy.get("entities"), Mapping) else {}
    note_entities = note.get("entity_set") if isinstance(note.get("entity_set"), Mapping) else {}

    url_entities = _dicts(entities.get("urls")) + _dicts(note_entities.get("urls"))
    media = _dicts(_dig(legacy, "extended_entities", "media")) or _dicts(entities.get("media"))
    raw_text = note_text or html.unescape(str(legacy.get("full_text") or ""))

    quoted = None
    if _depth == 0:
        quoted = parse_tweet_result(_dig(tweet, "quoted_status_result", "result"), _depth=1)

    return XPost(
        post_id=post_id,
        url=(
            f"https://x.com/{handle}/status/{post_id}"
            if handle
            else f"https://x.com/i/web/status/{post_id}"
        ),
        text=_expand_text(raw_text, url_entities, media),
        author_id=_str_or_none(user.get("rest_id")),
        author_handle=handle,
        author_name=name,
        created_at=_parse_created_at(legacy.get("created_at")),
        conversation_id=_str_or_none(legacy.get("conversation_id_str")),
        in_reply_to_post_id=_str_or_none(legacy.get("in_reply_to_status_id_str")),
        outbound_urls=_outbound_urls(url_entities),
        media_urls=_media_urls(media),
        hashtags=_unique(
            [
                str(tag.get("text"))
                for tag in _dicts(entities.get("hashtags")) + _dicts(note_entities.get("hashtags"))
                if tag.get("text")
            ]
        ),
        mentions=_unique(
            [
                str(mention.get("screen_name"))
                for mention in _dicts(entities.get("user_mentions"))
                + _dicts(note_entities.get("user_mentions"))
                if mention.get("screen_name")
            ]
        ),
        like_count=_int(legacy.get("favorite_count")),
        repost_count=_int(legacy.get("retweet_count")),
        reply_count=_int(legacy.get("reply_count")),
        is_long_form=note_text is not None,
        quoted=quoted,
    )


def _entry_tweet_results(entry: Mapping[str, Any]) -> list[Any]:
    content = entry.get("content")
    if not isinstance(content, Mapping):
        return []
    results = [_dig(content, "itemContent", "tweet_results", "result")]
    # Module entries (conversation groups) nest their items one level deeper.
    results.extend(
        _dig(item, "item", "itemContent", "tweet_results", "result")
        for item in _dicts(content.get("items"))
    )
    return [result for result in results if result is not None]


def parse_bookmarks_page(payload: Any, *, number: int = 1) -> BookmarksPage:
    """Parse a Bookmarks GraphQL response body into a :class:`BookmarksPage`."""
    instructions = _dicts(_dig(payload, "data", "bookmark_timeline_v2", "timeline", "instructions"))
    posts: dict[str, XPost] = {}
    next_cursor: str | None = None
    for instruction in instructions:
        entries = _dicts(instruction.get("entries"))
        if isinstance(instruction.get("entry"), Mapping):
            entries.append(instruction["entry"])
        for entry in entries:
            content = entry.get("content")
            content = content if isinstance(content, Mapping) else {}
            entry_id = str(entry.get("entryId") or "")
            if content.get("cursorType") == "Bottom" or entry_id.startswith("cursor-bottom"):
                next_cursor = _str_or_none(content.get("value")) or next_cursor
                continue
            for result in _entry_tweet_results(entry):
                post = parse_tweet_result(result)
                if post is not None and post.post_id not in posts:
                    posts[post.post_id] = post
    return BookmarksPage(number=number, posts=tuple(posts.values()), next_cursor=next_cursor)


# -- the client -----------------------------------------------------------------


class SessionSecretWriter(Protocol):
    """What the ct0 write-back needs from a secret sink (``BaoSink``)."""

    def write(self, values: Mapping[str, str]) -> list[str]: ...


SinkFactory = Callable[[Callable[[], datetime]], SessionSecretWriter | None]
"""Builds the write-back sink around a ``saved_at`` clock; None when unconfigured."""


def _default_sink_factory(saved_at_clock: Callable[[], datetime]) -> SessionSecretWriter | None:
    from src.config import bao_secrets

    if not bao_secrets.is_bao_configured():
        return None
    from src.cli.secret_sinks import BaoSink

    # Reuse the client the worker authenticated for its reads (no second login).
    return BaoSink(
        client=bao_secrets.get_authenticated_bao_client(), clock=saved_at_clock, echo=None
    )


class _PinnedClock:
    """The sink's ``saved_at`` clock, pinned on first use so it can be reused."""

    def __init__(self, now: Callable[[], datetime]) -> None:
        self._now = now
        self.at: datetime | None = None

    def __call__(self) -> datetime:
        if self.at is None:
            self.at = self._now()
        return self.at


@dataclass(frozen=True)
class _Session:
    auth_token: str = field(repr=False)
    ct0: str = field(repr=False)


@dataclass(frozen=True)
class _Rotation:
    """A ct0 X re-issued, used while the provider still returns ``stale_ct0``."""

    auth_token: str = field(repr=False)
    stale_ct0: str | None = field(repr=False)
    ct0: str = field(repr=False)


class BookmarkWalk:
    """One newest-first walk over the bookmarks timeline. Iterate it once.

    After iteration, :attr:`stop_reason` says why it stopped,
    :attr:`pages_fetched` how many GraphQL pages were read, and
    :attr:`rate_limit_reset_at` when X's rate-limit window reopens if the walk
    stopped on :attr:`WalkStopReason.RATE_LIMITED`.
    """

    def __init__(
        self,
        client: XBookmarksClient,
        *,
        stop_when: Callable[[tuple[str, ...]], bool] | None,
        max_pages: int,
    ) -> None:
        self._client = client
        self._stop_when = stop_when
        self.max_pages = max_pages
        self.stop_reason: WalkStopReason | None = None
        self.pages_fetched = 0
        self.rate_limit_reset_at: datetime | None = None
        self.rediscovered_query_id = False
        self._started = False

    def __iter__(self) -> Iterator[BookmarksPage]:
        if self._started:
            raise RuntimeError("a BookmarkWalk can be iterated only once")
        self._started = True
        return self._pages()

    def _stop(self, reason: WalkStopReason) -> None:
        self.stop_reason = reason
        logger.info(
            "x_bookmarks.walk_stopped: %s after %d page(s)", reason.value, self.pages_fetched
        )

    def _pages(self) -> Iterator[BookmarksPage]:
        cursor: str | None = None
        seen_cursors: set[str] = set()
        while True:
            if self.pages_fetched >= self.max_pages:
                self._stop(WalkStopReason.PAGE_CAP)
                return
            if self.pages_fetched:
                self._client._pause_between_pages()
            payload = self._client._fetch_page_payload(cursor, self)
            if payload is None:
                self._stop(WalkStopReason.RATE_LIMITED)
                return
            self.pages_fetched += 1
            page = parse_bookmarks_page(payload, number=self.pages_fetched)
            if not page.posts:
                self._stop(WalkStopReason.EXHAUSTED)
                return
            try:
                yield page
            except GeneratorExit:
                self._stop(WalkStopReason.CALLER_STOPPED)
                raise
            if self._stop_when is not None and self._stop_when(page.post_ids):
                self._stop(WalkStopReason.STOP_WHEN)
                return
            if not page.next_cursor or page.next_cursor in seen_cursors:
                self._stop(WalkStopReason.EXHAUSTED)
                return
            seen_cursors.add(page.next_cursor)
            cursor = page.next_cursor


class XBookmarksClient:
    """Read the operator's X bookmarks through X's own web GraphQL API.

    Every seam is injectable for network-free tests: ``http`` (an
    ``httpx.Client``, e.g. over ``httpx.MockTransport``), ``credentials``,
    ``query_id_store``, ``sink_factory``, ``sleep`` and ``clock`` (epoch
    seconds).
    """

    def __init__(
        self,
        *,
        credentials: CredentialProvider | None = None,
        query_id_store: QueryIdStore | None = None,
        http: httpx.Client | None = None,
        sink_factory: SinkFactory | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
        page_delay_s: float | None = None,
        max_rate_limit_wait_s: float = DEFAULT_MAX_RATE_LIMIT_WAIT_S,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if not 1 <= page_size <= MAX_PAGE_SIZE:
            raise ValueError(f"page_size must be between 1 and {MAX_PAGE_SIZE}")
        if page_delay_s is None:
            from src.config.settings import get_settings

            page_delay_s = get_settings().x_bookmarks_page_delay_s
        self._credentials = credentials or get_credential_provider()
        self._store: QueryIdStore = query_id_store or SettingsQueryIdStore()
        self._owns_http = http is None
        self._http = http or httpx.Client(timeout=REQUEST_TIMEOUT_S, follow_redirects=False)
        self._sink_factory: SinkFactory = sink_factory or _default_sink_factory
        self._page_size = page_size
        self._page_delay_s = max(0.0, page_delay_s)
        self._max_rate_limit_wait_s = max_rate_limit_wait_s
        self._sleep = sleep
        self._clock = clock
        self._query_id: str | None = None
        self._cache_invalidated = False
        self._rotation: _Rotation | None = None

    # -- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> XBookmarksClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # -- public API --------------------------------------------------------

    def iter_pages(
        self,
        *,
        stop_when: Callable[[tuple[str, ...]], bool] | None = None,
        max_pages: int = DEFAULT_MAX_PAGES,
    ) -> BookmarkWalk:
        """Walk the bookmarks newest-first, one :class:`BookmarksPage` at a time.

        ``stop_when`` receives each yielded page's post IDs after the caller
        has consumed the page; returning True ends the walk without fetching
        another page (an incremental sync stops once a whole page is known).
        ``max_pages`` is a hard cap (at most 500).

        Raises :class:`CredentialsMissingError`, :class:`SessionExpiredError`,
        :class:`QueryIdDiscoveryError` or :class:`XBookmarksUpstreamError`
        while iterating. A long rate limit is not an error: the walk stops
        with :attr:`WalkStopReason.RATE_LIMITED`.
        """
        if not 1 <= max_pages <= HARD_MAX_PAGES:
            raise ValueError(f"max_pages must be between 1 and {HARD_MAX_PAGES}")
        return BookmarkWalk(self, stop_when=stop_when, max_pages=max_pages)

    def discover_query_id(self) -> str:
        """Scrape X's web bundles for the current Bookmarks query ID.

        Reads the authenticated ``/i/bookmarks`` page, follows the inlined
        webpack runtime's chunk map to the Bookmarks chunk, and falls back to
        the ``main.<hash>.js`` bundle. Does not touch the cache.
        """
        response, _session = self._send_authenticated(
            self._bookmarks_page_request, judge=_is_dead_page_response
        )
        if response.status_code != 200:
            raise QueryIdDiscoveryError(
                f"GET {BOOKMARKS_PAGE_URL} returned HTTP {response.status_code}"
            )
        page_html = response.text
        for url in _bookmarks_chunk_urls(page_html):
            query_id = self._query_id_from_bundle(url)
            if query_id:
                return query_id
        main_url = _main_bundle_url(page_html)
        if main_url:
            query_id = self._query_id_from_bundle(main_url)
            if query_id:
                return query_id
        raise QueryIdDiscoveryError("the Bookmarks query ID was not found in X's web bundles")

    # -- query ID ------------------------------------------------------------

    def _resolve_query_id(self) -> str:
        if self._query_id:
            return self._query_id
        # After an invalidation the cache is not trusted again in this client:
        # a failed clear (database down) must not hand back the stale ID.
        cached = None if self._cache_invalidated else self._store.get()
        if _is_valid_query_id(cached):
            self._query_id = cached
            return str(cached)
        query_id = self.discover_query_id()
        logger.info("x_bookmarks.query_id_discovered: %s", query_id)
        self._store.set(query_id)
        self._query_id = query_id
        return query_id

    def _invalidate_query_id(self) -> None:
        self._query_id = None
        self._cache_invalidated = True
        self._store.clear()

    def _query_id_from_bundle(self, url: str) -> str | None:
        # The bundle host is not X's API: it never receives the session.
        request = self._http.build_request(
            "GET", url, headers={"user-agent": X_WEB_USER_AGENT, "referer": "https://x.com/"}
        )
        try:
            response = self._transmit(request)
        except XBookmarksUpstreamError:
            return None
        if response.status_code != 200:
            return None
        return extract_bookmarks_query_id(response.text)

    # -- requests ----------------------------------------------------------------

    def _bookmarks_page_request(self, session: _Session) -> httpx.Request:
        headers = x_web_headers(session.auth_token, session.ct0, referer="https://x.com/")
        return self._http.build_request(
            "GET",
            BOOKMARKS_PAGE_URL,
            headers={
                "cookie": headers["cookie"],
                "user-agent": X_WEB_USER_AGENT,
                "accept": "text/html",
            },
        )

    def _graphql_request(
        self, query_id: str, cursor: str | None
    ) -> Callable[[_Session], httpx.Request]:
        variables: dict[str, Any] = {"count": self._page_size, "includePromotedContent": False}
        if cursor:
            variables["cursor"] = cursor
        params = {
            "variables": _compact_json(variables),
            "features": _compact_json(FEATURES),
            "fieldToggles": _compact_json(FIELD_TOGGLES),
        }
        url = f"{GRAPHQL_BASE_URL}/{query_id}/Bookmarks"

        def build(session: _Session) -> httpx.Request:
            headers = x_web_headers(session.auth_token, session.ct0, referer=BOOKMARKS_PAGE_URL)
            headers["content-type"] = "application/json"
            return self._http.build_request("GET", url, params=params, headers=headers)

        return build

    def _transmit(self, request: httpx.Request) -> httpx.Response:
        error_type: str | None = None
        try:
            response = self._http.send(request)
            response.read()
        except httpx.HTTPError as exc:
            error_type = log_error_type(exc)
        finally:
            # Session cookies travel only in the explicit header, never the jar.
            self._http.cookies.clear()
        if error_type is not None:
            # Type only, raised outside the handler so neither __cause__ nor
            # __context__ keeps the httpx error: it holds the request, whose
            # headers carry the session cookies.
            logger.warning(
                "x_bookmarks.request_failed: %s %s (%s)",
                request.method,
                request.url.copy_with(query=None),
                error_type,
            )
            raise XBookmarksUpstreamError(f"request to X failed ({error_type})")
        return response

    # -- session ----------------------------------------------------------------

    def _read_session(self) -> _Session | None:
        auth_token = self._credentials.get(X_AUTH_TOKEN)
        ct0 = self._credentials.get(X_CT0)
        if not auth_token or not ct0:
            return None
        rotation = self._rotation
        if rotation and rotation.auth_token == auth_token and rotation.stale_ct0 == ct0:
            ct0 = rotation.ct0
        return _Session(auth_token=auth_token, ct0=ct0)

    def _require_session(self) -> _Session:
        session = self._read_session()
        if session is None:
            # A pair patched in moments ago must not be reported missing from a
            # stale cache: one bounded OpenBao refresh first.
            self._credentials.refresh()
            session = self._read_session()
        if session is None:
            missing = [
                CredentialProvider.spec(name).label
                for name in (X_AUTH_TOKEN, X_CT0)
                if not self._credentials.get(name)
            ]
            raise CredentialsMissingError(
                source=SOURCE,
                credential_label="/".join(missing) or X_SESSION_LABEL,
                refresh_command=REFRESH_COMMAND,
            )
        return session

    def _send_authenticated(
        self,
        build: Callable[[_Session], httpx.Request],
        *,
        judge: Callable[[httpx.Response], bool],
    ) -> tuple[httpx.Response, _Session]:
        """Send with the current session; refresh once and retry once if dead."""
        session = self._require_session()
        response = self._transmit(build(session))
        if judge(response):
            response, session = self._retry_after_refresh(build, judge, rejected=session)
        self._write_back_rotated_ct0(response, session)
        return response, session

    def _retry_after_refresh(
        self,
        build: Callable[[_Session], httpx.Request],
        judge: Callable[[httpx.Response], bool],
        *,
        rejected: _Session,
    ) -> tuple[httpx.Response, _Session]:
        logger.warning(
            "x_bookmarks.session_rejected: refreshing %s and %s once before failing closed",
            X_AUTH_TOKEN,
            X_CT0,
        )
        self._credentials.refresh()
        fresh = self._read_session()
        if fresh is not None and fresh != rejected:
            response = self._transmit(build(fresh))
            if not judge(response):
                logger.info("x_bookmarks.session_recovered: refreshed %s/%s", X_AUTH_TOKEN, X_CT0)
                return response, fresh
        for name in (X_AUTH_TOKEN, X_CT0):
            self._credentials.mark_rejected(name)
        raise SessionExpiredError(
            source=SOURCE, credential_label=X_SESSION_LABEL, refresh_command=REFRESH_COMMAND
        )

    def _mark_verified(self, session: _Session) -> None:
        # Only a pair the provider itself serves can be marked: an in-client
        # ct0 rotation that never reached the provider proves nothing about it.
        if (
            self._credentials.get(X_AUTH_TOKEN) == session.auth_token
            and self._credentials.get(X_CT0) == session.ct0
        ):
            self._credentials.mark_verified(X_AUTH_TOKEN)
            self._credentials.mark_verified(X_CT0)

    def _write_back_rotated_ct0(self, response: httpx.Response, session: _Session) -> None:
        """Persist a ``ct0`` X re-issued, before the response is discarded.

        ONE sink write of ``X_AUTH_TOKEN`` and ``X_CT0`` keeps the pair
        consistent, then the local credential cache gets the same values and
        ``saved_at``. Without OpenBao only the local cache is updated. Never
        raises: the fetch goes on with the new ``ct0`` either way.
        """
        new_ct0 = _rotated_ct0(response)
        if new_ct0 is None or new_ct0 == session.ct0:
            return
        self._rotation = _Rotation(
            auth_token=session.auth_token,
            stale_ct0=self._credentials.get(X_CT0),
            ct0=new_ct0,
        )
        values = {X_AUTH_TOKEN: session.auth_token, X_CT0: new_ct0}
        saved_at: datetime | None = None
        try:
            saved_at_clock = _PinnedClock(self._utc_now)
            sink = self._sink_factory(saved_at_clock)
            if sink is None:
                logger.warning(
                    "x_bookmarks.ct0_rotated: OpenBao is not configured; the new %s is "
                    "kept in this process only",
                    X_CT0,
                )
            else:
                sink.write(values)
                saved_at = saved_at_clock.at
                logger.info(
                    "x_bookmarks.ct0_written_back: patched %s and %s in OpenBao",
                    X_AUTH_TOKEN,
                    X_CT0,
                )
        except Exception as exc:
            logger.warning(
                "x_bookmarks.ct0_write_back_failed (%s); using the new %s in this process only",
                log_error_type(exc),
                X_CT0,
            )
        try:
            self._credentials.apply_local_write(values, saved_at=saved_at)
        except Exception as exc:
            logger.warning("x_bookmarks.ct0_local_apply_failed (%s)", log_error_type(exc))

    def _utc_now(self) -> datetime:
        return datetime.fromtimestamp(self._clock(), UTC)

    # -- pages -------------------------------------------------------------------

    def _pause_between_pages(self) -> None:
        if self._page_delay_s > 0:
            self._sleep(self._page_delay_s)

    def _rate_limit_wait(self, response: httpx.Response) -> tuple[float, datetime]:
        now = self._clock()
        try:
            wait = float(response.headers.get("x-rate-limit-reset", "")) - now
        except ValueError:
            wait = DEFAULT_RATE_LIMIT_WAIT_S
        if not math.isfinite(wait):
            wait = DEFAULT_RATE_LIMIT_WAIT_S
        wait = max(wait, MIN_RATE_LIMIT_WAIT_S)
        return wait, datetime.fromtimestamp(now + wait, UTC)

    def _fetch_page_payload(self, cursor: str | None, walk: BookmarkWalk) -> Any | None:
        """One page's JSON body, or None when a rate limit ends the walk."""
        rate_limit_waits = 0
        while True:
            query_id = self._resolve_query_id()
            response, session = self._send_authenticated(
                self._graphql_request(query_id, cursor), judge=_is_dead_api_response
            )
            if response.status_code == 429:
                wait, reset_at = self._rate_limit_wait(response)
                if wait > self._max_rate_limit_wait_s or (
                    rate_limit_waits >= MAX_RATE_LIMIT_WAITS_PER_PAGE
                ):
                    walk.rate_limit_reset_at = reset_at
                    logger.warning(
                        "x_bookmarks.rate_limited: window reopens in %ds; stopping the walk",
                        math.ceil(wait),
                    )
                    return None
                rate_limit_waits += 1
                logger.warning(
                    "x_bookmarks.rate_limited: waiting %ds for the window to reopen",
                    math.ceil(wait),
                )
                self._sleep(wait)
                continue
            payload = _json_body(response)
            if _is_stale_query_id(response, payload):
                if walk.rediscovered_query_id:
                    raise QueryIdDiscoveryError(
                        "X rejected the Bookmarks query ID again after rediscovery"
                    )
                walk.rediscovered_query_id = True
                logger.info(
                    "x_bookmarks.query_id_stale: HTTP %s; rediscovering once",
                    response.status_code,
                )
                self._invalidate_query_id()
                continue
            if not response.is_success:
                raise XBookmarksUpstreamError(
                    f"X Bookmarks returned HTTP {response.status_code}",
                    status_code=response.status_code,
                )
            if not _has_data(payload):
                raise XBookmarksUpstreamError(
                    "X Bookmarks returned an unexpected body", status_code=response.status_code
                )
            self._mark_verified(session)
            return payload


def _compact_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, separators=(",", ":"))
