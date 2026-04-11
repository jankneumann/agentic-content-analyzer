"""Migrate legacy config files to unified sources.d/ or sources.yaml format.

Parses rss_feeds.txt, youtube_playlists.txt, and AI-ML-Data-News.md into
the unified YAML source configuration used by src.config.sources.

Usage:
    python -m src.config.migrate_sources [--from-markdown AI-ML-Data-News.md] \
        [--output-dir sources.d] [--output sources.yaml]
"""

import argparse
import logging
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from src.config.sources import (
    GmailSource,
    PodcastSource,
    RSSSource,
    YouTubePlaylistSource,
    YouTubeRSSSource,
)

logger = logging.getLogger(__name__)

# Regex for markdown entries: - [Name](URL) - Description (RSS feed: RSS_URL)
ENTRY_PATTERN = re.compile(r"- \[([^\]]+)\]\(([^)]+)\)\s*-?\s*(.*?)(?:\(RSS feed:\s*([^)]+)\))?$")


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def parse_rss_feeds(path: Path) -> list[dict[str, Any]]:
    """Parse rss_feeds.txt: one URL per line, # comments.

    Returns a list of dicts suitable for RSSSource validation.
    """
    entries: list[dict[str, Any]] = []
    if not path.exists():
        logger.warning("RSS feeds file not found: %s", path)
        return entries

    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Strip trailing quote characters (some files have artifacts)
            url = line.rstrip('"').rstrip("'")
            entries.append({"type": "rss", "url": url})

    logger.info("Parsed %d RSS feeds from %s", len(entries), path)
    return entries


def parse_youtube_playlists(path: Path) -> list[dict[str, Any]]:
    """Parse youtube_playlists.txt: PLAYLIST_ID | description format.

    Returns a list of dicts suitable for YouTubePlaylistSource validation.
    """
    entries: list[dict[str, Any]] = []
    if not path.exists():
        logger.warning("YouTube playlists file not found: %s", path)
        return entries

    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "|" in line:
                playlist_id, description = line.split("|", 1)
                entries.append(
                    {
                        "type": "youtube_playlist",
                        "id": playlist_id.strip(),
                        "name": description.strip(),
                    }
                )
            else:
                entries.append(
                    {
                        "type": "youtube_playlist",
                        "id": line.strip(),
                    }
                )

    logger.info("Parsed %d YouTube playlists from %s", len(entries), path)
    return entries


def _parse_markdown_section(
    lines: list[str],
    start_line: int,
    end_line: int,
    source_type: str,
    extra_fields: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Parse a section of AI-ML-Data-News.md into source entries.

    Each entry follows: - [Name](URL) - Description (RSS feed: RSS_URL)

    Args:
        lines: All lines from the markdown file.
        start_line: 1-based start line number (inclusive).
        end_line: 1-based end line number (inclusive).
        source_type: The source type to assign (rss, podcast, youtube_rss).
        extra_fields: Additional fields to merge into each entry.

    Returns:
        List of source entry dicts.
    """
    entries: list[dict[str, Any]] = []
    extra = extra_fields or {}

    # Convert to 0-based indexing
    for line in lines[start_line - 1 : end_line]:
        line = line.strip()
        if not line.startswith("- ["):
            continue

        match = ENTRY_PATTERN.match(line)
        if not match:
            logger.debug("Skipping unmatched line: %s", line[:80])
            continue

        name, site_url, _description, rss_url = match.groups()

        # Use RSS feed URL if available, otherwise fall back to site URL
        url = rss_url.strip() if rss_url else site_url.strip()
        entry: dict[str, Any] = {
            "type": source_type,
            "name": name.strip(),
            "url": url,
            **extra,
        }
        entries.append(entry)

    return entries


def parse_markdown(path: Path) -> dict[str, list[dict[str, Any]]]:
    """Parse AI-ML-Data-News.md into categorized source entries.

    Detects section boundaries by scanning for H2 headers containing keywords:
      - "News" or "RSS" -> type: rss
      - "Podcast" -> type: podcast
      - "Video" or "YouTube" -> type: youtube_rss

    Returns:
        Dict with keys 'rss', 'podcasts', 'youtube_rss' mapping to entry lists.
    """
    if not path.exists():
        logger.warning("Markdown file not found: %s", path)
        return {"rss": [], "podcasts": [], "youtube_rss": []}

    lines = path.read_text().splitlines()
    total_lines = len(lines)

    if total_lines == 0:
        return {"rss": [], "podcasts": [], "youtube_rss": []}

    # Auto-detect section boundaries from H2 headers
    # Map section type -> (start_line, end_line) using 1-based indexing
    sections: list[tuple[str, int]] = []  # (type, start_line)

    for i, line in enumerate(lines, 1):
        stripped = line.strip().lower()
        if not stripped.startswith("## "):
            continue
        header = stripped[3:]
        if "podcast" in header:
            sections.append(("podcast", i))
        elif "video" in header or "youtube" in header:
            sections.append(("youtube_rss", i))
        elif "news" in header or "rss" in header:
            sections.append(("rss", i))

    # If no sections detected, treat entire file as RSS
    if not sections:
        return {"rss": [], "podcasts": [], "youtube_rss": []}

    # Build section ranges
    rss_entries: list[dict[str, Any]] = []
    podcast_entries: list[dict[str, Any]] = []
    youtube_entries: list[dict[str, Any]] = []

    for idx, (section_type, start) in enumerate(sections):
        end = sections[idx + 1][1] - 1 if idx + 1 < len(sections) else total_lines

        extra: dict[str, Any] | None = None
        if section_type == "podcast":
            extra = {"transcribe": False}

        entries = _parse_markdown_section(
            lines,
            start,
            end,
            section_type,
            extra_fields=extra,
        )

        if section_type == "rss":
            rss_entries.extend(entries)
        elif section_type == "podcast":
            podcast_entries.extend(entries)
        elif section_type == "youtube_rss":
            youtube_entries.extend(entries)

    logger.info("Parsed %d RSS entries from markdown news section", len(rss_entries))
    logger.info("Parsed %d podcast entries from markdown", len(podcast_entries))
    logger.info("Parsed %d YouTube RSS entries from markdown", len(youtube_entries))

    return {
        "rss": rss_entries,
        "podcasts": podcast_entries,
        "youtube_rss": youtube_entries,
    }


# Alias for test compatibility
parse_markdown_file = parse_markdown


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def deduplicate_sources(
    sources: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Deduplicate sources by URL (rss/podcast/youtube_rss) or ID (playlists).

    When duplicates exist, keep the entry with the richest metadata
    (the one with a 'name' field, preferring markdown-sourced entries).

    Args:
        sources: List of all source entry dicts.

    Returns:
        Deduplicated list preserving insertion order.
    """
    seen: dict[str, dict[str, Any]] = {}

    for entry in sources:
        # Determine the dedup key (type-aware: same URL but different type = distinct)
        source_type = entry.get("type", "unknown")
        if source_type == "youtube_playlist":
            key = f"playlist:{entry['id']}"
        else:
            key = f"{source_type}:url:{entry.get('url', '')}"

        if key in (f"{source_type}:url:", "playlist:"):
            continue

        if key in seen:
            existing = seen[key]
            # Keep the one with a name (richer metadata)
            if not existing.get("name") and entry.get("name"):
                seen[key] = entry
        else:
            seen[key] = entry

    return list(seen.values())


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------


def _dump_yaml(data: dict[str, Any]) -> str:
    """Serialize a dict to YAML with consistent formatting."""
    return str(yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True))


def _strip_type_from_entries(
    entries: list[dict[str, Any]], expected_type: str
) -> list[dict[str, Any]]:
    """Remove the 'type' key from entries when it matches the file default.

    This keeps individual entries concise since the type is set in defaults.
    """
    cleaned = []
    for entry in entries:
        e = dict(entry)
        if e.get("type") == expected_type:
            e.pop("type", None)
        cleaned.append(e)
    return cleaned


def _flatten_categorized(
    sources: dict[str, list[dict[str, Any]]] | list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert categorized dict to flat list, or pass through if already flat."""
    if isinstance(sources, list):
        return sources
    flat: list[dict[str, Any]] = []
    for entries in sources.values():
        flat.extend(entries)
    return flat


def write_sources_directory(
    all_sources: list[dict[str, Any]] | dict[str, list[dict[str, Any]]],
    output_dir: Path,
) -> None:
    """Write sources into sources.d/ directory with per-file organization.

    Creates:
      - _defaults.yaml: Global defaults
      - rss.yaml: All RSS sources
      - youtube.yaml: YouTube playlists and RSS sources
      - podcasts.yaml: Podcast sources
      - gmail.yaml: Gmail sources (template with default query)

    Args:
        all_sources: Deduplicated list of source entry dicts, or categorized dict.
        output_dir: Path to the sources.d/ directory.
    """
    all_sources = _flatten_categorized(all_sources)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Categorize sources
    rss = [s for s in all_sources if s.get("type") == "rss"]
    yt_playlists = [s for s in all_sources if s.get("type") == "youtube_playlist"]
    yt_rss = [s for s in all_sources if s.get("type") == "youtube_rss"]
    podcasts = [s for s in all_sources if s.get("type") == "podcast"]
    gmail = [s for s in all_sources if s.get("type") == "gmail"]

    # _defaults.yaml
    defaults_data = {
        "version": 1,
        "defaults": {
            "enabled": True,
            "max_entries": 10,
            "days_back": 7,
        },
    }
    (output_dir / "_defaults.yaml").write_text(_dump_yaml(defaults_data))
    logger.info("Wrote _defaults.yaml")

    # rss.yaml
    if rss:
        rss_data = {
            "defaults": {"type": "rss"},
            "sources": _strip_type_from_entries(rss, "rss"),
        }
        (output_dir / "rss.yaml").write_text(_dump_yaml(rss_data))
        logger.info("Wrote rss.yaml with %d sources", len(rss))

    # youtube.yaml
    yt_sources = yt_playlists + yt_rss
    if yt_sources:
        # YouTube has mixed types, so keep type on each entry
        yt_data = {
            "sources": yt_sources,
        }
        (output_dir / "youtube.yaml").write_text(_dump_yaml(yt_data))
        logger.info("Wrote youtube.yaml with %d sources", len(yt_sources))

    # podcasts.yaml
    if podcasts:
        podcasts_data = {
            "defaults": {"type": "podcast", "transcribe": False},
            "sources": _strip_type_from_entries(podcasts, "podcast"),
        }
        # Remove transcribe from individual entries since it's in defaults
        podcast_sources: list[dict[str, Any]] = podcasts_data["sources"]  # type: ignore[assignment]
        for entry in podcast_sources:
            entry.pop("transcribe", None)
        (output_dir / "podcasts.yaml").write_text(_dump_yaml(podcasts_data))
        logger.info("Wrote podcasts.yaml with %d sources", len(podcasts))

    # gmail.yaml (template)
    if gmail:
        gmail_data = {
            "defaults": {"type": "gmail"},
            "sources": _strip_type_from_entries(gmail, "gmail"),
        }
    else:
        gmail_data = {
            "defaults": {"type": "gmail"},
            "sources": [{"query": "label:newsletters-ai", "max_results": 50}],
        }
    (output_dir / "gmail.yaml").write_text(_dump_yaml(gmail_data))
    logger.info("Wrote gmail.yaml")


def write_sources_yaml(
    all_sources: list[dict[str, Any]] | dict[str, list[dict[str, Any]]],
    output_path: Path,
) -> None:
    """Write all sources into a single sources.yaml file.

    Args:
        all_sources: Deduplicated list of source entry dicts, or categorized dict.
        output_path: Path to write the merged YAML file.
    """
    all_sources = _flatten_categorized(all_sources)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "version": 1,
        "defaults": {
            "enabled": True,
            "max_entries": 10,
            "days_back": 7,
        },
        "sources": all_sources,
    }

    output_path.write_text(_dump_yaml(data))
    logger.info("Wrote %d sources to %s", len(all_sources), output_path)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_sources(sources: list[dict[str, Any]]) -> list[str]:
    """Validate source entries against Pydantic models.

    Returns a list of validation error messages (empty if all pass).
    """
    errors: list[str] = []
    type_map: dict[str, type[BaseModel]] = {
        "rss": RSSSource,
        "youtube_playlist": YouTubePlaylistSource,
        "youtube_rss": YouTubeRSSSource,
        "podcast": PodcastSource,
        "gmail": GmailSource,
    }

    for i, entry in enumerate(sources):
        source_type = entry.get("type", "unknown")
        model_cls = type_map.get(source_type)
        if model_cls is None:
            errors.append(f"Entry {i}: unknown type '{source_type}'")
            continue
        try:
            model_cls.model_validate(entry)
        except Exception as e:
            name = entry.get("name", entry.get("url", entry.get("id", "?")))
            errors.append(f"Entry {i} ({name}): {e}")

    return errors


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Migrate legacy config files to unified YAML source config.",
        prog="python -m src.config.migrate_sources",
    )
    parser.add_argument(
        "--from-markdown",
        type=Path,
        default=Path("AI-ML-Data-News.md"),
        help="Path to AI-ML-Data-News.md (default: AI-ML-Data-News.md)",
    )
    parser.add_argument(
        "--rss-feeds",
        type=Path,
        default=Path("rss_feeds.txt"),
        help="Path to rss_feeds.txt (default: rss_feeds.txt)",
    )
    parser.add_argument(
        "--youtube-playlists",
        type=Path,
        default=Path("youtube_playlists.txt"),
        help="Path to youtube_playlists.txt (default: youtube_playlists.txt)",
    )

    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory for sources.d/ layout (default: sources.d)",
    )
    output_group.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output path for single merged sources.yaml",
    )

    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Parse and validate without writing output files.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )

    return parser


def run(args: argparse.Namespace) -> None:
    """Execute the migration with parsed CLI arguments."""
    # --- Collect sources from all inputs ---
    all_sources: list[dict[str, Any]] = []

    # 1. Parse legacy text files
    all_sources.extend(parse_rss_feeds(args.rss_feeds))
    all_sources.extend(parse_youtube_playlists(args.youtube_playlists))

    # 2. Parse markdown file
    md_sources = parse_markdown(args.from_markdown)
    all_sources.extend(md_sources["rss"])
    all_sources.extend(md_sources["podcasts"])
    all_sources.extend(md_sources["youtube_rss"])

    logger.info("Total sources before dedup: %d", len(all_sources))

    # --- Deduplicate ---
    all_sources = deduplicate_sources(all_sources)
    logger.info("Total sources after dedup: %d", len(all_sources))

    # --- Validate ---
    errors = validate_sources(all_sources)
    if errors:
        logger.warning("Validation found %d issues:", len(errors))
        for err in errors:
            logger.warning("  %s", err)
    else:
        logger.info("All %d sources passed validation", len(all_sources))

    if args.validate_only:
        return

    # --- Write output ---
    if args.output is not None:
        write_sources_yaml(all_sources, args.output)
    else:
        output_dir = args.output_dir if args.output_dir is not None else Path("sources.d")
        write_sources_directory(all_sources, output_dir)

    # Summary
    type_counts: dict[str, int] = {}
    for s in all_sources:
        t = s.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    logger.info("Migration complete. Source counts by type:")
    for source_type, count in sorted(type_counts.items()):
        logger.info("  %s: %d", source_type, count)


def migrate(
    *,
    markdown_file: str | None = None,
    legacy_rss_file: str | None = None,
    legacy_youtube_file: str | None = None,
    output_dir: str | None = None,
    output: str | None = None,
) -> None:
    """High-level migration function for programmatic use and testing.

    Parses sources from the given input files, deduplicates, validates,
    and writes to the specified output format.

    Args:
        markdown_file: Path to AI-ML-Data-News.md (or similar markdown).
        legacy_rss_file: Path to rss_feeds.txt.
        legacy_youtube_file: Path to youtube_playlists.txt.
        output_dir: Output directory for sources.d/ layout.
        output: Output path for single merged sources.yaml.
    """
    all_sources: list[dict[str, Any]] = []

    if legacy_rss_file:
        all_sources.extend(parse_rss_feeds(Path(legacy_rss_file)))

    if legacy_youtube_file:
        all_sources.extend(parse_youtube_playlists(Path(legacy_youtube_file)))

    if markdown_file:
        md_path = Path(markdown_file)
        if md_path.exists():
            md_sources = parse_markdown(md_path)
            all_sources.extend(md_sources["rss"])
            all_sources.extend(md_sources["podcasts"])
            all_sources.extend(md_sources["youtube_rss"])

    all_sources = deduplicate_sources(all_sources)

    errors = validate_sources(all_sources)
    if errors:
        logger.warning("Validation found %d issues:", len(errors))
        for err in errors:
            logger.warning("  %s", err)

    if output is not None:
        write_sources_yaml(all_sources, Path(output))
    elif output_dir is not None:
        write_sources_directory(all_sources, Path(output_dir))
    else:
        write_sources_directory(all_sources, Path("sources.d"))


# Function aliases for test compatibility
parse_legacy_rss = parse_rss_feeds
parse_legacy_youtube = parse_youtube_playlists
write_sources_file = write_sources_yaml


def cli() -> None:
    """Entry point for the migration CLI."""
    parser = build_parser()
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(levelname)s: %(message)s",
    )

    run(args)


if __name__ == "__main__":
    cli()
