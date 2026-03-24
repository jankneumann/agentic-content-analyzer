"""Content normalization and hashing utilities for deduplication.

This module provides utilities to normalize newsletter content and generate
consistent hashes for detecting duplicate content across different sources
(Gmail, RSS) despite formatting differences.
"""

import hashlib
import re

# Pre-compiled regular expressions for text normalization
_HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
_URL_PATTERN = re.compile(r"https?://\S+")
_EMAIL_PATTERN = re.compile(r"\S+@\S+")
_FOOTER_PATTERN = re.compile(
    r"(?:unsubscribe.*$|view in browser.*$|forward to a friend.*$|update your preferences.*$|manage your subscription.*$|click here to.*$|you received this email because.*$|this email was sent to.*$)",
    flags=re.IGNORECASE | re.MULTILINE,
)
_WHITESPACE_PATTERN = re.compile(r"\s+")


def normalize_content(text: str) -> str:
    """
    Normalize content for consistent hashing across sources.

    Handles common variations between Gmail and RSS:
    - HTML formatting differences
    - Extra whitespace
    - Email footers/headers
    - Encoding variations

    Args:
        text: Raw text content to normalize

    Returns:
        Normalized text suitable for hashing
    """
    if not text:
        return ""

    # Convert to lowercase
    text = text.lower()

    # Remove HTML tags
    text = _HTML_TAG_PATTERN.sub("", text)

    # Decode common HTML entities
    text = (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )

    # Remove URLs (can vary between Gmail/RSS)
    text = _URL_PATTERN.sub("", text)

    # Remove email addresses
    text = _EMAIL_PATTERN.sub("", text)

    # Remove common email footer patterns
    text = _FOOTER_PATTERN.sub("", text)

    # Normalize whitespace
    text = _WHITESPACE_PATTERN.sub(" ", text)

    # Remove leading/trailing whitespace
    text = text.strip()

    return text


def generate_content_hash(raw_text: str) -> str:
    """
    Generate SHA-256 hash of normalized content.

    Args:
        raw_text: Raw text content from newsletter

    Returns:
        64-character SHA-256 hash hex string
    """
    normalized = normalize_content(raw_text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def calculate_content_similarity(text1: str, text2: str) -> float:
    """
    Calculate rough similarity between two texts.

    Uses normalized content length ratio as a simple similarity metric.
    More sophisticated methods (Levenshtein, embeddings) could be added.

    Args:
        text1: First text
        text2: Second text

    Returns:
        Similarity score 0.0-1.0 (1.0 = identical)
    """
    norm1 = normalize_content(text1)
    norm2 = normalize_content(text2)

    if not norm1 or not norm2:
        return 0.0

    # Simple length-based similarity
    len1, len2 = len(norm1), len(norm2)
    min_len = min(len1, len2)
    max_len = max(len1, len2)

    if max_len == 0:
        return 1.0

    return min_len / max_len


def should_skip_duplicate(
    existing_text: str, new_text: str, similarity_threshold: float = 0.85
) -> bool:
    """
    Determine if new content is a duplicate of existing content.

    Args:
        existing_text: Text from existing newsletter in database
        new_text: Text from newly ingested newsletter
        similarity_threshold: Minimum similarity to consider duplicate (0.0-1.0)

    Returns:
        True if new content should be skipped as duplicate
    """
    similarity = calculate_content_similarity(existing_text, new_text)
    return similarity >= similarity_threshold


# --- Markdown-specific functions for unified Content model ---

_LIST_MARKER_PATTERN = re.compile(r"^(\s*)[*+](\s+)")
_MULTI_SPACE_PATTERN = re.compile(r"  +")
_MULTI_BLANK_PATTERN = re.compile(r"\n{3,}")


def normalize_markdown(markdown: str) -> str:
    """
    Normalize markdown content for consistent hashing.

    Preserves semantic structure while normalizing formatting differences:
    - Consistent heading levels
    - Normalized whitespace
    - Consistent list markers
    - Removed trailing whitespace per line

    Args:
        markdown: Markdown content to normalize

    Returns:
        Normalized markdown suitable for hashing
    """
    if not markdown:
        return ""

    lines = markdown.split("\n")
    normalized_lines = []

    for line in lines:
        # Strip trailing whitespace
        line = line.rstrip()

        # Normalize list markers (-, *, +) to consistent format
        line = _LIST_MARKER_PATTERN.sub(r"\1-\2", line)

        # Normalize multiple spaces in content (not indentation)
        if not line.startswith(" " * 4) and not line.startswith("\t"):
            # Preserve leading whitespace, normalize internal
            leading = len(line) - len(line.lstrip())
            content = _MULTI_SPACE_PATTERN.sub(" ", line.lstrip())
            line = " " * leading + content

        normalized_lines.append(line)

    # Join and normalize line endings
    result = "\n".join(normalized_lines)

    # Collapse multiple blank lines into single
    result = _MULTI_BLANK_PATTERN.sub("\n\n", result)

    # Strip leading/trailing whitespace
    return result.strip()


def generate_markdown_hash(markdown: str) -> str:
    """
    Generate SHA-256 hash of normalized markdown content.

    Used for deduplication in the unified Content model. Unlike
    generate_content_hash (for raw text), this preserves markdown
    structure while normalizing formatting.

    Args:
        markdown: Markdown content to hash

    Returns:
        64-character SHA-256 hash hex string
    """
    normalized = normalize_markdown(markdown)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def generate_file_hash(file_bytes: bytes) -> str:
    """
    Generate SHA-256 hash of file bytes.

    Used for file upload deduplication before parsing.

    Args:
        file_bytes: Raw file content

    Returns:
        64-character SHA-256 hash hex string
    """
    return hashlib.sha256(file_bytes).hexdigest()
