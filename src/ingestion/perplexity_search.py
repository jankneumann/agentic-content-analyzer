"""Perplexity Sonar API ingestion.

Uses the OpenAI SDK with base_url override to search the web for AI-relevant
content via Perplexity's Sonar API. Discovered articles are stored as Content
records with citation URLs and search metadata.

The ``PerplexityClient`` handles API communication while
``PerplexityContentIngestionService`` orchestrates the full pipeline:
prompt retrieval -> search -> parse -> dedup -> store.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from src.config import settings
from src.models.content import Content, ContentSource, ContentStatus
from src.storage.database import get_db
from src.utils.content_hash import generate_markdown_hash
from src.utils.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class PerplexityResponse(BaseModel):
    """Parsed response from the Perplexity Sonar API."""

    content: str = ""
    citations: list[str] = []
    related_questions: list[str] = []
    model: str = ""
    usage: dict[str, int] = {}


@dataclass
class PerplexitySearchResult:
    """Aggregated result of a Perplexity search ingestion run."""

    items_ingested: int = 0
    items_skipped: int = 0
    queries_made: int = 0
    citations_found: int = 0
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class PerplexityClient:
    """Client for the Perplexity Sonar API using OpenAI SDK.

    Uses openai.OpenAI with base_url="https://api.perplexity.ai".
    Perplexity-specific parameters are passed via extra_body.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self.api_key = api_key or settings.perplexity_api_key
        self.model = model or settings.perplexity_model
        self._client = None

        if not self.api_key:
            raise ValueError(
                "PERPLEXITY_API_KEY is required. Set it in .env, .secrets.yaml, or environment."
            )

    def _get_client(self) -> Any:
        """Lazy-initialize OpenAI client with Perplexity base URL."""
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=self.api_key,
                base_url="https://api.perplexity.ai",
            )
        return self._client

    def search(
        self,
        prompt: str,
        system_prompt: str | None = None,
        recency_filter: str | None = None,
        domain_filter: list[str] | None = None,
        search_context_size: str | None = None,
    ) -> PerplexityResponse:
        """Execute a Perplexity search and return structured response.

        Args:
            prompt: The search query/prompt.
            system_prompt: Optional system message for context.
            recency_filter: Time filter (hour, day, week, month).
            domain_filter: List of domains to filter results.
            search_context_size: Context size (low, medium, high).

        Returns:
            PerplexityResponse with content, citations, and metadata.
        """
        client = self._get_client()

        recency = recency_filter or settings.perplexity_search_recency_filter
        context_size = search_context_size or settings.perplexity_search_context_size
        domains = domain_filter if domain_filter is not None else settings.perplexity_domain_filter

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Build extra_body with Perplexity-specific parameters
        extra_body: dict[str, Any] = {
            "search_recency_filter": recency,
            "search_context_size": context_size,
        }
        if domains:
            extra_body["search_domain_filter"] = domains

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                extra_body=extra_body,
            )

            # Extract content and citations
            content = ""
            if response.choices:
                content = response.choices[0].message.content or ""

            # Citations are in the response object (Perplexity extension)
            citations = getattr(response, "citations", []) or []

            # Usage tracking
            usage = {}
            if response.usage:
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens or 0,
                    "completion_tokens": response.usage.completion_tokens or 0,
                    "total_tokens": (response.usage.prompt_tokens or 0)
                    + (response.usage.completion_tokens or 0),
                }

            # Related questions (if available)
            related = getattr(response, "related_questions", []) or []

            logger.info(
                f"Perplexity search completed: {len(content)} chars, "
                f"{len(citations)} citations, model={response.model}"
            )

            return PerplexityResponse(
                content=content,
                citations=citations,
                related_questions=related,
                model=response.model or self.model,
                usage=usage,
            )

        except Exception as e:
            logger.error(f"Perplexity API call failed: {e}")
            raise

    def close(self) -> None:
        """Cleanup resources."""
        self._client = None


# ---------------------------------------------------------------------------
# Content conversion
# ---------------------------------------------------------------------------


def _generate_source_id(citations: list[str]) -> str:
    """Generate a stable source_id from sorted citation URLs."""
    sorted_citations = sorted(citations)
    hash_input = json.dumps(sorted_citations)
    citation_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
    return f"perplexity:{citation_hash}"


def _format_citations_markdown(citations: list[str]) -> str:
    """Format citations as numbered markdown links."""
    if not citations:
        return ""
    lines = ["\n## Sources\n"]
    for i, url in enumerate(citations, 1):
        lines.append(f"{i}. [{url}]({url})")
    return "\n".join(lines)


def _build_markdown_content(content: str, citations: list[str]) -> str:
    """Build full markdown content with citations appended."""
    parts = [content.strip()]
    citation_section = _format_citations_markdown(citations)
    if citation_section:
        parts.append(citation_section)
    return "\n\n".join(parts)


def _build_metadata(
    prompt: str,
    response: PerplexityResponse,
    search_context_size: str,
    recency_filter: str,
    domain_filter: list[str],
) -> dict[str, Any]:
    """Build metadata_json for a Content record."""
    return {
        "search_prompt": prompt,
        "model_used": response.model,
        "search_context_size": search_context_size,
        "search_recency_filter": recency_filter,
        "domain_filter": domain_filter,
        "citations": response.citations,
        "citation_count": len(response.citations),
        "related_questions": response.related_questions,
        "tokens_used": response.usage,
    }


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class PerplexityContentIngestionService:
    """Service for ingesting web content via Perplexity Sonar API.

    Orchestrates: prompt retrieval -> search -> parse -> dedup -> store.
    """

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.client = PerplexityClient(api_key=api_key, model=model)

    def _get_search_prompt(self) -> str:
        """Retrieve the search prompt, checking for user overrides first."""
        from src.services.prompt_service import PromptService

        with get_db() as db:
            service = PromptService(db)
            return service.get_pipeline_prompt("perplexity_search", "search_prompt")

    def ingest_content(
        self,
        *,
        prompt: str | None = None,
        max_results: int | None = None,
        force_reprocess: bool = False,
        recency_filter: str | None = None,
        context_size: str | None = None,
    ) -> PerplexitySearchResult:
        """Search the web and ingest discovered content.

        Args:
            prompt: Override the default/configured search prompt.
            max_results: Maximum results to store (default from settings).
            force_reprocess: Re-ingest content that already exists.
            recency_filter: Override recency filter (hour/day/week/month).
            context_size: Override search context size (low/medium/high).

        Returns:
            PerplexitySearchResult with ingestion stats.
        """
        result = PerplexitySearchResult()
        search_prompt = prompt or self._get_search_prompt()
        max_results = max_results or settings.perplexity_max_results
        recency = recency_filter or settings.perplexity_search_recency_filter
        ctx_size = context_size or settings.perplexity_search_context_size

        logger.info(
            f"Starting Perplexity search (model={self.client.model}, "
            f"context_size={ctx_size}, recency={recency})"
        )

        start_time = time.time()

        # Run search
        try:
            response = self.client.search(
                prompt=search_prompt,
                recency_filter=recency,
                search_context_size=ctx_size,
            )
            result.queries_made = 1
            result.citations_found = len(response.citations)
        except Exception as e:
            result.errors.append(f"Search failed: {e}")
            logger.error(f"Perplexity search failed: {e}")
            return result

        if not response.content.strip():
            logger.warning("Perplexity returned empty response")
            return result

        # Build Content record
        markdown_content = _build_markdown_content(response.content, response.citations)
        source_id = _generate_source_id(response.citations)
        metadata = _build_metadata(
            search_prompt, response, ctx_size, recency, settings.perplexity_domain_filter
        )

        # Deduplicate and store
        with get_db() as db:
            try:
                db.begin_nested()  # SAVEPOINT

                if not force_reprocess and self._is_duplicate(db, source_id, response.citations):
                    logger.debug(f"Skipping duplicate: {source_id}")
                    result.items_skipped += 1
                    return result

                # Determine title from first line of content
                first_line = response.content.strip().split("\n")[0][:120]
                title = first_line if first_line else "Perplexity Web Search"

                content = Content(
                    source_type=ContentSource.PERPLEXITY,
                    source_id=source_id,
                    title=title,
                    author="Perplexity AI",
                    publication="Web Search",
                    published_date=datetime.now(UTC),
                    markdown_content=markdown_content,
                    content_hash=generate_markdown_hash(markdown_content),
                    status=ContentStatus.PENDING,
                    metadata_json=metadata,
                    ingested_at=datetime.now(UTC),
                )
                db.add(content)
                db.flush()
                result.items_ingested += 1
                logger.info(
                    f"Ingested Perplexity content: id={content.id}, "
                    f"source_id={source_id}, citations={len(response.citations)}"
                )
            except Exception as exc:
                db.rollback()
                result.errors.append(f"Storage failed: {exc}")
                logger.warning(f"Failed to store Perplexity content: {exc}", exc_info=True)

            if result.items_ingested > 0:
                db.commit()

        elapsed = time.time() - start_time
        logger.info(
            f"Perplexity ingestion complete: {result.items_ingested} ingested, "
            f"{result.items_skipped} skipped, {result.citations_found} citations, "
            f"{elapsed:.1f}s elapsed"
        )

        return result

    def _is_duplicate(
        self,
        db: Any,
        source_id: str,
        citations: list[str],
    ) -> bool:
        """Check if content already exists using multi-level dedup.

        1. Check source_id match (hash of sorted citations)
        2. Check citation URL overlap (>50% shared with existing)
        3. Fallback: content hash
        """
        from sqlalchemy import text

        # Level 1: exact source_id match
        existing = db.query(Content).filter(Content.source_id == source_id).first()
        if existing:
            return True

        # Level 2: citation URL overlap via JSONB
        if citations:
            for citation_url in citations[:5]:  # Check first 5 citations for performance
                row = db.execute(
                    text(
                        "SELECT metadata_json->'citations' AS citations "
                        "FROM contents "
                        "WHERE CAST(source_type AS text) = :source_type "
                        "AND metadata_json->'citations' @> CAST(:citation_json AS jsonb) "
                        "LIMIT 1"
                    ),
                    {
                        "source_type": ContentSource.PERPLEXITY.value,
                        "citation_json": json.dumps([citation_url]),
                    },
                ).first()

                if row and row.citations:
                    existing_citations = (
                        json.loads(row.citations)
                        if isinstance(row.citations, str)
                        else row.citations
                    )
                    overlap = len(set(citations) & set(existing_citations))
                    if overlap > len(citations) * 0.5:
                        logger.debug(
                            f"Citation overlap detected: {overlap}/{len(citations)} "
                            f"({overlap / len(citations):.0%})"
                        )
                        return True

        return False

    def close(self) -> None:
        """Cleanup resources."""
        self.client.close()
