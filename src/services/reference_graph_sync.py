"""One-way sync: PostgreSQL → Neo4j citation edges."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from src.models.content_reference import ContentReference, ResolutionStatus

logger = logging.getLogger(__name__)


class ReferenceGraphSync:
    """Sync resolved references to Neo4j as CITES edges.

    Reuses the existing GraphitiClient.driver for raw Cypher queries.
    All operations are fire-and-forget: errors are logged, never raised.
    """

    def __init__(self, driver=None):  # type: ignore[no-untyped-def]
        """Initialize with a Neo4j driver instance.

        Args:
            driver: neo4j async driver instance (from GraphitiClient.driver)
        """
        self.driver = driver

    async def sync_reference(self, ref: ContentReference) -> None:
        """Create/update CITES edge when reference is resolved."""
        if ref.resolution_status != ResolutionStatus.RESOLVED:
            return
        if not ref.target_content_id:
            return
        if not self.driver:
            logger.debug("Neo4j driver not available, skipping citation sync")
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
        """Sync all resolved refs for a content item to Neo4j."""
        if not self.driver:
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
        """Find Episode UUID in Neo4j matching a content_id."""
        try:
            query = """
            MATCH (e:Episode)
            WHERE e.source_id = $content_id OR e.content_id = $content_id
            RETURN e.uuid AS uuid
            LIMIT 1
            """
            async with self.driver.session() as session:
                result = await session.run(query, content_id=str(content_id))
                record = await result.single()
                return record["uuid"] if record else None
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
        """MERGE citation edge in Neo4j."""
        query = """
        MATCH (s:Episode {uuid: $source_uuid})
        MATCH (t:Episode {uuid: $target_uuid})
        MERGE (s)-[r:CITES]->(t)
        SET r.reference_type = $reference_type,
            r.confidence = $confidence,
            r.synced_at = datetime()
        """
        async with self.driver.session() as session:
            await session.run(
                query,
                source_uuid=source_uuid,
                target_uuid=target_uuid,
                reference_type=reference_type,
                confidence=confidence,
            )
