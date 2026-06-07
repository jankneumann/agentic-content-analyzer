"""CLI commands for curating ingestion sources.

Usage:
    aca curate rss                  # health-check rss.yaml (report only)
    aca curate rss --apply          # disable dead feeds, fix Reddit URLs
    aca curate rss --disable-stale  # also disable feeds idle > --stale-days
    aca curate youtube-rss          # health-check youtube_rss.yaml (report only)
    aca curate youtube-rss --apply  # disable dead channels, fix channel-page URLs
    aca curate youtube-rss --via-api  # check via the YouTube Data API (needs a key)
    aca curate blog                 # validate blog discovery + overlap report
    aca curate find-moved           # web-search for relocated feeds (report only)
    aca curate find-moved --apply   # re-enable live-again feeds, rewrite moved URLs

``rss`` and ``youtube-rss`` share one health-check/plan/apply engine (blog and
YouTube channel feeds are both RSS/Atom); they differ only in which source file
and source type they target. Report-only by default; mutations are gated behind
--apply and preserve comments/ordering via line-based edits (see
src/services/source_curator.py).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer

from src.cli.output import is_json_mode, output_result

app = typer.Typer(
    name="curate",
    help="Health-check and curate ingestion sources (RSS feeds, blog scrapers).",
    no_args_is_help=True,
)

_RSS_FILE = Path("sources.d/rss.yaml")
_YOUTUBE_RSS_FILE = Path("sources.d/youtube_rss.yaml")
_BLOGS_FILE = Path("sources.d/blogs.yaml")

# YouTube rate-limits aggressive concurrent fetches with 429s far sooner than
# blog CDNs, so the youtube-rss command checks more gently by default.
_YOUTUBE_DEFAULT_CONCURRENCY = 10


def _load_sources():  # type: ignore[no-untyped-def]
    from src.config.sources import load_sources_config

    return load_sources_config()


@app.command("rss")
def curate_rss(
    file: Annotated[
        Path,
        typer.Option("--file", help="RSS sources file to curate."),
    ] = _RSS_FILE,
    stale_days: Annotated[
        int,
        typer.Option("--stale-days", help="Flag feeds with no post in N days as stale."),
    ] = 180,
    disable_stale: Annotated[
        bool,
        typer.Option("--disable-stale", help="Also disable stale feeds (off by default)."),
    ] = False,
    disable_empty: Annotated[
        bool,
        typer.Option(
            "--disable-empty/--no-disable-empty",
            help="Disable feeds that return 200 but no entries (Reddit fixed, arXiv kept).",
        ),
    ] = True,
    disable_blocked: Annotated[
        bool,
        typer.Option(
            "--disable-blocked",
            help="Also disable BLOCKED feeds (403/429). Off by default — usually rate-limit, not dead.",
        ),
    ] = False,
    fix_urls: Annotated[
        bool,
        typer.Option("--fix-urls/--no-fix-urls", help="Rewrite fixable URLs (e.g. Reddit /.rss)."),
    ] = True,
    apply: Annotated[
        bool,
        typer.Option("--apply", help="Write changes to the file (default: dry-run report only)."),
    ] = False,
    concurrency: Annotated[
        int,
        typer.Option("--concurrency", help="Max concurrent feed fetches."),
    ] = 30,
    timeout: Annotated[
        float,
        typer.Option("--timeout", help="Per-feed fetch timeout in seconds."),
    ] = 15.0,
) -> None:
    """Health-check RSS feeds and optionally disable dead ones / fix Reddit URLs."""
    sources = _load_sources().get_rss_sources()
    if not sources:
        output_result("No RSS sources found.", success=False)
        raise typer.Exit(1)

    _run_feed_curation(
        sources,
        file=file,
        stale_days=stale_days,
        disable_stale=disable_stale,
        disable_empty=disable_empty,
        disable_blocked=disable_blocked,
        fix_urls=fix_urls,
        apply=apply,
        concurrency=concurrency,
        timeout=timeout,
    )


@app.command("youtube-rss")
def curate_youtube_rss(
    file: Annotated[
        Path,
        typer.Option("--file", help="YouTube RSS sources file to curate."),
    ] = _YOUTUBE_RSS_FILE,
    stale_days: Annotated[
        int,
        typer.Option("--stale-days", help="Flag channels with no upload in N days as stale."),
    ] = 180,
    disable_stale: Annotated[
        bool,
        typer.Option("--disable-stale", help="Also disable stale channels (off by default)."),
    ] = False,
    disable_empty: Annotated[
        bool,
        typer.Option(
            "--disable-empty/--no-disable-empty",
            help="Disable channels that return 200 but no videos (channel-page URLs fixed).",
        ),
    ] = True,
    disable_blocked: Annotated[
        bool,
        typer.Option(
            "--disable-blocked",
            help="Also disable BLOCKED channels (403/429). Off by default — usually rate-limit.",
        ),
    ] = False,
    fix_urls: Annotated[
        bool,
        typer.Option(
            "--fix-urls/--no-fix-urls",
            help="Rewrite channel-page URLs (/channel/UC...) to the videos.xml feed.",
        ),
    ] = True,
    apply: Annotated[
        bool,
        typer.Option("--apply", help="Write changes to the file (default: dry-run report only)."),
    ] = False,
    concurrency: Annotated[
        int,
        typer.Option("--concurrency", help="Max concurrent feed fetches."),
    ] = _YOUTUBE_DEFAULT_CONCURRENCY,
    timeout: Annotated[
        float,
        typer.Option("--timeout", help="Per-feed fetch timeout in seconds."),
    ] = 15.0,
    via_api: Annotated[
        bool | None,
        typer.Option(
            "--via-api/--via-rss",
            help="Check through the YouTube Data API instead of the public feed. "
            "Default: auto (API when a key is configured, else RSS).",
        ),
    ] = None,
    use_oauth: Annotated[
        bool,
        typer.Option(
            "--oauth",
            help="Use OAuth instead of an API key (only needed for private playlists).",
        ),
    ] = False,
) -> None:
    """Health-check YouTube channel RSS feeds and optionally disable dead channels.

    YouTube channel feeds (``youtube.com/feeds/videos.xml?channel_id=...``) are
    ordinary Atom feeds, so by default this reuses the same engine as
    ``curate rss``: deleted/terminated channels surface as FAIL_HTTP (404) and get
    disabled; 429s are kept-flagged as rate-limiting (not dead); and a pasted
    channel-page URL (``/channel/UC...``) is auto-rewritten to its feed.

    The public feed endpoint is bot-blocked from datacenter IPs, so when a Data
    API key (``YOUTUBE_API_KEY``/``GOOGLE_API_KEY``) is configured this checks via
    the authenticated API instead — sidestepping the block and distinguishing
    dead channels from throttling precisely. Force the transport with
    ``--via-api`` / ``--via-rss``; non-YouTube feeds in the file fall back to a
    plain fetch automatically.
    """
    sources = _load_sources().get_youtube_rss_sources()
    if not sources:
        output_result("No YouTube RSS sources found.", success=False)
        raise typer.Exit(1)

    # Auto: prefer the API when credentials exist (or OAuth requested), since the
    # public feed is unreliable from server IPs; fall back to RSS otherwise.
    if via_api is None:
        from src.config.settings import get_settings

        via_api = use_oauth or bool(get_settings().get_youtube_api_key())

    _run_feed_curation(
        sources,
        file=file,
        stale_days=stale_days,
        disable_stale=disable_stale,
        disable_empty=disable_empty,
        disable_blocked=disable_blocked,
        fix_urls=fix_urls,
        apply=apply,
        concurrency=concurrency,
        timeout=timeout,
        feed_noun="channels",
        via_api=via_api,
        use_oauth=use_oauth,
    )


@app.command("blog")
def curate_blog(
    max_links: Annotated[
        int,
        typer.Option("--max-links", help="Max links to attempt to discover per blog."),
    ] = 10,
) -> None:
    """Validate that blog sources yield discoverable post links, and flag overlap with RSS."""
    from src.services.source_curator import check_blog_sources, detect_overlaps

    config = _load_sources()
    blog_sources = config.get_blog_sources()
    if not blog_sources:
        output_result("No blog sources found.", success=False)
        raise typer.Exit(1)

    health = check_blog_sources(blog_sources, max_links=max_links)
    overlaps = detect_overlaps(config.get_rss_sources(), blog_sources)

    if is_json_mode():
        output_result(
            {
                "blogs": [
                    {
                        "name": h.name,
                        "url": h.url,
                        "links": h.links_found,
                        "ok": h.ok,
                        "detail": h.detail,
                    }
                    for h in health
                ],
                "overlaps": [
                    {"domain": o.domain, "rss": o.rss_urls, "blogs": o.blog_urls} for o in overlaps
                ],
            }
        )
        return

    ok = [h for h in health if h.ok]
    bad = [h for h in health if not h.ok]
    typer.echo(f"Validated {len(health)} blog sources ({len(ok)} ok, {len(bad)} need attention):\n")
    for h in health:
        marker = "ok " if h.ok else "!! "
        detail = f"  ({h.detail})" if h.detail else ""
        typer.echo(f"  {marker}{h.links_found:>2} links  {h.name}{detail}")

    if overlaps:
        typer.echo(
            f"\nDomains present in BOTH rss.yaml and blogs.yaml ({len(overlaps)}) "
            "— consider dropping the blog entry if the feed covers it:"
        )
        for o in overlaps:
            typer.echo(f"  {o.domain}")
            for u in o.rss_urls:
                typer.echo(f"    rss:  {u}")
            for u in o.blog_urls:
                typer.echo(f"    blog: {u}")
    else:
        typer.echo("\nNo domain overlap between rss.yaml and blogs.yaml.")


@app.command("find-moved")
def find_moved(
    file: Annotated[
        Path,
        typer.Option("--file", help="RSS sources file to update with --apply."),
    ] = _RSS_FILE,
    limit: Annotated[
        int,
        typer.Option("--limit", help="Max feeds to investigate (web search has per-call cost)."),
    ] = 20,
    include_stale: Annotated[
        bool,
        typer.Option(
            "--include-stale",
            help="Also investigate enabled-but-stale feeds, not just disabled ones.",
        ),
    ] = False,
    stale_days: Annotated[
        int,
        typer.Option("--stale-days", help="A candidate must have a post newer than N days."),
    ] = 180,
    apply: Annotated[
        bool,
        typer.Option(
            "--apply",
            help="Re-enable live-again feeds and rewrite relocated URLs (default: report only).",
        ),
    ] = False,
) -> None:
    """Search the web for relocated feeds, then optionally re-enable them.

    Investigates disabled feeds by default, web-searching for a live replacement
    and verifying freshness AND identity. Report-only by default; with --apply,
    re-enables live-again feeds and rewrites the URL of relocated ones in-place
    (comment-preserving). Always review the proposals before applying.
    """
    from src.config.sources import RSSSource
    from src.services.source_curator import apply_relocations_to_file, find_moved_feeds

    # get_rss_sources() returns only enabled feeds; the recovery targets are the
    # *disabled* ones, so read config.sources directly.
    all_rss = [s for s in _load_sources().sources if isinstance(s, RSSSource)]
    targets = [s for s in all_rss if not s.enabled]
    if include_stale:
        targets += [s for s in all_rss if s.enabled]

    if not targets:
        output_result("No disabled feeds to investigate.", success=False)
        raise typer.Exit(1)

    try:
        provider = _resolve_search_provider()
    except RuntimeError as exc:
        output_result(str(exc), success=False)
        raise typer.Exit(1)

    candidates = find_moved_feeds(targets, provider=provider, stale_days=stale_days, limit=limit)
    found = [c for c in candidates if c.new_url]

    stats = {"reenabled": 0, "rewritten": 0, "changed": False}
    if apply and found:
        if not file.exists():
            output_result(f"Source file not found: {file}", success=False)
            raise typer.Exit(1)
        stats = apply_relocations_to_file(file, found, dry_run=False)

    if is_json_mode():
        output_result(
            {
                "file": str(file),
                "applied": apply,
                "investigated": len(candidates),
                "stats": stats,
                "found": [
                    {
                        "name": c.name,
                        "original": c.original_url,
                        "new_url": c.new_url,
                        "detail": c.detail,
                    }
                    for c in found
                ],
                "not_found": [
                    {"name": c.name, "original": c.original_url, "detail": c.detail}
                    for c in candidates
                    if not c.new_url
                ],
            }
        )
        return

    typer.echo(f"Investigated {len(candidates)} feeds — {len(found)} live candidate(s):\n")
    for c in found:
        if c.new_url == c.original_url:
            typer.echo(f"  {c.name}  [live again — re-enable]")
            typer.echo(f"    {c.original_url}  ({c.detail})")
        else:
            typer.echo(f"  {c.name}  [relocated]")
            typer.echo(f"    old: {c.original_url}")
            typer.echo(f"    new: {c.new_url}  ({c.detail})")
    if not found:
        typer.echo("  (none found)")

    if apply:
        verb = "Wrote" if stats["changed"] else "No changes to"
        typer.echo(
            f"\n{verb} {file} (reenabled={stats['reenabled']}, rewritten={stats['rewritten']})."
        )
    else:
        typer.echo("\nReport-only — verify each candidate, then re-run with --apply to write them.")


def _run_feed_curation(
    sources: list,
    *,
    file: Path,
    stale_days: int,
    disable_stale: bool,
    disable_empty: bool,
    disable_blocked: bool,
    fix_urls: bool,
    apply: bool,
    concurrency: int,
    timeout: float,
    feed_noun: str = "feeds",
    via_api: bool = False,
    use_oauth: bool = False,
) -> None:
    """Shared health-check → plan → apply → report flow for RSS-style sources.

    Drives both ``curate rss`` and ``curate youtube-rss``: the differences are
    the source list/file handed in, the noun used in the report (``feeds`` vs
    ``channels``), and the transport — ``via_api`` health-checks YouTube sources
    through the authenticated Data API instead of fetching the public feed.
    """
    from src.services.source_curator import (
        FeedStatus,
        apply_plan_to_file,
        build_curation_plan,
    )

    if via_api:
        from src.services.source_curator import check_youtube_feeds_via_api

        try:
            results = check_youtube_feeds_via_api(
                sources, stale_days=stale_days, use_oauth=use_oauth
            )
        except RuntimeError as exc:
            output_result(str(exc), success=False)
            raise typer.Exit(1)
    else:
        from src.services.source_curator import check_rss_feeds

        results = asyncio.run(
            check_rss_feeds(
                sources, stale_days=stale_days, concurrency=concurrency, timeout=timeout
            )
        )
    plan = build_curation_plan(
        results,
        disable_empty=disable_empty,
        disable_stale=disable_stale,
        disable_blocked=disable_blocked,
        fix_urls=fix_urls,
    )

    if not file.exists():
        output_result(f"Source file not found: {file}", success=False)
        raise typer.Exit(1)
    stats = apply_plan_to_file(file, plan, dry_run=not apply)

    counts = {s.value: 0 for s in FeedStatus}
    for r in results:
        counts[r.status.value] += 1

    if is_json_mode():
        output_result(
            {
                "file": str(file),
                "applied": apply,
                "via": "youtube_api" if via_api else "rss",
                "checked": len(results),
                "counts": counts,
                "disabled": [
                    {"name": h.name, "url": h.url, "reason": h.detail} for h in plan.disable
                ],
                "rewritten": [{"url": h.url, "new_url": new} for h, new in plan.rewrite],
                "kept_flagged": [{"name": h.name, "url": h.url} for h in plan.keep_flagged],
                "stats": stats,
            }
        )
        return

    via = "YouTube Data API" if via_api else "RSS"
    typer.echo(f"Checked {len(results)} {feed_noun} in {file} (via {via}):")
    typer.echo("  " + "  ".join(f"{k}={v}" for k, v in counts.items() if v))
    _echo_group("Will disable" if not apply else "Disabled", plan.disable)
    if plan.rewrite:
        label = "Will fix URL" if not apply else "Fixed URL"
        typer.echo(f"\n{label} ({len(plan.rewrite)}):")
        for h, new in plan.rewrite:
            typer.echo(f"  {h.url}\n    -> {new}")
    if plan.keep_flagged:
        typer.echo(f"\nKept (needs review, not auto-disabled) ({len(plan.keep_flagged)}):")
        for h in plan.keep_flagged:
            typer.echo(f"  [{h.detail}] {h.name}  {h.url}")

    if apply:
        verb = "Wrote" if stats["changed"] else "No changes to"
        typer.echo(
            f"\n{verb} {file} (disabled={stats['disabled']}, rewritten={stats['rewritten']})."
        )
    else:
        typer.echo("\nDry run — re-run with --apply to write these changes.")


def _resolve_search_provider() -> object:
    """Return a configured web-search provider or raise with guidance."""
    from src.config.settings import get_settings
    from src.services.web_search import get_web_search_provider

    s = get_settings()
    provider_name = getattr(s, "web_search_provider", "tavily")
    key_attr = {
        "tavily": "tavily_api_key",
        "perplexity": "perplexity_api_key",
        "grok": "xai_api_key",
    }.get(provider_name)
    if key_attr and not getattr(s, key_attr, None):
        raise RuntimeError(
            f"No API key for web_search_provider '{provider_name}'. "
            "Set the key in .secrets.yaml and run under a PROFILE (e.g. PROFILE=local)."
        )
    return get_web_search_provider()


def _echo_group(label: str, items: list) -> None:
    if not items:
        return
    typer.echo(f"\n{label} ({len(items)}):")
    for h in items:
        typer.echo(f"  [{h.detail}] {h.name}  {h.url}")
