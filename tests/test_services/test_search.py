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

    @pytest.mark.asyncio
    @patch("src.services.search.get_settings")
    async def test_hybrid_search_aggregation_pagination(self, mock_settings):
        """Test that results are aggregated by content_id and pagination is applied before fetching."""
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

        # Mock BM25 results: chunk 1 (doc 101), chunk 2 (doc 101), chunk 3 (doc 102)
        # Format: (chunk_id, score, content_id)
        self.mock_bm25.search.return_value = [
            (1, 1.0, 101),
            (2, 0.9, 101),
            (3, 0.8, 102),
        ]

        # Mock Vector results: chunk 3 (doc 102), chunk 4 (doc 102)
        # We need to mock _vector_search carefully as it's an async method
        self.service._vector_search = AsyncMock(
            return_value=[
                (3, 0.95, 102),
                (4, 0.90, 102),
            ]
        )

        # Mock _aggregate_to_documents to avoid DB calls and verify arguments
        self.service._aggregate_to_documents = MagicMock(return_value=[])

        # We request limit=1. Doc 102 should have higher score than Doc 101.
        # RRF Logic:
        # Chunk 1 (Doc 101): BM25 Rank 1. Score ~ 0.5/61
        # Chunk 3 (Doc 102): BM25 Rank 3, Vector Rank 1. Score ~ 0.5/63 + 0.5/61.
        # Chunk 3 score > Chunk 1 score.
        # So Doc 102 > Doc 101.
        query = SearchQuery(query="test", limit=1, offset=0)

        # Act
        await self.service.search(query)

        # Assert
        call_args = self.service._aggregate_to_documents.call_args
        assert call_args is not None
        chunks_to_fetch_arg = call_args[0][0]  # first arg is chunks_to_fetch dict

        # We expect chunks 3 and 4 to be fetched (belonging to doc 102)
        assert 3 in chunks_to_fetch_arg
        assert 4 in chunks_to_fetch_arg
        # Chunk 1 and 2 (doc 101) should NOT be fetched because limit=1 and doc 102 is better
        assert 1 not in chunks_to_fetch_arg
        assert 2 not in chunks_to_fetch_arg


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


# --- RRF Multi-source tests ---


class TestRRFMulti:
    def setup_method(self):
        self.mock_session = MagicMock()
        self.mock_bm25 = MagicMock()
        self.mock_bm25.name = "test_bm25"
        self.mock_embedder = MagicMock()
        self.mock_embedder.name = "test_embedder"
        self.service = HybridSearchService(
            session=self.mock_session,
            bm25_strategy=self.mock_bm25,
            embedding_provider=self.mock_embedder,
        )

    def test_three_source_fusion(self):
        """Three score sources should all contribute to RRF."""
        bm25 = {1: 10.0, 2: 5.0}
        vector = {1: 0.9, 3: 0.8}
        tree = {1: 1.0, 4: 0.5}

        rrf = self.service._calculate_rrf_multi(
            [bm25, vector, tree],
            weights=[0.5, 0.5, 0.5],
            k=60,
        )

        # Chunk 1 appears in all 3 sources — highest score
        assert rrf[1] > rrf[2]
        assert rrf[1] > rrf[3]
        assert rrf[1] > rrf[4]
        assert 2 in rrf
        assert 3 in rrf
        assert 4 in rrf

    def test_empty_tree_scores_no_effect(self):
        """Empty tree scores with weight 0 should produce same as 2-source RRF."""
        bm25 = {1: 10.0, 2: 5.0}
        vector = {1: 0.9}

        rrf = self.service._calculate_rrf_multi(
            [bm25, vector, {}],
            weights=[0.5, 0.5, 0.0],
            k=60,
        )

        rrf2 = self.service._calculate_rrf(bm25, vector, 0.5, 0.5, 60)

        # Should produce same results
        assert set(rrf.keys()) == set(rrf2.keys())
        for k in rrf:
            assert abs(rrf[k] - rrf2[k]) < 1e-10


# --- Tree search unit tests ---


class TestTreeSearchHelpers:
    def setup_method(self):
        self.mock_session = MagicMock()
        self.mock_bm25 = MagicMock()
        self.mock_bm25.name = "test_bm25"
        self.mock_embedder = MagicMock()
        self.mock_embedder.name = "test_embedder"
        self.service = HybridSearchService(
            session=self.mock_session,
            bm25_strategy=self.mock_bm25,
            embedding_provider=self.mock_embedder,
        )

    def test_find_tree_indexed_content_empty(self):
        """No content IDs should return empty set."""
        result = self.service._find_tree_indexed_content([])
        assert result == set()

    def test_find_tree_indexed_content(self):
        """Should query for content with tree_depth IS NOT NULL."""
        mock_result = MagicMock()
        mock_result.__iter__ = lambda self: iter(
            [MagicMock(content_id=1), MagicMock(content_id=3)]
        )
        self.mock_session.execute.return_value = mock_result

        result = self.service._find_tree_indexed_content([1, 2, 3])
        assert result == {1, 3}

    def test_load_tree_structure_empty(self):
        """No tree chunks should return empty."""
        mock_result = MagicMock()
        mock_result.__iter__ = lambda self: iter([])
        self.mock_session.execute.return_value = mock_result

        tree_json, id_mapping = self.service._load_tree_structure(42)
        assert tree_json == ""
        assert id_mapping == {}

    def test_load_tree_structure_builds_compact_ids(self):
        """Should assign N001, N002 IDs and use json.dumps."""
        rows = [
            MagicMock(
                id=100, chunk_text="Root summary", heading_text="Document",
                tree_depth=0, parent_chunk_id=None, is_summary=True,
            ),
            MagicMock(
                id=101, chunk_text="Section summary", heading_text="Section A",
                tree_depth=1, parent_chunk_id=100, is_summary=True,
            ),
            MagicMock(
                id=102, chunk_text="Leaf content", heading_text="Sub A.1",
                tree_depth=2, parent_chunk_id=101, is_summary=False,
            ),
        ]
        mock_result = MagicMock()
        mock_result.__iter__ = lambda self: iter(rows)
        self.mock_session.execute.return_value = mock_result

        tree_json, id_mapping = self.service._load_tree_structure(42)

        assert "N001" in tree_json
        assert "N002" in tree_json
        assert id_mapping["N001"] == 100
        assert id_mapping["N002"] == 101

        # Should be valid JSON (json.dumps was used)
        import json
        parsed = json.loads(tree_json)
        assert isinstance(parsed, list)

    def test_get_tree_leaves_empty(self):
        result = self.service._get_tree_leaves([], 42)
        assert result == []

    @pytest.mark.asyncio
    @patch("src.services.search.get_settings")
    async def test_tree_search_handles_invalid_json(self, mock_settings):
        """Invalid JSON from LLM should return empty results."""
        mock_settings.return_value = MagicMock(
            tree_search_timeout_seconds=5,
            tree_search_max_selected_nodes=10,
        )

        # Mock _load_tree_structure
        self.service._load_tree_structure = MagicMock(
            return_value=('{"node_id": "N001"}', {"N001": 100})
        )

        # Mock LLM to return invalid JSON
        with patch("src.services.llm_router.LLMRouter") as mock_router_cls:
            mock_router = MagicMock()
            mock_router.generate = AsyncMock(
                return_value=MagicMock(content="not valid json {{{")
            )
            mock_router_cls.return_value = mock_router

            with patch("src.config.models.get_model_config"):
                results = await self.service._tree_search_single("test query", 42)
                assert results == []

    @pytest.mark.asyncio
    @patch("src.services.search.get_settings")
    async def test_tree_search_caps_node_list(self, mock_settings):
        """node_list exceeding max_selected_nodes should be truncated."""
        mock_settings.return_value = MagicMock(
            tree_search_timeout_seconds=5,
            tree_search_max_selected_nodes=2,  # Low cap
        )

        id_mapping = {f"N{i:03d}": 100 + i for i in range(1, 11)}
        self.service._load_tree_structure = MagicMock(
            return_value=('{"tree": "data"}', id_mapping)
        )

        # Mock LLM to return 5 nodes
        import json
        llm_response = json.dumps({
            "thinking": "test",
            "node_list": ["N001", "N002", "N003", "N004", "N005"],
        })

        with patch("src.services.llm_router.LLMRouter") as mock_router_cls:
            mock_router = MagicMock()
            mock_router.generate = AsyncMock(
                return_value=MagicMock(content=llm_response)
            )
            mock_router_cls.return_value = mock_router

            # Mock leaf fetching
            mock_leaf_result = MagicMock()
            mock_leaf_result.__iter__ = lambda self: iter(
                [MagicMock(id=101), MagicMock(id=102)]
            )
            self.mock_session.execute.return_value = mock_leaf_result

            with patch("src.config.models.get_model_config"):
                results = await self.service._tree_search_single("test", 42)
                # Should only process first 2 nodes (max_selected_nodes=2)
                assert len(results) <= 2

    @pytest.mark.asyncio
    @patch("src.services.search.get_settings")
    async def test_tree_search_skips_invalid_node_ids(self, mock_settings):
        """Node IDs not matching N\\d{3,} pattern should be skipped."""
        mock_settings.return_value = MagicMock(
            tree_search_timeout_seconds=5,
            tree_search_max_selected_nodes=10,
        )

        self.service._load_tree_structure = MagicMock(
            return_value=('{}', {"N001": 100, "N002": 101})
        )

        import json
        llm_response = json.dumps({
            "thinking": "test",
            "node_list": ["N001", "INVALID", "42", "N002"],
        })

        with patch("src.services.llm_router.LLMRouter") as mock_router_cls:
            mock_router = MagicMock()
            mock_router.generate = AsyncMock(
                return_value=MagicMock(content=llm_response)
            )
            mock_router_cls.return_value = mock_router

            mock_leaf_result = MagicMock()
            mock_leaf_result.__iter__ = lambda self: iter(
                [MagicMock(id=100), MagicMock(id=101)]
            )
            self.mock_session.execute.return_value = mock_leaf_result

            with patch("src.config.models.get_model_config"):
                results = await self.service._tree_search_single("test", 42)
                # Only N001 and N002 should be processed (INVALID and 42 skipped)
                assert len(results) <= 2
