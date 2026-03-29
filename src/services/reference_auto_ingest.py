"""Auto-ingest trigger for unresolved structured references."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from src.models.content import Content

from src.models.content_reference import ContentReference, ExternalIdType

logger = logging.getLogger(__name__)


class AutoIngestTrigger:
    """Optionally ingest content for unresolved structured references.

    Only triggers for structured IDs (arXiv, DOI), not bare URLs.
    Depth tracking via metadata_json.auto_ingest_depth prevents recursion.
    """

    def __init__(self, db: Session, enabled: bool = False, max_depth: int = 1):
        self.db = db
        self.enabled = enabled
        self.max_depth = max_depth

    async def maybe_ingest(self, ref: ContentReference) -> Content | None:
        """Attempt to auto-ingest content for an unresolved reference.

        Returns the newly ingested Content or None.
        """
        if not self.enabled:
            return None

        # Only auto-ingest for structured IDs
        if not ref.external_id or not ref.external_id_type:
            return None

        # Check depth limit
        from src.models.content import Content

        source = self.db.get(Content, ref.source_content_id) if ref.source_content_id else None
        if not source:
            return None

        source_depth = (source.metadata_json or {}).get("auto_ingest_depth", 0)
        if source_depth >= self.max_depth:
            logger.debug(
                "Skipping auto-ingest for ref %s: depth %d >= max %d",
                ref.external_id,
                source_depth,
                self.max_depth,
            )
            return None

        new_depth = source_depth + 1

        try:
            if ref.external_id_type == ExternalIdType.DOI:
                return self._ingest_doi(ref.external_id, new_depth)
            elif ref.external_id_type == ExternalIdType.ARXIV:
                return self._ingest_arxiv(ref.external_id, new_depth)
            else:
                return None
        except Exception:
            logger.warning(
                "Auto-ingest failed for %s:%s",
                ref.external_id_type,
                ref.external_id,
                exc_info=True,
            )
            return None

    def _ingest_doi(self, doi: str, depth: int) -> Content | None:
        """Auto-ingest via Scholar for DOI references.

        Calls the synchronous orchestrator function which returns an int
        (number of papers ingested). Since the orchestrator manages its own
        DB session internally, we cannot directly get the Content object back.
        We query for the newly ingested content by DOI after ingestion.
        """
        try:
            from src.ingestion.orchestrator import ingest_scholar_paper

            count = ingest_scholar_paper(identifier=f"DOI:{doi}")
            if count > 0:
                return self._find_and_tag_by_doi(doi, depth)
            return None
        except Exception:
            logger.warning("DOI auto-ingest failed for %s", doi, exc_info=True)
            return None

    def _ingest_arxiv(self, arxiv_id: str, depth: int) -> Content | None:
        """Auto-ingest for arXiv references -- DEFERRED until add-arxiv-ingest lands."""
        logger.info(
            "arXiv auto-ingest not available (add-arxiv-ingest not implemented): %s",
            arxiv_id,
        )
        return None

    def _find_and_tag_by_doi(self, doi: str, depth: int) -> Content | None:
        """Find recently ingested content by DOI and tag with depth metadata."""
        from src.models.content import Content

        content = (
            self.db.query(Content)
            .filter(Content.source_id == f"DOI:{doi}")
            .order_by(Content.ingested_at.desc())
            .first()
        )
        if content:
            self._tag_auto_ingested(content, depth)
            return content
        logger.debug("Could not find ingested content for DOI:%s after auto-ingest", doi)
        return None

    def _tag_auto_ingested(self, content: Content, depth: int) -> None:
        """Tag auto-ingested content with depth tracking metadata."""
        meta = content.metadata_json or {}
        meta["ingestion_mode"] = "auto_ingest"
        meta["auto_ingest_depth"] = depth
        content.metadata_json = meta
