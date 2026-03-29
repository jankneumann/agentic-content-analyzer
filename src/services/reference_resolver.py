"""Content reference resolution service.

Resolves unresolved ContentReference records by matching external identifiers
(arXiv ID, DOI, S2 paper ID) and URLs against existing Content records.

Supports three resolution modes:
- Forward resolution: resolve refs for a specific content item or in batch
- Reverse resolution: when new content arrives, find refs that point to it
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from src.models.content import Content
from src.models.content_reference import (
    ContentReference,
    ExternalIdType,
    ResolutionStatus,
)

logger = logging.getLogger(__name__)


class ReferenceResolver:
    """Resolves unresolved content_references against the database."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def resolve_reference(self, ref: ContentReference) -> str:
        """Attempt to resolve a single reference to a Content record.

        Tries structured ID lookup first (GIN-indexed), then URL match.
        Returns the resolution status string.
        """
        # 1. Try structured ID lookup via GIN index
        if ref.external_id and ref.external_id_type:
            target = self._find_by_external_id(ref.external_id, ref.external_id_type)
            if target:
                ref.target_content_id = target.id
                ref.resolution_status = ResolutionStatus.RESOLVED
                ref.resolved_at = datetime.now(UTC)
                return ResolutionStatus.RESOLVED

        # 2. Try URL match against source_url
        if ref.external_url:
            target = self._find_by_source_url(ref.external_url)
            if target:
                ref.target_content_id = target.id
                ref.resolution_status = ResolutionStatus.RESOLVED
                ref.resolved_at = datetime.now(UTC)
                return ResolutionStatus.RESOLVED

        # 3. Not found
        return ResolutionStatus.UNRESOLVED

    def _find_by_external_id(self, ext_id: str, id_type: str) -> Content | None:
        """GIN-indexed lookup in metadata_json.

        CRITICAL: Use sa.cast({...}, JSONB) not :param::jsonb — psycopg2
        misparsing of double-colon silently breaks queries.
        """
        key_map: dict[str, str] = {
            ExternalIdType.ARXIV: "arxiv_id",
            ExternalIdType.DOI: "doi",
            ExternalIdType.S2: "s2_paper_id",
        }
        json_key = key_map.get(id_type)
        if not json_key:
            return None

        # Use sa.cast() which generates CAST(... AS jsonb) not ::jsonb
        return (
            self.db.query(Content)
            .filter(Content.metadata_json.op("@>")(sa.cast({json_key: ext_id}, JSONB)))
            .first()
        )

    def _find_by_source_url(self, url: str) -> Content | None:
        """Match against contents.source_url."""
        return self.db.query(Content).filter(Content.source_url == url).first()

    def resolve_for_content(self, content_id: int) -> int:
        """Resolve all unresolved refs for a specific content item.

        Args:
            content_id: The source content ID whose refs to resolve.

        Returns:
            Number of references successfully resolved.
        """
        refs = (
            self.db.query(ContentReference)
            .filter(
                ContentReference.source_content_id == content_id,
                ContentReference.resolution_status == ResolutionStatus.UNRESOLVED,
            )
            .all()
        )

        resolved = 0
        for ref in refs:
            status = self.resolve_reference(ref)
            if status == ResolutionStatus.RESOLVED:
                resolved += 1

        self.db.commit()
        return resolved

    def resolve_batch(self, batch_size: int = 100) -> int:
        """Resolve oldest unresolved refs in batch.

        Args:
            batch_size: Maximum number of references to process.

        Returns:
            Number of references successfully resolved.
        """
        refs = (
            self.db.query(ContentReference)
            .filter(
                ContentReference.resolution_status == ResolutionStatus.UNRESOLVED,
            )
            .order_by(ContentReference.created_at)
            .limit(batch_size)
            .all()
        )

        resolved = 0
        for ref in refs:
            status = self.resolve_reference(ref)
            if status == ResolutionStatus.RESOLVED:
                resolved += 1

        self.db.commit()
        return resolved

    def resolve_incoming(self, new_content: Content) -> int:
        """Reverse resolution: find unresolved refs matching new content.

        When new content is ingested, check if any existing unresolved
        references point to it (by arXiv ID, DOI, or source URL).

        Args:
            new_content: The newly ingested Content record.

        Returns:
            Number of references resolved to this content.
        """
        resolved = 0

        # Check by arXiv ID
        arxiv_id = (new_content.metadata_json or {}).get("arxiv_id")
        if arxiv_id:
            resolved += self._resolve_matching_refs(ExternalIdType.ARXIV, arxiv_id, new_content.id)

        # Check by DOI
        doi = (new_content.metadata_json or {}).get("doi")
        if doi:
            resolved += self._resolve_matching_refs(ExternalIdType.DOI, doi, new_content.id)

        # Check by S2 paper ID
        s2_id = (new_content.metadata_json or {}).get("s2_paper_id")
        if s2_id:
            resolved += self._resolve_matching_refs(ExternalIdType.S2, s2_id, new_content.id)

        # Check by source_url
        if new_content.source_url:
            resolved += self._resolve_matching_refs_by_url(new_content.source_url, new_content.id)

        if resolved > 0:
            self.db.commit()

        return resolved

    def _resolve_matching_refs(self, id_type: str, ext_id: str, target_id: int) -> int:
        """Resolve unresolved refs matching an external ID.

        Args:
            id_type: The external ID type to match.
            ext_id: The external ID value to match.
            target_id: The content ID to set as target.

        Returns:
            Number of references resolved.
        """
        refs = (
            self.db.query(ContentReference)
            .filter(
                ContentReference.external_id_type == id_type,
                ContentReference.external_id == ext_id,
                ContentReference.resolution_status == ResolutionStatus.UNRESOLVED,
            )
            .all()
        )

        count = 0
        for ref in refs:
            ref.target_content_id = target_id
            ref.resolution_status = ResolutionStatus.RESOLVED
            ref.resolved_at = datetime.now(UTC)
            count += 1
        return count

    def _resolve_matching_refs_by_url(self, url: str, target_id: int) -> int:
        """Resolve unresolved refs matching a URL.

        Args:
            url: The URL to match against external_url.
            target_id: The content ID to set as target.

        Returns:
            Number of references resolved.
        """
        refs = (
            self.db.query(ContentReference)
            .filter(
                ContentReference.external_url == url,
                ContentReference.resolution_status == ResolutionStatus.UNRESOLVED,
            )
            .all()
        )

        count = 0
        for ref in refs:
            ref.target_content_id = target_id
            ref.resolution_status = ResolutionStatus.RESOLVED
            ref.resolved_at = datetime.now(UTC)
            count += 1
        return count
