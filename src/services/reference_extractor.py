"""Reference extraction service for identifying academic and web references in content.

Extracts arXiv IDs, DOIs, Semantic Scholar IDs, and classifiable URLs from
Content markdown and links_json. Provides chunk-anchored context snippets
and persistent storage via ContentReference model.

Migrated from ``src.ingestion.reference_extractor`` — that module now re-exports
from here for backward compatibility.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa

if TYPE_CHECKING:
    from src.ingestion.scholar import ScholarContentIngestionService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ReferenceExtractionResult:
    content_scanned: int = 0
    references_found: int = 0
    references_resolved: int = 0
    references_unresolved: int = 0
    papers_ingested: int = 0
    papers_skipped_duplicate: int = 0


@dataclass
class ExtractedReference:
    """A single reference extracted from content text or links."""

    external_id: str | None = None
    external_id_type: str | None = None  # ExternalIdType value
    external_url: str | None = None
    source_chunk_id: int | None = None
    context_snippet: str | None = None
    confidence: float = 1.0
    reference_type: str = "cites"  # ReferenceType value


# ---------------------------------------------------------------------------
# Unified pattern registry
# ---------------------------------------------------------------------------

REFERENCE_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "arxiv": [
        re.compile(r"arXiv:(\d{4}\.\d{4,}(?:v\d+)?)", re.IGNORECASE),
        re.compile(r"arxiv\.org/abs/(\d{4}\.\d{4,}(?:v\d+)?)"),
        re.compile(r"arxiv\.org/pdf/(\d{4}\.\d{4,}(?:v\d+)?)"),
    ],
    "doi": [
        re.compile(r'doi\.org/(10\.\d{4,}/[^\s)"\'>\]]+)'),
        re.compile(r'DOI:\s*(10\.\d{4,}/[^\s)"\'>\]]+)', re.IGNORECASE),
    ],
    "s2": [
        re.compile(r"semanticscholar\.org/paper/[^/]+/([0-9a-f]{40})"),
    ],
}

# Backward-compatible aliases for the old standalone constants
ARXIV_PATTERNS = REFERENCE_PATTERNS["arxiv"]
DOI_PATTERNS = REFERENCE_PATTERNS["doi"]
S2_URL_PATTERN = REFERENCE_PATTERNS["s2"][0]


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

_URL_TEMPLATES = {
    "arxiv": "https://arxiv.org/abs/{}",
    "doi": "https://doi.org/{}",
    "s2": "https://www.semanticscholar.org/paper/{}",
}


def normalize_id(id_type: str, raw_id: str) -> str:
    """Normalize a raw extracted identifier."""
    if id_type == "arxiv":
        return re.sub(r"v\d+$", "", raw_id)
    elif id_type == "doi":
        return raw_id.lower().rstrip(".,;:")
    return raw_id


def _build_url(id_type: str, raw_id: str) -> str | None:
    """Build a canonical URL from an identifier type and raw value."""
    template = _URL_TEMPLATES.get(id_type)
    return template.format(raw_id) if template else None


URL_CLASSIFIERS = [
    (re.compile(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,})"), "arxiv", "https://arxiv.org/abs/{}"),
    (re.compile(r"doi\.org/(10\.\d{4,}/[^\s]+)"), "doi", "https://doi.org/{}"),
    (
        re.compile(r"semanticscholar\.org/paper/[^/]+/([0-9a-f]{40})"),
        "s2",
        "https://www.semanticscholar.org/paper/{}",
    ),
]


def classify_url(url: str) -> ExtractedReference | None:
    """Classify a URL as a known academic reference, or return None."""
    for pattern, id_type, url_template in URL_CLASSIFIERS:
        m = pattern.search(url)
        if m:
            raw_id = m.group(1)
            return ExtractedReference(
                external_id=normalize_id(id_type, raw_id),
                external_id_type=id_type,
                external_url=url_template.format(raw_id),
                confidence=1.0,
            )
    return None


def extract_context(text: str, match: re.Match, window: int = 150) -> str:  # type: ignore[type-arg]
    """Return a snippet of *text* surrounding *match*."""
    start = max(0, match.start() - window)
    end = min(len(text), match.end() + window)
    return text[start:end].strip()


def _deduplicate_refs(refs: list[ExtractedReference]) -> list[ExtractedReference]:
    """Remove duplicate references based on (external_id, external_id_type, external_url)."""
    seen: set[tuple[str | None, str | None, str | None]] = set()
    unique: list[ExtractedReference] = []
    for ref in refs:
        key = (ref.external_id, ref.external_id_type, ref.external_url)
        if key not in seen:
            seen.add(key)
            unique.append(ref)
    return unique


# ---------------------------------------------------------------------------
# Main service class
# ---------------------------------------------------------------------------


class ReferenceExtractor:
    """Extracts academic paper references from Content markdown.

    Combines regex-based extraction with optional ingestion through
    ScholarContentIngestionService for the ``aca ingest scholar-refs`` workflow.
    """

    def __init__(self) -> None:
        self._scholar_service: ScholarContentIngestionService | None = None

    # ------------------------------------------------------------------
    # Legacy single-type extractors (kept for backward compatibility)
    # ------------------------------------------------------------------

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
    # Chunk-anchored extraction (new)
    # ------------------------------------------------------------------

    def _find_chunk_for_offset(self, chunks: list, offset: int) -> object | None:
        """Return the chunk containing *offset* using cumulative text length.

        *chunks* must be ordered by ``chunk_index``.  Each chunk is expected to
        have a ``text`` attribute (``DocumentChunk.text``).
        """
        cumulative = 0
        for chunk in chunks:
            chunk_text = getattr(chunk, "text", "") or ""
            chunk_len = len(chunk_text)
            if cumulative + chunk_len > offset:
                return chunk
            cumulative += chunk_len
        return None

    def extract_from_content(self, content: object, db: object) -> list[ExtractedReference]:
        """Extract references from a single Content record.

        Scans ``markdown_content`` for structured IDs and ``links_json``
        for classifiable URLs.  Returns an empty list when there is nothing
        to scan.

        Args:
            content: A ``Content`` model instance.
            db: A SQLAlchemy ``Session``.
        """
        refs: list[ExtractedReference] = []
        markdown = getattr(content, "markdown_content", None)
        if not markdown:
            return refs

        # Load chunks for anchoring (may be empty)
        from src.models.chunk import DocumentChunk

        chunks = (
            db.query(DocumentChunk)  # type: ignore[union-attr]
            .filter(DocumentChunk.content_id == content.id)  # type: ignore[union-attr]
            .order_by(DocumentChunk.chunk_index)
            .all()
        )

        # Scan text for structured IDs
        for id_type, patterns in REFERENCE_PATTERNS.items():
            for pattern in patterns:
                for match in pattern.finditer(markdown):
                    chunk = self._find_chunk_for_offset(chunks, match.start())
                    raw_id = match.group(1)
                    refs.append(
                        ExtractedReference(
                            external_id=normalize_id(id_type, raw_id),
                            external_id_type=id_type,
                            external_url=_build_url(id_type, raw_id),
                            source_chunk_id=chunk.id if chunk else None,  # type: ignore[union-attr]
                            context_snippet=(
                                extract_context(markdown, match) if not chunk else None
                            ),
                            confidence=1.0,
                        )
                    )

        # Classify URLs from links_json
        for url in getattr(content, "links_json", None) or []:
            classified = classify_url(url)
            if classified:
                refs.append(classified)
            else:
                refs.append(
                    ExtractedReference(
                        external_url=url,
                        confidence=0.5,
                    )
                )

        return _deduplicate_refs(refs)

    # ------------------------------------------------------------------
    # Persistent storage
    # ------------------------------------------------------------------

    def store_references(self, content_id: int, refs: list[ExtractedReference], db: object) -> int:
        """Persist extracted references using upsert-style conflict handling.

        Handles two conflict paths:
        - Named constraint ``uq_content_reference`` for refs with ``external_id``.
        - Partial index on ``(source_content_id, external_url)`` where
          ``external_id IS NULL`` for URL-only refs.

        Returns the number of newly stored rows.
        """
        from sqlalchemy.dialects.postgresql import insert

        from src.models.content_reference import ContentReference

        stored = 0
        for ref in refs:
            values = {
                "source_content_id": content_id,
                "external_id": ref.external_id,
                "external_id_type": ref.external_id_type,
                "external_url": ref.external_url,
                "source_chunk_id": ref.source_chunk_id,
                "context_snippet": ref.context_snippet,
                "confidence": ref.confidence,
                "reference_type": ref.reference_type or "cites",
            }
            stmt = insert(ContentReference).values(**values)
            if ref.external_id is not None:
                stmt = stmt.on_conflict_do_nothing(constraint="uq_content_reference")
            else:
                stmt = stmt.on_conflict_do_nothing(
                    index_elements=["source_content_id", "external_url"],
                    index_where=sa.text("external_id IS NULL"),
                )
            result = db.execute(stmt)  # type: ignore[union-attr]
            stored += result.rowcount  # type: ignore[union-attr]
        db.commit()  # type: ignore[union-attr]
        return stored

    # ------------------------------------------------------------------
    # Scholar ingestion workflow (existing)
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
                query = query.filter(Content.source_type.cast(sa_text("text")).in_(source_types))

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
            "Reference ingestion: scanned=%d, found=%d, ingested=%d, skipped_dup=%d, unresolved=%d",
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
