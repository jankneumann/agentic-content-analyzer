"""Tests for YouTube ingestion."""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.ingestion.youtube import (
    DEFAULT_LANGUAGES,
    YouTubeClient,
    YouTubeContentIngestionService,
    YouTubeRSSIngestionService,
)
from src.models.youtube import YouTubeTranscript

# Test playlist IDs (real playlists for integration testing)
TEST_PUBLIC_PLAYLIST_ID = "PLN4UY0S3lPrs40eHdRIiJ-iXJYMkjI4P6"
TEST_PRIVATE_PLAYLIST_ID = "PLgmaR0EXVZsLXQ30zPCMobz0p02XrNBJq"


class TestYouTubeClient:
    """Tests for YouTubeClient."""

    @patch("src.ingestion.youtube.build")
    @patch("src.ingestion.youtube.settings")
    def test_authenticate_api_key(self, mock_settings: Mock, mock_build: Mock) -> None:
        """Test API key authentication (triggered lazily on .service access)."""
        mock_settings.get_youtube_api_key.return_value = "test-api-key"

        client = YouTubeClient(use_oauth=False)

        # Auth is lazy — trigger it by accessing .service
        _ = client.service

        mock_build.assert_called_once_with("youtube", "v3", developerKey="test-api-key")
        assert client._service is not None

    @patch("src.ingestion.youtube.build")
    @patch("src.ingestion.youtube.settings")
    def test_authenticate_api_key_missing(self, mock_settings: Mock, mock_build: Mock) -> None:
        """Test API key authentication fails when key is missing."""
        mock_settings.get_youtube_api_key.return_value = None

        client = YouTubeClient(use_oauth=False)

        # Auth is lazy — accessing .service triggers the error
        with pytest.raises(ValueError, match="YOUTUBE_API_KEY or GOOGLE_API_KEY required"):
            _ = client.service

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
    def test_get_transcript_success(self, mock_api_class: Mock) -> None:
        """Test successful transcript retrieval."""
        # Setup mock snippet objects (v1.2+ API returns objects, not dicts)
        mock_snippet1 = Mock()
        mock_snippet1.text = "Hello"
        mock_snippet1.start = 0.0
        mock_snippet1.duration = 1.5

        mock_snippet2 = Mock()
        mock_snippet2.text = "World"
        mock_snippet2.start = 1.5
        mock_snippet2.duration = 1.5

        mock_fetched = [mock_snippet1, mock_snippet2]

        mock_transcript = Mock()
        mock_transcript.fetch.return_value = mock_fetched
        mock_transcript.language_code = "en"
        mock_transcript.is_generated = False

        mock_list = Mock()
        mock_list.find_manually_created_transcript.return_value = mock_transcript

        # v1.2+ API: YouTubeTranscriptApi() returns instance, then call .list()
        mock_api_instance = Mock()
        mock_api_instance.list.return_value = mock_list
        mock_api_class.return_value = mock_api_instance

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
    def test_get_transcript_auto_generated(self, mock_api_class: Mock) -> None:
        """Test transcript retrieval falls back to auto-generated."""
        from youtube_transcript_api._errors import NoTranscriptFound

        # Setup mock snippet object (v1.2+ API)
        mock_snippet = Mock()
        mock_snippet.text = "Auto generated"
        mock_snippet.start = 0.0
        mock_snippet.duration = 2.0

        mock_transcript = Mock()
        mock_transcript.fetch.return_value = [mock_snippet]
        mock_transcript.language_code = "en"
        mock_transcript.is_generated = True

        mock_list = Mock()
        mock_list.find_manually_created_transcript.side_effect = NoTranscriptFound("test", [], [])
        mock_list.find_generated_transcript.return_value = mock_transcript

        mock_api_instance = Mock()
        mock_api_instance.list.return_value = mock_list
        mock_api_class.return_value = mock_api_instance

        client = YouTubeClient.__new__(YouTubeClient)

        result = client.get_transcript("test-video-id")

        assert result is not None
        assert result.is_auto_generated is True

    @patch("src.ingestion.youtube.YouTubeTranscriptApi")
    def test_get_transcript_disabled(self, mock_api_class: Mock) -> None:
        """Test transcript retrieval when transcripts are disabled."""
        from youtube_transcript_api._errors import TranscriptsDisabled

        mock_api_instance = Mock()
        mock_api_instance.list.side_effect = TranscriptsDisabled("test")
        mock_api_class.return_value = mock_api_instance

        client = YouTubeClient.__new__(YouTubeClient)

        result = client.get_transcript("test-video-id")

        assert result is None


class TestDefaultLanguages:
    """Tests for default language configuration."""

    def test_default_languages(self) -> None:
        """Test default languages are English variants."""
        assert "en" in DEFAULT_LANGUAGES
        assert "en-US" in DEFAULT_LANGUAGES
        assert "en-GB" in DEFAULT_LANGUAGES


class TestCLI:
    """Tests for CLI entry point.

    Note: CLI now uses YouTubeContentIngestionService (unified Content model)
    instead of legacy YouTubeIngestionService. The service methods are async,
    so main() bridges via asyncio.run().
    """

    @patch("src.ingestion.youtube.asyncio")
    @patch("src.ingestion.youtube.YouTubeContentIngestionService")
    def test_main_with_playlist_id(self, mock_service_class: Mock, mock_asyncio: Mock) -> None:
        """Test CLI with specific playlist ID."""
        import sys

        from src.ingestion.youtube import main

        mock_service = Mock()
        mock_service.ingest_playlist = AsyncMock(return_value=5)
        mock_service_class.return_value = mock_service
        mock_asyncio.run.return_value = 5

        with patch.object(
            sys, "argv", ["youtube", "--playlist-id", "PLtest", "--max-videos", "20"]
        ):
            main()

        # main() calls asyncio.run() with the coroutine from ingest_playlist
        mock_asyncio.run.assert_called_once()

    @patch("src.ingestion.youtube.asyncio")
    @patch("src.ingestion.youtube.YouTubeContentIngestionService")
    def test_main_public_only(self, mock_service_class: Mock, mock_asyncio: Mock) -> None:
        """Test CLI with public-only flag."""
        import sys

        from src.ingestion.youtube import main

        mock_service = Mock()
        mock_service.ingest_all_playlists = AsyncMock(return_value=0)
        mock_service_class.return_value = mock_service
        mock_asyncio.run.return_value = 0

        with patch.object(sys, "argv", ["youtube", "--public-only"]):
            main()

        # Should initialize service with use_oauth=False
        mock_service_class.assert_called_once_with(use_oauth=False)


class TestAsyncYouTubeIngestion:
    """Tests for async YouTubeContentIngestionService methods.

    These tests verify the async patterns: semaphore concurrency, parallel
    processing via gather, and empty/edge-case handling.
    """

    @pytest.mark.asyncio
    @patch("src.ingestion.youtube.settings")
    @patch("src.ingestion.youtube.asyncio.to_thread")
    async def test_ingest_playlist_empty(
        self,
        mock_to_thread: AsyncMock,
        mock_settings: Mock,
    ) -> None:
        """Verify 0 returned when no videos in playlist."""
        mock_to_thread.return_value = []
        mock_settings.youtube_max_concurrent_videos = 5

        service = YouTubeContentIngestionService.__new__(YouTubeContentIngestionService)
        service.client = Mock()

        count = await service.ingest_playlist(
            playlist_id="PLempty",
            max_videos=10,
        )

        assert count == 0

    @pytest.mark.asyncio
    @patch("src.ingestion.youtube.settings")
    async def test_ingest_all_playlists_concurrency(
        self,
        mock_settings: Mock,
    ) -> None:
        """Verify playlist-level semaphore limits concurrent playlist processing."""
        mock_settings.youtube_max_concurrent_playlists = 2
        mock_settings.youtube_max_concurrent_videos = 5
        mock_settings.youtube_keyframe_extraction = False

        service = YouTubeContentIngestionService.__new__(YouTubeContentIngestionService)
        service.client = Mock()
        service.client.oauth_available = True

        # Track concurrent execution to verify semaphore
        max_concurrent = 0
        current_concurrent = 0
        lock = asyncio.Lock()

        async def mock_ingest_playlist(**kwargs):
            nonlocal max_concurrent, current_concurrent
            async with lock:
                current_concurrent += 1
                max_concurrent = max(max_concurrent, current_concurrent)
            await asyncio.sleep(0.01)  # Simulate work
            async with lock:
                current_concurrent -= 1
            return 1

        service.ingest_playlist = mock_ingest_playlist

        # Create 4 playlist sources
        from src.config.sources import YouTubePlaylistSource

        sources = [YouTubePlaylistSource(id=f"PL{i}", name=f"Playlist {i}") for i in range(4)]

        total = await service.ingest_all_playlists(
            sources=sources,
            max_videos_per_playlist=5,
        )

        assert total == 4
        # Semaphore should limit to 2 concurrent playlists
        assert max_concurrent <= 2

    @pytest.mark.asyncio
    @patch("src.ingestion.youtube.settings")
    async def test_ingest_playlist_partial_failure(
        self,
        mock_settings: Mock,
    ) -> None:
        """Verify partial failure: gather with return_exceptions=True
        counts only successful results."""
        mock_settings.youtube_max_concurrent_videos = 5
        mock_settings.youtube_keyframe_extraction = False

        service = YouTubeContentIngestionService.__new__(YouTubeContentIngestionService)
        service.client = Mock()

        # Replace _process_video: vid2 raises, others succeed
        async def mock_process(video, playlist_id, **kwargs):
            if video["video_id"] == "vid2":
                raise RuntimeError("Processing failed")
            return True

        service._process_video = mock_process

        videos = [
            {
                "video_id": "vid1",
                "title": "Good 1",
                "channel_title": "Ch",
                "published_date": datetime(2024, 1, 1, tzinfo=UTC),
                "thumbnail_url": "",
            },
            {
                "video_id": "vid2",
                "title": "Bad",
                "channel_title": "Ch",
                "published_date": datetime(2024, 1, 2, tzinfo=UTC),
                "thumbnail_url": "",
            },
            {
                "video_id": "vid3",
                "title": "Good 2",
                "channel_title": "Ch",
                "published_date": datetime(2024, 1, 3, tzinfo=UTC),
                "thumbnail_url": "",
            },
        ]

        with patch("src.ingestion.youtube.asyncio.to_thread", return_value=videos):
            count = await service.ingest_playlist(
                playlist_id="PLtest",
                max_videos=10,
            )

        # Only vid1 and vid3 succeed; vid2 raised an exception
        assert count == 2


class TestAsyncYouTubeRSSIngestion:
    """Tests for async YouTubeRSSIngestionService methods."""

    @pytest.mark.asyncio
    @patch("src.ingestion.youtube.settings")
    async def test_ingest_all_feeds_concurrency(
        self,
        mock_settings: Mock,
    ) -> None:
        """Verify feed-level semaphore limits concurrent feed processing."""
        mock_settings.youtube_max_concurrent_playlists = 2
        mock_settings.youtube_max_concurrent_videos = 5

        service = YouTubeRSSIngestionService.__new__(YouTubeRSSIngestionService)
        service.client = Mock()

        max_concurrent = 0
        current_concurrent = 0
        lock = asyncio.Lock()

        async def mock_ingest_feed(**kwargs):
            nonlocal max_concurrent, current_concurrent
            async with lock:
                current_concurrent += 1
                max_concurrent = max(max_concurrent, current_concurrent)
            await asyncio.sleep(0.01)
            async with lock:
                current_concurrent -= 1
            return 2

        service.ingest_feed = mock_ingest_feed

        from src.config.sources import YouTubeRSSSource

        sources = [
            YouTubeRSSSource(
                url=f"https://youtube.com/feeds/videos.xml?channel_id=UC{i}",
                name=f"Feed {i}",
            )
            for i in range(4)
        ]

        total = await service.ingest_all_feeds(sources=sources, max_entries_per_feed=5)

        assert total == 8  # 4 feeds * 2 each
        # Semaphore should limit to 2 concurrent feeds
        assert max_concurrent <= 2


@pytest.mark.integration
class TestYouTubeIntegration:
    """Integration tests using real YouTube API.

    These tests require valid API credentials and network access.
    Run with: pytest -m integration tests/test_ingestion/test_youtube.py
    """

    @pytest.fixture
    def api_key_available(self) -> bool:
        """Check if YouTube API key is available."""
        from src.config.settings import settings

        return settings.get_youtube_api_key() is not None

    def test_get_public_playlist_videos(self, api_key_available: bool) -> None:
        """Test fetching videos from public test playlist."""
        if not api_key_available:
            pytest.skip("YOUTUBE_API_KEY or GOOGLE_API_KEY not configured")

        client = YouTubeClient(use_oauth=False)
        videos = client.get_playlist_videos(TEST_PUBLIC_PLAYLIST_ID, max_results=5)

        assert isinstance(videos, list)
        # Public playlist should have at least some videos
        if len(videos) > 0:
            video = videos[0]
            assert "video_id" in video
            assert "title" in video
            assert "channel_title" in video

    def test_get_transcript_from_public_playlist(self, api_key_available: bool) -> None:
        """Test fetching transcript from a video in public playlist."""
        if not api_key_available:
            pytest.skip("YOUTUBE_API_KEY or GOOGLE_API_KEY not configured")

        client = YouTubeClient(use_oauth=False)
        videos = client.get_playlist_videos(TEST_PUBLIC_PLAYLIST_ID, max_results=1)

        if not videos:
            pytest.skip("No videos in public test playlist")

        video_id = videos[0]["video_id"]
        transcript = client.get_transcript(video_id)

        # Transcript may or may not be available
        if transcript is not None:
            assert isinstance(transcript, YouTubeTranscript)
            assert transcript.video_id == video_id
            assert len(transcript.segments) > 0

    @pytest.fixture
    def oauth_available(self) -> bool:
        """Check if YouTube OAuth credentials are available."""
        import os

        from src.config.settings import settings

        return os.path.exists(settings.youtube_token_file)

    def test_get_private_playlist_videos(self, oauth_available: bool) -> None:
        """Test fetching videos from private test playlist (requires OAuth)."""
        if not oauth_available:
            pytest.skip("YouTube OAuth token not configured")

        client = YouTubeClient(use_oauth=True)
        videos = client.get_playlist_videos(TEST_PRIVATE_PLAYLIST_ID, max_results=5)

        assert isinstance(videos, list)
        # Private playlist should have videos if OAuth is working
        if len(videos) > 0:
            video = videos[0]
            assert "video_id" in video
            assert "title" in video
