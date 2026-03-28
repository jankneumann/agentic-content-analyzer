"""Tests for academic reference extraction."""

from src.ingestion.reference_extractor import (
    ReferenceExtractionResult,
    ReferenceExtractor,
)


class TestArxivExtraction:
    def setup_method(self):
        self.extractor = ReferenceExtractor()

    def test_arxiv_colon_format(self):
        text = "See arXiv:2401.12345 for details"
        assert self.extractor.extract_arxiv_ids(text) == {"2401.12345"}

    def test_arxiv_url(self):
        text = "Available at https://arxiv.org/abs/2301.54321"
        assert self.extractor.extract_arxiv_ids(text) == {"2301.54321"}

    def test_arxiv_pdf_url(self):
        text = "PDF: https://arxiv.org/pdf/2305.99999"
        assert self.extractor.extract_arxiv_ids(text) == {"2305.99999"}

    def test_multiple_arxiv(self):
        text = "arXiv:2401.11111 and arXiv:2401.22222"
        assert len(self.extractor.extract_arxiv_ids(text)) == 2

    def test_case_insensitive(self):
        text = "ARXIV:2401.12345"
        assert self.extractor.extract_arxiv_ids(text) == {"2401.12345"}

    def test_no_match(self):
        text = "No references here"
        assert self.extractor.extract_arxiv_ids(text) == set()


class TestDoiExtraction:
    def setup_method(self):
        self.extractor = ReferenceExtractor()

    def test_doi_url(self):
        text = "https://doi.org/10.1234/conf.2024.123"
        assert self.extractor.extract_dois(text) == {"10.1234/conf.2024.123"}

    def test_doi_prefix(self):
        text = "DOI: 10.5678/journal.2024.456"
        assert self.extractor.extract_dois(text) == {"10.5678/journal.2024.456"}

    def test_doi_trailing_punctuation(self):
        text = "See doi.org/10.1234/test."
        result = self.extractor.extract_dois(text)
        assert "10.1234/test" in result

    def test_no_match(self):
        assert self.extractor.extract_dois("No DOIs") == set()


class TestS2Extraction:
    def setup_method(self):
        self.extractor = ReferenceExtractor()

    def test_s2_url(self):
        s2_id = "a" * 40
        text = f"https://www.semanticscholar.org/paper/Title/{s2_id}"
        assert self.extractor.extract_s2_ids(text) == {s2_id}

    def test_no_match(self):
        assert self.extractor.extract_s2_ids("No S2 URLs") == set()


class TestExtractAll:
    def setup_method(self):
        self.extractor = ReferenceExtractor()

    def test_mixed_references(self):
        text = """
        See arXiv:2401.12345 and https://doi.org/10.1234/test
        Also https://www.semanticscholar.org/paper/Title/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
        """
        refs = self.extractor.extract_all(text)
        assert "2401.12345" in refs["arxiv"]
        assert "10.1234/test" in refs["doi"]
        assert "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" in refs["s2"]

    def test_dedup(self):
        text = "arXiv:2401.12345 and again arXiv:2401.12345"
        refs = self.extractor.extract_all(text)
        assert len(refs["arxiv"]) == 1


class TestExtractFromContents:
    def setup_method(self):
        self.extractor = ReferenceExtractor()

    def test_extracts_from_content_objects(self):
        class FakeContent:
            def __init__(self, md):
                self.markdown_content = md

        contents = [
            FakeContent("Check arXiv:2401.12345"),
            FakeContent("See doi.org/10.1234/test"),
            FakeContent(""),
        ]
        result = self.extractor.extract_from_contents(contents)
        assert "ArXiv:2401.12345" in result
        assert "DOI:10.1234/test" in result
        assert len(result) == 2

    def test_empty_contents(self):
        result = self.extractor.extract_from_contents([])
        assert result == []

    def test_s2_id_format(self):
        class FakeContent:
            def __init__(self, md):
                self.markdown_content = md

        s2_id = "b" * 40
        contents = [
            FakeContent(f"https://www.semanticscholar.org/paper/Title/{s2_id}"),
        ]
        result = self.extractor.extract_from_contents(contents)
        assert s2_id in result


class TestReferenceExtractionResult:
    def test_defaults(self):
        result = ReferenceExtractionResult()
        assert result.content_scanned == 0
        assert result.references_found == 0
        assert result.references_resolved == 0
        assert result.references_unresolved == 0
        assert result.papers_ingested == 0
        assert result.papers_skipped_duplicate == 0

    def test_custom_values(self):
        result = ReferenceExtractionResult(
            content_scanned=10,
            references_found=5,
            papers_ingested=3,
        )
        assert result.content_scanned == 10
        assert result.references_found == 5
        assert result.papers_ingested == 3
