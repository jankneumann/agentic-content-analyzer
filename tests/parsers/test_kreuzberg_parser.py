"""Comprehensive test suite for KreuzbergParser.

All kreuzberg imports are mocked since kreuzberg is an optional dependency
that may not be installed in the test environment.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.document import DocumentContent, DocumentFormat, TableData

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_mock_kreuzberg():
    """Build a mock kreuzberg module with realistic extraction results."""
    module = MagicMock()

    # ExtractionConfig / OutputFormat
    module.ExtractionConfig = MagicMock
    module.OutputFormat = MagicMock()
    module.OutputFormat.MARKDOWN = "markdown"

    # Default extraction result
    result = MagicMock()
    result.content = "# Test Document\n\nSome content here with [a link](https://example.com)."
    result.metadata = {
        "title": "Test Document",
        "page_count": 3,
        "language": "en",
        "authors": ["Alice", "Bob"],
    }
    result.tables = []
    result.detected_languages = ["en"]

    module.extract_file = AsyncMock(return_value=result)
    module.extract_bytes = AsyncMock(return_value=result)

    # Keep a reference so tests can customise it
    module._default_result = result

    return module


# Create a single module-level mock so we never need importlib.reload
_mock_kreuzberg = _make_mock_kreuzberg()

# Patch sys.modules BEFORE importing KreuzbergParser
# This avoids any need for importlib.reload (which breaks C-extension modules)
_kreuzberg_patch = patch.dict(sys.modules, {"kreuzberg": _mock_kreuzberg})
_kreuzberg_patch.start()

from src.parsers.kreuzberg_parser import KreuzbergParser  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_mock_kreuzberg():
    """Reset the shared mock kreuzberg module before each test."""
    result = MagicMock()
    result.content = "# Test Document\n\nSome content here with [a link](https://example.com)."
    result.metadata = {
        "title": "Test Document",
        "page_count": 3,
        "language": "en",
        "authors": ["Alice", "Bob"],
    }
    result.tables = []
    result.detected_languages = ["en"]

    _mock_kreuzberg.extract_file = AsyncMock(return_value=result)
    _mock_kreuzberg.extract_bytes = AsyncMock(return_value=result)
    _mock_kreuzberg._default_result = result

    yield


@pytest.fixture()
def mock_kreuzberg():
    """Provide access to the mock kreuzberg module for test customisation."""
    return _mock_kreuzberg


@pytest.fixture()
def parser():
    """Return a ready-to-use KreuzbergParser instance."""
    return KreuzbergParser()


# ---------------------------------------------------------------------------
# 1. Initialisation tests
# ---------------------------------------------------------------------------


class TestInit:
    def test_init_succeeds_when_kreuzberg_available(self):
        parser = KreuzbergParser()
        assert parser is not None
        assert parser.max_file_size_mb == 100
        assert parser.timeout_seconds == 120

    def test_init_fails_when_kreuzberg_missing(self):
        """Without a mock in sys.modules, importing kreuzberg should fail."""
        # Temporarily remove the mock so the import inside __init__ fails
        with patch.dict(sys.modules, {"kreuzberg": None}):
            # When sys.modules[key] is None, Python raises ImportError
            with pytest.raises(ImportError, match="kreuzberg is required"):
                KreuzbergParser()

    def test_name_property(self, parser):
        assert parser.name == "kreuzberg"


# ---------------------------------------------------------------------------
# 2. Parse success tests
# ---------------------------------------------------------------------------


class TestParseSuccess:
    @pytest.mark.asyncio
    async def test_parse_file_path(self, parser, mock_kreuzberg, tmp_path):
        test_file = tmp_path / "document.pdf"
        test_file.write_bytes(b"%PDF-1.4 fake content")

        result = await parser.parse(str(test_file))

        assert isinstance(result, DocumentContent)
        assert result.markdown_content == mock_kreuzberg._default_result.content
        assert result.source_format == DocumentFormat.PDF
        mock_kreuzberg.extract_file.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_parse_bytes(self, parser, mock_kreuzberg):
        raw = b"fake pdf bytes"

        result = await parser.parse(raw, format_hint="pdf")

        assert isinstance(result, DocumentContent)
        assert result.markdown_content == mock_kreuzberg._default_result.content
        mock_kreuzberg.extract_bytes.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_parse_sets_parser_used(self, parser, tmp_path):
        test_file = tmp_path / "doc.pdf"
        test_file.write_bytes(b"%PDF")

        result = await parser.parse(str(test_file))

        assert result.parser_used == "kreuzberg"

    @pytest.mark.asyncio
    async def test_parse_maps_metadata(self, parser, mock_kreuzberg, tmp_path):
        test_file = tmp_path / "report.pdf"
        test_file.write_bytes(b"%PDF")

        # Customise the extraction result metadata
        mock_kreuzberg._default_result.metadata = {
            "title": "Annual Report",
            "page_count": 42,
            "language": "de",
            "authors": ["Jane Doe"],
        }
        mock_kreuzberg._default_result.content = "Annual report content for word count."

        result = await parser.parse(str(test_file))

        assert result.metadata.title == "Annual Report"
        assert result.metadata.page_count == 42
        assert result.metadata.language == "de"
        assert result.metadata.author == "Jane Doe"
        assert result.metadata.word_count == 6

    @pytest.mark.asyncio
    async def test_parse_extracts_tables(self, parser, mock_kreuzberg, tmp_path):
        test_file = tmp_path / "data.xlsx"
        test_file.write_bytes(b"fake xlsx")

        table_mock = MagicMock()
        table_mock.markdown = "| A | B |\n| --- | --- |\n| 1 | 2 |"
        table_mock.cells = [["A", "B"], ["1", "2"]]
        mock_kreuzberg._default_result.tables = [table_mock]

        result = await parser.parse(str(test_file))

        assert len(result.tables) == 1
        assert isinstance(result.tables[0], TableData)
        assert result.tables[0].headers == ["A", "B"]
        assert result.tables[0].rows == [["1", "2"]]
        assert "| A | B |" in result.tables[0].markdown

    @pytest.mark.asyncio
    async def test_parse_extracts_links(self, parser, mock_kreuzberg, tmp_path):
        test_file = tmp_path / "links.html"
        test_file.write_bytes(b"<html></html>")

        mock_kreuzberg._default_result.content = (
            "Visit [Example](https://example.com) and https://other.com for more."
        )

        result = await parser.parse(str(test_file))

        assert "https://example.com" in result.links
        assert "https://other.com" in result.links

    @pytest.mark.asyncio
    async def test_parse_deduplicates_links(self, parser, mock_kreuzberg, tmp_path):
        test_file = tmp_path / "dup.html"
        test_file.write_bytes(b"<html></html>")

        mock_kreuzberg._default_result.content = (
            "See [link](https://example.com) and also https://example.com twice."
        )

        result = await parser.parse(str(test_file))

        assert result.links.count("https://example.com") == 1

    @pytest.mark.asyncio
    async def test_parse_records_processing_time(self, parser, tmp_path):
        test_file = tmp_path / "fast.pdf"
        test_file.write_bytes(b"%PDF")

        result = await parser.parse(str(test_file))

        assert result.processing_time_ms >= 0


# ---------------------------------------------------------------------------
# 3. Error handling tests
# ---------------------------------------------------------------------------


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_parse_file_too_large(self, parser, tmp_path):
        big_file = tmp_path / "huge.pdf"
        big_file.write_bytes(b"%PDF-1.4 some content")
        # Set a 0 MB limit so any file exceeds it
        parser.max_file_size_mb = 0

        with pytest.raises(ValueError, match="exceeds limit"):
            await parser.parse(str(big_file))

    @pytest.mark.asyncio
    async def test_parse_timeout(self, parser, mock_kreuzberg, tmp_path):
        test_file = tmp_path / "slow.pdf"
        test_file.write_bytes(b"%PDF")

        # Make extract_file hang so asyncio.wait_for triggers TimeoutError
        async def hang(*args, **kwargs):
            await asyncio.sleep(999)

        mock_kreuzberg.extract_file = hang
        parser.timeout_seconds = 0.01  # very short timeout

        with pytest.raises(TimeoutError):
            await parser.parse(str(test_file))

    @pytest.mark.asyncio
    async def test_parse_extraction_error(self, parser, mock_kreuzberg, tmp_path):
        test_file = tmp_path / "bad.pdf"
        test_file.write_bytes(b"%PDF")

        mock_kreuzberg.extract_file = AsyncMock(side_effect=RuntimeError("extraction failed"))

        with pytest.raises(RuntimeError, match="extraction failed"):
            await parser.parse(str(test_file))


# ---------------------------------------------------------------------------
# 4. Format detection tests
# ---------------------------------------------------------------------------


class TestFormatDetection:
    def test_can_parse_supported_format(self, parser):
        assert parser.can_parse("document.pdf") is True
        assert parser.can_parse("document.docx") is True
        assert parser.can_parse("document.pptx") is True
        assert parser.can_parse("document.xlsx") is True
        assert parser.can_parse("document.html") is True
        assert parser.can_parse("document.epub") is True

    def test_can_parse_fallback_format(self, parser):
        assert parser.can_parse("audio.mp3") is True
        assert parser.can_parse("audio.wav") is True

    def test_can_parse_unknown_format(self, parser):
        assert parser.can_parse("file.xyz") is False
        assert parser.can_parse("file.zzz") is False

    def test_can_parse_with_format_hint(self, parser):
        # Format hint overrides extension detection
        assert parser.can_parse("file.xyz", format_hint="pdf") is True
        assert parser.can_parse("document.pdf", format_hint="xyz") is False

    def test_detect_format_from_extension(self, parser):
        assert parser._detect_format("report.pdf") == "pdf"
        assert parser._detect_format("report.docx") == "docx"
        assert parser._detect_format(Path("slides.pptx")) == "pptx"
        assert parser._detect_format("image.png") == "png"

    def test_detect_format_bytes_returns_unknown(self, parser):
        assert parser._detect_format(b"raw bytes") == "unknown"

    @pytest.mark.asyncio
    async def test_parse_maps_format_to_document_format(self, parser, tmp_path):
        expected_mapping = [
            ("pdf", DocumentFormat.PDF),
            ("docx", DocumentFormat.DOCX),
            ("html", DocumentFormat.HTML),
            ("md", DocumentFormat.MARKDOWN),
            ("png", DocumentFormat.IMAGE),
            ("mp3", DocumentFormat.AUDIO),
        ]
        for ext, expected in expected_mapping:
            f = tmp_path / f"test.{ext}"
            f.write_bytes(b"content")
            result = await parser.parse(str(f))
            assert result.source_format == expected, f"Failed for .{ext}"


# ---------------------------------------------------------------------------
# 5. Configuration tests
# ---------------------------------------------------------------------------


class TestConfiguration:
    def test_custom_max_file_size(self):
        parser = KreuzbergParser(max_file_size_mb=50)
        assert parser.max_file_size_mb == 50

    def test_custom_timeout(self):
        parser = KreuzbergParser(timeout_seconds=60)
        assert parser.timeout_seconds == 60

    def test_default_configuration(self):
        parser = KreuzbergParser()
        assert parser.max_file_size_mb == 100
        assert parser.timeout_seconds == 120
