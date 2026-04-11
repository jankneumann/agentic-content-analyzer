"""Unit tests for HuggingFace Papers ingestion."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.ingestion.huggingface_papers import (
    DiscoveredPaper,
    HuggingFacePapersClient,
    HuggingFacePapersContentIngestionService,
)
from src.models.content import ContentSource


# --- Fixtures ---


@pytest.fixture
def client():
    """Create a HuggingFacePapersClient for testing."""
    return HuggingFacePapersClient(timeout=10.0)


# --- Link Discovery Tests ---


class TestDiscoverPaperLinks:
    """Tests for HuggingFacePapersClient.discover_paper_links()."""

    def test_extracts_paper_links(self, client: HuggingFacePapersClient):
        """Paper links with arXiv IDs are extracted from HTML."""
        html = """
        <html><body>
        <div>
            <a href="/papers/2401.12345">Attention Mechanisms for LLMs</a>
            <a href="/papers/2401.67890">Diffusion Models Survey</a>
        </div>
        </body></html>
        """
        papers = client.discover_paper_links(html, "https://huggingface.co/papers")
        assert len(papers) == 2
        assert papers[0].arxiv_id == "2401.12345"
        assert papers[0].url == "https://huggingface.co/papers/2401.12345"
        assert papers[0].title_hint == "Attention Mechanisms for LLMs"
        assert papers[1].arxiv_id == "2401.67890"

    def test_version_suffix_stripped_for_dedup(self, client: HuggingFacePapersClient):
        """Version suffixes are stripped to deduplicate same paper."""
        html = """
        <html><body>
        <a href="/papers/2401.12345v2">Paper v2</a>
        <a href="/papers/2401.12345">Paper base</a>
        </body></html>
        """
        papers = client.discover_paper_links(html, "https://huggingface.co/papers")
        assert len(papers) == 1
        assert papers[0].arxiv_id == "2401.12345"

    def test_non_paper_links_ignored(self, client: HuggingFacePapersClient):
        """Links to non-paper pages are ignored."""
        html = """
        <html><body>
        <a href="/papers/2401.12345">Real Paper</a>
        <a href="/about">About Page</a>
        <a href="/models/gpt2">Model Page</a>
        <a href="/datasets/squad">Dataset Page</a>
        <a href="/papers/">Papers Index</a>
        </body></html>
        """
        papers = client.discover_paper_links(html, "https://huggingface.co/papers")
        assert len(papers) == 1
        assert papers[0].arxiv_id == "2401.12345"

    def test_max_papers_limit(self, client: HuggingFacePapersClient):
        """max_papers parameter limits results."""
        html = "<html><body>"
        for i in range(20):
            html += f'<a href="/papers/2401.{10000 + i}">Paper {i}</a>'
        html += "</body></html>"

        papers = client.discover_paper_links(
            html, "https://huggingface.co/papers", max_papers=5
        )
        assert len(papers) == 5

    def test_deduplicates_same_paper(self, client: HuggingFacePapersClient):
        """Duplicate links to the same paper are deduplicated."""
        html = """
        <html><body>
        <a href="/papers/2401.12345">First mention</a>
        <a href="/papers/2401.12345">Second mention</a>
        <a href="/papers/2401.12345">Third mention</a>
        </body></html>
        """
        papers = client.discover_paper_links(html, "https://huggingface.co/papers")
        assert len(papers) == 1

    def test_resolves_relative_urls(self, client: HuggingFacePapersClient):
        """Relative URLs are resolved to absolute."""
        html = '<html><body><a href="/papers/2401.12345">Paper</a></body></html>'
        papers = client.discover_paper_links(html, "https://huggingface.co/papers")
        assert len(papers) == 1
        assert papers[0].url == "https://huggingface.co/papers/2401.12345"

    def test_short_title_hint_ignored(self, client: HuggingFacePapersClient):
        """Title hints shorter than 10 chars are ignored."""
        html = '<html><body><a href="/papers/2401.12345">Short</a></body></html>'
        papers = client.discover_paper_links(html, "https://huggingface.co/papers")
        assert len(papers) == 1
        assert papers[0].title_hint is None

    def test_empty_page_returns_empty(self, client: HuggingFacePapersClient):
        """Empty page returns no papers."""
        html = "<html><body><p>No papers here</p></body></html>"
        papers = client.discover_paper_links(html, "https://huggingface.co/papers")
        assert len(papers) == 0

    def test_five_digit_arxiv_ids(self, client: HuggingFacePapersClient):
        """5-digit arXiv IDs (e.g., 2401.12345) are supported."""
        html = '<html><body><a href="/papers/2401.12345">Five digit paper</a></body></html>'
        papers = client.discover_paper_links(html, "https://huggingface.co/papers")
        assert len(papers) == 1
        assert papers[0].arxiv_id == "2401.12345"

    def test_four_digit_arxiv_ids(self, client: HuggingFacePapersClient):
        """4-digit arXiv IDs (e.g., 2401.1234) are supported."""
        html = '<html><body><a href="/papers/2401.1234">Four digit paper</a></body></html>'
        papers = client.discover_paper_links(html, "https://huggingface.co/papers")
        assert len(papers) == 1
        assert papers[0].arxiv_id == "2401.1234"


# --- Title Extraction Tests ---


class TestExtractTitle:
    """Tests for title extraction from paper page."""

    def test_h1_title(self):
        """Extracts title from <h1> element."""
        from bs4 import BeautifulSoup

        html = "<html><body><h1>Attention Is All You Need</h1></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        title = HuggingFacePapersClient._extract_title(soup, None)
        assert title == "Attention Is All You Need"

    def test_og_title(self):
        """Extracts title from og:title meta tag."""
        from bs4 import BeautifulSoup

        html = '<html><head><meta property="og:title" content="Transformer Architecture"></head></html>'
        soup = BeautifulSoup(html, "html.parser")
        title = HuggingFacePapersClient._extract_title(soup, None)
        assert title == "Transformer Architecture"

    def test_title_tag_strips_hf_suffix(self):
        """Strips HuggingFace suffix from <title> tag."""
        from bs4 import BeautifulSoup

        html = "<html><head><title>Paper Title - Hugging Face</title></head></html>"
        soup = BeautifulSoup(html, "html.parser")
        title = HuggingFacePapersClient._extract_title(soup, None)
        assert title == "Paper Title"

    def test_fallback_to_hint(self):
        """Falls back to title_hint when no title elements found."""
        from bs4 import BeautifulSoup

        html = "<html><body></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        title = HuggingFacePapersClient._extract_title(soup, "Hint Title from Link")
        assert title == "Hint Title from Link"

    def test_fallback_to_untitled(self):
        """Returns 'Untitled Paper' when nothing found."""
        from bs4 import BeautifulSoup

        html = "<html><body></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        title = HuggingFacePapersClient._extract_title(soup, None)
        assert title == "Untitled Paper"


# --- Author Extraction Tests ---


class TestExtractAuthors:
    """Tests for author extraction."""

    def test_profile_links(self):
        """Extracts authors from profile links."""
        from bs4 import BeautifulSoup

        html = """
        <html><body>
        <a href="/profile/alice">Alice Smith</a>
        <a href="/profile/bob">Bob Jones</a>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        author = HuggingFacePapersClient._extract_authors(soup)
        assert author == "Alice Smith, Bob Jones"

    def test_meta_author(self):
        """Extracts author from meta tag."""
        from bs4 import BeautifulSoup

        html = '<html><head><meta name="author" content="Jane Doe"></head></html>'
        soup = BeautifulSoup(html, "html.parser")
        author = HuggingFacePapersClient._extract_authors(soup)
        assert author == "Jane Doe"

    def test_citation_author_meta(self):
        """Extracts from citation_author meta tags."""
        from bs4 import BeautifulSoup

        html = """
        <html><head>
        <meta name="citation_author" content="Author One">
        <meta name="citation_author" content="Author Two">
        </head></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        author = HuggingFacePapersClient._extract_authors(soup)
        assert author == "Author One, Author Two"

    def test_no_author_returns_none(self):
        """Returns None when no author found."""
        from bs4 import BeautifulSoup

        html = "<html><body></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        author = HuggingFacePapersClient._extract_authors(soup)
        assert author is None

    def test_deduplicates_authors(self):
        """Same author appearing in multiple links is deduplicated."""
        from bs4 import BeautifulSoup

        html = """
        <html><body>
        <a href="/profile/alice">Alice</a>
        <a href="/profile/alice-2">Alice</a>
        <a href="/profile/bob">Bob</a>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        author = HuggingFacePapersClient._extract_authors(soup)
        assert author == "Alice, Bob"


# --- Abstract Extraction Tests ---


class TestExtractAbstract:
    """Tests for abstract extraction."""

    def test_abstract_class(self):
        """Extracts abstract from element with 'abstract' in class."""
        from bs4 import BeautifulSoup

        long_text = "This is a detailed abstract about transformer models. " * 5
        html = f'<html><body><div class="paper-abstract">{long_text}</div></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        abstract = HuggingFacePapersClient._extract_abstract(soup)
        assert abstract is not None
        assert "transformer" in abstract

    def test_og_description_fallback(self):
        """Falls back to OG description for abstract."""
        from bs4 import BeautifulSoup

        long_desc = "A comprehensive study of attention mechanisms in neural networks. " * 3
        html = f'<html><head><meta property="og:description" content="{long_desc}"></head></html>'
        soup = BeautifulSoup(html, "html.parser")
        abstract = HuggingFacePapersClient._extract_abstract(soup)
        assert abstract is not None
        assert "attention" in abstract

    def test_short_content_returns_none(self):
        """Content shorter than 50 chars returns None."""
        from bs4 import BeautifulSoup

        html = '<html><body><div class="abstract">Short.</div></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        abstract = HuggingFacePapersClient._extract_abstract(soup)
        assert abstract is None


# --- Content Extraction Tests ---


class TestExtractPaperContent:
    """Tests for HuggingFacePapersClient.extract_paper_content()."""

    def test_successful_extraction(self):
        """Successful extraction returns ContentData with correct fields."""
        client = HuggingFacePapersClient()
        paper = DiscoveredPaper(
            url="https://huggingface.co/papers/2401.12345",
            arxiv_id="2401.12345",
            title_hint="Test Paper Title for Extraction",
        )

        long_abstract = "We present a novel approach to transformer architectures. " * 5
        html = f"""
        <html>
        <head>
            <meta property="og:title" content="Novel Transformer Architecture">
            <meta name="author" content="John Doe">
            <meta property="og:description" content="{long_abstract}">
        </head>
        <body><h1>Novel Transformer Architecture</h1></body>
        </html>
        """

        with patch.object(client._client, "get") as mock_get:
            mock_response = MagicMock()
            mock_response.text = html
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            result = client.extract_paper_content(paper)

        assert result is not None
        assert result.source_type == ContentSource.HUGGINGFACE_PAPERS
        assert result.source_id == "hf-paper:2401.12345"
        assert result.source_url == "https://huggingface.co/papers/2401.12345"
        assert result.title == "Novel Transformer Architecture"
        assert result.author == "John Doe"
        assert result.publication == "HuggingFace Papers"
        assert result.parser_used == "HFPapersClient"
        assert "2401.12345" in result.markdown_content
        assert result.metadata_json["arxiv_id"] == "2401.12345"
        assert "arxiv.org" in result.metadata_json["arxiv_url"]
        assert len(result.content_hash) == 64  # SHA-256 hex

    def test_insufficient_content_returns_none(self):
        """Returns None when extracted content is too short."""
        client = HuggingFacePapersClient()
        paper = DiscoveredPaper(
            url="https://huggingface.co/papers/2401.99999",
            arxiv_id="2401.99999",
        )

        html = "<html><body><p>Very short</p></body></html>"

        with patch.object(client._client, "get") as mock_get:
            mock_response = MagicMock()
            mock_response.text = html
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            result = client.extract_paper_content(paper)

        assert result is None

    def test_http_error_returns_none(self):
        """Returns None on HTTP errors."""
        import httpx

        client = HuggingFacePapersClient()
        paper = DiscoveredPaper(
            url="https://huggingface.co/papers/2401.00000",
            arxiv_id="2401.00000",
        )

        with patch.object(
            client._client, "get", side_effect=httpx.ConnectError("Failed")
        ):
            result = client.extract_paper_content(paper)

        assert result is None


# --- Upvote Extraction Tests ---


class TestExtractUpvotes:
    """Tests for upvote count extraction."""

    def test_upvote_element(self):
        """Extracts upvote count from element with upvote class."""
        from bs4 import BeautifulSoup

        html = '<html><body><span class="upvote-count">42</span></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        upvotes = HuggingFacePapersClient._extract_upvotes(soup)
        assert upvotes == 42

    def test_no_upvotes_returns_none(self):
        """Returns None when no upvote element found."""
        from bs4 import BeautifulSoup

        html = "<html><body></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        upvotes = HuggingFacePapersClient._extract_upvotes(soup)
        assert upvotes is None


# --- Ingestion Service Tests ---


class TestHuggingFacePapersContentIngestionService:
    """Tests for HuggingFacePapersContentIngestionService."""

    @patch("src.ingestion.huggingface_papers.get_db")
    @patch.object(HuggingFacePapersClient, "extract_paper_content")
    @patch.object(HuggingFacePapersClient, "discover_paper_links")
    @patch.object(HuggingFacePapersClient, "fetch_listing_page")
    def test_ingest_single_source(
        self, mock_fetch, mock_discover, mock_extract, mock_db
    ):
        """Ingests papers from a single configured source."""
        mock_fetch.return_value = "<html></html>"
        mock_discover.return_value = [
            DiscoveredPaper(
                url="https://huggingface.co/papers/2401.12345",
                arxiv_id="2401.12345",
                title_hint="Test Paper",
            ),
        ]

        mock_content = MagicMock()
        mock_content.source_type = ContentSource.HUGGINGFACE_PAPERS
        mock_content.source_id = "hf-paper:2401.12345"
        mock_content.source_url = "https://huggingface.co/papers/2401.12345"
        mock_content.title = "Test Paper"
        mock_content.content_hash = "a" * 64
        mock_content.markdown_content = "Content"
        mock_content.metadata_json = {"arxiv_id": "2401.12345"}
        mock_extract.return_value = mock_content

        # Mock database - no existing content
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = None
        mock_db.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db.return_value.__exit__ = MagicMock(return_value=False)

        source = MagicMock()
        source.enabled = True
        source.url = "https://huggingface.co/papers"
        source.name = "HuggingFace Daily Papers"
        source.max_entries = 30
        source.request_delay = 0

        service = HuggingFacePapersContentIngestionService()
        result = service.ingest_content(sources=[source], max_papers=30)

        assert result.items_ingested >= 0
        assert len(result.source_results) == 1
        assert result.source_results[0].url == "https://huggingface.co/papers"

    @patch("src.ingestion.huggingface_papers.get_db")
    @patch.object(HuggingFacePapersClient, "fetch_listing_page")
    def test_http_error_does_not_abort(self, mock_fetch, mock_db):
        """HTTP errors on a source are captured, not raised."""
        import httpx

        mock_fetch.side_effect = httpx.ConnectError("Failed")

        source = MagicMock()
        source.enabled = True
        source.url = "https://huggingface.co/papers"
        source.name = "HF Papers"
        source.max_entries = 30

        service = HuggingFacePapersContentIngestionService()
        result = service.ingest_content(sources=[source])

        assert len(result.source_results) == 1
        assert result.source_results[0].success is False
        assert result.source_results[0].error is not None

    def test_no_sources_returns_empty_result(self):
        """Empty source list returns empty result."""
        service = HuggingFacePapersContentIngestionService()
        result = service.ingest_content(sources=[])
        assert result.items_ingested == 0
        assert len(result.source_results) == 0

    @patch("src.ingestion.huggingface_papers.get_db")
    @patch.object(HuggingFacePapersClient, "discover_paper_links")
    @patch.object(HuggingFacePapersClient, "fetch_listing_page")
    def test_no_papers_found(self, mock_fetch, mock_discover, mock_db):
        """Returns zero when no paper links found on page."""
        mock_fetch.return_value = "<html><body>No papers</body></html>"
        mock_discover.return_value = []

        source = MagicMock()
        source.enabled = True
        source.url = "https://huggingface.co/papers"
        source.name = "HF Papers"
        source.max_entries = 30
        source.request_delay = 0

        service = HuggingFacePapersContentIngestionService()
        result = service.ingest_content(sources=[source])

        assert result.items_ingested == 0
        assert result.source_results[0].items_fetched == 0

    @patch("src.ingestion.huggingface_papers.get_db")
    @patch.object(HuggingFacePapersClient, "extract_paper_content")
    @patch.object(HuggingFacePapersClient, "discover_paper_links")
    @patch.object(HuggingFacePapersClient, "fetch_listing_page")
    def test_skips_disabled_sources(
        self, mock_fetch, mock_discover, mock_extract, mock_db
    ):
        """Disabled sources are skipped."""
        source = MagicMock()
        source.enabled = False
        source.url = "https://huggingface.co/papers"
        source.name = "Disabled"

        service = HuggingFacePapersContentIngestionService()
        result = service.ingest_content(sources=[source])

        assert result.items_ingested == 0
        mock_fetch.assert_not_called()
