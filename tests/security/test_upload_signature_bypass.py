from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.workflow_dependencies import get_upload_service
from src.contracts.workflow_models import UploadReference


@pytest.mark.security
class TestUploadSecurityFix:
    @pytest.fixture
    def client(self, monkeypatch, upload_service):
        """Create a development client using the canonical upload boundary."""
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("APP_SECRET_KEY", "")
        monkeypatch.setenv("ADMIN_API_KEY", "")
        monkeypatch.setenv("WORKER_ENABLED", "false")
        from src.config.settings import get_settings

        get_settings.cache_clear()
        app.dependency_overrides[get_upload_service] = lambda: upload_service
        try:
            with TestClient(app) as c:
                yield c
        finally:
            app.dependency_overrides.clear()
            get_settings.cache_clear()

    @pytest.fixture
    def upload_service(self):
        service = AsyncMock()
        service.max_size_bytes = 1024
        service.store.return_value = UploadReference(
            id="upl_security",
            filename="fixture",
            media_type="application/octet-stream",
            size_bytes=1,
        )
        return service

    def test_upload_invalid_wav_rejected(self, client, upload_service):
        """Test that invalid WAV content is rejected."""
        files = {"file": ("fake.wav", b"Not a WAV file", "audio/wav")}
        response = client.post("/api/v1/uploads", files=files)
        assert response.status_code == 422
        assert "content does not match" in response.json()["detail"].lower()
        upload_service.store.assert_not_awaited()

    def test_upload_invalid_mp3_rejected(self, client, upload_service):
        """Test that invalid MP3 content is rejected."""
        files = {"file": ("fake.mp3", b"Not an MP3 file", "audio/mpeg")}
        response = client.post("/api/v1/uploads", files=files)
        assert response.status_code == 422
        assert "content does not match" in response.json()["detail"].lower()
        upload_service.store.assert_not_awaited()

    def test_upload_invalid_epub_rejected(self, client, upload_service):
        """Test that invalid EPUB content is rejected."""
        files = {"file": ("fake.epub", b"Not a ZIP/EPUB", "application/epub+zip")}
        response = client.post("/api/v1/uploads", files=files)
        assert response.status_code == 422
        assert "content does not match" in response.json()["detail"].lower()
        upload_service.store.assert_not_awaited()

    def test_upload_invalid_msg_rejected(self, client, upload_service):
        """Test that invalid MSG content is rejected."""
        files = {"file": ("fake.msg", b"Not an OLE file", "application/vnd.ms-outlook")}
        response = client.post("/api/v1/uploads", files=files)
        assert response.status_code == 422
        assert "content does not match" in response.json()["detail"].lower()
        upload_service.store.assert_not_awaited()

    def test_upload_youtube_rejected(self, client, upload_service):
        """Test that the removed .youtube pseudo-upload stays rejected."""
        files = {"file": ("video.youtube", b"some content", "application/octet-stream")}
        response = client.post("/api/v1/uploads", files=files)
        assert response.status_code == 422
        assert "unsupported upload media type" in response.json()["detail"].lower()
        upload_service.store.assert_not_awaited()

    def test_upload_valid_wav_accepted(self, client, upload_service):
        """Test that valid WAV content is accepted."""
        # WAV starts with RIFF
        valid_wav = b"RIFF" + b"\x00" * 36
        files = {"file": ("valid.wav", valid_wav, "audio/wav")}
        response = client.post("/api/v1/uploads", files=files)
        assert response.status_code == 201
        upload_service.store.assert_awaited_once()

    def test_upload_valid_mp3_id3_accepted(self, client, upload_service):
        """Test that valid MP3 (ID3) content is accepted."""
        valid_mp3 = b"ID3" + b"\x00" * 100
        files = {"file": ("valid.mp3", valid_mp3, "audio/mpeg")}
        response = client.post("/api/v1/uploads", files=files)
        assert response.status_code == 201
        upload_service.store.assert_awaited_once()

    def test_upload_valid_mp3_frame_accepted(self, client, upload_service):
        """Test that valid MP3 (frame sync) content is accepted."""
        valid_mp3 = b"\xff\xfb" + b"\x00" * 100
        files = {"file": ("valid_frame.mp3", valid_mp3, "audio/mpeg")}
        response = client.post("/api/v1/uploads", files=files)
        assert response.status_code == 201
        upload_service.store.assert_awaited_once()

    def test_upload_valid_epub_accepted(self, client, upload_service):
        """Test that valid EPUB (ZIP) content is accepted."""
        valid_epub = b"PK\x03\x04" + b"\x00" * 100
        files = {"file": ("valid.epub", valid_epub, "application/epub+zip")}
        response = client.post("/api/v1/uploads", files=files)
        assert response.status_code == 201
        upload_service.store.assert_awaited_once()

    def test_upload_valid_msg_accepted(self, client, upload_service):
        """Test that valid MSG (OLE CF) content is accepted."""
        valid_msg = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 100
        files = {"file": ("valid.msg", valid_msg, "application/vnd.ms-outlook")}
        response = client.post("/api/v1/uploads", files=files)
        assert response.status_code == 201
        upload_service.store.assert_awaited_once()
