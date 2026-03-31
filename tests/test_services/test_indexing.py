"""Tests for indexing service — tree index construction and summarization."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.chunk import ChunkType, DocumentChunk
from src.services.indexing import _insert_tree_chunks, build_tree_index


class TestInsertTreeChunks:
    def test_resolves_parent_chunk_ids(self):
        """Tree chunks with _parent_index get correct parent_chunk_id after insert."""
        db = MagicMock()
        id_counter = iter(range(100, 200))

        def mock_flush():
            for chunk in [c for c in chunks if c.id is None]:
                chunk.id = next(id_counter)

        db.flush = mock_flush

        # Create tree: root → child
        root = DocumentChunk()
        root.chunk_text = "Root"
        root.tree_depth = 0
        root.is_summary = True
        root._parent_index = None
        root.id = None

        child = DocumentChunk()
        child.chunk_text = "Child"
        child.tree_depth = 1
        child.is_summary = False
        child._parent_index = 0  # References root's position
        child.id = None

        chunks = [root, child]
        _insert_tree_chunks(chunks, db)

        assert root.id is not None
        assert child.parent_chunk_id == root.id


class TestBuildTreeIndex:
    @patch("src.services.indexing.get_settings")
    @patch("src.services.indexing._run_async")
    def test_skips_when_tree_exists_and_no_force(self, mock_async, mock_settings):
        mock_settings.return_value = MagicMock(
            tree_index_min_tokens=100,
            tree_index_min_heading_depth=2,
            tree_summarization_max_concurrent=10,
            tree_max_depth=10,
        )

        db = MagicMock()
        # Simulate existing tree chunks
        db.query.return_value.filter.return_value.count.return_value = 5

        result = build_tree_index(42, db, force=False)
        assert result == 0

    @patch("src.services.indexing.get_settings")
    @patch("src.services.indexing._run_async")
    def test_force_deletes_existing_tree_chunks(self, mock_async, mock_settings):
        mock_settings.return_value = MagicMock(
            tree_index_min_tokens=10,
            tree_index_min_heading_depth=2,
            tree_summarization_max_concurrent=10,
            tree_max_depth=10,
            embedding_model="test-model",
        )

        db = MagicMock()
        # First call: count existing
        db.query.return_value.filter.return_value.count.return_value = 5

        # Second call: get content
        mock_content = MagicMock()
        mock_content.markdown_content = "# Title\n\n## Section A\n\nContent A.\n\n## Section B\n\nContent B."
        db.query.return_value.get.return_value = mock_content

        # Mock async operations (summarization + embedding)
        mock_async.return_value = None

        # Mock embedding module (lazy import inside build_tree_index)
        with patch("src.services.embedding.embed_chunks", new_callable=AsyncMock) as mock_embed:
            with patch("src.services.embedding.get_embedding_provider") as mock_prov:
                mock_prov.return_value = MagicMock(name="test")
                mock_embed.return_value = []

                result = build_tree_index(42, db, force=True)

        # Should have called delete for existing tree chunks
        db.execute.assert_called()

    @patch("src.services.indexing.get_settings")
    def test_returns_zero_for_missing_content(self, mock_settings):
        mock_settings.return_value = MagicMock(
            tree_index_min_tokens=10,
            tree_index_min_heading_depth=2,
        )
        db = MagicMock()
        db.query.return_value.filter.return_value.count.return_value = 0
        db.query.return_value.get.return_value = None  # Content not found

        result = build_tree_index(99, db, force=True)
        assert result == 0
