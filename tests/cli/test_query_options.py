"""Tests for CLI shared query options."""

from __future__ import annotations

import pytest
import typer

from src.cli.query_options import build_query_from_options
from src.models.content import ContentSource, ContentStatus


class TestBuildQueryFromOptionsSources:
    def test_valid_single_source(self):
        q = build_query_from_options(
            source="gmail", status=None, after=None, before=None, publication=None, search=None
        )
        assert q.source_types == [ContentSource.GMAIL]

    def test_valid_multiple_sources(self):
        q = build_query_from_options(
            source="gmail,rss,youtube",
            status=None,
            after=None,
            before=None,
            publication=None,
            search=None,
        )
        assert q.source_types == [ContentSource.GMAIL, ContentSource.RSS, ContentSource.YOUTUBE]

    def test_sources_with_whitespace(self):
        q = build_query_from_options(
            source="gmail , rss",
            status=None,
            after=None,
            before=None,
            publication=None,
            search=None,
        )
        assert q.source_types == [ContentSource.GMAIL, ContentSource.RSS]

    def test_invalid_source_raises_bad_parameter(self):
        with pytest.raises(typer.BadParameter, match="Invalid source"):
            build_query_from_options(
                source="invalid_source",
                status=None,
                after=None,
                before=None,
                publication=None,
                search=None,
            )

    def test_invalid_source_lists_valid_options(self):
        with pytest.raises(typer.BadParameter, match="Valid:"):
            build_query_from_options(
                source="notreal",
                status=None,
                after=None,
                before=None,
                publication=None,
                search=None,
            )

    def test_empty_source_string_raises(self):
        with pytest.raises(typer.BadParameter, match="Empty source"):
            build_query_from_options(
                source=",,,", status=None, after=None, before=None, publication=None, search=None
            )

    def test_none_source_no_filter(self):
        q = build_query_from_options(
            source=None, status=None, after=None, before=None, publication=None, search=None
        )
        assert q.source_types is None

    def test_trailing_comma_handled(self):
        q = build_query_from_options(
            source="gmail,", status=None, after=None, before=None, publication=None, search=None
        )
        assert q.source_types == [ContentSource.GMAIL]


class TestBuildQueryFromOptionsStatuses:
    def test_valid_single_status(self):
        q = build_query_from_options(
            source=None, status="pending", after=None, before=None, publication=None, search=None
        )
        assert q.statuses == [ContentStatus.PENDING]

    def test_valid_multiple_statuses(self):
        q = build_query_from_options(
            source=None,
            status="pending,completed",
            after=None,
            before=None,
            publication=None,
            search=None,
        )
        assert q.statuses == [ContentStatus.PENDING, ContentStatus.COMPLETED]

    def test_invalid_status_raises_bad_parameter(self):
        with pytest.raises(typer.BadParameter, match="Invalid status"):
            build_query_from_options(
                source=None,
                status="INVALID",
                after=None,
                before=None,
                publication=None,
                search=None,
            )

    def test_invalid_status_lists_valid_options(self):
        with pytest.raises(typer.BadParameter, match="Valid:"):
            build_query_from_options(
                source=None,
                status="BADSTATUS",
                after=None,
                before=None,
                publication=None,
                search=None,
            )

    def test_default_statuses_applied_when_no_status(self):
        q = build_query_from_options(
            source=None,
            status=None,
            after=None,
            before=None,
            publication=None,
            search=None,
            default_statuses=[ContentStatus.PENDING, ContentStatus.PARSED],
        )
        assert q.statuses == [ContentStatus.PENDING, ContentStatus.PARSED]

    def test_default_statuses_overridden_when_status_provided(self):
        q = build_query_from_options(
            source=None,
            status="completed",
            after=None,
            before=None,
            publication=None,
            search=None,
            default_statuses=[ContentStatus.PENDING, ContentStatus.PARSED],
        )
        assert q.statuses == [ContentStatus.COMPLETED]


class TestBuildQueryFromOptionsDates:
    def test_valid_after_date(self):
        q = build_query_from_options(
            source=None, status=None, after="2026-01-15", before=None, publication=None, search=None
        )
        assert q.start_date is not None
        assert q.start_date.year == 2026
        assert q.start_date.month == 1
        assert q.start_date.day == 15
        assert q.start_date.tzinfo is not None

    def test_valid_before_date(self):
        q = build_query_from_options(
            source=None, status=None, after=None, before="2026-02-28", publication=None, search=None
        )
        assert q.end_date is not None
        assert q.end_date.month == 2

    def test_before_date_is_end_of_day(self):
        """--before parses as end-of-day to include the full specified day."""
        q = build_query_from_options(
            source=None, status=None, after=None, before="2026-01-31", publication=None, search=None
        )
        assert q.end_date is not None
        assert q.end_date.hour == 23
        assert q.end_date.minute == 59
        assert q.end_date.second == 59
        assert q.end_date.microsecond == 999999

    def test_after_date_is_start_of_day(self):
        """--after parses as start-of-day (midnight)."""
        q = build_query_from_options(
            source=None, status=None, after="2026-01-15", before=None, publication=None, search=None
        )
        assert q.start_date is not None
        assert q.start_date.hour == 0
        assert q.start_date.minute == 0
        assert q.start_date.second == 0

    def test_invalid_after_date_format(self):
        with pytest.raises(typer.BadParameter, match="Invalid date format"):
            build_query_from_options(
                source=None,
                status=None,
                after="01-15-2026",
                before=None,
                publication=None,
                search=None,
            )

    def test_invalid_before_date_format(self):
        with pytest.raises(typer.BadParameter, match="YYYY-MM-DD"):
            build_query_from_options(
                source=None,
                status=None,
                after=None,
                before="not-a-date",
                publication=None,
                search=None,
            )

    def test_none_dates_no_filter(self):
        q = build_query_from_options(
            source=None, status=None, after=None, before=None, publication=None, search=None
        )
        assert q.start_date is None
        assert q.end_date is None


class TestBuildQueryFromOptionsOther:
    def test_publication_passed_as_publication_search(self):
        q = build_query_from_options(
            source=None, status=None, after=None, before=None, publication="The Batch", search=None
        )
        assert q.publication_search == "The Batch"

    def test_search_passed_as_search(self):
        q = build_query_from_options(
            source=None,
            status=None,
            after=None,
            before=None,
            publication=None,
            search="transformer",
        )
        assert q.search == "transformer"

    def test_limit_passed_through(self):
        q = build_query_from_options(
            source=None,
            status=None,
            after=None,
            before=None,
            publication=None,
            search=None,
            limit=10,
        )
        assert q.limit == 10

    def test_combined_options(self):
        q = build_query_from_options(
            source="gmail,rss",
            status="pending",
            after="2026-01-01",
            before="2026-02-01",
            publication="DeepLearning",
            search="GPT",
            limit=5,
        )
        assert q.source_types == [ContentSource.GMAIL, ContentSource.RSS]
        assert q.statuses == [ContentStatus.PENDING]
        assert q.start_date is not None
        assert q.end_date is not None
        assert q.publication_search == "DeepLearning"
        assert q.search == "GPT"
        assert q.limit == 5

    def test_no_options_returns_empty_query(self):
        q = build_query_from_options(
            source=None, status=None, after=None, before=None, publication=None, search=None
        )
        assert q.source_types is None
        assert q.statuses is None
        assert q.start_date is None
        assert q.end_date is None
        assert q.publication_search is None
        assert q.search is None
        assert q.limit is None
