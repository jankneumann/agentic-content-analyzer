"""Shared bounded reference extraction and resolution workflows."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from src.models.content import Content
from src.models.content_reference import ContentReference, ResolutionStatus
from src.storage.database import get_db

REFERENCE_BATCH_TIMEOUT_S = 60.0


class ReferenceWorkflowService:
    """Own reference batch selection and execution for every adapter."""

    @staticmethod
    def _select_contents(
        db: Session,
        *,
        content_ids: list[int] | None,
        since: datetime | None,
        until: datetime | None,
        batch_size: int,
    ) -> list[Content]:
        if content_ids:
            return (
                db.query(Content)
                .filter(Content.id.in_(content_ids))
                .order_by(Content.ingested_at.asc(), Content.id.asc())
                .all()
            )

        query = db.query(Content)
        if since is not None:
            query = query.filter(Content.ingested_at >= since)
        if until is not None:
            query = query.filter(Content.ingested_at <= until)
        return (
            query.order_by(Content.ingested_at.asc(), Content.id.asc()).limit(batch_size + 1).all()
        )

    def extract(
        self,
        *,
        content_ids: list[int] | None,
        since: datetime | None,
        until: datetime | None,
        batch_size: int,
    ) -> dict[str, Any]:
        from src.services.reference_extractor import ReferenceExtractor

        extractor = ReferenceExtractor()
        with get_db() as db:
            selected = self._select_contents(
                db,
                content_ids=content_ids,
                since=since,
                until=until,
                batch_size=batch_size,
            )
            has_more = content_ids is None and len(selected) > batch_size
            next_cursor: datetime | None = None
            if has_more:
                overflow = selected[batch_size]
                selected = selected[:batch_size]
                next_cursor = overflow.ingested_at
                if next_cursor is not None and next_cursor.tzinfo is None:
                    next_cursor = next_cursor.replace(tzinfo=UTC)

            per_content: list[dict[str, int]] = []
            total_refs = 0
            for content in selected:
                if content.id is None:
                    raise RuntimeError("Persisted content is missing an ID")
                refs = extractor.extract_from_content(content, db)
                stored = extractor.store_references(content.id, refs, db) if refs else 0
                total_refs += stored
                per_content.append({"content_id": content.id, "references_found": stored})

        return {
            "references_extracted": total_refs,
            "content_processed": len(per_content),
            "has_more": has_more,
            "next_cursor": next_cursor,
            "per_content": per_content,
        }

    def resolve(self, *, batch_size: int) -> dict[str, Any]:
        from src.services.reference_resolver import ReferenceResolver

        with get_db() as db:
            resolved = ReferenceResolver(db).resolve_batch(batch_size=batch_size)
            remaining = (
                db.query(ContentReference)
                .filter(ContentReference.resolution_status == ResolutionStatus.UNRESOLVED)
                .count()
            )
        return {
            "resolved_count": int(resolved),
            "still_unresolved_count": int(remaining),
            "has_more": remaining > 0,
        }
