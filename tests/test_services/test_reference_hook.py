"""Tests for the post-ingestion reference hook (src/services/reference_hook.py)."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

from src.services.reference_hook import (
    _find_chunk_for_ref,
    on_content_ingested,
    reanchor_references,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_content(content_id: int = 1, title: str = "Test Content") -> MagicMock:
    content = MagicMock()
    content.id = content_id
    content.title = title
    content.markdown_content = "Some text with arXiv:2401.12345 reference"
    content.source_url = "https://example.com/article"
    content.metadata_json = {"arxiv_id": "2401.12345"}
    return content


def _make_settings(
    *,
    extraction_enabled: bool = True,
    min_confidence: float = 0.5,
) -> MagicMock:
    settings = MagicMock()
    settings.reference_extraction_enabled = extraction_enabled
    settings.reference_min_confidence = min_confidence
    return settings


def _make_extracted_ref(
    *,
    external_id: str = "2401.12345",
    external_id_type: str = "arxiv",
    confidence: float = 1.0,
) -> MagicMock:
    ref = MagicMock()
    ref.external_id = external_id
    ref.external_id_type = external_id_type
    ref.confidence = confidence
    ref.context_snippet = "surrounding text with arXiv:2401.12345 reference"
    ref.reference_type = "cites"
    return ref


# ---------------------------------------------------------------------------
# on_content_ingested
# ---------------------------------------------------------------------------


class TestOnContentIngested:
    """Tests for the main hook entry point."""

    @patch("src.services.reference_hook._run_reverse_resolution")
    @patch("src.services.reference_hook._enqueue_resolution")
    @patch("src.services.reference_extractor.ReferenceExtractor")
    @patch("src.config.settings.get_settings")
    def test_happy_path_extracts_and_stores(
        self, mock_get_settings, mock_extractor_cls, mock_enqueue, mock_reverse
    ):
        """Happy path: extracts refs, stores them, enqueues resolution."""
        settings = _make_settings()
        mock_get_settings.return_value = settings

        ref = _make_extracted_ref()
        extractor = MagicMock()
        extractor.extract_from_content.return_value = [ref]
        extractor.store_references.return_value = 1
        mock_extractor_cls.return_value = extractor

        content = _make_content()
        db = MagicMock()

        on_content_ingested(content, db)

        extractor.extract_from_content.assert_called_once_with(content, db)
        extractor.store_references.assert_called_once_with(content.id, [ref], db)
        mock_enqueue.assert_called_once_with(content.id)
        mock_reverse.assert_called_once_with(content, db)

    @patch("src.services.reference_extractor.ReferenceExtractor")
    @patch("src.config.settings.get_settings")
    def test_disabled_skips_extraction(self, mock_get_settings, mock_extractor_cls):
        """When reference_extraction_enabled is False, no extraction occurs."""
        settings = _make_settings(extraction_enabled=False)
        mock_get_settings.return_value = settings

        content = _make_content()
        db = MagicMock()

        on_content_ingested(content, db)

        mock_extractor_cls.assert_not_called()

    @patch("src.config.settings.get_settings")
    def test_error_logged_not_raised(self, mock_get_settings, caplog):
        """Errors are logged but never propagate."""
        mock_get_settings.side_effect = RuntimeError("kaboom")

        content = _make_content()
        db = MagicMock()

        # Must not raise
        with caplog.at_level(logging.WARNING):
            on_content_ingested(content, db)

        assert "Reference extraction failed" in caplog.text

    @patch("src.services.reference_hook._run_reverse_resolution")
    @patch("src.services.reference_hook._enqueue_resolution")
    @patch("src.services.reference_extractor.ReferenceExtractor")
    @patch("src.config.settings.get_settings")
    def test_filters_by_confidence(
        self, mock_get_settings, mock_extractor_cls, mock_enqueue, mock_reverse
    ):
        """Low-confidence refs below the threshold are filtered out."""
        settings = _make_settings(min_confidence=0.8)
        mock_get_settings.return_value = settings

        high_conf = _make_extracted_ref(confidence=0.9)
        low_conf = _make_extracted_ref(
            external_id="10.1234/test", external_id_type="doi", confidence=0.3
        )
        extractor = MagicMock()
        extractor.extract_from_content.return_value = [high_conf, low_conf]
        extractor.store_references.return_value = 1
        mock_extractor_cls.return_value = extractor

        content = _make_content()
        db = MagicMock()

        on_content_ingested(content, db)

        # store_references should receive only the high-confidence ref
        extractor.store_references.assert_called_once_with(content.id, [high_conf], db)

    @patch("src.services.reference_hook._run_reverse_resolution")
    @patch("src.services.reference_hook._enqueue_resolution")
    @patch("src.services.reference_extractor.ReferenceExtractor")
    @patch("src.config.settings.get_settings")
    def test_all_refs_filtered_returns_early(
        self, mock_get_settings, mock_extractor_cls, mock_enqueue, mock_reverse
    ):
        """When all refs are below confidence threshold, store is not called."""
        settings = _make_settings(min_confidence=0.9)
        mock_get_settings.return_value = settings

        low_conf = _make_extracted_ref(confidence=0.3)
        extractor = MagicMock()
        extractor.extract_from_content.return_value = [low_conf]
        mock_extractor_cls.return_value = extractor

        content = _make_content()
        db = MagicMock()

        on_content_ingested(content, db)

        extractor.store_references.assert_not_called()
        mock_enqueue.assert_not_called()

    @patch("src.services.reference_hook._run_reverse_resolution")
    @patch("src.services.reference_hook._enqueue_resolution")
    @patch("src.services.reference_extractor.ReferenceExtractor")
    @patch("src.config.settings.get_settings")
    def test_no_refs_returns_early(
        self, mock_get_settings, mock_extractor_cls, mock_enqueue, mock_reverse
    ):
        """When no refs are extracted, store/enqueue/reverse are skipped."""
        settings = _make_settings()
        mock_get_settings.return_value = settings

        extractor = MagicMock()
        extractor.extract_from_content.return_value = []
        mock_extractor_cls.return_value = extractor

        content = _make_content()
        db = MagicMock()

        on_content_ingested(content, db)

        extractor.store_references.assert_not_called()
        mock_enqueue.assert_not_called()
        mock_reverse.assert_not_called()


# ---------------------------------------------------------------------------
# reanchor_references
# ---------------------------------------------------------------------------


class TestReanchorReferences:
    """Tests for the chunk re-anchoring hook."""

    @patch("src.models.chunk.DocumentChunk")
    @patch("src.models.content_reference.ContentReference")
    def test_reanchors_refs_to_chunks(self, mock_ref_model, mock_chunk_model):
        """Re-anchors unanchored refs when matching chunks exist."""
        db = MagicMock()

        # Create a ref with context_snippet but no source_chunk_id
        ref = MagicMock()
        ref.source_chunk_id = None
        ref.context_snippet = "xxxx surrounding text with arXiv:2401.12345 reference yyyy"
        ref.external_id = "2401.12345"

        # Make the query chain return our ref
        ref_query = MagicMock()
        ref_query.filter.return_value = ref_query
        ref_query.all.return_value = [ref]

        # Create a chunk that contains the ref's text
        chunk = MagicMock()
        chunk.id = 42
        chunk.text = "This is surrounding text with arXiv:2401.12345 reference in chunk"

        chunk_query = MagicMock()
        chunk_query.filter.return_value = chunk_query
        chunk_query.order_by.return_value = chunk_query
        chunk_query.all.return_value = [chunk]

        # Wire up db.query to return different chains
        def query_side_effect(model):
            if model is mock_ref_model:
                return ref_query
            return chunk_query

        db.query.side_effect = query_side_effect

        result = reanchor_references(content_id=1, db=db)

        assert result == 1
        assert ref.source_chunk_id == 42
        db.commit.assert_called_once()

    @patch("src.models.chunk.DocumentChunk")
    @patch("src.models.content_reference.ContentReference")
    def test_no_unanchored_refs_returns_zero(self, mock_ref_model, mock_chunk_model):
        """Returns 0 when there are no unanchored refs."""
        db = MagicMock()

        ref_query = MagicMock()
        ref_query.filter.return_value = ref_query
        ref_query.all.return_value = []

        db.query.return_value = ref_query

        result = reanchor_references(content_id=1, db=db)

        assert result == 0
        db.commit.assert_not_called()

    def test_error_returns_zero(self, caplog):
        """Errors are caught and 0 is returned."""
        db = MagicMock()
        db.query.side_effect = RuntimeError("db error")

        with caplog.at_level(logging.WARNING):
            result = reanchor_references(content_id=1, db=db)

        assert result == 0
        assert "re-anchoring failed" in caplog.text


# ---------------------------------------------------------------------------
# _find_chunk_for_ref
# ---------------------------------------------------------------------------


class TestFindChunkForRef:
    """Tests for the chunk matching helper."""

    def test_matches_by_snippet(self):
        """Finds chunk containing the middle of the context snippet."""
        ref = MagicMock()
        ref.context_snippet = "prefix___this is the matching text___suffix"
        ref.external_id = None

        chunk = MagicMock()
        chunk.text = "The full chunk contains this is the matching text here."

        result = _find_chunk_for_ref(ref, [chunk])
        assert result is chunk

    def test_matches_by_external_id(self):
        """Falls back to external_id literal match."""
        ref = MagicMock()
        ref.context_snippet = None
        ref.external_id = "2401.12345"

        chunk = MagicMock()
        chunk.text = "References arXiv:2401.12345 in the text"

        result = _find_chunk_for_ref(ref, [chunk])
        assert result is chunk

    def test_no_match_returns_none(self):
        """Returns None when no chunk matches."""
        ref = MagicMock()
        ref.context_snippet = "something completely different and long enough to slice"
        ref.external_id = "9999.99999"

        chunk = MagicMock()
        chunk.text = "Unrelated content about cats"

        result = _find_chunk_for_ref(ref, [chunk])
        assert result is None

    def test_empty_chunks_returns_none(self):
        """Returns None when chunks list is empty."""
        ref = MagicMock()
        ref.context_snippet = "some snippet that is long enough for matching"
        ref.external_id = "2401.12345"

        result = _find_chunk_for_ref(ref, [])
        assert result is None
