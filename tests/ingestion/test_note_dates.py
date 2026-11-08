"""Authored-date resolution for uploaded notes (Evernote exports, Web Clipper notes)."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.ingestion.files import FileContentIngestionService
from src.ingestion.note_dates import date_from_text, resolve_note_date
from src.models.document import DocumentContent, DocumentFormat, DocumentMetadata

NOW = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)


def _resolve(
    *,
    head: str | None = None,
    title: str | None = None,
    stem: str | None = None,
    parser_created: datetime | None = None,
):
    return resolve_note_date(
        raw_head=head.encode() if head is not None else None,
        title=title,
        filename_stem=stem,
        parser_created=parser_created,
        now=NOW,
    )


# --- frontmatter -------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2019-03-14T10:22:00+01:00", datetime(2019, 3, 14, 9, 22, tzinfo=UTC)),
        ("2019-03-14T10:22:00Z", datetime(2019, 3, 14, 10, 22, tzinfo=UTC)),
        ("'2019-03-14 10:22'", datetime(2019, 3, 14, 10, 22, tzinfo=UTC)),
        ("2019-03-14", datetime(2019, 3, 14, tzinfo=UTC)),
        ("20190314T102200Z", datetime(2019, 3, 14, 10, 22, tzinfo=UTC)),
        ("14 March 2019 (2019.03.14)", datetime(2019, 3, 14, tzinfo=UTC)),
    ],
)
def test_frontmatter_created_formats(value: str, expected: datetime) -> None:
    result = _resolve(head=f"---\ncreated: {value}\ntags: [a]\n---\n\n# Note\n")

    assert result.value == expected
    assert result.source == "frontmatter:created"


def test_frontmatter_beats_title_and_filename() -> None:
    result = _resolve(
        head="---\ncreated: 2018-01-02\n---\nbody",
        title="2021-05-06 Clipped article",
        stem="2021-05-06 Clipped article",
    )

    assert result.value == datetime(2018, 1, 2, tzinfo=UTC)


def test_frontmatter_key_precedence_prefers_created_over_date() -> None:
    result = _resolve(
        head="---\ndate: 2020-01-01\ncaptured_at: 2019-06-01\nCreated: 2018-01-01\n---\n"
    )

    assert result.value == datetime(2018, 1, 1, tzinfo=UTC)
    assert result.source == "frontmatter:created"


def test_unusable_frontmatter_date_falls_through_to_title() -> None:
    result = _resolve(
        head="---\ncreated: not a date\nupdated: 2017-01-01\n---\n",
        title="2016-04-05 Meeting notes",
    )

    assert result.value == datetime(2016, 4, 5, tzinfo=UTC)
    assert result.source == "title"


@pytest.mark.parametrize(
    "head",
    [
        "# No frontmatter\n\ncreated: 2019-03-14\n",  # key outside a frontmatter block
        "---\ncreated: [unclosed\n---\n",  # malformed YAML
        "---\n- just\n- a list\n---\n",  # not a mapping
        "---\ncreated: 2019-03-14\n",  # never closed
        "---\ncreated: 2999-01-01\n---\n",  # future
        "---\ncreated: 1901-01-01\n---\n",  # implausibly old
    ],
)
def test_frontmatter_without_usable_date_is_ignored(head: str) -> None:
    assert _resolve(head=head).source == "ingested_at"


def test_bom_and_crlf_frontmatter_is_read() -> None:
    result = _resolve(head="﻿---\r\ncreated: 2019-03-14\r\n---\r\nbody")

    assert result.value == datetime(2019, 3, 14, tzinfo=UTC)


# --- title / filename --------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2024-03-14 How agents plan", datetime(2024, 3, 14, tzinfo=UTC)),
        ("How agents plan (2024-03-14)", datetime(2024, 3, 14, tzinfo=UTC)),
        ("2024_03_14-how-agents-plan", datetime(2024, 3, 14, tzinfo=UTC)),
        ("2024.03.14 How agents plan", datetime(2024, 3, 14, tzinfo=UTC)),
        ("20240314 How agents plan", datetime(2024, 3, 14, tzinfo=UTC)),
    ],
)
def test_title_date_formats(text: str, expected: datetime) -> None:
    assert date_from_text(text, now=NOW) == expected


@pytest.mark.parametrize(
    "text",
    [
        "Order 2024031412345",  # digits run on: not a date
        "2024-13-45 not a calendar date",
        "2024-03/14 mixed separators",
        "Top 10 ideas for 2024",
        "Plans for 2099-01-01",  # future
    ],
)
def test_title_without_date(text: str) -> None:
    assert date_from_text(text, now=NOW) is None


def test_leftmost_valid_title_date_wins() -> None:
    assert date_from_text("2023-99-01 then 2022-02-03 then 2021-01-01", now=NOW) == datetime(
        2022, 2, 3, tzinfo=UTC
    )


def test_filename_used_when_title_has_no_date() -> None:
    result = _resolve(title="How agents plan", stem="2024-03-14 How agents plan")

    assert result.value == datetime(2024, 3, 14, tzinfo=UTC)
    assert result.source == "filename"


# --- fallbacks ---------------------------------------------------------------


def test_parser_metadata_used_after_note_signals() -> None:
    parser_date = datetime(2015, 7, 8, 9, 0)

    result = _resolve(title="Untitled", parser_created=parser_date)

    assert result.value == datetime(2015, 7, 8, 9, 0, tzinfo=UTC)
    assert result.source == "parser"


def test_no_signal_falls_back_to_now() -> None:
    result = _resolve(head="plain text", title="Untitled", stem="untitled")

    assert result.value == NOW
    assert result.source == "ingested_at"


# --- FileContentIngestionService wiring ---------------------------------------


def _document(path: str, markdown: str) -> DocumentContent:
    return DocumentContent(
        markdown_content=markdown,
        source_path=path,
        source_format=DocumentFormat.MARKDOWN,
        parser_used="test",
        metadata=DocumentMetadata(title=Path(path).stem),
    )


@pytest.mark.asyncio
async def test_ingest_file_uses_frontmatter_created_date(tmp_path: Path) -> None:
    body = "---\ncreated: 2019-03-14T10:22:00Z\n---\n\n# Old Evernote note\n"
    path = tmp_path / "Old Evernote note.md"
    path.write_text(body)
    router = MagicMock()
    router.parse = AsyncMock(return_value=_document(str(path), body))
    service = FileContentIngestionService(router=router, db=MagicMock())
    service._find_duplicate = MagicMock(return_value=None)  # type: ignore[method-assign]

    with patch("src.services.indexing.index_content"):
        content = await service.ingest_file(path)

    assert content.published_date == datetime(2019, 3, 14, 10, 22, tzinfo=UTC)
    assert content.metadata_json["published_date_source"] == "frontmatter:created"


@pytest.mark.asyncio
async def test_ingest_bytes_uses_filename_date() -> None:
    body = b"# Clipped article\n\nNo frontmatter here."
    router = MagicMock()
    router.parse = AsyncMock(return_value=_document("2023-11-02 Clipped article.md", body.decode()))
    service = FileContentIngestionService(router=router, db=MagicMock())
    service._find_duplicate = MagicMock(return_value=None)  # type: ignore[method-assign]

    with patch("src.services.indexing.index_content"):
        content = await service.ingest_bytes(body, filename="2023-11-02 Clipped article.md")

    assert content.published_date == datetime(2023, 11, 2, tzinfo=UTC)
    assert content.metadata_json["published_date_source"] == "title"


def test_binary_formats_skip_frontmatter_scan_but_keep_title_date() -> None:
    service = FileContentIngestionService(router=MagicMock(), db=MagicMock())
    doc = DocumentContent(
        markdown_content="---\ncreated: 2001-01-01\n---\n",
        source_path="2020-06-07 Board deck.pdf",
        source_format=DocumentFormat.PDF,
        parser_used="test",
    )

    content = service._create_content(
        doc,
        Path("2020-06-07 Board deck.pdf"),
        hashlib.sha256(b"x").hexdigest(),
        None,
        None,
    )

    assert content.published_date == datetime(2020, 6, 7, tzinfo=UTC)
    assert content.metadata_json["published_date_source"] == "title"
