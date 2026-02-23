import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from src.api.app import app
from src.api.dependencies import verify_admin_key
from src.models.content import Content, ContentStatus

@pytest.mark.security
class TestUploadSecurityFix:

    @pytest.fixture
    def client(self, monkeypatch):
        """
        Simple TestClient with admin auth bypassed via dependency override.
        This avoids the need for a running database or complex fixtures.
        Sets necessary environment variables to pass Settings validation.
        """
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")
        monkeypatch.setenv("WORKER_ENABLED", "false")

        # Clear cache to pick up new env vars
        try:
            from src.config.settings import get_settings
            get_settings.cache_clear()
        except ImportError:
            pass

        app.dependency_overrides[verify_admin_key] = lambda: "test-admin-key"
        with TestClient(app) as c:
            yield c
        app.dependency_overrides = {}

    @pytest.fixture
    def mock_ingestion(self):
        with patch("src.api.upload_routes.FileContentIngestionService") as mock_service:
            mock_instance = mock_service.return_value
            mock_content = Content(
                id=1,
                title="Test Document",
                status=ContentStatus.PARSED,
                source_id="test",
                source_type="file_upload",
            )
            mock_instance.ingest_file = AsyncMock(return_value=mock_content)
            yield mock_instance

    def test_upload_invalid_wav_rejected(self, client, mock_ingestion):
        """Test that invalid WAV content is rejected (415)."""
        files = {"file": ("fake.wav", b"Not a WAV file", "audio/wav")}
        response = client.post("/api/v1/documents/upload", files=files)
        assert response.status_code == 415
        assert "does not match expected format" in response.json()["detail"]

    def test_upload_invalid_mp3_rejected(self, client, mock_ingestion):
        """Test that invalid MP3 content is rejected (415)."""
        files = {"file": ("fake.mp3", b"Not an MP3 file", "audio/mpeg")}
        response = client.post("/api/v1/documents/upload", files=files)
        assert response.status_code == 415
        assert "does not match expected format" in response.json()["detail"]

    def test_upload_invalid_epub_rejected(self, client, mock_ingestion):
        """Test that invalid EPUB content is rejected (415)."""
        files = {"file": ("fake.epub", b"Not a ZIP/EPUB", "application/epub+zip")}
        response = client.post("/api/v1/documents/upload", files=files)
        assert response.status_code == 415
        assert "does not match expected format" in response.json()["detail"]

    def test_upload_invalid_msg_rejected(self, client, mock_ingestion):
        """Test that invalid MSG content is rejected (415)."""
        files = {"file": ("fake.msg", b"Not an OLE file", "application/vnd.ms-outlook")}
        response = client.post("/api/v1/documents/upload", files=files)
        assert response.status_code == 415
        assert "does not match expected format" in response.json()["detail"]

    def test_upload_youtube_rejected(self, client, mock_ingestion):
        """Test that .youtube extension is now explicitly rejected (415)."""
        files = {"file": ("video.youtube", b"some content", "application/octet-stream")}
        response = client.post("/api/v1/documents/upload", files=files)
        assert response.status_code == 415
        # It should say unsupported format because we removed it from 'supported' set
        assert "Unsupported format: youtube" in response.json()["detail"]

    def test_upload_valid_wav_accepted(self, client, mock_ingestion):
        """Test that VALID WAV content is accepted (200)."""
        # WAV starts with RIFF
        valid_wav = b"RIFF" + b"\x00" * 36
        files = {"file": ("valid.wav", valid_wav, "audio/wav")}
        response = client.post("/api/v1/documents/upload", files=files)
        assert response.status_code == 200
        assert mock_ingestion.ingest_file.called

    def test_upload_valid_mp3_id3_accepted(self, client, mock_ingestion):
        """Test that VALID MP3 (ID3) content is accepted (200)."""
        valid_mp3 = b"ID3" + b"\x00" * 100
        files = {"file": ("valid.mp3", valid_mp3, "audio/mpeg")}
        response = client.post("/api/v1/documents/upload", files=files)
        assert response.status_code == 200
        assert mock_ingestion.ingest_file.called

    def test_upload_valid_mp3_frame_accepted(self, client, mock_ingestion):
        """Test that VALID MP3 (Frame Sync) content is accepted (200)."""
        valid_mp3 = b"\xff\xfb" + b"\x00" * 100
        files = {"file": ("valid_frame.mp3", valid_mp3, "audio/mpeg")}
        response = client.post("/api/v1/documents/upload", files=files)
        assert response.status_code == 200
        assert mock_ingestion.ingest_file.called

    def test_upload_valid_epub_accepted(self, client, mock_ingestion):
        """Test that VALID EPUB (ZIP) content is accepted (200)."""
        valid_epub = b"PK\x03\x04" + b"\x00" * 100
        files = {"file": ("valid.epub", valid_epub, "application/epub+zip")}
        response = client.post("/api/v1/documents/upload", files=files)
        assert response.status_code == 200
        assert mock_ingestion.ingest_file.called

    def test_upload_valid_msg_accepted(self, client, mock_ingestion):
        """Test that VALID MSG (OLE CF) content is accepted (200)."""
        valid_msg = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 100
        files = {"file": ("valid.msg", valid_msg, "application/vnd.ms-outlook")}
        response = client.post("/api/v1/documents/upload", files=files)
        assert response.status_code == 200
        assert mock_ingestion.ingest_file.called
