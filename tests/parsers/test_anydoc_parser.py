"""Comprehensive test suite for AnydocParser.

All anydoc imports are mocked since firecrawl-anydoc is an optional
dependency that may not be installed in the test environment.
"""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.models.document import DocumentFormat

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_block(kind, text=None, content=None, blocks=None, table=None):
    """Build a lightweight fake anydoc Block (MagicMock attrs are truthy)."""
    return SimpleNamespace(
        kind=kind,
        text=text,
        content=content,
        blocks=blocks,
        table=table,
        list=None,
        level=None,
        lang=None,
        anchor=None,
    )


def _make_inline(text):
    return SimpleNamespace(text=text, content=None)


def _make_cell(text):
    return SimpleNamespace(
        cell=SimpleNamespace(
            blocks=[_make_block("paragraph", content=[_make_inline(text)])],
            col_span=1,
            row_span=1,
        ),
        kind="cell",
        origin_col=0,
        origin_row=0,
    )


def _make_table(grid_texts, header_rows=0):
    """Build a fake anydoc Table from a 2D list of cell strings."""
    grid = [[_make_cell(text) for text in row] for row in grid_texts]
    return SimpleNamespace(grid=grid, header_rows=header_rows, kind="data")


def _make_mock_anydoc():
    """Build a mock anydoc module with realistic conversion results."""
    module = MagicMock()
    module.to_markdown_bytes = MagicMock(
        return_value="# Test Document\n\nSome content with [a link](https://example.com)."
    )
    module.to_document = MagicMock(return_value=SimpleNamespace(blocks=[], assets=[], notes=[]))
    return module


# Patch sys.modules BEFORE importing AnydocParser so the availability check
# in __init__ passes even when firecrawl-anydoc is not installed.
_mock_anydoc = _make_mock_anydoc()
_anydoc_patch = patch.dict(sys.modules, {"anydoc": _mock_anydoc})
_anydoc_patch.start()

from src.parsers.anydoc_parser import AnydocParser  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_mock_anydoc():
    """Reset the shared mock anydoc module before each test."""
    _mock_anydoc.to_markdown_bytes = MagicMock(
        return_value="# Test Document\n\nSome content with [a link](https://example.com)."
    )
    _mock_anydoc.to_document = MagicMock(
        return_value=SimpleNamespace(blocks=[], assets=[], notes=[])
    )
    yield


@pytest.fixture()
def mock_anydoc():
    """Provide access to the mock anydoc module for test customisation."""
    return _mock_anydoc


@pytest.fixture()
def parser():
    """Return a ready-to-use AnydocParser instance."""
    return AnydocParser()


@pytest.fixture()
def docx_file(tmp_path):
    """Create a dummy .docx file on disk."""
    path = tmp_path / "report.docx"
    path.write_bytes(b"fake docx bytes")
    return path


# ---------------------------------------------------------------------------
# 1. Initialisation tests
# ---------------------------------------------------------------------------


class TestInit:
    def test_init_defaults(self):
        parser = AnydocParser()
        assert parser.max_file_size_mb == 100
        assert parser.timeout_seconds == 60
        assert parser.extract_tables is True

    def test_init_fails_when_anydoc_missing(self):
        with patch.dict(sys.modules, {"anydoc": None}):
            with pytest.raises(ImportError, match="anydoc is required"):
                AnydocParser()

    def test_name_property(self, parser):
        assert parser.name == "anydoc"


# ---------------------------------------------------------------------------
# 2. Parse success tests
# ---------------------------------------------------------------------------


class TestParse:
    @pytest.mark.asyncio
    async def test_parse_file_path(self, parser, docx_file, mock_anydoc):
        result = await parser.parse(docx_file)

        mock_anydoc.to_markdown_bytes.assert_called_once_with(b"fake docx bytes", "docx")
        assert result.markdown_content.startswith("# Test Document")
        assert result.parser_used == "anydoc"
        assert result.source_format == DocumentFormat.DOCX
        assert result.metadata.title == "report"
        assert result.metadata.word_count == 8
        assert result.links == ["https://example.com"]

    @pytest.mark.asyncio
    async def test_parse_bytes_without_hint(self, parser, mock_anydoc):
        result = await parser.parse(b"raw bytes")

        # Unknown format: rely on anydoc content auto-detection
        mock_anydoc.to_markdown_bytes.assert_called_once_with(b"raw bytes", None)
        assert result.source_path == "stream"
        assert result.source_format == DocumentFormat.UNKNOWN

    @pytest.mark.asyncio
    async def test_parse_bytes_with_hint(self, parser, mock_anydoc):
        result = await parser.parse(b"a,b\n1,2", format_hint="csv")

        mock_anydoc.to_markdown_bytes.assert_called_once_with(b"a,b\n1,2", "csv")
        assert result.source_format == DocumentFormat.TEXT

    @pytest.mark.asyncio
    async def test_parse_file_like_object(self, parser, mock_anydoc):
        class FakeStream:
            def read(self):
                return b"stream bytes"

        result = await parser.parse(FakeStream(), format_hint="pptx")

        mock_anydoc.to_markdown_bytes.assert_called_once_with(b"stream bytes", "pptx")
        assert result.source_path == "stream"
        assert result.source_format == DocumentFormat.PPTX

    @pytest.mark.asyncio
    async def test_parse_rejects_urls(self, parser):
        with pytest.raises(ValueError, match="does not fetch URLs"):
            await parser.parse("https://example.com/report.docx")

    @pytest.mark.asyncio
    async def test_parse_rejects_oversized_file(self, tmp_path, mock_anydoc):
        parser = AnydocParser(max_file_size_mb=0)
        path = tmp_path / "big.docx"
        path.write_bytes(b"x" * 1024)

        with pytest.raises(ValueError, match="exceeds limit"):
            await parser.parse(path)

    @pytest.mark.asyncio
    async def test_parse_propagates_conversion_errors(self, parser, docx_file, mock_anydoc):
        mock_anydoc.to_markdown_bytes.side_effect = ValueError("corrupt document")

        with pytest.raises(ValueError, match="corrupt document"):
            await parser.parse(docx_file)


# ---------------------------------------------------------------------------
# 3. Table extraction tests
# ---------------------------------------------------------------------------


class TestTableExtraction:
    @pytest.mark.asyncio
    async def test_extracts_structured_tables(self, parser, docx_file, mock_anydoc):
        table = _make_table([["Model", "Score"], ["Fable 5", "98.2"]], header_rows=0)
        mock_anydoc.to_document.return_value = SimpleNamespace(
            blocks=[_make_block("table", table=table)], assets=[], notes=[]
        )

        result = await parser.parse(docx_file)

        assert len(result.tables) == 1
        assert result.tables[0].headers == ["Model", "Score"]
        assert result.tables[0].rows == [["Fable 5", "98.2"]]
        assert "| Model | Score |" in result.tables[0].markdown

    @pytest.mark.asyncio
    async def test_respects_declared_header_rows(self, parser, docx_file, mock_anydoc):
        table = _make_table([["h1", "h2"], ["a", "b"], ["c", "d"]], header_rows=1)
        mock_anydoc.to_document.return_value = SimpleNamespace(
            blocks=[_make_block("table", table=table)], assets=[], notes=[]
        )

        result = await parser.parse(docx_file)

        assert result.tables[0].headers == ["h1", "h2"]
        assert result.tables[0].rows == [["a", "b"], ["c", "d"]]

    @pytest.mark.asyncio
    async def test_finds_nested_tables(self, parser, docx_file, mock_anydoc):
        inner = _make_block("table", table=_make_table([["x"]]))
        outer = _make_block("list", blocks=[inner])
        mock_anydoc.to_document.return_value = SimpleNamespace(blocks=[outer], assets=[], notes=[])

        result = await parser.parse(docx_file)

        assert len(result.tables) == 1
        assert result.tables[0].headers == ["x"]

    @pytest.mark.asyncio
    async def test_table_failure_is_nonfatal(self, parser, docx_file, mock_anydoc):
        mock_anydoc.to_document.side_effect = RuntimeError("model walk failed")

        result = await parser.parse(docx_file)

        assert result.tables == []
        assert any("table extraction failed" in w.lower() for w in result.warnings)
        assert result.markdown_content.startswith("# Test Document")

    @pytest.mark.asyncio
    async def test_pdf_skips_table_extraction(self, parser, tmp_path, mock_anydoc):
        """anydoc's document model rejects PDFs — no warning should be emitted."""
        path = tmp_path / "report.pdf"
        path.write_bytes(b"%PDF-1.4 fake")

        result = await parser.parse(path)

        mock_anydoc.to_document.assert_not_called()
        assert result.tables == []
        assert result.warnings == []

    @pytest.mark.asyncio
    async def test_tables_disabled(self, docx_file, mock_anydoc):
        parser = AnydocParser(extract_tables=False)

        result = await parser.parse(docx_file)

        mock_anydoc.to_document.assert_not_called()
        assert result.tables == []


# ---------------------------------------------------------------------------
# 4. can_parse / format detection tests
# ---------------------------------------------------------------------------


class TestCanParse:
    def test_supported_office_formats(self, parser):
        for name in ("a.docx", "b.pptx", "c.xlsx", "d.odt", "e.rtf", "f.epub", "g.csv"):
            assert parser.can_parse(name) is True

    def test_pdf_is_fallback(self, parser):
        assert parser.can_parse("report.pdf") is True
        assert "pdf" in parser.fallback_formats

    def test_unsupported_formats(self, parser):
        assert parser.can_parse("image.png") is False
        assert parser.can_parse("page.html") is False
        assert parser.can_parse("audio.mp3") is False

    def test_urls_rejected(self, parser):
        assert parser.can_parse("https://example.com/report.docx") is False

    def test_format_hint_overrides_extension(self, parser):
        assert parser.can_parse("mislabeled.bin", format_hint="docx") is True

    def test_detect_format(self, parser):
        assert parser._detect_format("report.DOCX") == "docx"
        assert parser._detect_format(Path("some/dir/deck.pptx")) == "pptx"
        assert parser._detect_format(b"bytes") == "unknown"
