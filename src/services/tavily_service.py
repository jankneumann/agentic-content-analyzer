"""Service for performing web searches using Tavily."""

from typing import Any

from tavily import TavilyClient

from src.config.settings import settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


class TavilyService:
    """Service for Tavily web search integration."""

    def __init__(self, api_key: str | None = None):
        """Initialize Tavily service.

        Args:
            api_key: Tavily API key. Defaults to settings.tavily_api_key.
        """
        self.api_key = api_key or settings.tavily_api_key
        self.client = None

        if self.api_key:
            self.client = TavilyClient(api_key=self.api_key)
        else:
            logger.warning("Tavily API key not configured. Web search will be unavailable.")

    def search(self, query: str, search_depth: str = "basic", max_results: int = 3) -> list[dict[str, Any]]:
        """Perform a web search.

        Args:
            query: Search query string.
            search_depth: "basic" or "advanced".
            max_results: Number of results to return.

        Returns:
            List of search result dictionaries with 'title', 'url', 'content'.
        """
        if not self.client:
            logger.warning("Web search requested but Tavily client is not initialized.")
            return []

        try:
            response = self.client.search(
                query=query,
                search_depth=search_depth,
                max_results=max_results,
            )
            return response.get("results", [])
        except Exception as e:
            logger.error(f"Tavily search failed: {e}")
            return []

    def format_results(self, results: list[dict[str, Any]]) -> str:
        """Format search results into a readable string for LLM context.

        Args:
            results: List of search result dictionaries.

        Returns:
            Formatted string.
        """
        if not results:
            return "No search results found."

        formatted = []
        for i, result in enumerate(results, 1):
            formatted.append(
                f"{i}. {result.get('title', 'Untitled')}\n"
                f"   URL: {result.get('url', 'N/A')}\n"
                f"   Snippet: {result.get('content', 'No content available')[:500]}..."
            )

        return "\n\n".join(formatted)


# Global instance
_tavily_service = None

def get_tavily_service() -> TavilyService:
    """Get the singleton Tavily service instance."""
    global _tavily_service
    if _tavily_service is None:
        _tavily_service = TavilyService()
    return _tavily_service
