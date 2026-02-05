"""Analyze markdown structure preservation in Content records.

This script checks if the markdown_content field in Content records
has properly preserved document structure (headers, lists, links, etc.)
from the original HTML source.

Usage:
    python -m src.scripts.analyze_markdown_quality [--limit N] [--source TYPE] [--verbose]

Examples:
    # Analyze 10 most recent content items
    python -m src.scripts.analyze_markdown_quality

    # Analyze 50 items with verbose output
    python -m src.scripts.analyze_markdown_quality --limit 50 --verbose

    # Analyze only RSS content
    python -m src.scripts.analyze_markdown_quality --source rss

    # Show items with structural issues
    python -m src.scripts.analyze_markdown_quality --issues-only
"""

import argparse
from dataclasses import dataclass

from src.models.content import Content, ContentSource
from src.parsers.html_markdown import validate_markdown_quality
from src.storage.database import get_db
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class MarkdownStats:
    """Statistics about markdown structure."""

    length: int
    lines: int
    h1: int
    h2: int
    h3: int
    bullet_lists: int
    numbered_lists: int
    links: int
    code_blocks: int
    paragraphs: int
    has_html_tags: bool


def analyze_markdown_structure(markdown: str | None) -> MarkdownStats | None:
    """Analyze markdown for structural elements.

    Args:
        markdown: Markdown content to analyze

    Returns:
        MarkdownStats with counts of structural elements, or None if no content
    """
    if not markdown:
        return None

    lines = markdown.split("\n")

    # Count structural elements
    h1_count = sum(1 for line in lines if line.startswith("# ") and not line.startswith("## "))
    h2_count = sum(1 for line in lines if line.startswith("## ") and not line.startswith("### "))
    h3_count = sum(1 for line in lines if line.startswith("### "))

    # List items (- or * or numbered)
    bullet_items = sum(1 for line in lines if line.strip().startswith(("- ", "* ")))
    numbered_items = sum(
        1 for line in lines if line.strip() and line.strip()[0].isdigit() and ". " in line[:5]
    )

    # Links
    link_count = markdown.count("](")

    # Code blocks
    code_blocks = markdown.count("```") // 2

    # Paragraphs (double newlines)
    paragraphs = markdown.count("\n\n")

    # Check for HTML tags that shouldn't be in markdown
    html_tags = [
        "<p>",
        "</p>",
        "<h1>",
        "</h1>",
        "<ul>",
        "</ul>",
        "<li>",
        "</li>",
        "<div>",
        "</div>",
    ]
    has_html = any(tag in markdown for tag in html_tags)

    return MarkdownStats(
        length=len(markdown),
        lines=len(lines),
        h1=h1_count,
        h2=h2_count,
        h3=h3_count,
        bullet_lists=bullet_items,
        numbered_lists=numbered_items,
        links=link_count,
        code_blocks=code_blocks,
        paragraphs=paragraphs,
        has_html_tags=has_html,
    )


def print_content_analysis(
    content: Content,
    stats: MarkdownStats,
    verbose: bool = False,
    max_preview: int = 500,
) -> None:
    """Print analysis for a single content item.

    Args:
        content: Content record to analyze
        stats: Pre-computed markdown statistics
        verbose: Whether to show full preview
        max_preview: Maximum characters to show in preview
    """
    print(f"\n{'=' * 80}")
    title = content.title[:60] if content.title else "N/A"
    print(f"ID: {content.id} | Title: {title}...")
    source = content.source_type.value if content.source_type else "Unknown"
    print(f"Source: {source} | Publication: {content.publication or 'N/A'}")
    print(f"Status: {content.status}")
    print("-" * 80)

    quality = validate_markdown_quality(content.markdown_content)

    print("📊 Structure Analysis:")
    print(f"   Length: {stats.length:,} chars | Lines: {stats.lines}")
    print(f"   Headers: H1={stats.h1}, H2={stats.h2}, H3={stats.h3}")
    print(f"   Lists: Bullets={stats.bullet_lists}, Numbered={stats.numbered_lists}")
    print(f"   Links: {stats.links} | Code blocks: {stats.code_blocks}")
    print(f"   Paragraphs: {stats.paragraphs}")
    print(f"   Has HTML tags: {'⚠️ YES' if stats.has_html_tags else '✅ No'}")
    print(
        f"   Quality Valid: {quality.valid} | Issues: {quality.issues if quality.issues else 'None'}"
    )

    if verbose and content.markdown_content:
        print(f"\n📝 Preview (first {max_preview} chars):")
        print("-" * 40)
        preview = content.markdown_content[:max_preview]
        if len(content.markdown_content) > max_preview:
            preview += "\n... [truncated]"
        print(preview)


def print_aggregate_stats(all_stats: list[MarkdownStats]) -> None:
    """Print aggregate statistics across all analyzed items.

    Args:
        all_stats: List of MarkdownStats from analyzed items
    """
    if not all_stats:
        print("\n⚠️  No content items with markdown found")
        return

    print(f"\n{'=' * 80}")
    print("📈 AGGREGATE STATISTICS")
    print("=" * 80)

    avg_length = sum(s.length for s in all_stats) / len(all_stats)
    avg_headers = sum(s.h1 + s.h2 + s.h3 for s in all_stats) / len(all_stats)
    avg_lists = sum(s.bullet_lists + s.numbered_lists for s in all_stats) / len(all_stats)
    avg_links = sum(s.links for s in all_stats) / len(all_stats)

    items_with_headers = sum(1 for s in all_stats if s.h1 + s.h2 + s.h3 > 0)
    items_with_lists = sum(1 for s in all_stats if s.bullet_lists + s.numbered_lists > 0)
    items_with_links = sum(1 for s in all_stats if s.links > 0)
    items_with_html = sum(1 for s in all_stats if s.has_html_tags)

    print(f"Total items analyzed: {len(all_stats)}")
    print(f"Average content length: {avg_length:,.0f} chars")
    print(f"Average headers per item: {avg_headers:.1f}")
    print(f"Average list items per item: {avg_lists:.1f}")
    print(f"Average links per item: {avg_links:.1f}")

    print("\nStructure presence:")

    def pct(x: int) -> float:
        return x / len(all_stats) * 100

    print(
        f"  Items with headers: {items_with_headers}/{len(all_stats)} ({pct(items_with_headers):.0f}%)"
    )
    print(f"  Items with lists: {items_with_lists}/{len(all_stats)} ({pct(items_with_lists):.0f}%)")
    print(f"  Items with links: {items_with_links}/{len(all_stats)} ({pct(items_with_links):.0f}%)")

    if items_with_html > 0:
        print(
            f"\n⚠️  Items with residual HTML tags: {items_with_html}/{len(all_stats)} ({pct(items_with_html):.0f}%)"
        )
    else:
        print("\n✅ No items have residual HTML tags")


def main() -> None:
    """Main entry point for markdown quality analysis."""
    parser = argparse.ArgumentParser(
        description="Analyze markdown structure preservation in Content records"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of items to analyze (default: 10)",
    )
    parser.add_argument(
        "--source",
        type=str,
        choices=["gmail", "rss", "youtube", "file"],
        help="Filter by content source type",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show content preview for each item",
    )
    parser.add_argument(
        "--issues-only",
        action="store_true",
        help="Only show items with structural issues",
    )
    parser.add_argument(
        "--stats-only",
        action="store_true",
        help="Only show aggregate statistics, not individual items",
    )

    args = parser.parse_args()

    # Map source argument to enum
    source_map = {
        "gmail": ContentSource.GMAIL,
        "rss": ContentSource.RSS,
        "youtube": ContentSource.YOUTUBE,
        "file": ContentSource.FILE_UPLOAD,
    }

    with get_db() as db:
        # Build query
        query = (
            db.query(Content)
            .filter(Content.markdown_content.isnot(None))
            .filter(Content.markdown_content != "")
        )

        if args.source:
            query = query.filter(Content.source_type == source_map[args.source])

        contents = query.order_by(Content.ingested_at.desc()).limit(args.limit).all()

        print(f"\n🔍 Analyzing {len(contents)} Content records with markdown...\n")

        all_stats: list[MarkdownStats] = []
        items_with_issues: list[tuple[Content, MarkdownStats]] = []

        for content in contents:
            stats = analyze_markdown_structure(content.markdown_content)
            if stats:
                all_stats.append(stats)

                # Check for issues
                has_issues = (
                    stats.has_html_tags
                    or (stats.h1 + stats.h2 + stats.h3 == 0 and stats.length > 500)
                    or stats.paragraphs == 0
                )

                if has_issues:
                    items_with_issues.append((content, stats))

                # Print individual analysis if not stats-only
                if not args.stats_only:
                    if args.issues_only and not has_issues:
                        continue
                    print_content_analysis(content, stats, verbose=args.verbose)

        # Print aggregate statistics
        print_aggregate_stats(all_stats)

        # Summary of issues
        if items_with_issues and not args.stats_only:
            print(f"\n⚠️  {len(items_with_issues)} items have potential structural issues")
            if not args.issues_only:
                print("   Run with --issues-only to see only problematic items")


if __name__ == "__main__":
    main()
