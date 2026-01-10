"""Tests for YouTube ingestion."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.ingestion.youtube import (
    DEFAULT_LANGUAGES,
    YouTubeClient,
    YouTubeIngestionService,
)
from src.models.youtube import TranscriptSegment, YouTubeTranscript


class TestYouTubeClient:
    """Tests for YouTubeClient."""

    @patch("src.ingestion.youtube.build")
    @patch("src.ingestion.youtube.settings")
    def test_authenticate_api_key(self, mock_settings: Mock, mock_build: Mock) -> None:
        """Test API key authentication."""
        mock_settings.get_youtube_api_key.return_value = "test-api-key"

        client = YouTubeClient(use_oauth=False)

        mock_build.assert_called_once_with("youtube", "v3", developerKey="test-api-key")
        assert client.service is not None

    @patch("src.ingestion.youtube.build")
    @patch("src.ingestion.youtube.settings")
    def test_authenticate_api_key_missing(self, mock_settings: Mock, mock_build: Mock) -> None:
        """Test API key authentication fails when key is missing."""
        mock_settings.get_youtube_api_key.return_value = None

        with pytest.raises(ValueError, match="YOUTUBE_API_KEY or GOOGLE_API_KEY required"):
            YouTubeClient(use_oauth=False)

    def test_parse_date_valid(self) -> None:
        """Test parsing valid ISO 8601 date."""
        client = YouTubeClient.__new__(YouTubeClient)

        result = client._parse_date("2024-01-15T10:30:00Z")

        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_parse_date_invalid(self) -> None:
        """Test parsing invalid date returns current time."""
        client = YouTubeClient.__new__(YouTubeClient)

        result = client._parse_date("not-a-date")

        # Should return current time (within a few seconds)
        now = datetime.now(UTC)
        assert abs((now - result).total_seconds()) < 5

    def test_get_best_thumbnail_maxres(self) -> None:
        """Test getting best thumbnail prefers maxres."""
        client = YouTubeClient.__new__(YouTubeClient)
        thumbnails = {
            "default": {"url": "http://default.jpg"},
            "medium": {"url": "http://medium.jpg"},
            "high": {"url": "http://high.jpg"},
            "maxres": {"url": "http://maxres.jpg"},
        }

        result = client._get_best_thumbnail(thumbnails)

        assert result == "http://maxres.jpg"

    def test_get_best_thumbnail_fallback(self) -> None:
        """Test getting best thumbnail falls back correctly."""
        client = YouTubeClient.__new__(YouTubeClient)
        thumbnails = {
            "default": {"url": "http://default.jpg"},
            "medium": {"url": "http://medium.jpg"},
        }

        result = client._get_best_thumbnail(thumbnails)

        assert result == "http://medium.jpg"

    def test_get_best_thumbnail_empty(self) -> None:
        """Test getting best thumbnail with empty dict."""
        client = YouTubeClient.__new__(YouTubeClient)

        result = client._get_best_thumbnail({})

        assert result is None

    @patch("src.ingestion.youtube.YouTubeTranscriptApi")
    def test_get_transcript_success(self, mock_api: Mock) -> None:
        """Test successful transcript retrieval."""
        # Setup mock
        mock_transcript = Mock()
        mock_transcript.fetch.return_value = [
            {"text": "Hello", "start": 0.0, "duration": 1.5},
            {"text": "World", "start": 1.5, "duration": 1.5},
        ]
        mock_transcript.language_code = "en"
        mock_transcript.is_generated = False

        mock_list = Mock()
        mock_list.find_manually_created_transcript.return_value = mock_transcript
        mock_api.list_transcripts.return_value = mock_list

        # Create client without authentication
        client = YouTubeClient.__new__(YouTubeClient)

        result = client.get_transcript("test-video-id")

        assert result is not None
        assert isinstance(result, YouTubeTranscript)
        assert result.video_id == "test-video-id"
        assert len(result.segments) == 2
        assert result.segments[0].text == "Hello"
        assert result.language == "en"
        assert result.is_auto_generated is False

    @patch("src.ingestion.youtube.YouTubeTranscriptApi")
    def test_get_transcript_auto_generated(self, mock_api: Mock) -> None:
        """Test transcript retrieval falls back to auto-generated."""
        from youtube_transcript_api._errors import NoTranscriptFound

        # Setup mock
        mock_transcript = Mock()
        mock_transcript.fetch.return_value = [
            {"text": "Auto generated", "start": 0.0, "duration": 2.0},
        ]
        mock_transcript.language_code = "en"
        mock_transcript.is_generated = True

        mock_list = Mock()
        mock_list.find_manually_created_transcript.side_effect = NoTranscriptFound("test", [], [])
        mock_list.find_generated_transcript.return_value = mock_transcript
        mock_api.list_transcripts.return_value = mock_list

        client = YouTubeClient.__new__(YouTubeClient)

        result = client.get_transcript("test-video-id")

        assert result is not None
        assert result.is_auto_generated is True

    @patch("src.ingestion.youtube.YouTubeTranscriptApi")
    def test_get_transcript_disabled(self, mock_api: Mock) -> None:
        """Test transcript retrieval when transcripts are disabled."""
        from youtube_transcript_api._errors import TranscriptsDisabled

        mock_api.list_transcripts.side_effect = TranscriptsDisabled("test")

        client = YouTubeClient.__new__(YouTubeClient)

        result = client.get_transcript("test-video-id")

        assert result is None


class TestYouTubeIngestionService:
    """Tests for YouTubeIngestionService."""

    @pytest.fixture
    def mock_service(self) -> YouTubeIngestionService:
        """Create mock ingestion service."""
        with patch.object(YouTubeIngestionService, "__init__", lambda x, **k: None):
            service = YouTubeIngestionService()
            service.client = Mock()
            return service

    def test_ingest_playlist_empty(self, mock_service: YouTubeIngestionService) -> None:
        """Test ingestion with empty playlist."""
        mock_service.client.get_playlist_videos.return_value = []

        count = mock_service.ingest_playlist("PLtest")

        assert count == 0

    @patch("src.ingestion.youtube.get_db")
    def test_ingest_playlist_success(
        self, mock_get_db: Mock, mock_service: YouTubeIngestionService
    ) -> None:
        """Test successful playlist ingestion."""
        # Setup mock videos
        mock_service.client.get_playlist_videos.return_value = [
            {
                "video_id": "vid123",
                "title": "Test Video",
                "channel_title": "Test Channel",
                "published_date": datetime.now(UTC),
                "thumbnail_url": "http://thumb.jpg",
                "playlist_id": "PLtest",
            }
        ]

        # Setup mock transcript
        mock_transcript = YouTubeTranscript(
            video_id="vid123",
            title="Test Video",
            segments=[
                TranscriptSegment(text="Hello", start=0.0, duration=1.5),
            ],
            language="en",
            is_auto_generated=False,
        )
        mock_service.client.get_transcript.return_value = mock_transcript

        # Setup mock database
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_get_db.return_value.__enter__.return_value = mock_db

        count = mock_service.ingest_playlist("PLtest")

        assert count == 1
        mock_db.add.assert_called_once()

    @patch("src.ingestion.youtube.get_db")
    def test_ingest_playlist_skip_existing(
        self, mock_get_db: Mock, mock_service: YouTubeIngestionService
    ) -> None:
        """Test ingestion skips existing videos."""
        mock_service.client.get_playlist_videos.return_value = [
            {
                "video_id": "vid123",
                "title": "Test Video",
                "channel_title": "Test Channel",
                "published_date": datetime.now(UTC),
            }
        ]

        # Mock that video already exists
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = Mock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        count = mock_service.ingest_playlist("PLtest", force_reprocess=False)

        assert count == 0
        mock_db.add.assert_not_called()

    @patch("src.ingestion.youtube.get_db")
    def test_ingest_playlist_no_transcript(
        self, mock_get_db: Mock, mock_service: YouTubeIngestionService
    ) -> None:
        """Test ingestion handles videos without transcripts."""
        mock_service.client.get_playlist_videos.return_value = [
            {
                "video_id": "vid123",
                "title": "Test Video",
                "channel_title": "Test Channel",
                "published_date": datetime.now(UTC),
            }
        ]
        mock_service.client.get_transcript.return_value = None

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_get_db.return_value.__enter__.return_value = mock_db

        count = mock_service.ingest_playlist("PLtest")

        assert count == 0

    @patch("src.ingestion.youtube.settings")
    def test_ingest_all_playlists_empty_config(
        self, mock_settings: Mock, mock_service: YouTubeIngestionService
    ) -> None:
        """Test ingestion with no configured playlists."""
        mock_settings.get_youtube_playlists.return_value = []

        count = mock_service.ingest_all_playlists()

        assert count == 0


class TestDefaultLanguages:
    """Tests for default language configuration."""

    def test_default_languages(self) -> None:
        """Test default languages are English variants."""
        assert "en" in DEFAULT_LANGUAGES
        assert "en-US" in DEFAULT_LANGUAGES
        assert "en-GB" in DEFAULT_LANGUAGES


class TestCLI:
    """Tests for CLI entry point."""

    @patch("src.ingestion.youtube.YouTubeIngestionService")
    def test_main_with_playlist_id(self, mock_service_class: Mock) -> None:
        """Test CLI with specific playlist ID."""
        import sys

        from src.ingestion.youtube import main

        mock_service = Mock()
        mock_service.ingest_playlist.return_value = 5
        mock_service_class.return_value = mock_service

        with patch.object(
            sys, "argv", ["youtube", "--playlist-id", "PLtest", "--max-videos", "20"]
        ):
            main()

        mock_service.ingest_playlist.assert_called_once()
        call_kwargs = mock_service.ingest_playlist.call_args[1]
        assert call_kwargs["playlist_id"] == "PLtest"
        assert call_kwargs["max_videos"] == 20

    @patch("src.ingestion.youtube.YouTubeIngestionService")
    def test_main_public_only(self, mock_service_class: Mock) -> None:
        """Test CLI with public-only flag."""
        import sys

        from src.ingestion.youtube import main

        mock_service = Mock()
        mock_service.ingest_all_playlists.return_value = 0
        mock_service_class.return_value = mock_service

        with patch.object(sys, "argv", ["youtube", "--public-only"]):
            main()

        # Should initialize service with use_oauth=False
        mock_service_class.assert_called_once_with(use_oauth=False)
