"""Auto-routing of submitted URLs to the appropriate ingest handler.

When a user shares a single URL (via the iOS Share Sheet, the bookmarklet, the
Chrome extension, or ``aca ingest url``) we want to send it to the *right*
handler instead of always treating it as a generic web page:

- a YouTube video link  -> YouTube transcript/analysis ingestion
- a YouTube playlist link -> playlist ingestion
- an RSS / Atom feed URL -> RSS feed ingestion
- anything else          -> generic web-page extraction (Trafilatura)

The heart of this module is :func:`classify_url`, a **pure** (network-free)
function that maps a URL to a :class:`RouteKind`. Keeping it side-effect free
makes routing deterministic and trivial to unit-test; the actual dispatch and
I/O live in ``src/ingestion/orchestrator.py`` and the save-URL API.
"""

from __future__ import annotations

from enum import StrEnum
from urllib.parse import parse_qs, urlsplit

from src.models.content import ContentSource
from src.utils.youtube_links import extract_playlist_id, is_youtube_url


class RouteKind(StrEnum):
    """The ingest handler a submitted URL should be routed to.

    This is intentionally finer-grained than :class:`ContentSource`: a single
    YouTube *video* and a YouTube *playlist* both map to ``ContentSource.YOUTUBE``
    but are handled by different code paths. Use :func:`route_to_source` to map a
    ``RouteKind`` back to the storage-level ``ContentSource``.
    """

    YOUTUBE_VIDEO = "youtube_video"
    YOUTUBE_PLAYLIST = "youtube_playlist"
    RSS_FEED = "rss_feed"
    WEBPAGE = "webpage"


# Path basenames that unambiguously indicate a feed document.
_FEED_BASENAMES = frozenset(
    {
        "feed",
        "rss",
        "atom",
        "feed.xml",
        "rss.xml",
        "atom.xml",
        "index.xml",
        "feed.atom",
        "feed.rss",
        "feed.json",
        "rss.json",
    }
)

# Trailing path suffixes that indicate a feed document.
_FEED_SUFFIXES = (".rss", ".atom")


def looks_like_feed_url(url: str) -> bool:
    """Heuristically decide whether *url* points at an RSS/Atom feed.

    This is a deterministic, network-free check based purely on the URL shape.
    It intentionally errs toward precision over recall: feeds at non-obvious
    paths (e.g. a bare ``/blog`` that happens to serve XML) will be missed and
    fall through to generic web-page extraction. Detected patterns include:

    - paths ending in ``.rss`` or ``.atom``
    - a final path segment of ``feed``/``rss``/``atom`` (with or without a
      trailing slash) or a feed-ish filename (``feed.xml``, ``index.xml`` ...)
    - a ``/feeds/`` path segment (Blogger, FeedBurner)
    - a WordPress-style ``?feed=rss2`` query parameter
    - Substack ``*.substack.com/feed`` URLs

    Args:
        url: The URL to inspect.

    Returns:
        True if the URL looks like a feed document.
    """
    parts = urlsplit(url)
    host = parts.netloc.lower()
    # Strip a trailing slash so ``/feed`` and ``/feed/`` are treated the same,
    # then split into lowercased segments.
    path = parts.path.rstrip("/").lower()

    # WordPress and friends: ?feed=rss2, ?feed=atom, &feed=...
    query = parse_qs(parts.query)
    if "feed" in query:
        return True

    # Substack newsletters expose their feed at <name>.substack.com/feed.
    if host.endswith(".substack.com") and path in ("/feed", "/feed.xml"):
        return True

    if not path:
        return False

    if path.endswith(_FEED_SUFFIXES):
        return True

    segments = [seg for seg in path.split("/") if seg]
    if not segments:
        return False

    basename = segments[-1]
    if basename in _FEED_BASENAMES:
        return True

    # A /feeds/ segment anywhere (e.g. Blogger /feeds/posts/default,
    # FeedBurner /feeds/<id>).
    return "feeds" in segments[:-1]


def classify_url(url: str) -> RouteKind:
    """Classify a submitted URL into the ingest handler that should process it.

    Precedence (first match wins):

    1. YouTube video  -> :attr:`RouteKind.YOUTUBE_VIDEO`
    2. YouTube playlist -> :attr:`RouteKind.YOUTUBE_PLAYLIST`
    3. Feed-shaped URL -> :attr:`RouteKind.RSS_FEED`
    4. otherwise       -> :attr:`RouteKind.WEBPAGE`

    A ``watch?v=...&list=...`` URL is classified as a *video* (the user shared a
    specific video that merely lives inside a playlist), while a bare
    ``playlist?list=...`` is classified as a *playlist*.

    Args:
        url: The URL to classify.

    Returns:
        The :class:`RouteKind` the URL should be routed to.
    """
    # 1. A concrete video id beats everything (handles watch?v=...&list=...).
    if is_youtube_url(url):
        return RouteKind.YOUTUBE_VIDEO

    # 2. A playlist id with no video id.
    if extract_playlist_id(url) is not None and _is_youtube_host(url):
        return RouteKind.YOUTUBE_PLAYLIST

    # 3. Feed-shaped URLs.
    if looks_like_feed_url(url):
        return RouteKind.RSS_FEED

    # 4. Default: treat as a generic web page.
    return RouteKind.WEBPAGE


def route_to_source(kind: RouteKind) -> ContentSource:
    """Map a :class:`RouteKind` to the storage-level :class:`ContentSource`.

    Used when persisting the ``source_type`` of a shared URL so the row reflects
    how it was actually handled.
    """
    return {
        RouteKind.YOUTUBE_VIDEO: ContentSource.YOUTUBE,
        RouteKind.YOUTUBE_PLAYLIST: ContentSource.YOUTUBE,
        RouteKind.RSS_FEED: ContentSource.RSS,
        RouteKind.WEBPAGE: ContentSource.WEBPAGE,
    }[kind]


def _is_youtube_host(url: str) -> bool:
    """Return True if *url*'s host is a YouTube domain."""
    host = urlsplit(url).netloc.lower()
    # Strip a leading userinfo/port if present is unnecessary for host checks here.
    return (
        host == "youtube.com"
        or host.endswith(".youtube.com")
        or host == "youtu.be"
        or host.endswith(".youtu.be")
    )
