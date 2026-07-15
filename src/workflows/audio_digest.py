"""Durable audio-digest workflow."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy.orm import Session

from src.contracts.workflow_models import AudioDigestRequest
from src.delivery.tts_service import TTSService
from src.models.audio_digest import AudioDigest, AudioDigestStatus
from src.models.digest import Digest
from src.models.jobs import ResourceReference
from src.models.podcast import VoiceProvider
from src.services.audio_digest_service import AudioDigestService
from src.services.operation_service import OperationService
from src.storage.database import get_db
from src.workflows.resource import recover_owned_resource

_PROVIDERS = {
    "openai": VoiceProvider.OPENAI_TTS,
    "openai_tts": VoiceProvider.OPENAI_TTS,
    "elevenlabs": VoiceProvider.ELEVENLABS,
    "google": VoiceProvider.GOOGLE_TTS,
    "google_tts": VoiceProvider.GOOGLE_TTS,
    "aws_polly": VoiceProvider.AWS_POLLY,
}


class AudioDigestWorkflow:
    """Reserve, generate, store, and attach one digest narration."""

    def __init__(
        self,
        *,
        operation_service: OperationService | Any | None = None,
        audio_service_factory: Callable[[str], AudioDigestService | Any] | None = None,
        voice_resolver: Callable[[str], str] | None = None,
        session_factory: Callable[[], AbstractContextManager[Session]] = get_db,
    ) -> None:
        self.operations = operation_service or OperationService()
        self.audio_service_factory = audio_service_factory or self._service_for
        self.voice_resolver = voice_resolver or self._resolve_voice
        self.session_factory = session_factory

    async def execute(self, operation_id: str | int, request: AudioDigestRequest) -> AudioDigest:
        existing = await self._existing(operation_id)
        if existing is not None and existing.status == AudioDigestStatus.COMPLETED:
            await self._attach_result(operation_id, existing)
            return existing
        with self.session_factory() as db:
            digest = db.get(Digest, request.digest_id)
            if digest is None:
                raise ValueError(f"Digest {request.digest_id} not found")
            if existing is None:
                record = AudioDigest(
                    operation_id=int(operation_id),
                    digest_id=request.digest_id,
                    voice=request.voice,
                    speed=request.speed,  # type: ignore[arg-type]
                    provider=request.provider,
                    status=AudioDigestStatus.PROCESSING,
                )
                db.add(record)
                db.commit()
                db.refresh(record)
                record_id = cast(int, record.id)
            else:
                loaded = db.get(AudioDigest, cast(int, existing.id))
                if loaded is None:
                    raise RuntimeError("Attached audio digest resource does not exist")
                record = loaded
                record.status = AudioDigestStatus.PROCESSING
                record.error_message = None
                db.commit()
                record_id = cast(int, record.id)
            db.refresh(digest)
            db.expunge(digest)
        if existing is None:
            await self.operations.attach_resource(
                operation_id,
                ResourceReference(
                    type="audio_digest",
                    id=str(record_id),
                    url=f"/api/v1/audio-digests/{record_id}",
                ),
            )

        try:
            await self.operations.update_progress(operation_id, 20, "Generating audio digest")
            artifact = await self.audio_service_factory(request.provider).generate(
                digest,
                audio_digest_id=record_id,
                voice_id=self.voice_resolver(request.voice),
                speed=request.speed,
            )
            with self.session_factory() as db:
                loaded = db.get(AudioDigest, record_id)
                if loaded is None:
                    raise RuntimeError(f"Reserved audio digest {record_id} disappeared")
                record = loaded
                record.audio_url = artifact.storage_path
                record.duration_seconds = artifact.duration_seconds  # type: ignore[assignment]
                record.file_size_bytes = artifact.file_size_bytes
                record.text_char_count = artifact.text_char_count
                record.chunk_count = artifact.chunk_count
                record.status = AudioDigestStatus.COMPLETED
                record.completed_at = datetime.now(UTC)
                db.commit()
                db.refresh(record)
        except Exception as exc:
            with self.session_factory() as db:
                failed = db.get(AudioDigest, record_id)
                if failed is not None:
                    failed.status = AudioDigestStatus.FAILED
                    failed.error_message = str(exc)
                    db.commit()
            raise
        await self._attach_result(operation_id, record)
        return cast(AudioDigest, record)

    async def _existing(self, operation_id: str | int) -> AudioDigest | None:
        return await recover_owned_resource(
            operations=self.operations,
            session_factory=self.session_factory,
            model=AudioDigest,
            operation_id=operation_id,
            resource_type="audio_digest",
            resource_url=lambda record_id: f"/api/v1/audio-digests/{record_id}",
        )

    async def _attach_result(self, operation_id: str | int, record: AudioDigest) -> None:
        await self.operations.attach_result(operation_id, {"audio_digest_id": record.id})
        await self.operations.update_progress(operation_id, 100, "Audio digest complete")

    @staticmethod
    def _service_for(provider: str) -> AudioDigestService:
        try:
            voice_provider = _PROVIDERS[provider]
        except KeyError as exc:
            raise ValueError(f"Unsupported audio digest provider: {provider}") from exc
        return AudioDigestService(tts=TTSService(provider=voice_provider))

    @staticmethod
    def _resolve_voice(voice: str) -> str:
        from src.config import settings

        return settings.get_audio_digest_voice_id(voice)
