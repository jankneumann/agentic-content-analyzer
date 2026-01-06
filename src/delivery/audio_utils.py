"""Audio utilities for MP3 manipulation using ffmpeg.

Provides functions for concatenating MP3 files via WAV intermediate format
for maximum compatibility across different TTS sources.
"""

import subprocess
import tempfile
from pathlib import Path

from src.utils.logging import get_logger

logger = get_logger(__name__)


def concatenate_mp3_files(mp3_bytes_list: list[bytes], output_path: Path) -> None:
    """Concatenate MP3 files via WAV intermediate for robust compatibility.

    Converts all MP3 segments to WAV, concatenates them, then encodes
    the final result to MP3. This ensures consistent format regardless
    of source encoding differences.

    Args:
        mp3_bytes_list: List of MP3 audio data as bytes
        output_path: Where to write the final concatenated MP3

    Raises:
        RuntimeError: If ffmpeg operations fail
        ValueError: If mp3_bytes_list is empty
    """
    if not mp3_bytes_list:
        raise ValueError("Cannot concatenate empty list of MP3 files")

    if len(mp3_bytes_list) == 1:
        # Single file - just write directly
        output_path.write_bytes(mp3_bytes_list[0])
        logger.debug(f"Single MP3 file written directly to {output_path}")
        return

    mp3_temp_files = []
    wav_temp_files = []
    concat_file_path = None
    combined_wav_path = None

    try:
        # Step 1: Write MP3 bytes to temp files and convert each to WAV
        for i, mp3_bytes in enumerate(mp3_bytes_list):
            # Write MP3 to temp file
            mp3_temp = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{i}.mp3", mode="wb")
            mp3_temp.write(mp3_bytes)
            mp3_temp.close()
            mp3_temp_files.append(mp3_temp.name)

            # Convert MP3 to WAV (normalize to consistent format)
            wav_temp = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{i}.wav")
            wav_temp.close()
            wav_temp_files.append(wav_temp.name)

            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                mp3_temp.name,
                "-acodec",
                "pcm_s16le",  # Standard WAV format
                "-ar",
                "24000",  # Match OpenAI TTS sample rate
                "-ac",
                "1",  # Mono
                wav_temp.name,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"MP3 to WAV conversion failed: {result.stderr}")

        logger.debug(
            f"Converted {len(wav_temp_files)} MP3 files to WAV "
            f"(total input size: {sum(len(b) for b in mp3_bytes_list) / 1024:.1f} KB)"
        )

        # Step 2: Create concat file list for ffmpeg
        concat_file = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        for wav_file in wav_temp_files:
            escaped_path = wav_file.replace("'", "'\\''")
            concat_file.write(f"file '{escaped_path}'\n")
        concat_file.close()
        concat_file_path = concat_file.name

        # Step 3: Concatenate WAV files
        combined_wav = tempfile.NamedTemporaryFile(delete=False, suffix="_combined.wav")
        combined_wav.close()
        combined_wav_path = combined_wav.name

        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            concat_file_path,
            "-c",
            "copy",
            combined_wav_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"WAV concatenation failed: {result.stderr}")

        logger.debug(f"Combined WAV size: {Path(combined_wav_path).stat().st_size / 1024:.1f} KB")

        # Step 4: Convert combined WAV to MP3
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            combined_wav_path,
            "-acodec",
            "libmp3lame",
            "-b:a",
            "192k",  # Good quality bitrate
            "-ar",
            "24000",  # Keep sample rate
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"WAV to MP3 conversion failed: {result.stderr}")

        logger.info(
            f"Successfully concatenated {len(mp3_bytes_list)} segments to {output_path} "
            f"({output_path.stat().st_size / 1024:.1f} KB)"
        )

    except Exception as e:
        logger.error(f"MP3 concatenation failed: {e}")
        raise RuntimeError(f"MP3 concatenation failed: {e}")

    finally:
        # Clean up all temp files
        for f in mp3_temp_files:
            try:
                Path(f).unlink(missing_ok=True)
            except Exception:
                pass
        for f in wav_temp_files:
            try:
                Path(f).unlink(missing_ok=True)
            except Exception:
                pass
        if concat_file_path:
            try:
                Path(concat_file_path).unlink(missing_ok=True)
            except Exception:
                pass
        if combined_wav_path:
            try:
                Path(combined_wav_path).unlink(missing_ok=True)
            except Exception:
                pass
