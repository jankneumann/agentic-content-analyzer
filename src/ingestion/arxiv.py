"""arXiv content ingestion service.

Provides search-based and single-paper ingestion of arXiv papers into the
unified Content model. Papers are stored with full PDF text (via Docling)
or abstract-only fallback. Version-aware updates replace older revisions.

Follows the Client-Service pattern: ArxivClient handles HTTP, this module
handles business logic, dedup, and persistence.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from src.ingestion.arxiv_client import (
    ArxivClient,
    ArxivPaper,
    normalize_arxiv_id,
)
from src.ingestion.gmail import ContentData
from src.models.content import Content, ContentSource, ContentStatus
from src.storage.database import get_db
from src.utils.content_hash import generate_markdown_hash
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.config.sources import ArxivSource

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ArxivIngestionResult:
    """Result from search-based ingestion."""

    source_name: str
    query: str
    papers_found: int = 0
    papers_ingested: int = 0
    papers_skipped_duplicate: int = 0
    papers_updated_version: int = 0
    papers_enriched_scholar: int = 0
    papers_failed: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class ArxivPaperResult:
    """Result from single-paper ingestion."""

    identifier: str
    arxiv_id: str | None = None
    ingested: bool = False
    already_exists: bool = False
    version_updated: bool = False
    error: str | None = None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class ArxivContentIngestionService:
    """Service for ingesting arXiv papers with full PDF text extraction.

    Supports two ingestion modes:
    - **search**: keyword + category search from source config
    - **single_paper**: direct lookup by arXiv ID, URL, or DOI

    Deduplication is three-tier:
    1. Source ID match (source_type=ARXIV + source_id=base_arxiv_id)
    2. Cross-source arXiv ID lookup via GIN-indexed metadata_json
    3. Version comparison for updates
    """

    def __init__(self, client: ArxivClient | None = None) -> None:
        self._client = client or ArxivClient()
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    # ------------------------------------------------------------------
    # PDF extraction
    # ------------------------------------------------------------------

    def _extract_pdf_content(
        self,
        arxiv_id: str,
        version: int,
        max_pages: int = 80,
    ) -> tuple[str | None, str | None]:
        """Download and extract PDF content via Docling.

        Returns (markdown, parser_used) or (None, None) on failure.
        """
        full_id = f"{arxiv_id}v{version}"
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / f"{arxiv_id.replace('/', '_')}.pdf"

            # Download
            if not self._client.download_pdf(full_id, pdf_path):
                return None, None

            # Check page count before expensive Docling parse
            try:
                page_count = self._get_pdf_page_count(pdf_path)
                if page_count and page_count > max_pages:
                    logger.info(
                        f"Skipped PDF for {full_id}: {page_count} pages exceeds limit of {max_pages}"
                    )
                    return None, None
            except Exception as exc:
                logger.warning(f"Could not check page count for {full_id}: {exc}")

            # Parse via Docling
            try:
                from src.parsers.docling_parser import DoclingParser

                parser = DoclingParser()
                result = asyncio.run(parser.parse(pdf_path, format_hint="pdf"))
                if result.markdown:
                    return result.markdown, "DoclingParser"
                logger.warning(f"Docling returned empty markdown for {full_id}")
                return None, None
            except Exception as exc:
                logger.warning(f"Docling parse failed for {full_id}: {exc}")
                return None, None

    @staticmethod
    def _get_pdf_page_count(pdf_path: Path) -> int | None:
        """Get page count using PyPDF2 or pypdf (lightweight check)."""
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(pdf_path))
            return len(reader.pages)
        except ImportError:
            pass
        try:
            from PyPDF2 import PdfReader as PdfReader2  # type: ignore[import-untyped]

            reader2 = PdfReader2(str(pdf_path))
            return len(reader2.pages)
        except ImportError:
            return None

    # ------------------------------------------------------------------
    # Markdown / metadata helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_abstract_markdown(paper: ArxivPaper) -> str:
        """Generate structured markdown from arXiv metadata (no PDF)."""
        lines: list[str] = []
        lines.append(f"# {paper.title}")
        lines.append("")

        if paper.authors:
            author_names = ", ".join(a.name for a in paper.authors)
            lines.append(f"**Authors:** {author_names}")

        if paper.published:
            lines.append(f"**Published:** {paper.published.strftime('%Y-%m-%d')}")

        if paper.categories:
            lines.append(f"**Categories:** {', '.join(paper.categories)}")

        lines.append(f"**arXiv:** [{paper.arxiv_id}](https://arxiv.org/abs/{paper.arxiv_id})")
        lines.append("")

        if paper.abstract:
            lines.append("## Abstract")
            lines.append("")
            lines.append(paper.abstract)
            lines.append("")

        if paper.comment:
            lines.append(f"*{paper.comment}*")
            lines.append("")

        lines.append("---")
        lines.append("*Abstract only — full text extraction not available.*")
        return "\n".join(lines)

    @staticmethod
    def _build_metadata(
        paper: ArxivPaper,
        ingestion_mode: str,
        pdf_extracted: bool = False,
        pdf_pages: int | None = None,
    ) -> dict[str, Any]:
        """Build metadata_json dict for an arXiv paper."""
        meta: dict[str, Any] = {
            "arxiv_id": paper.arxiv_id,
            "arxiv_version": paper.version,
            "arxiv_url": f"https://arxiv.org/abs/{paper.arxiv_id}v{paper.version}",
            "pdf_url": paper.pdf_url,
            "categories": paper.categories,
            "primary_category": paper.primary_category,
            "authors": [{"name": a.name, "affiliation": a.affiliation} for a in paper.authors],
            "abstract": paper.abstract,
            "pdf_extracted": pdf_extracted,
            "ingestion_mode": ingestion_mode,
        }
        if paper.updated:
            meta["updated_date"] = paper.updated.isoformat()
        if paper.doi:
            meta["doi"] = paper.doi
        if paper.journal_ref:
            meta["journal_ref"] = paper.journal_ref
        if paper.comment:
            meta["comment"] = paper.comment
        if pdf_pages is not None:
            meta["pdf_pages"] = pdf_pages
        return meta

    def _paper_to_content_data(
        self,
        paper: ArxivPaper,
        markdown: str,
        parser_used: str,
        metadata: dict[str, Any],
    ) -> ContentData:
        """Map ArxivPaper to ContentData for database storage."""
        content_hash = generate_markdown_hash(markdown)

        # Author: first author + "et al." if multiple
        author: str | None = None
        if paper.authors:
            author = paper.authors[0].name
            if len(paper.authors) > 1:
                author = f"{author} et al."

        return ContentData(
            source_type=ContentSource.ARXIV,
            source_id=paper.arxiv_id,
            source_url=f"https://arxiv.org/abs/{paper.arxiv_id}",
            title=paper.title,
            author=author,
            publication=f"arXiv [{paper.primary_category}]" if paper.primary_category else "arXiv",
            published_date=paper.published,
            markdown_content=markdown,
            content_hash=content_hash,
            metadata_json=metadata,
            raw_content=paper.abstract or "",
            raw_format="xml",
            parser_used=parser_used,
        )

    # ------------------------------------------------------------------
    # Version checking & cross-source dedup
    # ------------------------------------------------------------------

    def _check_version_update(
        self, arxiv_id: str, incoming_version: int, db: Any
    ) -> Content | None:
        """Check if we should update an existing arXiv record.

        Returns the existing Content if incoming version is newer.
        Returns None if no update needed (same/older version or not found).
        """
        existing = (
            db.query(Content)
            .filter(
                Content.source_type == ContentSource.ARXIV,
                Content.source_id == arxiv_id,
            )
            .first()
        )
        if not existing:
            return None

        current_version = (existing.metadata_json or {}).get("arxiv_version", 0)
        if incoming_version > current_version:
            return existing  # Caller should update
        return None  # Same or older — skip

    def _check_cross_source_duplicate(self, arxiv_id: str, db: Any) -> tuple[Content | None, str]:
        """Check for existing content with the same arXiv ID across all sources.

        Returns (existing_content, match_type) where match_type is:
        - "arxiv": same source type, use version check
        - "scholar": Scholar record, enrich with full text
        - "none": no existing content
        """
        # Check arXiv records first (primary dedup)
        arxiv_record = (
            db.query(Content)
            .filter(
                Content.source_type == ContentSource.ARXIV,
                Content.source_id == arxiv_id,
            )
            .first()
        )
        if arxiv_record:
            return arxiv_record, "arxiv"

        # Cross-source: check metadata_json for arxiv_id via GIN index
        result = db.execute(
            text("SELECT id FROM contents WHERE metadata_json @> CAST(:val AS jsonb) LIMIT 1"),
            {"val": json.dumps({"arxiv_id": arxiv_id})},
        ).first()

        if result:
            content = db.query(Content).get(result[0])
            if content and content.source_type == ContentSource.SCHOLAR:
                return content, "scholar"
            if content:
                return content, "other"

        return None, "none"

    def _enrich_scholar_record(
        self,
        scholar_record: Content,
        paper: ArxivPaper,
        markdown: str,
        metadata: dict[str, Any],
        db: Any,
    ) -> bool:
        """Replace Scholar abstract with arXiv full-text PDF content.

        Returns True if enrichment succeeded.
        """
        from src.models.summary import Summary

        scholar_record.markdown_content = markdown
        scholar_record.content_hash = generate_markdown_hash(markdown)
        scholar_record.parser_used = metadata.get("parser_used", "DoclingParser")
        scholar_record.status = ContentStatus.PENDING

        # Merge arXiv-specific metadata into existing metadata
        existing_meta = scholar_record.metadata_json or {}
        existing_meta.update(
            {
                "arxiv_id": paper.arxiv_id,
                "arxiv_version": paper.version,
                "pdf_extracted": True,
                "enriched_from_arxiv": True,
            }
        )
        scholar_record.metadata_json = existing_meta

        # Delete stale summaries
        db.query(Summary).filter(Summary.content_id == scholar_record.id).delete()

        db.flush()
        logger.info(f"Enriched Scholar record {paper.arxiv_id} with arXiv full text")
        return True

    def _update_version(
        self,
        existing: Content,
        paper: ArxivPaper,
        markdown: str,
        parser_used: str,
        metadata: dict[str, Any],
        db: Any,
    ) -> None:
        """Update an existing arXiv record with a newer version."""
        from src.models.summary import Summary

        existing.title = paper.title
        existing.markdown_content = markdown
        existing.content_hash = generate_markdown_hash(markdown)
        existing.parser_used = parser_used
        existing.metadata_json = metadata
        existing.status = ContentStatus.PENDING

        # Delete stale summaries for re-summarization
        db.query(Summary).filter(Summary.content_id == existing.id).delete()

        db.flush()
        logger.info(
            f"Updated {paper.arxiv_id} from v{(existing.metadata_json or {}).get('arxiv_version', '?')} "
            f"to v{paper.version}"
        )

    # ------------------------------------------------------------------
    # Core ingestion
    # ------------------------------------------------------------------

    def _ingest_paper(
        self,
        paper: ArxivPaper,
        *,
        pdf_extraction: bool = True,
        max_pdf_pages: int = 80,
        force_reprocess: bool = False,
        ingestion_mode: str = "search",
    ) -> str:
        """Ingest a single paper. Returns status: 'ingested', 'updated', 'enriched', 'skipped', 'failed'."""
        with get_db() as db:
            # Check for existing content
            existing, match_type = self._check_cross_source_duplicate(paper.arxiv_id, db)

            if match_type == "arxiv" and existing and not force_reprocess:
                # Version check
                current_version = (existing.metadata_json or {}).get("arxiv_version", 0)
                if paper.version <= current_version:
                    return "skipped"

            # Extract PDF content
            markdown: str | None = None
            parser_used = "ArxivAbstractParser"
            pdf_pages: int | None = None

            if pdf_extraction:
                markdown, parser_used_result = self._extract_pdf_content(
                    paper.arxiv_id, paper.version, max_pages=max_pdf_pages
                )
                if markdown and parser_used_result:
                    parser_used = parser_used_result
                    # Try to get page count for metadata
                    pdf_pages = None  # Already checked during extraction

            # Fallback to abstract
            if not markdown:
                markdown = self._format_abstract_markdown(paper)
                parser_used = "ArxivAbstractParser"

            pdf_extracted = parser_used == "DoclingParser"
            metadata = self._build_metadata(
                paper, ingestion_mode, pdf_extracted=pdf_extracted, pdf_pages=pdf_pages
            )

            # Handle Scholar enrichment
            if match_type == "scholar" and existing and pdf_extracted:
                self._enrich_scholar_record(existing, paper, markdown, metadata, db)
                db.commit()
                return "enriched"
            elif match_type == "scholar" and existing and not pdf_extracted:
                # Don't replace Scholar content with abstract-only
                logger.info(
                    f"Skipped enrichment of Scholar record for {paper.arxiv_id}: PDF extraction failed"
                )
                return "skipped"

            # Handle version update
            if match_type == "arxiv" and existing:
                current_version = (existing.metadata_json or {}).get("arxiv_version", 0)
                if paper.version > current_version or force_reprocess:
                    self._update_version(existing, paper, markdown, parser_used, metadata, db)
                    db.commit()
                    return "updated"
                return "skipped"

            # New record
            content_data = self._paper_to_content_data(paper, markdown, parser_used, metadata)
            content = Content(
                source_type=content_data.source_type,
                source_id=content_data.source_id,
                source_url=content_data.source_url,
                title=content_data.title,
                author=content_data.author,
                publication=content_data.publication,
                published_date=content_data.published_date,
                markdown_content=content_data.markdown_content,
                content_hash=content_data.content_hash,
                metadata_json=content_data.metadata_json,
                raw_content=content_data.raw_content,
                raw_format=content_data.raw_format,
                parser_used=content_data.parser_used,
                status=ContentStatus.PARSED,
                ingested_at=datetime.now(UTC),
            )
            db.add(content)
            db.flush()  # Make visible for subsequent dedup checks
            db.commit()
            return "ingested"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ingest_from_search(
        self,
        source_config: ArxivSource,
        *,
        force_reprocess: bool = False,
        after_date: datetime | None = None,
    ) -> ArxivIngestionResult:
        """Ingest papers from a configured arXiv source.

        Args:
            source_config: ArxivSource configuration.
            force_reprocess: Force re-ingest of existing papers.
            after_date: Only ingest papers published after this date.

        Returns:
            ArxivIngestionResult with counts.
        """
        result = ArxivIngestionResult(
            source_name=source_config.name or "arXiv",
            query=source_config.search_query or "",
        )

        papers = self._client.search_papers(
            query=source_config.search_query,
            categories=source_config.categories,
            sort_by=source_config.sort_by,
            max_results=source_config.max_entries or 20,
        )
        result.papers_found = len(papers)

        # Client-side date filtering
        if after_date:
            papers = [p for p in papers if p.published and p.published >= after_date]

        for paper in papers:
            try:
                status = self._ingest_paper(
                    paper,
                    pdf_extraction=source_config.pdf_extraction,
                    max_pdf_pages=source_config.max_pdf_pages,
                    force_reprocess=force_reprocess,
                    ingestion_mode="search",
                )
                if status == "ingested":
                    result.papers_ingested += 1
                elif status == "updated":
                    result.papers_updated_version += 1
                elif status == "enriched":
                    result.papers_enriched_scholar += 1
                elif status == "skipped":
                    result.papers_skipped_duplicate += 1
                else:
                    result.papers_failed += 1
            except Exception as exc:
                logger.error(f"Failed to ingest {paper.arxiv_id}: {exc}")
                result.papers_failed += 1
                result.errors.append(f"{paper.arxiv_id}: {exc}")

        logger.info(
            f"arXiv source '{result.source_name}': "
            f"{result.papers_ingested} ingested, "
            f"{result.papers_updated_version} updated, "
            f"{result.papers_enriched_scholar} enriched, "
            f"{result.papers_skipped_duplicate} skipped, "
            f"{result.papers_failed} failed"
        )
        return result

    def ingest_paper(
        self,
        identifier: str,
        *,
        pdf_extraction: bool = True,
        force_reprocess: bool = False,
    ) -> ArxivPaperResult:
        """Ingest a single paper by identifier.

        Args:
            identifier: arXiv ID, URL, or DOI.
            pdf_extraction: Whether to download and parse the PDF.
            force_reprocess: Force re-ingest.

        Returns:
            ArxivPaperResult with status.
        """
        result = ArxivPaperResult(identifier=identifier)

        try:
            base_id = normalize_arxiv_id(identifier)
        except ValueError as exc:
            result.error = str(exc)
            return result

        result.arxiv_id = base_id

        paper = self._client.get_paper(base_id)
        if not paper:
            result.error = f"Paper not found on arXiv: {base_id}"
            return result

        try:
            status = self._ingest_paper(
                paper,
                pdf_extraction=pdf_extraction,
                force_reprocess=force_reprocess,
                ingestion_mode="single",
            )
            result.ingested = status in ("ingested", "updated", "enriched")
            result.already_exists = status == "skipped"
            result.version_updated = status == "updated"
        except Exception as exc:
            result.error = str(exc)

        return result

    def ingest_content(
        self,
        sources: list[ArxivSource] | None = None,
        *,
        after_date: datetime | None = None,
        force_reprocess: bool = False,
    ) -> int:
        """Ingest from all configured arXiv sources.

        Args:
            sources: List of ArxivSource configs. Loads from sources.d if None.
            after_date: Only ingest papers after this date.
            force_reprocess: Force re-ingest.

        Returns:
            Total number of papers ingested.
        """
        if sources is None:
            from src.config.sources import load_sources_config

            config = load_sources_config()
            sources = config.get_arxiv_sources()

        if not sources:
            logger.info("No arXiv sources configured")
            return 0

        total = 0
        for source in sources:
            if not source.enabled:
                continue
            try:
                result = self.ingest_from_search(
                    source,
                    force_reprocess=force_reprocess,
                    after_date=after_date,
                )
                total += (
                    result.papers_ingested
                    + result.papers_updated_version
                    + result.papers_enriched_scholar
                )
            except Exception as exc:
                logger.error(f"arXiv source '{source.name}' failed: {exc}")

        return total
