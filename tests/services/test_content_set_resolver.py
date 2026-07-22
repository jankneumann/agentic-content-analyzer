"""Contract and invariant tests for canonical workflow content resolution."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from src.models.content import ContentSource, ContentStatus
from src.models.query import (
    ContentQuery,
    DateBasis,
    ResolvedContentSet,
    SelectionExclusionReason,
    SelectionPolicy,
)
from src.services.content_set_resolver import ContentSetResolver
from tests.factories.content import ContentFactory
from tests.factories.summary import SummaryFactory

START = datetime(2026, 7, 12, tzinfo=UTC)
END = START + timedelta(days=1)


def _summary_for(content, **overrides):
    return SummaryFactory(content=content, content_id=content.id, **overrides)


def _resolve(db_session, query: ContentQuery | None = None) -> ResolvedContentSet:
    return ContentSetResolver().resolve(query or ContentQuery(), session=db_session)


def test_content_query_exposes_workflow_contract_fields() -> None:
    query = ContentQuery()
    assert query.date_basis == DateBasis.PUBLISHED_DATE
    assert query.canonical_only is True
    assert query.require_summary is True

    assert ContentQuery(source_types=[]).source_types == []
    with pytest.raises(ValidationError, match="nonexistent_source"):
        ContentQuery(source_types=["nonexistent_source"])
    with pytest.raises(ValidationError, match="Valid fields"):
        ContentQuery(sort_by="nonexistent_field")
    with pytest.raises(ValidationError, match="greater than 0"):
        ContentQuery(limit=0)


def test_resolver_returns_one_canonical_item_and_reports_aliases(db_session) -> None:
    canonical = ContentFactory(
        source_type=ContentSource.RSS,
        published_date=START + timedelta(hours=1),
    )
    summary = _summary_for(canonical)
    alias = ContentFactory(
        source_type=ContentSource.GMAIL,
        canonical_id=canonical.id,
        published_date=START + timedelta(hours=2),
    )
    _summary_for(alias)

    resolved = _resolve(db_session, ContentQuery(start_date=START, end_date=END))

    assert resolved.content_ids == (canonical.id,)
    assert resolved.summary_ids == (summary.id,)
    assert resolved.eligible_content_count == 1
    assert resolved.eligible_summary_count == 1
    assert resolved.exclusion_counts == {SelectionExclusionReason.DUPLICATE_ALIAS: 1}
    duplicate = resolved.exclusions_by_reason[SelectionExclusionReason.DUPLICATE_ALIAS][0]
    assert duplicate.content_id == alias.id
    assert duplicate.canonical_content_id == canonical.id


def test_resolver_uses_latest_summary_with_id_as_tie_breaker(db_session) -> None:
    content = ContentFactory(published_date=START + timedelta(hours=1))
    older = _summary_for(content, created_at=START)
    same_time_first = _summary_for(content, created_at=START + timedelta(hours=1))
    same_time_latest = _summary_for(content, created_at=START + timedelta(hours=1))

    resolved = _resolve(db_session, ContentQuery(start_date=START, end_date=END))

    assert older.id < same_time_first.id < same_time_latest.id
    assert resolved.summary_ids == (same_time_latest.id,)


def test_missing_summary_and_non_workflow_statuses_have_structured_diagnostics(db_session) -> None:
    missing = ContentFactory(published_date=START + timedelta(hours=1))
    filtered = ContentFactory(
        status=ContentStatus.FILTERED_OUT,
        published_date=START + timedelta(hours=2),
    )
    failed = ContentFactory(
        status=ContentStatus.FAILED,
        published_date=START + timedelta(hours=3),
    )
    pending = ContentFactory(
        status=ContentStatus.PENDING,
        published_date=START + timedelta(hours=4),
    )
    for content in (filtered, failed, pending):
        _summary_for(content)

    resolved = _resolve(db_session, ContentQuery(start_date=START, end_date=END))

    assert resolved.content_ids == ()
    assert resolved.exclusion_counts == {
        SelectionExclusionReason.FAILED: 1,
        SelectionExclusionReason.FILTERED_OUT: 1,
        SelectionExclusionReason.MISSING_SUMMARY: 1,
        SelectionExclusionReason.UNSUPPORTED_STATUS: 1,
    }
    assert (
        resolved.exclusions_by_reason[SelectionExclusionReason.MISSING_SUMMARY][0].content_id
        == missing.id
    )


def test_published_period_is_half_open_and_excludes_null_dates(db_session) -> None:
    at_start = ContentFactory(published_date=START)
    before_end = ContentFactory(published_date=END - timedelta(microseconds=1))
    at_end = ContentFactory(published_date=END)
    null_date = ContentFactory(published_date=None, ingested_at=START + timedelta(hours=1))
    for content in (at_start, before_end, at_end, null_date):
        _summary_for(content)

    first_period = _resolve(db_session, ContentQuery(start_date=START, end_date=END))
    second_period = _resolve(
        db_session,
        ContentQuery(start_date=END, end_date=END + timedelta(days=1)),
    )

    assert set(first_period.content_ids) == {at_start.id, before_end.id}
    assert at_end.id not in first_period.content_ids
    assert at_end.id in second_period.content_ids
    outside = first_period.exclusions_by_reason[SelectionExclusionReason.OUTSIDE_PERIOD]
    assert {item.content_id for item in outside} == {at_end.id, null_date.id}


def test_ingested_date_basis_must_be_explicit_for_null_publication_date(db_session) -> None:
    content = ContentFactory(published_date=None, ingested_at=START + timedelta(hours=1))
    summary = _summary_for(content)

    published = _resolve(db_session, ContentQuery(start_date=START, end_date=END))
    ingested = _resolve(
        db_session,
        ContentQuery(
            start_date=START,
            end_date=END,
            date_basis=DateBasis.INGESTED_AT,
        ),
    )

    assert content.id not in published.content_ids
    assert ingested.content_ids == (content.id,)
    assert ingested.summary_ids == (summary.id,)
    assert ingested.policy.date_basis == DateBasis.INGESTED_AT


def test_filters_order_limit_and_empty_lists_are_normalized(db_session) -> None:
    first = ContentFactory(
        source_type=ContentSource.RSS,
        publication="AI Weekly",
        title="Agent systems",
        published_date=START + timedelta(hours=1),
    )
    second = ContentFactory(
        source_type=ContentSource.RSS,
        publication="AI Weekly",
        title="Agent evaluations",
        published_date=START + timedelta(hours=2),
    )
    ignored = ContentFactory(
        source_type=ContentSource.YOUTUBE,
        publication="Video Weekly",
        title="Agent video",
        published_date=START + timedelta(hours=3),
    )
    for content in (first, second, ignored):
        _summary_for(content)

    resolved = _resolve(
        db_session,
        ContentQuery(
            source_types=[ContentSource.RSS],
            statuses=[],
            publications=["AI Weekly"],
            publication_search="weekly",
            search="Agent",
            start_date=START,
            end_date=END,
            limit=1,
            sort_order="desc",
        ),
    )

    assert resolved.content_ids == (second.id,)
    assert resolved.policy.source_types == (ContentSource.RSS,)
    assert resolved.policy.statuses == (ContentStatus.COMPLETED,)
    assert ignored.id not in {exclusion.content_id for exclusion in resolved.exclusions}


def test_policy_normalization_deduplicates_filters_and_uses_actual_sort_basis(
    db_session,
) -> None:
    content = ContentFactory(
        source_type=ContentSource.RSS,
        published_date=None,
        ingested_at=START + timedelta(hours=1),
    )
    _summary_for(content)
    resolver = ContentSetResolver()

    duplicate_query = ContentQuery(
        source_types=[ContentSource.RSS, ContentSource.RSS],
        statuses=[ContentStatus.COMPLETED, ContentStatus.COMPLETED],
        date_basis=DateBasis.INGESTED_AT,
        sort_by="title",
    )
    canonical_query = ContentQuery(
        source_types=[ContentSource.RSS],
        statuses=[ContentStatus.COMPLETED],
        date_basis=DateBasis.INGESTED_AT,
        sort_by="ingested_at",
    )

    duplicate = resolver.resolve(duplicate_query, session=db_session)
    canonical = resolver.resolve(canonical_query, session=db_session)

    assert duplicate.policy == canonical.policy
    assert duplicate.policy.source_types == (ContentSource.RSS,)
    assert duplicate.policy.statuses == (ContentStatus.COMPLETED,)
    assert duplicate.policy.sort_by == "ingested_at"
    assert duplicate.fingerprint == canonical.fingerprint


def test_supplied_policy_is_canonicalized_or_rejected(db_session) -> None:
    resolver = ContentSetResolver()
    with pytest.raises(ValueError, match="schema_version=1"):
        resolver.resolve(SelectionPolicy(schema_version=2), session=db_session)
    with pytest.raises(ValueError, match="canonical_only"):
        resolver.resolve(SelectionPolicy(canonical_only=False), session=db_session)
    with pytest.raises(ValueError, match="require_summary"):
        resolver.resolve(SelectionPolicy(require_summary=False), session=db_session)

    resolved = resolver.resolve(
        SelectionPolicy(
            source_types=(ContentSource.RSS, ContentSource.RSS),
            statuses=(ContentStatus.COMPLETED, ContentStatus.COMPLETED),
            date_basis=DateBasis.INGESTED_AT,
            sort_by="title",
        ),
        session=db_session,
    )
    assert resolved.policy.source_types == (ContentSource.RSS,)
    assert resolved.policy.statuses == (ContentStatus.COMPLETED,)
    assert resolved.policy.sort_by == "ingested_at"


def test_resolver_projects_content_and_bounds_summary_lookup(db_session, monkeypatch) -> None:
    eligible = ContentFactory(published_date=START + timedelta(hours=1))
    outside = ContentFactory(published_date=END + timedelta(hours=1))
    failed = ContentFactory(
        status=ContentStatus.FAILED,
        published_date=START + timedelta(hours=2),
    )
    for content in (eligible, outside, failed):
        _summary_for(content)

    resolver = ContentSetResolver()
    policy = resolver.normalize(ContentQuery(start_date=START, end_date=END))
    statement = str(resolver._candidate_query(db_session, policy).statement)
    assert "markdown_content" not in statement
    assert "raw_content" not in statement

    looked_up_ids: list[int] = []
    original = resolver._latest_summaries

    def capture_summary_ids(session, content_ids):
        looked_up_ids.extend(content_ids)
        return original(session, content_ids)

    monkeypatch.setattr(resolver, "_latest_summaries", capture_summary_ids)
    resolved = resolver.resolve(policy, session=db_session)

    assert resolved.content_ids == (eligible.id,)
    assert looked_up_ids == [eligible.id]
    assert outside.id in {
        item.content_id
        for item in resolved.exclusions_by_reason[SelectionExclusionReason.OUTSIDE_PERIOD]
    }
    assert failed.id in {
        item.content_id for item in resolved.exclusions_by_reason[SelectionExclusionReason.FAILED]
    }


def test_preview_and_execution_share_fingerprint_until_summary_changes(db_session) -> None:
    content = ContentFactory(published_date=START + timedelta(hours=1))
    first_summary = _summary_for(content, created_at=START)
    query = ContentQuery(start_date=START, end_date=END)
    resolver = ContentSetResolver()

    preview = resolver.preview(query, session=db_session)
    execution = resolver.resolve(query, session=db_session)

    assert preview.fingerprint == execution.fingerprint
    assert execution.summary_ids == (first_summary.id,)
    assert len(execution.fingerprint) == 64

    latest_summary = _summary_for(content, created_at=START + timedelta(hours=1))
    changed = resolver.resolve(query, session=db_session)
    assert changed.summary_ids == (latest_summary.id,)
    assert changed.fingerprint != execution.fingerprint


def test_resolved_selection_models_are_immutable(db_session) -> None:
    content = ContentFactory(published_date=START + timedelta(hours=1))
    _summary_for(content)
    resolved = _resolve(db_session, ContentQuery(start_date=START, end_date=END))

    with pytest.raises(ValidationError, match="frozen"):
        resolved.fingerprint = "changed"
    with pytest.raises(ValidationError, match="frozen"):
        resolved.policy.limit = 2
