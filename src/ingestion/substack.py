"""Substack API ingestion.

Fetches Substack subscriptions via the unofficial substack_api client and ingests
recent posts for enabled sources in sources.d/substack.yaml.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import httpx
import yaml
from dateutil.parser import isoparse
from substack_api import Newsletter, Post, SubstackAuth

from src.config import settings
from src.config.sources import SourceFileConfig, SubstackSource
from src.ingestion.gmail import ContentData
from src.models.content import Content, ContentSource, ContentStatus
from src.parsers.html_markdown import convert_html_to_markdown
from src.storage.database import get_db
from src.utils.content_hash import generate_markdown_hash
from src.utils.html_parser import html_to_text
from src.utils.logging import get_logger
from src.utils.substack import (
    extract_substack_canonical_url,
    find_existing_substack_content,
    normalize_substack_url,
)

logger = get_logger(__name__)


@dataclass
class SubstackSubscription:
    name: str
    url: str
    is_paid: bool = False


@dataclass
class SyncResult:
    """Result of a substack-sync operation."""

    rss_added: int
    rss_existing: int
    rss_removed: int
    substack_added: int
    substack_existing: int


class SubstackClient:
    """Wrapper around the substack-api 1.1.3 client with HTTP fallbacks."""

    def __init__(self, session_cookie: str | None = None) -> None:
        self.session_cookie = session_cookie or settings.substack_session_cookie
        self._auth: SubstackAuth | None = None
        self._http = httpx.Client(timeout=30)
        if self.session_cookie:
            self._http.cookies.set("substack.sid", self.session_cookie)

    def _get_auth(self) -> SubstackAuth | None:
        """Get or create SubstackAuth from cookies file if available."""
        if self._auth is not None:
            return self._auth
        # SubstackAuth requires a cookies file path; session cookie is used via HTTP
        return None

    def close(self) -> None:
        self._http.close()

    def fetch_subscriptions(self) -> list[SubstackSubscription]:
        """Return a list of subscriptions (name + url + paid status)."""
        subscriptions = self._fetch_subscriptions_from_http()

        if not subscriptions:
            return []

        results: list[SubstackSubscription] = []
        for entry in subscriptions:
            name = (
                entry.get("name")
                or entry.get("publication")
                or entry.get("title")
                or entry.get("subdomain")
                or "Substack"
            )
            url = (
                entry.get("url")
                or entry.get("publication_url")
                or entry.get("base_url")
                or entry.get("canonical_url")
            )
            if not url and entry.get("subdomain"):
                url = f"https://{entry['subdomain']}.substack.com"
            if not url:
                continue
            is_paid = entry.get("membership_state") not in ("free_signup", None)
            results.append(SubstackSubscription(name=name, url=url, is_paid=is_paid))

        return results

    def _fetch_subscriptions_from_http(self) -> list[dict[str, Any]] | None:
        if not self.session_cookie:
            logger.warning("SUBSTACK_SESSION_COOKIE not set; subscription sync may be incomplete.")
            return None

        endpoints = [
            "https://substack.com/api/v1/subscriptions",
            "https://substack.com/api/v1/user/subscriptions",
        ]
        for endpoint in endpoints:
            try:
                response = self._http.get(endpoint)
                if response.status_code == 404:
                    continue
                response.raise_for_status()
                data = response.json()
                if isinstance(data, dict) and "subscriptions" in data:
                    return self._join_subscriptions_with_publications(data)
                if isinstance(data, list):
                    return data
            except Exception as exc:
                logger.warning(f"Substack HTTP subscription fetch failed: {exc}")
                continue
        return None

    def _join_subscriptions_with_publications(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        """Join subscription records with publication metadata.

        The API returns subscriptions (user-publication junction records) and
        publications (metadata with name, subdomain, base_url) as separate arrays.
        We merge them so each result has the fields fetch_subscriptions expects.
        """
        subs = data.get("subscriptions", [])
        pubs = data.get("publications", [])
        pub_by_id: dict[int, dict[str, Any]] = {p["id"]: p for p in pubs if "id" in p}

        results: list[dict[str, Any]] = []
        for sub in subs:
            pub = pub_by_id.get(sub.get("publication_id", -1), {})
            merged = {**sub, **pub}
            # Ensure the fields that fetch_subscriptions looks for are present
            if "url" not in merged and pub.get("base_url"):
                merged["url"] = pub["base_url"]
            if "name" not in merged and pub.get("subdomain"):
                merged["name"] = pub["subdomain"]
            results.append(merged)

        return results

    def fetch_posts(self, publication_url: str, max_entries: int = 10) -> list[dict[str, Any]]:
        """Fetch recent posts for a publication using substack-api 1.1.3."""
        posts = self._fetch_posts_from_api(publication_url, max_entries)
        if posts is None:
            posts = self._fetch_posts_from_http(publication_url, max_entries)
        return posts or []

    def _fetch_posts_from_api(
        self, publication_url: str, max_entries: int
    ) -> list[dict[str, Any]] | None:
        """Fetch posts using the Newsletter class from substack-api 1.1.3."""
        try:
            newsletter = Newsletter(url=publication_url, auth=self._get_auth())
            posts: list[Post] = newsletter.get_posts(sorting="new", limit=max_entries)

            results: list[dict[str, Any]] = []
            for post in posts:
                try:
                    metadata = post.get_metadata()
                    # Try to get content (may fail for paywalled posts without auth)
                    try:
                        content = post.get_content()
                    except Exception:
                        content = None

                    results.append(
                        {
                            "id": metadata.get("id"),
                            "slug": metadata.get("slug"),
                            "title": metadata.get("title"),
                            "subtitle": metadata.get("subtitle"),
                            "post_date": metadata.get("post_date"),
                            "canonical_url": metadata.get("canonical_url"),
                            "description": metadata.get("description"),
                            "body_html": content,
                            "is_paywalled": post.is_paywalled(),
                            "metadata": metadata,
                        }
                    )
                except Exception as post_exc:
                    logger.warning(f"Failed to fetch post data: {post_exc}")
                    continue

            return results if results else None
        except Exception as exc:
            logger.warning(f"Newsletter.get_posts failed for {publication_url}: {exc}")
            return None

    def _fetch_posts_from_http(
        self, publication_url: str, max_entries: int
    ) -> list[dict[str, Any]] | None:
        archive_url = urljoin(publication_url.rstrip("/") + "/", "api/v1/archive")
        try:
            response = self._http.get(archive_url, params={"limit": max_entries, "sort": "new"})
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "posts" in data:
                return data["posts"]
        except Exception as exc:
            logger.warning(f"Substack HTTP archive fetch failed: {exc}")
            return None
        return None


class SubstackContentIngestionService:
    """Service for ingesting Substack posts into the unified Content model."""

    def __init__(self, session_cookie: str | None = None) -> None:
        self.client = SubstackClient(session_cookie=session_cookie)
        if session_cookie is None and settings.substack_session_cookie is None:
            logger.warning(
                "SUBSTACK_SESSION_COOKIE not set; paid Substack posts may be unavailable."
            )

    def close(self) -> None:
        self.client.close()

    def ingest_content(
        self,
        sources: list[SubstackSource] | None = None,
        max_entries_per_source: int = 10,
        after_date: datetime | None = None,
        force_reprocess: bool = False,
    ) -> int:
        logger.info("Starting Substack content ingestion...")

        if sources is None:
            sources_config = settings.get_sources_config()
            sources = sources_config.get_substack_sources()

        if not sources:
            logger.warning("No Substack sources configured. Add sources to sources.d/substack.yaml")
            return 0

        enabled_sources = [s for s in sources if s.enabled]
        logger.info(
            f"Fetching from {len(enabled_sources)} Substack sources "
            f"({len(sources) - len(enabled_sources)} disabled)"
        )

        contents: list[ContentData] = []
        for source in enabled_sources:
            max_entries = source.max_entries or max_entries_per_source
            posts = self.client.fetch_posts(source.url, max_entries=max_entries)
            for post in posts:
                content = self._post_to_content(self._coerce_post(post), source)
                if content is None:
                    continue
                if after_date and content.published_date and content.published_date < after_date:
                    continue
                contents.append(content)

        if not contents:
            logger.info("No Substack content found")
            return 0

        count = 0
        with get_db() as db:
            for content_data in contents:
                try:
                    existing = (
                        db.query(Content)
                        .filter(
                            Content.source_type == content_data.source_type,
                            Content.source_id == content_data.source_id,
                        )
                        .first()
                    )

                    substack_duplicate = None
                    if not existing:
                        canonical_url = normalize_substack_url(content_data.source_url)
                        substack_duplicate = find_existing_substack_content(db, canonical_url)

                    content_duplicate = None
                    if not existing and not substack_duplicate and content_data.content_hash:
                        content_duplicate = (
                            db.query(Content)
                            .filter(Content.content_hash == content_data.content_hash)
                            .first()
                        )

                    if existing:
                        if force_reprocess:
                            existing.title = content_data.title
                            existing.author = content_data.author
                            existing.publication = content_data.publication
                            existing.published_date = content_data.published_date
                            existing.markdown_content = content_data.markdown_content
                            existing.links_json = content_data.links_json
                            existing.metadata_json = content_data.metadata_json
                            existing.raw_content = content_data.raw_content
                            existing.raw_format = content_data.raw_format
                            existing.parser_used = content_data.parser_used
                            existing.content_hash = content_data.content_hash
                            existing.status = ContentStatus.PARSED
                            existing.error_message = None
                            count += 1
                            logger.info(f"Updated for reprocessing: {content_data.title}")
                            continue
                        logger.debug(
                            "Content already exists (use --force to reprocess): "
                            f"{content_data.source_id}"
                        )
                        continue

                    if substack_duplicate:
                        content = Content(
                            source_type=content_data.source_type,
                            source_id=content_data.source_id,
                            source_url=content_data.source_url,
                            title=content_data.title,
                            author=content_data.author,
                            publication=content_data.publication,
                            published_date=content_data.published_date,
                            markdown_content=content_data.markdown_content,
                            links_json=content_data.links_json,
                            metadata_json=content_data.metadata_json,
                            raw_content=content_data.raw_content,
                            raw_format=content_data.raw_format,
                            parser_used=content_data.parser_used,
                            content_hash=content_data.content_hash,
                            canonical_id=substack_duplicate.id,
                            status=ContentStatus.COMPLETED,
                        )
                        db.add(content)
                        count += 1
                        logger.info(f"Linked duplicate to canonical ID {substack_duplicate.id}")
                        continue

                    if content_duplicate:
                        content = Content(
                            source_type=content_data.source_type,
                            source_id=content_data.source_id,
                            source_url=content_data.source_url,
                            title=content_data.title,
                            author=content_data.author,
                            publication=content_data.publication,
                            published_date=content_data.published_date,
                            markdown_content=content_data.markdown_content,
                            links_json=content_data.links_json,
                            metadata_json=content_data.metadata_json,
                            raw_content=content_data.raw_content,
                            raw_format=content_data.raw_format,
                            parser_used=content_data.parser_used,
                            content_hash=content_data.content_hash,
                            canonical_id=content_duplicate.id,
                            status=ContentStatus.COMPLETED,
                        )
                        db.add(content)
                        count += 1
                        logger.info(f"Linked duplicate to canonical ID {content_duplicate.id}")
                        continue

                    content = Content(
                        source_type=content_data.source_type,
                        source_id=content_data.source_id,
                        source_url=content_data.source_url,
                        title=content_data.title,
                        author=content_data.author,
                        publication=content_data.publication,
                        published_date=content_data.published_date,
                        markdown_content=content_data.markdown_content,
                        links_json=content_data.links_json,
                        metadata_json=content_data.metadata_json,
                        raw_content=content_data.raw_content,
                        raw_format=content_data.raw_format,
                        parser_used=content_data.parser_used,
                        content_hash=content_data.content_hash,
                        status=ContentStatus.PARSED,
                    )
                    db.add(content)
                    count += 1
                    logger.info(f"Ingested: {content_data.title}")

                except Exception as exc:
                    logger.error(f"Error storing content: {exc}")
                    db.rollback()
                    continue

        logger.info(f"Successfully ingested {count} Substack items")
        return count

    def _post_to_content(self, post: dict[str, Any], source: SubstackSource) -> ContentData | None:
        title = post.get("title") or post.get("subject") or "Untitled"
        raw_html = post.get("body_html") or post.get("html") or post.get("body")
        markdown_content = (
            post.get("body_markdown")
            or post.get("markdown")
            or (convert_html_to_markdown(html=raw_html) if raw_html else "")
        )
        if not markdown_content and raw_html:
            markdown_content = html_to_text(raw_html)

        if not markdown_content:
            logger.debug(f"Skipping Substack post with empty content: {title}")
            return None

        link_candidate = post.get("canonical_url") or post.get("url") or post.get("post_url")
        link_candidates = [link_candidate] if isinstance(link_candidate, str) else []
        canonical_url = extract_substack_canonical_url(
            links=link_candidates,
            source_url=source.url,
        )
        if canonical_url is None and post.get("slug"):
            canonical_url = normalize_substack_url(f"{source.url.rstrip('/')}/p/{post['slug']}")
        canonical_url = canonical_url or source.url

        published_date = self._parse_date(post.get("post_date") or post.get("published_at"))

        metadata = {
            "publication_url": source.url,
            "substack_url": canonical_url,
            "post_id": post.get("id") or post.get("post_id"),
            "slug": post.get("slug"),
        }

        source_id = str(post.get("id") or post.get("post_id") or canonical_url)
        content_hash = generate_markdown_hash(markdown_content)

        publication = source.name
        if not publication:
            pub_value = post.get("publication")
            if isinstance(pub_value, dict):
                publication = pub_value.get("name")
            elif isinstance(pub_value, str):
                publication = pub_value

        return ContentData(
            source_type=ContentSource.SUBSTACK,
            source_id=source_id,
            source_url=canonical_url,
            title=title,
            author=self._extract_author(post),
            publication=publication,
            published_date=published_date,
            markdown_content=markdown_content,
            links_json=None,
            metadata_json=metadata,
            raw_content=raw_html,
            raw_format="html" if raw_html else "text",
            parser_used="substack_api",
            content_hash=content_hash,
        )

    def _coerce_post(self, post: Any) -> dict[str, Any]:
        if isinstance(post, dict):
            return post
        if hasattr(post, "dict"):
            return post.dict()  # type: ignore[no-any-return]
        fields = (
            "title",
            "subject",
            "body_html",
            "html",
            "body",
            "body_markdown",
            "markdown",
            "canonical_url",
            "url",
            "post_url",
            "slug",
            "post_date",
            "published_at",
            "id",
            "post_id",
            "author",
        )
        return {field: getattr(post, field, None) for field in fields}

    def _extract_author(self, post: dict[str, Any]) -> str | None:
        author = post.get("author")
        if isinstance(author, dict):
            return author.get("name") or author.get("handle")
        return author

    def _parse_date(self, value: Any) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        try:
            parsed = isoparse(str(value))
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=UTC)
            return parsed
        except Exception:
            return None


def sync_substack_sources(
    output_path: Path | None = None,
    session_cookie: str | None = None,
) -> SyncResult:
    """Sync Substack subscriptions: paid → substack.yaml, free → rss.yaml."""
    sources_dir = Path(settings.sources_config_dir)
    substack_path = output_path or sources_dir / "substack.yaml"
    rss_path = sources_dir / "rss.yaml"
    substack_path.parent.mkdir(parents=True, exist_ok=True)

    client = SubstackClient(session_cookie=session_cookie)
    subscriptions = client.fetch_subscriptions()
    client.close()

    paid = [s for s in subscriptions if s.is_paid]
    free = [s for s in subscriptions if not s.is_paid]
    logger.info(f"Found {len(subscriptions)} subscriptions: {len(paid)} paid, {len(free)} free")

    substack_result = _sync_paid_to_substack(paid, substack_path)
    paid_urls = {s.url for s in paid}
    rss_result = _sync_free_to_rss(free, rss_path, exclude_urls=paid_urls)

    result = SyncResult(
        rss_added=rss_result[0],
        rss_existing=rss_result[1],
        rss_removed=rss_result[2],
        substack_added=substack_result[0],
        substack_existing=substack_result[1],
    )
    logger.info(
        f"Sync complete: "
        f"{result.substack_added} paid added to substack.yaml "
        f"({result.substack_existing} existing), "
        f"{result.rss_added} free added to rss.yaml "
        f"({result.rss_existing} already present, "
        f"{result.rss_removed} removed — now in substack.yaml)"
    )
    return result


def _sync_paid_to_substack(
    subscriptions: list[SubstackSubscription], path: Path
) -> tuple[int, int]:
    """Write paid subscriptions to substack.yaml, preserving existing entries.

    Returns (added, existing) counts.
    """
    existing_entries: dict[str, dict[str, Any]] = {}
    if path.exists():
        try:
            raw_config = yaml.safe_load(path.read_text())
            existing_config = (
                SourceFileConfig.model_validate(raw_config) if raw_config else SourceFileConfig()
            )
            for entry in existing_config.sources:
                url = normalize_substack_url(entry.get("url")) or entry.get("url")
                if url:
                    existing_entries[url] = entry
        except Exception as exc:
            logger.warning(f"Failed to read existing Substack sources: {exc}")

    added = 0
    existing = 0
    merged_sources: list[dict[str, Any]] = []
    for subscription in subscriptions:
        canonical_url = normalize_substack_url(subscription.url) or subscription.url
        entry = existing_entries.get(canonical_url)
        if entry:
            merged_sources.append(entry)
            existing += 1
        else:
            merged_sources.append(
                {
                    "name": subscription.name,
                    "url": canonical_url,
                    "enabled": True,
                    "tags": [],
                }
            )
            added += 1

    config = {
        "defaults": {"type": "substack"},
        "sources": merged_sources,
    }
    path.write_text(yaml.safe_dump(config, sort_keys=False, allow_unicode=True))
    return added, existing


def _sync_free_to_rss(
    subscriptions: list[SubstackSubscription],
    rss_path: Path,
    exclude_urls: set[str] | None = None,
) -> tuple[int, int, int]:
    """Append free Substack subscriptions to rss.yaml, deduplicating by URL.

    Removes any existing RSS entries whose base URL matches exclude_urls
    (paid subscriptions that moved to substack.yaml).

    Returns (added, already_existing, removed) counts.
    """
    # Build normalized set of paid URLs to exclude
    exclude_normalized: set[str] = set()
    if exclude_urls:
        for url in exclude_urls:
            exclude_normalized.add(_normalize_feed_url(url))

    # Load existing RSS entries and build a set of known feed URLs
    existing_urls: set[str] = set()
    existing_sources: list[dict[str, Any]] = []
    rss_defaults: dict[str, Any] = {"type": "rss"}
    removed = 0

    if rss_path.exists():
        try:
            raw_config = yaml.safe_load(rss_path.read_text())
            if raw_config:
                existing_config = SourceFileConfig.model_validate(raw_config)
                rss_defaults = raw_config.get("defaults", rss_defaults)
                for entry in existing_config.sources:
                    url = entry.get("url", "")
                    normalized = _normalize_feed_url(url)
                    if normalized in exclude_normalized:
                        logger.info(
                            f"Removing RSS entry (now in substack.yaml): {entry.get('name', url)}"
                        )
                        removed += 1
                        continue
                    existing_sources.append(entry)
                    existing_urls.add(normalized)
        except Exception as exc:
            logger.warning(f"Failed to read existing RSS sources: {exc}")

    added = 0
    already_existing = 0
    for sub in subscriptions:
        feed_url = sub.url.rstrip("/") + "/feed"
        normalized = _normalize_feed_url(feed_url)

        if normalized in existing_urls:
            already_existing += 1
            continue

        existing_sources.append({"name": sub.name, "url": feed_url})
        existing_urls.add(normalized)
        added += 1

    config = {
        "defaults": rss_defaults,
        "sources": existing_sources,
    }
    rss_path.write_text(yaml.safe_dump(config, sort_keys=False, allow_unicode=True))
    return added, already_existing, removed


def _normalize_feed_url(url: str) -> str:
    """Normalize a feed URL for dedup comparison.

    Strips scheme, www., and trailing /feed to compare base domains + paths.
    """
    from urllib.parse import urlparse

    parsed = urlparse(url.lower())
    host = parsed.netloc
    if host.startswith("www."):
        host = host[4:]
    path = parsed.path.rstrip("/")
    if path.endswith("/feed"):
        path = path[: -len("/feed")]
    return f"{host}{path}"
