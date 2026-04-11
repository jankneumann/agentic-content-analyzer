"""Summary markdown generation and post-processing utilities.

Generates markdown_content from summary JSON fields and extracts theme_tags
using the markdown utilities from Phase 3.
"""

import re
from typing import Any

from src.utils.markdown import extract_relevance_scores, extract_theme_tags

# Pre-compiled pattern for markdown links
LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def generate_summary_markdown(summary_data: dict[str, Any]) -> str:
    """Generate markdown content from summary JSON fields.

    Converts the structured JSON summary data into a well-formatted
    markdown document that can be rendered in the UI or used for
    further processing.

    Args:
        summary_data: Dictionary containing summary fields:
            - executive_summary (str)
            - key_themes (list[str])
            - strategic_insights (list[str])
            - technical_details (list[str])
            - actionable_items (list[str])
            - notable_quotes (list[str])
            - relevant_links (list[dict])
            - relevance_scores (dict[str, float])

    Returns:
        Formatted markdown string

    Example:
        >>> data = {
        ...     "executive_summary": "AI is changing everything.",
        ...     "key_themes": ["AI", "ML"],
        ...     "strategic_insights": ["Consider AI adoption"],
        ...     "technical_details": ["Use transformers"],
        ...     "actionable_items": ["Start POC"],
        ...     "notable_quotes": ["The future is now"],
        ...     "relevant_links": [{"title": "Paper", "url": "https://..."}],
        ...     "relevance_scores": {"cto_leadership": 0.9}
        ... }
        >>> md = generate_summary_markdown(data)
        >>> "## Executive Summary" in md
        True
    """
    sections = []

    # Executive Summary
    if exec_summary := summary_data.get("executive_summary"):
        sections.append("## Executive Summary\n")
        sections.append(f"{exec_summary}\n")

    # Key Themes
    if themes := summary_data.get("key_themes"):
        sections.append("## Key Themes\n")
        for theme in themes:
            sections.append(f"- {theme}")
        sections.append("")

    # Strategic Insights
    if insights := summary_data.get("strategic_insights"):
        sections.append("## Strategic Insights\n")
        sections.append("*For CTOs and Technical Leaders*\n")
        for insight in insights:
            sections.append(f"- {insight}")
        sections.append("")

    # Technical Details
    if details := summary_data.get("technical_details"):
        sections.append("## Technical Details\n")
        sections.append("*For Developers and Practitioners*\n")
        for detail in details:
            sections.append(f"- {detail}")
        sections.append("")

    # Actionable Items
    if actions := summary_data.get("actionable_items"):
        sections.append("## Actionable Items\n")
        for action in actions:
            sections.append(f"- {action}")
        sections.append("")

    # Notable Quotes
    if quotes := summary_data.get("notable_quotes"):
        sections.append("## Notable Quotes\n")
        for quote in quotes:
            sections.append(f"> {quote}\n")
        sections.append("")

    # Relevant Links
    if links := summary_data.get("relevant_links"):
        sections.append("## Relevant Links\n")
        for link in links:
            title = link.get("title", "Untitled")
            url = link.get("url", "")
            if url:
                sections.append(f"- [{title}]({url})")
            else:
                sections.append(f"- {title}")
        sections.append("")

    # Relevance Scores
    if scores := summary_data.get("relevance_scores"):
        sections.append("## Relevance Scores\n")
        for category, score in scores.items():
            # Format category name (convert snake_case to Title Case)
            formatted_category = category.replace("_", " ").title()
            sections.append(f"- **{formatted_category}**: {score:.2f}")
        sections.append("")

    return "\n".join(sections)


def extract_summary_theme_tags(summary_data: dict[str, Any]) -> list[str]:
    """Extract theme tags from summary data.

    Primarily uses the key_themes field, with fallback to extracting
    from generated markdown.

    Args:
        summary_data: Dictionary containing summary fields

    Returns:
        List of theme tags (deduplicated)
    """
    themes: list[str] = []
    seen: set[str] = set()

    # Primary source: key_themes field
    if key_themes := summary_data.get("key_themes"):
        for theme in key_themes:
            normalized = theme.lower().strip()
            if normalized and normalized not in seen:
                themes.append(theme.strip())
                seen.add(normalized)

    # If no themes found, try extracting from markdown
    if not themes and "markdown_content" in summary_data:
        themes = extract_theme_tags(summary_data["markdown_content"])

    return themes


def enrich_summary_data(summary_data: dict[str, Any]) -> dict[str, Any]:
    """Enrich summary data with markdown_content and theme_tags.

    Takes existing summary data and adds:
    - markdown_content: Generated markdown representation
    - theme_tags: Extracted theme tags

    This is a non-destructive operation that preserves all existing fields.

    Args:
        summary_data: Dictionary containing summary fields

    Returns:
        Enriched dictionary with additional fields
    """
    enriched = dict(summary_data)

    # Generate markdown if not present
    if not enriched.get("markdown_content"):
        enriched["markdown_content"] = generate_summary_markdown(summary_data)

    # Extract theme tags if not present
    if not enriched.get("theme_tags"):
        enriched["theme_tags"] = extract_summary_theme_tags(summary_data)

    return enriched


def parse_markdown_summary(markdown: str) -> dict[str, Any]:
    """Parse markdown back into structured summary data.

    Useful for round-tripping or processing externally generated markdown.

    Args:
        markdown: Markdown content following summary template

    Returns:
        Dictionary with extracted summary fields
    """
    from src.utils.markdown import get_section_by_name, parse_sections

    sections = parse_sections(markdown)
    result: dict[str, Any] = {}

    # Executive Summary
    if section := get_section_by_name(sections, "Executive Summary"):
        result["executive_summary"] = section.content.strip()

    # Key Themes
    if section := get_section_by_name(sections, "Key Themes"):
        result["key_themes"] = section.items

    # Strategic Insights
    if section := get_section_by_name(sections, "Strategic Insights"):
        result["strategic_insights"] = section.items

    # Technical Details
    if section := get_section_by_name(sections, "Technical Details"):
        result["technical_details"] = section.items

    # Actionable Items
    if section := get_section_by_name(sections, "Actionable Items"):
        result["actionable_items"] = section.items

    # Notable Quotes (blockquotes need special handling)
    if section := get_section_by_name(sections, "Notable Quotes"):
        # Parse blockquotes from content
        quotes = []
        for line in section.content.split("\n"):
            if line.strip().startswith(">"):
                quotes.append(line.strip().lstrip(">").strip())
        result["notable_quotes"] = quotes if quotes else section.items

    # Relevant Links (parse markdown links)
    if section := get_section_by_name(sections, "Relevant Links"):
        links = []
        for item in section.items:
            if match := LINK_PATTERN.search(item):
                links.append({"title": match.group(1), "url": match.group(2)})
        result["relevant_links"] = links

    # Relevance Scores
    result["relevance_scores"] = extract_relevance_scores(markdown)

    return result
