"""Markdown parsing and extraction utilities.

Provides functions for parsing markdown content into structured sections,
extracting theme tags, relevance scores, and embedded references.
"""

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MarkdownSection:
    """A section parsed from markdown content.

    Attributes:
        heading: The section heading text (without # prefix)
        level: Heading level (1-6)
        content: The content under this heading (raw markdown)
        items: List items extracted from the content (if any)
        subsections: Nested sections under this heading
    """

    heading: str
    level: int
    content: str = ""
    items: list[str] = field(default_factory=list)
    subsections: list["MarkdownSection"] = field(default_factory=list)


# Standard section names used in summaries and digests
STANDARD_SECTIONS = {
    # Summary sections
    "Executive Summary",
    "Key Themes",
    "Strategic Insights",
    "Technical Details",
    "Actionable Items",
    "Notable Quotes",
    "Relevant Links",
    "Relevance Scores",
    # Digest sections
    "Executive Overview",
    "Technical Developments",
    "Emerging Trends",
    "Actionable Recommendations",
    "Sources",
    "Historical Context",
}

# Pattern for embedded references: [TYPE:id] or [TYPE:id|params]
EMBED_PATTERN = re.compile(
    r"\[(?P<type>TABLE|IMAGE|CODE):(?P<id>[^\]|]+)(?:\|(?P<params>[^\]]+))?\]"
)

# Pattern for theme hashtags: #theme-name or #ThemeName
HASHTAG_PATTERN = re.compile(r"#([a-zA-Z][a-zA-Z0-9_-]*)")

# Pattern for relevance scores: **Category Name**: 0.85 or Category Name: 0.85
SCORE_PATTERN = re.compile(r"(?:\*\*)?([A-Za-z][A-Za-z0-9 _-]+?)(?:\*\*)?:\s*(\d+\.?\d*)")

# Patterns for text cleaning and normalization
CLEAN_PATTERN = re.compile(r"[\*\`]+")
KEBAB_CAMEL_PATTERN1 = re.compile(r"[-_]")
KEBAB_CAMEL_PATTERN2 = re.compile(r"([a-z])([A-Z])")
NORMALIZE_KEY_PATTERN = re.compile(r"[^a-z0-9]+")

# Patterns for Markdown parsing
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+([^\n]+)$")  # NOSONAR
LIST_ITEM_PATTERN = re.compile(r"^[-*+]\s+([^\n]+)$")  # NOSONAR


def parse_sections(markdown: str) -> list[MarkdownSection]:
    """Parse markdown content into structured sections.

    Splits markdown by headings and extracts section content,
    list items, and nested subsections.

    Args:
        markdown: Raw markdown content

    Returns:
        List of MarkdownSection objects representing the document structure

    Example:
        >>> md = '''# Title
        ... ## Section 1
        ... - Item 1
        ... - Item 2
        ... ## Section 2
        ... Content here.
        ... '''
        >>> sections = parse_sections(md)
        >>> sections[0].heading
        'Title'
        >>> sections[0].subsections[0].heading
        'Section 1'
    """
    if not markdown or not markdown.strip():
        return []

    lines = markdown.split("\n")
    root_sections: list[MarkdownSection] = []
    section_stack: list[MarkdownSection] = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # Check for heading
        heading_match = HEADING_PATTERN.match(line)
        if heading_match:
            level = len(heading_match.group(1))
            heading = heading_match.group(2).strip()

            # Create new section
            section = MarkdownSection(heading=heading, level=level)

            # Find where this section fits in the hierarchy
            while section_stack and section_stack[-1].level >= level:
                section_stack.pop()

            if section_stack:
                # Add as subsection
                section_stack[-1].subsections.append(section)
            else:
                # Add to root
                root_sections.append(section)

            section_stack.append(section)
            i += 1
            continue

        # If we have a current section, add content to it
        if section_stack:
            current = section_stack[-1]

            # Check for list item
            list_match = LIST_ITEM_PATTERN.match(line)
            if list_match:
                current.items.append(list_match.group(1).strip())
            elif line.strip():
                # Add to content
                if current.content:
                    current.content += "\n" + line
                else:
                    current.content = line

        i += 1

    return root_sections


def extract_theme_tags(markdown: str) -> list[str]:
    """Extract theme tags from markdown content.

    Looks for themes in two places:
    1. Key Themes section (list items)
    2. Hashtags throughout the content (#ai-agents, #LLM, etc.)

    Args:
        markdown: Raw markdown content

    Returns:
        List of unique theme tags (deduplicated, lowercase normalized)

    Example:
        >>> md = '''## Key Themes
        ... - Artificial Intelligence
        ... - Machine Learning
        ...
        ... This is about #AI and #ML.
        ... '''
        >>> extract_theme_tags(md)
        ['artificial intelligence', 'machine learning', 'ai', 'ml']
    """
    themes: list[str] = []
    seen: set[str] = set()

    # Extract from Key Themes section
    sections = parse_sections(markdown)
    for section in _flatten_sections(sections):
        if section.heading.lower() in ("key themes", "themes"):
            for item in section.items:
                # Clean up item (remove markdown formatting)
                clean = CLEAN_PATTERN.sub("", item).strip()
                normalized = clean.lower()
                if normalized and normalized not in seen:
                    themes.append(clean)
                    seen.add(normalized)

    # Extract hashtags
    for match in HASHTAG_PATTERN.finditer(markdown):
        tag = match.group(1)
        # Convert kebab-case or camelCase to spaces
        tag_clean = KEBAB_CAMEL_PATTERN1.sub(" ", tag)
        tag_clean = KEBAB_CAMEL_PATTERN2.sub(r"\1 \2", tag_clean)
        normalized = tag_clean.lower()
        if normalized not in seen:
            themes.append(tag_clean)
            seen.add(normalized)

    return themes


def extract_relevance_scores(markdown: str) -> dict[str, float]:
    """Extract relevance scores from markdown content.

    Looks for scores in the Relevance Scores section or inline patterns.
    Supports formats like:
    - **Category Name**: 0.85
    - Category Name: 0.85
    - - **Category**: 0.9

    Args:
        markdown: Raw markdown content

    Returns:
        Dictionary mapping category names to float scores (0.0-1.0)

    Example:
        >>> md = '''## Relevance Scores
        ... - **AI Strategy**: 0.95
        ... - **Technical Implementation**: 0.82
        ... '''
        >>> extract_relevance_scores(md)
        {'ai_strategy': 0.95, 'technical_implementation': 0.82}
    """
    scores: dict[str, float] = {}

    # First try to find Relevance Scores section
    sections = parse_sections(markdown)
    for section in _flatten_sections(sections):
        if "relevance" in section.heading.lower() and "score" in section.heading.lower():
            # Parse items in this section
            for item in section.items:
                match = SCORE_PATTERN.search(item)
                if match:
                    category = match.group(1).strip()
                    score_str = match.group(2)
                    try:
                        score = float(score_str)
                        # Normalize to 0-1 if needed
                        if score > 1:
                            score = score / 100
                        key = _normalize_key(category)
                        scores[key] = min(1.0, max(0.0, score))
                    except ValueError:
                        continue

            # Also check content
            for match in SCORE_PATTERN.finditer(section.content):
                category = match.group(1).strip()
                score_str = match.group(2)
                try:
                    score = float(score_str)
                    if score > 1:
                        score = score / 100
                    key = _normalize_key(category)
                    if key not in scores:
                        scores[key] = min(1.0, max(0.0, score))
                except ValueError:
                    continue

    return scores


def extract_embedded_refs(markdown: str) -> dict[str, list[str]]:
    """Extract embedded reference markers from markdown.

    Looks for patterns like:
    - [TABLE:table-id]
    - [IMAGE:image-id]
    - [IMAGE:id|video=xxx&t=123]
    - [CODE:snippet-id]

    Args:
        markdown: Raw markdown content

    Returns:
        Dictionary with keys 'tables', 'images', 'code' containing lists of IDs

    Example:
        >>> md = '''See [TABLE:sales-2024] for details.
        ... Here's the chart [IMAGE:chart-1|width=500].
        ... '''
        >>> extract_embedded_refs(md)
        {'tables': ['sales-2024'], 'images': ['chart-1'], 'code': []}
    """
    refs: dict[str, list[str]] = {
        "tables": [],
        "images": [],
        "code": [],
    }

    for match in EMBED_PATTERN.finditer(markdown):
        ref_type = match.group("type").lower()
        ref_id = match.group("id")

        if ref_type == "table":
            if ref_id not in refs["tables"]:
                refs["tables"].append(ref_id)
        elif ref_type == "image":
            if ref_id not in refs["images"]:
                refs["images"].append(ref_id)
        elif ref_type == "code":
            if ref_id not in refs["code"]:
                refs["code"].append(ref_id)

    return refs


def render_with_embeds(
    markdown: str,
    tables_json: dict[str, Any] | None = None,
    images: list[dict[str, Any]] | None = None,
) -> str:
    """Render markdown with embedded content replaced.

    Replaces embed markers with actual content:
    - [TABLE:id] -> Rendered markdown table
    - [IMAGE:id] -> HTML img tag or markdown image
    - [IMAGE:id|video=xxx&t=123] -> YouTube thumbnail with deep link
    - [CODE:id] -> Code block

    Args:
        markdown: Raw markdown with embed markers
        tables_json: Dict mapping table IDs to table data
            Each table should have 'headers' and 'rows' keys
        images: List of image dicts with 'id', 'url', 'alt_text', etc.

    Returns:
        Markdown with embeds replaced by rendered content

    Example:
        >>> md = "See [TABLE:t1] below."
        >>> tables = {"t1": {"headers": ["A", "B"], "rows": [["1", "2"]]}}
        >>> render_with_embeds(md, tables_json=tables)
        'See \\n| A | B |\\n|---|---|\\n| 1 | 2 |\\n below.'
    """
    tables_json = tables_json or {}
    images = images or []

    # Build image lookup
    image_lookup: dict[str, dict[str, Any]] = {}
    for img in images:
        if "id" in img:
            image_lookup[img["id"]] = img

    def replace_embed(match: re.Match[str]) -> str:
        ref_type = match.group("type")
        ref_id = match.group("id")
        params_str = match.group("params") or ""

        # Parse params
        params: dict[str, str] = {}
        if params_str:
            for part in params_str.split("&"):
                if "=" in part:
                    key, value = part.split("=", 1)
                    params[key] = value

        if ref_type == "TABLE":
            return _render_table(ref_id, tables_json.get(ref_id))

        elif ref_type == "IMAGE":
            img_data = image_lookup.get(ref_id, {})

            # Check for YouTube video params
            video_id = params.get("video")
            timestamp = params.get("t")

            if video_id:
                return _render_youtube_thumbnail(ref_id, video_id, timestamp, img_data)
            else:
                return _render_image(ref_id, img_data, params)

        elif ref_type == "CODE":
            # Code embeds not yet implemented
            return f"<!-- Code embed: {ref_id} -->"

        return match.group(0)  # Return original if unknown type

    return EMBED_PATTERN.sub(replace_embed, markdown)


def get_section_by_name(
    sections: list[MarkdownSection],
    name: str,
) -> MarkdownSection | None:
    """Find a section by name (case-insensitive).

    Args:
        sections: List of parsed sections
        name: Section name to find

    Returns:
        MarkdownSection if found, None otherwise
    """
    name_lower = name.lower()
    for section in _flatten_sections(sections):
        if section.heading.lower() == name_lower:
            return section
    return None


def sections_to_dict(sections: list[MarkdownSection]) -> dict[str, Any]:
    """Convert sections to a dictionary structure.

    Args:
        sections: List of parsed sections

    Returns:
        Dictionary with section headings as keys
    """
    result: dict[str, Any] = {}

    for section in sections:
        key = _normalize_key(section.heading)
        section_data: dict[str, Any] = {
            "content": section.content,
            "items": section.items,
        }

        if section.subsections:
            section_data["subsections"] = sections_to_dict(section.subsections)

        result[key] = section_data

    return result


# --- Private Helper Functions ---


def _flatten_sections(sections: list[MarkdownSection]) -> list[MarkdownSection]:
    """Flatten nested sections into a single list."""
    result: list[MarkdownSection] = []
    for section in sections:
        result.append(section)
        result.extend(_flatten_sections(section.subsections))
    return result


def _normalize_key(text: str) -> str:
    """Normalize text to a valid dictionary key.

    Converts to lowercase, replaces spaces with underscores,
    removes special characters.
    """
    key = text.lower().strip()
    key = NORMALIZE_KEY_PATTERN.sub("_", key)
    key = key.strip("_")
    return key


def _render_table(table_id: str, table_data: dict[str, Any] | None) -> str:
    """Render a table as markdown."""
    if not table_data:
        return f"<!-- Table not found: {table_id} -->"

    headers = table_data.get("headers", [])
    rows = table_data.get("rows", [])

    if not headers:
        return f"<!-- Table {table_id} has no headers -->"

    lines = []

    # Header row
    lines.append("| " + " | ".join(str(h) for h in headers) + " |")

    # Separator
    lines.append("|" + "|".join("---" for _ in headers) + "|")

    # Data rows
    for row in rows:
        # Ensure row has same length as headers
        padded_row = list(row) + [""] * (len(headers) - len(row))
        lines.append("| " + " | ".join(str(cell) for cell in padded_row[: len(headers)]) + " |")

    return "\n" + "\n".join(lines) + "\n"


def _render_image(
    image_id: str,
    img_data: dict[str, Any],
    params: dict[str, str],
) -> str:
    """Render an image as markdown or HTML."""
    url = img_data.get("url") or img_data.get("storage_path", "")
    alt_text = img_data.get("alt_text", f"Image: {image_id}")
    caption = img_data.get("caption", "")

    if not url:
        return f"<!-- Image not found: {image_id} -->"

    # Check for width/height params
    width = params.get("width")
    height = params.get("height")

    if width or height:
        # Use HTML for sizing
        style_parts = []
        if width:
            style_parts.append(f"width: {width}px")
        if height:
            style_parts.append(f"height: {height}px")
        style = "; ".join(style_parts)
        img_tag = f'<img src="{url}" alt="{alt_text}" style="{style}">'
    else:
        # Use markdown
        img_tag = f"![{alt_text}]({url})"

    if caption:
        return f"{img_tag}\n*{caption}*"
    return img_tag


def _render_youtube_thumbnail(
    image_id: str,
    video_id: str,
    timestamp: str | None,
    img_data: dict[str, Any],
) -> str:
    """Render a YouTube video thumbnail with deep link."""
    # Use stored thumbnail or YouTube's default
    url = img_data.get("url") or f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
    alt_text = img_data.get("alt_text", f"Video thumbnail: {video_id}")

    # Build YouTube deep link
    youtube_url = f"https://www.youtube.com/watch?v={video_id}"
    if timestamp:
        youtube_url += f"&t={timestamp}"

    return f"[![{alt_text}]({url})]({youtube_url})"
