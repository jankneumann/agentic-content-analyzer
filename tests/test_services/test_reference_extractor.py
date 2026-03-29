"""Tests for the reference extraction service (src/services/reference_extractor.py)."""

from __future__ import annotations

import re
from unittest.mock import MagicMock, patch

from src.services.reference_extractor import (
    ARXIV_PATTERNS,
    DOI_PATTERNS,
    REFERENCE_PATTERNS,
    S2_URL_PATTERN,
    ExtractedReference,
    ReferenceExtractionResult,
    ReferenceExtractor,
    _build_url,
    _deduplicate_refs,
    classify_url,
    extract_context,
    normalize_id,
)

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------


class TestReferencePatterns:
    """Test the unified REFERENCE_PATTERNS dict and backward-compat aliases."""

    def test_arxiv_colon(self):
        m = REFERENCE_PATTERNS["arxiv"][0].search("arXiv:2401.12345")
        assert m and m.group(1) == "2401.12345"

    def test_arxiv_colon_with_version(self):
        m = REFERENCE_PATTERNS["arxiv"][0].search("arXiv:2401.12345v3")
        assert m and m.group(1) == "2401.12345v3"

    def test_arxiv_colon_case_insensitive(self):
        m = REFERENCE_PATTERNS["arxiv"][0].search("ARXIV:2401.12345")
        assert m and m.group(1) == "2401.12345"

    def test_arxiv_abs_url(self):
        m = REFERENCE_PATTERNS["arxiv"][1].search("https://arxiv.org/abs/2301.54321v2")
        assert m and m.group(1) == "2301.54321v2"

    def test_arxiv_pdf_url(self):
        m = REFERENCE_PATTERNS["arxiv"][2].search("https://arxiv.org/pdf/2305.99999")
        assert m and m.group(1) == "2305.99999"

    def test_doi_url(self):
        m = REFERENCE_PATTERNS["doi"][0].search("https://doi.org/10.1234/conf.2024.123")
        assert m and m.group(1) == "10.1234/conf.2024.123"

    def test_doi_prefix(self):
        m = REFERENCE_PATTERNS["doi"][1].search("DOI: 10.5678/journal.2024.456")
        assert m and m.group(1) == "10.5678/journal.2024.456"

    def test_doi_prefix_case_insensitive(self):
        m = REFERENCE_PATTERNS["doi"][1].search("doi: 10.5678/journal.2024.456")
        assert m and m.group(1) == "10.5678/journal.2024.456"

    def test_s2_url(self):
        s2_id = "a" * 40
        m = REFERENCE_PATTERNS["s2"][0].search(
            f"https://www.semanticscholar.org/paper/Title/{s2_id}"
        )
        assert m and m.group(1) == s2_id

    def test_s2_no_match_short_hex(self):
        m = REFERENCE_PATTERNS["s2"][0].search("https://www.semanticscholar.org/paper/Title/abc123")
        assert m is None

    def test_backward_compat_aliases(self):
        assert ARXIV_PATTERNS is REFERENCE_PATTERNS["arxiv"]
        assert DOI_PATTERNS is REFERENCE_PATTERNS["doi"]
        assert S2_URL_PATTERN is REFERENCE_PATTERNS["s2"][0]


# ---------------------------------------------------------------------------
# normalize_id
# ---------------------------------------------------------------------------


class TestNormalizeId:
    def test_arxiv_strips_version(self):
        assert normalize_id("arxiv", "2401.12345v3") == "2401.12345"

    def test_arxiv_no_version_unchanged(self):
        assert normalize_id("arxiv", "2401.12345") == "2401.12345"

    def test_doi_lowercase_and_strip(self):
        assert normalize_id("doi", "10.1234/FOO.BAR.,;:") == "10.1234/foo.bar"

    def test_doi_no_trailing_punct(self):
        assert normalize_id("doi", "10.1234/clean") == "10.1234/clean"

    def test_s2_passthrough(self):
        s2_id = "a" * 40
        assert normalize_id("s2", s2_id) == s2_id

    def test_unknown_type_passthrough(self):
        assert normalize_id("pmid", "12345") == "12345"


# ---------------------------------------------------------------------------
# classify_url
# ---------------------------------------------------------------------------


class TestClassifyUrl:
    def test_arxiv_abs(self):
        ref = classify_url("https://arxiv.org/abs/2401.12345")
        assert ref is not None
        assert ref.external_id == "2401.12345"
        assert ref.external_id_type == "arxiv"
        assert ref.external_url == "https://arxiv.org/abs/2401.12345"
        assert ref.confidence == 1.0

    def test_arxiv_pdf(self):
        ref = classify_url("https://arxiv.org/pdf/2401.12345")
        assert ref is not None
        assert ref.external_id_type == "arxiv"

    def test_doi(self):
        ref = classify_url("https://doi.org/10.1234/test.123")
        assert ref is not None
        assert ref.external_id_type == "doi"
        assert ref.external_url == "https://doi.org/10.1234/test.123"

    def test_semantic_scholar(self):
        s2_id = "b" * 40
        ref = classify_url(f"https://www.semanticscholar.org/paper/Title/{s2_id}")
        assert ref is not None
        assert ref.external_id == s2_id
        assert ref.external_id_type == "s2"

    def test_unknown_url(self):
        assert classify_url("https://example.com/some-article") is None

    def test_empty_string(self):
        assert classify_url("") is None


# ---------------------------------------------------------------------------
# extract_context
# ---------------------------------------------------------------------------


class TestExtractContext:
    def test_basic_window(self):
        text = "x" * 200 + "TARGET" + "y" * 200
        # Create a fake match at position 200..206
        m = re.search(r"TARGET", text)
        assert m is not None
        snippet = extract_context(text, m, window=10)
        assert "TARGET" in snippet
        assert len(snippet) <= len("TARGET") + 20 + 2  # window both sides + strip margin

    def test_near_start(self):
        text = "AB TARGET rest of text"
        m = re.search(r"TARGET", text)
        assert m is not None
        snippet = extract_context(text, m, window=150)
        assert snippet.startswith("AB")
        assert "TARGET" in snippet

    def test_near_end(self):
        text = "start of text TARGET XY"
        m = re.search(r"TARGET", text)
        assert m is not None
        snippet = extract_context(text, m, window=150)
        assert snippet.endswith("XY")

    def test_default_window_150(self):
        text = "a" * 300 + "MATCH" + "b" * 300
        m = re.search(r"MATCH", text)
        assert m is not None
        snippet = extract_context(text, m)
        # Should include ~150 chars on each side
        assert len(snippet) <= 305


# ---------------------------------------------------------------------------
# _deduplicate_refs
# ---------------------------------------------------------------------------


class TestDeduplicateRefs:
    def test_no_duplicates(self):
        refs = [
            ExtractedReference(external_id="a", external_id_type="arxiv", external_url="u1"),
            ExtractedReference(external_id="b", external_id_type="doi", external_url="u2"),
        ]
        assert len(_deduplicate_refs(refs)) == 2

    def test_removes_exact_duplicates(self):
        ref = ExtractedReference(external_id="a", external_id_type="arxiv", external_url="u1")
        refs = [
            ref,
            ExtractedReference(external_id="a", external_id_type="arxiv", external_url="u1"),
        ]
        assert len(_deduplicate_refs(refs)) == 1

    def test_keeps_different_types(self):
        refs = [
            ExtractedReference(external_id="a", external_id_type="arxiv", external_url="u1"),
            ExtractedReference(external_id="a", external_id_type="doi", external_url="u1"),
        ]
        assert len(_deduplicate_refs(refs)) == 2

    def test_url_only_dedup(self):
        refs = [
            ExtractedReference(external_url="https://example.com"),
            ExtractedReference(external_url="https://example.com"),
        ]
        assert len(_deduplicate_refs(refs)) == 1

    def test_preserves_order(self):
        refs = [
            ExtractedReference(external_id="c", external_id_type="arxiv"),
            ExtractedReference(external_id="a", external_id_type="arxiv"),
            ExtractedReference(external_id="b", external_id_type="arxiv"),
        ]
        deduped = _deduplicate_refs(refs)
        assert [r.external_id for r in deduped] == ["c", "a", "b"]

    def test_empty_list(self):
        assert _deduplicate_refs([]) == []


# ---------------------------------------------------------------------------
# _build_url
# ---------------------------------------------------------------------------


class TestBuildUrl:
    def test_arxiv(self):
        assert _build_url("arxiv", "2401.12345") == "https://arxiv.org/abs/2401.12345"

    def test_doi(self):
        assert _build_url("doi", "10.1234/test") == "https://doi.org/10.1234/test"

    def test_s2(self):
        s2_id = "a" * 40
        assert _build_url("s2", s2_id) == f"https://www.semanticscholar.org/paper/{s2_id}"

    def test_unknown(self):
        assert _build_url("pmid", "12345") is None


# ---------------------------------------------------------------------------
# ReferenceExtractor — legacy methods
# ---------------------------------------------------------------------------


class TestReferenceExtractorLegacy:
    def setup_method(self):
        self.extractor = ReferenceExtractor()

    def test_extract_arxiv_ids(self):
        text = "arXiv:2401.12345 and https://arxiv.org/abs/2301.54321"
        assert self.extractor.extract_arxiv_ids(text) == {"2401.12345", "2301.54321"}

    def test_extract_dois(self):
        text = "https://doi.org/10.1234/conf.2024.123"
        assert self.extractor.extract_dois(text) == {"10.1234/conf.2024.123"}

    def test_extract_s2_ids(self):
        s2_id = "a" * 40
        text = f"https://www.semanticscholar.org/paper/Title/{s2_id}"
        assert self.extractor.extract_s2_ids(text) == {s2_id}

    def test_extract_all(self):
        s2_id = "a" * 40
        text = f"arXiv:2401.12345 doi.org/10.1234/test semanticscholar.org/paper/T/{s2_id}"
        refs = self.extractor.extract_all(text)
        assert "2401.12345" in refs["arxiv"]
        assert "10.1234/test" in refs["doi"]
        assert s2_id in refs["s2"]

    def test_extract_from_contents(self):
        class FakeContent:
            def __init__(self, md):
                self.markdown_content = md

        contents = [FakeContent("arXiv:2401.12345"), FakeContent(""), FakeContent(None)]
        result = self.extractor.extract_from_contents(contents)
        assert "ArXiv:2401.12345" in result

    def test_extract_from_contents_empty(self):
        assert self.extractor.extract_from_contents([]) == []


# ---------------------------------------------------------------------------
# ReferenceExtractor._find_chunk_for_offset
# ---------------------------------------------------------------------------


class TestFindChunkForOffset:
    def setup_method(self):
        self.extractor = ReferenceExtractor()

    def _make_chunk(self, chunk_id, text):
        c = MagicMock()
        c.id = chunk_id
        c.text = text
        return c

    def test_finds_first_chunk(self):
        chunks = [self._make_chunk(1, "Hello "), self._make_chunk(2, "World!")]
        assert self.extractor._find_chunk_for_offset(chunks, 3).id == 1  # type: ignore[union-attr]

    def test_finds_second_chunk(self):
        chunks = [self._make_chunk(1, "Hello "), self._make_chunk(2, "World!")]
        assert self.extractor._find_chunk_for_offset(chunks, 6).id == 2  # type: ignore[union-attr]

    def test_offset_beyond_all_chunks(self):
        chunks = [self._make_chunk(1, "Short")]
        assert self.extractor._find_chunk_for_offset(chunks, 100) is None

    def test_empty_chunks(self):
        assert self.extractor._find_chunk_for_offset([], 0) is None

    def test_chunk_with_none_text(self):
        c = self._make_chunk(1, None)
        c.text = None
        assert self.extractor._find_chunk_for_offset([c], 0) is None


# ---------------------------------------------------------------------------
# ReferenceExtractor.extract_from_content
# ---------------------------------------------------------------------------


class TestExtractFromContent:
    def setup_method(self):
        self.extractor = ReferenceExtractor()

    def _make_content(self, markdown=None, links_json=None):
        c = MagicMock()
        c.id = 42
        c.markdown_content = markdown
        c.links_json = links_json
        return c

    @patch("src.services.reference_extractor.DocumentChunk", create=True)
    def test_none_markdown_returns_empty(self, _mock_chunk):
        content = self._make_content(markdown=None)
        db = MagicMock()
        result = self.extractor.extract_from_content(content, db)
        assert result == []

    @patch("src.services.reference_extractor.DocumentChunk", create=True)
    def test_empty_markdown_returns_empty(self, _mock_chunk):
        content = self._make_content(markdown="")
        db = MagicMock()
        result = self.extractor.extract_from_content(content, db)
        assert result == []

    def test_extracts_arxiv_from_markdown(self):
        content = self._make_content(
            markdown="See arXiv:2401.12345v2 for details",
            links_json=[],
        )
        db = MagicMock()
        # Mock the chunk query to return empty list
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        result = self.extractor.extract_from_content(content, db)
        assert len(result) >= 1
        arxiv_refs = [r for r in result if r.external_id_type == "arxiv"]
        assert len(arxiv_refs) >= 1
        # Version should be stripped by normalize_id
        assert arxiv_refs[0].external_id == "2401.12345"
        assert arxiv_refs[0].external_url == "https://arxiv.org/abs/2401.12345v2"

    def test_classifies_known_urls_from_links_json(self):
        content = self._make_content(
            markdown="Some text without IDs",
            links_json=["https://arxiv.org/abs/2401.99999", "https://example.com/article"],
        )
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        result = self.extractor.extract_from_content(content, db)
        arxiv_refs = [r for r in result if r.external_id_type == "arxiv"]
        url_only = [r for r in result if r.external_id is None]
        assert len(arxiv_refs) == 1
        assert len(url_only) == 1
        assert url_only[0].external_url == "https://example.com/article"
        assert url_only[0].confidence == 0.5

    def test_deduplicates_results(self):
        content = self._make_content(
            markdown="arXiv:2401.12345 and again arXiv:2401.12345",
            links_json=[],
        )
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        result = self.extractor.extract_from_content(content, db)
        arxiv_refs = [r for r in result if r.external_id_type == "arxiv"]
        # Two regex matches but deduped to one
        assert len(arxiv_refs) == 1

    def test_anchors_to_chunks(self):
        chunk = MagicMock()
        chunk.id = 7
        chunk.text = "See arXiv:2401.12345 for details"

        content = self._make_content(
            markdown="See arXiv:2401.12345 for details",
            links_json=[],
        )
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [chunk]

        result = self.extractor.extract_from_content(content, db)
        assert len(result) >= 1
        # When chunk is found, context_snippet should be None
        arxiv_ref = [r for r in result if r.external_id_type == "arxiv"][0]
        assert arxiv_ref.source_chunk_id == 7
        assert arxiv_ref.context_snippet is None


# ---------------------------------------------------------------------------
# ReferenceExtractor.store_references
# ---------------------------------------------------------------------------


class TestStoreReferences:
    def setup_method(self):
        self.extractor = ReferenceExtractor()

    def test_stores_ref_with_external_id(self):
        db = MagicMock()
        exec_result = MagicMock()
        exec_result.rowcount = 1
        db.execute.return_value = exec_result

        ref = ExtractedReference(
            external_id="2401.12345",
            external_id_type="arxiv",
            external_url="https://arxiv.org/abs/2401.12345",
        )
        stored = self.extractor.store_references(1, [ref], db)
        assert stored == 1
        db.execute.assert_called_once()
        db.commit.assert_called_once()

    def test_stores_url_only_ref(self):
        db = MagicMock()
        exec_result = MagicMock()
        exec_result.rowcount = 1
        db.execute.return_value = exec_result

        ref = ExtractedReference(
            external_url="https://example.com/article",
            confidence=0.5,
        )
        stored = self.extractor.store_references(1, [ref], db)
        assert stored == 1
        db.execute.assert_called_once()
        db.commit.assert_called_once()

    def test_mixed_refs_both_conflict_paths(self):
        """Test that refs with external_id use constraint and URL-only use index."""
        db = MagicMock()
        exec_result = MagicMock()
        exec_result.rowcount = 1
        db.execute.return_value = exec_result

        refs = [
            ExtractedReference(
                external_id="2401.12345",
                external_id_type="arxiv",
                external_url="https://arxiv.org/abs/2401.12345",
            ),
            ExtractedReference(
                external_url="https://example.com/article",
                confidence=0.5,
            ),
        ]
        stored = self.extractor.store_references(1, refs, db)
        assert stored == 2
        assert db.execute.call_count == 2
        db.commit.assert_called_once()

    def test_conflict_returns_zero_rowcount(self):
        db = MagicMock()
        exec_result = MagicMock()
        exec_result.rowcount = 0  # conflict → not inserted
        db.execute.return_value = exec_result

        ref = ExtractedReference(
            external_id="2401.12345",
            external_id_type="arxiv",
            external_url="https://arxiv.org/abs/2401.12345",
        )
        stored = self.extractor.store_references(1, [ref], db)
        assert stored == 0

    def test_empty_refs(self):
        db = MagicMock()
        stored = self.extractor.store_references(1, [], db)
        assert stored == 0
        db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# ReferenceExtractionResult dataclass
# ---------------------------------------------------------------------------


class TestReferenceExtractionResult:
    def test_defaults(self):
        result = ReferenceExtractionResult()
        assert result.content_scanned == 0
        assert result.references_found == 0
        assert result.references_resolved == 0
        assert result.references_unresolved == 0
        assert result.papers_ingested == 0
        assert result.papers_skipped_duplicate == 0


# ---------------------------------------------------------------------------
# ExtractedReference dataclass
# ---------------------------------------------------------------------------


class TestExtractedReference:
    def test_defaults(self):
        ref = ExtractedReference()
        assert ref.external_id is None
        assert ref.external_id_type is None
        assert ref.external_url is None
        assert ref.source_chunk_id is None
        assert ref.context_snippet is None
        assert ref.confidence == 1.0
        assert ref.reference_type == "cites"

    def test_custom_values(self):
        ref = ExtractedReference(
            external_id="2401.12345",
            external_id_type="arxiv",
            external_url="https://arxiv.org/abs/2401.12345",
            source_chunk_id=5,
            context_snippet="see paper",
            confidence=0.9,
            reference_type="discusses",
        )
        assert ref.external_id == "2401.12345"
        assert ref.reference_type == "discusses"


# ---------------------------------------------------------------------------
# Backward-compatibility shim
# ---------------------------------------------------------------------------


class TestBackwardCompatShim:
    def test_import_from_old_location(self):
        from src.ingestion.reference_extractor import (
            ReferenceExtractionResult as OldResult,
            ReferenceExtractor as OldExtractor,
        )

        assert OldExtractor is ReferenceExtractor
        assert OldResult is ReferenceExtractionResult

    def test_old_module_exports_patterns(self):
        from src.ingestion.reference_extractor import (
            ARXIV_PATTERNS as OLD_ARXIV,
            DOI_PATTERNS as OLD_DOI,
            S2_URL_PATTERN as OLD_S2,
        )

        assert OLD_ARXIV is ARXIV_PATTERNS
        assert OLD_DOI is DOI_PATTERNS
        assert OLD_S2 is S2_URL_PATTERN
