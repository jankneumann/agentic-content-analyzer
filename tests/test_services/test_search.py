"""Tests for HybridSearchService — RRF fusion, aggregation, and highlighting."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.search import SearchQuery, SearchResponse, SearchType
from src.services.search import (
    HybridSearchService,
    _extract_query_terms,
    _generate_highlight,
)

# --- Unit tests for helper functions ---


class TestExtractQueryTerms:
    def test_basic_terms(self):
        terms = _extract_query_terms("machine learning models")
        assert terms == ["machine", "learning", "models"]

    def test_deduplication(self):
        terms = _extract_query_terms("the the quick quick fox")
        assert terms == ["the", "quick", "fox"]

    def test_skips_single_chars(self):
        terms = _extract_query_terms("a quick fox")
        # "a" is single char, skipped
        assert "a" not in terms
        assert "quick" in terms

    def test_empty_query(self):
        assert _extract_query_terms("") == []

    def test_special_chars_stripped(self):
        terms = _extract_query_terms("what's AI/ML?")
        assert "what" in terms
        assert "AI" not in terms  # lowercase
        assert "ai" in terms or "ml" in terms


class TestGenerateHighlight:
    def test_marks_matching_terms(self):
        text = "Machine learning is a subset of artificial intelligence"
        result = _generate_highlight(text, ["machine", "intelligence"], SearchType.HYBRID)
        assert "<mark>" in result
        assert "Machine" in result or "machine" in result

    def test_html_escapes_content(self):
        text = "Use <script>alert('xss')</script> for testing"
        result = _generate_highlight(text, ["testing"], SearchType.HYBRID)
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_vector_only_no_match_returns_plain(self):
        text = "This document discusses quantum computing concepts"
        result = _generate_highlight(text, ["unrelated"], SearchType.VECTOR)
        assert "<mark>" not in result
        assert len(result) <= 200

    def test_empty_terms_returns_snippet(self):
        text = "Some document text here"
        result = _generate_highlight(text, [], SearchType.HYBRID)
        assert result == text[:200]


# --- RRF calculation tests ---


class TestRRFCalculation:
    def setup_method(self):
        """Create a service with mock dependencies."""
        self.mock_session = MagicMock()
        self.mock_bm25 = MagicMock()
        self.mock_bm25.name = "test_bm25"
        self.mock_bm25.search = MagicMock(return_value=[])

        self.mock_embedder = MagicMock()
        self.mock_embedder.name = "test_embedder"
        self.mock_embedder.embed = AsyncMock(return_value=[0.1] * 384)
        self.mock_embedder.dimensions = 384

        self.service = HybridSearchService(
            session=self.mock_session,
            bm25_strategy=self.mock_bm25,
            embedding_provider=self.mock_embedder,
            rerank_provider=None,
        )

    def test_rrf_single_method(self):
        """Chunks from only one method should still get RRF scores."""
        bm25 = {1: 10.0, 2: 8.0, 3: 5.0}
        vector: dict[int, float] = {}
        rrf = self.service._calculate_rrf(bm25, vector, bm25_weight=0.5, vector_weight=0.5, k=60)

        assert 1 in rrf
        assert 2 in rrf
        assert 3 in rrf
        # Rank 1 should have highest score
        assert rrf[1] > rrf[2] > rrf[3]

    def test_rrf_both_methods(self):
        """Chunks appearing in both methods should get boosted."""
        bm25 = {1: 10.0, 2: 8.0}
        vector = {1: 0.95, 3: 0.90}

        rrf = self.service._calculate_rrf(bm25, vector, bm25_weight=0.5, vector_weight=0.5, k=60)

        # Chunk 1 appears in both, should have highest score
        assert rrf[1] > rrf[2]
        assert rrf[1] > rrf[3]

    def test_rrf_weight_bias(self):
        """Higher weight should give that method more influence."""
        bm25 = {1: 10.0}  # Rank 1 in BM25
        vector = {2: 0.99}  # Rank 1 in vector

        rrf_bm25_heavy = self.service._calculate_rrf(
            bm25,
            vector,
            bm25_weight=0.9,
            vector_weight=0.1,
            k=60,
        )
        rrf_vector_heavy = self.service._calculate_rrf(
            bm25,
            vector,
            bm25_weight=0.1,
            vector_weight=0.9,
            k=60,
        )

        # With BM25-heavy weights, chunk 1 (BM25 top) should score higher
        assert rrf_bm25_heavy[1] > rrf_bm25_heavy[2]
        # With vector-heavy weights, chunk 2 (vector top) should score higher
        assert rrf_vector_heavy[2] > rrf_vector_heavy[1]

    def test_rrf_empty_inputs(self):
        """Empty inputs should return empty."""
        rrf = self.service._calculate_rrf({}, {}, bm25_weight=0.5, vector_weight=0.5, k=60)
        assert rrf == {}


# --- Search method tests ---


class TestHybridSearchService:
    def setup_method(self):
        self.mock_session = MagicMock()
        self.mock_bm25 = MagicMock()
        self.mock_bm25.name = "test_bm25"
        self.mock_bm25.search = MagicMock(return_value=[])

        self.mock_embedder = MagicMock()
        self.mock_embedder.name = "test_embedder"
        self.mock_embedder.embed = AsyncMock(return_value=[0.1] * 384)
        self.mock_embedder.dimensions = 384

        self.service = HybridSearchService(
            session=self.mock_session,
            bm25_strategy=self.mock_bm25,
            embedding_provider=self.mock_embedder,
            rerank_provider=None,
        )

    @pytest.mark.asyncio
    @patch("src.services.search.get_settings")
    async def test_empty_results(self, mock_settings):
        """Query with no matches should return empty response."""
        mock_settings.return_value = MagicMock(
            search_bm25_weight=0.5,
            search_vector_weight=0.5,
            search_rrf_k=60,
            search_max_limit=100,
            search_rerank_enabled=False,
            embedding_model="test-model",
            search_rerank_model=None,
            database_provider="local",
        )

        # Mock vector search to also return empty
        self.mock_session.execute.return_value = []

        query = SearchQuery(query="nonexistent topic", limit=10)
        result = await self.service.search(query)

        assert isinstance(result, SearchResponse)
        assert result.total == 0
        assert result.results == []
        assert result.meta.bm25_strategy == "test_bm25"

    @pytest.mark.asyncio
    @patch("src.services.search.get_settings")
    async def test_bm25_only_search(self, mock_settings):
        """BM25-only search should not call embedding provider."""
        mock_settings.return_value = MagicMock(
            search_bm25_weight=0.5,
            search_vector_weight=0.5,
            search_rrf_k=60,
            search_max_limit=100,
            search_rerank_enabled=False,
            embedding_model="test-model",
            search_rerank_model=None,
            database_provider="local",
        )

        self.mock_bm25.search.return_value = []

        query = SearchQuery(query="test", type=SearchType.BM25, limit=10)
        await self.service.search(query)

        # Embedder should NOT be called for BM25-only
        self.mock_embedder.embed.assert_not_called()


# --- Indexing service tests ---


class TestIndexContent:
    @patch("src.services.indexing.get_settings")
    def test_skips_when_disabled(self, mock_settings):
        """index_content should be a no-op when search indexing is disabled."""
        mock_settings.return_value = MagicMock(enable_search_indexing=False)

        from src.services.indexing import index_content

        mock_content = MagicMock(id=1, markdown_content="test")
        mock_db = MagicMock()

        index_content(mock_content, mock_db)

        # Should not try to chunk
        mock_db.add.assert_not_called()

    @patch("src.services.indexing.get_settings")
    def test_skips_empty_content(self, mock_settings):
        """index_content should skip content with no markdown."""
        mock_settings.return_value = MagicMock(enable_search_indexing=True)

        from src.services.indexing import index_content

        mock_content = MagicMock(id=1, markdown_content=None)
        mock_db = MagicMock()

        index_content(mock_content, mock_db)
        mock_db.add.assert_not_called()

    @patch("src.services.indexing._index_content_impl")
    @patch("src.services.indexing.get_settings")
    def test_catches_exceptions(self, mock_settings, mock_impl):
        """index_content should never raise, even on errors."""
        mock_settings.return_value = MagicMock(enable_search_indexing=True)
        mock_impl.side_effect = RuntimeError("chunking exploded")

        from src.services.indexing import index_content

        mock_content = MagicMock(id=1, markdown_content="test")
        mock_db = MagicMock()

        # Should NOT raise
        index_content(mock_content, mock_db)
