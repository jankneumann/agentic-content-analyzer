"""Obsidian frontmatter generation and filename utilities.

Generates YAML frontmatter for Obsidian-compatible markdown files,
slugifies filenames with date prefixes, and computes content hashes
for incremental sync.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import datetime
from typing import Any

# Characters unsafe in YAML values (could break parsing or be misinterpreted)
_YAML_UNSAFE_CHARS = re.compile(r"[:\n]|^---|^#")
# Characters not allowed in filenames
_FILENAME_UNSAFE = re.compile(r"[^\w\s-]")
_WHITESPACE_RUN = re.compile(r"[\s_]+")


def sanitize_tag(tag: str) -> str:
    """Sanitize a tag for safe inclusion in YAML frontmatter.

    Strips YAML-unsafe characters (colons, newlines, document separators,
    leading #) and returns cleaned tag or empty string.

    Args:
        tag: Raw tag string.

    Returns:
        Sanitized tag, or empty string if nothing remains.
    """
    cleaned = tag.strip()
    # Remove leading '#' (Obsidian adds its own)
    cleaned = cleaned.lstrip("#").strip()
    # Remove colons and newlines
    cleaned = cleaned.replace(":", "").replace("\n", " ").replace("\r", "")
    # Remove YAML document separator
    cleaned = cleaned.replace("---", "")
    return cleaned.strip()


def build_frontmatter(
    aca_id: str,
    aca_type: str,
    *,
    date: datetime | str | None = None,
    tags: list[str] | None = None,
    content_hash: str = "",
    **extra: Any,
) -> str:
    """Build YAML frontmatter block for an Obsidian note.

    Args:
        aca_id: Unique identifier for this content item.
        aca_type: Content type (digest, summary, insight, content_stub, entity, moc).
        date: Publication/creation date (datetime or ISO string).
        tags: List of theme tags (will be sanitized).
        content_hash: SHA-256 hash prefixed with 'sha256:'.
        **extra: Additional frontmatter fields.

    Returns:
        YAML frontmatter string including ``---`` delimiters.
    """
    lines = ["---"]
    lines.append("generator: aca")
    lines.append(f"aca_id: \"{aca_id}\"")
    lines.append(f"aca_type: {aca_type}")

    if date is not None:
        if isinstance(date, datetime):
            lines.append(f"date: {date.strftime('%Y-%m-%d')}")
        else:
            lines.append(f"date: {str(date)[:10]}")

    if tags:
        safe_tags = [sanitize_tag(t) for t in tags]
        safe_tags = [t for t in safe_tags if t]
        if safe_tags:
            tag_list = ", ".join(safe_tags)
            lines.append(f"tags: [{tag_list}]")

    if content_hash:
        lines.append(f"content_hash: \"{content_hash}\"")

    for key, value in extra.items():
        if value is not None:
            if isinstance(value, list):
                formatted = ", ".join(f"\"{v}\"" if isinstance(v, str) else str(v) for v in value)
                lines.append(f"{key}: [{formatted}]")
            elif isinstance(value, bool):
                lines.append(f"{key}: {'true' if value else 'false'}")
            elif isinstance(value, (int, float)):
                lines.append(f"{key}: {value}")
            else:
                lines.append(f"{key}: \"{value}\"")

    lines.append("---")
    return "\n".join(lines) + "\n"


def slugify_filename(
    title: str,
    date: datetime | str | None = None,
    aca_type: str = "",
) -> str:
    """Generate an Obsidian-friendly filename from title and date.

    For time-stamped content, produces ``YYYY-MM-DD-slugified-title.md``.
    For entities, produces ``Title.md`` (no date prefix).

    Args:
        title: Content title.
        date: Optional date for prefix.
        aca_type: Content type — entities skip the date prefix.

    Returns:
        Slugified filename with .md extension.
    """
    # Normalize unicode
    slug = unicodedata.normalize("NFKD", title)
    slug = slug.encode("ascii", "ignore").decode("ascii")
    # Lowercase and clean
    slug = slug.lower().strip()
    slug = _FILENAME_UNSAFE.sub("", slug)
    slug = _WHITESPACE_RUN.sub("-", slug)
    slug = slug.strip("-")

    if not slug:
        slug = "untitled"

    # Entities use name without date prefix
    if aca_type == "entity":
        # Preserve original casing for entities
        entity_name = title.strip().replace("/", "-").replace("\\", "-")
        entity_name = _WHITESPACE_RUN.sub(" ", entity_name).strip()
        return f"{entity_name}.md" if entity_name else "untitled.md"

    # Date prefix for time-stamped content
    if date is not None:
        if isinstance(date, datetime):
            prefix = date.strftime("%Y-%m-%d")
        else:
            prefix = str(date)[:10]
        return f"{prefix}-{slug}.md"

    return f"{slug}.md"


def compute_content_hash(content: str) -> str:
    """Compute SHA-256 hash of content, prefixed with 'sha256:'.

    The hash is computed on the full content EXCLUDING any existing
    content_hash frontmatter field (to avoid circular dependency).

    Args:
        content: Full file content (frontmatter + body).

    Returns:
        Hash string in format ``sha256:<64-char-hex>``.
    """
    # Remove content_hash line if present (avoid circular hash)
    lines = content.split("\n")
    filtered = [line for line in lines if not line.startswith("content_hash:")]
    clean = "\n".join(filtered)

    digest = hashlib.sha256(clean.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"
