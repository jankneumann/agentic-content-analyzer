"""Deepgram cloud STT provider.

Uses Deepgram's streaming WebSocket API for real-time transcription.
Returns raw transcripts (cleaned=False).
"""

import asyncio
from collections.abc import AsyncIterator

from src.services.cloud_stt.models import TranscriptResult, TranscriptResultType
from src.services.cloud_stt.provider import CloudSTTProvider
from src.utils.logging import get_logger

logger = get_logger(__name__)


class DeepgramSTTProvider(CloudSTTProvider):
    """Deepgram-based cloud STT with real-time streaming.

    Uses Deepgram's WebSocket API for low-latency transcription.
    Returns raw transcripts without cleanup (cleaned=False).
    """

    def __init__(self, model_id: str = "deepgram-nova-3", api_key: str | None = None):
        self._model_id = model_id
        self._api_key = api_key
        self._language = "auto"
        self._audio_buffer: bytearray = bytearray()
        self._results_queue: asyncio.Queue[TranscriptResult] = asyncio.Queue()
        self._running = False
        self._ws = None  # Deepgram WebSocket connection
        self._listen_task: asyncio.Task | None = None  # type: ignore[type-arg]

    async def start_stream(self, language: str = "auto") -> None:
        self._language = language
        self._audio_buffer = bytearray()
        self._running = True

        try:
            from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents

            client = DeepgramClient(api_key=self._api_key)
            options = LiveOptions(
                model="nova-3",
                language=language.split("-")[0] if language != "auto" else "en",
                encoding="linear16",
                sample_rate=16000,
                channels=1,
                interim_results=True,
                punctuate=True,
            )

            self._ws = client.listen.live.v("1")

            # Register event handlers
            self._ws.on(LiveTranscriptionEvents.Transcript, self._on_transcript)
            self._ws.on(LiveTranscriptionEvents.Error, self._on_error)

            await asyncio.to_thread(self._ws.start, options)
            logger.debug("Deepgram STT stream started (lang=%s)", language)

        except ImportError:
            logger.error("deepgram-sdk not installed. Install with: pip install deepgram-sdk")
            await self._results_queue.put(
                TranscriptResult(
                    type=TranscriptResultType.ERROR,
                    text="Deepgram SDK not installed",
                )
            )
            self._running = False
        except Exception as e:
            logger.error("Deepgram STT start error: %s", e)
            await self._results_queue.put(
                TranscriptResult(
                    type=TranscriptResultType.ERROR,
                    text=f"Failed to start Deepgram stream: {e}",
                )
            )
            self._running = False

    def _on_transcript(self, _ws: object, result: object, **_kwargs: object) -> None:
        """Handle transcript results from Deepgram."""
        try:
            channel = result.channel  # type: ignore[attr-defined]
            alternatives = channel.alternatives
            if not alternatives:
                return

            text = alternatives[0].transcript.strip()
            if not text:
                return

            is_final = result.is_final  # type: ignore[attr-defined]
            confidence = alternatives[0].confidence

            # Use asyncio-safe queue put
            self._results_queue.put_nowait(
                TranscriptResult(
                    type=TranscriptResultType.FINAL if is_final else TranscriptResultType.INTERIM,
                    text=text,
                    cleaned=False,
                    confidence=confidence if is_final else None,
                )
            )
        except Exception as e:
            logger.error("Deepgram transcript parse error: %s", e)

    def _on_error(self, _ws: object, error: object, **_kwargs: object) -> None:
        """Handle errors from Deepgram."""
        logger.error("Deepgram STT error: %s", error)
        self._results_queue.put_nowait(
            TranscriptResult(
                type=TranscriptResultType.ERROR,
                text=f"Deepgram error: {error}",
            )
        )

    async def send_audio(self, chunk: bytes) -> None:
        if not self._running or not self._ws:
            return
        try:
            await asyncio.to_thread(self._ws.send, chunk)
        except Exception as e:
            logger.error("Deepgram send error: %s", e)

    def get_results(self) -> AsyncIterator[TranscriptResult]:
        return self._result_iterator()

    async def _result_iterator(self) -> AsyncIterator[TranscriptResult]:
        while self._running or not self._results_queue.empty():
            try:
                result = await asyncio.wait_for(self._results_queue.get(), timeout=0.1)
                yield result
            except TimeoutError:
                continue

    async def stop_stream(self) -> None:
        self._running = False

        if self._ws:
            try:
                await asyncio.to_thread(self._ws.finish)
            except Exception as e:
                logger.debug("Deepgram finish error: %s", e)
            self._ws = None

        logger.debug("Deepgram STT stream stopped")
