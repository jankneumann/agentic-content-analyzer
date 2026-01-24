"""Tests for audio digest API endpoints."""

import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.audio_digest import AudioDigest, AudioDigestStatus


@pytest.fixture
def sample_audio_digest(db_session, sample_digest) -> AudioDigest:
    """Create a sample audio digest in the test database."""
    audio_digest = AudioDigest(
        digest_id=sample_digest.id,
        voice="nova",
        speed=1.0,
        provider="openai",
        status=AudioDigestStatus.COMPLETED,
        audio_url="audio-digests/2025/01/24/abc123_audio_digest_1.mp3",
        duration_seconds=120.5,
        file_size_bytes=1024000,
        text_char_count=5000,
        chunk_count=2,
        completed_at=datetime.now(UTC),
    )
    db_session.add(audio_digest)
    db_session.commit()
    db_session.refresh(audio_digest)
    return audio_digest


@pytest.fixture
def sample_audio_digests(db_session, sample_digest) -> list[AudioDigest]:
    """Create multiple sample audio digests in the test database."""
    audio_digests = [
        AudioDigest(
            digest_id=sample_digest.id,
            voice="nova",
            speed=1.0,
            provider="openai",
            status=AudioDigestStatus.COMPLETED,
            audio_url="audio-digests/2025/01/24/abc123_audio_1.mp3",
            duration_seconds=120.5,
            completed_at=datetime.now(UTC),
        ),
        AudioDigest(
            digest_id=sample_digest.id,
            voice="alloy",
            speed=1.25,
            provider="openai",
            status=AudioDigestStatus.PROCESSING,
        ),
        AudioDigest(
            digest_id=sample_digest.id,
            voice="shimmer",
            speed=1.0,
            provider="openai",
            status=AudioDigestStatus.FAILED,
            error_message="TTS service unavailable",
        ),
    ]

    for ad in audio_digests:
        db_session.add(ad)

    db_session.commit()

    for ad in audio_digests:
        db_session.refresh(ad)

    return audio_digests


class TestCreateAudioDigest:
    """Tests for POST /api/v1/digests/{digest_id}/audio endpoint."""

    def test_create_audio_digest_success(self, client, sample_digest):
        """Test creating an audio digest returns pending status."""
        response = client.post(
            f"/api/v1/digests/{sample_digest.id}/audio",
            json={
                "voice": "nova",
                "speed": 1.0,
                "provider": "openai",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["digest_id"] == sample_digest.id
        assert data["voice"] == "nova"
        assert data["speed"] == 1.0
        assert data["provider"] == "openai"
        assert data["status"] == "pending"
        assert data["audio_url"] is None
        assert "id" in data
        assert "created_at" in data

    def test_create_audio_digest_with_defaults(self, client, sample_digest):
        """Test creating an audio digest with default values."""
        response = client.post(
            f"/api/v1/digests/{sample_digest.id}/audio",
            json={},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["voice"] == "nova"  # default
        assert data["speed"] == 1.0  # default
        assert data["provider"] == "openai"  # default

    def test_create_audio_digest_custom_speed(self, client, sample_digest):
        """Test creating an audio digest with custom speed."""
        response = client.post(
            f"/api/v1/digests/{sample_digest.id}/audio",
            json={
                "voice": "alloy",
                "speed": 1.5,
                "provider": "openai",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["voice"] == "alloy"
        assert data["speed"] == 1.5

    def test_create_audio_digest_digest_not_found(self, client):
        """Test creating audio digest for non-existent digest returns 404."""
        response = client.post(
            "/api/v1/digests/99999/audio",
            json={"voice": "nova"},
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_create_audio_digest_invalid_speed(self, client, sample_digest):
        """Test creating audio digest with invalid speed returns 422."""
        response = client.post(
            f"/api/v1/digests/{sample_digest.id}/audio",
            json={
                "voice": "nova",
                "speed": 5.0,  # Max is 4.0
            },
        )

        assert response.status_code == 422  # Validation error


class TestListDigestAudio:
    """Tests for GET /api/v1/digests/{digest_id}/audio endpoint."""

    def test_list_digest_audio_empty(self, client, sample_digest):
        """Test listing audio digests when none exist."""
        response = client.get(f"/api/v1/digests/{sample_digest.id}/audio")

        assert response.status_code == 200
        data = response.json()
        assert data == []

    def test_list_digest_audio_returns_items(self, client, sample_audio_digests):
        """Test listing audio digests returns all items."""
        digest_id = sample_audio_digests[0].digest_id
        response = client.get(f"/api/v1/digests/{digest_id}/audio")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    def test_list_digest_audio_ordered_by_created_at(self, client, sample_audio_digests):
        """Test audio digests are ordered by created_at descending."""
        digest_id = sample_audio_digests[0].digest_id
        response = client.get(f"/api/v1/digests/{digest_id}/audio")

        assert response.status_code == 200
        data = response.json()
        # Most recent first
        assert len(data) == 3

    def test_list_digest_audio_returns_list_items(self, client, sample_audio_digest):
        """Test list items have expected fields."""
        response = client.get(f"/api/v1/digests/{sample_audio_digest.digest_id}/audio")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        item = data[0]
        assert "id" in item
        assert "digest_id" in item
        assert "voice" in item
        assert "provider" in item
        assert "status" in item
        assert "duration_seconds" in item
        assert "created_at" in item
        # List items don't include full details
        assert "error_message" not in item
        assert "audio_url" not in item


class TestGetAudioDigest:
    """Tests for GET /api/v1/audio-digests/{audio_digest_id} endpoint."""

    def test_get_audio_digest_success(self, client, sample_audio_digest):
        """Test getting audio digest by ID returns full detail."""
        response = client.get(f"/api/v1/audio-digests/{sample_audio_digest.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_audio_digest.id
        assert data["digest_id"] == sample_audio_digest.digest_id
        assert data["voice"] == "nova"
        assert data["speed"] == 1.0
        assert data["provider"] == "openai"
        assert data["status"] == "completed"
        assert data["audio_url"] == sample_audio_digest.audio_url
        assert data["duration_seconds"] == 120.5
        assert data["file_size_bytes"] == 1024000
        assert data["text_char_count"] == 5000
        assert data["chunk_count"] == 2
        assert "created_at" in data
        assert "completed_at" in data

    def test_get_audio_digest_not_found(self, client):
        """Test getting non-existent audio digest returns 404."""
        response = client.get("/api/v1/audio-digests/99999")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_audio_digest_with_error(self, client, sample_audio_digests):
        """Test getting failed audio digest shows error message."""
        # Get the failed one
        failed_digest = [
            ad for ad in sample_audio_digests if ad.status == AudioDigestStatus.FAILED
        ][0]
        response = client.get(f"/api/v1/audio-digests/{failed_digest.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["error_message"] == "TTS service unavailable"


class TestStreamAudioDigest:
    """Tests for GET /api/v1/audio-digests/{audio_digest_id}/stream endpoint."""

    def test_stream_audio_digest_not_found(self, client):
        """Test streaming non-existent audio digest returns 404."""
        response = client.get("/api/v1/audio-digests/99999/stream")

        assert response.status_code == 404

    def test_stream_audio_digest_not_ready(self, client, sample_audio_digests):
        """Test streaming audio digest not yet completed returns 400."""
        processing_digest = [
            ad for ad in sample_audio_digests if ad.status == AudioDigestStatus.PROCESSING
        ][0]
        response = client.get(f"/api/v1/audio-digests/{processing_digest.id}/stream")

        assert response.status_code == 400
        assert "not ready" in response.json()["detail"].lower()

    def test_stream_audio_digest_no_url(self, client, db_session, sample_digest):
        """Test streaming audio digest with no audio URL returns 404."""
        # Create completed audio digest without URL
        audio_digest = AudioDigest(
            digest_id=sample_digest.id,
            voice="nova",
            speed=1.0,
            provider="openai",
            status=AudioDigestStatus.COMPLETED,
            audio_url=None,  # No URL
        )
        db_session.add(audio_digest)
        db_session.commit()
        db_session.refresh(audio_digest)

        response = client.get(f"/api/v1/audio-digests/{audio_digest.id}/stream")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_stream_audio_digest_file_missing(self, client, sample_audio_digest):
        """Test streaming when file is missing on disk returns 404."""
        # The sample_audio_digest has a URL but the file doesn't exist
        response = client.get(f"/api/v1/audio-digests/{sample_audio_digest.id}/stream")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_stream_audio_digest_success(self, client, db_session, sample_digest):
        """Test streaming audio file returns FileResponse."""
        # Create a temporary audio file
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp.write(b"fake mp3 data for testing")
            tmp_path = Path(tmp.name)

        try:
            # Create audio digest pointing to the temp file
            audio_digest = AudioDigest(
                digest_id=sample_digest.id,
                voice="nova",
                speed=1.0,
                provider="openai",
                status=AudioDigestStatus.COMPLETED,
                audio_url=str(tmp_path),
            )
            db_session.add(audio_digest)
            db_session.commit()
            db_session.refresh(audio_digest)

            # Mock the storage to return the correct path
            mock_storage = MagicMock()
            mock_storage._resolve_path = MagicMock(return_value=tmp_path)

            with patch("src.api.audio_digest_routes.get_storage", return_value=mock_storage):
                response = client.get(f"/api/v1/audio-digests/{audio_digest.id}/stream")

            assert response.status_code == 200
            assert response.headers["content-type"] == "audio/mpeg"
            assert "accept-ranges" in response.headers
            assert response.content == b"fake mp3 data for testing"

        finally:
            tmp_path.unlink(missing_ok=True)


class TestDeleteAudioDigest:
    """Tests for DELETE /api/v1/audio-digests/{audio_digest_id} endpoint."""

    def test_delete_audio_digest_success(self, client, sample_audio_digest):
        """Test deleting an audio digest removes the record."""
        audio_digest_id = sample_audio_digest.id

        # Mock storage delete
        mock_storage = MagicMock()
        mock_storage.delete = AsyncMock(return_value=True)

        with patch("src.api.audio_digest_routes.get_storage", return_value=mock_storage):
            response = client.delete(f"/api/v1/audio-digests/{audio_digest_id}")

        assert response.status_code == 200
        data = response.json()
        assert "deleted" in data["message"].lower()

        # Verify it's actually deleted
        get_response = client.get(f"/api/v1/audio-digests/{audio_digest_id}")
        assert get_response.status_code == 404

    def test_delete_audio_digest_not_found(self, client):
        """Test deleting non-existent audio digest returns 404."""
        response = client.delete("/api/v1/audio-digests/99999")

        assert response.status_code == 404

    def test_delete_audio_digest_without_file(self, client, db_session, sample_digest):
        """Test deleting audio digest without audio file still succeeds."""
        # Create audio digest without URL
        audio_digest = AudioDigest(
            digest_id=sample_digest.id,
            voice="nova",
            speed=1.0,
            provider="openai",
            status=AudioDigestStatus.PENDING,
            audio_url=None,
        )
        db_session.add(audio_digest)
        db_session.commit()
        db_session.refresh(audio_digest)

        response = client.delete(f"/api/v1/audio-digests/{audio_digest.id}")

        assert response.status_code == 200
