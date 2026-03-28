"""Content relevance filter for ingestion sources.

Shared utility that determines whether ingested content is relevant to
configured topics. Supports two strategies that can be combined:

- **keyword**: Fast title + excerpt keyword matching (zero cost, ~0ms)
- **llm**: LLM-based classification using title + first N characters (default: gemini-2.5-flash-lite)
- **keyword+llm**: Keyword pre-filter, then LLM confirmation on matches

Usage:
    from src.services.content_filter import ContentRelevanceFilter

    # Create filter with explicit config
    f = ContentRelevanceFilter(
        strategy="keyword+llm",
        topics=["AI", "machine learning", "leadership"],
    )

    # Filter a list of ContentData items
    relevant = f.filter_contents(contents)

    # Check a single item
    if f.is_relevant(title="New LLM Release", content="..."):
        ...
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class FilterResult:
    """Result of a relevance check."""

    relevant: bool
    strategy_used: str  # "keyword", "llm", "none", "keyword+llm"
    matched_keywords: list[str] = field(default_factory=list)


class ContentRelevanceFilter:
    """Determines whether content is relevant to configured topics.

    Reusable across all ingestion sources. Instantiate once per ingestion run,
    call is_relevant() for each item.

    Args:
        strategy: Filtering strategy — "none", "keyword", "llm", or "keyword+llm".
        topics: List of topic strings to match against (e.g., ["AI", "machine learning"]).
        excerpt_chars: Number of characters from content start used for LLM classification.
        model_override: Override the default model (MODEL_CONTENT_FILTERING / gemini-2.5-flash-lite).
    """

    def __init__(
        self,
        strategy: str = "none",
        topics: list[str] | None = None,
        excerpt_chars: int = 1000,
        model_override: str | None = None,
    ) -> None:
        self.strategy = strategy
        self.topics = topics or []
        self.excerpt_chars = excerpt_chars
        self.model_override = model_override

        # Pre-compile keyword patterns for fast matching
        self._keyword_patterns: list[tuple[str, re.Pattern[str]]] = []
        if self.topics:
            for topic in self.topics:
                # Word-boundary match, case-insensitive
                pattern = re.compile(r"\b" + re.escape(topic) + r"\b", re.IGNORECASE)
                self._keyword_patterns.append((topic, pattern))

    @property
    def enabled(self) -> bool:
        """Whether filtering is active (strategy != none and topics configured)."""
        return self.strategy != "none" and len(self.topics) > 0

    def is_relevant(
        self,
        title: str,
        content: str,
    ) -> FilterResult:
        """Check whether content is relevant to configured topics.

        Args:
            title: Content title.
            content: Markdown content (full or excerpt — will be truncated to excerpt_chars).

        Returns:
            FilterResult with relevance decision and metadata.
        """
        if not self.enabled:
            return FilterResult(relevant=True, strategy_used="none")

        excerpt = content[: self.excerpt_chars] if content else ""
        text = f"{title} {excerpt}".strip()

        if self.strategy == "keyword":
            return self._check_keywords(text)
        elif self.strategy == "llm":
            return self._check_llm(title, excerpt)
        elif self.strategy == "keyword+llm":
            keyword_result = self._check_keywords(text)
            if not keyword_result.relevant:
                # Keywords found nothing — try LLM as fallback
                return self._check_llm(title, excerpt)
            return keyword_result
        else:
            logger.warning(f"Unknown content filter strategy: {self.strategy!r}, passing through")
            return FilterResult(relevant=True, strategy_used="none")

    def filter_contents(
        self,
        contents: list,
    ) -> list:
        """Filter a list of ContentData-like objects by relevance.

        Each item must have `title` and `markdown_content` attributes.
        Returns only relevant items. Logs filtered-out items at debug level.

        Args:
            contents: List of objects with title and markdown_content attributes.

        Returns:
            Filtered list of relevant items.
        """
        if not self.enabled:
            return contents

        relevant = []
        filtered_count = 0
        for item in contents:
            result = self.is_relevant(
                title=item.title,
                content=item.markdown_content,
            )
            if result.relevant:
                relevant.append(item)
            else:
                filtered_count += 1
                logger.debug(f"Filtered out (strategy={result.strategy_used}): {item.title!r}")

        if filtered_count > 0:
            logger.info(
                f"Content filter: {len(relevant)} relevant, {filtered_count} filtered out "
                f"(strategy={self.strategy}, topics={len(self.topics)})"
            )

        return relevant

    # --- Private methods ---

    def _check_keywords(self, text: str) -> FilterResult:
        """Check for keyword matches in combined title + content text."""
        matched = []
        for topic, pattern in self._keyword_patterns:
            if pattern.search(text):
                matched.append(topic)

        return FilterResult(
            relevant=len(matched) > 0,
            strategy_used="keyword",
            matched_keywords=matched,
        )

    def _check_llm(self, title: str, excerpt: str) -> FilterResult:
        """Classify content relevance using an LLM."""
        try:
            return self._call_llm(title, excerpt)
        except Exception:
            logger.warning("LLM content filter failed, defaulting to relevant", exc_info=True)
            return FilterResult(relevant=True, strategy_used="llm")

    def _call_llm(self, title: str, excerpt: str) -> FilterResult:
        """Make the actual LLM call for relevance classification."""
        from src.config.models import ModelStep, get_model_config
        from src.services.llm_router import LLMRouter
        from src.services.prompt_service import PromptService

        model_config = get_model_config()
        model = self.model_override or model_config.get_model_for_step(ModelStep.CONTENT_FILTERING)

        prompt_service = PromptService()
        system_prompt = prompt_service.get_pipeline_prompt("content_filtering", "system")
        topics_str = ", ".join(self.topics)

        # Truncate excerpt for prompt (use configured chars)
        truncated = excerpt[: self.excerpt_chars] if excerpt else "(no content)"
        user_prompt = prompt_service.render(
            "pipeline.content_filtering.user_template",
            topics=topics_str,
            title=title,
            excerpt=truncated,
        )

        router = LLMRouter(model_config)
        response = router.generate_sync(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=32,
            temperature=0.0,
        )

        # Parse JSON response
        relevant = self._parse_llm_response(response.text)
        logger.debug(
            f"LLM filter: title={title!r} → relevant={relevant} "
            f"(model={model}, tokens={response.input_tokens}+{response.output_tokens})"
        )

        return FilterResult(relevant=relevant, strategy_used="llm")

    @staticmethod
    def _parse_llm_response(text: str) -> bool:
        """Parse the LLM's JSON response, defaulting to relevant on parse failure."""
        text = text.strip()
        # Strip markdown code block if present
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]).strip()
            if text.startswith("json"):
                text = text[4:].strip()

        try:
            data = json.loads(text)
            return bool(data.get("relevant", True))
        except (json.JSONDecodeError, AttributeError):
            logger.warning(f"Could not parse LLM filter response: {text!r}, defaulting to relevant")
            return True


def create_content_filter(
    source: object | None = None,
    *,
    strategy: str | None = None,
    topics: list[str] | None = None,
    excerpt_chars: int | None = None,
) -> ContentRelevanceFilter:
    """Create a ContentRelevanceFilter from source config.

    Filter configuration is read from sources.d/ via the standard cascade:
      _defaults.yaml → per-file defaults → per-source entry

    Explicit keyword arguments take highest precedence.

    Args:
        source: A source object (e.g., RSSSource, BlogSource) whose
            content_filter_* attributes provide per-source overrides.
            These cascade over _defaults.yaml and per-file defaults.
        strategy: Explicit override (highest precedence).
        topics: Explicit override (highest precedence).
        excerpt_chars: Explicit override (highest precedence).

    Returns:
        Configured ContentRelevanceFilter instance.
    """
    # Resolve from source object (already has cascade-resolved values)
    src_strategy = getattr(source, "content_filter_strategy", None) if source else None
    src_topics = getattr(source, "content_filter_topics", None) if source else None
    src_excerpt = getattr(source, "content_filter_excerpt_chars", None) if source else None

    # Explicit args > source config > hardcoded defaults
    resolved_strategy = strategy or src_strategy or "none"
    resolved_topics = topics or src_topics or []
    resolved_excerpt = excerpt_chars or src_excerpt or 1000

    return ContentRelevanceFilter(
        strategy=resolved_strategy,
        topics=resolved_topics,
        excerpt_chars=resolved_excerpt,
    )
