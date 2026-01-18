"""YouTube keyframe extraction for slide detection using ffmpeg."""

import asyncio
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.config import settings
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Default scene change threshold for ffmpeg (0-1, lower = more sensitive)
DEFAULT_SCENE_THRESHOLD = 0.3

# Default similarity threshold (0-1, higher = more similar required to consider duplicate)
DEFAULT_SIMILARITY_THRESHOLD = 0.85


@dataclass
class SlideFrame:
    """A unique slide frame with metadata."""

    path: str
    timestamp: float
    hash_value: str = ""
    is_representative: bool = True


@dataclass
class KeyframeExtractionResult:
    """Result of keyframe extraction for a video."""

    video_id: str
    slides: list[SlideFrame] = field(default_factory=list)
    slide_count: int = 0
    extraction_method: str = ""  # "scene_detection" or "interval"
    error: str | None = None


class KeyframeExtractor:
    """Extract keyframes from YouTube videos using ffmpeg scene detection."""

    def __init__(self, output_dir: str | None = None) -> None:
        """
        Initialize keyframe extractor.

        Args:
            output_dir: Directory to store extracted keyframes
        """
        self.output_dir = output_dir or settings.youtube_temp_dir
        os.makedirs(self.output_dir, exist_ok=True)

    async def is_available(self) -> bool:
        """Check if ffmpeg and required dependencies are available."""
        try:
            await self._verify_ffmpeg()
            return True
        except RuntimeError:
            return False

    async def _verify_ffmpeg(self) -> None:
        """Verify ffmpeg is installed."""
        try:
            process = await asyncio.create_subprocess_exec(
                "ffmpeg",
                "-version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await process.communicate()
            if process.returncode != 0:
                raise OSError(stderr.decode())
        except (OSError, FileNotFoundError) as e:
            raise RuntimeError(
                "ffmpeg not found. Install with: apt install ffmpeg (Linux) "
                "or brew install ffmpeg (macOS)"
            ) from e

    async def download_video(self, video_id: str) -> str | None:
        """
        Download a YouTube video for processing.

        Args:
            video_id: YouTube video ID

        Returns:
            Path to downloaded video or None if failed
        """
        try:
            import yt_dlp
        except ImportError:
            logger.error("yt-dlp not installed. Install with: pip install yt-dlp")
            return None

        def _download_sync():
            """Run synchronous download in a separate thread."""
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            output_path = os.path.join(self.output_dir, f"{video_id}.mp4")

            ydl_opts: dict[str, Any] = {
                "format": "worst[ext=mp4]",  # Use lowest quality to save bandwidth
                "outtmpl": output_path,
                "quiet": True,
                "no_warnings": True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])

            if os.path.exists(output_path):
                logger.info(f"Downloaded video: {video_id}")
                return output_path
            return None

        try:
            return await asyncio.to_thread(_download_sync)
        except Exception as e:
            logger.error(f"Error downloading video {video_id}: {e}")
            return None

    async def get_video_duration(self, video_path: str) -> float:
        """
        Get video duration in seconds using ffprobe.

        Args:
            video_path: Path to video file

        Returns:
            Duration in seconds
        """
        try:
            cmd = [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                video_path,
            ]
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            if process.returncode != 0:
                logger.warning(f"Error getting duration: {stderr.decode()}")
                return 0.0
            return float(stdout.decode().strip())
        except Exception as e:
            logger.warning(f"Error getting duration: {e}")
            return 0.0

    async def extract_scene_changes(
        self,
        video_path: str,
        output_dir: str | None = None,
        scene_threshold: float | None = None,
        max_frames: int = 100,
    ) -> list[SlideFrame]:
        """
        Extract frames at scene changes using ffmpeg.

        This is ideal for presentations where slides have clear transitions.

        Args:
            video_path: Path to video file
            output_dir: Directory for extracted frames
            scene_threshold: Scene detection sensitivity (0-1, lower = more frames)
            max_frames: Maximum frames to extract

        Returns:
            List of SlideFrame objects with timestamps
        """
        if scene_threshold is None:
            scene_threshold = settings.youtube_scene_threshold

        if output_dir is None:
            video_name = Path(video_path).stem
            output_dir = os.path.join(self.output_dir, f"{video_name}_frames")

        os.makedirs(output_dir, exist_ok=True)

        # Use ffmpeg scene detection filter
        output_pattern = os.path.join(output_dir, "frame_%06d.jpg")

        try:
            # Extract frames at scene changes with timestamp metadata
            cmd = [
                "ffmpeg",
                "-i",
                video_path,
                "-vf",
                f"select='gt(scene,{scene_threshold})',showinfo",
                "-vsync",
                "vfr",
                "-frame_pts",
                "1",
                "-q:v",
                "2",  # High quality JPEG
                output_pattern,
                "-y",  # Overwrite
            ]

            # Run ffmpeg and capture showinfo output for timestamps
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await process.communicate()

            if process.returncode != 0:
                logger.error(f"ffmpeg error: {stderr.decode()}")
                return []

            # Parse timestamps from showinfo output
            timestamps = self._parse_showinfo_timestamps(stderr.decode())

            # Get list of extracted frames
            frame_files = sorted([f for f in os.listdir(output_dir) if f.endswith(".jpg")])[
                :max_frames
            ]

            slides = []
            for i, frame_file in enumerate(frame_files):
                frame_path = os.path.join(output_dir, frame_file)
                # Use parsed timestamp or estimate
                timestamp = timestamps[i] if i < len(timestamps) else i * 10.0

                slides.append(
                    SlideFrame(
                        path=frame_path,
                        timestamp=timestamp,
                        is_representative=True,
                    )
                )

            logger.info(f"Extracted {len(slides)} scene-change frames from {video_path}")
            return slides

        except Exception as e:
            logger.error(f"ffmpeg execution error: {e}")
            return []

    async def extract_interval_frames(
        self,
        video_path: str,
        output_dir: str | None = None,
        interval_seconds: float = 5.0,
        max_frames: int = 100,
    ) -> list[SlideFrame]:
        """
        Extract frames at fixed intervals.

        Alternative to scene detection for videos without clear transitions.

        Args:
            video_path: Path to video file
            output_dir: Directory for extracted frames
            interval_seconds: Seconds between frame captures
            max_frames: Maximum frames to extract

        Returns:
            List of SlideFrame objects with timestamps
        """
        if output_dir is None:
            video_name = Path(video_path).stem
            output_dir = os.path.join(self.output_dir, f"{video_name}_frames")

        os.makedirs(output_dir, exist_ok=True)
        output_pattern = os.path.join(output_dir, "frame_%06d.jpg")

        try:
            # Extract one frame every N seconds
            cmd = [
                "ffmpeg",
                "-i",
                video_path,
                "-vf",
                f"fps=1/{interval_seconds}",
                "-q:v",
                "2",
                output_pattern,
                "-y",
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await process.communicate()
            if process.returncode != 0:
                logger.error(f"ffmpeg error: {stderr.decode()}")
                return []

            # Get list of extracted frames
            frame_files = sorted([f for f in os.listdir(output_dir) if f.endswith(".jpg")])[
                :max_frames
            ]

            slides = []
            for i, frame_file in enumerate(frame_files):
                frame_path = os.path.join(output_dir, frame_file)
                timestamp = i * interval_seconds

                slides.append(
                    SlideFrame(
                        path=frame_path,
                        timestamp=timestamp,
                        is_representative=True,
                    )
                )

            logger.info(f"Extracted {len(slides)} interval frames from {video_path}")
            return slides

        except Exception as e:
            logger.error(f"ffmpeg execution error: {e}")
            return []

    def _parse_showinfo_timestamps(self, ffmpeg_output: str) -> list[float]:
        """
        Parse frame timestamps from ffmpeg showinfo filter output.

        Args:
            ffmpeg_output: stderr output from ffmpeg with showinfo

        Returns:
            List of timestamps in seconds
        """
        timestamps: list[float] = []
        # Pattern: pts_time:123.456
        pattern = r"pts_time:(\d+\.?\d*)"

        for match in re.finditer(pattern, ffmpeg_output):
            timestamps.append(float(match.group(1)))

        return timestamps

    async def compute_image_hash(self, image_path: str) -> str | None:
        """
        Compute perceptual hash of an image for similarity comparison.

        Args:
            image_path: Path to image file

        Returns:
            Hex string hash or None if failed
        """

        def _compute_sync():
            """Run synchronous image hashing in a separate thread."""
            try:
                import imagehash
                from PIL import Image
            except ImportError:
                logger.warning(
                    "imagehash/Pillow not installed. Install with: pip install imagehash Pillow"
                )
                return None

            try:
                img = Image.open(image_path)
                hash_value = imagehash.average_hash(img, hash_size=16)
                return str(hash_value)

            except Exception as e:
                logger.warning(f"Error computing hash for {image_path}: {e}")
                return None

        return await asyncio.to_thread(_compute_sync)

    def compute_hash_similarity(self, hash1: str, hash2: str) -> float:
        """
        Compute similarity between two image hashes.

        Args:
            hash1: First hash string
            hash2: Second hash string

        Returns:
            Similarity score between 0.0 (different) and 1.0 (identical)
        """
        try:
            import imagehash
        except ImportError:
            return 0.0

        try:
            h1 = imagehash.hex_to_hash(hash1)
            h2 = imagehash.hex_to_hash(hash2)
            distance = h1 - h2
            max_distance = 16 * 16
            return 1.0 - (distance / max_distance)

        except Exception as e:
            logger.warning(f"Error computing similarity: {e}")
            return 0.0

    async def deduplicate_slides(
        self,
        slides: list[SlideFrame],
        similarity_threshold: float | None = None,
    ) -> list[SlideFrame]:
        """
        Remove visually similar slides, keeping one per unique visual.

        Args:
            slides: List of SlideFrame objects (sorted by timestamp)
            similarity_threshold: Minimum similarity to consider as duplicate

        Returns:
            List of unique SlideFrame objects
        """
        if not slides:
            return []

        if similarity_threshold is None:
            similarity_threshold = settings.youtube_similarity_threshold

        # Compute hashes in parallel for slides that don't have one
        slides_to_hash = [s for s in slides if not s.hash_value]
        if slides_to_hash:
            hash_tasks = [self.compute_image_hash(s.path) for s in slides_to_hash]
            hashes = await asyncio.gather(*hash_tasks)
            for slide, hash_value in zip(slides_to_hash, hashes):
                slide.hash_value = hash_value or "unknown"

        unique_slides: list[SlideFrame] = []
        current_hash: str | None = None

        for slide in slides:
            if slide.hash_value == "unknown":
                unique_slides.append(slide)
                continue

            if current_hash is None:
                current_hash = slide.hash_value
                unique_slides.append(slide)
                continue

            similarity = self.compute_hash_similarity(current_hash, slide.hash_value)

            if similarity < similarity_threshold:
                # New unique slide
                current_hash = slide.hash_value
                unique_slides.append(slide)
                logger.debug(f"New slide at {slide.timestamp:.1f}s")
            else:
                logger.debug(f"Duplicate at {slide.timestamp:.1f}s (sim={similarity:.2f})")

        logger.info(f"Deduplicated: {len(slides)} -> {len(unique_slides)} unique slides")
        return unique_slides

    async def extract_unique_slides(
        self,
        video_path: str,
        output_dir: str | None = None,
        scene_threshold: float | None = None,
        similarity_threshold: float | None = None,
        max_frames: int = 100,
    ) -> tuple[list[SlideFrame], str]:
        """
        Extract unique slides using scene detection + deduplication.

        This is the main method - uses ffmpeg scene detection first,
        then deduplicates similar frames.

        Args:
            video_path: Path to video file
            output_dir: Directory for extracted frames
            scene_threshold: ffmpeg scene detection sensitivity
            similarity_threshold: Perceptual hash similarity threshold
            max_frames: Maximum frames to extract

        Returns:
            Tuple of (list of unique SlideFrame objects, extraction method used)
        """
        extraction_method = "scene_detection"

        # Step 1: Extract frames at scene changes
        slides = await self.extract_scene_changes(
            video_path=video_path,
            output_dir=output_dir,
            scene_threshold=scene_threshold,
            max_frames=max_frames,
        )

        if not slides:
            # Fallback to interval extraction if scene detection fails
            logger.info("Scene detection found no frames, falling back to intervals")
            extraction_method = "interval"
            duration = await self.get_video_duration(video_path)
            interval = max(5.0, duration / 50)  # Aim for ~50 frames

            slides = await self.extract_interval_frames(
                video_path=video_path,
                output_dir=output_dir,
                interval_seconds=interval,
                max_frames=max_frames,
            )

        # Step 2: Deduplicate similar frames
        unique_slides = await self.deduplicate_slides(
            slides=slides,
            similarity_threshold=similarity_threshold,
        )

        # Step 3: Clean up duplicate files
        unique_paths = {s.path for s in unique_slides}
        for slide in slides:
            if slide.path not in unique_paths:
                try:
                    os.remove(slide.path)
                except OSError:
                    pass

        return unique_slides, extraction_method

    def match_slides_to_transcript(
        self,
        slides: list[SlideFrame],
        transcript_segments: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Match slides to transcript segments by timestamp.

        Args:
            slides: List of SlideFrame objects
            transcript_segments: Transcript with start times

        Returns:
            List of dicts with slide path, timestamp, and transcript text
        """
        if not slides or not transcript_segments:
            return []

        matched: list[dict[str, Any]] = []
        for slide in slides:
            # Find closest transcript segment
            closest = min(transcript_segments, key=lambda s: abs(s["start"] - slide.timestamp))

            matched.append(
                {
                    "frame_path": slide.path,
                    "timestamp": slide.timestamp,
                    "transcript_text": closest["text"],
                    "transcript_start": closest["start"],
                    "hash": slide.hash_value,
                }
            )

        return matched

    async def extract_keyframes_for_video(
        self,
        video_id: str,
        transcript_segments: list[dict[str, Any]] | None = None,
    ) -> KeyframeExtractionResult:
        """
        Full keyframe extraction pipeline for a YouTube video.

        Downloads video, extracts unique slides, matches to transcript,
        and cleans up.

        Args:
            video_id: YouTube video ID
            transcript_segments: Optional transcript segments for matching

        Returns:
            KeyframeExtractionResult with slides and metadata
        """
        result = KeyframeExtractionResult(video_id=video_id)

        # Verify ffmpeg is available
        try:
            await self._verify_ffmpeg()
        except RuntimeError as e:
            result.error = str(e)
            return result

        # Download video
        video_path = await self.download_video(video_id)
        if not video_path:
            result.error = "Failed to download video"
            return result

        try:
            # Extract unique slides
            slides, method = await self.extract_unique_slides(video_path)
            result.extraction_method = method

            if not slides:
                result.error = "No slides extracted"
                return result

            # Match to transcript if provided
            if transcript_segments:
                self.match_slides_to_transcript(slides, transcript_segments)

            result.slides = slides
            result.slide_count = len(slides)

            logger.info(
                f"Extracted {len(slides)} unique slides from video {video_id} using {method}"
            )

        finally:
            # Clean up downloaded video
            if video_path and os.path.exists(video_path):
                try:
                    os.remove(video_path)
                    logger.debug(f"Cleaned up video file: {video_path}")
                except OSError as e:
                    logger.warning(f"Failed to clean up video file: {e}")

        return result

    def cleanup_frames_dir(self, video_id: str) -> None:
        """
        Clean up extracted frames directory for a video.

        Args:
            video_id: YouTube video ID
        """
        frames_dir = os.path.join(self.output_dir, f"{video_id}_frames")
        if os.path.exists(frames_dir):
            try:
                import shutil

                shutil.rmtree(frames_dir)
                logger.debug(f"Cleaned up frames directory: {frames_dir}")
            except Exception as e:
                logger.warning(f"Failed to clean up frames directory: {e}")
