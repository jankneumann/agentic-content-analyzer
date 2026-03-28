"""Tests for the arXiv API client."""

from __future__ import annotations

import pytest

from src.ingestion.arxiv_client import (
    extract_version,
    normalize_arxiv_id,
)


class TestNormalizeArxivId:
    def test_bare_new_id(self):
        assert normalize_arxiv_id("2301.12345") == "2301.12345"

    def test_new_id_with_version(self):
        assert normalize_arxiv_id("2301.12345v3") == "2301.12345"

    def test_bare_old_id(self):
        assert normalize_arxiv_id("hep-th/9901001") == "hep-th/9901001"

    def test_old_id_with_version(self):
        assert normalize_arxiv_id("hep-th/9901001v2") == "hep-th/9901001"

    def test_arxiv_prefix(self):
        assert normalize_arxiv_id("arXiv:2301.12345") == "2301.12345"

    def test_abs_url(self):
        assert normalize_arxiv_id("https://arxiv.org/abs/2301.12345v3") == "2301.12345"

    def test_pdf_url(self):
        assert normalize_arxiv_id("https://arxiv.org/pdf/2301.12345") == "2301.12345"

    def test_doi(self):
        assert normalize_arxiv_id("10.48550/arXiv.2301.12345") == "2301.12345"

    def test_doi_full_url(self):
        assert normalize_arxiv_id("https://doi.org/10.48550/arXiv.2301.12345") == "2301.12345"

    def test_whitespace(self):
        assert normalize_arxiv_id("  2301.12345  ") == "2301.12345"

    def test_invalid_raises(self):
        with pytest.raises(ValueError, match="Cannot parse arXiv ID"):
            normalize_arxiv_id("not-an-id")

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            normalize_arxiv_id("")

    def test_five_digit_id(self):
        assert normalize_arxiv_id("2301.12345") == "2301.12345"


class TestExtractVersion:
    def test_no_version(self):
        assert extract_version("2301.12345") == 1

    def test_version_1(self):
        assert extract_version("2301.12345v1") == 1

    def test_version_3(self):
        assert extract_version("2301.12345v3") == 3

    def test_version_in_url(self):
        assert extract_version("http://arxiv.org/abs/2301.12345v2") == 2


class TestArxivClientParsing:
    """Test the Atom feed parsing logic using feedparser-compatible dicts."""

    def test_parse_entry_extracts_fields(self):
        from src.ingestion.arxiv_client import ArxivClient

        client = ArxivClient(api_delay=0, pdf_delay=0)

        entry = {
            "id": "http://arxiv.org/abs/2301.12345v2",
            "title": "A Great  Paper  Title",
            "summary": "This is  the  abstract.",
            "authors": [
                {"name": "Jane Smith"},
                {"name": "John Doe", "arxiv_affiliation": "MIT"},
            ],
            "tags": [
                {"term": "cs.AI", "scheme": None},
                {"term": "cs.LG", "scheme": None},
            ],
            "arxiv_primary_category": {"term": "cs.AI"},
            "published_parsed": (2023, 1, 15, 0, 0, 0, 0, 0, 0),
            "updated_parsed": (2023, 6, 1, 0, 0, 0, 0, 0, 0),
            "arxiv_doi": "10.48550/arXiv.2301.12345",
            "arxiv_journal_ref": "NeurIPS 2024",
            "arxiv_comment": "15 pages, 5 figures",
        }

        paper = client._parse_entry(entry)

        assert paper.arxiv_id == "2301.12345"
        assert paper.version == 2
        assert paper.title == "A Great Paper Title"  # whitespace collapsed
        assert paper.abstract == "This is the abstract."
        assert len(paper.authors) == 2
        assert paper.authors[0].name == "Jane Smith"
        assert paper.authors[1].affiliation == "MIT"
        assert paper.categories == ["cs.AI", "cs.LG"]
        assert paper.primary_category == "cs.AI"
        assert paper.published is not None
        assert paper.published.tzinfo is not None  # UTC-aware
        assert paper.doi == "10.48550/arXiv.2301.12345"
        assert paper.journal_ref == "NeurIPS 2024"
        assert paper.comment == "15 pages, 5 figures"

        client.close()

    def test_parse_entry_handles_missing_fields(self):
        from src.ingestion.arxiv_client import ArxivClient

        client = ArxivClient(api_delay=0, pdf_delay=0)

        entry = {
            "id": "http://arxiv.org/abs/2301.99999v1",
            "title": "Minimal Paper",
            "summary": "Short abstract.",
            "authors": [],
            "tags": [],
        }

        paper = client._parse_entry(entry)

        assert paper.arxiv_id == "2301.99999"
        assert paper.version == 1
        assert paper.authors == []
        assert paper.categories == []
        assert paper.doi is None
        assert paper.journal_ref is None

        client.close()
