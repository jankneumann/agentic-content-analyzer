"""Tests for Grok X Search ingestion."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from src.ingestion.xsearch import (
    GrokXClient,
    GrokXContentIngestionService,
    XPostContent,
    XThreadData,
    build_metadata,
    format_thread_markdown,
    thread_to_content_data,
)
from src.models.content import ContentSource

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_thread() -> XThreadData:
    """Single-post thread fixture."""
    return XThreadData(
        root_post_id="12345",
        thread_post_ids=["12345"],
        author_handle="testuser",
        author_name="Test User",
        posts=[XPostContent(text="This is a test post about AI.", post_id="12345")],
        posted_at=datetime(2026, 2, 23, 14, 30, tzinfo=UTC),
        is_thread=False,
        thread_length=1,
        likes=100,
        retweets=50,
        replies=10,
        source_url="https://x.com/testuser/status/12345",
    )


@pytest.fixture
def sample_multi_post_thread() -> XThreadData:
    """Multi-post thread fixture."""
    return XThreadData(
        root_post_id="67890",
        thread_post_ids=["67890", "67891", "67892"],
        author_handle="researcher",
        author_name="Dr. AI Researcher",
        posts=[
            XPostContent(text="1/ New research paper on RAG architectures...", post_id="67890"),
            XPostContent(text="2/ The key finding is that...", post_id="67891"),
            XPostContent(text="3/ In conclusion, this shows...", post_id="67892"),
        ],
        posted_at=datetime(2026, 2, 23, 10, 0, tzinfo=UTC),
        is_thread=True,
        thread_length=3,
        likes=500,
        retweets=200,
        replies=50,
        linked_urls=["https://arxiv.org/abs/2026.12345"],
        hashtags=["AI", "RAG"],
        mentions=["@openai"],
        source_url="https://x.com/researcher/status/67890",
    )


# ---------------------------------------------------------------------------
# XThreadData model tests
# ---------------------------------------------------------------------------


class TestXThreadData:
    def test_basic_creation(self, sample_thread):
        assert sample_thread.root_post_id == "12345"
        assert sample_thread.author_handle == "testuser"
        assert len(sample_thread.posts) == 1
        assert not sample_thread.is_thread

    def test_thread_creation(self, sample_multi_post_thread):
        assert sample_multi_post_thread.root_post_id == "67890"
        assert len(sample_multi_post_thread.thread_post_ids) == 3
        assert sample_multi_post_thread.is_thread
        assert sample_multi_post_thread.thread_length == 3

    def test_default_values(self):
        thread = XThreadData(
            root_post_id="999",
            author_handle="user",
        )
        assert thread.thread_post_ids == []
        assert thread.posts == []
        assert thread.likes == 0
        assert thread.is_thread is False


# ---------------------------------------------------------------------------
# Markdown formatting tests
# ---------------------------------------------------------------------------


class TestFormatThreadMarkdown:
    def test_single_post_format(self, sample_thread):
        md = format_thread_markdown(sample_thread)
        assert "# @testuser" in md
        assert "**Posted**: 2026-02-23 14:30 UTC" in md
        assert "100 likes" in md
        assert "50 retweets" in md
        assert "This is a test post about AI." in md
        assert "## Content" in md
        assert "View on X" in md

    def test_multi_post_thread_format(self, sample_multi_post_thread):
        md = format_thread_markdown(sample_multi_post_thread)
        assert "# @researcher" in md
        assert "**Thread**: 3 posts" in md
        assert "## Thread Content" in md
        assert "### 1/3" in md
        assert "### 2/3" in md
        assert "### 3/3" in md
        assert "1/ New research paper" in md
        assert "3/ In conclusion" in md

    def test_includes_links(self, sample_multi_post_thread):
        md = format_thread_markdown(sample_multi_post_thread)
        assert "## Links" in md
        assert "arxiv.org" in md

    def test_includes_source_url(self, sample_thread):
        md = format_thread_markdown(sample_thread)
        assert "https://x.com/testuser/status/12345" in md


# ---------------------------------------------------------------------------
# Metadata and ContentData conversion tests
# ---------------------------------------------------------------------------


class TestBuildMetadata:
    def test_metadata_structure(self, sample_thread):
        meta = build_metadata(sample_thread, "test prompt", 3)
        assert meta["root_post_id"] == "12345"
        assert meta["author_handle"] == "testuser"
        assert meta["search_query"] == "test prompt"
        assert meta["tool_calls_made"] == 3
        assert meta["likes"] == 100

    def test_thread_post_ids_in_metadata(self, sample_multi_post_thread):
        meta = build_metadata(sample_multi_post_thread, "prompt", 1)
        assert meta["thread_post_ids"] == ["67890", "67891", "67892"]
        assert meta["is_thread"] is True


class TestThreadToContentData:
    def test_conversion(self, sample_thread):
        cd = thread_to_content_data(sample_thread, "search prompt", 2)
        assert cd.source_type == ContentSource.XSEARCH
        assert cd.source_id == "xpost:12345"
        assert cd.author == "@testuser"
        assert cd.publication == "X (Twitter)"
        assert "This is a test post" in cd.markdown_content
        assert cd.metadata_json is not None
        assert cd.metadata_json["search_query"] == "search prompt"

    def test_source_url(self, sample_thread):
        cd = thread_to_content_data(sample_thread, "prompt", 0)
        assert cd.source_url == "https://x.com/testuser/status/12345"

    def test_title_truncation(self):
        long_text = "A" * 200
        thread = XThreadData(
            root_post_id="1",
            author_handle="user",
            posts=[XPostContent(text=long_text, post_id="1")],
        )
        cd = thread_to_content_data(thread, "p", 0)
        # Title should include @handle prefix + truncated text
        assert len(cd.title) <= 130  # "@user: " + 120 chars


# ---------------------------------------------------------------------------
# GrokXClient tests
# ---------------------------------------------------------------------------


class TestGrokXClient:
    def test_init_requires_api_key(self):
        with patch("src.ingestion.xsearch.settings") as mock_settings:
            mock_settings.xai_api_key = None
            with pytest.raises(ValueError, match="XAI_API_KEY is required"):
                GrokXClient()

    def test_init_with_explicit_key(self):
        client = GrokXClient(api_key="test-key-123")
        assert client.api_key == "test-key-123"
        assert client.model == "grok-4-1-fast"  # default

    def test_init_with_custom_model(self):
        client = GrokXClient(api_key="key", model="grok-4-1")
        assert client.model == "grok-4-1"

    def test_parse_json_threads(self):
        client = GrokXClient(api_key="key")
        json_response = """[
            {
                "root_post_id": "111",
                "author_handle": "@alice",
                "text": "Hello world",
                "likes": 42
            }
        ]"""
        threads = client.parse_threads_from_response(json_response)
        assert len(threads) == 1
        assert threads[0].root_post_id == "111"
        assert threads[0].author_handle == "alice"  # @ stripped
        assert threads[0].likes == 42

    def test_parse_synthesised_response(self):
        client = GrokXClient(api_key="key")
        text = "Here's what I found: @openai announced a new model. Check https://openai.com/blog"
        threads = client.parse_threads_from_response(text)
        assert len(threads) == 1
        assert threads[0].author_handle == "grok_synthesis"
        assert "openai" in threads[0].mentions
        assert any("openai.com" in u for u in threads[0].linked_urls)

    def test_parse_synthesised_strips_trailing_punctuation_from_urls(self):
        """URLs in prose text should not include trailing punctuation."""
        client = GrokXClient(api_key="key")
        text = (
            "Check out https://example.com/page. "
            "Also see (https://other.com/path) "
            "and https://third.com/foo;"
        )
        threads = client.parse_threads_from_response(text)
        assert len(threads) == 1
        urls = threads[0].linked_urls + threads[0].media_urls
        # None of the captured URLs should end with punctuation
        assert any("example.com/page" in u for u in urls)
        for url in urls:
            assert not url.endswith(".")
            assert not url.endswith(")")
            assert not url.endswith(";")

    def test_parse_empty_response(self):
        client = GrokXClient(api_key="key")
        threads = client.parse_threads_from_response("")
        assert threads == []

    def test_parse_whitespace_response(self):
        client = GrokXClient(api_key="key")
        threads = client.parse_threads_from_response("   \n  ")
        assert threads == []

    @patch("xai_sdk.Client")
    def test_search_calls_sdk(self, mock_client_cls):
        """Test that search() correctly calls the xAI SDK."""
        # Set up mock chain
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_chat = MagicMock()
        mock_client.chat.create.return_value = mock_chat

        # Mock stream() to yield one chunk with content
        mock_response = MagicMock()
        mock_response.server_side_tool_usage = None
        mock_chunk = MagicMock()
        mock_chunk.tool_calls = []
        mock_chunk.content = "Search results here"
        mock_chat.stream.return_value = [(mock_response, mock_chunk)]

        client = GrokXClient(api_key="test-key")
        text, calls = client.search("Find AI news")

        assert text == "Search results here"
        assert calls == 0
        mock_client_cls.assert_called_once_with(api_key="test-key")


# ---------------------------------------------------------------------------
# Service tests
# ---------------------------------------------------------------------------


class TestGrokXContentIngestionService:
    @patch("src.ingestion.xsearch.get_db")
    @patch("src.ingestion.xsearch.GrokXClient")
    def test_ingest_with_custom_prompt(self, mock_client_cls, mock_get_db):
        """Service uses custom prompt when provided."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.search.return_value = ("", 0)
        mock_client.parse_threads_from_response.return_value = []

        service = GrokXContentIngestionService(api_key="key")
        service.client = mock_client

        count = service.ingest_threads(prompt="Custom AI search")
        assert count == 0
        mock_client.search.assert_called_once()
        call_args = mock_client.search.call_args
        assert call_args[0][0] == "Custom AI search"

    @patch("src.ingestion.xsearch.get_db")
    @patch("src.ingestion.xsearch.GrokXClient")
    def test_ingest_empty_response(self, mock_client_cls, mock_get_db):
        """Service handles empty Grok response gracefully."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.search.return_value = ("", 0)

        service = GrokXContentIngestionService(api_key="key")
        service.client = mock_client

        count = service.ingest_threads(prompt="test")
        assert count == 0

    @patch("src.ingestion.xsearch.get_db")
    @patch("src.ingestion.xsearch.GrokXClient")
    def test_ingest_single_failure_does_not_block_others(self, mock_client_cls, mock_get_db):
        """One thread failing to flush should not prevent other threads from ingesting.

        Verifies the SAVEPOINT (begin_nested) isolation pattern: each thread is
        wrapped in a nested transaction so a flush failure rolls back only that
        thread, not the entire batch.
        """
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.search.return_value = ("two threads", 1)

        good_thread = XThreadData(
            root_post_id="aaa",
            thread_post_ids=["aaa"],
            author_handle="good",
            posts=[XPostContent(text="Good post", post_id="aaa")],
        )
        bad_thread = XThreadData(
            root_post_id="bbb",
            thread_post_ids=["bbb"],
            author_handle="bad",
            posts=[XPostContent(text="Bad post", post_id="bbb")],
        )
        mock_client.parse_threads_from_response.return_value = [bad_thread, good_thread]

        # Set up mock DB session — bad_thread causes flush to raise, good_thread succeeds
        mock_db = MagicMock()
        flush_call_count = 0

        def side_effect_flush():
            nonlocal flush_call_count
            flush_call_count += 1
            if flush_call_count == 1:
                raise Exception("Unique constraint violation")

        mock_db.flush.side_effect = side_effect_flush
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.execute.return_value.first.return_value = None

        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        service = GrokXContentIngestionService(api_key="key")
        service.client = mock_client

        count = service.ingest_threads(prompt="test")

        # Good thread should succeed even though bad thread failed
        assert count == 1
        # rollback should have been called for the bad thread
        mock_db.rollback.assert_called_once()
        # commit for the good thread
        mock_db.commit.assert_called_once()

    @patch("src.ingestion.xsearch.get_db")
    @patch("src.ingestion.xsearch.GrokXClient")
    def test_ingest_uses_prompt_service_when_no_prompt(self, mock_client_cls, mock_get_db):
        """Service falls back to PromptService when no prompt provided."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.search.return_value = ("", 0)
        mock_client.parse_threads_from_response.return_value = []

        # Mock the PromptService — lazy import inside _get_search_prompt,
        # so patch at source module
        with patch("src.services.prompt_service.PromptService") as mock_ps_cls:
            mock_ps = MagicMock()
            mock_ps.get_pipeline_prompt.return_value = "Default prompt from service"
            mock_ps_cls.return_value = mock_ps

            # Mock get_db for the prompt service call
            mock_db = MagicMock()
            mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

            service = GrokXContentIngestionService(api_key="key")
            service.client = mock_client

            service.ingest_threads()

            mock_ps.get_pipeline_prompt.assert_called_once_with("xsearch", "search_prompt")


# ---------------------------------------------------------------------------
# Orchestrator tests
# ---------------------------------------------------------------------------


class TestOrchestratorIntegration:
    @patch("src.ingestion.xsearch.GrokXContentIngestionService")
    def test_ingest_xsearch(self, mock_service_cls):
        """Test orchestrator function wires correctly."""
        from src.ingestion.orchestrator import ingest_xsearch

        mock_service = MagicMock()
        mock_service.ingest_threads.return_value = 3
        mock_service_cls.return_value = mock_service

        count = ingest_xsearch(prompt="test", max_threads=10)
        assert count == 3
        mock_service.ingest_threads.assert_called_once_with(
            prompt="test",
            max_threads=10,
            force_reprocess=False,
        )
        mock_service.close.assert_called_once()

    @patch("src.ingestion.xsearch.GrokXContentIngestionService")
    def test_ingest_xsearch_closes_on_error(self, mock_service_cls):
        """Service.close() is called even when ingest_threads raises."""
        from src.ingestion.orchestrator import ingest_xsearch

        mock_service = MagicMock()
        mock_service.ingest_threads.side_effect = RuntimeError("API error")
        mock_service_cls.return_value = mock_service

        with pytest.raises(RuntimeError, match="API error"):
            ingest_xsearch()

        mock_service.close.assert_called_once()
