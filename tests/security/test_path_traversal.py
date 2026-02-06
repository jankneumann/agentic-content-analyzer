"""Security tests for path traversal vulnerabilities in YouTube keyframe extraction.

These tests verify that malicious video IDs with path traversal or shell injection
characters are properly rejected.
"""

from unittest.mock import MagicMock, patch

import pytest


class TestPathTraversal:
    """Test path traversal and shell injection prevention in KeyframeExtractor."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings with required YouTube configuration."""
        mock = MagicMock()
        mock.youtube_temp_dir = "/tmp/youtube_downloads"  # noqa: S108
        mock.youtube_scene_threshold = 0.3
        mock.youtube_similarity_threshold = 0.85
        return mock

    @pytest.fixture
    def extractor(self, mock_settings):
        """Create a KeyframeExtractor instance with mocked dependencies."""
        # Patch settings in both the module and where it's imported
        with patch("src.config.settings", mock_settings):
            with patch("src.ingestion.youtube_keyframes.settings", mock_settings):
                # Import after patching
                from src.ingestion.youtube_keyframes import KeyframeExtractor

                with patch.object(KeyframeExtractor, "_verify_ffmpeg"):
                    yield KeyframeExtractor(output_dir="/tmp/test")  # noqa: S108

    def test_path_traversal_video_id(self, extractor):
        """Test that invalid video IDs with path traversal characters are rejected."""
        malicious_id = "../../evil"

        with pytest.raises(ValueError, match="Invalid video ID"):
            extractor.download_video(malicious_id)

    def test_shell_injection_video_id(self, extractor):
        """Test that invalid video IDs with shell characters are rejected."""
        malicious_id = "video; rm -rf /"

        with pytest.raises(ValueError, match="Invalid video ID"):
            extractor.download_video(malicious_id)

    def test_valid_video_id(self, extractor, mock_settings):
        """Test that valid video IDs are accepted."""
        valid_id = "dQw4w9WgXcQ"

        mock_ytdlp_module = MagicMock()
        mock_ytdlp_context = MagicMock()
        mock_ytdlp_module.YoutubeDL.return_value.__enter__.return_value = mock_ytdlp_context

        with patch("src.config.settings", mock_settings):
            with patch("src.ingestion.youtube_keyframes.settings", mock_settings):
                with patch.dict("sys.modules", {"yt_dlp": mock_ytdlp_module}):
                    with patch("os.path.exists", return_value=True):
                        result = extractor.download_video(valid_id)
                        assert result is not None
                        assert valid_id in result
