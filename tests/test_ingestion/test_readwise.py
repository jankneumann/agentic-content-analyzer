"""Unit tests for Readwise Highlights API v2 ingestion.

Covers:
- Pure helpers: _book_source_id, _book_markdown, _parse_dt, _highlight_fingerprint
- ReadwiseIngestResult dataclass
- ReadwiseClient: init validation, verify_token, export 429 retry, iter_export
  pagination + source_types filter
- ReadwiseContentIngestionService: happy path, book idempotency, highlight
  insert/update/soft-delete, force_reprocess, error isolation
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from src.ingestion.readwise import (
    READWISE_AUTH_URL,
    READWISE_EXPORT_URL,
    ReadwiseClient,
    ReadwiseContentIngestionService,
    ReadwiseIngestResult,
    _book_markdown,
    _book_source_id,
    _highlight_fingerprint,
    _parse_dt,
)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


class TestBookSourceId:
    def test_prefix(self):
        assert _book_source_id(12345) == "readwise:12345"

    def test_accepts_string(self):
        assert _book_source_id("abc") == "readwise:abc"


class TestBookMarkdown:
    def test_renders_header_with_author_and_source(self):
        book = {
            "title": "Thinking, Fast and Slow",
            "author": "Daniel Kahneman",
            "source": "kindle",
            "category": "books",
            "highlights": [],
        }
        md = _book_markdown(book)
        assert md.startswith("# Thinking, Fast and Slow")
        assert "*by Daniel Kahneman*" in md
        assert "Readwise source: kindle · books" in md

    def test_renders_highlights_as_bullets_with_notes(self):
        book = {
            "title": "X",
            "highlights": [
                {"text": "First highlight.", "note": "my note"},
                {"text": "Second highlight."},
            ],
        }
        md = _book_markdown(book)
        assert "## Highlights" in md
        assert "- First highlight." in md
        assert "  > my note" in md
        assert "- Second highlight." in md

    def test_skips_deleted_highlights(self):
        book = {
            "title": "X",
            "highlights": [
                {"text": "Kept."},
                {"text": "Gone.", "is_deleted": True},
            ],
        }
        md = _book_markdown(book)
        assert "- Kept." in md
        assert "Gone." not in md

    def test_skips_empty_text(self):
        book = {"title": "X", "highlights": [{"text": "   "}, {"text": "real"}]}
        md = _book_markdown(book)
        assert "- real" in md
        # Only one bullet should appear
        assert md.count("\n- ") == 1

    def test_handles_missing_title(self):
        md = _book_markdown({})
        assert md.startswith("# (untitled)")


class TestParseDt:
    def test_none_returns_none(self):
        assert _parse_dt(None) is None
        assert _parse_dt("") is None

    def test_iso_utc_z(self):
        dt = _parse_dt("2026-04-20T12:00:00Z")
        assert dt is not None
        assert dt.tzinfo is not None
        assert dt.year == 2026 and dt.hour == 12

    def test_iso_with_offset(self):
        dt = _parse_dt("2026-04-20T12:00:00+02:00")
        assert dt is not None
        assert dt.tzinfo is not None

    def test_naive_iso_gets_utc(self):
        dt = _parse_dt("2026-04-20T12:00:00")
        assert dt is not None
        assert dt.tzinfo is UTC

    def test_passthrough_datetime(self):
        orig = datetime(2026, 4, 20, 12, 0, 0, tzinfo=UTC)
        assert _parse_dt(orig) == orig

    def test_invalid_returns_none(self):
        assert _parse_dt("not-a-date") is None


class TestHighlightFingerprint:
    def test_deterministic(self):
        hl = {"text": "x", "highlighted_at": "2026-04-20T12:00:00Z", "location": 42}
        assert _highlight_fingerprint(hl) == _highlight_fingerprint(hl)

    def test_differs_on_text_change(self):
        a = {"text": "x", "highlighted_at": "t", "location": 1}
        b = {"text": "y", "highlighted_at": "t", "location": 1}
        assert _highlight_fingerprint(a) != _highlight_fingerprint(b)

    def test_length_32(self):
        assert len(_highlight_fingerprint({})) == 32


# ---------------------------------------------------------------------------
# ReadwiseIngestResult dataclass
# ---------------------------------------------------------------------------


class TestReadwiseIngestResult:
    def test_defaults(self):
        r = ReadwiseIngestResult()
        assert r.books_ingested == 0
        assert r.books_updated == 0
        assert r.highlights_created == 0
        assert r.highlights_soft_deleted == 0
        assert r.errors == []
        assert r.latest_updated_at is None

    def test_items_ingested_combines_new_and_updated(self):
        r = ReadwiseIngestResult(books_ingested=3, books_updated=2)
        assert r.items_ingested == 5

    def test_errors_list_independence(self):
        r1 = ReadwiseIngestResult()
        r2 = ReadwiseIngestResult()
        r1.errors.append("e")
        assert r2.errors == []


# ---------------------------------------------------------------------------
# ReadwiseClient
# ---------------------------------------------------------------------------


class TestReadwiseClientInit:
    @patch("src.ingestion.readwise.settings")
    def test_uses_settings_key(self, mock_settings):
        mock_settings.readwise_api_key = "tok-abc"
        c = ReadwiseClient()
        assert c.api_key == "tok-abc"
        c.close()

    @patch("src.ingestion.readwise.settings")
    def test_explicit_override(self, mock_settings):
        mock_settings.readwise_api_key = "env-key"
        c = ReadwiseClient(api_key="arg-key")
        assert c.api_key == "arg-key"
        c.close()

    @patch("src.ingestion.readwise.settings")
    def test_missing_key_raises(self, mock_settings):
        mock_settings.readwise_api_key = None
        with pytest.raises(ValueError, match="READWISE_API_KEY is required"):
            ReadwiseClient()

    @patch("src.ingestion.readwise.settings")
    def test_sets_auth_header(self, mock_settings):
        mock_settings.readwise_api_key = "tok-xyz"
        c = ReadwiseClient()
        assert c._client.headers.get("Authorization") == "Token tok-xyz"
        c.close()


class TestReadwiseClientVerifyToken:
    @patch("src.ingestion.readwise.settings")
    def test_204_is_true(self, mock_settings):
        mock_settings.readwise_api_key = "tok"
        c = ReadwiseClient()
        mock_resp = MagicMock(status_code=204)
        c._client = MagicMock()
        c._client.get.return_value = mock_resp
        assert c.verify_token() is True
        c._client.get.assert_called_once_with(READWISE_AUTH_URL)

    @patch("src.ingestion.readwise.settings")
    def test_non_204_is_false(self, mock_settings):
        mock_settings.readwise_api_key = "tok"
        c = ReadwiseClient()
        c._client = MagicMock()
        c._client.get.return_value = MagicMock(status_code=401)
        assert c.verify_token() is False


class TestReadwiseClientExport:
    @patch("src.ingestion.readwise.settings")
    def test_builds_params(self, mock_settings):
        mock_settings.readwise_api_key = "tok"
        c = ReadwiseClient()
        c._client = MagicMock()
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"results": [], "nextPageCursor": None}
        c._client.get.return_value = resp

        c.export(
            updated_after=datetime(2026, 4, 20, tzinfo=UTC),
            ids=[1, 2],
            include_deleted=True,
            page_cursor="cur-1",
        )

        _, kwargs = c._client.get.call_args
        params = kwargs["params"]
        assert params["updatedAfter"].startswith("2026-04-20")
        assert params["ids"] == "1,2"
        assert params["includeDeleted"] == "true"
        assert params["pageCursor"] == "cur-1"
        c._client.get.assert_called_with(READWISE_EXPORT_URL, params=params)

    @patch("src.ingestion.readwise.settings")
    @patch("src.ingestion.readwise.time.sleep")
    def test_429_retries(self, mock_sleep, mock_settings):
        mock_settings.readwise_api_key = "tok"
        c = ReadwiseClient()
        c._client = MagicMock()
        throttled = MagicMock(status_code=429, headers={"Retry-After": "1"})
        ok = MagicMock(status_code=200)
        ok.json.return_value = {"results": [{"id": 1}], "nextPageCursor": None}
        c._client.get.side_effect = [throttled, ok]

        result = c.export()
        assert result == {"results": [{"id": 1}], "nextPageCursor": None}
        assert c._client.get.call_count == 2
        mock_sleep.assert_called_once_with(1.0)

    @patch("src.ingestion.readwise.settings")
    @patch("src.ingestion.readwise.time.sleep")
    def test_429_exhaustion_raises(self, mock_sleep, mock_settings):
        mock_settings.readwise_api_key = "tok"
        c = ReadwiseClient()
        c._client = MagicMock()
        c._client.get.return_value = MagicMock(status_code=429, headers={"Retry-After": "0"})

        with pytest.raises(RuntimeError, match="exhausted retries"):
            c.export()
        assert c._client.get.call_count == 4  # 4 attempts

    @patch("src.ingestion.readwise.settings")
    def test_http_error_propagates(self, mock_settings):
        mock_settings.readwise_api_key = "tok"
        c = ReadwiseClient()
        c._client = MagicMock()
        bad = MagicMock(status_code=500)
        bad.raise_for_status.side_effect = RuntimeError("boom")
        c._client.get.return_value = bad
        with pytest.raises(RuntimeError, match="boom"):
            c.export()


class TestReadwiseClientIterExport:
    @patch("src.ingestion.readwise.settings")
    def test_paginates_until_cursor_exhausted(self, mock_settings):
        mock_settings.readwise_api_key = "tok"
        c = ReadwiseClient()
        c.export = MagicMock(
            side_effect=[
                {"results": [{"id": 1}], "nextPageCursor": "cur-2"},
                {"results": [{"id": 2}], "nextPageCursor": None},
            ]
        )
        out = list(c.iter_export())
        assert [b["id"] for b in out] == [1, 2]
        assert c.export.call_count == 2

    @patch("src.ingestion.readwise.settings")
    def test_source_types_filter(self, mock_settings):
        mock_settings.readwise_api_key = "tok"
        c = ReadwiseClient()
        c.export = MagicMock(
            return_value={
                "results": [
                    {"id": 1, "source": "kindle"},
                    {"id": 2, "source": "instapaper"},
                    {"id": 3, "source": "pocket"},
                ],
                "nextPageCursor": None,
            }
        )
        out = list(c.iter_export(source_types=["kindle", "pocket"]))
        assert [b["id"] for b in out] == [1, 3]


# ---------------------------------------------------------------------------
# ReadwiseContentIngestionService
# ---------------------------------------------------------------------------


def _make_book(
    user_book_id: int = 100,
    title: str = "A Book",
    source: str = "kindle",
    highlights: list[dict] | None = None,
    **extra,
) -> dict:
    return {
        "user_book_id": user_book_id,
        "title": title,
        "author": "Author",
        "source": source,
        "category": "books",
        "source_url": "https://example.com/book",
        "highlights": highlights or [],
        **extra,
    }


def _make_highlight(hl_id: int = 1, text: str = "a highlight", **extra) -> dict:
    return {
        "id": hl_id,
        "text": text,
        "note": extra.pop("note", None),
        "location": extra.pop("location", 42),
        "location_type": extra.pop("location_type", "location"),
        "color": extra.pop("color", "yellow"),
        "highlighted_at": extra.pop("highlighted_at", "2026-04-20T12:00:00Z"),
        "tags": extra.pop("tags", []),
        "readwise_url": extra.pop("readwise_url", f"https://readwise.io/h/{hl_id}"),
        **extra,
    }


@pytest.fixture
def mock_db():
    """Context-manager-aware mock session returned by get_db()."""
    db = MagicMock()
    return db


@pytest.fixture
def patched_db(mock_db):
    """Patch get_db() to yield our mock_db."""
    with patch("src.ingestion.readwise.get_db") as gd:
        gd.return_value.__enter__ = MagicMock(return_value=mock_db)
        gd.return_value.__exit__ = MagicMock(return_value=False)
        yield mock_db


class TestServiceHappyPath:
    @patch("src.ingestion.readwise.ReadwiseClient")
    def test_new_book_creates_content_and_highlights(self, mock_client_cls, patched_db):
        mock_client = mock_client_cls.return_value
        mock_client.iter_export.return_value = iter(
            [_make_book(highlights=[_make_highlight(1, "first"), _make_highlight(2, "second")])]
        )

        # query().filter().one_or_none() returns None for both Content and Highlight
        patched_db.query.return_value.filter.return_value.one_or_none.return_value = None

        service = ReadwiseContentIngestionService(api_key="tok")
        result = service.ingest_content()

        assert result.books_ingested == 1
        assert result.books_updated == 0
        assert result.highlights_created == 2
        assert result.highlights_soft_deleted == 0
        # 1 book add + 2 highlight adds = 3 adds
        assert patched_db.add.call_count == 3
        patched_db.commit.assert_called()

    @patch("src.ingestion.readwise.ReadwiseClient")
    def test_skips_book_with_no_user_book_id(self, mock_client_cls, patched_db):
        mock_client = mock_client_cls.return_value
        mock_client.iter_export.return_value = iter([{"title": "no id"}])

        service = ReadwiseContentIngestionService(api_key="tok")
        result = service.ingest_content()

        assert result.books_ingested == 0
        assert result.books_skipped == 1

    @patch("src.ingestion.readwise.ReadwiseClient")
    def test_max_books_caps_iteration(self, mock_client_cls, patched_db):
        mock_client = mock_client_cls.return_value
        mock_client.iter_export.return_value = iter(
            [_make_book(user_book_id=i, highlights=[]) for i in range(5)]
        )
        patched_db.query.return_value.filter.return_value.one_or_none.return_value = None

        service = ReadwiseContentIngestionService(api_key="tok")
        result = service.ingest_content(max_books=2)

        assert result.books_ingested == 2


class TestServiceBookIdempotency:
    @patch("src.ingestion.readwise.ReadwiseClient")
    def test_unchanged_content_is_skipped(self, mock_client_cls, patched_db):
        """When content_hash matches, book is neither updated nor reingested."""
        from src.utils.content_hash import generate_markdown_hash

        from src.ingestion.readwise import _book_markdown

        book = _make_book(highlights=[])
        existing = MagicMock()
        existing.id = 42
        existing.content_hash = generate_markdown_hash(_book_markdown(book))

        # First query (for Content) returns existing; subsequent Highlight queries return None
        patched_db.query.return_value.filter.return_value.one_or_none.side_effect = [existing]

        mock_client = mock_client_cls.return_value
        mock_client.iter_export.return_value = iter([book])

        service = ReadwiseContentIngestionService(api_key="tok")
        result = service.ingest_content()

        assert result.books_ingested == 0
        assert result.books_updated == 0
        assert result.books_skipped == 1

    @patch("src.ingestion.readwise.ReadwiseClient")
    def test_changed_content_is_updated(self, mock_client_cls, patched_db):
        existing = MagicMock()
        existing.id = 99
        existing.content_hash = "stale-hash"
        patched_db.query.return_value.filter.return_value.one_or_none.side_effect = [existing]

        mock_client = mock_client_cls.return_value
        mock_client.iter_export.return_value = iter([_make_book(highlights=[])])

        service = ReadwiseContentIngestionService(api_key="tok")
        result = service.ingest_content()

        assert result.books_updated == 1
        assert result.books_ingested == 0

    @patch("src.ingestion.readwise.ReadwiseClient")
    def test_force_reprocess_resets_status(self, mock_client_cls, patched_db):
        from src.models.content import ContentStatus
        from src.utils.content_hash import generate_markdown_hash

        from src.ingestion.readwise import _book_markdown

        book = _make_book(highlights=[])
        existing = MagicMock()
        existing.id = 1
        existing.content_hash = generate_markdown_hash(_book_markdown(book))
        existing.status = ContentStatus.COMPLETED
        patched_db.query.return_value.filter.return_value.one_or_none.side_effect = [existing]

        mock_client = mock_client_cls.return_value
        mock_client.iter_export.return_value = iter([book])

        service = ReadwiseContentIngestionService(api_key="tok")
        result = service.ingest_content(force_reprocess=True)

        assert result.books_updated == 1
        assert existing.status == ContentStatus.PENDING


class TestServiceHighlightSync:
    @patch("src.ingestion.readwise.ReadwiseClient")
    def test_soft_delete_tombstone(self, mock_client_cls, patched_db):
        """A highlight with is_deleted=True should soft-delete the matching row."""
        existing_content = MagicMock()
        existing_content.id = 10
        existing_content.content_hash = "matches"

        existing_hl = MagicMock()
        existing_hl.deleted_at = None

        # Order of queries: Content lookup, then Highlight lookup
        patched_db.query.return_value.filter.return_value.one_or_none.side_effect = [
            existing_content,
            existing_hl,
        ]

        # Make content_hash match so book is not updated either way
        with patch(
            "src.ingestion.readwise.generate_markdown_hash", return_value="matches"
        ):
            mock_client = mock_client_cls.return_value
            mock_client.iter_export.return_value = iter(
                [_make_book(highlights=[_make_highlight(1, "x", is_deleted=True)])]
            )

            service = ReadwiseContentIngestionService(api_key="tok")
            result = service.ingest_content(include_deleted=True)

        assert result.highlights_soft_deleted == 1
        assert existing_hl.deleted_at is not None

    @patch("src.ingestion.readwise.ReadwiseClient")
    def test_existing_highlight_updates_when_changed(self, mock_client_cls, patched_db):
        """Changed fields on an existing highlight bump highlights_updated."""
        existing_content = MagicMock()
        existing_content.id = 10
        existing_content.content_hash = "matches"

        existing_hl = MagicMock()
        existing_hl.deleted_at = None
        existing_hl.text = "OLD TEXT"
        existing_hl.note = None
        existing_hl.color = None
        existing_hl.location = 1
        existing_hl.location_type = "location"
        existing_hl.source_url = None
        existing_hl.highlighted_at = None
        existing_hl.tags = []

        patched_db.query.return_value.filter.return_value.one_or_none.side_effect = [
            existing_content,
            existing_hl,
        ]

        with patch(
            "src.ingestion.readwise.generate_markdown_hash", return_value="matches"
        ):
            mock_client = mock_client_cls.return_value
            mock_client.iter_export.return_value = iter(
                [_make_book(highlights=[_make_highlight(1, "NEW TEXT")])]
            )

            service = ReadwiseContentIngestionService(api_key="tok")
            result = service.ingest_content()

        assert result.highlights_updated == 1
        assert existing_hl.text == "NEW TEXT"

    @patch("src.ingestion.readwise.ReadwiseClient")
    def test_existing_highlight_unchanged_no_op(self, mock_client_cls, patched_db):
        """Highlight whose fields already match must not bump the updated counter."""
        existing_content = MagicMock()
        existing_content.id = 10
        existing_content.content_hash = "matches"

        hl_payload = _make_highlight(1, "same text", tags=[{"name": "fav"}])
        # Pre-populate the mock with matching values so nothing should change
        existing_hl = MagicMock()
        existing_hl.deleted_at = None
        existing_hl.text = "same text"
        existing_hl.note = None
        existing_hl.color = "yellow"
        existing_hl.location = 42
        existing_hl.location_type = "location"
        existing_hl.source_url = "https://readwise.io/h/1"
        existing_hl.highlighted_at = _parse_dt("2026-04-20T12:00:00Z")
        existing_hl.tags = ["fav"]

        patched_db.query.return_value.filter.return_value.one_or_none.side_effect = [
            existing_content,
            existing_hl,
        ]

        with patch(
            "src.ingestion.readwise.generate_markdown_hash", return_value="matches"
        ):
            mock_client = mock_client_cls.return_value
            mock_client.iter_export.return_value = iter(
                [_make_book(highlights=[hl_payload])]
            )

            service = ReadwiseContentIngestionService(api_key="tok")
            result = service.ingest_content()

        assert result.highlights_updated == 0
        assert result.highlights_created == 0


class TestServiceErrorIsolation:
    @patch("src.ingestion.readwise.ReadwiseClient")
    def test_book_error_is_captured_not_raised(self, mock_client_cls, patched_db):
        """A failure on one book should not abort the run."""
        mock_client = mock_client_cls.return_value
        mock_client.iter_export.return_value = iter(
            [_make_book(user_book_id=1), _make_book(user_book_id=2)]
        )

        # First book: query raises; second book: normal new-book path
        new_book_flow = [None, None]  # highlight lookups for book 2
        patched_db.query.return_value.filter.return_value.one_or_none.side_effect = [
            RuntimeError("db exploded"),
            None,
            *new_book_flow,
        ]

        service = ReadwiseContentIngestionService(api_key="tok")
        result = service.ingest_content()

        assert len(result.errors) == 1
        assert "db exploded" in result.errors[0]
        # Second book should still have been ingested
        assert result.books_ingested == 1

    @patch("src.ingestion.readwise.ReadwiseClient")
    def test_close_delegates_to_client(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        service = ReadwiseContentIngestionService(api_key="tok")
        service.close()
        mock_client.close.assert_called_once()
