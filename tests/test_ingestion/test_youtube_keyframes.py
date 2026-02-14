"""Tests for YouTube keyframe extraction."""

import tempfile
from unittest.mock import AsyncMock, Mock, patch

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
    """Tests for KeyframeExtractor class.

    All extraction methods are now async (subprocess → asyncio.create_subprocess_exec,
    blocking I/O → asyncio.to_thread). Tests use @pytest.mark.asyncio and AsyncMock.
    """

    @pytest.fixture
    def mock_extractor(self) -> KeyframeExtractor:
        """Create extractor with mocked output dir creation.

        Note: __init__ does not call _verify_ffmpeg (it is called lazily
        from is_available and extract_keyframes_for_video), so no async
        patching is needed for construction.
        """
        with patch("os.makedirs"):
            return KeyframeExtractor(output_dir="/tmp/test_keyframes")  # noqa: S108

    def test_init_creates_output_dir(self) -> None:
        """Test initialization creates output directory."""
        test_dir = "/tmp/test_output"  # noqa: S108
        with patch("os.makedirs") as mock_makedirs:
            KeyframeExtractor(output_dir=test_dir)
            mock_makedirs.assert_called_once_with(test_dir, exist_ok=True)

    @pytest.mark.asyncio
    async def test_is_available_true(self, mock_extractor: KeyframeExtractor) -> None:
        """Test is_available returns True when ffmpeg exists."""
        with patch.object(mock_extractor, "_verify_ffmpeg", new_callable=AsyncMock):
            assert await mock_extractor.is_available() is True

    @pytest.mark.asyncio
    async def test_is_available_false(self, mock_extractor: KeyframeExtractor) -> None:
        """Test is_available returns False when ffmpeg missing."""
        with patch.object(
            mock_extractor,
            "_verify_ffmpeg",
            new_callable=AsyncMock,
            side_effect=RuntimeError("ffmpeg not found"),
        ):
            assert await mock_extractor.is_available() is False

    @pytest.mark.asyncio
    async def test_verify_ffmpeg_success(self) -> None:
        """Test ffmpeg verification succeeds."""
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"ffmpeg version 6.0", b""))
        mock_process.returncode = 0

        extractor = KeyframeExtractor.__new__(KeyframeExtractor)
        extractor.output_dir = "/tmp/test"  # noqa: S108

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            await extractor._verify_ffmpeg()

    @pytest.mark.asyncio
    async def test_verify_ffmpeg_not_found(self) -> None:
        """Test ffmpeg verification fails when not found."""
        extractor = KeyframeExtractor.__new__(KeyframeExtractor)

        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError(),
        ):
            with pytest.raises(RuntimeError, match="ffmpeg not found"):
                await extractor._verify_ffmpeg()

    @pytest.mark.asyncio
    async def test_get_video_duration(self, mock_extractor: KeyframeExtractor) -> None:
        """Test getting video duration."""
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"123.456\n", b""))
        mock_process.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            duration = await mock_extractor.get_video_duration("/path/to/video.mp4")

        assert duration == 123.456

    @pytest.mark.asyncio
    async def test_get_video_duration_error(self, mock_extractor: KeyframeExtractor) -> None:
        """Test getting duration returns 0 on error."""
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b"error"))
        mock_process.returncode = 1

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            duration = await mock_extractor.get_video_duration("/path/to/video.mp4")

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

    @pytest.mark.asyncio
    async def test_extract_scene_changes(
        self,
        mock_extractor: KeyframeExtractor,
    ) -> None:
        """Test scene change extraction."""
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b"pts_time:0.000\npts_time:10.500"))
        mock_process.returncode = 0

        with (
            patch("asyncio.create_subprocess_exec", return_value=mock_process),
            patch("os.listdir", return_value=["frame_000001.jpg", "frame_000002.jpg"]),
            patch("os.makedirs"),
        ):
            slides = await mock_extractor.extract_scene_changes(
                video_path="/path/to/video.mp4",
                output_dir="/tmp/frames",  # noqa: S108
                scene_threshold=0.3,
            )

        assert len(slides) == 2
        assert slides[0].timestamp == 0.0
        assert slides[1].timestamp == 10.5

    @pytest.mark.asyncio
    async def test_extract_interval_frames(
        self,
        mock_extractor: KeyframeExtractor,
    ) -> None:
        """Test interval-based frame extraction."""
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_process.returncode = 0

        with (
            patch("asyncio.create_subprocess_exec", return_value=mock_process),
            patch(
                "os.listdir",
                return_value=[
                    "frame_000001.jpg",
                    "frame_000002.jpg",
                    "frame_000003.jpg",
                ],
            ),
            patch("os.makedirs"),
        ):
            slides = await mock_extractor.extract_interval_frames(
                video_path="/path/to/video.mp4",
                output_dir="/tmp/frames",  # noqa: S108
                interval_seconds=5.0,
            )

        assert len(slides) == 3
        assert slides[0].timestamp == 0.0
        assert slides[1].timestamp == 5.0
        assert slides[2].timestamp == 10.0

    @pytest.mark.asyncio
    async def test_deduplicate_slides_empty(self, mock_extractor: KeyframeExtractor) -> None:
        """Test deduplication with empty list."""
        result = await mock_extractor.deduplicate_slides([])
        assert result == []

    @pytest.mark.asyncio
    @patch.object(KeyframeExtractor, "compute_image_hash", new_callable=AsyncMock)
    @patch.object(KeyframeExtractor, "compute_hash_similarity")
    async def test_deduplicate_slides_removes_duplicates(
        self,
        mock_similarity: Mock,
        mock_hash: AsyncMock,
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

        result = await mock_extractor.deduplicate_slides(slides, similarity_threshold=0.85)

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
    async def extractor_if_available(self) -> KeyframeExtractor | None:
        """Create extractor only if ffmpeg is available."""
        with tempfile.TemporaryDirectory() as tmpdir:
            extractor = KeyframeExtractor(output_dir=tmpdir)
            if await extractor.is_available():
                return extractor
            return None

    @pytest.mark.skip(reason="Requires ffmpeg and network access")
    @pytest.mark.asyncio
    async def test_full_extraction_pipeline(
        self, extractor_if_available: KeyframeExtractor | None
    ) -> None:
        """Test full extraction pipeline with real video."""
        if extractor_if_available is None:
            pytest.skip("ffmpeg not available")

        # This would test with a real video
        # result = await extractor_if_available.extract_keyframes_for_video("dQw4w9WgXcQ")
        # assert result.slide_count > 0


class TestDefaultValues:
    """Tests for default configuration values."""

    def test_default_scene_threshold(self) -> None:
        """Test default scene threshold."""
        assert DEFAULT_SCENE_THRESHOLD == 0.3

    def test_default_similarity_threshold(self) -> None:
        """Test default similarity threshold."""
        assert DEFAULT_SIMILARITY_THRESHOLD == 0.85
