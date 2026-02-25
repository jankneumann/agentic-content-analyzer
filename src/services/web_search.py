"""Unified Web Search Provider abstraction.

Provides a protocol and factory for ad-hoc web search across multiple providers
(Tavily, Perplexity, Grok). Used by chat, podcast generation, and digest review
for real-time web context. NOT used by ingestion pipeline (which uses dedicated
*ContentIngestionService classes via the orchestrator).

Provider implementations:
- TavilyWebSearchProvider: Wraps existing TavilyService
- PerplexityWebSearchProvider: Uses PerplexityClient for citation-rich results
- GrokWebSearchProvider: Adapts GrokXClient for X/Twitter social signal
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class WebSearchResult:
    """Structured result from a web search provider."""

    title: str
    url: str
    content: str  # Brief excerpt or snippet
    score: float | None = None
    citations: list[str] | None = None  # Perplexity-specific: source URLs
    metadata: dict[str, Any] | None = None


@runtime_checkable
class WebSearchProvider(Protocol):
    """Protocol for ad-hoc web search providers.

    Consumers (chat, podcast, review) use this to search the web.
    Ingestion consumers use orchestrator functions directly.
    """

    @property
    def name(self) -> str:
        """Provider identifier: 'tavily', 'perplexity', 'grok'."""
        ...

    def search(self, query: str, max_results: int = 3) -> list[WebSearchResult]:
        """Execute a web search and return structured results."""
        ...

    def format_results(self, results: list[WebSearchResult]) -> str:
        """Format results as a numbered list for LLM tool consumption."""
        ...


# ---------------------------------------------------------------------------
# Tavily Adapter
# ---------------------------------------------------------------------------


class TavilyWebSearchProvider:
    """Wraps existing TavilyService to implement WebSearchProvider."""

    def __init__(self) -> None:
        from src.services.tavily_service import get_tavily_service

        self._service = get_tavily_service()

    @property
    def name(self) -> str:
        return "tavily"

    def search(self, query: str, max_results: int = 3) -> list[WebSearchResult]:
        raw_results = self._service.search(query, max_results=max_results)
        return [
            WebSearchResult(
                title=r.get("title", "Untitled"),
                url=r.get("url", ""),
                content=r.get("content", ""),
                score=r.get("score"),
            )
            for r in raw_results
        ]

    def format_results(self, results: list[WebSearchResult]) -> str:
        if not results:
            return "No search results found."
        formatted = []
        for i, result in enumerate(results, 1):
            formatted.append(
                f"{i}. {result.title}\n   URL: {result.url}\n   Snippet: {result.content[:500]}..."
            )
        return "\n\n".join(formatted)


# ---------------------------------------------------------------------------
# Perplexity Adapter
# ---------------------------------------------------------------------------


class PerplexityWebSearchProvider:
    """Uses PerplexityClient for citation-rich ad-hoc search results."""

    def __init__(self) -> None:
        from src.config import settings

        self._api_key = settings.perplexity_api_key
        self._model = settings.perplexity_model

    @property
    def name(self) -> str:
        return "perplexity"

    def search(self, query: str, max_results: int = 3) -> list[WebSearchResult]:
        if not self._api_key:
            logger.warning("Perplexity API key not configured.")
            return []

        try:
            from src.ingestion.perplexity_search import PerplexityClient

            client = PerplexityClient(api_key=self._api_key, model=self._model)
            try:
                response = client.search(prompt=query)
            finally:
                client.close()

            # Convert citations into individual WebSearchResult objects
            results: list[WebSearchResult] = []
            for i, citation_url in enumerate(response.citations):
                if i >= max_results:
                    break
                results.append(
                    WebSearchResult(
                        title=f"Source {i + 1}",
                        url=citation_url,
                        content=response.content[:500] if i == 0 else "",
                        citations=response.citations,
                    )
                )

            # If no citations but we have content, return it as a single result
            if not results and response.content:
                results.append(
                    WebSearchResult(
                        title="Perplexity Search Result",
                        url="",
                        content=response.content[:500],
                        citations=[],
                    )
                )

            return results
        except Exception as e:
            logger.error(f"Perplexity search failed: {e}")
            return []

    def format_results(self, results: list[WebSearchResult]) -> str:
        if not results:
            return "No search results found."
        formatted = []
        for i, result in enumerate(results, 1):
            parts = [f"{i}. {result.title}"]
            if result.url:
                parts.append(f"   URL: {result.url}")
            if result.content:
                parts.append(f"   Snippet: {result.content[:500]}...")
            formatted.append("\n".join(parts))
        return "\n\n".join(formatted)


# ---------------------------------------------------------------------------
# Grok Adapter
# ---------------------------------------------------------------------------


class GrokWebSearchProvider:
    """Adapts GrokXClient for the WebSearchProvider protocol.

    Grok's x_search is server-side — it returns synthesized text, not
    individual results. This adapter parses the synthesis into structured
    WebSearchResult objects.
    """

    def __init__(self) -> None:
        from src.config import settings

        self._api_key = settings.xai_api_key
        self._model = settings.grok_model

    @property
    def name(self) -> str:
        return "grok"

    def search(self, query: str, max_results: int = 3) -> list[WebSearchResult]:
        if not self._api_key:
            logger.warning("xAI API key not configured.")
            return []

        try:
            from src.ingestion.xsearch import GrokXClient

            client = GrokXClient(api_key=self._api_key, model=self._model)
            response_text, _tool_calls = client.search(prompt=query)

            if not response_text.strip():
                return []

            # Parse the synthesized response into a single result
            # Grok returns prose, not structured results
            import re

            # Extract any URLs from the synthesis
            raw_urls = re.findall(r"https?://\S+", response_text)
            urls = [re.sub(r"[.,;:!?\)\]\}>]+$", "", u) for u in raw_urls]

            results: list[WebSearchResult] = []

            # Create a result per URL found, up to max_results
            for url in urls[:max_results]:
                results.append(
                    WebSearchResult(
                        title=url.split("/")[-1][:80] or "X Search Result",
                        url=url,
                        content=response_text[:300],
                        metadata={"source": "x.com"},
                    )
                )

            # If no URLs, return the synthesis as a single result
            if not results:
                results.append(
                    WebSearchResult(
                        title="Grok X Search",
                        url="",
                        content=response_text[:500],
                        metadata={"source": "x.com"},
                    )
                )

            return results[:max_results]
        except Exception as e:
            logger.error(f"Grok search failed: {e}")
            return []

    def format_results(self, results: list[WebSearchResult]) -> str:
        if not results:
            return "No search results found."
        formatted = []
        for i, result in enumerate(results, 1):
            parts = [f"{i}. {result.title}"]
            if result.url:
                parts.append(f"   URL: {result.url}")
            if result.content:
                parts.append(f"   Snippet: {result.content[:500]}...")
            formatted.append("\n".join(parts))
        return "\n\n".join(formatted)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_web_search_provider(provider: str | None = None) -> WebSearchProvider:
    """Factory function for web search providers.

    Used by ad-hoc search consumers (chat, podcast, review).
    Ingestion consumers use orchestrator functions directly.

    Args:
        provider: Override provider name. Uses settings.web_search_provider if None.

    Returns:
        WebSearchProvider instance.

    Raises:
        ValueError: If provider is unknown.
    """
    from src.config import settings as app_settings

    provider_name = provider or app_settings.web_search_provider

    if provider_name == "tavily":
        return TavilyWebSearchProvider()
    elif provider_name == "perplexity":
        return PerplexityWebSearchProvider()
    elif provider_name == "grok":
        return GrokWebSearchProvider()
    else:
        raise ValueError(
            f"Unknown web search provider: {provider_name}. Valid values: tavily, perplexity, grok"
        )
