"""Source curation: health-check RSS feeds (blog *and* YouTube channel feeds)
and blog scrapers, then safely disable dead sources and fix fixable URLs in the
hand-curated sources.d/ YAML.

The same engine serves blog RSS (``rss.yaml``) and YouTube channel RSS
(``youtube_rss.yaml``): both are real RSS/Atom feeds whose source objects expose
``url``/``name``/``enabled``, so classification and the line-based YAML mutation
are shared. Only the EMPTY-feed URL fixes are source-flavored (Reddit ``/.rss``,
YouTube channel-page → ``feeds/videos.xml``).

Two concerns kept separate:
  - **classify**: fetch each feed/blog and bucket it (OK/FAIL/EMPTY/STALE).
  - **mutate**: line-based edits to sources.d/*.yaml that preserve comments and
    ordering (a full YAML round-trip would normalize quoting/spacing across the
    whole hand-curated file). Defaults to dry-run; the CLI gates writes behind
    an explicit --apply.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from urllib.parse import urlparse

import feedparser
import httpx

from src.utils.logging import get_logger

logger = get_logger(__name__)

# Browser-like headers: a custom bot UA is the first thing anti-bot filters
# reject, and feed CDNs (Cloudflare) are happy with a realistic browser UA.
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Accept": "application/rss+xml,application/xml,text/xml,*/*;q=0.8",
}

DEFAULT_STALE_DAYS = 180
DEFAULT_CONCURRENCY = 30
DEFAULT_TIMEOUT = 15.0


class FeedStatus(StrEnum):
    OK = "OK"
    FAIL_NET = "FAIL_NET"  # DNS/connection/timeout (after retry)
    FAIL_HTTP = "FAIL_HTTP"  # definitively-dead HTTP (404/410/400/401/451)
    BLOCKED = "BLOCKED"  # 403/429 — bot-detection or rate-limit, NOT necessarily dead
    EMPTY = "EMPTY"  # 200 but zero parseable entries
    STALE = "STALE"  # newest entry older than the stale threshold


# 403 Forbidden / 429 Too Many Requests usually mean bot-detection or
# rate-limiting (recoverable), not a dead feed — kept separate from dead 4xx.
_BLOCKED_CODES = frozenset({403, 429})
# Transient outcomes worth a second attempt before classifying.
_RETRY_CODES = frozenset({500, 502, 503, 504})


@dataclass
class FeedHealth:
    url: str
    name: str
    status: FeedStatus
    detail: str = ""
    entry_count: int = 0
    newest: datetime | None = None


class CurationAction(StrEnum):
    DISABLE = "disable"
    REWRITE_URL = "rewrite_url"
    KEEP_FLAGGED = "keep_flagged"  # health is bad but auto-action is unsafe


@dataclass
class CurationPlan:
    """The decided changes for one source file."""

    disable: list[FeedHealth] = field(default_factory=list)
    rewrite: list[tuple[FeedHealth, str]] = field(default_factory=list)
    keep_flagged: list[FeedHealth] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.disable and not self.rewrite


@dataclass
class BlogHealth:
    name: str
    url: str
    links_found: int
    ok: bool
    detail: str = ""


@dataclass
class Overlap:
    """A registrable domain present in both rss.yaml and blogs.yaml."""

    domain: str
    rss_urls: list[str]
    blog_urls: list[str]


# --- RSS health checking ---


def _newest_entry_date(parsed: feedparser.FeedParserDict) -> datetime | None:
    dates: list[datetime] = []
    for entry in parsed.entries:
        for key in ("published_parsed", "updated_parsed"):
            t = entry.get(key)
            if t:
                try:
                    dates.append(datetime(*t[:6], tzinfo=UTC))
                    break
                except (TypeError, ValueError):
                    pass
    return max(dates) if dates else None


async def _fetch_once(client, url, timeout):  # type: ignore[no-untyped-def]  # noqa: ASYNC109
    """Single fetch. Returns (status_code, text) or raises on network error."""
    resp = await client.get(url, headers=_HEADERS, follow_redirects=True, timeout=timeout)
    return resp.status_code, resp.text


async def _check_one_feed(
    client: httpx.AsyncClient,
    url: str,
    name: str,
    *,
    stale_days: int,
    timeout: float,  # noqa: ASYNC109
    sem: asyncio.Semaphore,
    retries: int = 1,
) -> FeedHealth:
    """Fetch and classify a feed, retrying transient failures.

    A single check is non-deterministic for rate-limited hosts, so transient
    outcomes (network error, 5xx) get a brief retry before being trusted.
    """
    async with sem:
        status_code: int | None = None
        text = ""
        net_err = ""
        for attempt in range(retries + 1):
            try:
                status_code, text = await _fetch_once(client, url, timeout)
                net_err = ""
                if status_code not in _RETRY_CODES:
                    break
            except Exception as exc:  # network errors are the signal here
                status_code = None
                net_err = type(exc).__name__
            if attempt < retries:
                await asyncio.sleep(1.5)

    if status_code is None:
        return FeedHealth(url, name, FeedStatus.FAIL_NET, net_err)
    return _classify_feed_response(url, name, status_code, text, stale_days=stale_days)


def _classify_feed_response(
    url: str, name: str, status_code: int, text: str, *, stale_days: int
) -> FeedHealth:
    """Bucket a fetched feed response (status + body) into a FeedHealth.

    The shared decision used by every transport: the async RSS checker, the sync
    fallback fetch, and (after mapping freshness) the YouTube Data API checker.
    """
    if status_code in _BLOCKED_CODES:
        return FeedHealth(url, name, FeedStatus.BLOCKED, str(status_code))
    if status_code >= 400:
        return FeedHealth(url, name, FeedStatus.FAIL_HTTP, str(status_code))

    parsed = feedparser.parse(text)
    count = len(parsed.entries)
    if count == 0:
        return FeedHealth(url, name, FeedStatus.EMPTY, f"{status_code} 0-entries")

    return _classify_freshness(url, name, count, _newest_entry_date(parsed), stale_days=stale_days)


def _classify_freshness(
    url: str, name: str, count: int, newest: datetime | None, *, stale_days: int
) -> FeedHealth:
    """OK vs STALE given the entry count and newest-entry timestamp.

    Transport-agnostic: ``count``/``newest`` come from feedparser for RSS or from
    the Data API's playlistItems for YouTube, so both share one staleness rule.
    """
    if newest and (datetime.now(UTC) - newest) > timedelta(days=stale_days):
        age = (datetime.now(UTC) - newest).days
        return FeedHealth(
            url, name, FeedStatus.STALE, f"newest {newest.date()} ({age}d ago)", count, newest
        )
    return FeedHealth(url, name, FeedStatus.OK, f"{count} entries", count, newest)


async def check_rss_feeds(
    sources: list,
    *,
    stale_days: int = DEFAULT_STALE_DAYS,
    concurrency: int = DEFAULT_CONCURRENCY,
    timeout: float = DEFAULT_TIMEOUT,  # noqa: ASYNC109
) -> list[FeedHealth]:
    """Concurrently health-check RSS sources. Only ``enabled`` sources are checked."""
    enabled = [s for s in sources if getattr(s, "enabled", True)]
    sem = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient() as client:
        tasks = [
            _check_one_feed(
                client,
                s.url,
                s.name or s.url,
                stale_days=stale_days,
                timeout=timeout,
                sem=sem,
            )
            for s in enabled
        ]
        return list(await asyncio.gather(*tasks))


# --- YouTube Data API health checking ---
#
# The public videos.xml feed is IP/bot-blocked from datacenters (a 403 that has
# nothing to do with whether the channel is alive). The Data API uses a different
# host (googleapis.com) and authenticates with an API key / OAuth, so it sidesteps
# that wall AND returns precise signals: a terminated channel yields an empty
# items list, and throttling yields explicit quotaExceeded/rateLimitExceeded
# reasons. Quota cost is ~1-2 units per channel against the default 10k/day.


def _parse_youtube_feed_ref(url: str) -> tuple[str, str] | None:
    """Extract the API lookup key from a YouTube feed URL.

    Returns ``(kind, value)`` where kind is ``channel`` / ``playlist`` / ``user``,
    or None when the URL isn't a recognizable YouTube channel/playlist reference
    (e.g. a non-YouTube RSS feed that happens to live in youtube_rss.yaml).
    """
    from urllib.parse import parse_qs

    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().removeprefix("www.")
    if not host.endswith("youtube.com"):
        return None

    qs = parse_qs(parsed.query)
    if "channel_id" in qs:
        return ("channel", qs["channel_id"][0])
    if "playlist_id" in qs:
        return ("playlist", qs["playlist_id"][0])
    if "user" in qs:
        return ("user", qs["user"][0])
    # channel-page URL form: /channel/UC...
    if m := _YT_CHANNEL_PATH.match(parsed.path):
        return ("channel", m.group("cid"))
    return None


def _http_error_status(exc: object) -> int | None:
    """Best-effort HTTP status from a googleapiclient HttpError across versions."""
    status = getattr(exc, "status_code", None)
    if status is None:
        status = getattr(getattr(exc, "resp", None), "status", None)
    return int(status) if status is not None else None


def _classify_youtube_http_error(exc: object, url: str, name: str) -> FeedHealth:
    """Map a YouTube Data API HttpError to a FeedHealth bucket.

    Throttling (429, or 403 with a quota/rate reason) is BLOCKED — recoverable,
    never auto-disabled. A definitive 4xx is FAIL_HTTP; 5xx is FAIL_NET (transient).
    """
    status = _http_error_status(exc)
    content = getattr(exc, "content", b"")
    if isinstance(content, bytes | bytearray):
        content = content.decode("utf-8", "ignore")
    blob = f"{exc} {content}".lower()
    is_throttle = any(t in blob for t in ("quota", "ratelimit", "rate limit", "userratelimit"))

    if status == 429 or (status == 403 and is_throttle):
        return FeedHealth(url, name, FeedStatus.BLOCKED, f"{status} throttled")
    if status and status >= 500:
        return FeedHealth(url, name, FeedStatus.FAIL_NET, f"HTTP {status}")
    return FeedHealth(url, name, FeedStatus.FAIL_HTTP, str(status or "HttpError"))


def _newest_playlist_date(items: list[dict]) -> datetime | None:
    """Newest publishedAt across playlistItems snippets (ISO-8601, e.g. ...Z)."""
    dates: list[datetime] = []
    for item in items:
        published = (item.get("snippet") or {}).get("publishedAt")
        if not published:
            continue
        try:
            dates.append(datetime.fromisoformat(published.replace("Z", "+00:00")))
        except ValueError:
            pass
    return max(dates) if dates else None


def _check_one_youtube_api(service: object, source: object, *, stale_days: int) -> FeedHealth:
    """Health-check a single YouTube source via the Data API."""
    from googleapiclient.errors import HttpError

    url = getattr(source, "url", "")
    name = getattr(source, "name", None) or url
    ref = _parse_youtube_feed_ref(url)
    if ref is None:
        # Not a YouTube channel/playlist ref (e.g. a plain RSS feed): fall back to
        # a synchronous fetch so mixed-source files aren't mis-flagged.
        return _check_one_feed_sync(url, name, stale_days=stale_days)

    kind, value = ref
    try:
        playlist_id = value
        if kind in ("channel", "user"):
            key = {"id": value} if kind == "channel" else {"forUsername": value}
            resp = service.channels().list(part="contentDetails", **key).execute()  # type: ignore[attr-defined]
            items = resp.get("items", [])
            if not items:
                return FeedHealth(url, name, FeedStatus.FAIL_HTTP, "channel not found")
            playlist_id = items[0]["contentDetails"]["relatedPlaylists"].get("uploads")
            if not playlist_id:
                return FeedHealth(url, name, FeedStatus.EMPTY, "no uploads playlist")

        resp = (
            service.playlistItems()  # type: ignore[attr-defined]
            .list(part="snippet", playlistId=playlist_id, maxResults=1)
            .execute()
        )
        items = resp.get("items", [])
        count = resp.get("pageInfo", {}).get("totalResults", len(items))
        if not items:
            return FeedHealth(url, name, FeedStatus.EMPTY, "no videos")
        return _classify_freshness(
            url, name, count, _newest_playlist_date(items), stale_days=stale_days
        )
    except HttpError as exc:
        return _classify_youtube_http_error(exc, url, name)
    except Exception as exc:  # network / transport errors
        return FeedHealth(url, name, FeedStatus.FAIL_NET, type(exc).__name__)


def _check_one_feed_sync(url: str, name: str, *, stale_days: int) -> FeedHealth:
    """Synchronous single-feed fetch+classify (used by the API path's fallback)."""
    try:
        with httpx.Client(follow_redirects=True, timeout=DEFAULT_TIMEOUT) as client:
            resp = client.get(url, headers=_HEADERS)
    except Exception as exc:
        return FeedHealth(url, name, FeedStatus.FAIL_NET, type(exc).__name__)
    return _classify_feed_response(url, name, resp.status_code, resp.text, stale_days=stale_days)


def check_youtube_feeds_via_api(
    sources: list,
    *,
    stale_days: int = DEFAULT_STALE_DAYS,
    use_oauth: bool = False,
    client: object | None = None,
) -> list[FeedHealth]:
    """Health-check YouTube channel/playlist feeds through the YouTube Data API v3.

    Authenticated alternative to ``check_rss_feeds`` for YouTube: avoids the
    bot-blocked public videos.xml endpoint and classifies dead vs throttled
    channels precisely. Requires an API key (YOUTUBE_API_KEY/GOOGLE_API_KEY) or,
    with ``use_oauth``, OAuth credentials (needed only for private playlists).

    Args:
        sources: source objects with ``url``/``name``/``enabled``.
        use_oauth: authenticate via OAuth (private content) instead of API key.
        client: a pre-built YouTubeClient (injected in tests); resolved otherwise.

    Raises:
        RuntimeError: if no API key / OAuth credentials are available.
    """
    enabled = [s for s in sources if getattr(s, "enabled", True)]
    if client is None:
        from src.ingestion.youtube import YouTubeClient

        client = YouTubeClient(use_oauth=use_oauth)
    try:
        service = client.service  # type: ignore[attr-defined]  # lazy-authenticates
    except ValueError as exc:  # no credentials configured
        raise RuntimeError(
            "YouTube Data API check needs YOUTUBE_API_KEY or GOOGLE_API_KEY "
            "(or OAuth credentials with --oauth). Set one in .secrets.yaml and run "
            "under a PROFILE (e.g. PROFILE=local)."
        ) from exc

    return [_check_one_youtube_api(service, s, stale_days=stale_days) for s in enabled]


# --- Curation policy ---


def _registrable_domain(url: str) -> str:
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def _reddit_rss_fix(url: str) -> str | None:
    """Reddit serves HTML unless the path ends in ``.rss``. Returns the fixed URL."""
    host = (urlparse(url).hostname or "").lower()
    if not host.endswith("reddit.com"):
        return None
    trimmed = url.rstrip("/")
    if trimmed.endswith(".rss"):
        return None
    return f"{trimmed}/.rss"


# A YouTube *channel page* URL — what people usually copy from the address bar —
# rather than the channel's Atom feed. ``/channel/UC...`` and (handle-less)
# ``/c/...`` legacy paths only; ``@handle`` can't be turned into a feed without
# resolving the channel id via the API, so it's left for manual review.
_YT_CHANNEL_PATH = re.compile(r"^/channel/(?P<cid>UC[\w-]+)/?$")


def _youtube_channel_rss_fix(url: str) -> str | None:
    """A YouTube channel-page URL (``/channel/UC...``) isn't a feed — feedparser
    yields 0 entries (EMPTY). Rewrite it to the channel's Atom feed.

    Returns the fixed feed URL, or None when the URL is already a feed (or not a
    recognizable YouTube channel-page URL).
    """
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().removeprefix("www.")
    if host not in ("youtube.com", "m.youtube.com"):
        return None
    m = _YT_CHANNEL_PATH.match(parsed.path)
    if not m:
        return None
    return f"https://www.youtube.com/feeds/videos.xml?channel_id={m.group('cid')}"


def _empty_feed_url_fix(url: str) -> str | None:
    """Best-effort rewrite for a feed that returned 200 but 0 entries, trying the
    source-flavored fixers in turn. Returns the fixed URL or None."""
    return _reddit_rss_fix(url) or _youtube_channel_rss_fix(url)


def build_curation_plan(
    results: list[FeedHealth],
    *,
    disable_failing: bool = True,
    disable_empty: bool = True,
    disable_stale: bool = False,
    disable_blocked: bool = False,
    fix_urls: bool = True,
) -> CurationPlan:
    """Turn raw health results into a decided set of edits.

    Exemptions baked in regardless of flags:
      - Reddit EMPTY feeds are *rewritten* (add ``/.rss``), never disabled.
      - YouTube channel-page EMPTY URLs (``/channel/UC...``) are *rewritten* to
        the channel's ``feeds/videos.xml`` feed, never disabled.
      - arXiv EMPTY feeds are *kept and flagged* — they return rss+xml but
        feedparser yields 0 entries (format quirk), so disabling would be wrong.
      - BLOCKED (403/429) feeds are *kept and flagged* by default — the block is
        usually bot-detection or rate-limiting, not a dead feed. Opt in with
        ``disable_blocked`` to treat them as failures.
    """
    plan = CurationPlan()
    for r in results:
        if r.status in (FeedStatus.FAIL_NET, FeedStatus.FAIL_HTTP):
            if disable_failing:
                plan.disable.append(r)
        elif r.status == FeedStatus.BLOCKED:
            (plan.disable if disable_blocked else plan.keep_flagged).append(r)
        elif r.status == FeedStatus.EMPTY:
            if fix_urls and (fixed := _empty_feed_url_fix(r.url)):
                plan.rewrite.append((r, fixed))
            elif "arxiv.org" in (urlparse(r.url).hostname or ""):
                plan.keep_flagged.append(r)
            elif disable_empty:
                plan.disable.append(r)
        elif r.status == FeedStatus.STALE and disable_stale:
            plan.disable.append(r)
    return plan


# --- Line-based YAML mutation (comment-preserving) ---

# Matches a `url:` line in either `- url: X` or `  url: X` form, capturing the
# leading whitespace, optional list dash, and the (possibly quoted) value.
_URL_LINE = re.compile(r"^(?P<indent>\s*)(?P<dash>- )?url:\s*(?P<value>\S.*?)\s*$")
_LIST_ITEM = re.compile(r"^\s*- ")
_ENABLED_LINE = re.compile(r"^(?P<indent>\s*)enabled:\s*(?P<value>\S+)\s*$")


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _entry_bounds(lines: list[str], url_idx: int) -> tuple[int, int]:
    """Return [start, end) line range of the list entry containing line ``url_idx``."""
    start = url_idx
    while start > 0 and not _LIST_ITEM.match(lines[start]):
        start -= 1
    end = url_idx + 1
    while end < len(lines) and not _LIST_ITEM.match(lines[end]):
        end += 1
    return start, end


def apply_plan_to_text(text: str, plan: CurationPlan) -> tuple[str, dict]:
    """Apply a curation plan to YAML text via surgical line edits.

    Index-based (not streaming) so a disable works whether the entry's
    ``enabled:`` key sits before or after its ``url:`` line. Idempotent:
    re-running overwrites an already-false flag in place rather than inserting
    a duplicate key.

    Returns (new_text, stats).
    """
    disable_urls = {h.url for h in plan.disable}
    rewrite_map = {h.url: new for h, new in plan.rewrite}
    lines = text.splitlines(keepends=True)

    overwrites: dict[int, str] = {}  # line index -> replacement (existing enabled: key)
    inserts: dict[int, str] = {}  # after this line index, insert text
    disabled = 0
    rewritten = 0

    for i, line in enumerate(lines):
        m = _URL_LINE.match(line.rstrip("\n"))
        if not m:
            continue
        value = _unquote(m.group("value"))

        if value in rewrite_map:
            suffix = "\n" if line.endswith("\n") else ""
            lines[i] = f"{line[: m.start('value')]}{rewrite_map[value]}{suffix}"
            rewritten += 1
            continue

        if value in disable_urls:
            start, end = _entry_bounds(lines, i)
            existing = next(
                (j for j in range(start, end) if _ENABLED_LINE.match(lines[j].rstrip("\n"))),
                None,
            )
            if existing is not None:
                ind = _ENABLED_LINE.match(lines[existing].rstrip("\n")).group("indent")
                overwrites[existing] = f"{ind}enabled: false\n"
            else:
                key_col = len(m.group("indent")) + (2 if m.group("dash") else 0)
                inserts[i] = f"{' ' * key_col}enabled: false\n"
            disabled += 1

    for idx, repl in overwrites.items():
        lines[idx] = repl

    out: list[str] = []
    for i, line in enumerate(lines):
        out.append(line)
        if i in inserts:
            out.append(inserts[i])

    return "".join(out), {"disabled": disabled, "rewritten": rewritten}


def apply_plan_to_file(file_path: Path, plan: CurationPlan, *, dry_run: bool = True) -> dict:
    """Apply a plan to a sources file. No-op write when dry_run."""
    text = file_path.read_text()
    new_text, stats = apply_plan_to_text(text, plan)
    stats["changed"] = new_text != text
    if not dry_run and stats["changed"]:
        file_path.write_text(new_text)
    return stats


# --- Blog scraper validation ---


def check_blog_sources(sources: list, *, max_links: int = 10) -> list[BlogHealth]:
    """Validate that each blog source's index page yields discoverable post links."""
    from src.ingestion.blog_scraper import BlogScrapingClient

    out: list[BlogHealth] = []
    enabled = [s for s in sources if getattr(s, "enabled", True)]
    with BlogScrapingClient() as client:
        for s in enabled:
            name = s.name or s.url
            try:
                html = client.fetch_index_page(s.url)
                links = client.discover_post_links(
                    html,
                    s.url,
                    link_selector=getattr(s, "link_selector", None),
                    link_pattern=getattr(s, "link_pattern", None),
                    max_links=max_links,
                )
                ok = len(links) > 0
                detail = "" if ok else "no links discovered (check selector/pattern or JS-rendered)"
                out.append(BlogHealth(name, s.url, len(links), ok, detail))
            except Exception as exc:
                out.append(BlogHealth(name, s.url, 0, False, type(exc).__name__))
    return out


# --- Relocation discovery (find moved feeds via web search) ---

# Result hosts that are directories/social, never the publication's own feed.
_AGGREGATOR_HOSTS = frozenset(
    {
        "muckrack.com",
        "feeder.co",
        "feedspot.com",
        "rss.com",
        "x.com",
        "twitter.com",
        "linkedin.com",
        "facebook.com",
        "instagram.com",
        "wikipedia.org",
        "youtube.com",
        "crunchbase.com",
        "similarweb.com",
        "f6s.com",
    }
)
# Paths appended to a candidate host to guess its feed location.
_FEED_CANDIDATE_PATHS = ("/feed", "/rss", "/feed.xml", "/rss.xml", "/index.xml", "/atom.xml")

# Generic words/platform labels that don't identify a specific publication.
_IDENTITY_STOPWORDS = frozenset(
    {
        "blog",
        "news",
        "feed",
        "rss",
        "the",
        "ai",
        "data",
        "newsletter",
        "podcast",
        "updates",
        "posts",
        "medium",
        "substack",
        "wordpress",
        "blogspot",
        "github",
        "ghost",
        "beehiiv",
        "com",
        "www",
        "tech",
        "weekly",
        "daily",
    }
)


def _identity_tokens(name: str, url: str) -> set[str]:
    """Significant tokens identifying a publication: domain label + name words.

    Used to reject look-alive-but-unrelated feeds (a fresh feed on an unrelated
    domain found via an ambiguous web search).
    """
    tokens: set[str] = set()
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    labels = host.split(".")
    if len(labels) >= 2:
        tokens.add(labels[-2])  # registrable label, e.g. "anaconda", "semianalysis"
    for word in re.split(r"[^a-z0-9]+", name.lower()):
        tokens.add(word)
    return {t for t in tokens if len(t) >= 4 and t not in _IDENTITY_STOPWORDS}


@dataclass
class MovedCandidate:
    """A proposed relocation for a dead/stale feed (proposal-only — never auto-applied)."""

    original_url: str
    name: str
    new_url: str | None
    detail: str


def _candidate_feed_urls(result_urls: list[str], *, limit: int = 6) -> list[str]:
    """Derive feed-URL guesses from web-search result URLs.

    A result whose path already looks like a feed is used as-is; otherwise the
    result's host (minus known aggregators) seeds ``host + /feed`` style guesses.
    """
    candidates: list[str] = []
    seen: set[str] = set()

    def _add(url: str) -> None:
        if url not in seen:
            seen.add(url)
            candidates.append(url)

    for raw in result_urls:
        parsed = urlparse(raw)
        host = (parsed.hostname or "").lower()
        if not host or host.removeprefix("www.") in _AGGREGATOR_HOSTS:
            continue
        path = parsed.path.lower()
        if any(tok in path for tok in ("feed", "rss", ".xml", ".atom")):
            _add(raw)  # already a feed-looking URL
        else:
            base = f"{parsed.scheme or 'https'}://{host}"
            for suffix in _FEED_CANDIDATE_PATHS:
                _add(base + suffix)
    return candidates[:limit]


def find_moved_feeds(
    feeds: list,
    *,
    provider: object | None = None,
    stale_days: int = DEFAULT_STALE_DAYS,
    limit: int | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> list[MovedCandidate]:
    """For each dead/stale feed, web-search for a relocated feed and verify it.

    Proposal-only: returns the best fresh candidate per feed (or None). Never
    mutates source files — web-search guesses need a human eye before applying.

    Args:
        feeds: source objects with ``url`` and ``name`` (typically the disabled ones).
        provider: a WebSearchProvider; resolved from settings if None.
        stale_days: a candidate must have a post newer than this to count as live.
        limit: cap how many feeds to investigate (web search has per-call cost).
    """
    if provider is None:
        from src.services.web_search import get_web_search_provider

        provider = get_web_search_provider()

    targets = feeds[:limit] if limit else feeds
    out: list[MovedCandidate] = []

    with httpx.Client(headers=_HEADERS, follow_redirects=True, timeout=timeout) as client:
        for f in targets:
            name = getattr(f, "name", None) or getattr(f, "url", "")
            orig = getattr(f, "url", "")
            orig_host = (urlparse(orig).hostname or "").lower().removeprefix("www.")
            try:
                results = provider.search(f"{name} RSS feed", max_results=5)  # type: ignore[attr-defined]
            except Exception as exc:  # search failures shouldn't abort the batch
                out.append(MovedCandidate(orig, name, None, f"search error: {type(exc).__name__}"))
                continue

            best = _best_live_candidate(
                client,
                _candidate_feed_urls([r.url for r in results if r.url]),
                orig_host=orig_host,
                stale_days=stale_days,
                identity_tokens=_identity_tokens(name, orig),
            )
            out.append(best_to_candidate(orig, name, best))
    return out


def _identity_match(parsed: feedparser.FeedParserDict, cand_host: str, tokens: set[str]) -> bool:
    """True if the candidate feed plausibly belongs to the same publication.

    Requires a shared identity token in the feed title or candidate host. With
    no tokens to match on, fall back to permissive (let the caller decide).
    """
    if not tokens:
        return True
    haystack = f"{parsed.feed.get('title', '')} {cand_host}".lower()
    return any(tok in haystack for tok in tokens)


def _best_live_candidate(
    client: httpx.Client,
    candidate_urls: list[str],
    *,
    orig_host: str,
    stale_days: int,
    identity_tokens: set[str],
) -> tuple[str, str] | None:
    """Probe candidate feed URLs; return (url, detail) for the freshest live one
    that also matches the publication's identity (rejects unrelated live feeds)."""
    best: tuple[str, str, datetime] | None = None
    for url in candidate_urls:
        try:
            resp = client.get(url)
        except Exception as exc:
            logger.debug("probe failed for candidate %s: %s", url, type(exc).__name__)
            continue
        if resp.status_code >= 400:
            continue
        parsed = feedparser.parse(resp.text)
        if not parsed.entries:
            continue
        newest = _newest_entry_date(parsed)
        if not newest or (datetime.now(UTC) - newest) > timedelta(days=stale_days):
            continue
        cand_host = (urlparse(url).hostname or "").lower().removeprefix("www.")
        if not _identity_match(parsed, cand_host, identity_tokens):
            continue  # fresh but unrelated publication
        # Prefer a candidate on a different host than the (dead) original, and
        # the freshest such one; otherwise accept the first live candidate.
        detail = f"{len(parsed.entries)} entries, newest {newest.date()}"
        if (cand_host != orig_host and (best is None or newest > best[2])) or best is None:
            best = (url, detail, newest)
    return (best[0], best[1]) if best else None


def best_to_candidate(orig: str, name: str, best: tuple[str, str] | None) -> MovedCandidate:
    if best is None:
        return MovedCandidate(orig, name, None, "no fresh feed found")
    return MovedCandidate(orig, name, best[0], best[1])


def apply_relocations_to_text(text: str, candidates: list[MovedCandidate]) -> tuple[str, dict]:
    """Re-enable feeds found live again, rewriting the URL when relocated.

    The inverse of ``apply_plan_to_text``: for each candidate with a ``new_url``,
    locate the entry by its ``original_url``, then
      - rewrite the ``url:`` value when it relocated (new_url != original_url), and
      - flip ``enabled: false`` -> ``enabled: true`` to re-enable it.

    A feed with no ``enabled:`` line is already enabled, so only its URL is
    rewritten (reenabled count unaffected). Comment/ordering-preserving and
    idempotent, like ``apply_plan_to_text``. Returns (new_text, stats).
    """
    by_orig = {c.original_url: c for c in candidates if c.new_url}
    lines = text.splitlines(keepends=True)

    overwrites: dict[int, str] = {}  # line index -> replacement enabled: line
    reenabled = 0
    rewritten = 0

    for i, line in enumerate(lines):
        m = _URL_LINE.match(line.rstrip("\n"))
        if not m:
            continue
        value = _unquote(m.group("value"))
        cand = by_orig.get(value)
        if cand is None:
            continue

        if cand.new_url and cand.new_url != value:
            suffix = "\n" if line.endswith("\n") else ""
            lines[i] = f"{line[: m.start('value')]}{cand.new_url}{suffix}"
            rewritten += 1

        start, end = _entry_bounds(lines, i)
        existing = next(
            (j for j in range(start, end) if _ENABLED_LINE.match(lines[j].rstrip("\n"))),
            None,
        )
        if existing is not None:
            em = _ENABLED_LINE.match(lines[existing].rstrip("\n"))
            if em.group("value").lower() == "false":
                reenabled += 1
            overwrites[existing] = f"{em.group('indent')}enabled: true\n"

    for idx, repl in overwrites.items():
        lines[idx] = repl

    return "".join(lines), {"reenabled": reenabled, "rewritten": rewritten}


def apply_relocations_to_file(
    file_path: Path, candidates: list[MovedCandidate], *, dry_run: bool = True
) -> dict:
    """Apply relocations to a sources file. No-op write when dry_run."""
    text = file_path.read_text()
    new_text, stats = apply_relocations_to_text(text, candidates)
    stats["changed"] = new_text != text
    if not dry_run and stats["changed"]:
        file_path.write_text(new_text)
    return stats


# --- Overlap detection (rss.yaml vs blogs.yaml) ---


_FEED_SUFFIXES = (
    "/feed/",
    "/feed",
    "/rss/",
    "/rss",
    "/.rss",
    "/rss.xml",
    "/feed.xml",
    "/index.xml",
)


def _norm_host_path(url: str) -> tuple[str, str]:
    """Return (hostname, path) with feed markers and trailing slash stripped.

    Strips ``/feed``, ``/rss`` etc. and a ``?format=rss`` query so a feed URL and
    the blog index it belongs to normalize to the same host+path.
    """
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().removeprefix("www.")
    path = parsed.path.rstrip("/")
    for suffix in _FEED_SUFFIXES:
        if path.endswith(suffix.rstrip("/")):
            path = path[: -len(suffix.rstrip("/"))].rstrip("/")
            break
    return host, path or "/"


def detect_overlaps(rss_sources: list, blog_sources: list) -> list[Overlap]:
    """Find sites reachable via *both* a feed and a blog scraper.

    Matches on hostname AND a path-prefix relationship (one path is a prefix of
    the other after stripping feed markers), so sibling sub-blogs on a shared
    host — e.g. ``aws.amazon.com/blogs/machine-learning`` vs
    ``aws.amazon.com/blogs/architecture`` — are NOT treated as redundant.
    """
    rss_norm = [(_norm_host_path(s.url), s.url) for s in rss_sources]

    overlaps: list[Overlap] = []
    for b in blog_sources:
        (bhost, bpath) = _norm_host_path(b.url)
        matches = [
            rurl
            for (rhost, rpath), rurl in rss_norm
            if rhost == bhost and (rpath.startswith(bpath) or bpath.startswith(rpath))
        ]
        if matches:
            overlaps.append(Overlap(bhost, matches, [b.url]))
    return overlaps
