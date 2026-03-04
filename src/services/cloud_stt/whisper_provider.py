"""OpenAI Whisper cloud STT provider.

Uses OpenAI's Whisper API for raw transcription. Returns unclean transcripts
(cleaned=False), so the separate VOICE_CLEANUP step should be used.
"""

import asyncio
import io
import wave
from collections.abc import AsyncIterator

from src.services.cloud_stt.models import TranscriptResult, TranscriptResultType
from src.services.cloud_stt.provider import CloudSTTProvider
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Whisper processes in ~4-second chunks (128KB at 16kHz 16-bit mono)
_WHISPER_CHUNK_SIZE = 128000


class WhisperSTTProvider(CloudSTTProvider):
    """OpenAI Whisper-based cloud STT.

    Uses OpenAI's transcription API to convert audio to text.
    Returns raw transcripts without cleanup (cleaned=False).
    """

    def __init__(self, model_id: str = "whisper-1", api_key: str | None = None):
        self._model_id = model_id
        self._api_key = api_key
        self._language = "auto"
        self._audio_buffer: bytearray = bytearray()
        self._results_queue: asyncio.Queue[TranscriptResult] = asyncio.Queue()
        self._running = False
        self._process_task: asyncio.Task | None = None  # type: ignore[type-arg]

    async def start_stream(self, language: str = "auto") -> None:
        self._language = language
        self._audio_buffer = bytearray()
        self._running = True
        logger.debug("Whisper STT stream started (model=%s, lang=%s)", self._model_id, language)

    async def send_audio(self, chunk: bytes) -> None:
        if not self._running:
            return
        self._audio_buffer.extend(chunk)

        if len(self._audio_buffer) >= _WHISPER_CHUNK_SIZE:
            audio_data = bytes(self._audio_buffer)
            self._audio_buffer = bytearray()
            self._process_task = asyncio.create_task(self._transcribe(audio_data))

    def get_results(self) -> AsyncIterator[TranscriptResult]:
        return self._result_iterator()

    async def _result_iterator(self) -> AsyncIterator[TranscriptResult]:
        while self._running or not self._results_queue.empty():
            try:
                yield await asyncio.wait_for(self._results_queue.get(), timeout=0.1)
            except TimeoutError:
                continue

    async def stop_stream(self) -> None:
        self._running = False

        if self._audio_buffer:
            audio_data = bytes(self._audio_buffer)
            self._audio_buffer = bytearray()
            await self._transcribe(audio_data)

        if self._process_task and not self._process_task.done():
            await self._process_task

        logger.debug("Whisper STT stream stopped")

    async def _transcribe(self, audio_data: bytes) -> None:
        """Send audio to OpenAI Whisper API for transcription."""
        try:
            from openai import OpenAI

            client = OpenAI(api_key=self._api_key) if self._api_key else OpenAI()

            # Whisper API expects a WAV file, so wrap PCM data
            wav_buffer = _pcm_to_wav(audio_data)

            kwargs: dict = {"model": self._model_id, "file": ("audio.wav", wav_buffer, "audio/wav")}
            if self._language != "auto":
                # Whisper uses ISO 639-1 codes (e.g., "en" not "en-US")
                kwargs["language"] = self._language.split("-")[0]

            response = await asyncio.to_thread(
                client.audio.transcriptions.create,
                **kwargs,
            )

            text = response.text.strip() if response.text else ""
            if text:
                await self._results_queue.put(
                    TranscriptResult(
                        type=TranscriptResultType.FINAL,
                        text=text,
                        cleaned=False,  # Whisper returns raw transcription
                    )
                )
        except Exception as e:
            logger.error("Whisper STT transcription error: %s", e)
            await self._results_queue.put(
                TranscriptResult(
                    type=TranscriptResultType.ERROR,
                    text=f"Transcription error: {e}",
                )
            )


def _pcm_to_wav(pcm_data: bytes, sample_rate: int = 16000, channels: int = 1) -> io.BytesIO:
    """Wrap raw PCM 16-bit data in a WAV container."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 16-bit = 2 bytes
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    buf.seek(0)
    return buf
