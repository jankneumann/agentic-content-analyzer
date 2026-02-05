"""Tests for document content models."""

from src.models.document import (
    DocumentContent,
    DocumentFormat,
    DocumentMetadata,
    TableData,
)


class TestDocumentFormat:
    """Tests for DocumentFormat enum."""

    def test_all_formats_present(self):
        """Test all expected formats are defined."""
        formats = [f.value for f in DocumentFormat]

        assert "pdf" in formats
        assert "docx" in formats
        assert "pptx" in formats
        assert "xlsx" in formats
        assert "html" in formats
        assert "md" in formats
        assert "youtube" in formats
        assert "audio" in formats
        assert "video" in formats
        assert "image" in formats
        assert "unknown" in formats

    def test_format_string_values(self):
        """Test format enum values are lowercase strings."""
        assert DocumentFormat.PDF.value == "pdf"
        assert DocumentFormat.YOUTUBE.value == "youtube"
        assert DocumentFormat.UNKNOWN.value == "unknown"


class TestTableData:
    """Tests for TableData model."""

    def test_minimal_table(self):
        """Test creating a table with just markdown."""
        table = TableData(markdown="| A | B |\n|---|---|\n| 1 | 2 |")

        assert table.markdown == "| A | B |\n|---|---|\n| 1 | 2 |"
        assert table.headers == []
        assert table.rows == []
        assert table.caption is None

    def test_full_table(self):
        """Test creating a fully populated table."""
        table = TableData(
            caption="Sales Data",
            headers=["Product", "Revenue"],
            rows=[["Widget", "$100"], ["Gadget", "$200"]],
            markdown="| Product | Revenue |\n|---|---|\n| Widget | $100 |\n| Gadget | $200 |",
        )

        assert table.caption == "Sales Data"
        assert table.headers == ["Product", "Revenue"]
        assert len(table.rows) == 2
        assert table.rows[0] == ["Widget", "$100"]


class TestDocumentMetadata:
    """Tests for DocumentMetadata model."""

    def test_empty_metadata(self):
        """Test creating empty metadata."""
        meta = DocumentMetadata()

        assert meta.title is None
        assert meta.author is None
        assert meta.page_count is None

    def test_full_metadata(self):
        """Test creating fully populated metadata."""
        from datetime import datetime

        meta = DocumentMetadata(
            title="Annual Report",
            author="John Doe",
            created_date=datetime(2025, 1, 1),
            page_count=50,
            word_count=15000,
            language="en",
        )

        assert meta.title == "Annual Report"
        assert meta.author == "John Doe"
        assert meta.page_count == 50


class TestDocumentContent:
    """Tests for DocumentContent model."""

    def test_minimal_content(self):
        """Test creating content with required fields only."""
        content = DocumentContent(
            markdown_content="# Hello World",
            source_path="/path/to/doc.pdf",
            source_format=DocumentFormat.PDF,
            parser_used="markitdown",
        )

        assert content.markdown_content == "# Hello World"
        assert content.source_path == "/path/to/doc.pdf"
        assert content.source_format == DocumentFormat.PDF
        assert content.parser_used == "markitdown"

    def test_default_values(self):
        """Test default values are set correctly."""
        content = DocumentContent(
            markdown_content="Content",
            source_path="file.txt",
            source_format=DocumentFormat.TEXT,
            parser_used="markitdown",
        )

        assert content.metadata is not None
        assert content.tables == []
        assert content.links == []
        assert content.warnings == []
        assert content.processing_time_ms == 0

    def test_full_content(self):
        """Test creating fully populated content."""
        content = DocumentContent(
            markdown_content="# Report\n\nSome text with [link](https://example.com)",
            source_path="/path/to/report.pdf",
            source_format=DocumentFormat.PDF,
            parser_used="docling",
            metadata=DocumentMetadata(title="Report", page_count=10),
            tables=[TableData(markdown="| A | B |", headers=["A", "B"], rows=[["1", "2"]])],
            links=["https://example.com"],
            processing_time_ms=150,
            warnings=["Table structure may be incomplete"],
        )

        assert content.metadata.title == "Report"
        assert len(content.tables) == 1
        assert len(content.links) == 1
        assert content.processing_time_ms == 150
        assert len(content.warnings) == 1

    def test_to_newsletter_content(self):
        """Test conversion to newsletter fields."""
        content = DocumentContent(
            markdown_content="# Newsletter Content\n\nImportant information here.",
            source_path="newsletter.html",
            source_format=DocumentFormat.HTML,
            parser_used="markitdown",
            links=["https://example.com", "https://docs.example.com"],
        )

        raw_text, raw_html, links = content.to_newsletter_content()

        assert raw_text == content.markdown_content
        assert raw_html == content.markdown_content  # Markdown is valid HTML
        assert links == ["https://example.com", "https://docs.example.com"]

    def test_to_newsletter_content_empty_links(self):
        """Test conversion with no links."""
        content = DocumentContent(
            markdown_content="Simple content",
            source_path="doc.txt",
            source_format=DocumentFormat.TEXT,
            parser_used="markitdown",
        )

        raw_text, _raw_html, links = content.to_newsletter_content()

        assert raw_text == "Simple content"
        assert links == []


class TestContentSourceEnum:
    """Tests for ContentSource enum."""

    def test_source_types(self):
        """Test FILE_UPLOAD and YOUTUBE source types."""
        from src.models.content import ContentSource

        assert ContentSource.FILE_UPLOAD.value == "file_upload"
        assert ContentSource.YOUTUBE.value == "youtube"

    def test_all_source_types(self):
        """Test all source types are present."""
        from src.models.content import ContentSource

        sources = [s.value for s in ContentSource]

        assert "gmail" in sources
        assert "rss" in sources
        assert "file_upload" in sources
        assert "youtube" in sources
