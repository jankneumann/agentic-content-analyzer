"""Tests for the unified WebSearchProvider abstraction.

Covers the factory function, all three provider adapters (Tavily, Perplexity, Grok),
the WebSearchResult dataclass, and protocol conformance.

Mocking pattern:
  All provider __init__ and search() methods use lazy imports. Patch at SOURCE module:
  - TavilyWebSearchProvider.__init__: from src.services.tavily_service import ...
  - Perplexity/Grok __init__: from src.config import settings
  - Perplexity search(): from src.ingestion.perplexity_search import PerplexityClient
  - Grok search(): from src.ingestion.xsearch import GrokXClient
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.services.web_search import (
    GrokWebSearchProvider,
    PerplexityWebSearchProvider,
    TavilyWebSearchProvider,
    WebSearchProvider,
    WebSearchResult,
    get_web_search_provider,
)

# ---------------------------------------------------------------------------
# WebSearchResult dataclass
# ---------------------------------------------------------------------------


class TestWebSearchResult:
    def test_creation_with_all_fields(self):
        result = WebSearchResult(
            title="Test Article",
            url="https://example.com/article",
            content="A short excerpt from the article.",
            score=0.95,
            citations=["https://source1.com", "https://source2.com"],
            metadata={"provider": "test", "rank": 1},
        )
        assert result.title == "Test Article"
        assert result.url == "https://example.com/article"
        assert result.content == "A short excerpt from the article."
        assert result.score == 0.95
        assert result.citations == ["https://source1.com", "https://source2.com"]
        assert result.metadata == {"provider": "test", "rank": 1}

    def test_default_optional_fields_are_none(self):
        result = WebSearchResult(
            title="Minimal",
            url="https://example.com",
            content="Some content",
        )
        assert result.score is None
        assert result.citations is None
        assert result.metadata is None

    def test_required_fields_only(self):
        result = WebSearchResult(title="Title", url="", content="")
        assert result.title == "Title"
        assert result.url == ""
        assert result.content == ""


# ---------------------------------------------------------------------------
# Factory: get_web_search_provider()
# ---------------------------------------------------------------------------


class TestGetWebSearchProvider:
    @patch("src.services.tavily_service.get_tavily_service")
    def test_returns_tavily_for_tavily(self, mock_tavily):
        """Factory returns TavilyWebSearchProvider for 'tavily'."""
        provider = get_web_search_provider("tavily")
        assert isinstance(provider, TavilyWebSearchProvider)

    @patch("src.config.settings")
    def test_returns_perplexity_for_perplexity(self, mock_settings):
        mock_settings.perplexity_api_key = "test-key"
        mock_settings.perplexity_model = "sonar"
        provider = get_web_search_provider("perplexity")
        assert isinstance(provider, PerplexityWebSearchProvider)

    @patch("src.config.settings")
    def test_returns_grok_for_grok(self, mock_settings):
        mock_settings.xai_api_key = "test-xai"
        mock_settings.grok_model = "grok-3"
        provider = get_web_search_provider("grok")
        assert isinstance(provider, GrokWebSearchProvider)

    def test_raises_for_unknown_provider(self):
        with pytest.raises(ValueError, match="Unknown web search provider: foobar"):
            get_web_search_provider("foobar")

    @patch("src.services.tavily_service.get_tavily_service")
    @patch("src.config.settings")
    def test_uses_settings_when_no_override(self, mock_settings, mock_tavily):
        """When provider=None, should read from settings.web_search_provider."""
        mock_settings.web_search_provider = "tavily"
        provider = get_web_search_provider(None)
        assert isinstance(provider, TavilyWebSearchProvider)


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestProtocolConformance:
    """Verify all providers satisfy the WebSearchProvider protocol."""

    @patch("src.services.tavily_service.get_tavily_service")
    def test_tavily_is_web_search_provider(self, mock_tavily):
        provider = TavilyWebSearchProvider()
        assert isinstance(provider, WebSearchProvider)

    @patch("src.config.settings")
    def test_perplexity_is_web_search_provider(self, mock_settings):
        mock_settings.perplexity_api_key = "test"
        mock_settings.perplexity_model = "sonar"
        provider = PerplexityWebSearchProvider()
        assert isinstance(provider, WebSearchProvider)

    @patch("src.config.settings")
    def test_grok_is_web_search_provider(self, mock_settings):
        mock_settings.xai_api_key = "test"
        mock_settings.grok_model = "grok-3"
        provider = GrokWebSearchProvider()
        assert isinstance(provider, WebSearchProvider)


# ---------------------------------------------------------------------------
# TavilyWebSearchProvider
# ---------------------------------------------------------------------------


class TestTavilyWebSearchProvider:
    @patch("src.services.tavily_service.get_tavily_service")
    def test_name(self, mock_tavily):
        provider = TavilyWebSearchProvider()
        assert provider.name == "tavily"

    @patch("src.services.tavily_service.get_tavily_service")
    def test_search_returns_web_search_results(self, mock_tavily):
        mock_service = MagicMock()
        mock_service.search.return_value = [
            {
                "title": "AI News",
                "url": "https://ainews.com",
                "content": "Latest AI.",
                "score": 0.92,
            },
            {
                "title": "ML Update",
                "url": "https://ml.com",
                "content": "ML breakthroughs.",
                "score": 0.85,
            },
        ]
        mock_tavily.return_value = mock_service
        provider = TavilyWebSearchProvider()

        results = provider.search("AI news", max_results=5)

        mock_service.search.assert_called_once_with("AI news", max_results=5)
        assert len(results) == 2
        assert all(isinstance(r, WebSearchResult) for r in results)
        assert results[0].title == "AI News"
        assert results[0].score == 0.92
        assert results[1].title == "ML Update"

    @patch("src.services.tavily_service.get_tavily_service")
    def test_search_handles_missing_fields(self, mock_tavily):
        mock_service = MagicMock()
        mock_service.search.return_value = [{}]
        mock_tavily.return_value = mock_service
        provider = TavilyWebSearchProvider()

        results = provider.search("test")

        assert results[0].title == "Untitled"
        assert results[0].url == ""
        assert results[0].content == ""
        assert results[0].score is None

    @patch("src.services.tavily_service.get_tavily_service")
    def test_search_empty_results(self, mock_tavily):
        mock_service = MagicMock()
        mock_service.search.return_value = []
        mock_tavily.return_value = mock_service
        provider = TavilyWebSearchProvider()

        results = provider.search("obscure query")
        assert results == []

    @patch("src.services.tavily_service.get_tavily_service")
    def test_format_results_numbered(self, mock_tavily):
        provider = TavilyWebSearchProvider()
        results = [
            WebSearchResult(title="First", url="https://example.com/1", content="First content."),
            WebSearchResult(title="Second", url="https://example.com/2", content="Second content."),
        ]

        formatted = provider.format_results(results)

        assert "1. First" in formatted
        assert "URL: https://example.com/1" in formatted
        assert "2. Second" in formatted

    @patch("src.services.tavily_service.get_tavily_service")
    def test_format_results_empty(self, mock_tavily):
        provider = TavilyWebSearchProvider()
        assert provider.format_results([]) == "No search results found."

    @patch("src.services.tavily_service.get_tavily_service")
    def test_format_results_truncates_long_content(self, mock_tavily):
        provider = TavilyWebSearchProvider()
        long_content = "x" * 1000
        results = [WebSearchResult(title="Long", url="https://example.com", content=long_content)]

        formatted = provider.format_results(results)

        # Content truncated at 500 chars + "..."
        assert "x" * 500 + "..." in formatted


# ---------------------------------------------------------------------------
# PerplexityWebSearchProvider
# ---------------------------------------------------------------------------


class TestPerplexityWebSearchProvider:
    def _make_provider(self, api_key="test-pplx-key", model="sonar"):
        """Create PerplexityWebSearchProvider with injected settings."""
        with patch("src.config.settings") as mock_settings:
            mock_settings.perplexity_api_key = api_key
            mock_settings.perplexity_model = model
            return PerplexityWebSearchProvider()

    def test_name(self):
        provider = self._make_provider()
        assert provider.name == "perplexity"

    @patch("src.ingestion.perplexity_search.PerplexityClient")
    def test_search_maps_citations_to_results(self, mock_client_cls):
        provider = self._make_provider()

        mock_response = MagicMock()
        mock_response.content = "AI is transforming many industries with new breakthroughs."
        mock_response.citations = [
            "https://source1.com/article",
            "https://source2.com/paper",
            "https://source3.com/blog",
        ]

        mock_client = MagicMock()
        mock_client.search.return_value = mock_response
        mock_client_cls.return_value = mock_client

        results = provider.search("AI breakthroughs", max_results=3)

        assert len(results) == 3
        assert all(isinstance(r, WebSearchResult) for r in results)
        assert results[0].url == "https://source1.com/article"
        assert results[0].title == "Source 1"
        assert len(results[0].content) > 0  # First result gets content
        assert results[1].content == ""  # Others don't
        assert results[0].citations == mock_response.citations

    @patch("src.ingestion.perplexity_search.PerplexityClient")
    def test_search_respects_max_results(self, mock_client_cls):
        provider = self._make_provider()

        mock_response = MagicMock()
        mock_response.content = "Content."
        mock_response.citations = [
            "https://a.com",
            "https://b.com",
            "https://c.com",
            "https://d.com",
        ]

        mock_client = MagicMock()
        mock_client.search.return_value = mock_response
        mock_client_cls.return_value = mock_client

        results = provider.search("test", max_results=2)
        assert len(results) == 2

    def test_search_returns_empty_when_no_api_key(self):
        provider = self._make_provider(api_key=None)
        results = provider.search("test query")
        assert results == []

    def test_search_returns_empty_when_empty_api_key(self):
        provider = self._make_provider(api_key="")
        results = provider.search("test query")
        assert results == []

    @patch("src.ingestion.perplexity_search.PerplexityClient")
    def test_search_returns_single_result_when_no_citations(self, mock_client_cls):
        provider = self._make_provider()

        mock_response = MagicMock()
        mock_response.content = "AI is advancing rapidly."
        mock_response.citations = []

        mock_client = MagicMock()
        mock_client.search.return_value = mock_response
        mock_client_cls.return_value = mock_client

        results = provider.search("AI advances")

        assert len(results) == 1
        assert results[0].title == "Perplexity Search Result"
        assert results[0].url == ""
        assert results[0].content == "AI is advancing rapidly."

    @patch("src.ingestion.perplexity_search.PerplexityClient")
    def test_search_handles_exception_gracefully(self, mock_client_cls):
        provider = self._make_provider()

        mock_client = MagicMock()
        mock_client.search.side_effect = RuntimeError("API error")
        mock_client_cls.return_value = mock_client

        results = provider.search("failing query")
        assert results == []

    @patch("src.ingestion.perplexity_search.PerplexityClient")
    def test_search_closes_client(self, mock_client_cls):
        provider = self._make_provider()

        mock_response = MagicMock()
        mock_response.content = "Response."
        mock_response.citations = ["https://example.com"]

        mock_client = MagicMock()
        mock_client.search.return_value = mock_response
        mock_client_cls.return_value = mock_client

        provider.search("query")
        mock_client.close.assert_called_once()

    @patch("src.ingestion.perplexity_search.PerplexityClient")
    def test_search_closes_client_on_error(self, mock_client_cls):
        provider = self._make_provider()

        mock_client = MagicMock()
        mock_client.search.side_effect = RuntimeError("boom")
        mock_client_cls.return_value = mock_client

        provider.search("query")
        mock_client.close.assert_called_once()

    def test_format_results_with_urls(self):
        provider = self._make_provider()
        results = [
            WebSearchResult(title="Source 1", url="https://example.com/1", content="First."),
            WebSearchResult(title="Source 2", url="https://example.com/2", content=""),
        ]

        formatted = provider.format_results(results)

        assert "1. Source 1" in formatted
        assert "URL: https://example.com/1" in formatted
        assert "Snippet: First." in formatted
        assert "2. Source 2" in formatted

    def test_format_results_omits_empty_url_and_content(self):
        provider = self._make_provider()
        results = [WebSearchResult(title="No URL", url="", content="")]

        formatted = provider.format_results(results)

        assert "1. No URL" in formatted
        assert "URL:" not in formatted
        assert "Snippet:" not in formatted

    def test_format_results_empty(self):
        provider = self._make_provider()
        assert provider.format_results([]) == "No search results found."


# ---------------------------------------------------------------------------
# GrokWebSearchProvider
# ---------------------------------------------------------------------------


class TestGrokWebSearchProvider:
    def _make_provider(self, api_key="test-xai", model="grok-3"):
        """Create GrokWebSearchProvider with injected settings."""
        with patch("src.config.settings") as mock_settings:
            mock_settings.xai_api_key = api_key
            mock_settings.grok_model = model
            return GrokWebSearchProvider()

    def test_name(self):
        provider = self._make_provider()
        assert provider.name == "grok"

    @patch("src.ingestion.xsearch.GrokXClient")
    def test_search_extracts_urls_from_response(self, mock_grok_client_cls):
        provider = self._make_provider()

        response_text = (
            "Here are the latest AI developments:\n"
            "1. OpenAI released GPT-5: https://openai.com/blog/gpt5\n"
            "2. Anthropic announced Claude 4: https://anthropic.com/claude4\n"
            "3. DeepMind published new research: https://deepmind.com/research\n"
        )
        mock_client = MagicMock()
        mock_client.search.return_value = (response_text, 2)
        mock_grok_client_cls.return_value = mock_client

        results = provider.search("AI news", max_results=3)

        assert len(results) == 3
        assert all(isinstance(r, WebSearchResult) for r in results)
        assert results[0].url == "https://openai.com/blog/gpt5"
        assert results[1].url == "https://anthropic.com/claude4"
        assert results[2].url == "https://deepmind.com/research"
        assert results[0].metadata == {"source": "x.com"}

    @patch("src.ingestion.xsearch.GrokXClient")
    def test_search_limits_to_max_results(self, mock_grok_client_cls):
        provider = self._make_provider()

        response_text = "https://url1.com https://url2.com https://url3.com https://url4.com"
        mock_client = MagicMock()
        mock_client.search.return_value = (response_text, 1)
        mock_grok_client_cls.return_value = mock_client

        results = provider.search("test", max_results=2)
        assert len(results) == 2

    @patch("src.ingestion.xsearch.GrokXClient")
    def test_search_no_urls_returns_synthesis(self, mock_grok_client_cls):
        provider = self._make_provider()

        response_text = "AI is advancing rapidly with many new developments in the field."
        mock_client = MagicMock()
        mock_client.search.return_value = (response_text, 1)
        mock_grok_client_cls.return_value = mock_client

        results = provider.search("AI news")

        assert len(results) == 1
        assert results[0].title == "Grok X Search"
        assert results[0].url == ""
        assert results[0].content == response_text[:500]
        assert results[0].metadata == {"source": "x.com"}

    def test_search_returns_empty_when_no_api_key(self):
        provider = self._make_provider(api_key=None)
        results = provider.search("test")
        assert results == []

    def test_search_returns_empty_when_empty_api_key(self):
        provider = self._make_provider(api_key="")
        results = provider.search("test")
        assert results == []

    @patch("src.ingestion.xsearch.GrokXClient")
    def test_search_handles_empty_response(self, mock_grok_client_cls):
        provider = self._make_provider()

        mock_client = MagicMock()
        mock_client.search.return_value = ("", 0)
        mock_grok_client_cls.return_value = mock_client

        results = provider.search("test")
        assert results == []

    @patch("src.ingestion.xsearch.GrokXClient")
    def test_search_handles_whitespace_response(self, mock_grok_client_cls):
        provider = self._make_provider()

        mock_client = MagicMock()
        mock_client.search.return_value = ("   \n\t  ", 0)
        mock_grok_client_cls.return_value = mock_client

        results = provider.search("test")
        assert results == []

    @patch("src.ingestion.xsearch.GrokXClient")
    def test_search_handles_exception_gracefully(self, mock_grok_client_cls):
        provider = self._make_provider()

        mock_client = MagicMock()
        mock_client.search.side_effect = RuntimeError("xAI API error")
        mock_grok_client_cls.return_value = mock_client

        results = provider.search("failing query")
        assert results == []

    @patch("src.ingestion.xsearch.GrokXClient")
    def test_search_strips_trailing_punctuation(self, mock_grok_client_cls):
        provider = self._make_provider()

        response_text = (
            "Check out https://example.com/article. "
            "Also see https://example.com/paper, and "
            "https://example.com/blog)"
        )
        mock_client = MagicMock()
        mock_client.search.return_value = (response_text, 1)
        mock_grok_client_cls.return_value = mock_client

        results = provider.search("test", max_results=5)
        urls = [r.url for r in results]

        assert "https://example.com/article" in urls
        assert "https://example.com/paper" in urls
        assert "https://example.com/blog" in urls

    @patch("src.ingestion.xsearch.GrokXClient")
    def test_search_title_from_url_path(self, mock_grok_client_cls):
        provider = self._make_provider()

        response_text = "https://example.com/my-great-article"
        mock_client = MagicMock()
        mock_client.search.return_value = (response_text, 1)
        mock_grok_client_cls.return_value = mock_client

        results = provider.search("test")
        assert results[0].title == "my-great-article"

    @patch("src.ingestion.xsearch.GrokXClient")
    def test_search_content_truncated_to_300_chars(self, mock_grok_client_cls):
        provider = self._make_provider()

        long_text = "A" * 1000
        response_text = f"https://example.com/article {long_text}"
        mock_client = MagicMock()
        mock_client.search.return_value = (response_text, 1)
        mock_grok_client_cls.return_value = mock_client

        results = provider.search("test")
        assert len(results[0].content) == 300

    def test_format_results_numbered(self):
        provider = self._make_provider()
        results = [
            WebSearchResult(
                title="gpt5-announcement",
                url="https://openai.com/blog/gpt5",
                content="OpenAI has released GPT-5.",
                metadata={"source": "x.com"},
            ),
        ]

        formatted = provider.format_results(results)

        assert "1. gpt5-announcement" in formatted
        assert "URL: https://openai.com/blog/gpt5" in formatted

    def test_format_results_empty(self):
        provider = self._make_provider()
        assert provider.format_results([]) == "No search results found."
