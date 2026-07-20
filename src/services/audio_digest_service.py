"""Public digest narration boundary used by durable workflows."""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.delivery.audio_utils import concatenate_mp3_files
from src.delivery.text_chunker import TextChunker
from src.delivery.tts_service import TTSService
from src.models.digest import Digest
from src.processors.digest_text_preparer import DigestTextPreparer
from src.services.file_storage import FileStorageProvider, get_storage


@dataclass(frozen=True)
class AudioDigestArtifact:
    """Stored narration output ready for workflow-owned persistence."""

    storage_path: str
    duration_seconds: float
    file_size_bytes: int
    text_char_count: int
    chunk_count: int


class AudioDigestService:
    """Narrate and store one digest without creating ORM records."""

    def __init__(
        self,
        *,
        tts: TTSService,
        storage: FileStorageProvider | None = None,
        text_preparer: DigestTextPreparer | None = None,
    ) -> None:
        self.tts = tts
        self.storage = storage or get_storage(bucket="audio-digests")
        self.text_preparer = text_preparer or DigestTextPreparer(use_ssml=tts.supports_ssml)

    async def generate(
        self,
        digest: Digest | Any,
        *,
        audio_digest_id: int,
        voice_id: str,
        speed: float,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> AudioDigestArtifact:
        """Generate narration for a workflow-reserved audio digest identifier."""

        text = self.text_preparer.prepare_digest(digest)
        chunks = TextChunker(provider=self.tts.provider_name).chunk(text)
        if not chunks:
            raise ValueError("Digest narration text is empty")

        segments: list[bytes] = []
        for index, chunk in enumerate(chunks, 1):
            if progress_callback:
                progress_callback(index, len(chunks), f"Synthesizing chunk {index}/{len(chunks)}")
            segments.append(await self.tts.synthesize_voice(chunk.text, voice_id, speed=speed))
        audio = self._combine(segments)
        filename = f"audio_digest_{audio_digest_id}.mp3"
        storage_path = await self.storage.save(
            data=audio,
            filename=filename,
            content_type="audio/mpeg",
        )
        return AudioDigestArtifact(
            storage_path=storage_path,
            duration_seconds=self.text_preparer.estimate_duration(text),
            file_size_bytes=len(audio),
            text_char_count=len(text),
            chunk_count=len(chunks),
        )

    def _combine(self, segments: list[bytes]) -> bytes:
        if len(segments) == 1:
            return segments[0]
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as handle:
            output_path = Path(handle.name)
        try:
            concatenate_mp3_files(segments, output_path)
            return output_path.read_bytes()
        finally:
            output_path.unlink(missing_ok=True)
