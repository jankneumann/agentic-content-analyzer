"""Content normalization and hashing utilities for deduplication.

This module provides utilities to normalize newsletter content and generate
consistent hashes for detecting duplicate content across different sources
(Gmail, RSS) despite formatting differences.
"""

import hashlib
import re


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
    text = re.sub(r"<[^>]+>", "", text)

    # Decode common HTML entities
    text = text.replace("&nbsp;", " ")
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')
    text = text.replace("&#39;", "'")

    # Remove URLs (can vary between Gmail/RSS)
    text = re.sub(r"https?://\S+", "", text)

    # Remove email addresses
    text = re.sub(r"\S+@\S+", "", text)

    # Remove common email footer patterns
    footer_patterns = [
        r"unsubscribe.*$",
        r"view in browser.*$",
        r"forward to a friend.*$",
        r"update your preferences.*$",
        r"manage your subscription.*$",
        r"click here to.*$",
        r"you received this email because.*$",
        r"this email was sent to.*$",
    ]
    for pattern in footer_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.MULTILINE)

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text)

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
