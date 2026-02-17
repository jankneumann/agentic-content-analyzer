"""Tests for DoclingParser."""

from unittest.mock import MagicMock, patch

import pytest

from src.models.document import DocumentFormat
from src.parsers.docling_parser import DoclingParser


class TestDoclingParser:
    """Tests for DoclingParser functionality."""

    @pytest.fixture
    def parser(self):
        """Create a DoclingParser instance without loading actual Docling."""
        with patch(
            "src.parsers.docling_parser.DoclingParser.converter", new_callable=lambda: MagicMock()
        ):
            parser = DoclingParser(enable_ocr=False)
            # Don't actually load the converter
            parser._converter = MagicMock()
            return parser

    def test_name_property(self, parser):
        """Test parser name is correct."""
        assert parser.name == "docling"

    def test_supported_formats(self, parser):
        """Test supported formats include expected types."""
        assert "pdf" in parser.supported_formats
        assert "docx" in parser.supported_formats
        assert "png" in parser.supported_formats
        assert "jpg" in parser.supported_formats
        assert "jpeg" in parser.supported_formats
        assert "html" in parser.supported_formats
        assert "pptx" in parser.supported_formats
        assert "xlsx" in parser.supported_formats

    def test_fallback_formats(self, parser):
        """Test fallback formats include txt."""
        assert "txt" in parser.fallback_formats

    def test_can_parse_supported_format(self, parser):
        """Test can_parse returns True for supported formats."""
        assert parser.can_parse("document.pdf") is True
        assert parser.can_parse("document.docx") is True
        assert parser.can_parse("image.png") is True
        assert parser.can_parse("image.jpg") is True

    def test_can_parse_fallback_format(self, parser):
        """Test can_parse returns True for fallback formats."""
        assert parser.can_parse("file.txt") is True

    def test_can_parse_unknown_format(self, parser):
        """Test can_parse returns False for unknown formats."""
        assert parser.can_parse("file.xyz") is False
        assert parser.can_parse("document.unknown") is False
        # YouTube is not supported by Docling
        assert parser.can_parse("https://youtube.com/watch?v=abc123") is False

    def test_detect_format_from_extension(self, parser):
        """Test format detection from file extension."""
        assert parser._detect_format("doc.pdf") == "pdf"
        assert parser._detect_format("doc.docx") == "docx"
        assert parser._detect_format("/path/to/image.png") == "png"
        assert parser._detect_format("/path/to/image.JPEG") == "jpeg"

    def test_detect_format_unknown(self, parser):
        """Test unknown format detection."""
        assert parser._detect_format("no_extension") == "unknown"
        assert parser._detect_format(b"raw bytes") == "unknown"

    def test_likely_needs_ocr_scanned_file(self, parser):
        """Test OCR detection for scanned files."""
        assert parser._likely_needs_ocr("document_scanned.pdf") is True
        assert parser._likely_needs_ocr("scan_2024.pdf") is True
        assert parser._likely_needs_ocr("ocr_needed.pdf") is True

    def test_likely_needs_ocr_regular_file(self, parser):
        """Test OCR detection for regular files."""
        assert parser._likely_needs_ocr("document.pdf") is False
        assert parser._likely_needs_ocr("report.docx") is False

    def test_likely_needs_ocr_image_files(self, parser):
        """Test OCR detection for image files."""
        assert parser._likely_needs_ocr("slide.png") is True
        assert parser._likely_needs_ocr("photo.jpg") is True
        assert parser._likely_needs_ocr("diagram.jpeg") is True
        assert parser._likely_needs_ocr("scan.tiff") is True

    def test_extract_links_markdown_format(self, parser):
        """Test link extraction from markdown links."""
        markdown = """
        Here's a link: [Click here](https://example.com/page)
        And another: [Documentation](https://docs.example.com)
        """
        links = parser._extract_links(markdown)
        assert "https://example.com/page" in links
        assert "https://docs.example.com" in links

    def test_extract_links_bare_urls(self, parser):
        """Test link extraction from bare URLs."""
        markdown = """
        Check out https://example.com for more info.
        Also see http://docs.example.org/guide
        """
        links = parser._extract_links(markdown)
        assert "https://example.com" in links
        assert "http://docs.example.org/guide" in links

    def test_extract_links_deduplication(self, parser):
        """Test that duplicate links are removed."""
        markdown = """
        First: [Link](https://example.com)
        Second: [Same](https://example.com)
        Bare: https://example.com
        """
        links = parser._extract_links(markdown)
        # Should only have one copy
        assert links.count("https://example.com") == 1

    def test_cell_to_text_string(self, parser):
        """Test cell conversion for string input."""
        assert parser._cell_to_text("hello") == "hello"
        assert parser._cell_to_text("") == ""

    def test_cell_to_text_none(self, parser):
        """Test cell conversion for None input."""
        assert parser._cell_to_text(None) == ""

    def test_cell_to_text_object_with_text(self, parser):
        """Test cell conversion for object with text attribute."""
        mock_cell = MagicMock()
        mock_cell.text = "cell value"
        assert parser._cell_to_text(mock_cell) == "cell value"

    def test_cell_to_text_object_without_text(self, parser):
        """Test cell conversion for object without text attribute."""
        mock_obj = MagicMock(spec=[])  # No text attribute
        result = parser._cell_to_text(mock_obj)
        assert isinstance(result, str)

    def test_format_map_coverage(self, parser):
        """Test FORMAT_MAP covers all supported formats."""
        for fmt in parser.supported_formats:
            assert fmt in parser.FORMAT_MAP or fmt in {"pptx", "xlsx", "md"}

    def test_init_default_values(self):
        """Test default initialization values."""
        with patch(
            "src.parsers.docling_parser.DoclingParser.converter", new_callable=lambda: MagicMock()
        ):
            parser = DoclingParser()
            assert parser.enable_ocr is False
            assert parser.max_file_size_mb == 100
            assert parser.timeout_seconds == 300

    def test_init_custom_values(self):
        """Test custom initialization values."""
        with patch(
            "src.parsers.docling_parser.DoclingParser.converter", new_callable=lambda: MagicMock()
        ):
            parser = DoclingParser(
                enable_ocr=True,
                max_file_size_mb=50,
                timeout_seconds=120,
            )
            assert parser.enable_ocr is True
            assert parser.max_file_size_mb == 50
            assert parser.timeout_seconds == 120


class TestDoclingParserParsing:
    """Tests for DoclingParser.parse() method with mocked Docling."""

    @pytest.fixture
    def mock_docling_document(self):
        """Create a mock DoclingDocument."""
        mock_doc = MagicMock()
        mock_doc.export_to_markdown.return_value = "# Test Document\n\nThis is test content."
        mock_doc.name = "Test Document"
        mock_doc.tables = []
        mock_doc.pages = [MagicMock(), MagicMock()]  # 2 pages
        mock_doc.origin = MagicMock()
        mock_doc.origin.filename = "test.pdf"
        return mock_doc

    @pytest.fixture
    def mock_conversion_result(self, mock_docling_document):
        """Create a mock ConversionResult."""
        mock_result = MagicMock()
        mock_result.document = mock_docling_document
        return mock_result

    @pytest.mark.asyncio
    async def test_parse_basic_document(self, mock_conversion_result):
        """Test parsing a basic document."""
        with patch("src.parsers.docling_parser.DoclingParser.converter") as mock_converter:
            mock_converter.convert.return_value = mock_conversion_result

            parser = DoclingParser()
            parser._converter = mock_converter

            result = await parser.parse("test.pdf")

            assert result.markdown_content == "# Test Document\n\nThis is test content."
            assert result.parser_used == "docling"
            assert result.source_path == "test.pdf"
            assert result.source_format == DocumentFormat.PDF

    @pytest.mark.asyncio
    async def test_parse_extracts_metadata(self, mock_conversion_result):
        """Test that parsing extracts metadata."""
        with patch("src.parsers.docling_parser.DoclingParser.converter") as mock_converter:
            mock_converter.convert.return_value = mock_conversion_result

            parser = DoclingParser()
            parser._converter = mock_converter

            result = await parser.parse("test.pdf")

            assert result.metadata.title == "Test Document"
            assert result.metadata.page_count == 2

    @pytest.mark.asyncio
    async def test_parse_with_tables(self, mock_conversion_result, mock_docling_document):
        """Test parsing document with tables."""
        # Add a mock table
        mock_table = MagicMock()
        mock_table.export_to_markdown.return_value = "| A | B |\n|---|---|\n| 1 | 2 |"
        mock_table.caption = "Test Table"
        mock_table.data = None  # No structured data
        mock_docling_document.tables = [mock_table]

        with patch("src.parsers.docling_parser.DoclingParser.converter") as mock_converter:
            mock_converter.convert.return_value = mock_conversion_result

            parser = DoclingParser()
            parser._converter = mock_converter

            result = await parser.parse("test.pdf")

            assert len(result.tables) == 1
            assert result.tables[0].caption == "Test Table"
            assert "| A | B |" in result.tables[0].markdown

    @pytest.mark.asyncio
    async def test_parse_processing_time(self, mock_conversion_result):
        """Test that processing time is recorded."""
        with patch("src.parsers.docling_parser.DoclingParser.converter") as mock_converter:
            mock_converter.convert.return_value = mock_conversion_result

            parser = DoclingParser()
            parser._converter = mock_converter

            result = await parser.parse("test.pdf")

            assert result.processing_time_ms >= 0

    @pytest.mark.asyncio
    async def test_parse_ocr_warning(self, mock_conversion_result):
        """Test OCR warning when OCR disabled but likely needed."""
        with patch("src.parsers.docling_parser.DoclingParser.converter") as mock_converter:
            mock_converter.convert.return_value = mock_conversion_result

            parser = DoclingParser(enable_ocr=False)
            parser._converter = mock_converter

            result = await parser.parse("scanned_document.pdf")

            assert len(result.warnings) > 0
            assert "OCR" in result.warnings[0]
