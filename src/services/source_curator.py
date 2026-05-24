"""Source curation: health-check RSS feeds and blog scrapers, then safely
disable dead sources and fix fixable URLs in the hand-curated sources.d/ YAML.

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
    if status_code in _BLOCKED_CODES:
        return FeedHealth(url, name, FeedStatus.BLOCKED, str(status_code))
    if status_code >= 400:
        return FeedHealth(url, name, FeedStatus.FAIL_HTTP, str(status_code))

    parsed = feedparser.parse(text)
    count = len(parsed.entries)
    if count == 0:
        return FeedHealth(url, name, FeedStatus.EMPTY, f"{status_code} 0-entries")

    newest = _newest_entry_date(parsed)
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
            if fix_urls and (fixed := _reddit_rss_fix(r.url)):
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
_ENABLED_LINE = re.compile(r"^(?P<indent>\s*)enabled:\s*\S+\s*$")


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
