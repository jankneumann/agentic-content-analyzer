"""Tests for podcast API endpoints."""

from src.models.podcast import Podcast, PodcastStatus


class TestListPodcasts:
    """Tests for GET /api/v1/podcasts/ endpoint."""

    def test_list_podcasts_empty(self, client):
        """Test listing podcasts when database is empty."""
        response = client.get("/api/v1/podcasts/")

        assert response.status_code == 200
        data = response.json()
        assert data == []

    def test_list_podcasts_returns_items(self, client, sample_podcast):
        """Test listing podcasts returns all items."""
        response = client.get("/api/v1/podcasts/")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == sample_podcast.id

    def test_list_podcasts_filter_by_status(self, client, sample_podcast):
        """Test filtering podcasts by status."""
        response = client.get("/api/v1/podcasts/?status=completed")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "completed"


class TestGetPodcast:
    """Tests for GET /api/v1/podcasts/{id} endpoint."""

    def test_get_podcast_returns_detail(self, client, sample_podcast, sample_script):
        """Test getting podcast by ID returns full detail."""
        response = client.get(f"/api/v1/podcasts/{sample_podcast.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_podcast.id
        assert data["script_id"] == sample_podcast.script_id
        assert data["title"] == sample_script.title
        assert data["status"] == "completed"
        assert "duration_seconds" in data
        assert "voice_provider" in data

    def test_get_podcast_not_found(self, client):
        """Test getting non-existent podcast returns 404."""
        response = client.get("/api/v1/podcasts/99999")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestPodcastStatistics:
    """Tests for GET /api/v1/podcasts/statistics endpoint."""

    def test_podcast_statistics_empty(self, client):
        """Test statistics endpoint with empty database."""
        response = client.get("/api/v1/podcasts/statistics")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["completed"] == 0
        assert data["generating"] == 0
        assert data["failed"] == 0

    def test_podcast_statistics_with_data(self, client, sample_podcast):
        """Test statistics endpoint with podcasts in database."""
        response = client.get("/api/v1/podcasts/statistics")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["completed"] == 1
        assert "total_duration_seconds" in data
        assert "by_voice_provider" in data


class TestListApprovedScripts:
    """Tests for GET /api/v1/podcasts/approved-scripts endpoint."""

    def test_list_approved_scripts_empty(self, client):
        """Test listing approved scripts when none exist."""
        response = client.get("/api/v1/podcasts/approved-scripts")

        assert response.status_code == 200
        data = response.json()
        assert data == []

    def test_list_approved_scripts_returns_items(self, client, sample_podcast, sample_script):
        """Test listing approved scripts returns items."""
        # sample_script is approved because sample_podcast requires it
        response = client.get("/api/v1/podcasts/approved-scripts")

        assert response.status_code == 200
        data = response.json()
        # Note: sample_script status was updated to approved in sample_podcast fixture
        assert len(data) == 1
        assert data[0]["id"] == sample_script.id


class TestGenerateAudio:
    """Tests for POST /api/v1/podcasts/generate endpoint."""

    def test_generate_audio_with_approved_script(self, client, sample_script, db_session):
        """Test generating audio from approved script returns queued status."""
        # Ensure script is approved
        sample_script.status = PodcastStatus.SCRIPT_APPROVED.value
        db_session.commit()

        response = client.post(
            "/api/v1/podcasts/generate",
            json={
                "script_id": sample_script.id,
                "voice_provider": "openai_tts",
                "alex_voice": "alex_male",
                "sam_voice": "sam_female",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "queued"
        assert data["script_id"] == sample_script.id
        assert "podcast_id" in data

    def test_generate_audio_script_not_found(self, client):
        """Test generating audio for non-existent script returns 404."""
        response = client.post(
            "/api/v1/podcasts/generate",
            json={
                "script_id": 99999,
                "voice_provider": "openai_tts",
                "alex_voice": "alex_male",
                "sam_voice": "sam_female",
            },
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_generate_audio_script_not_approved(self, client, sample_script, db_session):
        """Test generating audio for non-approved script returns 400."""
        # Set script status to pending
        sample_script.status = PodcastStatus.SCRIPT_PENDING_REVIEW.value
        db_session.commit()

        response = client.post(
            "/api/v1/podcasts/generate",
            json={
                "script_id": sample_script.id,
                "voice_provider": "openai_tts",
                "alex_voice": "alex_male",
                "sam_voice": "sam_female",
            },
        )

        assert response.status_code == 400
        assert "approved" in response.json()["detail"].lower()

    def test_generate_audio_invalid_voice_provider(self, client, sample_script, db_session):
        """Test generating audio with invalid voice provider returns 400."""
        sample_script.status = PodcastStatus.SCRIPT_APPROVED.value
        db_session.commit()

        response = client.post(
            "/api/v1/podcasts/generate",
            json={
                "script_id": sample_script.id,
                "voice_provider": "invalid_provider",
                "alex_voice": "alex_male",
                "sam_voice": "sam_female",
            },
        )

        assert response.status_code == 400
        assert "invalid" in response.json()["detail"].lower()


class TestStreamAudio:
    """Tests for GET /api/v1/podcasts/{id}/audio endpoint."""

    def test_stream_audio_not_found(self, client):
        """Test streaming audio for non-existent podcast returns 404."""
        response = client.get("/api/v1/podcasts/99999/audio")

        assert response.status_code == 404

    def test_stream_audio_not_completed(self, client, sample_script, db_session):
        """Test streaming audio for non-completed podcast returns 400."""
        # Ensure script is approved
        sample_script.status = PodcastStatus.SCRIPT_APPROVED.value

        # Create a generating podcast
        podcast = Podcast(
            script_id=sample_script.id,
            audio_format="mp3",
            voice_provider="openai_tts",
            status="generating",
        )
        db_session.add(podcast)
        db_session.commit()
        db_session.refresh(podcast)

        response = client.get(f"/api/v1/podcasts/{podcast.id}/audio")

        assert response.status_code == 400
        assert "not ready" in response.json()["detail"].lower()

    def test_stream_audio_file_not_found(self, client, sample_podcast, db_session):
        """Test streaming audio when file doesn't exist returns 404."""
        from unittest.mock import AsyncMock, patch

        # Mock storage to return False for exists check
        mock_storage = AsyncMock()
        mock_storage.exists = AsyncMock(return_value=False)

        with patch("src.services.file_storage.get_storage", return_value=mock_storage):
            with patch("os.path.exists", return_value=False):
                response = client.get(f"/api/v1/podcasts/{sample_podcast.id}/audio")

        assert response.status_code == 404
        assert "file not found" in response.json()["detail"].lower()

    def test_stream_audio_success(self, client, sample_podcast, db_session, tmp_path):
        """Test streaming audio successfully returns file."""
        from unittest.mock import AsyncMock, patch

        # Create a temporary audio file
        audio_file = tmp_path / "test_podcast.mp3"
        audio_file.write_bytes(b"fake audio content")

        # Update podcast to point to the temp file
        sample_podcast.audio_url = str(audio_file)
        db_session.commit()

        # Mock storage to return True for exists check and return file content
        mock_storage = AsyncMock()
        mock_storage.exists = AsyncMock(return_value=True)
        mock_storage.provider_name = "local"
        mock_storage.get = AsyncMock(return_value=b"fake audio content")

        with patch("src.services.file_storage.get_storage", return_value=mock_storage):
            response = client.get(f"/api/v1/podcasts/{sample_podcast.id}/audio")

        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/mpeg"
