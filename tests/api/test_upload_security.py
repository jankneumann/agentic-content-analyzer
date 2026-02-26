"""Tests for upload file content security."""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.api.app import app
from src.api.dependencies import verify_admin_key
from src.models.content import Content, ContentStatus


class TestUploadContentSecurity:
    """Tests for file upload content security and spoofing prevention."""

    def setup_method(self):
        # Override admin key dependency
        app.dependency_overrides[verify_admin_key] = lambda: "test-admin-key"
        self.client = TestClient(app)

    def teardown_method(self):
        app.dependency_overrides = {}

    def test_reject_extension_mismatch(self, db_session):
        """Test rejection when file extension does not match content signature."""
        # Create a file that claims to be a PDF but is actually a shell script
        # PDF signature: %PDF- (25 50 44 46 2d)
        # Shell script: #!/bin/bash
        content = b"#!/bin/bash\necho 'Compromised'"
        files = {"file": ("malicious.pdf", content, "application/pdf")}

        response = self.client.post(
            "/api/v1/upload/document", files=files, headers={"X-Admin-Key": "test-admin-key"}
        )

        # Should be rejected with 415 Unsupported Media Type or 400 Bad Request
        # The current implementation might return 415 for signature mismatch
        assert response.status_code in [400, 415]
        assert "signature" in response.json()["detail"].lower()

    def test_reject_executable_content(self, db_session):
        """Test rejection of executable file signatures even with safe extensions."""
        # ELF binary signature (7f 45 4c 46) renamed to .txt
        content = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 100
        files = {"file": ("malware.txt", content, "text/plain")}

        response = self.client.post(
            "/api/v1/upload/document", files=files, headers={"X-Admin-Key": "test-admin-key"}
        )

        assert response.status_code in [400, 415]
        # Should detect binary content or signature mismatch
        assert "signature" in response.json()["detail"].lower()

    def test_allow_valid_pdf(self, db_session):
        """Test acceptance of valid PDF file."""
        # Valid PDF header
        content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\n"
        files = {"file": ("document.pdf", content, "application/pdf")}

        with patch("src.api.upload_routes.process_document") as mock_process:
            mock_process.return_value = Content(
                id=1,
                title="document.pdf",
                content_hash="hash",
                status=ContentStatus.PENDING,
                source_type="file_upload",
                source_id="file_1",
                markdown_content="",
            )

            response = self.client.post(
                "/api/v1/upload/document", files=files, headers={"X-Admin-Key": "test-admin-key"}
            )

            assert response.status_code == 200
            assert response.json()["title"] == "document.pdf"

    def test_upload_service_respects_format_hint(self, db_session):
        """Test that ingestion service respects format hint for ambiguous files."""
        # A file that could be markdown or text
        content = b"# This is a header\n\nSome content."

        # We need to mock the IngestionService to verify it receives the hint
        with patch("src.api.upload_routes.IngestionService") as MockIngestionService:
            mock_instance = MockIngestionService.return_value
            mock_instance.ingest_file = AsyncMock(
                return_value=Content(
                    id=1,
                    title="notes.txt",
                    content_hash="hash",
                    status=ContentStatus.PENDING,
                    source_type="file_upload",
                    source_id="file_1",
                    markdown_content="",
                )
            )

            files = {"file": ("notes.txt", content, "text/plain")}
            self.client.post(
                "/api/v1/upload/document", files=files, headers={"X-Admin-Key": "test-admin-key"}
            )

            assert mock_instance.ingest_file.called
            # Verify arguments
            _args, kwargs = mock_instance.ingest_file.call_args
            assert str(kwargs["file_path"]).endswith(".txt")
            assert kwargs["format_hint"] == "txt"
