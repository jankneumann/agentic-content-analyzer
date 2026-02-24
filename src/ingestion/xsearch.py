"""Grok API X Search ingestion.

Uses the xAI SDK to search X (Twitter) for AI-relevant posts and threads,
then stores them as Content records for summarization and digest inclusion.

The ``x_search`` tool is *server-side* — Grok autonomously searches X and
returns synthesised results with citations.  We parse those results into
structured ``XThreadData`` objects and persist them via the standard
Content model.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from src.config import settings
from src.ingestion.gmail import ContentData
from src.models.content import Content, ContentSource, ContentStatus
from src.storage.database import get_db
from src.utils.content_hash import generate_markdown_hash
from src.utils.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class XPostContent(BaseModel):
    """A single post within a thread."""

    text: str
    post_id: str | None = None


class XThreadData(BaseModel):
    """Parsed data for a single X thread (or standalone post)."""

    root_post_id: str
    thread_post_ids: list[str] = Field(default_factory=list)
    author_handle: str
    author_name: str = ""
    posts: list[XPostContent] = Field(default_factory=list)
    posted_at: datetime | None = None
    is_thread: bool = False
    thread_length: int = 1
    likes: int = 0
    retweets: int = 0
    replies: int = 0
    media_urls: list[str] = Field(default_factory=list)
    linked_urls: list[str] = Field(default_factory=list)
    hashtags: list[str] = Field(default_factory=list)
    mentions: list[str] = Field(default_factory=list)
    source_url: str | None = None


@dataclass
class XSearchResult:
    """Aggregated result of an X search ingestion run."""

    items_ingested: int = 0
    items_skipped: int = 0
    tool_calls_made: int = 0
    threads_found: int = 0
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Markdown formatting
# ---------------------------------------------------------------------------


def format_thread_markdown(thread: XThreadData) -> str:
    """Format an XThreadData into rich markdown for Content.markdown_content."""
    parts: list[str] = []

    # Header
    title = thread.posts[0].text[:80] if thread.posts else "X Post"
    parts.append(f"# @{thread.author_handle} - {title}")
    parts.append("")

    # Metadata
    posted = thread.posted_at.strftime("%Y-%m-%d %H:%M UTC") if thread.posted_at else "Unknown"
    parts.append(f"**Posted**: {posted}")
    if thread.is_thread:
        parts.append(f"**Thread**: {thread.thread_length} posts")
    engagement_parts = []
    if thread.likes:
        engagement_parts.append(f"{thread.likes:,} likes")
    if thread.retweets:
        engagement_parts.append(f"{thread.retweets:,} retweets")
    if thread.replies:
        engagement_parts.append(f"{thread.replies:,} replies")
    if engagement_parts:
        parts.append(f"**Engagement**: {', '.join(engagement_parts)}")
    parts.append("")

    # Thread content
    if thread.is_thread and len(thread.posts) > 1:
        parts.append("## Thread Content")
        parts.append("")
        for i, post in enumerate(thread.posts, 1):
            parts.append(f"### {i}/{thread.thread_length}")
            parts.append(post.text)
            parts.append("")
    else:
        parts.append("## Content")
        parts.append("")
        if thread.posts:
            parts.append(thread.posts[0].text)
            parts.append("")

    # Media
    if thread.media_urls:
        parts.append("## Media")
        parts.append("")
        for url in thread.media_urls:
            parts.append(f"- [{url}]({url})")
        parts.append("")

    # Links
    if thread.linked_urls:
        parts.append("## Links")
        parts.append("")
        for url in thread.linked_urls:
            parts.append(f"- [{url}]({url})")
        parts.append("")

    # Source link
    if thread.source_url:
        parts.append("## Source")
        parts.append("")
        parts.append(f"[View on X]({thread.source_url})")
        parts.append("")

    return "\n".join(parts)


def build_metadata(thread: XThreadData, search_prompt: str, tool_calls: int) -> dict[str, Any]:
    """Build metadata_json for a Content record from thread data."""
    return {
        "root_post_id": thread.root_post_id,
        "thread_post_ids": thread.thread_post_ids,
        "author_handle": thread.author_handle,
        "author_name": thread.author_name,
        "posted_at": thread.posted_at.isoformat() if thread.posted_at else None,
        "likes": thread.likes,
        "retweets": thread.retweets,
        "replies": thread.replies,
        "is_thread": thread.is_thread,
        "thread_length": thread.thread_length,
        "media_urls": thread.media_urls,
        "linked_urls": thread.linked_urls,
        "hashtags": thread.hashtags,
        "mentions": thread.mentions,
        "search_query": search_prompt,
        "tool_calls_made": tool_calls,
    }


def thread_to_content_data(thread: XThreadData, search_prompt: str, tool_calls: int) -> ContentData:
    """Convert an XThreadData into a ContentData for storage."""
    markdown = format_thread_markdown(thread)
    title_text = thread.posts[0].text[:120] if thread.posts else "X Post"
    return ContentData(
        source_type=ContentSource.XSEARCH,
        source_id=f"xpost:{thread.root_post_id}",
        source_url=thread.source_url or f"https://x.com/i/status/{thread.root_post_id}",
        title=f"@{thread.author_handle}: {title_text}",
        author=f"@{thread.author_handle}",
        publication="X (Twitter)",
        published_date=thread.posted_at,
        markdown_content=markdown,
        content_hash=generate_markdown_hash(markdown),
        metadata_json=build_metadata(thread, search_prompt, tool_calls),
    )


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class GrokXClient:
    """Client for searching X threads using the xAI Grok SDK.

    Uses Grok's server-side ``x_search`` tool — the model autonomously
    searches X and returns a synthesised answer with embedded citations.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self.api_key = api_key or settings.xai_api_key
        self.model = model or settings.grok_model
        if not self.api_key:
            raise ValueError(
                "XAI_API_KEY is required. Set it in .env, .secrets.yaml, or environment."
            )

    def search(self, prompt: str, max_turns: int | None = None) -> tuple[str, int]:
        """Run an X search via Grok and return (response_text, tool_call_count).

        Args:
            prompt: The search prompt for Grok.
            max_turns: Max agentic tool calling turns (unused by SDK but
                       included for future compatibility).

        Returns:
            Tuple of (full response text, number of tool calls made).
        """
        from xai_sdk import Client
        from xai_sdk.chat import user
        from xai_sdk.tools import x_search

        client = Client(api_key=self.api_key)
        chat = client.chat.create(
            model=self.model,
            tools=[x_search()],
        )
        chat.append(user(prompt))

        response_text = ""
        tool_call_count = 0
        final_response = None
        for response, chunk in chat.stream():
            final_response = response
            for _tc in chunk.tool_calls:
                tool_call_count += 1
            if chunk.content:
                response_text += chunk.content

        # Capture final counts from response object
        if (
            final_response
            and hasattr(final_response, "server_side_tool_usage")
            and final_response.server_side_tool_usage
        ):
            logger.info(f"Server-side tool usage: {final_response.server_side_tool_usage}")

        logger.info(
            f"Grok X search completed: {len(response_text)} chars, {tool_call_count} tool calls"
        )
        return response_text, tool_call_count

    def parse_threads_from_response(self, response_text: str) -> list[XThreadData]:
        """Parse Grok's response into structured thread data.

        Grok returns a synthesised text response — not raw post data.
        We parse it heuristically by looking for patterns like @handles,
        post IDs, and structured sections.  For robust parsing we also
        ask Grok to return JSON when possible.
        """
        threads: list[XThreadData] = []

        # Try JSON first — if Grok returned structured data
        try:
            data = json.loads(response_text)
            if isinstance(data, list):
                for item in data:
                    thread = self._parse_json_thread(item)
                    if thread:
                        threads.append(thread)
                return threads
        except (json.JSONDecodeError, TypeError):
            pass

        # Fallback: parse the synthesised text as a single consolidated post
        # Grok's x_search returns synthesised summaries, not individual posts.
        # We create one Content record per search run with the full synthesis.
        if response_text.strip():
            thread = self._synthesised_to_thread(response_text)
            threads.append(thread)

        return threads

    def _parse_json_thread(self, item: dict[str, Any]) -> XThreadData | None:
        """Parse a single JSON item into XThreadData."""
        try:
            root_id = str(item.get("root_post_id") or item.get("post_id") or item.get("id", ""))
            if not root_id:
                return None

            posts = []
            if "posts" in item and isinstance(item["posts"], list):
                for p in item["posts"]:
                    posts.append(
                        XPostContent(
                            text=str(p.get("text", "")),
                            post_id=str(p.get("post_id", "")),
                        )
                    )
            elif "text" in item:
                posts.append(XPostContent(text=str(item["text"]), post_id=root_id))

            handle = str(item.get("author_handle", item.get("author", "unknown")))
            handle = handle.lstrip("@")

            posted_at = None
            if item.get("posted_at"):
                try:
                    from dateutil.parser import isoparse  # type: ignore[import-untyped]

                    posted_at = isoparse(str(item["posted_at"]))
                except (ValueError, TypeError):
                    pass

            thread_ids = [str(i) for i in item.get("thread_post_ids", [root_id])]

            return XThreadData(
                root_post_id=root_id,
                thread_post_ids=thread_ids,
                author_handle=handle,
                author_name=str(item.get("author_name", "")),
                posts=posts,
                posted_at=posted_at,
                is_thread=len(posts) > 1,
                thread_length=len(posts),
                likes=int(item.get("likes", 0)),
                retweets=int(item.get("retweets", 0)),
                replies=int(item.get("replies", 0)),
                media_urls=item.get("media_urls", []),
                linked_urls=item.get("linked_urls", []),
                hashtags=item.get("hashtags", []),
                mentions=item.get("mentions", []),
                source_url=item.get("source_url"),
            )
        except Exception:
            logger.warning("Failed to parse JSON thread item", exc_info=True)
            return None

    def _synthesised_to_thread(self, text: str) -> XThreadData:
        """Wrap a synthesised Grok response as a single XThreadData.

        When Grok returns a prose synthesis (its default mode), we treat
        the entire response as one content item attributed to the search.
        """
        # Generate a stable ID from the content hash
        content_hash = generate_markdown_hash(text)
        post_id = f"synth-{content_hash[:16]}"

        # Extract @handles mentioned in the text
        handles = re.findall(r"@(\w{1,15})", text)
        mentions = list(dict.fromkeys(handles))  # dedupe, preserve order

        # Extract URLs and strip trailing punctuation that gets captured
        # from prose text (e.g., "Check https://example.com." or "(https://example.com)")
        raw_urls = re.findall(r"https?://\S+", text)
        urls = [re.sub(r"[.,;:!?\)\]\}>]+$", "", u) for u in raw_urls]
        x_urls = [u for u in urls if "x.com/" in u or "twitter.com/" in u]
        other_urls = [u for u in urls if u not in x_urls]

        return XThreadData(
            root_post_id=post_id,
            thread_post_ids=[post_id],
            author_handle="grok_synthesis",
            author_name="Grok X Search Synthesis",
            posts=[XPostContent(text=text, post_id=post_id)],
            posted_at=datetime.now(UTC),
            is_thread=False,
            thread_length=1,
            mentions=mentions,
            linked_urls=other_urls,
            media_urls=x_urls,
        )


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class GrokXContentIngestionService:
    """Service for ingesting X threads into the Content model.

    Orchestrates: prompt retrieval -> Grok search -> parse -> dedup -> store.
    """

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.client = GrokXClient(api_key=api_key, model=model)

    def _get_search_prompt(self) -> str:
        """Retrieve the search prompt, checking for user overrides first."""
        from src.services.prompt_service import PromptService

        with get_db() as db:
            service = PromptService(db)
            return service.get_pipeline_prompt("xsearch", "search_prompt")

    def ingest_threads(
        self,
        *,
        prompt: str | None = None,
        max_threads: int | None = None,
        force_reprocess: bool = False,
    ) -> XSearchResult:
        """Search X and ingest discovered threads.

        Args:
            prompt: Override the default/configured search prompt.
            max_threads: Maximum threads to ingest (default from settings).
            force_reprocess: Re-ingest threads that already exist.

        Returns:
            XSearchResult with ingestion stats and error details.
        """
        result = XSearchResult()
        search_prompt = prompt or self._get_search_prompt()
        max_threads = max_threads or settings.grok_x_max_threads

        logger.info(f"Starting Grok X search (max_threads={max_threads})")

        # Run search
        response_text, tool_calls = self.client.search(
            search_prompt, max_turns=settings.grok_x_max_turns
        )
        result.tool_calls_made = tool_calls

        if not response_text.strip():
            logger.warning("Grok returned empty response")
            return result

        # Parse threads
        threads = self.client.parse_threads_from_response(response_text)
        result.threads_found = len(threads)
        logger.info(f"Parsed {len(threads)} thread(s) from Grok response")

        # Limit
        if len(threads) > max_threads:
            threads = threads[:max_threads]

        # Deduplicate and store.
        # Each thread (including its dedup check) is wrapped in a SAVEPOINT
        # (begin_nested) so a failure on one thread doesn't corrupt the
        # session or roll back previously flushed items.
        with get_db() as db:
            for thread in threads:
                try:
                    db.begin_nested()  # SAVEPOINT — wraps dedup + insert

                    if not force_reprocess and self._is_duplicate(db, thread):
                        logger.debug(f"Skipping duplicate: {thread.root_post_id}")
                        result.items_skipped += 1
                        continue

                    content_data = thread_to_content_data(thread, search_prompt, tool_calls)
                    content = Content(
                        source_type=content_data.source_type,
                        source_id=content_data.source_id,
                        source_url=content_data.source_url,
                        title=content_data.title,
                        author=content_data.author,
                        publication=content_data.publication,
                        published_date=content_data.published_date,
                        markdown_content=content_data.markdown_content,
                        content_hash=generate_markdown_hash(content_data.markdown_content),
                        status=ContentStatus.PENDING,
                        metadata_json=content_data.metadata_json,
                        ingested_at=datetime.now(UTC),
                    )
                    db.add(content)
                    db.flush()
                    result.items_ingested += 1
                    logger.info(
                        f"Ingested X content: id={content.id}, source_id={content_data.source_id}"
                    )
                except Exception as exc:
                    db.rollback()  # rolls back to SAVEPOINT, not entire transaction
                    result.errors.append(f"{thread.root_post_id}: {exc}")
                    logger.warning(
                        f"Failed to ingest thread {thread.root_post_id}",
                        exc_info=True,
                    )

            if result.items_ingested > 0:
                db.commit()
                logger.info(f"Committed {result.items_ingested} X content item(s)")

        return result

    def _is_duplicate(self, db: Any, thread: XThreadData) -> bool:
        """Check if a thread already exists using multi-level dedup.

        1. Check source_id match (root_post_id)
        2. Check if any thread post IDs overlap with stored threads
           using JSONB containment (@>) for exact array element matching
        """
        from sqlalchemy import text

        source_id = f"xpost:{thread.root_post_id}"

        # Level 1: exact source_id match
        existing = db.query(Content).filter(Content.source_id == source_id).first()
        if existing:
            return True

        # Level 2: check thread_post_ids overlap via JSONB containment.
        # Uses @> operator for exact array element matching (not substring).
        # CAST() avoids psycopg2 :param::type misparsing.
        for post_id in thread.thread_post_ids:
            existing = db.execute(
                text(
                    "SELECT 1 FROM content "
                    "WHERE CAST(source_type AS text) = :source_type "
                    "AND metadata_json->'thread_post_ids' @> CAST(:post_id_json AS jsonb) "
                    "LIMIT 1"
                ),
                {
                    "source_type": ContentSource.XSEARCH.value,
                    "post_id_json": json.dumps([post_id]),
                },
            ).first()
            if existing:
                return True

        return False

    def close(self) -> None:
        """Cleanup resources (no-op for SDK client)."""
        pass
