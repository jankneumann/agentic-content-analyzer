"""Tests for ScholarContentIngestionService.

Covers:
- ScholarSearchResult and ScholarPaperResult dataclasses
- _format_paper_markdown: structured markdown generation
- _build_metadata: metadata dict construction
- _paper_to_content_data: S2Paper → ContentData mapping
- _apply_filters: citation count, paper type, and field of study filters
- _check_cross_source_duplicate: GIN-indexed JSONB containment dedup
- _store_paper: persistence with dedup (primary, content hash)
- ingest_from_search: full search lifecycle
- ingest_paper: single paper + optional references
- ingest_from_citations: citation graph traversal
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.ingestion.scholar import (
    ScholarContentIngestionService,
    ScholarPaperResult,
    ScholarSearchResult,
)

# ---------------------------------------------------------------------------
# Fixtures: fake S2 types (avoid importing not-yet-existing client module)
# ---------------------------------------------------------------------------


@dataclass
class FakeS2Author:
    name: str
    author_id: str | None = None


@dataclass
class FakeS2Paper:
    paper_id: str
    title: str
    abstract: str | None = None
    year: int | None = None
    venue: str | None = None
    citation_count: int = 0
    influential_citation_count: int = 0
    fields_of_study: list[str] = field(default_factory=list)
    authors: list[FakeS2Author] = field(default_factory=list)
    publication_types: list[str] = field(default_factory=list)
    external_ids: dict[str, str] = field(default_factory=dict)
    open_access_pdf: dict[str, str] | None = None
    tldr: dict[str, str] | None = None


@dataclass
class FakeS2SearchResult:
    total: int
    offset: int
    data: list[FakeS2Paper]


def _make_paper(**overrides) -> FakeS2Paper:
    """Factory for creating test papers with sensible defaults."""
    defaults = {
        "paper_id": "abc123",
        "title": "Attention Is All You Need",
        "abstract": "We propose a new architecture...",
        "year": 2017,
        "venue": "NeurIPS",
        "citation_count": 100000,
        "influential_citation_count": 5000,
        "fields_of_study": ["Computer Science"],
        "authors": [
            FakeS2Author(name="Ashish Vaswani", author_id="1"),
            FakeS2Author(name="Noam Shazeer", author_id="2"),
        ],
        "publication_types": ["Conference"],
        "external_ids": {"ArXiv": "1706.03762", "DOI": "10.5555/3295222.3295349"},
        "open_access_pdf": {"url": "https://arxiv.org/pdf/1706.03762"},
        "tldr": {"text": "Transformers replace recurrence with self-attention."},
    }
    defaults.update(overrides)
    return FakeS2Paper(**defaults)


def _make_source(**overrides) -> MagicMock:
    """Factory for ScholarSource mock."""
    source = MagicMock()
    source.name = overrides.get("name", "Test Source")
    source.query = overrides.get("query", "transformers")
    source.max_entries = overrides.get("max_entries", 20)
    source.min_citation_count = overrides.get("min_citation_count", 0)
    source.paper_types = overrides.get("paper_types", [])
    source.fields_of_study = overrides.get("fields_of_study", [])
    source.year_range = overrides.get("year_range", "")
    source.tags = overrides.get("tags", ["ai"])
    source.enabled = overrides.get("enabled", True)
    return source


# ---------------------------------------------------------------------------
# Result dataclass tests
# ---------------------------------------------------------------------------


class TestScholarSearchResult:
    def test_creation(self):
        r = ScholarSearchResult(
            source_name="test",
            query="ai",
            papers_found=10,
            papers_ingested=5,
            papers_skipped_duplicate=3,
            papers_skipped_filter=2,
        )
        assert r.papers_found == 10
        assert r.papers_failed == 0

    def test_defaults(self):
        r = ScholarSearchResult(
            source_name="s",
            query="q",
            papers_found=0,
            papers_ingested=0,
            papers_skipped_duplicate=0,
            papers_skipped_filter=0,
        )
        assert r.papers_failed == 0


class TestScholarPaperResult:
    def test_creation(self):
        r = ScholarPaperResult(identifier="abc123")
        assert r.identifier == "abc123"
        assert r.paper_id is None
        assert r.ingested is False
        assert r.already_exists is False
        assert r.refs_ingested == 0
        assert r.error is None

    def test_full_creation(self):
        r = ScholarPaperResult(
            identifier="DOI:10.123",
            paper_id="abc",
            ingested=True,
            refs_ingested=5,
        )
        assert r.ingested is True
        assert r.refs_ingested == 5


# ---------------------------------------------------------------------------
# Markdown formatting
# ---------------------------------------------------------------------------


class TestFormatPaperMarkdown:
    def setup_method(self):
        self.service = ScholarContentIngestionService(client=MagicMock())

    def test_basic_paper(self):
        paper = _make_paper()
        md = self.service._format_paper_markdown(paper)

        assert "# Attention Is All You Need" in md
        assert "Ashish Vaswani" in md
        assert "NeurIPS (2017)" in md
        assert "100000" in md
        assert "5000 influential" in md
        assert "Computer Science" in md
        assert "## Abstract" in md
        assert "We propose a new architecture" in md
        assert "## TL;DR" in md
        assert "Transformers replace recurrence" in md
        assert "semanticscholar.org/paper/abc123" in md
        assert "arxiv.org/abs/1706.03762" in md
        assert "doi.org/10.5555/3295222.3295349" in md

    def test_minimal_paper(self):
        paper = _make_paper(
            abstract=None,
            venue=None,
            year=None,
            authors=[],
            fields_of_study=[],
            external_ids={},
            open_access_pdf=None,
            tldr=None,
        )
        md = self.service._format_paper_markdown(paper)
        assert "# Attention Is All You Need" in md
        assert "Unknown Venue" in md
        assert "## Abstract" not in md
        assert "## TL;DR" not in md

    def test_open_access_non_arxiv(self):
        """Non-arXiv open access PDFs should get their own link."""
        paper = _make_paper(
            external_ids={},
            open_access_pdf={"url": "https://example.com/paper.pdf"},
        )
        md = self.service._format_paper_markdown(paper)
        assert "Open Access PDF" in md
        assert "example.com/paper.pdf" in md


# ---------------------------------------------------------------------------
# Metadata building
# ---------------------------------------------------------------------------


class TestBuildMetadata:
    def setup_method(self):
        self.service = ScholarContentIngestionService(client=MagicMock())

    def test_full_metadata(self):
        paper = _make_paper()
        meta = self.service._build_metadata(paper, "search", search_query="ai")

        assert meta["s2_paper_id"] == "abc123"
        assert meta["arxiv_id"] == "1706.03762"
        assert meta["doi"] == "10.5555/3295222.3295349"
        assert meta["venue"] == "NeurIPS"
        assert meta["year"] == 2017
        assert meta["citation_count"] == 100000
        assert meta["ingestion_mode"] == "search"
        assert meta["search_query"] == "ai"
        assert len(meta["authors"]) == 2

    def test_minimal_metadata(self):
        paper = _make_paper(
            external_ids={},
            open_access_pdf=None,
            tldr=None,
        )
        meta = self.service._build_metadata(paper, "single_paper")
        # Optional fields are omitted when not present (avoids null in JSON)
        assert "arxiv_id" not in meta
        assert "doi" not in meta
        assert "tldr" not in meta
        assert "open_access_pdf_url" not in meta


# ---------------------------------------------------------------------------
# Paper to ContentData mapping
# ---------------------------------------------------------------------------


class TestPaperToContentData:
    def setup_method(self):
        self.service = ScholarContentIngestionService(client=MagicMock())

    def test_basic_mapping(self):
        paper = _make_paper()
        cd = self.service._paper_to_content_data(paper, "search")

        assert cd.source_type.value == "scholar"
        assert cd.source_id == "abc123"
        assert cd.title == "Attention Is All You Need"
        assert cd.author == "Ashish Vaswani et al."
        assert cd.publication == "NeurIPS (2017)"
        assert cd.published_date == datetime(2017, 1, 1, tzinfo=UTC)
        assert cd.parser_used == "semantic_scholar"
        assert len(cd.content_hash) == 64  # SHA-256 hex
        assert cd.metadata_json["ingestion_mode"] == "search"

    def test_single_author(self):
        paper = _make_paper(authors=[FakeS2Author(name="Solo Author", author_id="1")])
        cd = self.service._paper_to_content_data(paper, "search")
        assert cd.author == "Solo Author"

    def test_no_authors(self):
        paper = _make_paper(authors=[])
        cd = self.service._paper_to_content_data(paper, "search")
        assert cd.author is None

    def test_no_venue(self):
        paper = _make_paper(venue=None)
        cd = self.service._paper_to_content_data(paper, "search")
        assert cd.publication is None

    def test_no_year(self):
        paper = _make_paper(year=None)
        cd = self.service._paper_to_content_data(paper, "search")
        assert cd.published_date is None

    def test_source_url_prefers_open_access(self):
        paper = _make_paper(open_access_pdf={"url": "https://example.com/paper.pdf"})
        cd = self.service._paper_to_content_data(paper, "search")
        assert cd.source_url == "https://example.com/paper.pdf"

    def test_source_url_fallback_to_s2(self):
        paper = _make_paper(open_access_pdf=None)
        cd = self.service._paper_to_content_data(paper, "search")
        assert "semanticscholar.org/paper/abc123" in cd.source_url

    def test_extra_meta_passed_through(self):
        paper = _make_paper()
        cd = self.service._paper_to_content_data(
            paper, "search", search_query="test", source_name="My Source"
        )
        assert cd.metadata_json["search_query"] == "test"
        assert cd.metadata_json["source_name"] == "My Source"


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------


class TestApplyFilters:
    def setup_method(self):
        self.service = ScholarContentIngestionService(client=MagicMock())

    def test_no_filters(self):
        papers = [_make_paper(citation_count=0)]
        result = self.service._apply_filters(papers)
        assert len(result) == 1

    def test_citation_filter(self):
        papers = [
            _make_paper(paper_id="a", citation_count=5),
            _make_paper(paper_id="b", citation_count=50),
        ]
        result = self.service._apply_filters(papers, min_citations=10)
        assert len(result) == 1
        assert result[0].paper_id == "b"

    def test_paper_type_filter(self):
        papers = [
            _make_paper(paper_id="a", publication_types=["Conference"]),
            _make_paper(paper_id="b", publication_types=["Review"]),
        ]
        result = self.service._apply_filters(papers, paper_types=["Review"])
        assert len(result) == 1
        assert result[0].paper_id == "b"

    def test_fields_of_study_filter(self):
        papers = [
            _make_paper(paper_id="a", fields_of_study=["Computer Science"]),
            _make_paper(paper_id="b", fields_of_study=["Biology"]),
        ]
        result = self.service._apply_filters(papers, fields_of_study=["Computer Science"])
        assert len(result) == 1
        assert result[0].paper_id == "a"

    def test_combined_filters(self):
        papers = [
            _make_paper(
                paper_id="a",
                citation_count=100,
                publication_types=["Review"],
                fields_of_study=["Computer Science"],
            ),
            _make_paper(
                paper_id="b",
                citation_count=5,
                publication_types=["Review"],
                fields_of_study=["Computer Science"],
            ),
            _make_paper(
                paper_id="c",
                citation_count=100,
                publication_types=["Conference"],
                fields_of_study=["Computer Science"],
            ),
        ]
        result = self.service._apply_filters(
            papers,
            min_citations=10,
            paper_types=["Review"],
            fields_of_study=["Computer Science"],
        )
        assert len(result) == 1
        assert result[0].paper_id == "a"

    def test_empty_list(self):
        result = self.service._apply_filters([])
        assert result == []


# ---------------------------------------------------------------------------
# Cross-source dedup
# ---------------------------------------------------------------------------


class TestCheckCrossSourceDuplicate:
    def setup_method(self):
        self.service = ScholarContentIngestionService(client=MagicMock())

    def test_doi_match(self):
        paper = _make_paper(external_ids={"DOI": "10.123/test"})
        db = MagicMock()
        db.execute.return_value.first.return_value = (1,)

        assert self.service._check_cross_source_duplicate(paper, db) is True

    def test_arxiv_match(self):
        paper = _make_paper(external_ids={"ArXiv": "2301.12345"})
        db = MagicMock()
        db.execute.return_value.first.return_value = (1,)

        assert self.service._check_cross_source_duplicate(paper, db) is True

    def test_no_match(self):
        paper = _make_paper(external_ids={"DOI": "10.123/test", "ArXiv": "2301.12345"})
        db = MagicMock()
        db.execute.return_value.first.return_value = None

        assert self.service._check_cross_source_duplicate(paper, db) is False

    def test_no_external_ids(self):
        paper = _make_paper(external_ids={})
        db = MagicMock()
        assert self.service._check_cross_source_duplicate(paper, db) is False
        db.execute.assert_not_called()

    def test_doi_first_then_arxiv(self):
        """DOI match should be checked first; if found, arXiv is skipped."""
        paper = _make_paper(external_ids={"DOI": "10.123/test", "ArXiv": "2301.12345"})
        db = MagicMock()
        # First call (DOI) returns a match
        db.execute.return_value.first.return_value = (1,)

        assert self.service._check_cross_source_duplicate(paper, db) is True
        # Only one execute call (DOI), arXiv not checked
        assert db.execute.call_count == 1


# ---------------------------------------------------------------------------
# Store paper
# ---------------------------------------------------------------------------


class TestStorePaper:
    def setup_method(self):
        self.service = ScholarContentIngestionService(client=MagicMock())

    @patch("src.services.indexing.index_content")
    def test_store_new_paper(self, mock_index):
        paper = _make_paper()
        cd = self.service._paper_to_content_data(paper, "search")
        db = MagicMock()
        # No existing content
        db.query.return_value.filter.return_value.first.return_value = None

        result = self.service._store_paper(cd, db)

        assert result is True
        db.add.assert_called_once()
        assert db.flush.call_count >= 1

    def test_store_existing_paper_skip(self):
        paper = _make_paper()
        cd = self.service._paper_to_content_data(paper, "search")
        db = MagicMock()
        # Existing content found
        db.query.return_value.filter.return_value.first.return_value = MagicMock()

        result = self.service._store_paper(cd, db)

        assert result is False
        db.add.assert_not_called()

    @patch("src.services.indexing.index_content")
    def test_store_existing_force_reprocess(self, mock_index):
        paper = _make_paper()
        cd = self.service._paper_to_content_data(paper, "search")
        db = MagicMock()
        existing = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = existing

        result = self.service._store_paper(cd, db, force_reprocess=True)

        assert result is True
        assert existing.title == cd.title


# ---------------------------------------------------------------------------
# ingest_from_search
# ---------------------------------------------------------------------------


class TestIngestFromSearch:
    def setup_method(self):
        self.mock_client = AsyncMock()
        self.service = ScholarContentIngestionService(client=self.mock_client)

    @pytest.mark.asyncio
    @patch("src.ingestion.scholar.get_db")
    async def test_successful_search(self, mock_get_db):
        papers = [_make_paper(paper_id=f"p{i}") for i in range(3)]
        self.mock_client.search_papers.return_value = FakeS2SearchResult(
            total=3, offset=0, data=papers
        )

        db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)
        # No existing content, no cross-source dups
        db.query.return_value.filter.return_value.first.return_value = None
        db.execute.return_value.first.return_value = None

        source = _make_source()

        with patch("src.services.indexing.index_content"):
            result = await self.service.ingest_from_search(source)

        assert result.papers_found == 3
        assert result.papers_ingested == 3
        assert result.papers_skipped_duplicate == 0

    @pytest.mark.asyncio
    @patch("src.ingestion.scholar.get_db")
    async def test_search_with_filters(self, mock_get_db):
        papers = [
            _make_paper(paper_id="a", citation_count=5),
            _make_paper(paper_id="b", citation_count=50),
        ]
        self.mock_client.search_papers.return_value = FakeS2SearchResult(
            total=2, offset=0, data=papers
        )

        db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)
        db.query.return_value.filter.return_value.first.return_value = None
        db.execute.return_value.first.return_value = None

        source = _make_source(min_citation_count=10)

        with patch("src.services.indexing.index_content"):
            result = await self.service.ingest_from_search(source)

        assert result.papers_found == 2
        assert result.papers_skipped_filter == 1
        assert result.papers_ingested == 1

    @pytest.mark.asyncio
    async def test_search_api_error(self):
        self.mock_client.search_papers.side_effect = Exception("API error")
        source = _make_source()

        result = await self.service.ingest_from_search(source)

        assert result.papers_found == 0
        assert result.papers_failed == 1

    @pytest.mark.asyncio
    @patch("src.ingestion.scholar.get_db")
    async def test_search_empty_results(self, mock_get_db):
        self.mock_client.search_papers.return_value = FakeS2SearchResult(total=0, offset=0, data=[])
        source = _make_source()

        result = await self.service.ingest_from_search(source)

        assert result.papers_found == 0
        assert result.papers_ingested == 0

    @pytest.mark.asyncio
    @patch("src.ingestion.scholar.get_db")
    async def test_search_cross_source_dedup(self, mock_get_db):
        papers = [_make_paper()]
        self.mock_client.search_papers.return_value = FakeS2SearchResult(
            total=1, offset=0, data=papers
        )

        db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)
        # Cross-source dup found
        db.execute.return_value.first.return_value = (1,)

        source = _make_source()
        result = await self.service.ingest_from_search(source)

        assert result.papers_skipped_duplicate == 1
        assert result.papers_ingested == 0


# ---------------------------------------------------------------------------
# ingest_paper
# ---------------------------------------------------------------------------


class TestIngestPaper:
    def setup_method(self):
        self.mock_client = AsyncMock()
        self.service = ScholarContentIngestionService(client=self.mock_client)

    @pytest.mark.asyncio
    @patch("src.ingestion.scholar.get_db")
    async def test_ingest_new_paper(self, mock_get_db):
        paper = _make_paper()
        self.mock_client.get_paper.return_value = paper

        db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)
        db.query.return_value.filter.return_value.first.return_value = None
        db.execute.return_value.first.return_value = None

        with patch("src.services.indexing.index_content"):
            result = await self.service.ingest_paper("abc123")

        assert result.ingested is True
        assert result.paper_id == "abc123"

    @pytest.mark.asyncio
    @patch("src.ingestion.scholar.get_db")
    async def test_ingest_existing_paper(self, mock_get_db):
        paper = _make_paper()
        self.mock_client.get_paper.return_value = paper

        db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)
        # Cross-source dup found
        db.execute.return_value.first.return_value = (1,)

        result = await self.service.ingest_paper("abc123")

        assert result.already_exists is True
        assert result.ingested is False

    @pytest.mark.asyncio
    async def test_ingest_paper_not_found(self):
        self.mock_client.get_paper.return_value = None

        result = await self.service.ingest_paper("nonexistent")

        assert result.error == "Paper not found"
        assert result.ingested is False

    @pytest.mark.asyncio
    async def test_ingest_paper_api_error(self):
        self.mock_client.get_paper.side_effect = Exception("timeout")

        result = await self.service.ingest_paper("abc123")

        assert result.error == "timeout"

    @pytest.mark.asyncio
    @patch("src.ingestion.scholar.get_db")
    async def test_ingest_paper_with_refs(self, mock_get_db):
        paper = _make_paper()
        self.mock_client.get_paper.return_value = paper
        ref_papers = [_make_paper(paper_id=f"ref{i}") for i in range(3)]
        self.mock_client.get_paper_references.return_value = ref_papers

        db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)
        db.query.return_value.filter.return_value.first.return_value = None
        db.execute.return_value.first.return_value = None

        with patch("src.services.indexing.index_content"):
            result = await self.service.ingest_paper("abc123", with_refs=True)

        assert result.ingested is True
        assert result.refs_ingested == 3


# ---------------------------------------------------------------------------
# ingest_from_citations
# ---------------------------------------------------------------------------


class TestIngestFromCitations:
    def setup_method(self):
        self.mock_client = AsyncMock()
        self.service = ScholarContentIngestionService(client=self.mock_client)

    @pytest.mark.asyncio
    @patch("src.ingestion.scholar.get_db")
    async def test_ingest_references(self, mock_get_db):
        ref_papers = [_make_paper(paper_id=f"ref{i}") for i in range(3)]
        self.mock_client.get_paper_references.return_value = ref_papers

        db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)
        db.query.return_value.filter.return_value.first.return_value = None
        db.execute.return_value.first.return_value = None

        with patch("src.services.indexing.index_content"):
            result = await self.service.ingest_from_citations("seed123")

        assert result.papers_found == 3
        assert result.papers_ingested == 3

    @pytest.mark.asyncio
    @patch("src.ingestion.scholar.get_db")
    async def test_ingest_citations(self, mock_get_db):
        cit_papers = [_make_paper(paper_id=f"cit{i}") for i in range(2)]
        self.mock_client.get_paper_citations.return_value = cit_papers

        db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)
        db.query.return_value.filter.return_value.first.return_value = None
        db.execute.return_value.first.return_value = None

        with patch("src.services.indexing.index_content"):
            result = await self.service.ingest_from_citations("seed123", direction="citations")

        assert result.papers_found == 2
        assert result.papers_ingested == 2

    @pytest.mark.asyncio
    @patch("src.ingestion.scholar.get_db")
    async def test_citation_min_citations_filter(self, mock_get_db):
        papers = [
            _make_paper(paper_id="a", citation_count=5),
            _make_paper(paper_id="b", citation_count=50),
        ]
        self.mock_client.get_paper_references.return_value = papers

        db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)
        db.query.return_value.filter.return_value.first.return_value = None
        db.execute.return_value.first.return_value = None

        with patch("src.services.indexing.index_content"):
            result = await self.service.ingest_from_citations("seed123", min_citations=10)

        assert result.papers_found == 2
        assert result.papers_skipped_filter == 1
        assert result.papers_ingested == 1

    @pytest.mark.asyncio
    async def test_citation_api_error(self):
        self.mock_client.get_paper_references.side_effect = Exception("API error")

        result = await self.service.ingest_from_citations("seed123")

        assert result.papers_failed == 1

    @pytest.mark.asyncio
    @patch("src.ingestion.scholar.get_db")
    async def test_citation_empty(self, mock_get_db):
        self.mock_client.get_paper_references.return_value = []

        result = await self.service.ingest_from_citations("seed123")

        assert result.papers_found == 0
        assert result.papers_ingested == 0


# ---------------------------------------------------------------------------
# Lazy client creation
# ---------------------------------------------------------------------------


class TestLazyClient:
    def test_lazy_creates_client(self):
        """Service without explicit client lazy-creates one via _get_client."""
        service = ScholarContentIngestionService(client=None)

        mock_cls = MagicMock()
        fake_module = MagicMock(SemanticScholarClient=mock_cls)

        with patch.dict(
            "sys.modules",
            {"src.ingestion.semantic_scholar_client": fake_module},
        ):
            client = service._get_client()
            assert client is mock_cls.return_value
            mock_cls.assert_called_once()

    def test_get_client_returns_existing(self):
        """If client already exists, _get_client returns it without creating a new one."""
        mock_client = MagicMock()
        service = ScholarContentIngestionService(client=mock_client)
        assert service._get_client() is mock_client


# ---------------------------------------------------------------------------
# Close
# ---------------------------------------------------------------------------


class TestClose:
    @pytest.mark.asyncio
    async def test_close_with_client(self):
        mock_client = AsyncMock()
        service = ScholarContentIngestionService(client=mock_client)
        await service.close()
        mock_client.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_without_client(self):
        service = ScholarContentIngestionService(client=None)
        # Should not raise
        await service.close()
