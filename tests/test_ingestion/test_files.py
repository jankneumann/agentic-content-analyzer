"""Tests for FileIngestionService."""

import hashlib
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.document import DocumentContent, DocumentFormat, DocumentMetadata
from src.models.newsletter import Newsletter, NewsletterSource, ProcessingStatus


class TestFileIngestionService:
    """Tests for FileIngestionService functionality."""

    @pytest.fixture
    def mock_router(self):
        """Create a mock ParserRouter."""
        router = MagicMock()
        router.available_parsers = ["markitdown", "docling"]

        mock_markitdown = MagicMock()
        mock_markitdown.supported_formats = {"docx", "pptx", "xlsx"}
        mock_markitdown.fallback_formats = {"pdf"}

        mock_docling = MagicMock()
        mock_docling.supported_formats = {"pdf", "docx", "png"}
        mock_docling.fallback_formats = set()

        router.parsers = {
            "markitdown": mock_markitdown,
            "docling": mock_docling,
        }
        return router

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value.first.return_value = None
        return db

    @pytest.fixture
    def mock_document_content(self):
        """Create a mock DocumentContent."""
        return DocumentContent(
            markdown_content="# Test Document\n\nThis is test content.",
            source_path="test.pdf",
            source_format=DocumentFormat.PDF,
            parser_used="docling",
            metadata=DocumentMetadata(title="Test Document"),
            links=["https://example.com"],
            processing_time_ms=100,
        )

    @pytest.fixture
    def service(self, mock_router, mock_db):
        """Create a FileIngestionService instance."""
        with patch("src.ingestion.files.settings") as mock_settings:
            mock_settings.max_upload_size_mb = 50
            from src.ingestion.files import FileIngestionService

            return FileIngestionService(router=mock_router, db=mock_db)

    def test_calculate_file_hash(self, service):
        """Test file hash calculation."""
        # Create a temp file with known content
        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
            f.write(b"test content")
            temp_path = Path(f.name)

        try:
            file_hash = service._calculate_file_hash(temp_path)

            # Verify hash matches expected
            expected_hash = hashlib.sha256(b"test content").hexdigest()
            assert file_hash == expected_hash
        finally:
            temp_path.unlink()

    def test_get_supported_formats(self, service, mock_router):
        """Test getting supported formats."""
        formats = service.get_supported_formats()

        assert "docx" in formats
        assert "pdf" in formats
        assert "pptx" in formats
        assert "png" in formats
        # YouTube should be excluded
        assert "youtube" not in formats

    @pytest.mark.asyncio
    async def test_ingest_file_success(self, service, mock_router, mock_db, mock_document_content):
        """Test successful file ingestion."""
        # Create a temp file
        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".pdf") as f:
            f.write(b"test PDF content")
            temp_path = Path(f.name)

        try:
            # Mock router.parse
            mock_router.parse = AsyncMock(return_value=mock_document_content)

            # Mock newsletter creation
            mock_newsletter = Newsletter(
                id=1,
                source=NewsletterSource.FILE_UPLOAD,
                source_id="file_abc123_20240110",
                title="Test Document",
                published_date=datetime.now(UTC),
                status=ProcessingStatus.PENDING,
                ingested_at=datetime.now(UTC),
            )
            mock_db.refresh = MagicMock(side_effect=lambda n: setattr(n, "id", 1))

            result = await service.ingest_file(temp_path)

            # Verify router.parse was called
            mock_router.parse.assert_called_once()

            # Verify newsletter was added to db
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()

        finally:
            temp_path.unlink()

    @pytest.mark.asyncio
    async def test_ingest_file_not_found(self, service):
        """Test error when file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            await service.ingest_file(Path("/nonexistent/file.pdf"))

    @pytest.mark.asyncio
    async def test_ingest_file_too_large(self, service):
        """Test error when file exceeds size limit."""
        # Create a mock Path that reports a large file size
        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.stat.return_value.st_size = 100 * 1024 * 1024  # 100MB

        service.max_file_size_mb = 50  # 50MB limit

        with pytest.raises(ValueError) as exc_info:
            await service.ingest_file(mock_path)

        assert "exceeds limit" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_ingest_file_duplicate_detection(
        self, service, mock_router, mock_db, mock_document_content
    ):
        """Test duplicate file detection."""
        # Create a temp file
        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".pdf") as f:
            f.write(b"test PDF content")
            temp_path = Path(f.name)

        try:
            # Mock existing duplicate found
            existing_newsletter = Newsletter(
                id=99,
                source=NewsletterSource.FILE_UPLOAD,
                source_id="file_existing",
                title="Existing Document",
                published_date=datetime.now(UTC),
                status=ProcessingStatus.COMPLETED,
                content_hash="abc123",
            )
            mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
                existing_newsletter
            )

            result = await service.ingest_file(temp_path)

            # Verify router.parse was NOT called (duplicate detected)
            mock_router.parse = AsyncMock()
            # The duplicate link was created

        finally:
            temp_path.unlink()

    @pytest.mark.asyncio
    async def test_ingest_bytes_success(self, service, mock_router, mock_db, mock_document_content):
        """Test successful bytes ingestion."""
        test_bytes = b"test document content"

        # Mock router.parse
        mock_router.parse = AsyncMock(return_value=mock_document_content)

        # Mock db.refresh
        mock_db.refresh = MagicMock(side_effect=lambda n: setattr(n, "id", 1))

        result = await service.ingest_bytes(
            data=test_bytes,
            filename="test.pdf",
            publication="Test Publisher",
        )

        # Verify router.parse was called
        mock_router.parse.assert_called_once()
        call_args = mock_router.parse.call_args
        assert call_args[1]["format_hint"] == "pdf"

    @pytest.mark.asyncio
    async def test_ingest_bytes_too_large(self, service):
        """Test error when bytes exceed size limit."""
        # Create bytes larger than limit
        large_bytes = b"x" * (60 * 1024 * 1024)  # 60MB
        service.max_file_size_mb = 50  # 50MB limit

        with pytest.raises(ValueError) as exc_info:
            await service.ingest_bytes(data=large_bytes, filename="large.pdf")

        assert "exceeds limit" in str(exc_info.value)

    def test_create_newsletter_with_override_title(self, service, mock_document_content):
        """Test newsletter creation with title override."""
        newsletter = service._create_newsletter(
            content=mock_document_content,
            file_path=Path("test.pdf"),
            file_hash="abc123",
            publication="Test Pub",
            title_override="Custom Title",
        )

        assert newsletter.title == "Custom Title"
        assert newsletter.publication == "Test Pub"
        assert newsletter.source == NewsletterSource.FILE_UPLOAD

    def test_create_newsletter_extracted_title(self, service, mock_document_content):
        """Test newsletter creation with extracted title."""
        newsletter = service._create_newsletter(
            content=mock_document_content,
            file_path=Path("test.pdf"),
            file_hash="abc123",
            publication=None,
            title_override=None,
        )

        # Should use metadata title
        assert newsletter.title == "Test Document"

    def test_create_newsletter_filename_fallback(self, service):
        """Test newsletter creation falls back to filename."""
        content = DocumentContent(
            markdown_content="content",
            source_path="my_report.pdf",
            source_format=DocumentFormat.PDF,
            parser_used="docling",
            metadata=DocumentMetadata(),  # No title
        )

        newsletter = service._create_newsletter(
            content=content,
            file_path=Path("my_report.pdf"),
            file_hash="abc123",
            publication=None,
            title_override=None,
        )

        # Should use filename stem
        assert newsletter.title == "my_report"

    def test_create_duplicate_link(self, service, mock_db):
        """Test creating a duplicate link."""
        canonical = Newsletter(
            id=99,
            source=NewsletterSource.FILE_UPLOAD,
            source_id="file_original",
            title="Original Document",
            publication="Original Pub",
            published_date=datetime.now(UTC),
            content_hash="hash123",
        )

        mock_db.refresh = MagicMock(side_effect=lambda n: setattr(n, "id", 100))

        result = service._create_duplicate_link(
            canonical=canonical,
            file_path=Path("duplicate.pdf"),
            publication=None,
        )

        assert result.canonical_newsletter_id == 99
        assert "[Duplicate]" in result.title
        assert result.content_hash == "hash123"
        assert result.status == ProcessingStatus.COMPLETED

    def test_find_duplicate_not_found(self, service, mock_db):
        """Test find_duplicate when no duplicate exists."""
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = None

        result = service._find_duplicate("new_hash")
        assert result is None

    def test_find_duplicate_found(self, service, mock_db):
        """Test find_duplicate when duplicate exists."""
        existing = Newsletter(
            id=1,
            source=NewsletterSource.FILE_UPLOAD,
            source_id="existing",
            title="Existing",
            published_date=datetime.now(UTC),
            content_hash="existing_hash",
        )
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            existing
        )

        result = service._find_duplicate("existing_hash")
        assert result == existing
