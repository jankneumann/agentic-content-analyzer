"""Digest markdown generation and post-processing utilities.

Generates markdown_content from digest JSON fields and extracts theme_tags
and source_content_ids using the markdown utilities from Phase 3.
"""

import re
from typing import TYPE_CHECKING, Any

from src.utils.markdown import extract_theme_tags

# Pre-compiled patterns for digest markdown parsing
LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
THEME_PATTERN = re.compile(r"#([a-zA-Z][a-zA-Z0-9_-]*)")

if TYPE_CHECKING:
    from src.models.digest import DigestSection


def _get_section_attr(section: "dict[str, Any] | DigestSection", key: str) -> Any:
    """Get an attribute from a section that may be a dict or DigestSection.

    Args:
        section: Dictionary or DigestSection object
        key: Attribute/key name to retrieve

    Returns:
        The value, or None if not found
    """
    if isinstance(section, dict):
        return section.get(key)
    return getattr(section, key, None)


def generate_digest_markdown(digest_data: dict[str, Any]) -> str:
    """Generate markdown content from digest JSON fields.

    Converts the structured JSON digest data into a well-formatted
    markdown document suitable for rendering or further processing.

    Args:
        digest_data: Dictionary containing digest fields:
            - title (str)
            - executive_overview (str)
            - strategic_insights (list[dict])
            - technical_developments (list[dict])
            - emerging_trends (list[dict])
            - actionable_recommendations (dict[str, list[str]])
            - sources (list[dict])
            - historical_context (list[dict], optional)

    Returns:
        Formatted markdown string

    Example:
        >>> data = {
        ...     "title": "Weekly AI Digest",
        ...     "executive_overview": "Big week for AI.",
        ...     "strategic_insights": [{"title": "AI Adoption", "summary": "Growing fast"}],
        ...     "technical_developments": [],
        ...     "emerging_trends": [],
        ...     "actionable_recommendations": {"CTOs": ["Invest in AI"]},
        ...     "sources": [{"title": "Newsletter A", "publication": "AI Weekly"}]
        ... }
        >>> md = generate_digest_markdown(data)
        >>> "## Executive Overview" in md
        True
    """
    sections = []

    # Title
    if title := digest_data.get("title"):
        sections.append(f"# {title}\n")

    # Executive Overview
    if overview := digest_data.get("executive_overview"):
        sections.append("## Executive Overview\n")
        sections.append(f"{overview}\n")

    # Strategic Insights
    if insights := digest_data.get("strategic_insights"):
        sections.append("## Strategic Insights\n")
        sections.append("*For CTOs and Technical Leaders*\n")
        for insight in insights:
            sections.append(_format_digest_section(insight))
        sections.append("")

    # Technical Developments
    if developments := digest_data.get("technical_developments"):
        sections.append("## Technical Developments\n")
        sections.append("*For Developers and Practitioners*\n")
        for dev in developments:
            sections.append(_format_digest_section(dev))
        sections.append("")

    # Emerging Trends
    if trends := digest_data.get("emerging_trends"):
        sections.append("## Emerging Trends\n")
        for trend in trends:
            sections.append(_format_digest_section(trend))
        sections.append("")

    # Actionable Recommendations
    if recommendations := digest_data.get("actionable_recommendations"):
        sections.append("## Actionable Recommendations\n")
        for role, actions in recommendations.items():
            formatted_role = role.replace("_", " ").title()
            sections.append(f"### {formatted_role}\n")
            for action in actions:
                sections.append(f"- {action}")
            sections.append("")

    # Historical Context
    if context := digest_data.get("historical_context"):
        sections.append("## Historical Context\n")
        for item in context:
            if isinstance(item, dict):
                if item_title := item.get("title"):
                    sections.append(f"### {item_title}\n")
                if item_content := item.get("content"):
                    sections.append(f"{item_content}\n")
            else:
                sections.append(f"- {item}")
        sections.append("")

    # Sources
    if sources := digest_data.get("sources"):
        sections.append("## Sources\n")
        for source in sources:
            source_title = source.get("title", "Untitled")
            publication = source.get("publication", "")
            url = source.get("url", "")

            if url:
                sections.append(f"- [{source_title}]({url})")
            elif publication:
                sections.append(f"- {source_title} ({publication})")
            else:
                sections.append(f"- {source_title}")
        sections.append("")

    return "\n".join(sections)


def _format_digest_section(section_data: "dict[str, Any] | DigestSection | str") -> str:
    """Format a single digest section (insight, development, trend).

    Args:
        section_data: Dictionary, DigestSection object, or simple string
                     with title, summary, details, themes, continuity

    Returns:
        Formatted markdown for this section
    """
    if isinstance(section_data, str):
        return f"- {section_data}"

    lines = []

    # Section title
    if title := _get_section_attr(section_data, "title"):
        lines.append(f"### {title}\n")

    # Summary
    if summary := _get_section_attr(section_data, "summary"):
        lines.append(f"{summary}\n")

    # Details
    if details := _get_section_attr(section_data, "details"):
        for detail in details:
            lines.append(f"- {detail}")
        lines.append("")

    # Themes (as hashtags)
    if themes := _get_section_attr(section_data, "themes"):
        theme_tags = " ".join(f"#{theme.replace(' ', '-')}" for theme in themes)
        lines.append(f"*Themes: {theme_tags}*\n")

    # Historical continuity
    if continuity := _get_section_attr(section_data, "continuity"):
        lines.append(f"> *Historical context: {continuity}*\n")

    # Follow-up prompts
    if followup_prompts := _get_section_attr(section_data, "followup_prompts"):
        lines.append(f"<details>\n<summary>Follow-up prompts ({len(followup_prompts)})</summary>\n")
        for i, prompt in enumerate(followup_prompts, 1):
            lines.append(f"**{i}.** {prompt}\n")
        lines.append("</details>\n")

    return "\n".join(lines)


def extract_digest_theme_tags(digest_data: dict[str, Any]) -> list[str]:
    """Extract all theme tags from digest data.

    Aggregates themes from:
    - strategic_insights[].themes
    - technical_developments[].themes
    - emerging_trends[].themes

    Args:
        digest_data: Dictionary containing digest fields (sections may be
                    dicts or DigestSection objects)

    Returns:
        List of unique theme tags
    """
    themes: list[str] = []
    seen: set[str] = set()

    # Extract from each section type
    for section_key in ["strategic_insights", "technical_developments", "emerging_trends"]:
        if sections := digest_data.get(section_key):
            for section in sections:
                # Use helper to get themes from dict or DigestSection
                if section_themes := _get_section_attr(section, "themes"):
                    for theme in section_themes:
                        normalized = theme.lower().strip()
                        if normalized and normalized not in seen:
                            themes.append(theme.strip())
                            seen.add(normalized)

    # Fallback: extract from markdown if no themes found
    if not themes and "markdown_content" in digest_data:
        themes = extract_theme_tags(digest_data["markdown_content"])

    return themes


def extract_source_content_ids(digest_data: dict[str, Any]) -> list[int]:
    """Extract source content IDs from digest data.

    Looks for content_id in sources list or legacy newsletter_id.

    Args:
        digest_data: Dictionary containing digest fields

    Returns:
        List of content IDs
    """
    content_ids: list[int] = []
    seen: set[int] = set()

    # Primary: sources with content_id
    if sources := digest_data.get("sources"):
        for source in sources:
            if isinstance(source, dict):
                # Try content_id first (unified model)
                if content_id := source.get("content_id"):
                    if content_id not in seen:
                        content_ids.append(content_id)
                        seen.add(content_id)
                # Fallback to newsletter_id (legacy)
                elif newsletter_id := source.get("newsletter_id"):
                    if newsletter_id not in seen:
                        content_ids.append(newsletter_id)
                        seen.add(newsletter_id)

    return content_ids


def enrich_digest_data(digest_data: dict[str, Any]) -> dict[str, Any]:
    """Enrich digest data with markdown_content, theme_tags, source_content_ids.

    Takes existing digest data and adds:
    - markdown_content: Generated markdown representation
    - theme_tags: Aggregated theme tags from all sections
    - source_content_ids: IDs of source content used

    This is a non-destructive operation that preserves all existing fields.

    Args:
        digest_data: Dictionary containing digest fields

    Returns:
        Enriched dictionary with additional fields
    """
    enriched = dict(digest_data)

    # Generate markdown if not present
    if not enriched.get("markdown_content"):
        enriched["markdown_content"] = generate_digest_markdown(digest_data)

    # Extract theme tags if not present
    if not enriched.get("theme_tags"):
        enriched["theme_tags"] = extract_digest_theme_tags(digest_data)

    # Extract source content IDs if not present
    if not enriched.get("source_content_ids"):
        enriched["source_content_ids"] = extract_source_content_ids(digest_data)

    return enriched


def parse_markdown_digest(markdown: str) -> dict[str, Any]:
    """Parse markdown back into structured digest data.

    Useful for round-tripping or processing externally generated markdown.

    Args:
        markdown: Markdown content following digest template

    Returns:
        Dictionary with extracted digest fields
    """
    from src.utils.markdown import get_section_by_name, parse_sections

    sections = parse_sections(markdown)
    result: dict[str, Any] = {}

    # Title (H1)
    if sections and sections[0].level == 1:
        result["title"] = sections[0].heading

    # Executive Overview
    if section := get_section_by_name(sections, "Executive Overview"):
        result["executive_overview"] = section.content.strip()

    # Strategic Insights
    if section := get_section_by_name(sections, "Strategic Insights"):
        result["strategic_insights"] = _parse_digest_subsections(section)

    # Technical Developments
    if section := get_section_by_name(sections, "Technical Developments"):
        result["technical_developments"] = _parse_digest_subsections(section)

    # Emerging Trends
    if section := get_section_by_name(sections, "Emerging Trends"):
        result["emerging_trends"] = _parse_digest_subsections(section)

    # Actionable Recommendations
    if section := get_section_by_name(sections, "Actionable Recommendations"):
        recommendations: dict[str, list[str]] = {}
        for subsection in section.subsections:
            role = subsection.heading.lower().replace(" ", "_")
            recommendations[role] = subsection.items
        result["actionable_recommendations"] = recommendations

    # Sources
    if section := get_section_by_name(sections, "Sources"):
        sources = []
        for item in section.items:
            if match := LINK_PATTERN.search(item):
                sources.append({"title": match.group(1), "url": match.group(2)})
            else:
                sources.append({"title": item})
        result["sources"] = sources

    return result


def _parse_digest_subsections(section: Any) -> list[dict[str, Any]]:
    """Parse subsections into digest section format.

    Args:
        section: MarkdownSection with subsections

    Returns:
        List of section dictionaries
    """
    items = []

    for subsection in section.subsections:
        item: dict[str, Any] = {
            "title": subsection.heading,
            "summary": subsection.content.strip(),
            "details": subsection.items,
        }

        # Extract themes from hashtags in content
        themes = THEME_PATTERN.findall(subsection.content)
        if themes:
            item["themes"] = [t.replace("-", " ").replace("_", " ") for t in themes]

        items.append(item)

    # If no subsections, use items directly
    if not items and section.items:
        items = [{"title": item, "summary": "", "details": []} for item in section.items]

    return items
