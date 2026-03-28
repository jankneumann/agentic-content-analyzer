"""Scholar content ingestion via Semantic Scholar API.

Provides search-based, single-paper, and citation-graph ingestion of
academic papers into the unified Content model. Papers are stored with
structured markdown and rich metadata for downstream summarisation.

Follows the Client-Service pattern: SemanticScholarClient handles HTTP,
this module handles business logic, dedup, and persistence.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from src.ingestion.gmail import ContentData
from src.models.content import Content, ContentSource, ContentStatus
from src.storage.database import get_db
from src.utils.content_hash import generate_markdown_hash
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.config.sources import ScholarSource
    from src.ingestion.semantic_scholar_client import S2Paper, SemanticScholarClient

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ScholarSearchResult:
    """Result from search-based ingestion."""

    source_name: str
    query: str
    papers_found: int
    papers_ingested: int
    papers_skipped_duplicate: int
    papers_skipped_filter: int
    papers_failed: int = 0


@dataclass
class ScholarPaperResult:
    """Result from single-paper ingestion."""

    identifier: str
    paper_id: str | None = None
    ingested: bool = False
    already_exists: bool = False
    refs_ingested: int = 0
    error: str | None = None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class ScholarContentIngestionService:
    """Service for ingesting academic papers from Semantic Scholar.

    Supports three ingestion modes:
    - **search**: keyword search from source config entries
    - **single_paper**: direct lookup by S2 ID, DOI, or arXiv ID
    - **citation_traversal**: walk references/citations of a paper

    Deduplication is three-tier:
    1. Source ID match (source_type=SCHOLAR + source_id=S2PaperId)
    2. Cross-source DOI/arXiv lookup via GIN-indexed metadata_json
    3. Content hash (normalised markdown)
    """

    def __init__(self, client: SemanticScholarClient | None = None) -> None:
        """Initialise the scholar ingestion service.

        Args:
            client: Semantic Scholar API client.  Lazy-created if not provided.
        """
        self._client = client

    def _get_client(self) -> SemanticScholarClient:
        """Return (and lazily create) the API client."""
        if self._client is None:
            from src.ingestion.semantic_scholar_client import (
                SemanticScholarClient as _Client,
            )

            self._client = _Client()
        return self._client

    # ------------------------------------------------------------------
    # Markdown / metadata helpers
    # ------------------------------------------------------------------

    def _format_paper_markdown(self, paper: S2Paper) -> str:
        """Generate structured markdown for a paper.

        Format follows the design spec: title, authors, venue, citations,
        fields, abstract, TL;DR, and links.
        """
        lines: list[str] = []

        # Title
        lines.append(f"# {paper.title}")
        lines.append("")

        # Authors
        if paper.authors:
            author_names = ", ".join(a.name for a in paper.authors)
            lines.append(f"**Authors:** {author_names}")

        # Venue
        venue_str = paper.venue or "Unknown Venue"
        if paper.year:
            venue_str = f"{venue_str} ({paper.year})"
        lines.append(f"**Venue:** {venue_str}")

        # Citations
        lines.append(
            f"**Citations:** {paper.citation_count} "
            f"({paper.influential_citation_count} influential)"
        )

        # Fields of study
        if paper.fields_of_study:
            lines.append(f"**Fields:** {', '.join(paper.fields_of_study)}")

        lines.append("")

        # Abstract
        if paper.abstract:
            lines.append("## Abstract")
            lines.append("")
            lines.append(paper.abstract)
            lines.append("")

        # TL;DR
        tldr_text = paper.tldr.get("text") if paper.tldr else None
        if tldr_text:
            lines.append("## TL;DR")
            lines.append("")
            lines.append(tldr_text)
            lines.append("")

        # Links
        links: list[str] = []
        links.append(
            f"- [Semantic Scholar](https://www.semanticscholar.org/paper/{paper.paper_id})"
        )

        arxiv_id = paper.external_ids.get("ArXiv")
        doi = paper.external_ids.get("DOI")

        if arxiv_id:
            links.append(f"- [arXiv](https://arxiv.org/abs/{arxiv_id})")
            links.append(f"- [PDF](https://arxiv.org/pdf/{arxiv_id})")

        if doi:
            links.append(f"- [DOI](https://doi.org/{doi})")

        oa_url = self._get_open_access_url(paper)
        if oa_url and "arxiv.org" not in oa_url:
            links.append(f"- [Open Access PDF]({oa_url})")

        if links:
            lines.append("## Links")
            lines.append("")
            lines.extend(links)

        return "\n".join(lines)

    def _build_metadata(self, paper: S2Paper, ingestion_mode: str, **extra: Any) -> dict[str, Any]:
        """Build metadata_json dict for a paper."""
        meta: dict[str, Any] = {
            "s2_paper_id": paper.paper_id,
            "authors": [{"name": a.name, "authorId": a.author_id} for a in paper.authors],
            "citation_count": paper.citation_count,
            "influential_citation_count": paper.influential_citation_count,
            "fields_of_study": paper.fields_of_study,
            "publication_types": paper.publication_types,
            "ingestion_mode": ingestion_mode,
        }
        # Only include optional fields when present — avoids storing null
        # values that confuse GIN jsonb_path_ops containment queries
        if paper.external_ids.get("ArXiv"):
            meta["arxiv_id"] = paper.external_ids["ArXiv"]
        if paper.external_ids.get("DOI"):
            meta["doi"] = paper.external_ids["DOI"]
        if paper.external_ids.get("CorpusId"):
            meta["corpus_id"] = paper.external_ids["CorpusId"]
        if paper.venue:
            meta["venue"] = paper.venue
        if paper.year:
            meta["year"] = paper.year
        oa_url = self._get_open_access_url(paper)
        if oa_url:
            meta["open_access_pdf_url"] = oa_url
        if paper.tldr:
            tldr_text = paper.tldr.get("text")
            if tldr_text:
                meta["tldr"] = tldr_text
        meta.update(extra)
        return meta

    def _paper_to_content_data(
        self, paper: S2Paper, ingestion_mode: str, **extra_meta: Any
    ) -> ContentData:
        """Map S2Paper to ContentData for database storage."""
        markdown = self._format_paper_markdown(paper)
        content_hash = generate_markdown_hash(markdown)

        # Author: first author + "et al." if multiple
        author: str | None = None
        if paper.authors:
            author = paper.authors[0].name
            if len(paper.authors) > 1:
                author = f"{author} et al."

        # Publication: venue (year)
        publication: str | None = None
        if paper.venue:
            publication = f"{paper.venue} ({paper.year})" if paper.year else paper.venue

        # Published date: Jan 1 of the paper year (guard against invalid years)
        published_date: datetime | None = None
        if paper.year and 1900 <= paper.year <= 2100:
            published_date = datetime(paper.year, 1, 1, tzinfo=UTC)

        # Source URL: prefer open access PDF, fall back to S2 page
        source_url = (
            self._get_open_access_url(paper)
            or f"https://www.semanticscholar.org/paper/{paper.paper_id}"
        )

        metadata = self._build_metadata(paper, ingestion_mode, **extra_meta)

        return ContentData(
            source_type=ContentSource.SCHOLAR,
            source_id=paper.paper_id,
            source_url=source_url,
            title=paper.title,
            author=author,
            publication=publication,
            published_date=published_date,
            markdown_content=markdown,
            content_hash=content_hash,
            metadata_json=metadata,
            raw_content=paper.abstract or "",
            raw_format="abstract",
            parser_used="semantic_scholar",
        )

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    def _apply_filters(
        self,
        papers: list[S2Paper],
        min_citations: int = 0,
        paper_types: list[str] | None = None,
        fields_of_study: list[str] | None = None,
    ) -> list[S2Paper]:
        """Filter papers by citation count, type, and field of study."""
        filtered: list[S2Paper] = []
        for paper in papers:
            if paper.citation_count < min_citations:
                continue
            if paper_types and not any(pt in paper.publication_types for pt in paper_types):
                continue
            if fields_of_study and not any(f in paper.fields_of_study for f in fields_of_study):
                continue
            filtered.append(paper)
        return filtered

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------

    def _check_cross_source_duplicate(self, paper: S2Paper, db: Any) -> bool:
        """Check if paper already exists via DOI/arXiv across all source types.

        Uses GIN-indexed metadata_json containment queries for efficient
        cross-source dedup.

        Returns:
            True if a duplicate was found, False otherwise.
        """
        doi = paper.external_ids.get("DOI")
        arxiv_id = paper.external_ids.get("ArXiv")

        if doi:
            result = db.execute(
                text("SELECT id FROM contents WHERE metadata_json @> CAST(:val AS jsonb) LIMIT 1"),
                {"val": json.dumps({"doi": doi})},
            ).first()
            if result:
                return True

        if arxiv_id:
            result = db.execute(
                text("SELECT id FROM contents WHERE metadata_json @> CAST(:val AS jsonb) LIMIT 1"),
                {"val": json.dumps({"arxiv_id": arxiv_id})},
            ).first()
            if result:
                return True

        return False

    # ------------------------------------------------------------------
    # Persistence helper
    # ------------------------------------------------------------------

    def _store_paper(
        self,
        content_data: ContentData,
        db: Any,
        force_reprocess: bool = False,
    ) -> bool:
        """Store a single paper as a Content record.

        Returns:
            True if the paper was ingested (new or updated), False if skipped.
        """
        # Primary dedup: source_type + source_id
        existing = (
            db.query(Content)
            .filter(
                Content.source_type == content_data.source_type,
                Content.source_id == content_data.source_id,
            )
            .first()
        )

        if existing:
            if force_reprocess:
                existing.title = content_data.title
                existing.author = content_data.author
                existing.publication = content_data.publication
                existing.published_date = content_data.published_date
                existing.markdown_content = content_data.markdown_content
                existing.metadata_json = content_data.metadata_json
                existing.content_hash = content_data.content_hash
                existing.raw_content = content_data.raw_content
                existing.raw_format = content_data.raw_format
                existing.parser_used = content_data.parser_used
                existing.status = ContentStatus.PARSED
                existing.error_message = None
                db.flush()
                logger.info(f"Updated for reprocessing: {content_data.title}")
                return True
            logger.debug(f"Paper already exists: {content_data.source_id}")
            return False

        # Content hash dedup
        if content_data.content_hash:
            hash_dup = (
                db.query(Content).filter(Content.content_hash == content_data.content_hash).first()
            )
            if hash_dup:
                logger.info(
                    f"Content hash duplicate: '{content_data.title}' "
                    f"matches content ID {hash_dup.id}"
                )
                return False

        # Create new content
        content = Content(
            source_type=content_data.source_type,
            source_id=content_data.source_id,
            source_url=content_data.source_url,
            title=content_data.title,
            author=content_data.author,
            publication=content_data.publication,
            published_date=content_data.published_date,
            markdown_content=content_data.markdown_content,
            metadata_json=content_data.metadata_json,
            raw_content=content_data.raw_content,
            raw_format=content_data.raw_format,
            parser_used=content_data.parser_used,
            content_hash=content_data.content_hash,
            status=ContentStatus.PARSED,
        )
        db.add(content)
        db.flush()

        # Index for search (fail-safe)
        try:
            from src.services.indexing import index_content

            index_content(content, db)
        except Exception:
            logger.debug("Search indexing skipped (non-fatal)", exc_info=True)

        logger.info(f"Ingested paper: {content_data.title}")
        return True

    # ------------------------------------------------------------------
    # Public ingestion methods
    # ------------------------------------------------------------------

    async def ingest_from_search(
        self,
        source_config: ScholarSource,
        force_reprocess: bool = False,
    ) -> ScholarSearchResult:
        """Search-based ingestion from a source config entry.

        Calls the Semantic Scholar search API, applies filters, deduplicates,
        and stores matching papers.

        Args:
            source_config: ScholarSource from sources.d/scholar.yaml
            force_reprocess: Re-ingest papers that already exist

        Returns:
            ScholarSearchResult with counts
        """
        client = self._get_client()
        query = source_config.query
        max_entries = source_config.max_entries or 20

        logger.info(
            f"Scholar search: '{query}' (max={max_entries}, "
            f"source={source_config.name or 'unnamed'})"
        )

        result = ScholarSearchResult(
            source_name=source_config.name or query,
            query=query,
            papers_found=0,
            papers_ingested=0,
            papers_skipped_duplicate=0,
            papers_skipped_filter=0,
        )

        try:
            # Parse year_range for API parameter
            year_range = getattr(source_config, "year_range", "") or ""

            search_result = await client.search_papers(
                query=query,
                limit=max_entries,
                year_range=year_range if year_range else None,
                fields_of_study=(
                    source_config.fields_of_study if source_config.fields_of_study else None
                ),
            )
            papers = search_result.data
            result.papers_found = len(papers)
        except Exception as e:
            logger.error(f"Scholar search failed for '{query}': {e}")
            result.papers_failed = 1
            return result

        if not papers:
            logger.info(f"No papers found for query: '{query}'")
            return result

        # Apply local filters
        min_citations = getattr(source_config, "min_citation_count", 0) or 0
        paper_types = source_config.paper_types if source_config.paper_types else None
        fos = source_config.fields_of_study if source_config.fields_of_study else None

        filtered = self._apply_filters(
            papers,
            min_citations=min_citations,
            paper_types=paper_types,
            fields_of_study=fos,
        )
        result.papers_skipped_filter = len(papers) - len(filtered)

        # Store papers (use savepoints for per-paper error isolation)
        with get_db() as db:
            for paper in filtered:
                try:
                    sp = db.begin_nested()
                    # Cross-source dedup
                    if not force_reprocess and self._check_cross_source_duplicate(paper, db):
                        result.papers_skipped_duplicate += 1
                        logger.debug(f"Cross-source duplicate: {paper.title}")
                        sp.rollback()
                        continue

                    content_data = self._paper_to_content_data(
                        paper,
                        ingestion_mode="search",
                        search_query=query,
                        source_name=source_config.name,
                        source_tags=source_config.tags if source_config.tags else None,
                    )

                    if self._store_paper(content_data, db, force_reprocess):
                        result.papers_ingested += 1
                    else:
                        result.papers_skipped_duplicate += 1
                    sp.commit()
                except Exception as e:
                    result.papers_failed += 1
                    logger.error(
                        f"Failed to ingest paper '{paper.title}': {e}",
                        exc_info=True,
                    )
                    sp.rollback()

        logger.info(
            f"Scholar search '{query}': found={result.papers_found}, "
            f"ingested={result.papers_ingested}, "
            f"dup={result.papers_skipped_duplicate}, "
            f"filtered={result.papers_skipped_filter}, "
            f"failed={result.papers_failed}"
        )
        return result

    async def ingest_paper(
        self,
        identifier: str,
        with_refs: bool = False,
        force_reprocess: bool = False,
    ) -> ScholarPaperResult:
        """Ingest a single paper by identifier.

        Supports S2 paper ID, ``DOI:10.xxx``, ``ArXiv:2301.xxx``, etc.

        Args:
            identifier: Paper identifier (S2 ID, DOI, arXiv, etc.)
            with_refs: Also ingest the paper's references
            force_reprocess: Re-ingest if already exists

        Returns:
            ScholarPaperResult
        """
        client = self._get_client()
        result = ScholarPaperResult(identifier=identifier)

        logger.info(f"Ingesting paper: {identifier}")

        try:
            paper = await client.get_paper(identifier)
        except Exception as e:
            result.error = str(e)
            logger.error(f"Failed to fetch paper '{identifier}': {e}")
            return result

        if paper is None:
            result.error = "Paper not found"
            logger.warning(f"Paper not found: {identifier}")
            return result

        result.paper_id = paper.paper_id

        with get_db() as db:
            # Cross-source dedup
            if not force_reprocess and self._check_cross_source_duplicate(paper, db):
                result.already_exists = True
                logger.info(f"Paper already exists (cross-source): {paper.title}")
                return result

            content_data = self._paper_to_content_data(paper, ingestion_mode="single_paper")

            if self._store_paper(content_data, db, force_reprocess):
                result.ingested = True
            else:
                result.already_exists = True

        # Optionally ingest references
        if with_refs and result.paper_id:
            try:
                refs_result = await self.ingest_from_citations(
                    paper_id=result.paper_id,
                    direction="references",
                    force_reprocess=force_reprocess,
                )
                result.refs_ingested = refs_result.papers_ingested
            except Exception as e:
                logger.error(f"Failed to ingest references for {identifier}: {e}")

        return result

    async def ingest_from_citations(
        self,
        paper_id: str,
        direction: str = "references",
        min_citations: int = 0,
        limit: int = 50,
        force_reprocess: bool = False,
    ) -> ScholarSearchResult:
        """Citation graph traversal ingestion.

        Walk the references or citations of a paper and ingest them.

        Args:
            paper_id: S2 paper ID of the seed paper
            direction: ``"references"`` or ``"citations"``
            min_citations: Minimum citation count filter
            limit: Maximum papers to ingest
            force_reprocess: Re-ingest existing papers

        Returns:
            ScholarSearchResult with ingestion counts
        """
        client = self._get_client()

        logger.info(
            f"Ingesting {direction} for paper {paper_id} "
            f"(min_citations={min_citations}, limit={limit})"
        )

        result = ScholarSearchResult(
            source_name=f"{direction}:{paper_id}",
            query=paper_id,
            papers_found=0,
            papers_ingested=0,
            papers_skipped_duplicate=0,
            papers_skipped_filter=0,
        )

        try:
            if direction == "citations":
                papers = await client.get_paper_citations(paper_id, limit=limit)
            else:
                papers = await client.get_paper_references(paper_id, limit=limit)

            result.papers_found = len(papers)
        except Exception as e:
            logger.error(f"Failed to fetch {direction} for {paper_id}: {e}")
            result.papers_failed = 1
            return result

        if not papers:
            return result

        # Filter by citation count
        if min_citations > 0:
            filtered = [p for p in papers if p.citation_count >= min_citations]
            result.papers_skipped_filter = len(papers) - len(filtered)
            papers = filtered

        # Limit
        papers = papers[:limit]

        with get_db() as db:
            for paper in papers:
                try:
                    sp = db.begin_nested()
                    if not force_reprocess and self._check_cross_source_duplicate(paper, db):
                        result.papers_skipped_duplicate += 1
                        sp.rollback()
                        continue

                    content_data = self._paper_to_content_data(
                        paper,
                        ingestion_mode="citation_traversal",
                        seed_paper_id=paper_id,
                        traversal_direction=direction,
                    )

                    if self._store_paper(content_data, db, force_reprocess):
                        result.papers_ingested += 1
                    else:
                        result.papers_skipped_duplicate += 1
                    sp.commit()
                except Exception as e:
                    result.papers_failed += 1
                    logger.error(
                        f"Failed to ingest {direction} paper '{paper.title}': {e}",
                        exc_info=True,
                    )
                    sp.rollback()

        logger.info(
            f"Citation traversal ({direction}) for {paper_id}: "
            f"found={result.papers_found}, ingested={result.papers_ingested}"
        )
        return result

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None:
            await self._client.close()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_open_access_url(paper: S2Paper) -> str | None:
        """Extract the open access PDF URL from a paper, if available."""
        if paper.open_access_pdf and isinstance(paper.open_access_pdf, dict):
            return paper.open_access_pdf.get("url")
        return None
