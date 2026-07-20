"""Canonical, summary-backed content selection for durable workflows."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Query, Session, load_only

from src.models.content import Content, ContentStatus
from src.models.query import (
    SELECTION_SCHEMA_VERSION,
    ContentQuery,
    ResolvedContentItem,
    ResolvedContentSet,
    SelectionExclusion,
    SelectionExclusionReason,
    SelectionPolicy,
    compute_selection_fingerprint,
)
from src.models.summary import Summary
from src.storage.database import get_db

_CANDIDATE_BATCH_SIZE = 1000
_SUMMARY_LOOKUP_BATCH_SIZE = 1000


class ContentSetResolver:
    """Resolve a query once into an immutable value for downstream workflows."""

    def normalize(self, query: ContentQuery | None = None) -> SelectionPolicy:
        """Apply workflow defaults and normalize set-like filters."""

        query = query or ContentQuery()
        requested_statuses = set(query.statuses or [ContentStatus.COMPLETED])
        statuses = (
            (ContentStatus.COMPLETED,) if ContentStatus.COMPLETED in requested_statuses else ()
        )
        source_types = tuple(sorted(set(query.source_types or []), key=str))
        publications = tuple(sorted(set(query.publications or [])))
        policy = SelectionPolicy(
            source_types=source_types,
            statuses=statuses,
            publications=publications,
            publication_search=query.publication_search,
            start_date=self._normalize_policy_datetime(query.start_date),
            end_date=self._normalize_policy_datetime(query.end_date),
            date_basis=query.date_basis,
            search=query.search,
            limit=query.limit,
            sort_by=query.date_basis.value,
            sort_order=query.sort_order,
            # Theme, digest, and podcast selection never admits aliases or missing summaries.
            canonical_only=True,
            require_summary=True,
        )
        return self._canonicalize_policy(policy)

    def preview(
        self,
        query_or_session: ContentQuery | SelectionPolicy | Session | None = None,
        query: ContentQuery | SelectionPolicy | None = None,
        *,
        session: Session | None = None,
    ) -> ResolvedContentSet:
        """Preview with the exact same resolver used by execution."""

        return self.resolve(query_or_session, query, session=session)

    def resolve(
        self,
        query_or_session: ContentQuery | SelectionPolicy | Session | None = None,
        query: ContentQuery | SelectionPolicy | None = None,
        *,
        session: Session | None = None,
    ) -> ResolvedContentSet:
        """Return the immutable canonical content and summary selection."""

        actual_query: ContentQuery | SelectionPolicy | None
        if isinstance(query_or_session, Session):
            if session is not None:
                raise TypeError("session was supplied both positionally and by keyword")
            session = query_or_session
            actual_query = query
        else:
            if query is not None:
                raise TypeError("query was supplied twice")
            actual_query = query_or_session

        requested_policy = (
            actual_query
            if isinstance(actual_query, SelectionPolicy)
            else self.normalize(actual_query)
        )
        policy = self._canonicalize_policy(requested_policy)
        with self._session(session) as db:
            return self._resolve(db, policy)

    def _canonicalize_policy(self, policy: SelectionPolicy) -> SelectionPolicy:
        """Return the precise policy enforced by this summary-backed resolver."""

        if policy.schema_version != SELECTION_SCHEMA_VERSION:
            raise ValueError(
                f"ContentSetResolver supports only schema_version={SELECTION_SCHEMA_VERSION}"
            )
        if not policy.canonical_only:
            raise ValueError("ContentSetResolver requires canonical_only=true")
        if not policy.require_summary:
            raise ValueError("ContentSetResolver requires require_summary=true")

        requested_statuses = set(policy.statuses)
        statuses = (
            (ContentStatus.COMPLETED,) if ContentStatus.COMPLETED in requested_statuses else ()
        )
        return policy.model_copy(
            update={
                "source_types": tuple(sorted(set(policy.source_types), key=str)),
                "statuses": statuses,
                "publications": tuple(sorted(set(policy.publications))),
                "start_date": self._normalize_policy_datetime(policy.start_date),
                "end_date": self._normalize_policy_datetime(policy.end_date),
                "sort_by": policy.date_basis.value,
                "canonical_only": True,
                "require_summary": True,
            }
        )

    @contextmanager
    def _session(self, session: Session | None) -> Iterator[Session]:
        if session is not None:
            yield session
            return
        with get_db() as db:
            yield db

    def _resolve(self, db: Session, policy: SelectionPolicy) -> ResolvedContentSet:
        eligible_candidates: list[Content] = []
        exclusions: list[SelectionExclusion] = []

        for content in self._candidate_query(db, policy).yield_per(_CANDIDATE_BATCH_SIZE):
            reason = self._cheap_exclusion_reason(content, policy)
            if reason is not None:
                exclusions.append(
                    SelectionExclusion(
                        content_id=content.id,
                        canonical_content_id=content.canonical_id,
                        reason=reason,
                    )
                )
                continue
            eligible_candidates.append(content)

        summaries = self._latest_summaries(db, [content.id for content in eligible_candidates])
        items: list[ResolvedContentItem] = []
        for content in eligible_candidates:
            if content.id not in summaries:
                exclusions.append(
                    SelectionExclusion(
                        content_id=content.id,
                        reason=SelectionExclusionReason.MISSING_SUMMARY,
                    )
                )
                continue
            summary = summaries[content.id]
            selection_date = getattr(content, policy.date_basis.value)
            items.append(
                ResolvedContentItem(
                    content_id=content.id,
                    summary_id=summary.id,
                    source_type=content.source_type,
                    title=content.title,
                    publication=content.publication,
                    selection_date=selection_date,
                )
            )

        items.sort(key=lambda item: self._item_sort_key(item, policy))
        if policy.sort_order == "desc":
            items.reverse()
        if policy.limit is not None:
            items = items[: policy.limit]

        resolved_items = tuple(items)
        fingerprint = compute_selection_fingerprint(
            policy,
            [item.content_id for item in resolved_items],
            [item.summary_id for item in resolved_items],
        )
        return ResolvedContentSet(
            policy=policy,
            items=resolved_items,
            exclusions=tuple(sorted(exclusions, key=lambda item: (item.reason, item.content_id))),
            fingerprint=fingerprint,
        )

    def _candidate_query(self, db: Session, policy: SelectionPolicy) -> Query:
        query = db.query(Content).options(
            load_only(
                Content.id,
                Content.source_type,
                Content.title,
                Content.publication,
                Content.published_date,
                Content.canonical_id,
                Content.status,
                Content.ingested_at,
            )
        )
        if policy.source_types:
            query = query.filter(Content.source_type.in_(policy.source_types))
        if policy.publications:
            query = query.filter(Content.publication.in_(policy.publications))
        if policy.publication_search:
            query = query.filter(Content.publication.ilike(f"%{policy.publication_search}%"))
        if policy.search:
            query = query.filter(Content.title.ilike(f"%{policy.search}%"))
        return query.order_by(Content.id.asc())

    def _latest_summaries(self, db: Session, content_ids: list[int]) -> dict[int, Summary]:
        if not content_ids:
            return {}
        latest: dict[int, Summary] = {}
        for offset in range(0, len(content_ids), _SUMMARY_LOOKUP_BATCH_SIZE):
            batch = content_ids[offset : offset + _SUMMARY_LOOKUP_BATCH_SIZE]
            ordered = (
                db.query(Summary)
                .filter(Summary.content_id.in_(batch))
                .order_by(Summary.content_id.asc(), Summary.created_at.desc(), Summary.id.desc())
                .all()
            )
            for summary in ordered:
                latest.setdefault(summary.content_id, summary)
        return latest

    def _cheap_exclusion_reason(
        self,
        content: Content,
        policy: SelectionPolicy,
    ) -> SelectionExclusionReason | None:
        if content.canonical_id is not None:
            return SelectionExclusionReason.DUPLICATE_ALIAS
        if not self._inside_period(content, policy):
            return SelectionExclusionReason.OUTSIDE_PERIOD
        if content.status == ContentStatus.FILTERED_OUT:
            return SelectionExclusionReason.FILTERED_OUT
        if content.status == ContentStatus.FAILED:
            return SelectionExclusionReason.FAILED
        if content.status != ContentStatus.COMPLETED or content.status not in policy.statuses:
            return SelectionExclusionReason.UNSUPPORTED_STATUS
        return None

    def _inside_period(self, content: Content, policy: SelectionPolicy) -> bool:
        value = getattr(content, policy.date_basis.value)
        if value is None:
            return False
        comparable = self._comparable_datetime(value)
        if policy.start_date is not None and comparable < self._comparable_datetime(
            policy.start_date
        ):
            return False
        return not (
            policy.end_date is not None and comparable >= self._comparable_datetime(policy.end_date)
        )

    def _item_sort_key(self, item: ResolvedContentItem, policy: SelectionPolicy) -> tuple[Any, int]:
        # Workflow ordering is always date-stable, with ID resolving equal timestamps.
        return self._comparable_datetime(item.selection_date), item.content_id

    @staticmethod
    def _comparable_datetime(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value
        return value.astimezone(UTC).replace(tzinfo=None)

    @staticmethod
    def _normalize_policy_datetime(value: datetime | None) -> datetime | None:
        if value is None or value.tzinfo is None:
            return value
        return value.astimezone(UTC)
