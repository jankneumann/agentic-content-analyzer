"""CLI commands for curating ingestion sources.

Usage:
    aca curate rss                 # health-check rss.yaml (report only)
    aca curate rss --apply         # disable dead feeds, fix Reddit URLs
    aca curate rss --disable-stale # also disable feeds idle > --stale-days
    aca curate blog                # validate blog discovery + overlap report

Report-only by default; mutations are gated behind --apply and preserve
comments/ordering via line-based edits (see src/services/source_curator.py).
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
_BLOGS_FILE = Path("sources.d/blogs.yaml")


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
    from src.services.source_curator import (
        FeedStatus,
        apply_plan_to_file,
        build_curation_plan,
        check_rss_feeds,
    )

    sources = _load_sources().get_rss_sources()
    if not sources:
        output_result("No RSS sources found.", success=False)
        raise typer.Exit(1)

    results = asyncio.run(
        check_rss_feeds(sources, stale_days=stale_days, concurrency=concurrency, timeout=timeout)
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

    typer.echo(f"Checked {len(results)} feeds in {file}:")
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
) -> None:
    """Search the web for relocated feeds (proposal-only — does not modify files).

    Investigates disabled feeds by default, web-searching for a live replacement
    and verifying freshness. Review the proposals, then update rss.yaml by hand.
    """
    from src.config.sources import RSSSource
    from src.services.source_curator import find_moved_feeds

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

    if is_json_mode():
        output_result(
            {
                "investigated": len(candidates),
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
    typer.echo("\nProposal-only — verify each candidate, then update rss.yaml by hand.")


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
