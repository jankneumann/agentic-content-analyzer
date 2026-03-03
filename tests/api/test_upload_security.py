from unittest.mock import AsyncMock, patch

from src.api.upload_routes import (
    FILE_SIGNATURES,
    _validate_file_signature,
    _validate_mime_type,
)
from src.models.content import Content, ContentStatus

# ============================================================================
# Unit Tests: File Signature (Magic Bytes) Validation
# ============================================================================


class TestValidateFileSignature:
    """Unit tests for _validate_file_signature()."""

    def test_valid_pdf(self):
        """Valid PDF magic bytes should pass."""
        data = b"%PDF-1.4 rest of the file"
        assert _validate_file_signature(data, "pdf") is None

    def test_invalid_pdf(self):
        """Non-PDF data with .pdf extension should fail."""
        data = b"Hello, this is not a PDF"
        result = _validate_file_signature(data, "pdf")
        assert result is not None
        assert ".pdf" in result

    def test_valid_docx_zip_based(self):
        """Valid DOCX (ZIP-based) magic bytes should pass."""
        data = b"PK\x03\x04" + b"\x00" * 100
        assert _validate_file_signature(data, "docx") is None

    def test_valid_png(self):
        """Valid PNG magic bytes should pass."""
        data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        assert _validate_file_signature(data, "png") is None

    def test_valid_jpeg(self):
        """Valid JPEG magic bytes should pass."""
        data = b"\xff\xd8\xff" + b"\x00" * 100
        assert _validate_file_signature(data, "jpg") is None

    def test_valid_gif87a(self):
        """Valid GIF87a magic bytes should pass."""
        data = b"GIF87a" + b"\x00" * 100
        assert _validate_file_signature(data, "gif") is None

    def test_valid_gif89a(self):
        """Valid GIF89a magic bytes should pass."""
        data = b"GIF89a" + b"\x00" * 100
        assert _validate_file_signature(data, "gif") is None

    def test_valid_html_doctype(self):
        """HTML with DOCTYPE should pass."""
        data = b"<!DOCTYPE html><html><body>Hello</body></html>"
        assert _validate_file_signature(data, "html") is None

    def test_valid_html_tag(self):
        """HTML with <html> tag should pass."""
        data = b"<html><body>Hello</body></html>"
        assert _validate_file_signature(data, "html") is None

    def test_unknown_extension_passes(self):
        """Unknown extensions (not in FILE_SIGNATURES) should pass."""
        assert _validate_file_signature(b"any content", "txt") is None
        assert _validate_file_signature(b"any content", "md") is None
        assert _validate_file_signature(b"any content", "csv") is None

    def test_empty_data_fails_for_known_extension(self):
        """Empty data should fail for extensions with expected signatures."""
        result = _validate_file_signature(b"", "pdf")
        assert result is not None

    def test_exe_disguised_as_pdf(self):
        """Executable disguised as PDF should be rejected."""
        # MZ header (PE executable)
        data = b"MZ\x90\x00" + b"\x00" * 100
        result = _validate_file_signature(data, "pdf")
        assert result is not None
        assert ".pdf" in result

    def test_all_signatures_have_entries(self):
        """Verify FILE_SIGNATURES covers expected formats."""
        expected = {
            "pdf",
            "docx",
            "xlsx",
            "pptx",
            "zip",
            "png",
            "jpg",
            "jpeg",
            "gif",
            "html",
            "htm",
            "wav",
            "mp3",
            "epub",
            "msg",
        }
        assert expected == set(FILE_SIGNATURES.keys())


# ============================================================================
# Unit Tests: MIME Type Cross-Check
# ============================================================================


class TestValidateMimeType:
    """Unit tests for _validate_mime_type()."""

    def test_matching_mime_passes(self):
        """Matching MIME type and extension should pass."""
        assert _validate_mime_type("application/pdf", "pdf") is None
        assert _validate_mime_type("image/png", "png") is None
        assert _validate_mime_type("image/jpeg", "jpg") is None
        assert _validate_mime_type("text/html", "html") is None

    def test_mismatched_mime_fails(self):
        """MIME type contradicting extension should fail."""
        result = _validate_mime_type("image/png", "pdf")
        assert result is not None
        assert "application/pdf" in result

    def test_octet_stream_bypasses(self):
        """application/octet-stream should always pass (generic fallback)."""
        assert _validate_mime_type("application/octet-stream", "pdf") is None
        assert _validate_mime_type("application/octet-stream", "png") is None

    def test_none_content_type_bypasses(self):
        """None Content-Type should always pass."""
        assert _validate_mime_type(None, "pdf") is None

    def test_empty_content_type_bypasses(self):
        """Empty string Content-Type should always pass."""
        assert _validate_mime_type("", "pdf") is None

    def test_unknown_extension_bypasses(self):
        """Unknown extension (not in EXTENSION_MIME_MAP) should pass."""
        assert _validate_mime_type("application/weird", "xyz") is None

    def test_mime_with_charset_parameter(self):
        """MIME type with parameters (charset) should be stripped correctly."""
        assert _validate_mime_type("text/html; charset=utf-8", "html") is None

    def test_docx_with_zip_mime_passes(self):
        """DOCX uploaded as application/zip should pass (it's ZIP-based)."""
        assert _validate_mime_type("application/zip", "docx") is None

    def test_docx_with_correct_mime_passes(self):
        """DOCX with full MIME type should pass."""
        mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        assert _validate_mime_type(mime, "docx") is None


# ============================================================================
# Integration Tests: Upload Size
# ============================================================================


def test_upload_file_too_large(client):
    """Test that uploading a file larger than the limit returns 413."""
    # Mock settings.max_upload_size_mb to be small (e.g. 1MB)
    with patch("src.config.settings.settings.max_upload_size_mb", 1):
        # Create a file content larger than 1MB (e.g. 1.5MB)
        large_content = b"a" * (1024 * 1024 + 512 * 1024)

        files = {"file": ("large_file.txt", large_content, "text/plain")}

        response = client.post("/api/v1/documents/upload", files=files)

        assert response.status_code == 413
        assert "exceeds limit" in response.json()["detail"]


def test_upload_file_within_limit(client):
    """Test that uploading a file within the limit is accepted."""
    # Mock settings.max_upload_size_mb to be 2MB
    with patch("src.config.settings.settings.max_upload_size_mb", 2):
        # Create a file content smaller than 2MB (e.g. 1MB)
        content = b"a" * (1024 * 1024)

        files = {"file": ("ok_file.txt", content, "text/plain")}

        with patch("src.api.upload_routes.FileContentIngestionService") as mock_service:
            mock_instance = mock_service.return_value

            # Make ingest_file return a mock content object
            mock_content = Content(
                id=1,
                title="Test",
                status=ContentStatus.PARSED,
                source_id="test",
                source_type="file_upload",
            )
            mock_instance.ingest_file = AsyncMock(return_value=mock_content)

            response = client.post("/api/v1/documents/upload", files=files)

            assert response.status_code == 200
            # Verify ingest_file was called (implies temp file creation worked)
            assert mock_instance.ingest_file.called
            # Verify arguments
            _, kwargs = mock_instance.ingest_file.call_args
            assert str(kwargs["file_path"]).endswith(".txt")
            assert kwargs["format_hint"] == "txt"


# ============================================================================
# Integration Tests: File Signature Validation via API
# ============================================================================


def test_upload_pdf_with_wrong_magic_bytes_returns_415(client):
    """Upload a .pdf file whose content isn't actually PDF → 415."""
    fake_pdf = b"This is plain text, not a PDF"
    files = {"file": ("document.pdf", fake_pdf, "application/pdf")}

    response = client.post("/api/v1/documents/upload", files=files)

    assert response.status_code == 415
    assert "does not match expected format" in response.json()["detail"]


def test_upload_png_with_wrong_magic_bytes_returns_415(client):
    """Upload a .png file whose content is actually JPEG → 415."""
    jpeg_data = b"\xff\xd8\xff" + b"\x00" * 100
    files = {"file": ("image.png", jpeg_data, "image/png")}

    response = client.post("/api/v1/documents/upload", files=files)

    assert response.status_code == 415
    assert ".png" in response.json()["detail"]


def test_upload_unknown_extension_skips_signature_check(client):
    """Upload with an unknown extension should skip magic bytes check."""
    content = b"any content whatsoever"
    files = {"file": ("data.txt", content, "text/plain")}

    # txt is not in FILE_SIGNATURES, so it should pass magic bytes check
    # but may be rejected by format support check — we only care about not getting 415
    # from magic bytes. Use patch to bypass format check.
    with patch("src.api.upload_routes.FileContentIngestionService") as mock_service:
        mock_instance = mock_service.return_value
        mock_content = Content(
            id=1,
            title="Test",
            status=ContentStatus.PARSED,
            source_id="test",
            source_type="file_upload",
        )
        mock_instance.ingest_file = AsyncMock(return_value=mock_content)

        response = client.post("/api/v1/documents/upload", files=files)
        # Should not be 415 from signature check
        assert (
            response.status_code != 415
            or "does not match expected format" not in response.json().get("detail", "")
        )


def test_upload_no_extension_is_rejected(client):
    """Test that uploading a file with no extension (format="unknown") is REJECTED.

    Security regression test: Previously, "unknown" format bypassed the supported format check,
    allowing arbitrary files to be uploaded. This test ensures the fix works.
    """
    with patch("src.api.upload_routes.FileContentIngestionService") as mock_service:
        mock_instance = mock_service.return_value
        mock_content = Content(
            id=1,
            title="Exploit",
            status=ContentStatus.PARSED,
            source_id="exploit",
            source_type="file_upload",
        )
        mock_instance.ingest_file = AsyncMock(return_value=mock_content)

        # File with NO extension -> format_ext="unknown"
        content = b"#!/bin/bash\necho 'This is a script'"
        files = {"file": ("malicious_script", content, "application/octet-stream")}

        response = client.post("/api/v1/documents/upload", files=files)

        assert response.status_code == 415
        assert "Unsupported format: unknown" in response.json()["detail"]


# ============================================================================
# Integration Tests: MIME Type Cross-Check via API
# ============================================================================


def test_upload_pdf_with_mismatched_mime_returns_415(client):
    """Upload a valid PDF file but with wrong MIME type → 415."""
    valid_pdf = b"%PDF-1.4 fake pdf content"
    files = {"file": ("document.pdf", valid_pdf, "image/png")}

    response = client.post("/api/v1/documents/upload", files=files)

    assert response.status_code == 415
    assert "Content-Type" in response.json()["detail"]


def test_upload_pdf_with_octet_stream_passes_mime_check(client):
    """Upload a valid PDF with application/octet-stream should bypass MIME check."""
    valid_pdf = b"%PDF-1.4 fake pdf content"
    files = {"file": ("document.pdf", valid_pdf, "application/octet-stream")}

    # This should pass both magic bytes and MIME checks
    # May hit format support or processing — just verify no 415
    with patch("src.api.upload_routes.FileContentIngestionService") as mock_service:
        mock_instance = mock_service.return_value
        mock_content = Content(
            id=1,
            title="Test",
            status=ContentStatus.PARSED,
            source_id="test",
            source_type="file_upload",
        )
        mock_instance.ingest_file = AsyncMock(return_value=mock_content)

        response = client.post("/api/v1/documents/upload", files=files)
        assert response.status_code == 200
