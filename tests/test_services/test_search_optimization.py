from unittest.mock import MagicMock

from src.services.search import HybridSearchService, SearchQuery, SearchType


class TestSearchOptimization:
    def setup_method(self):
        self.mock_session = MagicMock()
        self.mock_bm25 = MagicMock()
        self.mock_embedder = MagicMock()
        self.service = HybridSearchService(
            session=self.mock_session,
            bm25_strategy=self.mock_bm25,
            embedding_provider=self.mock_embedder,
        )

    def test_aggregate_to_documents_uses_substr(self):
        """Verify that _aggregate_to_documents uses substr for chunk_text."""
        final_scores = {1: 0.9}
        bm25_scores = {1: 0.8}
        vector_scores = {1: 0.7}
        rrf_scores = {1: 0.9}
        rerank_scores = {}
        query = SearchQuery(query="test", type=SearchType.HYBRID)

        # Mock DB result
        mock_row = MagicMock()
        mock_row.chunk_id = 1
        mock_row.content_id = 101
        mock_row.chunk_text = "This is a test chunk text that is long enough."
        mock_row.section_path = "Section 1"
        mock_row.heading_text = "Heading"
        mock_row.chunk_type = "paragraph"
        mock_row.deep_link_url = "http://example.com"
        mock_row.title = "Test Doc"
        mock_row.source_type = "manual"
        mock_row.publication = "Test Pub"
        mock_row.published_date = None

        self.mock_session.execute.return_value = [mock_row]

        # Call the method
        results = self.service._aggregate_to_documents(
            final_scores, bm25_scores, vector_scores, rrf_scores, rerank_scores, query
        )

        # Check the SQL statement
        args, _ = self.mock_session.execute.call_args
        sql_stmt = args[0]
        assert "substr(dc.chunk_text, 1, 500)" in str(sql_stmt) or "substring(dc.chunk_text, 1, 500)" in str(sql_stmt)

        # Verify result structure
        assert len(results) == 1
        assert results[0].id == 101
        assert results[0].matching_chunks[0].chunk_id == 1
