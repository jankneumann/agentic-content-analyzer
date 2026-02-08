"""Substack URL normalization and deduplication helpers."""

from __future__ import annotations

from urllib.parse import urlparse, urlunparse

from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.models.content import Content
from src.utils.html_parser import remove_tracking_params


def normalize_substack_url(url: str | None) -> str | None:
    """Normalize a Substack post URL to its canonical form.

    Returns None if the URL is not a Substack post URL.
    """
    if not url:
        return None

    cleaned = remove_tracking_params(url)
    parsed = urlparse(cleaned)
    if not parsed.netloc:
        return None

    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]

    if not host.endswith("substack.com"):
        return None

    if "/p/" not in parsed.path and "/@" not in parsed.path:
        return None

    path = parsed.path.rstrip("/")
    if not path:
        return None

    return urlunparse(("https", host, path, "", "", ""))


def extract_substack_canonical_url(
    links: list[str] | None = None,
    source_url: str | None = None,
) -> str | None:
    """Find the first canonical Substack post URL from a source URL or link list."""
    candidates: list[str] = []
    if source_url:
        candidates.append(source_url)
    if links:
        candidates.extend(links)

    for candidate in candidates:
        normalized = normalize_substack_url(candidate)
        if normalized:
            return normalized

    return None


def find_existing_substack_content(db: Session, canonical_url: str | None) -> Content | None:
    """Find existing Content by canonical Substack URL in source_url or metadata."""
    if not canonical_url:
        return None

    return (
        db.query(Content)
        .filter(
            or_(
                Content.source_url == canonical_url,
                Content.metadata_json["substack_url"].as_string() == canonical_url,
            )
        )
        .first()
    )
