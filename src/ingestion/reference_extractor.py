"""Extract academic paper references from existing ingested content."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.ingestion.scholar import ScholarContentIngestionService

logger = logging.getLogger(__name__)


@dataclass
class ReferenceExtractionResult:
    content_scanned: int = 0
    references_found: int = 0
    references_resolved: int = 0
    references_unresolved: int = 0
    papers_ingested: int = 0
    papers_skipped_duplicate: int = 0


# Regex patterns for academic identifiers
ARXIV_PATTERNS = [
    re.compile(r"arXiv:(\d{4}\.\d{4,})", re.IGNORECASE),
    re.compile(r"arxiv\.org/abs/(\d{4}\.\d{4,})"),
    re.compile(r"arxiv\.org/pdf/(\d{4}\.\d{4,})"),
]

DOI_PATTERNS = [
    re.compile(r"doi\.org/(10\.\d{4,}/[^\s)\"'>]+)"),
    re.compile(r"DOI:\s*(10\.\d{4,}/[^\s)\"'>]+)", re.IGNORECASE),
]

S2_URL_PATTERN = re.compile(r"semanticscholar\.org/paper/[^/]+/([0-9a-f]{40})")


class ReferenceExtractor:
    """Extracts academic paper references from Content markdown.

    Combines regex-based extraction with optional ingestion through
    ScholarContentIngestionService for the ``aca ingest scholar-refs`` workflow.
    """

    def __init__(self) -> None:
        self._scholar_service: ScholarContentIngestionService | None = None

    def extract_arxiv_ids(self, text: str) -> set[str]:
        ids: set[str] = set()
        for pattern in ARXIV_PATTERNS:
            for match in pattern.finditer(text):
                ids.add(match.group(1))
        return ids

    def extract_dois(self, text: str) -> set[str]:
        dois: set[str] = set()
        for pattern in DOI_PATTERNS:
            for match in pattern.finditer(text):
                # Clean trailing punctuation
                doi = match.group(1).rstrip(".,;:")
                dois.add(doi)
        return dois

    def extract_s2_ids(self, text: str) -> set[str]:
        return {m.group(1) for m in S2_URL_PATTERN.finditer(text)}

    def extract_all(self, text: str) -> dict[str, set[str]]:
        return {
            "arxiv": self.extract_arxiv_ids(text),
            "doi": self.extract_dois(text),
            "s2": self.extract_s2_ids(text),
        }

    def extract_from_contents(
        self,
        contents: list,  # list of Content model instances
        after: str | None = None,
        before: str | None = None,
    ) -> list[str]:
        """Extract unique identifiers from Content records.

        Returns list of identifiers in S2-compatible format:
        - ArXiv:YYMM.NNNNN for arXiv IDs
        - DOI:10.xxx/... for DOIs
        - Raw hex for S2 IDs
        """
        all_ids: set[str] = set()
        scanned = 0

        for content in contents:
            text = content.markdown_content or ""
            if not text:
                continue
            scanned += 1

            refs = self.extract_all(text)
            for arxiv_id in refs["arxiv"]:
                all_ids.add(f"ArXiv:{arxiv_id}")
            for doi in refs["doi"]:
                all_ids.add(f"DOI:{doi}")
            for s2_id in refs["s2"]:
                all_ids.add(s2_id)

        logger.info(
            "Scanned %d content records, found %d unique references",
            scanned,
            len(all_ids),
        )
        return sorted(all_ids)

    # ------------------------------------------------------------------
    # Ingestion workflow (used by orchestrator)
    # ------------------------------------------------------------------

    def _get_scholar_service(self) -> ScholarContentIngestionService:
        """Lazy-create the scholar ingestion service."""
        if self._scholar_service is None:
            from src.ingestion.scholar import ScholarContentIngestionService

            self._scholar_service = ScholarContentIngestionService()
        return self._scholar_service

    async def ingest_extracted_references(
        self,
        *,
        after: datetime | None = None,
        before: datetime | None = None,
        source_types: list[str] | None = None,
        dry_run: bool = False,
        limit: int | None = None,
    ) -> ReferenceExtractionResult:
        """Extract references from existing content and ingest them.

        Queries the database for Content records, extracts academic
        identifiers (arXiv, DOI, S2), then uses ScholarContentIngestionService
        to resolve and ingest each reference.

        Args:
            after: Only scan content created after this date.
            before: Only scan content created before this date.
            source_types: Filter content by source type names.
            dry_run: Report what would be ingested without persisting.
            limit: Maximum references to ingest.

        Returns:
            ReferenceExtractionResult with counts.
        """
        from sqlalchemy import text as sa_text

        from src.models.content import Content
        from src.storage.database import get_db

        result = ReferenceExtractionResult()

        # Query content records
        with get_db() as db:
            query = db.query(Content)

            if after:
                query = query.filter(Content.created_at >= after)
            if before:
                query = query.filter(Content.created_at <= before)
            if source_types:
                query = query.filter(
                    Content.source_type.cast(sa_text("text")).in_(source_types)
                )

            contents = query.all()

        # Extract identifiers
        identifiers = self.extract_from_contents(contents)
        result.content_scanned = len(contents)
        result.references_found = len(identifiers)

        if dry_run:
            logger.info(
                "Dry run: found %d references from %d content records",
                result.references_found,
                result.content_scanned,
            )
            return result

        if not identifiers:
            return result

        # Apply limit
        if limit and limit < len(identifiers):
            identifiers = identifiers[:limit]

        # Ingest each reference
        service = self._get_scholar_service()
        for identifier in identifiers:
            try:
                paper_result = await service.ingest_paper(identifier)
                if paper_result.ingested:
                    result.papers_ingested += 1
                    result.references_resolved += 1
                elif paper_result.already_exists:
                    result.papers_skipped_duplicate += 1
                    result.references_resolved += 1
                elif paper_result.error:
                    result.references_unresolved += 1
                else:
                    result.references_resolved += 1
            except Exception as e:
                result.references_unresolved += 1
                logger.warning("Failed to resolve reference %s: %s", identifier, e)

        logger.info(
            "Reference ingestion: scanned=%d, found=%d, ingested=%d, "
            "skipped_dup=%d, unresolved=%d",
            result.content_scanned,
            result.references_found,
            result.papers_ingested,
            result.papers_skipped_duplicate,
            result.references_unresolved,
        )
        return result

    async def close(self) -> None:
        """Close the underlying scholar service if created."""
        if self._scholar_service is not None:
            await self._scholar_service.close()
