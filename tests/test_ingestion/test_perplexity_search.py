"""Tests for Perplexity Sonar API ingestion module.

Covers:
- PerplexityResponse model
- PerplexitySearchResult dataclass
- PerplexityClient: init, search, close, lazy client creation
- Helper functions: _generate_source_id, _format_citations_markdown,
  _build_markdown_content, _build_metadata
- PerplexityContentIngestionService: full ingest_content lifecycle,
  dedup, error handling, force_reprocess
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.ingestion.perplexity_search import (
    PerplexityClient,
    PerplexityContentIngestionService,
    PerplexityResponse,
    PerplexitySearchResult,
    _build_markdown_content,
    _build_metadata,
    _format_citations_markdown,
    _generate_source_id,
)

# ---------------------------------------------------------------------------
# PerplexityResponse model
# ---------------------------------------------------------------------------


class TestPerplexityResponse:
    def test_defaults(self):
        r = PerplexityResponse()
        assert r.content == ""
        assert r.citations == []
        assert r.related_questions == []
        assert r.model == ""
        assert r.usage == {}

    def test_full_creation(self):
        r = PerplexityResponse(
            content="AI summary content",
            citations=["https://a.com", "https://b.com"],
            related_questions=["What about X?"],
            model="sonar",
            usage={"prompt_tokens": 50, "completion_tokens": 100, "total_tokens": 150},
        )
        assert r.content == "AI summary content"
        assert len(r.citations) == 2
        assert r.model == "sonar"
        assert r.usage["total_tokens"] == 150


# ---------------------------------------------------------------------------
# PerplexitySearchResult dataclass
# ---------------------------------------------------------------------------


class TestPerplexitySearchResult:
    def test_defaults(self):
        r = PerplexitySearchResult()
        assert r.items_ingested == 0
        assert r.items_skipped == 0
        assert r.queries_made == 0
        assert r.citations_found == 0
        assert r.errors == []

    def test_custom_values(self):
        r = PerplexitySearchResult(
            items_ingested=5, items_skipped=2, queries_made=1, citations_found=12
        )
        assert r.items_ingested == 5
        assert r.items_skipped == 2

    def test_errors_list_independence(self):
        """Each instance should have its own errors list."""
        r1 = PerplexitySearchResult()
        r2 = PerplexitySearchResult()
        r1.errors.append("err")
        assert r2.errors == []


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


class TestGenerateSourceId:
    def test_deterministic(self):
        cites = ["https://b.com", "https://a.com"]
        assert _generate_source_id(cites) == _generate_source_id(cites)

    def test_sorted_order(self):
        """Order of input shouldn't matter — citations are sorted."""
        assert _generate_source_id(["https://b.com", "https://a.com"]) == _generate_source_id(
            ["https://a.com", "https://b.com"]
        )

    def test_prefix(self):
        result = _generate_source_id(["https://a.com"])
        assert result.startswith("perplexity:")
        assert len(result) == len("perplexity:") + 16  # 16-char hex hash

    def test_empty_citations(self):
        result = _generate_source_id([])
        assert result.startswith("perplexity:")


class TestFormatCitationsMarkdown:
    def test_formats_as_numbered_links(self):
        citations = ["https://a.com", "https://b.com"]
        md = _format_citations_markdown(citations)
        assert "## Sources" in md
        assert "1. [https://a.com](https://a.com)" in md
        assert "2. [https://b.com](https://b.com)" in md

    def test_empty_citations(self):
        assert _format_citations_markdown([]) == ""


class TestBuildMarkdownContent:
    def test_appends_citations(self):
        content = _build_markdown_content("Main content here.", ["https://a.com"])
        assert content.startswith("Main content here.")
        assert "## Sources" in content
        assert "[https://a.com]" in content

    def test_no_citations(self):
        content = _build_markdown_content("Just content.", [])
        assert content == "Just content."

    def test_strips_whitespace(self):
        content = _build_markdown_content("  padded  ", [])
        assert content == "padded"


class TestBuildMetadata:
    def test_includes_all_fields(self):
        response = PerplexityResponse(
            content="test",
            citations=["https://a.com"],
            related_questions=["Q?"],
            model="sonar",
            usage={"total_tokens": 100},
        )
        meta = _build_metadata("AI news", response, "medium", "week", ["example.com"])

        assert meta["search_prompt"] == "AI news"
        assert meta["model_used"] == "sonar"
        assert meta["search_context_size"] == "medium"
        assert meta["search_recency_filter"] == "week"
        assert meta["domain_filter"] == ["example.com"]
        assert meta["citation_count"] == 1
        assert meta["citations"] == ["https://a.com"]
        assert meta["related_questions"] == ["Q?"]
        assert meta["tokens_used"] == {"total_tokens": 100}


# ---------------------------------------------------------------------------
# PerplexityClient
# ---------------------------------------------------------------------------


class TestPerplexityClient:
    @patch("src.ingestion.perplexity_search.settings")
    def test_init_uses_settings_defaults(self, mock_settings):
        mock_settings.perplexity_api_key = "sk-test"
        mock_settings.perplexity_model = "sonar"

        client = PerplexityClient()
        assert client.api_key == "sk-test"
        assert client.model == "sonar"

    @patch("src.ingestion.perplexity_search.settings")
    def test_init_explicit_overrides(self, mock_settings):
        mock_settings.perplexity_api_key = "default"
        mock_settings.perplexity_model = "default"

        client = PerplexityClient(api_key="override-key", model="sonar-pro")
        assert client.api_key == "override-key"
        assert client.model == "sonar-pro"

    @patch("src.ingestion.perplexity_search.settings")
    def test_init_raises_without_api_key(self, mock_settings):
        mock_settings.perplexity_api_key = None

        with pytest.raises(ValueError, match="PERPLEXITY_API_KEY is required"):
            PerplexityClient()

    @patch("src.ingestion.perplexity_search.settings")
    def test_lazy_client_creation(self, mock_settings):
        mock_settings.perplexity_api_key = "sk-test"
        mock_settings.perplexity_model = "sonar"

        client = PerplexityClient()
        assert client._client is None  # Not created yet

    @patch("src.ingestion.perplexity_search.settings")
    @patch("openai.OpenAI")
    def test_search_creates_openai_client(self, mock_openai_cls, mock_settings):
        mock_settings.perplexity_api_key = "sk-test"
        mock_settings.perplexity_model = "sonar"
        mock_settings.perplexity_search_recency_filter = "week"
        mock_settings.perplexity_search_context_size = "medium"
        mock_settings.perplexity_domain_filter = []

        # Build mock response chain
        mock_choice = MagicMock()
        mock_choice.message.content = "AI content"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.citations = ["https://a.com"]
        mock_response.related_questions = []
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        mock_response.model = "sonar"

        mock_openai = MagicMock()
        mock_openai.chat.completions.create.return_value = mock_response
        mock_openai_cls.return_value = mock_openai

        client = PerplexityClient()
        result = client.search(prompt="AI news")

        mock_openai_cls.assert_called_once_with(
            api_key="sk-test", base_url="https://api.perplexity.ai"
        )
        assert result.content == "AI content"
        assert result.citations == ["https://a.com"]
        assert result.model == "sonar"

    @patch("src.ingestion.perplexity_search.settings")
    @patch("openai.OpenAI")
    def test_search_passes_extra_body(self, mock_openai_cls, mock_settings):
        mock_settings.perplexity_api_key = "sk-test"
        mock_settings.perplexity_model = "sonar"
        mock_settings.perplexity_search_recency_filter = "week"
        mock_settings.perplexity_search_context_size = "medium"
        mock_settings.perplexity_domain_filter = []

        mock_choice = MagicMock()
        mock_choice.message.content = "Content"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.citations = []
        mock_response.related_questions = []
        mock_response.usage.prompt_tokens = 5
        mock_response.usage.completion_tokens = 10
        mock_response.model = "sonar"

        mock_openai = MagicMock()
        mock_openai.chat.completions.create.return_value = mock_response
        mock_openai_cls.return_value = mock_openai

        client = PerplexityClient()
        client.search(prompt="test", recency_filter="day", search_context_size="high")

        call_kwargs = mock_openai.chat.completions.create.call_args
        assert call_kwargs.kwargs["extra_body"]["search_recency_filter"] == "day"
        assert call_kwargs.kwargs["extra_body"]["search_context_size"] == "high"

    @patch("src.ingestion.perplexity_search.settings")
    @patch("openai.OpenAI")
    def test_search_includes_domain_filter(self, mock_openai_cls, mock_settings):
        mock_settings.perplexity_api_key = "sk-test"
        mock_settings.perplexity_model = "sonar"
        mock_settings.perplexity_search_recency_filter = "week"
        mock_settings.perplexity_search_context_size = "medium"
        mock_settings.perplexity_domain_filter = []

        mock_choice = MagicMock()
        mock_choice.message.content = "Content"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.citations = []
        mock_response.related_questions = []
        mock_response.usage.prompt_tokens = 5
        mock_response.usage.completion_tokens = 10
        mock_response.model = "sonar"

        mock_openai = MagicMock()
        mock_openai.chat.completions.create.return_value = mock_response
        mock_openai_cls.return_value = mock_openai

        client = PerplexityClient()
        client.search(prompt="test", domain_filter=["arxiv.org", "github.com"])

        call_kwargs = mock_openai.chat.completions.create.call_args
        assert call_kwargs.kwargs["extra_body"]["search_domain_filter"] == [
            "arxiv.org",
            "github.com",
        ]

    @patch("src.ingestion.perplexity_search.settings")
    def test_close_resets_client(self, mock_settings):
        mock_settings.perplexity_api_key = "sk-test"
        mock_settings.perplexity_model = "sonar"

        client = PerplexityClient()
        client._client = MagicMock()  # Simulate initialized client
        client.close()
        assert client._client is None

    @patch("src.ingestion.perplexity_search.settings")
    @patch("openai.OpenAI")
    def test_search_with_system_prompt(self, mock_openai_cls, mock_settings):
        mock_settings.perplexity_api_key = "sk-test"
        mock_settings.perplexity_model = "sonar"
        mock_settings.perplexity_search_recency_filter = "week"
        mock_settings.perplexity_search_context_size = "medium"
        mock_settings.perplexity_domain_filter = []

        mock_choice = MagicMock()
        mock_choice.message.content = "Content"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.citations = []
        mock_response.related_questions = []
        mock_response.usage.prompt_tokens = 5
        mock_response.usage.completion_tokens = 10
        mock_response.model = "sonar"

        mock_openai = MagicMock()
        mock_openai.chat.completions.create.return_value = mock_response
        mock_openai_cls.return_value = mock_openai

        client = PerplexityClient()
        client.search(prompt="test", system_prompt="Be a helpful AI researcher")

        call_kwargs = mock_openai.chat.completions.create.call_args
        messages = call_kwargs.kwargs["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "Be a helpful AI researcher"
        assert messages[1]["role"] == "user"

    @patch("src.ingestion.perplexity_search.settings")
    @patch("openai.OpenAI")
    def test_search_api_error_propagates(self, mock_openai_cls, mock_settings):
        mock_settings.perplexity_api_key = "sk-test"
        mock_settings.perplexity_model = "sonar"
        mock_settings.perplexity_search_recency_filter = "week"
        mock_settings.perplexity_search_context_size = "medium"
        mock_settings.perplexity_domain_filter = []

        mock_openai = MagicMock()
        mock_openai.chat.completions.create.side_effect = RuntimeError("API down")
        mock_openai_cls.return_value = mock_openai

        client = PerplexityClient()
        with pytest.raises(RuntimeError, match="API down"):
            client.search(prompt="test")


# ---------------------------------------------------------------------------
# PerplexityContentIngestionService
# ---------------------------------------------------------------------------


class TestPerplexityContentIngestionService:
    @patch("src.ingestion.perplexity_search.PerplexityClient")
    def test_init_creates_client(self, mock_client_cls):
        service = PerplexityContentIngestionService(api_key="sk-test", model="sonar-pro")
        mock_client_cls.assert_called_once_with(api_key="sk-test", model="sonar-pro")

    @patch("src.ingestion.perplexity_search.get_db")
    @patch("src.ingestion.perplexity_search.PerplexityClient")
    def test_ingest_content_success(self, mock_client_cls, mock_get_db):
        """Full happy path: search -> dedup -> store."""
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        # No duplicates
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.execute.return_value.first.return_value = None

        mock_response = PerplexityResponse(
            content="AI breakthroughs this week include...",
            citations=["https://a.com", "https://b.com"],
            model="sonar",
            usage={"prompt_tokens": 10, "completion_tokens": 50, "total_tokens": 60},
        )

        mock_client = MagicMock()
        mock_client.search.return_value = mock_response
        mock_client.model = "sonar"
        mock_client_cls.return_value = mock_client

        service = PerplexityContentIngestionService()

        with patch.object(service, "_get_search_prompt", return_value="AI news"):
            result = service.ingest_content()

        assert result.items_ingested == 1
        assert result.queries_made == 1
        assert result.citations_found == 2
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @patch("src.ingestion.perplexity_search.get_db")
    @patch("src.ingestion.perplexity_search.PerplexityClient")
    def test_ingest_content_skips_duplicate(self, mock_client_cls, mock_get_db):
        """Duplicate source_id should skip ingestion."""
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        # source_id duplicate found
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock()

        mock_response = PerplexityResponse(
            content="Duplicate content.",
            citations=["https://a.com"],
            model="sonar",
        )

        mock_client = MagicMock()
        mock_client.search.return_value = mock_response
        mock_client.model = "sonar"
        mock_client_cls.return_value = mock_client

        service = PerplexityContentIngestionService()

        with patch.object(service, "_get_search_prompt", return_value="test"):
            result = service.ingest_content()

        assert result.items_ingested == 0
        assert result.items_skipped == 1
        mock_db.add.assert_not_called()

    @patch("src.ingestion.perplexity_search.PerplexityClient")
    def test_ingest_content_search_failure(self, mock_client_cls):
        """API failure during search should return result with error."""
        mock_client = MagicMock()
        mock_client.search.side_effect = RuntimeError("API rate limited")
        mock_client.model = "sonar"
        mock_client_cls.return_value = mock_client

        service = PerplexityContentIngestionService()

        with patch.object(service, "_get_search_prompt", return_value="test"):
            result = service.ingest_content()

        assert result.items_ingested == 0
        assert result.queries_made == 0
        assert len(result.errors) == 1
        assert "Search failed" in result.errors[0]

    @patch("src.ingestion.perplexity_search.PerplexityClient")
    def test_ingest_content_empty_response(self, mock_client_cls):
        """Empty content from API should return without storing."""
        mock_response = PerplexityResponse(content="", citations=[], model="sonar")

        mock_client = MagicMock()
        mock_client.search.return_value = mock_response
        mock_client.model = "sonar"
        mock_client_cls.return_value = mock_client

        service = PerplexityContentIngestionService()

        with patch.object(service, "_get_search_prompt", return_value="test"):
            result = service.ingest_content()

        assert result.items_ingested == 0
        assert result.queries_made == 1
        assert result.errors == []

    @patch("src.ingestion.perplexity_search.get_db")
    @patch("src.ingestion.perplexity_search.PerplexityClient")
    def test_ingest_content_with_custom_prompt(self, mock_client_cls, mock_get_db):
        """Custom prompt should bypass _get_search_prompt."""
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.execute.return_value.first.return_value = None

        mock_response = PerplexityResponse(
            content="Custom results.", citations=["https://c.com"], model="sonar"
        )

        mock_client = MagicMock()
        mock_client.search.return_value = mock_response
        mock_client.model = "sonar"
        mock_client_cls.return_value = mock_client

        service = PerplexityContentIngestionService()

        result = service.ingest_content(prompt="Find latest LLM benchmarks")

        mock_client.search.assert_called_once()
        call_kwargs = mock_client.search.call_args
        assert call_kwargs.kwargs["prompt"] == "Find latest LLM benchmarks"
        assert result.items_ingested == 1

    @patch("src.ingestion.perplexity_search.get_db")
    @patch("src.ingestion.perplexity_search.PerplexityClient")
    def test_ingest_content_force_reprocess_bypasses_dedup(self, mock_client_cls, mock_get_db):
        """force_reprocess=True should skip dedup check."""
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        mock_response = PerplexityResponse(
            content="Force reprocessed.", citations=["https://a.com"], model="sonar"
        )

        mock_client = MagicMock()
        mock_client.search.return_value = mock_response
        mock_client.model = "sonar"
        mock_client_cls.return_value = mock_client

        service = PerplexityContentIngestionService()

        with patch.object(service, "_get_search_prompt", return_value="test"):
            result = service.ingest_content(force_reprocess=True)

        assert result.items_ingested == 1
        # _is_duplicate should NOT have been called
        mock_db.query.return_value.filter.return_value.first.assert_not_called()

    @patch("src.ingestion.perplexity_search.PerplexityClient")
    def test_close_delegates_to_client(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        service = PerplexityContentIngestionService()
        service.close()

        mock_client.close.assert_called_once()
