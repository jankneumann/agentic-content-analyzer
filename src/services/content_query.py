"""Content query service for building and executing content queries.

Translates ContentQuery models into SQLAlchemy queries, providing
preview (COUNT + GROUP BY) and resolve (matched IDs) operations.
Centralizes the filter logic used across content listing, summarization,
and digest generation.
"""

from sqlalchemy import func
from sqlalchemy.orm import Query, Session

from src.models.content import Content
from src.models.query import PREVIEW_SAMPLE_LIMIT, ContentQuery, ContentQueryPreview
from src.storage.database import get_db
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ContentQueryService:
    """Translates ContentQuery models into SQLAlchemy queries."""

    def apply_filters(self, q: Query, query: ContentQuery) -> Query:
        """Apply ContentQuery filter clauses to an existing query.

        Only applies WHERE conditions — does NOT apply sort or limit.
        Use this when you need custom column selection or pagination
        (e.g., the list_contents endpoint).

        Args:
            q: Existing SQLAlchemy Query to add filters to
            query: Content query filters

        Returns:
            Query with filter conditions applied
        """
        if query.source_types:
            q = q.filter(Content.source_type.in_(query.source_types))
        if query.statuses:
            q = q.filter(Content.status.in_(query.statuses))
        if query.publications:
            q = q.filter(Content.publication.in_(query.publications))
        if query.publication_search:
            q = q.filter(Content.publication.ilike(f"%{query.publication_search}%"))
        if query.start_date:
            q = q.filter(Content.published_date >= query.start_date)
        if query.end_date:
            q = q.filter(Content.published_date <= query.end_date)
        if query.search:
            q = q.filter(Content.title.ilike(f"%{query.search}%"))
        return q

    def build_query(self, db: Session, query: ContentQuery) -> Query:
        """Build SQLAlchemy query from ContentQuery filters with sort and limit.

        Empty lists are treated as None (no filter).

        Args:
            db: SQLAlchemy session
            query: Content query filters

        Returns:
            SQLAlchemy Query object (not yet executed)
        """
        q = self.apply_filters(db.query(Content), query)

        # Sort_by is already validated by Pydantic
        sort_col = getattr(Content, query.sort_by)
        q = q.order_by(sort_col.desc() if query.sort_order == "desc" else sort_col.asc())

        if query.limit:
            q = q.limit(query.limit)

        return q

    def preview(self, query: ContentQuery) -> ContentQueryPreview:
        """Preview what content matches without loading full records.

        Uses COUNT + GROUP BY for breakdown, separate query for sample titles.
        Returns total_count=0 with empty dicts/lists when no content matches.

        Args:
            query: Content query filters

        Returns:
            Preview with count, breakdowns, date range, and sample titles
        """
        with get_db() as db:
            # Build a base query without sort/limit for aggregation
            base_q = self.apply_filters(db.query(Content), query)

            if query.limit:
                # When limit is set, we need to apply it to the base query
                # so that breakdowns reflect the actual items that would be processed
                limited_ids_q = base_q.with_entities(Content.id)
                sort_col = getattr(Content, query.sort_by)
                limited_ids_q = limited_ids_q.order_by(
                    sort_col.desc() if query.sort_order == "desc" else sort_col.asc()
                )
                limited_ids_q = limited_ids_q.limit(query.limit)
                limited_ids = [row[0] for row in limited_ids_q.all()]

                if not limited_ids:
                    return ContentQueryPreview(
                        total_count=0,
                        by_source={},
                        by_status={},
                        date_range={"earliest": None, "latest": None},
                        sample_titles=[],
                        query=query,
                    )

                # Rebuild base_q to only include limited IDs
                base_q = db.query(Content).filter(Content.id.in_(limited_ids))

            # Total count
            total_count = base_q.count()

            if total_count == 0:
                return ContentQueryPreview(
                    total_count=0,
                    by_source={},
                    by_status={},
                    date_range={"earliest": None, "latest": None},
                    sample_titles=[],
                    query=query,
                )

            # Breakdown by source type
            source_counts = (
                base_q.with_entities(Content.source_type, func.count(Content.id))
                .group_by(Content.source_type)
                .all()
            )
            by_source = dict(sorted((src.value, cnt) for src, cnt in source_counts))

            # Breakdown by status
            status_counts = (
                base_q.with_entities(Content.status, func.count(Content.id))
                .group_by(Content.status)
                .all()
            )
            by_status = dict(sorted((st.value, cnt) for st, cnt in status_counts))

            # Date range
            date_stats = base_q.with_entities(
                func.min(Content.published_date),
                func.max(Content.published_date),
            ).one()

            earliest = date_stats[0].isoformat() if date_stats[0] else None
            latest = date_stats[1].isoformat() if date_stats[1] else None

            # Sample titles (most recent first, up to PREVIEW_SAMPLE_LIMIT)
            sample_q = (
                base_q.with_entities(Content.title)
                .order_by(Content.published_date.desc())
                .limit(PREVIEW_SAMPLE_LIMIT)
            )
            sample_titles = [row[0] for row in sample_q.all()]

            return ContentQueryPreview(
                total_count=total_count,
                by_source=by_source,
                by_status=by_status,
                date_range={"earliest": earliest, "latest": latest},
                sample_titles=sample_titles,
                query=query,
            )

    def resolve(self, query: ContentQuery) -> list[int]:
        """Resolve query to a list of content IDs.

        Returns all matching IDs (bounded by query.limit).
        IDs are returned in the sort order specified by the query.

        Args:
            query: Content query filters

        Returns:
            List of matching content IDs
        """
        with get_db() as db:
            q = self.build_query(db, query).with_entities(Content.id)
            return [row[0] for row in q.all()]
