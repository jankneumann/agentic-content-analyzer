"""Tests for YouTube keyframe extraction."""

import subprocess
import tempfile
from unittest.mock import Mock, patch

import pytest

from src.ingestion.youtube_keyframes import (
    DEFAULT_SCENE_THRESHOLD,
    DEFAULT_SIMILARITY_THRESHOLD,
    KeyframeExtractionResult,
    KeyframeExtractor,
    SlideFrame,
)


class TestSlideFrame:
    """Tests for SlideFrame dataclass."""

    def test_creation(self) -> None:
        """Test SlideFrame creation with defaults."""
        frame = SlideFrame(path="/path/to/frame.jpg", timestamp=10.5)

        assert frame.path == "/path/to/frame.jpg"
        assert frame.timestamp == 10.5
        assert frame.hash_value == ""
        assert frame.is_representative is True

    def test_with_hash(self) -> None:
        """Test SlideFrame with hash value."""
        frame = SlideFrame(
            path="/path/to/frame.jpg",
            timestamp=10.5,
            hash_value="abc123",
            is_representative=False,
        )

        assert frame.hash_value == "abc123"
        assert frame.is_representative is False


class TestKeyframeExtractionResult:
    """Tests for KeyframeExtractionResult dataclass."""

    def test_creation_empty(self) -> None:
        """Test creation with empty slides."""
        result = KeyframeExtractionResult(video_id="vid123")

        assert result.video_id == "vid123"
        assert result.slides == []
        assert result.slide_count == 0
        assert result.extraction_method == ""
        assert result.error is None

    def test_creation_with_error(self) -> None:
        """Test creation with error."""
        result = KeyframeExtractionResult(
            video_id="vid123",
            error="ffmpeg not found",
        )

        assert result.error == "ffmpeg not found"

    def test_creation_with_slides(self) -> None:
        """Test creation with slides."""
        slides = [
            SlideFrame(path="/frame1.jpg", timestamp=0.0),
            SlideFrame(path="/frame2.jpg", timestamp=10.0),
        ]
        result = KeyframeExtractionResult(
            video_id="vid123",
            slides=slides,
            slide_count=2,
            extraction_method="scene_detection",
        )

        assert len(result.slides) == 2
        assert result.slide_count == 2
        assert result.extraction_method == "scene_detection"


class TestKeyframeExtractor:
    """Tests for KeyframeExtractor class."""

    @pytest.fixture
    def mock_extractor(self) -> KeyframeExtractor:
        """Create extractor with mocked ffmpeg verification."""
        with patch.object(KeyframeExtractor, "_verify_ffmpeg"):
            return KeyframeExtractor(output_dir="/tmp/test_keyframes")  # noqa: S108

    def test_init_creates_output_dir(self) -> None:
        """Test initialization creates output directory."""
        test_dir = "/tmp/test_output"  # noqa: S108
        with (
            patch.object(KeyframeExtractor, "_verify_ffmpeg"),
            patch("os.makedirs") as mock_makedirs,
        ):
            KeyframeExtractor(output_dir=test_dir)
            mock_makedirs.assert_called_once_with(test_dir, exist_ok=True)

    def test_is_available_true(self, mock_extractor: KeyframeExtractor) -> None:
        """Test is_available returns True when ffmpeg exists."""
        with patch.object(mock_extractor, "_verify_ffmpeg"):
            assert mock_extractor.is_available() is True

    def test_is_available_false(self, mock_extractor: KeyframeExtractor) -> None:
        """Test is_available returns False when ffmpeg missing."""
        with patch.object(
            mock_extractor, "_verify_ffmpeg", side_effect=RuntimeError("ffmpeg not found")
        ):
            assert mock_extractor.is_available() is False

    @patch("subprocess.run")
    def test_verify_ffmpeg_success(self, mock_run: Mock) -> None:
        """Test ffmpeg verification succeeds."""
        mock_run.return_value = Mock(returncode=0)

        with patch("os.makedirs"):
            extractor = KeyframeExtractor.__new__(KeyframeExtractor)
            extractor.output_dir = "/tmp/test"  # noqa: S108
            extractor._verify_ffmpeg()

        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_verify_ffmpeg_not_found(self, mock_run: Mock) -> None:
        """Test ffmpeg verification fails when not found."""
        mock_run.side_effect = FileNotFoundError()

        extractor = KeyframeExtractor.__new__(KeyframeExtractor)

        with pytest.raises(RuntimeError, match="ffmpeg not found"):
            extractor._verify_ffmpeg()

    @patch("subprocess.run")
    def test_get_video_duration(self, mock_run: Mock, mock_extractor: KeyframeExtractor) -> None:
        """Test getting video duration."""
        mock_run.return_value = Mock(stdout="123.456\n", returncode=0)

        duration = mock_extractor.get_video_duration("/path/to/video.mp4")

        assert duration == 123.456

    @patch("subprocess.run")
    def test_get_video_duration_error(
        self, mock_run: Mock, mock_extractor: KeyframeExtractor
    ) -> None:
        """Test getting duration returns 0 on error."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "ffprobe")

        duration = mock_extractor.get_video_duration("/path/to/video.mp4")

        assert duration == 0.0

    def test_parse_showinfo_timestamps(self, mock_extractor: KeyframeExtractor) -> None:
        """Test parsing timestamps from ffmpeg showinfo output."""
        ffmpeg_output = """
        [Parsed_showinfo_0] n:0 pts:0 pts_time:0.000 pos:48 fmt:yuv420p
        [Parsed_showinfo_0] n:1 pts:300 pts_time:10.500 pos:12345 fmt:yuv420p
        [Parsed_showinfo_0] n:2 pts:600 pts_time:21.000 pos:23456 fmt:yuv420p
        """

        timestamps = mock_extractor._parse_showinfo_timestamps(ffmpeg_output)

        assert len(timestamps) == 3
        assert timestamps[0] == 0.0
        assert timestamps[1] == 10.5
        assert timestamps[2] == 21.0

    def test_parse_showinfo_timestamps_empty(self, mock_extractor: KeyframeExtractor) -> None:
        """Test parsing empty output returns empty list."""
        timestamps = mock_extractor._parse_showinfo_timestamps("")
        assert timestamps == []

    @patch("subprocess.run")
    @patch("os.listdir")
    @patch("os.makedirs")
    def test_extract_scene_changes(
        self,
        mock_makedirs: Mock,
        mock_listdir: Mock,
        mock_run: Mock,
        mock_extractor: KeyframeExtractor,
    ) -> None:
        """Test scene change extraction."""
        mock_run.return_value = Mock(
            stderr="pts_time:0.000\npts_time:10.500",
            returncode=0,
        )
        mock_listdir.return_value = ["frame_000001.jpg", "frame_000002.jpg"]

        slides = mock_extractor.extract_scene_changes(
            video_path="/path/to/video.mp4",
            output_dir="/tmp/frames",  # noqa: S108
            scene_threshold=0.3,
        )

        assert len(slides) == 2
        assert slides[0].timestamp == 0.0
        assert slides[1].timestamp == 10.5

    @patch("subprocess.run")
    @patch("os.listdir")
    @patch("os.makedirs")
    def test_extract_interval_frames(
        self,
        mock_makedirs: Mock,
        mock_listdir: Mock,
        mock_run: Mock,
        mock_extractor: KeyframeExtractor,
    ) -> None:
        """Test interval-based frame extraction."""
        mock_run.return_value = Mock(returncode=0)
        mock_listdir.return_value = [
            "frame_000001.jpg",
            "frame_000002.jpg",
            "frame_000003.jpg",
        ]

        slides = mock_extractor.extract_interval_frames(
            video_path="/path/to/video.mp4",
            output_dir="/tmp/frames",  # noqa: S108
            interval_seconds=5.0,
        )

        assert len(slides) == 3
        assert slides[0].timestamp == 0.0
        assert slides[1].timestamp == 5.0
        assert slides[2].timestamp == 10.0

    def test_deduplicate_slides_empty(self, mock_extractor: KeyframeExtractor) -> None:
        """Test deduplication with empty list."""
        result = mock_extractor.deduplicate_slides([])
        assert result == []

    @patch.object(KeyframeExtractor, "compute_image_hash")
    @patch.object(KeyframeExtractor, "compute_hash_similarity")
    def test_deduplicate_slides_removes_duplicates(
        self,
        mock_similarity: Mock,
        mock_hash: Mock,
        mock_extractor: KeyframeExtractor,
    ) -> None:
        """Test deduplication removes similar slides."""
        mock_hash.side_effect = ["hash1", "hash1", "hash2", "hash2"]
        # First comparison: similar (0.95), second: different (0.50), third: similar
        mock_similarity.side_effect = [0.95, 0.50, 0.90]

        slides = [
            SlideFrame(path="/frame1.jpg", timestamp=0.0),
            SlideFrame(path="/frame2.jpg", timestamp=5.0),
            SlideFrame(path="/frame3.jpg", timestamp=10.0),
            SlideFrame(path="/frame4.jpg", timestamp=15.0),
        ]

        result = mock_extractor.deduplicate_slides(slides, similarity_threshold=0.85)

        # Should keep frames 1, 3 (frame 2 similar to 1, frame 4 similar to 3)
        assert len(result) == 2

    def test_match_slides_to_transcript_empty(self, mock_extractor: KeyframeExtractor) -> None:
        """Test matching with empty inputs."""
        result = mock_extractor.match_slides_to_transcript([], [])
        assert result == []

    def test_match_slides_to_transcript(self, mock_extractor: KeyframeExtractor) -> None:
        """Test matching slides to transcript segments."""
        slides = [
            SlideFrame(path="/frame1.jpg", timestamp=5.0, hash_value="hash1"),
            SlideFrame(path="/frame2.jpg", timestamp=15.0, hash_value="hash2"),
        ]
        transcript = [
            {"text": "First segment", "start": 0.0, "duration": 10.0},
            {"text": "Second segment", "start": 10.0, "duration": 10.0},
        ]

        result = mock_extractor.match_slides_to_transcript(slides, transcript)

        assert len(result) == 2
        assert result[0]["transcript_text"] == "First segment"
        assert result[0]["timestamp"] == 5.0
        assert result[1]["transcript_text"] == "Second segment"
        assert result[1]["timestamp"] == 15.0


class TestKeyframeExtractorIntegration:
    """Integration tests for KeyframeExtractor (may require ffmpeg)."""

    @pytest.fixture
    def extractor_if_available(self) -> KeyframeExtractor | None:
        """Create extractor only if ffmpeg is available."""
        try:
            subprocess.run(
                ["ffmpeg", "-version"],  # noqa: S607
                capture_output=True,
                check=True,
            )
            with tempfile.TemporaryDirectory() as tmpdir:
                return KeyframeExtractor(output_dir=tmpdir)
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

    @pytest.mark.skip(reason="Requires ffmpeg and network access")
    def test_full_extraction_pipeline(
        self, extractor_if_available: KeyframeExtractor | None
    ) -> None:
        """Test full extraction pipeline with real video."""
        if extractor_if_available is None:
            pytest.skip("ffmpeg not available")

        # This would test with a real video
        # result = extractor_if_available.extract_keyframes_for_video("dQw4w9WgXcQ")
        # assert result.slide_count > 0


class TestDefaultValues:
    """Tests for default configuration values."""

    def test_default_scene_threshold(self) -> None:
        """Test default scene threshold."""
        assert DEFAULT_SCENE_THRESHOLD == 0.3

    def test_default_similarity_threshold(self) -> None:
        """Test default similarity threshold."""
        assert DEFAULT_SIMILARITY_THRESHOLD == 0.85
