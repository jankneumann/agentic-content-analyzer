"""Tests for MarkItDownParser."""

import pytest

from src.models.document import DocumentFormat
from src.parsers.markitdown_parser import MarkItDownParser


class TestMarkItDownParser:
    """Tests for MarkItDownParser functionality."""

    @pytest.fixture
    def parser(self):
        """Create a MarkItDownParser instance."""
        return MarkItDownParser()

    def test_name_property(self, parser):
        """Test parser name is correct."""
        assert parser.name == "markitdown"

    def test_supported_formats(self, parser):
        """Test supported formats include expected types."""
        assert "docx" in parser.supported_formats
        assert "pptx" in parser.supported_formats
        assert "xlsx" in parser.supported_formats
        assert "html" in parser.supported_formats
        assert "youtube" in parser.supported_formats
        assert "epub" in parser.supported_formats

    def test_fallback_formats(self, parser):
        """Test fallback formats include PDF."""
        assert "pdf" in parser.fallback_formats

    def test_can_parse_supported_format(self, parser):
        """Test can_parse returns True for supported formats."""
        assert parser.can_parse("document.docx") is True
        assert parser.can_parse("presentation.pptx") is True
        assert parser.can_parse("spreadsheet.xlsx") is True

    def test_can_parse_fallback_format(self, parser):
        """Test can_parse returns True for fallback formats."""
        assert parser.can_parse("report.pdf") is True

    def test_can_parse_youtube_url(self, parser):
        """Test can_parse returns True for YouTube URLs."""
        assert parser.can_parse("https://youtube.com/watch?v=abc123") is True
        assert parser.can_parse("https://youtu.be/abc123") is True

    def test_can_parse_unknown_format(self, parser):
        """Test can_parse returns False for unknown formats."""
        assert parser.can_parse("file.xyz") is False
        assert parser.can_parse("document.unknown") is False

    def test_detect_format_from_extension(self, parser):
        """Test format detection from file extension."""
        assert parser._detect_format("doc.pdf") == "pdf"
        assert parser._detect_format("doc.docx") == "docx"
        assert parser._detect_format("/path/to/file.pptx") == "pptx"

    def test_detect_format_youtube(self, parser):
        """Test YouTube URL detection."""
        assert parser._detect_format("https://youtube.com/watch?v=test") == "youtube"
        assert parser._detect_format("https://www.youtube.com/watch?v=test") == "youtube"
        assert parser._detect_format("https://youtu.be/test") == "youtube"

    def test_detect_format_unknown(self, parser):
        """Test unknown format detection."""
        assert parser._detect_format("no_extension") == "unknown"
        assert parser._detect_format(b"raw bytes") == "unknown"

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
        Check out https://example.com/bare-url for more info.
        Also see http://another.com/page here.
        """
        links = parser._extract_links(markdown)
        assert "https://example.com/bare-url" in links
        assert "http://another.com/page" in links

    def test_extract_links_deduplication(self, parser):
        """Test that duplicate links are removed."""
        markdown = """
        Link: [First](https://example.com)
        Same link: [Second](https://example.com)
        Bare: https://example.com
        """
        links = parser._extract_links(markdown)
        assert links.count("https://example.com") == 1

    def test_extract_links_preserves_order(self, parser):
        """Test that link order is preserved."""
        markdown = """
        [First](https://first.com)
        [Second](https://second.com)
        [Third](https://third.com)
        """
        links = parser._extract_links(markdown)
        assert links == ["https://first.com", "https://second.com", "https://third.com"]

    def test_format_map_coverage(self, parser):
        """Test FORMAT_MAP includes expected mappings."""
        assert parser.FORMAT_MAP["pdf"] == DocumentFormat.PDF
        assert parser.FORMAT_MAP["docx"] == DocumentFormat.DOCX
        assert parser.FORMAT_MAP["youtube"] == DocumentFormat.YOUTUBE
        assert parser.FORMAT_MAP["mp3"] == DocumentFormat.AUDIO
        assert parser.FORMAT_MAP["msg"] == DocumentFormat.OUTLOOK_MSG

    @pytest.mark.asyncio
    async def test_parse_plain_text(self, parser, tmp_path):
        """Test parsing a plain text file."""
        # Create a temp text file
        text_file = tmp_path / "test.txt"
        text_file.write_text("Hello, this is a test document.\n\nWith multiple paragraphs.")

        result = await parser.parse(str(text_file))

        assert result.parser_used == "markitdown"
        assert result.source_format == DocumentFormat.TEXT
        assert "Hello" in result.markdown_content
        assert "multiple paragraphs" in result.markdown_content

    @pytest.mark.asyncio
    async def test_parse_markdown_file(self, parser, tmp_path):
        """Test parsing a markdown file."""
        md_file = tmp_path / "test.md"
        md_file.write_text("# Title\n\nSome **bold** text and a [link](https://example.com)")

        result = await parser.parse(str(md_file))

        assert result.parser_used == "markitdown"
        assert result.source_format == DocumentFormat.MARKDOWN
        assert "Title" in result.markdown_content
        assert "https://example.com" in result.links

    @pytest.mark.asyncio
    async def test_parse_html_file(self, parser, tmp_path):
        """Test parsing an HTML file."""
        html_file = tmp_path / "test.html"
        html_file.write_text("<html><body><h1>Header</h1><p>Paragraph</p></body></html>")

        result = await parser.parse(str(html_file))

        assert result.parser_used == "markitdown"
        assert result.source_format == DocumentFormat.HTML
        assert "Header" in result.markdown_content
        assert "Paragraph" in result.markdown_content

    @pytest.mark.asyncio
    async def test_parse_with_format_hint(self, parser, tmp_path):
        """Test parsing with explicit format hint overrides detected format."""
        # Create a text file but use format_hint to specify it as markdown
        text_file = tmp_path / "test.txt"
        text_file.write_text("# Header\n\nPlain text content")

        result = await parser.parse(str(text_file), format_hint="md")

        # Format hint should override the detected .txt extension
        assert result.source_format == DocumentFormat.MARKDOWN

    @pytest.mark.asyncio
    async def test_parse_processing_time(self, parser, tmp_path):
        """Test that processing time is recorded."""
        text_file = tmp_path / "test.txt"
        text_file.write_text("Test content")

        result = await parser.parse(str(text_file))

        assert result.processing_time_ms >= 0
