"""Tests for ScholarWebSearchProvider."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from src.services.web_search import (
    ScholarWebSearchProvider,
    WebSearchResult,
    get_web_search_provider,
)


class TestScholarWebSearchProviderName:
    """Test the provider name property."""

    def test_name_returns_scholar(self) -> None:
        provider = ScholarWebSearchProvider()
        assert provider.name == "scholar"


class TestScholarFormatResults:
    """Test format_results with various inputs."""

    def test_empty_results(self) -> None:
        provider = ScholarWebSearchProvider()
        assert provider.format_results([]) == "No academic papers found."

    def test_single_result_with_metadata(self) -> None:
        provider = ScholarWebSearchProvider()
        results = [
            WebSearchResult(
                title="Attention Is All You Need",
                url="https://www.semanticscholar.org/paper/abc123",
                content="We propose a new simple network architecture...",
                metadata={
                    "year": 2017,
                    "citation_count": 100000,
                    "venue": "NeurIPS",
                    "fields_of_study": ["Computer Science"],
                },
            )
        ]
        formatted = provider.format_results(results)
        assert "Attention Is All You Need" in formatted
        assert "https://www.semanticscholar.org/paper/abc123" in formatted
        assert "We propose a new simple network architecture" in formatted
        assert "Year: 2017" in formatted
        assert "Citations: 100000" in formatted
        assert "Venue: NeurIPS" in formatted

    def test_result_without_metadata(self) -> None:
        provider = ScholarWebSearchProvider()
        results = [
            WebSearchResult(
                title="Some Paper",
                url="https://www.semanticscholar.org/paper/xyz",
                content="Abstract text here.",
            )
        ]
        formatted = provider.format_results(results)
        assert "Some Paper" in formatted
        assert "Abstract text here." in formatted

    def test_multiple_results(self) -> None:
        provider = ScholarWebSearchProvider()
        results = [
            WebSearchResult(
                title="Paper A",
                url="https://example.com/a",
                content="Abstract A",
            ),
            WebSearchResult(
                title="Paper B",
                url="https://example.com/b",
                content="Abstract B",
            ),
        ]
        formatted = provider.format_results(results)
        assert "1. Paper A" in formatted
        assert "2. Paper B" in formatted

    def test_result_with_zero_citation_count(self) -> None:
        """Zero citation_count should not appear in metadata line."""
        provider = ScholarWebSearchProvider()
        results = [
            WebSearchResult(
                title="New Paper",
                url="https://example.com/new",
                content="Brand new.",
                metadata={"year": 2026, "citation_count": 0, "venue": None},
            ),
        ]
        formatted = provider.format_results(results)
        assert "Year: 2026" in formatted
        assert "Citations" not in formatted


class TestScholarFactoryRegistration:
    """Test that the factory returns ScholarWebSearchProvider."""

    def test_get_web_search_provider_scholar(self) -> None:
        provider = get_web_search_provider("scholar")
        assert isinstance(provider, ScholarWebSearchProvider)
        assert provider.name == "scholar"


def _make_mock_paper(
    title: str = "Test Paper",
    paper_id: str = "abc123",
    abstract: str | None = "A short abstract.",
    year: int | None = 2024,
    citation_count: int = 42,
    venue: str | None = "ICML",
    fields_of_study: list[str] | None = None,
) -> MagicMock:
    """Create a mock S2Paper."""
    paper = MagicMock()
    paper.title = title
    paper.paper_id = paper_id
    paper.abstract = abstract
    paper.year = year
    paper.citation_count = citation_count
    paper.venue = venue
    paper.fields_of_study = fields_of_study or ["Computer Science"]
    return paper


def _setup_mock_client(
    mock_s2_module: MagicMock,
    mock_settings_module: MagicMock,
    papers: list[MagicMock],
    api_key: str = "test-key",
) -> MagicMock:
    """Wire up mock SemanticScholarClient and Settings for search tests."""
    mock_settings = MagicMock()
    mock_settings.semantic_scholar_api_key = api_key
    mock_settings_module.get_settings.return_value = mock_settings

    mock_result = MagicMock()
    mock_result.data = papers

    mock_client = MagicMock()
    mock_client.search_papers = AsyncMock(return_value=mock_result)
    mock_client.close = AsyncMock()
    mock_s2_module.SemanticScholarClient.return_value = mock_client
    return mock_client


class TestScholarSearch:
    """Test the search method with mocked SemanticScholarClient.

    We mock at the import level since the S2 client module may not exist
    in all worktrees during parallel development.
    """

    @patch.dict(
        "sys.modules",
        {
            "src.ingestion.semantic_scholar_client": MagicMock(),
            "src.config.settings": MagicMock(),
        },
    )
    def test_search_returns_web_search_results(self) -> None:
        """search() bridges async S2 client to sync WebSearchResult list."""
        import sys

        mock_s2 = sys.modules["src.ingestion.semantic_scholar_client"]
        mock_settings_mod = sys.modules["src.config.settings"]

        paper = _make_mock_paper()
        _setup_mock_client(mock_s2, mock_settings_mod, [paper])

        provider = ScholarWebSearchProvider()
        results = provider.search("transformer architecture", max_results=5)

        assert len(results) == 1
        assert results[0].title == "Test Paper"
        assert "abc123" in results[0].url
        assert results[0].content == "A short abstract."
        assert results[0].metadata is not None
        assert results[0].metadata["year"] == 2024
        assert results[0].metadata["citation_count"] == 42

    @patch.dict(
        "sys.modules",
        {
            "src.ingestion.semantic_scholar_client": MagicMock(),
            "src.config.settings": MagicMock(),
        },
    )
    def test_search_truncates_long_abstracts(self) -> None:
        import sys

        mock_s2 = sys.modules["src.ingestion.semantic_scholar_client"]
        mock_settings_mod = sys.modules["src.config.settings"]

        paper = _make_mock_paper(
            title="Long Abstract Paper",
            paper_id="xyz789",
            abstract="A" * 500,
            year=2025,
            citation_count=0,
            venue=None,
            fields_of_study=[],
        )
        _setup_mock_client(mock_s2, mock_settings_mod, [paper], api_key="")

        provider = ScholarWebSearchProvider()
        results = provider.search("test", max_results=1)

        assert len(results) == 1
        assert results[0].content == "A" * 300 + "..."
        assert len(results[0].content) == 303

    @patch.dict(
        "sys.modules",
        {
            "src.ingestion.semantic_scholar_client": MagicMock(),
            "src.config.settings": MagicMock(),
        },
    )
    def test_search_handles_no_abstract(self) -> None:
        import sys

        mock_s2 = sys.modules["src.ingestion.semantic_scholar_client"]
        mock_settings_mod = sys.modules["src.config.settings"]

        paper = _make_mock_paper(
            title="No Abstract",
            paper_id="no-abs",
            abstract=None,
            year=None,
            citation_count=0,
            venue=None,
            fields_of_study=[],
        )
        _setup_mock_client(mock_s2, mock_settings_mod, [paper], api_key="")

        provider = ScholarWebSearchProvider()
        results = provider.search("test")

        assert len(results) == 1
        assert results[0].content == ""
