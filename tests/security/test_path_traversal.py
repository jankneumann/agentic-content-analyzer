import sys
from unittest.mock import MagicMock, patch

import pytest

# Mock dependencies
sys.modules["google"] = MagicMock()
sys.modules["google.auth"] = MagicMock()
sys.modules["google.auth.transport"] = MagicMock()
sys.modules["google.auth.transport.requests"] = MagicMock()
sys.modules["google.oauth2"] = MagicMock()
sys.modules["google.oauth2.credentials"] = MagicMock()
sys.modules["google_auth_oauthlib"] = MagicMock()
sys.modules["google_auth_oauthlib.flow"] = MagicMock()
sys.modules["googleapiclient"] = MagicMock()
sys.modules["googleapiclient.discovery"] = MagicMock()
sys.modules["googleapiclient.errors"] = MagicMock()
sys.modules["youtube_transcript_api"] = MagicMock()
sys.modules["youtube_transcript_api._errors"] = MagicMock()
sys.modules["httpx"] = MagicMock()
sys.modules["feedparser"] = MagicMock()
sys.modules["bs4"] = MagicMock()
sys.modules["markitdown"] = MagicMock()

# Mock Settings to avoid validation errors
mock_settings = MagicMock()
mock_settings.youtube_temp_dir = "/tmp/youtube_downloads"  # noqa: S108
mock_settings.youtube_scene_threshold = 0.3
mock_settings.youtube_similarity_threshold = 0.85

mock_config = MagicMock()
mock_config.settings = mock_settings

sys.modules["src.config"] = mock_config
sys.modules["src.config.settings"] = mock_config

# Mock logging
sys.modules["src.utils.logging"] = MagicMock()

from src.ingestion.youtube_keyframes import KeyframeExtractor  # noqa: E402


class TestPathTraversal:
    @pytest.fixture
    def extractor(self):
        with patch("src.ingestion.youtube_keyframes.KeyframeExtractor._verify_ffmpeg"):
            return KeyframeExtractor(output_dir="/tmp/test")  # noqa: S108

    def test_path_traversal_video_id(self, extractor):
        """Test that invalid video IDs with path traversal characters are rejected."""
        # Malicious video ID
        malicious_id = "../../evil"

        # We expect a ValueError when providing a malicious ID
        with pytest.raises(ValueError, match="Invalid video ID"):
            extractor.download_video(malicious_id)

    def test_shell_injection_video_id(self, extractor):
        """Test that invalid video IDs with shell characters are rejected."""
        # Malicious video ID
        malicious_id = "video; rm -rf /"

        with pytest.raises(ValueError, match="Invalid video ID"):
            extractor.download_video(malicious_id)

    def test_valid_video_id(self, extractor):
        """Test that valid video IDs are accepted."""
        valid_id = "dQw4w9WgXcQ"

        # Mock yt_dlp module
        mock_ytdlp_module = MagicMock()
        mock_ytdlp_context = MagicMock()
        mock_ytdlp_module.YoutubeDL.return_value.__enter__.return_value = mock_ytdlp_context

        with patch.dict("sys.modules", {"yt_dlp": mock_ytdlp_module}):
            # We also need to mock os.path.exists to return True so it returns the path
            with patch("os.path.exists", return_value=True):
                result = extractor.download_video(valid_id)
                assert result is not None
                assert valid_id in result
