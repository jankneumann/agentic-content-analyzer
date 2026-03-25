"""Unit tests for blog page scraping ingestion."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.ingestion.blog_scraper import (
    BlogContentIngestionService,
    BlogScrapingClient,
    DiscoveredLink,
)

# --- Fixtures ---


@pytest.fixture
def client():
    """Create a BlogScrapingClient for testing."""
    return BlogScrapingClient(timeout=10.0)


# --- Link Discovery Tests ---


class TestDiscoverPostLinks:
    """Tests for BlogScrapingClient.discover_post_links()."""

    def test_css_selector_extraction(self, client: BlogScrapingClient):
        """Links are extracted using configured CSS selector."""
        html = """
        <html><body>
        <article>
            <a href="/blog/post-1">Post One</a>
            <a href="/blog/post-2">Post Two</a>
        </article>
        </body></html>
        """
        links = client.discover_post_links(
            html,
            "https://example.com/blog",
            link_selector="article a[href]",
        )
        assert len(links) == 2
        assert links[0].url == "https://example.com/blog/post-1"
        assert links[0].title_hint == "Post One"
        assert links[1].url == "https://example.com/blog/post-2"

    def test_heuristic_extraction_article(self, client: BlogScrapingClient):
        """Heuristic mode extracts links from <article> elements."""
        html = """
        <html><body>
        <article>
            <a href="/posts/hello-world">Hello World</a>
        </article>
        <footer><a href="/about">About</a></footer>
        </body></html>
        """
        links = client.discover_post_links(html, "https://example.com")
        assert len(links) == 1
        assert "hello-world" in links[0].url

    def test_heuristic_extraction_main(self, client: BlogScrapingClient):
        """Heuristic mode falls back to <main> if no <article>."""
        html = """
        <html><body>
        <main>
            <a href="/posts/article-1">Article 1</a>
        </main>
        </body></html>
        """
        links = client.discover_post_links(html, "https://example.com")
        assert len(links) == 1

    def test_filters_cross_domain_links(self, client: BlogScrapingClient):
        """Links to other domains are excluded."""
        html = """
        <html><body>
        <article>
            <a href="https://example.com/blog/post-1">Own Post</a>
            <a href="https://other-domain.com/article">External</a>
        </article>
        </body></html>
        """
        links = client.discover_post_links(
            html,
            "https://example.com/blog",
            link_selector="article a[href]",
        )
        assert len(links) == 1
        assert "example.com" in links[0].url

    def test_filters_non_article_paths(self, client: BlogScrapingClient):
        """Non-article paths like /tag/, /category/, /about are excluded."""
        html = """
        <html><body>
        <article>
            <a href="/blog/real-post">Real Post</a>
            <a href="/tag/python">Python Tag</a>
            <a href="/category/tech">Tech Category</a>
            <a href="/about">About</a>
            <a href="/author/john">Author Page</a>
        </article>
        </body></html>
        """
        links = client.discover_post_links(
            html,
            "https://example.com",
            link_selector="article a[href]",
        )
        assert len(links) == 1
        assert "real-post" in links[0].url

    def test_resolves_relative_urls(self, client: BlogScrapingClient):
        """Relative URLs are resolved to absolute."""
        html = '<html><body><article><a href="../posts/new">New</a></article></body></html>'
        links = client.discover_post_links(html, "https://example.com/blog/")
        assert len(links) == 1
        assert links[0].url.startswith("https://example.com/")

    def test_deduplicates_urls(self, client: BlogScrapingClient):
        """Duplicate URLs are removed."""
        html = """
        <html><body>
        <article>
            <a href="/blog/same-post">First</a>
            <a href="/blog/same-post">Second</a>
            <a href="/blog/same-post/">Third (trailing slash)</a>
        </article>
        </body></html>
        """
        links = client.discover_post_links(
            html,
            "https://example.com",
            link_selector="article a[href]",
        )
        assert len(links) == 1

    def test_respects_max_links(self, client: BlogScrapingClient):
        """max_links parameter limits results."""
        html = "<html><body><article>"
        for i in range(20):
            html += f'<a href="/blog/post-{i}">Post {i}</a>'
        html += "</article></body></html>"

        links = client.discover_post_links(
            html,
            "https://example.com",
            link_selector="article a[href]",
            max_links=5,
        )
        assert len(links) == 5

    def test_link_pattern_filter(self, client: BlogScrapingClient):
        """link_pattern regex filters URLs."""
        html = """
        <html><body>
        <article>
            <a href="/blog/2026/03/good-post">Good</a>
            <a href="/blog/about-us">Not matching</a>
        </article>
        </body></html>
        """
        links = client.discover_post_links(
            html,
            "https://example.com",
            link_selector="article a[href]",
            link_pattern=r"/blog/\d{4}/",
        )
        assert len(links) == 1
        assert "good-post" in links[0].url

    def test_same_domain_subdomain(self, client: BlogScrapingClient):
        """Subdomain links are accepted."""
        html = """
        <html><body>
        <article>
            <a href="https://blog.example.com/post-1">Subdomain Post</a>
        </article>
        </body></html>
        """
        links = client.discover_post_links(
            html,
            "https://example.com/blog",
            link_selector="article a[href]",
        )
        assert len(links) == 1

    def test_filters_shallow_paths(self, client: BlogScrapingClient):
        """Links with paths not deeper than the index page are excluded."""
        html = """
        <html><body>
        <article>
            <a href="https://example.com/">Home</a>
            <a href="https://example.com/blog/">Blog Index</a>
            <a href="https://example.com/blog/post-1">Deep Post</a>
        </article>
        </body></html>
        """
        links = client.discover_post_links(
            html,
            "https://example.com/blog",
            link_selector="article a[href]",
        )
        assert len(links) == 1
        assert "post-1" in links[0].url


# --- Date Extraction Tests ---


class TestExtractPublishedDate:
    """Tests for BlogScrapingClient.extract_published_date()."""

    def test_og_published_time(self, client: BlogScrapingClient):
        """Extracts date from Open Graph article:published_time."""
        html = '<html><head><meta property="article:published_time" content="2026-03-20T12:00:00Z"></head></html>'
        dt = client.extract_published_date(html)
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 3
        assert dt.day == 20

    def test_time_datetime_element(self, client: BlogScrapingClient):
        """Extracts date from <time datetime> element."""
        html = '<html><body><time datetime="2026-01-15T08:30:00Z">Jan 15</time></body></html>'
        dt = client.extract_published_date(html)
        assert dt is not None
        assert dt.month == 1
        assert dt.day == 15

    def test_meta_date(self, client: BlogScrapingClient):
        """Extracts date from <meta name="date">."""
        html = '<html><head><meta name="date" content="2026-06-01"></head></html>'
        dt = client.extract_published_date(html)
        assert dt is not None
        assert dt.month == 6

    def test_json_ld_date_published(self, client: BlogScrapingClient):
        """Extracts date from JSON-LD datePublished."""
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "Article", "datePublished": "2026-02-28T10:00:00Z"}
        </script>
        </head></html>
        """
        dt = client.extract_published_date(html)
        assert dt is not None
        assert dt.month == 2
        assert dt.day == 28

    def test_fallback_returns_none(self, client: BlogScrapingClient):
        """Returns None when no date found."""
        html = "<html><body><p>No date here</p></body></html>"
        dt = client.extract_published_date(html)
        assert dt is None

    def test_json_ld_array_format(self, client: BlogScrapingClient):
        """Handles JSON-LD in array format."""
        html = """
        <html><head>
        <script type="application/ld+json">
        [{"@type": "Article", "datePublished": "2026-04-10"}]
        </script>
        </head></html>
        """
        dt = client.extract_published_date(html)
        assert dt is not None
        assert dt.month == 4

    def test_priority_og_over_time(self, client: BlogScrapingClient):
        """OG meta takes priority over <time> element."""
        html = """
        <html><head>
        <meta property="article:published_time" content="2026-01-01T00:00:00Z">
        </head><body>
        <time datetime="2026-12-31T00:00:00Z">Dec 31</time>
        </body></html>
        """
        dt = client.extract_published_date(html)
        assert dt is not None
        assert dt.month == 1  # OG date wins


# --- Title Extraction Tests ---


class TestExtractTitle:
    """Tests for title extraction."""

    def test_og_title(self):
        """Extracts title from og:title meta tag."""
        from bs4 import BeautifulSoup

        html = '<html><head><meta property="og:title" content="My Blog Post"></head></html>'
        soup = BeautifulSoup(html, "html.parser")
        title = BlogScrapingClient._extract_title(soup, "https://example.com/post")
        assert title == "My Blog Post"

    def test_h1_fallback(self):
        """Falls back to <h1> when no OG title."""
        from bs4 import BeautifulSoup

        html = "<html><body><h1>Article Heading</h1></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        title = BlogScrapingClient._extract_title(soup, "https://example.com/post")
        assert title == "Article Heading"

    def test_url_fallback(self):
        """Falls back to URL path when no title elements."""
        from bs4 import BeautifulSoup

        html = "<html><body><p>No title</p></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        title = BlogScrapingClient._extract_title(soup, "https://example.com/my-blog-post")
        assert title == "My Blog Post"


# --- Author Extraction Tests ---


class TestExtractAuthor:
    """Tests for author extraction."""

    def test_meta_author(self):
        """Extracts author from meta name=author."""
        from bs4 import BeautifulSoup

        html = '<html><head><meta name="author" content="Jane Doe"></head></html>'
        soup = BeautifulSoup(html, "html.parser")
        author = BlogScrapingClient._extract_author(soup)
        assert author == "Jane Doe"

    def test_json_ld_author(self):
        """Extracts author from JSON-LD."""
        from bs4 import BeautifulSoup

        html = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "Article", "author": {"@type": "Person", "name": "John Smith"}}
        </script>
        </head></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        author = BlogScrapingClient._extract_author(soup)
        assert author == "John Smith"

    def test_no_author_returns_none(self):
        """Returns None when no author found."""
        from bs4 import BeautifulSoup

        html = "<html><body></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        author = BlogScrapingClient._extract_author(soup)
        assert author is None


# --- Domain Matching Tests ---


class TestIsSameDomain:
    """Tests for domain matching logic."""

    def test_exact_match(self):
        assert BlogScrapingClient._is_same_domain("example.com", "example.com")

    def test_www_prefix(self):
        assert BlogScrapingClient._is_same_domain("www.example.com", "example.com")

    def test_subdomain(self):
        assert BlogScrapingClient._is_same_domain("blog.example.com", "example.com")

    def test_different_domain(self):
        assert not BlogScrapingClient._is_same_domain("other.com", "example.com")


# --- Content Extraction Tests ---


class TestExtractPostContent:
    """Tests for BlogScrapingClient.extract_post_content()."""

    @patch("src.ingestion.blog_scraper.convert_html_to_markdown")
    @patch("src.ingestion.blog_scraper.extract_links")
    def test_successful_extraction(self, mock_links, mock_convert):
        """Successful extraction returns ContentData."""
        mock_convert.return_value = (
            "# Blog Post\n\nThis is the content of the blog post. "
            + "It contains enough text to pass the minimum threshold of 100 characters required by the extraction logic. "
            * 2
        )
        mock_links.return_value = ["https://example.com/ref"]

        client = BlogScrapingClient()
        html = '<html><head><meta property="og:title" content="Test Post"><meta name="author" content="Author"></head><body><h1>Test</h1></body></html>'

        with patch.object(client._client, "get") as mock_get:
            mock_response = MagicMock()
            mock_response.text = html
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            result = client.extract_post_content("https://example.com/blog/test-post")

        assert result is not None
        assert result.source_type == "blog"
        assert result.source_id == "blog:https://example.com/blog/test-post"
        assert result.title == "Test Post"
        assert result.author == "Author"
        assert result.parser_used == "BlogScraper"

    @patch("src.ingestion.blog_scraper.convert_html_to_markdown")
    def test_insufficient_content_returns_none(self, mock_convert):
        """Returns None when extracted content is too short."""
        mock_convert.return_value = "Short"

        client = BlogScrapingClient()
        with patch.object(client._client, "get") as mock_get:
            mock_response = MagicMock()
            mock_response.text = "<html></html>"
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            result = client.extract_post_content("https://example.com/empty")

        assert result is None

    def test_http_error_returns_none(self):
        """Returns None on HTTP errors."""
        import httpx

        client = BlogScrapingClient()
        with patch.object(client._client, "get", side_effect=httpx.ConnectError("Failed")):
            result = client.extract_post_content("https://example.com/error")

        assert result is None


# --- Ingestion Service Tests ---


class TestBlogContentIngestionService:
    """Tests for BlogContentIngestionService."""

    @patch("src.ingestion.blog_scraper.get_db")
    @patch.object(BlogScrapingClient, "extract_post_content")
    @patch.object(BlogScrapingClient, "discover_post_links")
    @patch.object(BlogScrapingClient, "fetch_index_page")
    def test_ingest_single_source(self, mock_fetch, mock_discover, mock_extract, mock_db):
        """Ingests posts from a single configured source."""
        mock_fetch.return_value = "<html></html>"
        mock_discover.return_value = [
            DiscoveredLink(url="https://example.com/post-1", title_hint="Post 1"),
        ]

        mock_content = MagicMock()
        mock_content.source_type = "blog"
        mock_content.source_id = "blog:https://example.com/post-1"
        mock_content.source_url = "https://example.com/post-1"
        mock_content.title = "Post 1"
        mock_content.content_hash = "hash123"
        mock_content.markdown_content = "Content"
        mock_content.publication = None
        mock_extract.return_value = mock_content

        # Mock database - no existing content
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = None
        mock_db.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db.return_value.__exit__ = MagicMock(return_value=False)

        source = MagicMock()
        source.enabled = True
        source.url = "https://example.com/blog"
        source.name = "Test Blog"
        source.link_selector = None
        source.link_pattern = None
        source.max_entries = 10
        source.request_delay = 0
        source.content_filter_strategy = "none"

        service = BlogContentIngestionService()
        result = service.ingest_content(
            sources=[source],
            max_entries_per_source=10,
        )

        assert result.items_ingested >= 0
        assert len(result.source_results) == 1
        assert result.source_results[0].url == "https://example.com/blog"

    @patch("src.ingestion.blog_scraper.get_db")
    @patch.object(BlogScrapingClient, "fetch_index_page")
    def test_http_error_does_not_abort(self, mock_fetch, mock_db):
        """HTTP errors on a source don't abort other sources."""
        import httpx

        mock_fetch.side_effect = httpx.ConnectError("Failed")

        source = MagicMock()
        source.enabled = True
        source.url = "https://broken.com/blog"
        source.name = "Broken Blog"
        source.max_entries = 10

        service = BlogContentIngestionService()
        result = service.ingest_content(sources=[source])

        assert len(result.source_results) == 1
        assert result.source_results[0].success is False
        assert result.source_results[0].error is not None

    def test_no_sources_returns_empty_result(self):
        """Empty source list returns empty result."""
        service = BlogContentIngestionService()
        result = service.ingest_content(sources=[])
        assert result.items_ingested == 0
        assert len(result.source_results) == 0
