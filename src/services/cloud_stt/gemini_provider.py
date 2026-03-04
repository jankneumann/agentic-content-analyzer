"""Gemini cloud STT provider.

Uses Google's Gemini API with native audio input for transcription + cleanup
in a single API call. Returns cleaned transcripts (cleaned=True).
"""

import asyncio
from collections.abc import AsyncIterator

from src.services.cloud_stt.models import TranscriptResult, TranscriptResultType
from src.services.cloud_stt.prompts import GEMINI_TRANSCRIPTION_CLEANUP_PROMPT
from src.services.cloud_stt.provider import CloudSTTProvider
from src.utils.logging import get_logger

logger = get_logger(__name__)


class GeminiSTTProvider(CloudSTTProvider):
    """Gemini-based cloud STT with built-in transcript cleanup.

    Uses Google's generative AI SDK to send audio + cleanup prompt,
    receiving a cleaned transcript in a single API call.
    """

    def __init__(self, model_id: str = "gemini-2.5-flash", api_key: str | None = None):
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
        logger.debug("Gemini STT stream started (model=%s, lang=%s)", self._model_id, language)

    async def send_audio(self, chunk: bytes) -> None:
        if not self._running:
            return
        self._audio_buffer.extend(chunk)

        # Process accumulated audio in chunks (~2 seconds at 16kHz 16-bit mono = 64KB)
        if len(self._audio_buffer) >= 64000:
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

        # Process any remaining audio
        if self._audio_buffer:
            audio_data = bytes(self._audio_buffer)
            self._audio_buffer = bytearray()
            await self._transcribe(audio_data)

        # Wait for any pending processing
        if self._process_task and not self._process_task.done():
            await self._process_task

        logger.debug("Gemini STT stream stopped")

    async def _transcribe(self, audio_data: bytes) -> None:
        """Send audio to Gemini API for transcription + cleanup."""
        try:
            import google.generativeai as genai

            if self._api_key:
                genai.configure(api_key=self._api_key)

            model = genai.GenerativeModel(self._model_id)

            # Build prompt with language hint
            prompt = GEMINI_TRANSCRIPTION_CLEANUP_PROMPT
            if self._language != "auto":
                prompt += f"\n\nThe audio is in {self._language}."

            # Send audio + prompt to Gemini
            response = await asyncio.to_thread(
                model.generate_content,
                [
                    prompt,
                    {
                        "mime_type": "audio/pcm",
                        "data": audio_data,
                    },
                ],
            )

            text = response.text.strip() if response.text else ""
            if text:
                await self._results_queue.put(
                    TranscriptResult(
                        type=TranscriptResultType.FINAL,
                        text=text,
                        cleaned=True,  # Gemini cleans up via prompt
                    )
                )
        except Exception as e:
            logger.error("Gemini STT transcription error: %s", e)
            await self._results_queue.put(
                TranscriptResult(
                    type=TranscriptResultType.ERROR,
                    text=f"Transcription error: {e}",
                )
            )
