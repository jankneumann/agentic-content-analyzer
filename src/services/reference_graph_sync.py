"""One-way sync: PostgreSQL → graph database citation edges."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from src.storage.graph_provider import GraphDBProvider

from src.models.content_reference import ContentReference, ResolutionStatus

logger = logging.getLogger(__name__)


class ReferenceGraphSync:
    """Sync resolved references to graph database as CITES edges.

    Uses GraphDBProvider for backend-agnostic raw Cypher queries.
    All operations are fire-and-forget: errors are logged, never raised.
    """

    def __init__(self, provider: GraphDBProvider | None = None) -> None:
        """Initialize with a graph database provider.

        Args:
            provider: Graph database provider for executing Cypher queries.
                      If None, all sync operations are silently skipped.
        """
        self.provider = provider

    async def sync_reference(self, ref: ContentReference) -> None:
        """Create/update CITES edge when reference is resolved."""
        if ref.resolution_status != ResolutionStatus.RESOLVED:
            return
        if not ref.target_content_id:
            return
        if not self.provider:
            logger.debug("Graph provider not available, skipping citation sync")
            return

        try:
            source_uuid = await self._find_episode_uuid(ref.source_content_id)
            target_uuid = await self._find_episode_uuid(ref.target_content_id)

            if not source_uuid or not target_uuid:
                logger.debug(
                    "Episode not found for content_id %s or %s, skipping sync",
                    ref.source_content_id,
                    ref.target_content_id,
                )
                return

            await self._create_citation_edge(
                source_uuid=source_uuid,
                target_uuid=target_uuid,
                reference_type=ref.reference_type,
                confidence=ref.confidence,
            )
        except Exception:
            logger.warning(
                "Failed to sync citation edge for reference %s",
                ref.id,
                exc_info=True,
            )

    async def sync_resolved_for_content(self, content_id: int, db: Session | None = None) -> int:
        """Sync all resolved refs for a content item to graph database."""
        if not self.provider:
            return 0
        if not db:
            return 0

        try:
            refs = (
                db.query(ContentReference)
                .filter(
                    ContentReference.source_content_id == content_id,
                    ContentReference.resolution_status == ResolutionStatus.RESOLVED,
                )
                .all()
            )

            synced = 0
            for ref in refs:
                await self.sync_reference(ref)
                synced += 1
            return synced
        except Exception:
            logger.warning(
                "Failed to sync references for content %s",
                content_id,
                exc_info=True,
            )
            return 0

    async def _find_episode_uuid(self, content_id: int) -> str | None:
        """Find Episode UUID in graph matching a content_id."""
        try:
            records = await self.provider.execute_query(  # type: ignore[union-attr]
                """
                MATCH (e:Episode)
                WHERE e.source_id = $content_id OR e.content_id = $content_id
                RETURN e.uuid AS uuid
                LIMIT 1
                """,
                {"content_id": str(content_id)},
            )
            return records[0]["uuid"] if records else None
        except Exception:
            logger.warning("Failed to find episode for content_id %s", content_id)
            return None

    async def _create_citation_edge(
        self,
        source_uuid: str,
        target_uuid: str,
        reference_type: str,
        confidence: float,
    ) -> None:
        """MERGE citation edge in graph database."""
        await self.provider.execute_write(  # type: ignore[union-attr]
            """
            MATCH (s:Episode {uuid: $source_uuid})
            MATCH (t:Episode {uuid: $target_uuid})
            MERGE (s)-[r:CITES]->(t)
            SET r.reference_type = $reference_type,
                r.confidence = $confidence,
                r.synced_at = datetime()
            """,
            {
                "source_uuid": source_uuid,
                "target_uuid": target_uuid,
                "reference_type": reference_type,
                "confidence": confidence,
            },
        )
