"""Tests for ContentQueryService and ContentQuery model.

Tests each filter dimension independently, filter combinations,
edge cases, preview, and resolve operations.
"""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from src.models.content import ContentSource, ContentStatus
from src.models.query import CONTENT_SORT_FIELDS, PREVIEW_SAMPLE_LIMIT, ContentQuery
from src.services.content_query import ContentQueryService
from tests.factories.content import ContentFactory

# =============================================================================
# ContentQuery Model Validation
# =============================================================================


class TestContentQueryModel:
    """Tests for ContentQuery Pydantic model validation."""

    def test_empty_query_valid(self):
        """Empty query (no filters) is valid — matches all content."""
        q = ContentQuery()
        assert q.source_types is None
        assert q.statuses is None
        assert q.sort_by == "published_date"
        assert q.sort_order == "desc"

    def test_valid_source_types(self):
        q = ContentQuery(source_types=[ContentSource.YOUTUBE, ContentSource.RSS])
        assert len(q.source_types) == 2

    def test_valid_statuses(self):
        q = ContentQuery(statuses=[ContentStatus.PENDING, ContentStatus.PARSED])
        assert len(q.statuses) == 2

    def test_invalid_sort_by_raises(self):
        with pytest.raises(ValidationError, match="Invalid sort_by"):
            ContentQuery(sort_by="nonexistent_field")

    def test_valid_sort_by_fields(self):
        for field in CONTENT_SORT_FIELDS:
            q = ContentQuery(sort_by=field)
            assert q.sort_by == field

    def test_invalid_sort_order_raises(self):
        with pytest.raises(ValidationError, match="String should match pattern"):
            ContentQuery(sort_order="random")

    def test_sort_order_asc(self):
        q = ContentQuery(sort_order="asc")
        assert q.sort_order == "asc"

    def test_limit_must_be_positive(self):
        with pytest.raises(ValidationError, match="greater than 0"):
            ContentQuery(limit=0)

    def test_limit_negative_raises(self):
        with pytest.raises(ValidationError, match="greater than 0"):
            ContentQuery(limit=-1)

    def test_limit_positive_valid(self):
        q = ContentQuery(limit=50)
        assert q.limit == 50

    def test_full_query(self):
        """All fields populated."""
        q = ContentQuery(
            source_types=[ContentSource.RSS],
            statuses=[ContentStatus.COMPLETED],
            publications=["The Batch"],
            publication_search="batch",
            start_date=datetime(2026, 1, 1, tzinfo=UTC),
            end_date=datetime(2026, 2, 1, tzinfo=UTC),
            search="AI",
            limit=10,
            sort_by="title",
            sort_order="asc",
        )
        assert q.source_types == [ContentSource.RSS]
        assert q.publications == ["The Batch"]
        assert q.limit == 10


# =============================================================================
# ContentQueryService — Filter Dimensions
# =============================================================================


class TestContentQueryServiceFilters:
    """Tests for individual filter dimensions using the database."""

    def test_no_filters_matches_all(self, db_session):
        """Empty query matches all content."""
        ContentFactory.create_batch(3)
        db_session.flush()

        svc = ContentQueryService()
        q = ContentQuery()
        results = svc.build_query(db_session, q).all()
        assert len(results) == 3

    def test_filter_by_source_type(self, db_session):
        ContentFactory.create(source_type=ContentSource.YOUTUBE)
        ContentFactory.create(source_type=ContentSource.RSS)
        ContentFactory.create(source_type=ContentSource.GMAIL)
        db_session.flush()

        svc = ContentQueryService()
        q = ContentQuery(source_types=[ContentSource.YOUTUBE])
        results = svc.build_query(db_session, q).all()
        assert len(results) == 1
        assert results[0].source_type == ContentSource.YOUTUBE

    def test_filter_by_multiple_source_types(self, db_session):
        ContentFactory.create(source_type=ContentSource.YOUTUBE)
        ContentFactory.create(source_type=ContentSource.RSS)
        ContentFactory.create(source_type=ContentSource.GMAIL)
        db_session.flush()

        svc = ContentQueryService()
        q = ContentQuery(source_types=[ContentSource.YOUTUBE, ContentSource.RSS])
        results = svc.build_query(db_session, q).all()
        assert len(results) == 2

    def test_filter_by_status(self, db_session):
        ContentFactory.create(status=ContentStatus.PENDING)
        ContentFactory.create(status=ContentStatus.COMPLETED)
        ContentFactory.create(status=ContentStatus.FAILED)
        db_session.flush()

        svc = ContentQueryService()
        q = ContentQuery(statuses=[ContentStatus.PENDING])
        results = svc.build_query(db_session, q).all()
        assert len(results) == 1
        assert results[0].status == ContentStatus.PENDING

    def test_filter_by_multiple_statuses(self, db_session):
        ContentFactory.create(status=ContentStatus.PENDING)
        ContentFactory.create(status=ContentStatus.PARSED)
        ContentFactory.create(status=ContentStatus.COMPLETED)
        db_session.flush()

        svc = ContentQueryService()
        q = ContentQuery(statuses=[ContentStatus.PENDING, ContentStatus.PARSED])
        results = svc.build_query(db_session, q).all()
        assert len(results) == 2

    def test_filter_by_publications_exact(self, db_session):
        ContentFactory.create(publication="The Batch")
        ContentFactory.create(publication="AI Weekly")
        ContentFactory.create(publication="Tech Daily")
        db_session.flush()

        svc = ContentQueryService()
        q = ContentQuery(publications=["The Batch"])
        results = svc.build_query(db_session, q).all()
        assert len(results) == 1
        assert results[0].publication == "The Batch"

    def test_filter_by_publication_search_ilike(self, db_session):
        ContentFactory.create(publication="The Batch Weekly")
        ContentFactory.create(publication="AI Batch Report")
        ContentFactory.create(publication="Tech Daily")
        db_session.flush()

        svc = ContentQueryService()
        q = ContentQuery(publication_search="batch")
        results = svc.build_query(db_session, q).all()
        assert len(results) == 2

    def test_filter_by_start_date(self, db_session):
        ContentFactory.create(published_date=datetime(2026, 1, 10, tzinfo=UTC))
        ContentFactory.create(published_date=datetime(2026, 1, 20, tzinfo=UTC))
        ContentFactory.create(published_date=datetime(2026, 2, 5, tzinfo=UTC))
        db_session.flush()

        svc = ContentQueryService()
        q = ContentQuery(start_date=datetime(2026, 1, 15, tzinfo=UTC))
        results = svc.build_query(db_session, q).all()
        assert len(results) == 2

    def test_filter_by_end_date(self, db_session):
        ContentFactory.create(published_date=datetime(2026, 1, 10, tzinfo=UTC))
        ContentFactory.create(published_date=datetime(2026, 1, 20, tzinfo=UTC))
        ContentFactory.create(published_date=datetime(2026, 2, 5, tzinfo=UTC))
        db_session.flush()

        svc = ContentQueryService()
        q = ContentQuery(end_date=datetime(2026, 1, 25, tzinfo=UTC))
        results = svc.build_query(db_session, q).all()
        assert len(results) == 2

    def test_filter_by_date_range(self, db_session):
        ContentFactory.create(published_date=datetime(2026, 1, 5, tzinfo=UTC))
        ContentFactory.create(published_date=datetime(2026, 1, 15, tzinfo=UTC))
        ContentFactory.create(published_date=datetime(2026, 2, 1, tzinfo=UTC))
        db_session.flush()

        svc = ContentQueryService()
        q = ContentQuery(
            start_date=datetime(2026, 1, 10, tzinfo=UTC),
            end_date=datetime(2026, 1, 20, tzinfo=UTC),
        )
        results = svc.build_query(db_session, q).all()
        assert len(results) == 1

    def test_filter_by_title_search(self, db_session):
        ContentFactory.create(title="GPT-5 Architecture Deep Dive")
        ContentFactory.create(title="Weekly AI Roundup")
        ContentFactory.create(title="Python Best Practices")
        db_session.flush()

        svc = ContentQueryService()
        q = ContentQuery(search="AI")
        results = svc.build_query(db_session, q).all()
        assert len(results) == 1
        assert "AI" in results[0].title

    def test_filter_by_limit(self, db_session):
        ContentFactory.create_batch(5)
        db_session.flush()

        svc = ContentQueryService()
        q = ContentQuery(limit=2)
        results = svc.build_query(db_session, q).all()
        assert len(results) == 2

    def test_empty_list_treated_as_none(self, db_session):
        """Empty source_types=[] should match all, same as None."""
        ContentFactory.create_batch(3)
        db_session.flush()

        svc = ContentQueryService()
        q = ContentQuery(source_types=[])
        results = svc.build_query(db_session, q).all()
        assert len(results) == 3

    def test_combined_filters(self, db_session):
        """Multiple filters compose with AND semantics."""
        ContentFactory.create(
            source_type=ContentSource.YOUTUBE,
            status=ContentStatus.PENDING,
            published_date=datetime(2026, 2, 20, tzinfo=UTC),
        )
        ContentFactory.create(
            source_type=ContentSource.YOUTUBE,
            status=ContentStatus.COMPLETED,
            published_date=datetime(2026, 2, 20, tzinfo=UTC),
        )
        ContentFactory.create(
            source_type=ContentSource.RSS,
            status=ContentStatus.PENDING,
            published_date=datetime(2026, 2, 20, tzinfo=UTC),
        )
        db_session.flush()

        svc = ContentQueryService()
        q = ContentQuery(
            source_types=[ContentSource.YOUTUBE],
            statuses=[ContentStatus.PENDING],
        )
        results = svc.build_query(db_session, q).all()
        assert len(results) == 1
        assert results[0].source_type == ContentSource.YOUTUBE
        assert results[0].status == ContentStatus.PENDING

    def test_sort_order_asc(self, db_session):
        ContentFactory.create(title="Bravo", published_date=datetime(2026, 1, 2, tzinfo=UTC))
        ContentFactory.create(title="Alpha", published_date=datetime(2026, 1, 1, tzinfo=UTC))
        ContentFactory.create(title="Charlie", published_date=datetime(2026, 1, 3, tzinfo=UTC))
        db_session.flush()

        svc = ContentQueryService()
        q = ContentQuery(sort_by="published_date", sort_order="asc")
        results = svc.build_query(db_session, q).all()
        assert results[0].title == "Alpha"
        assert results[2].title == "Charlie"

    def test_sort_order_desc(self, db_session):
        ContentFactory.create(title="Bravo", published_date=datetime(2026, 1, 2, tzinfo=UTC))
        ContentFactory.create(title="Alpha", published_date=datetime(2026, 1, 1, tzinfo=UTC))
        ContentFactory.create(title="Charlie", published_date=datetime(2026, 1, 3, tzinfo=UTC))
        db_session.flush()

        svc = ContentQueryService()
        q = ContentQuery(sort_by="published_date", sort_order="desc")
        results = svc.build_query(db_session, q).all()
        assert results[0].title == "Charlie"
        assert results[2].title == "Alpha"

    def test_start_date_after_end_date_returns_empty(self, db_session):
        """start_date > end_date returns empty result (not an error)."""
        ContentFactory.create(published_date=datetime(2026, 1, 15, tzinfo=UTC))
        db_session.flush()

        svc = ContentQueryService()
        q = ContentQuery(
            start_date=datetime(2026, 2, 1, tzinfo=UTC),
            end_date=datetime(2026, 1, 1, tzinfo=UTC),
        )
        results = svc.build_query(db_session, q).all()
        assert len(results) == 0


# =============================================================================
# ContentQueryService — Preview
# =============================================================================


class TestContentQueryServicePreview:
    """Tests for ContentQueryService.preview() method."""

    def test_preview_with_content(self, db_session):
        ContentFactory.create(
            source_type=ContentSource.RSS,
            status=ContentStatus.PENDING,
            published_date=datetime(2026, 2, 10, tzinfo=UTC),
            title="RSS Article",
        )
        ContentFactory.create(
            source_type=ContentSource.YOUTUBE,
            status=ContentStatus.COMPLETED,
            published_date=datetime(2026, 2, 15, tzinfo=UTC),
            title="YouTube Video",
        )
        db_session.flush()

        svc = ContentQueryService()
        # Patch get_db to use our test session
        from contextlib import contextmanager
        from unittest.mock import patch

        @contextmanager
        def mock_get_db():
            yield db_session

        with patch("src.services.content_query.get_db", mock_get_db):
            preview = svc.preview(ContentQuery())

        assert preview.total_count == 2
        assert preview.by_source == {"rss": 1, "youtube": 1}
        assert preview.by_status == {"completed": 1, "pending": 1}
        assert preview.date_range["earliest"] is not None
        assert preview.date_range["latest"] is not None
        assert len(preview.sample_titles) == 2

    def test_preview_zero_matches(self, db_session):
        svc = ContentQueryService()
        from contextlib import contextmanager
        from unittest.mock import patch

        @contextmanager
        def mock_get_db():
            yield db_session

        with patch("src.services.content_query.get_db", mock_get_db):
            preview = svc.preview(ContentQuery(source_types=[ContentSource.YOUTUBE]))

        assert preview.total_count == 0
        assert preview.by_source == {}
        assert preview.by_status == {}
        assert preview.date_range == {"earliest": None, "latest": None}
        assert preview.sample_titles == []

    def test_preview_sample_titles_limited(self, db_session):
        for i in range(15):
            ContentFactory.create(
                title=f"Article {i}",
                published_date=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=i),
            )
        db_session.flush()

        svc = ContentQueryService()
        from contextlib import contextmanager
        from unittest.mock import patch

        @contextmanager
        def mock_get_db():
            yield db_session

        with patch("src.services.content_query.get_db", mock_get_db):
            preview = svc.preview(ContentQuery())

        assert len(preview.sample_titles) == PREVIEW_SAMPLE_LIMIT

    def test_preview_sample_titles_ordered_by_date_desc(self, db_session):
        ContentFactory.create(
            title="Old Article",
            published_date=datetime(2026, 1, 1, tzinfo=UTC),
        )
        ContentFactory.create(
            title="New Article",
            published_date=datetime(2026, 2, 1, tzinfo=UTC),
        )
        db_session.flush()

        svc = ContentQueryService()
        from contextlib import contextmanager
        from unittest.mock import patch

        @contextmanager
        def mock_get_db():
            yield db_session

        with patch("src.services.content_query.get_db", mock_get_db):
            preview = svc.preview(ContentQuery())

        assert preview.sample_titles[0] == "New Article"
        assert preview.sample_titles[1] == "Old Article"

    def test_preview_by_source_alphabetical(self, db_session):
        ContentFactory.create(source_type=ContentSource.YOUTUBE)
        ContentFactory.create(source_type=ContentSource.GMAIL)
        ContentFactory.create(source_type=ContentSource.RSS)
        db_session.flush()

        svc = ContentQueryService()
        from contextlib import contextmanager
        from unittest.mock import patch

        @contextmanager
        def mock_get_db():
            yield db_session

        with patch("src.services.content_query.get_db", mock_get_db):
            preview = svc.preview(ContentQuery())

        keys = list(preview.by_source.keys())
        assert keys == sorted(keys)

    def test_preview_with_limit(self, db_session):
        for i in range(5):
            ContentFactory.create(
                published_date=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=i),
            )
        db_session.flush()

        svc = ContentQueryService()
        from contextlib import contextmanager
        from unittest.mock import patch

        @contextmanager
        def mock_get_db():
            yield db_session

        with patch("src.services.content_query.get_db", mock_get_db):
            preview = svc.preview(ContentQuery(limit=3))

        assert preview.total_count == 3

    def test_preview_echoes_query(self, db_session):
        svc = ContentQueryService()
        from contextlib import contextmanager
        from unittest.mock import patch

        @contextmanager
        def mock_get_db():
            yield db_session

        query = ContentQuery(source_types=[ContentSource.RSS], limit=5)
        with patch("src.services.content_query.get_db", mock_get_db):
            preview = svc.preview(query)

        assert preview.query == query


# =============================================================================
# ContentQueryService — Resolve
# =============================================================================


class TestContentQueryServiceResolve:
    """Tests for ContentQueryService.resolve() method."""

    def test_resolve_returns_ids(self, db_session):
        c1 = ContentFactory.create(status=ContentStatus.PENDING)
        c2 = ContentFactory.create(status=ContentStatus.PARSED)
        ContentFactory.create(status=ContentStatus.COMPLETED)
        db_session.flush()

        svc = ContentQueryService()
        from contextlib import contextmanager
        from unittest.mock import patch

        @contextmanager
        def mock_get_db():
            yield db_session

        with patch("src.services.content_query.get_db", mock_get_db):
            ids = svc.resolve(ContentQuery(statuses=[ContentStatus.PENDING, ContentStatus.PARSED]))

        assert set(ids) == {c1.id, c2.id}

    def test_resolve_respects_limit(self, db_session):
        ContentFactory.create_batch(5)
        db_session.flush()

        svc = ContentQueryService()
        from contextlib import contextmanager
        from unittest.mock import patch

        @contextmanager
        def mock_get_db():
            yield db_session

        with patch("src.services.content_query.get_db", mock_get_db):
            ids = svc.resolve(ContentQuery(limit=2))

        assert len(ids) == 2

    def test_resolve_empty_result(self, db_session):
        svc = ContentQueryService()
        from contextlib import contextmanager
        from unittest.mock import patch

        @contextmanager
        def mock_get_db():
            yield db_session

        with patch("src.services.content_query.get_db", mock_get_db):
            ids = svc.resolve(ContentQuery(source_types=[ContentSource.YOUTUBE]))

        assert ids == []

    def test_resolve_respects_sort_order(self, db_session):
        c_old = ContentFactory.create(
            published_date=datetime(2026, 1, 1, tzinfo=UTC),
        )
        c_new = ContentFactory.create(
            published_date=datetime(2026, 2, 1, tzinfo=UTC),
        )
        db_session.flush()

        svc = ContentQueryService()
        from contextlib import contextmanager
        from unittest.mock import patch

        @contextmanager
        def mock_get_db():
            yield db_session

        with patch("src.services.content_query.get_db", mock_get_db):
            ids_desc = svc.resolve(ContentQuery(sort_order="desc"))
            ids_asc = svc.resolve(ContentQuery(sort_order="asc"))

        assert ids_desc[0] == c_new.id
        assert ids_asc[0] == c_old.id
