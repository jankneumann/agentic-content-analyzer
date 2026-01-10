"""Tests for ParserRouter."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.document import DocumentContent, DocumentFormat
from src.parsers.router import ParserRouter


class TestParserRouter:
    """Tests for ParserRouter functionality."""

    @pytest.fixture
    def mock_markitdown(self):
        """Create a mock MarkItDown parser."""
        parser = MagicMock()
        parser.name = "markitdown"
        parser.parse = AsyncMock(
            return_value=DocumentContent(
                markdown_content="Markdown content",
                source_path="test.txt",
                source_format=DocumentFormat.TEXT,
                parser_used="markitdown",
            )
        )
        return parser

    @pytest.fixture
    def mock_docling(self):
        """Create a mock Docling parser."""
        parser = MagicMock()
        parser.name = "docling"
        parser.parse = AsyncMock(
            return_value=DocumentContent(
                markdown_content="Docling content",
                source_path="test.pdf",
                source_format=DocumentFormat.PDF,
                parser_used="docling",
            )
        )
        return parser

    @pytest.fixture
    def router_markitdown_only(self, mock_markitdown):
        """Create router with only MarkItDown."""
        return ParserRouter(markitdown_parser=mock_markitdown)

    @pytest.fixture
    def router_both_parsers(self, mock_markitdown, mock_docling):
        """Create router with both parsers."""
        return ParserRouter(
            markitdown_parser=mock_markitdown,
            docling_parser=mock_docling,
        )

    def test_available_parsers_markitdown_only(self, router_markitdown_only):
        """Test available parsers with only MarkItDown."""
        assert "markitdown" in router_markitdown_only.available_parsers
        assert "docling" not in router_markitdown_only.available_parsers

    def test_available_parsers_both(self, router_both_parsers):
        """Test available parsers with both enabled."""
        assert "markitdown" in router_both_parsers.available_parsers
        assert "docling" in router_both_parsers.available_parsers

    def test_has_docling_false(self, router_markitdown_only):
        """Test has_docling is False when not available."""
        assert router_markitdown_only.has_docling is False

    def test_has_docling_true(self, router_both_parsers):
        """Test has_docling is True when available."""
        assert router_both_parsers.has_docling is True

    def test_detect_format_youtube(self, router_markitdown_only):
        """Test YouTube URL detection."""
        assert (
            router_markitdown_only._detect_format("https://youtube.com/watch?v=test") == "youtube"
        )
        assert router_markitdown_only._detect_format("https://youtu.be/test") == "youtube"

    def test_detect_format_extension(self, router_markitdown_only):
        """Test format detection from extension."""
        assert router_markitdown_only._detect_format("doc.pdf") == "pdf"
        assert router_markitdown_only._detect_format("doc.docx") == "docx"
        assert router_markitdown_only._detect_format("/path/to/file.pptx") == "pptx"

    def test_likely_needs_ocr_true(self, router_markitdown_only):
        """Test OCR indicator detection."""
        assert router_markitdown_only._likely_needs_ocr("scanned_document.pdf") is True
        assert router_markitdown_only._likely_needs_ocr("document_scan.pdf") is True
        assert router_markitdown_only._likely_needs_ocr("ocr_required.pdf") is True

    def test_likely_needs_ocr_false(self, router_markitdown_only):
        """Test normal files don't trigger OCR."""
        assert router_markitdown_only._likely_needs_ocr("regular_document.pdf") is False
        assert router_markitdown_only._likely_needs_ocr("report.pdf") is False

    def test_route_youtube_to_markitdown(self, router_both_parsers, mock_markitdown):
        """Test YouTube always routes to MarkItDown."""
        parser = router_both_parsers.route("https://youtube.com/watch?v=test")
        assert parser.name == "markitdown"

    def test_route_docx_to_markitdown(self, router_both_parsers, mock_markitdown):
        """Test DOCX routes to MarkItDown."""
        parser = router_both_parsers.route("document.docx")
        assert parser.name == "markitdown"

    def test_route_pdf_to_docling(self, router_both_parsers, mock_docling):
        """Test PDF routes to Docling when available."""
        parser = router_both_parsers.route("report.pdf")
        assert parser.name == "docling"

    def test_route_pdf_fallback_to_markitdown(self, router_markitdown_only, mock_markitdown):
        """Test PDF routes to MarkItDown when Docling unavailable."""
        parser = router_markitdown_only.route("report.pdf")
        assert parser.name == "markitdown"

    def test_route_ocr_to_docling(self, router_both_parsers, mock_docling):
        """Test OCR-needed files route to Docling."""
        parser = router_both_parsers.route("scanned_document.pdf")
        assert parser.name == "docling"

    def test_route_ocr_explicit(self, router_both_parsers, mock_docling):
        """Test explicit OCR request routes to Docling."""
        parser = router_both_parsers.route("document.pdf", ocr_needed=True)
        assert parser.name == "docling"

    def test_route_prefer_structured(self, router_both_parsers, mock_docling):
        """Test prefer_structured routes PDF to Docling."""
        parser = router_both_parsers.route("report.pdf", prefer_structured=True)
        assert parser.name == "docling"

    def test_route_with_format_hint(self, router_both_parsers, mock_markitdown):
        """Test format hint overrides detection."""
        # File with PDF extension but hint says it's HTML
        parser = router_both_parsers.route("file.pdf", format_hint="html")
        assert parser.name == "markitdown"

    def test_route_unknown_format_to_default(self, router_markitdown_only, mock_markitdown):
        """Test unknown format routes to default parser."""
        parser = router_markitdown_only.route("file.unknown")
        assert parser.name == "markitdown"

    @pytest.mark.asyncio
    async def test_parse_routes_correctly(self, router_both_parsers, mock_markitdown):
        """Test parse method routes and parses."""
        result = await router_both_parsers.parse("document.docx")

        mock_markitdown.parse.assert_called_once()
        assert result.parser_used == "markitdown"

    @pytest.mark.asyncio
    async def test_parse_pdf_uses_docling(self, router_both_parsers, mock_docling):
        """Test parse routes PDF to Docling."""
        result = await router_both_parsers.parse("report.pdf")

        mock_docling.parse.assert_called_once()
        assert result.parser_used == "docling"

    @pytest.mark.asyncio
    async def test_parse_bytes_uses_default(self, router_markitdown_only, mock_markitdown):
        """Test parse with bytes uses default parser."""
        mock_markitdown.parse.return_value = DocumentContent(
            markdown_content="Content from bytes",
            source_path="stream",
            source_format=DocumentFormat.UNKNOWN,
            parser_used="markitdown",
        )

        result = await router_markitdown_only.parse(b"raw bytes")

        mock_markitdown.parse.assert_called_once()


class TestParserRouterRoutingTable:
    """Tests for routing table configuration."""

    def test_routing_table_completeness(self):
        """Test routing table has expected entries."""
        table = ParserRouter.ROUTING_TABLE

        # MarkItDown formats
        assert table.get("docx") == "markitdown"
        assert table.get("pptx") == "markitdown"
        assert table.get("xlsx") == "markitdown"
        assert table.get("html") == "markitdown"
        assert table.get("mp3") == "markitdown"
        assert table.get("epub") == "markitdown"

        # YouTube - specialized parser
        assert table.get("youtube") == "youtube"

        # Docling formats
        assert table.get("pdf") == "docling"
        assert table.get("png") == "docling"
        assert table.get("jpg") == "docling"

    def test_ocr_indicators(self):
        """Test OCR required indicators."""
        indicators = ParserRouter.OCR_REQUIRED_INDICATORS

        assert "scanned" in indicators
        assert "scan" in indicators
        assert "ocr" in indicators
